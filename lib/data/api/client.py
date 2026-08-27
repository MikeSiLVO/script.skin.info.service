"""Robust HTTP client with connection pooling, retry, and abort support.

Uses requests library with:
- Session-based connection pooling
- Configurable automatic retry with exponential backoff
- Separate connect/read timeouts
- Abort flag integration for cancellation
- Rate limiting with sliding window
- Both GET and POST support
"""
from __future__ import annotations

import xbmc
import gzip
import socket
import time
import threading
import weakref
from typing import Optional, Dict, Any, Tuple, List
from collections import deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from lib.kodi.client import log, ADDON

_USER_AGENT = f"script.skin.info.service/{ADDON.getAddonInfo('version')}"


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse a Retry-After header (integer-seconds form only)."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class RateLimitHit(Exception):
    """Exception raised when a provider's API rate limit is reached.

    `retry_after_seconds` carries the server's Retry-After header value if present;
    callers can use it to schedule precise pause durations.
    """
    def __init__(self, provider: str, retry_after_seconds: Optional[float] = None):
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit reached for {provider}")


class RetryableError(Exception):
    """Raised for transient errors that may succeed on retry (timeouts, connection errors)."""
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider}: {reason}")


class RateLimiter:
    """Sliding window rate limiter for proactive rate limiting."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: deque = deque()
        self._lock = threading.Lock()

    def wait_if_needed(self, service_name: str = "API") -> None:
        """Wait if rate limit would be exceeded."""
        while True:
            now = time.time()
            with self._lock:
                while self.requests and now - self.requests[0] >= self.window:
                    self.requests.popleft()
                count = len(self.requests)
                if count < self.max_requests:
                    self.requests.append(now)
                    return
                oldest = self.requests[0]

            wait_time = self.window - (now - oldest) + 0.1
            if wait_time <= 0:
                continue

            log(
                "API",
                f"{service_name}: Rate limit ({count}/{self.max_requests}), "
                f"waiting {wait_time:.1f}s"
            )
            monitor = xbmc.Monitor()
            if monitor.waitForAbort(wait_time):
                return


class AbortRequested(Exception):
    """Raised when abort flag is set."""
    pass


# a blocked read cannot check its own abort flag, so a watcher closes the socket from outside
_OPEN_CONNS: "weakref.WeakSet" = weakref.WeakSet()
_CONN_LOCK = threading.Lock()
_CONN_WATCHER_STARTED = False
_WATCHER_IDLE_POLLS = 25
# per-thread cancel token for the in-flight request, read by the connection on connect
_REQUEST_TOKEN = threading.local()
# per-thread wall-clock limit for the in-flight request, enforced by the watcher because a
# thread blocked inside a chunk read cannot check anything itself
_REQUEST_DEADLINE = threading.local()


def _stamp_request(abort_flag, deadline_seconds: Optional[float] = None) -> None:
    """Publish this thread's cancel token and wall-clock limit for the connection to pick up.

    Always sets both: these are thread-locals, and a deadline left over from an earlier
    streamed request would have the watcher kill the next healthy connection instantly.
    """
    _REQUEST_TOKEN.token = abort_flag
    _REQUEST_DEADLINE.value = (
        time.monotonic() + deadline_seconds if deadline_seconds else None
    )


def _close_conn(conn) -> bool:
    """Shut down one connection's socket, untracking it only on success."""
    shut = False
    sock = getattr(conn, "sock", None)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
            shut = True
        except OSError:
            pass

    if not shut:
        # mid-handshake the socket is detached (fd -1), so use the dup taken at connect
        raw = getattr(conn, "_raw_dup", None)
        if raw is not None:
            try:
                raw.shutdown(socket.SHUT_RDWR)
                shut = True
            except OSError:
                pass

    if shut:
        with _CONN_LOCK:
            _OPEN_CONNS.discard(conn)
    return shut


def _close_all_conns() -> None:
    """Shut down every tracked socket, unblocking any stalled read on abort."""
    with _CONN_LOCK:
        conns = list(_OPEN_CONNS)
    if conns:
        log("API", f"shutdown: closing {len(conns)} open connection(s)", xbmc.LOGDEBUG)
    for conn in conns:
        _close_conn(conn)


def _conn_watcher() -> None:
    """Close a connection when its request is cancelled; close all on Kodi abort."""
    global _CONN_WATCHER_STARTED
    monitor = xbmc.Monitor()
    idle_polls = 0

    while not monitor.abortRequested():
        with _CONN_LOCK:
            conns = list(_OPEN_CONNS)

        now = time.monotonic()
        for conn in conns:
            token = getattr(conn, "_cancel_token", None)
            deadline = getattr(conn, "_deadline", None)
            cancelled = token is not None and token.is_requested()
            expired = deadline is not None and now > deadline
            if cancelled or expired:
                _close_conn(conn)

        idle_polls = 0 if conns else idle_polls + 1

        # Kodi cannot end the interpreter while a thread lives; _register_conn restarts this
        if idle_polls >= _WATCHER_IDLE_POLLS:
            with _CONN_LOCK:
                if not _OPEN_CONNS:
                    _CONN_WATCHER_STARTED = False
                    return
            idle_polls = 0

        if monitor.waitForAbort(0.2):
            break
    # repeat briefly to catch a request that connects mid-shutdown
    for _ in range(4):
        _close_all_conns()
        xbmc.sleep(100)


def _ensure_conn_watcher() -> None:
    """Start the connection watcher once."""
    global _CONN_WATCHER_STARTED
    with _CONN_LOCK:
        if _CONN_WATCHER_STARTED:
            return
        _CONN_WATCHER_STARTED = True
    threading.Thread(target=_conn_watcher, daemon=True).start()


def _register_conn(conn) -> None:
    """Track a live connection so the watcher can close its socket on abort."""
    with _CONN_LOCK:
        _OPEN_CONNS.add(conn)
    _ensure_conn_watcher()


def _unregister_conn(conn) -> None:
    """Drop a connection from the tracker when it closes."""
    with _CONN_LOCK:
        _OPEN_CONNS.discard(conn)


class _TrackedConnection(HTTPConnection):
    """Registers the connection so the watcher can close its socket for abort."""

    _raw_dup: Optional[socket.socket] = None
    _cancel_token: Any = None
    _deadline: Optional[float] = None

    def _tag_request(self) -> None:
        """Copy this thread's cancel token and deadline onto the connection."""
        self._cancel_token = getattr(_REQUEST_TOKEN, "token", None)
        self._deadline = getattr(_REQUEST_DEADLINE, "value", None)

    def _drop_raw_dup(self) -> None:
        """Release the duplicated socket handle."""
        raw, self._raw_dup = self._raw_dup, None
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass

    def request(self, *args, **kwargs):
        """Retag with the current request's token (covers keep-alive reuse), then send."""
        self._tag_request()
        _register_conn(self)
        return super().request(*args, **kwargs)

    def _new_conn(self):
        """Hold a dup of the raw socket: ssl wrapping detaches the original, leaving fd -1."""
        sock = super()._new_conn()
        self._drop_raw_dup()
        try:
            self._raw_dup = sock.dup()
        except OSError:
            self._raw_dup = None
        return sock

    def connect(self) -> None:
        """Register before connecting; a stalled handshake is invisible to the watcher after."""
        self._tag_request()
        _register_conn(self)
        super().connect()

    def close(self) -> None:
        """Untrack and clear the request tags, so a later reconnect starts on a clean slate."""
        _unregister_conn(self)
        self._cancel_token = None
        self._deadline = None
        self._drop_raw_dup()
        super().close()


class _TrackedHTTPConnection(_TrackedConnection):
    """HTTP connection that registers its socket for abort-closing."""


class _TrackedHTTPSConnection(_TrackedConnection, HTTPSConnection):
    """HTTPS connection that registers its socket for abort-closing."""


class _TrackedPool(HTTPConnectionPool):
    """Pool that untracks a connection when it goes back in the pool."""

    def _put_conn(self, conn) -> None:
        """Untrack on return to the pool: an idle pooled socket has no blocked read to break."""
        if conn is not None:
            _unregister_conn(conn)
        return super()._put_conn(conn)


class _TrackedHTTPConnectionPool(_TrackedPool):
    """Pool that hands out tracked HTTP connections."""

    ConnectionCls = _TrackedHTTPConnection  # type: ignore[assignment]


class _TrackedHTTPSConnectionPool(_TrackedPool, HTTPSConnectionPool):
    """Pool that hands out tracked HTTPS connections."""

    ConnectionCls = _TrackedHTTPSConnection  # type: ignore[assignment]


class _TrackedAdapter(HTTPAdapter):
    """Adapter whose connections register their socket so the watcher can close them."""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": _TrackedHTTPConnectionPool,
            "https": _TrackedHTTPSConnectionPool,
        }


class ApiSession:
    """HTTP client with connection pooling, retry, rate limiting, and abort support.

    Automatic retry with exponential backoff for server errors.
    429 raises RateLimitHit for caller to handle.
    """

    def __init__(
        self,
        service_name: str,
        base_url: str = "",
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        timeout: Tuple[float, float] = (5.0, 10.0),
        rate_limit: Optional[Tuple[int, float]] = None,
        retry_statuses: Optional[List[int]] = None,
        default_headers: Optional[Dict[str, str]] = None,
        connect_retries: int = 0,
        read_retries: int = 0
    ):
        """Initialize API session.

        Args:
            backoff_factor: Exponential multiplier (0.5 = 0.5s, 1s, 2s, ...).
            timeout: (connect_timeout, read_timeout) in seconds.
            rate_limit: Optional (max_requests, window_seconds) for proactive rate limiting.
            retry_statuses: HTTP status codes to retry (default: [500, 502, 503, 504]).
            connect_retries: Retries on connection errors (default 0 = fail fast).
            read_retries: Retries on read errors/timeouts (default 0 = fail fast).
        """
        self.service_name = service_name
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.rate_limiter: Optional[RateLimiter] = None
        if rate_limit:
            self.rate_limiter = RateLimiter(rate_limit[0], rate_limit[1])

        if retry_statuses is None:
            retry_statuses = [500, 502, 503, 504]

        self.retry_statuses = retry_statuses

        self.session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=retry_statuses,
            allowed_methods=["GET", "POST", "HEAD", "OPTIONS"],
            raise_on_status=False,
            connect=connect_retries,
            read=read_retries,
            # urllib3 sleeps Retry-After uncapped inside urlopen, hiding the block
            respect_retry_after_header=False,
        )

        adapter = _TrackedAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if default_headers:
            self.session.headers.update(default_headers)

        self.session.headers["User-Agent"] = _USER_AGENT

        self._tls = threading.local()

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}" if self.base_url else endpoint

    def _check_abort(self, abort_flag) -> None:
        """Check abort flag and raise if requested."""
        if abort_flag and abort_flag.is_requested():
            raise AbortRequested("Request aborted by user")

    def _get_capped(self, url, params, headers, request_timeout, cap, abort_flag):
        """GET that polls abort while reading the body, so a request in flight at
        shutdown can be dropped (a blocked read can't otherwise be interrupted).

        raw.read1 returns whatever has arrived, so a big response avoids the
        byte-by-byte cost of iter_content(1); Accept-Encoding is pinned to gzip so the
        body decodes with stdlib. The API's read timeout applies; cap backstops a
        runaway. Falls back to iter_content(1) where read1 is missing.
        """
        deadline = time.time() + cap
        req_headers = dict(headers or {})
        req_headers["Accept-Encoding"] = "gzip"
        response = self.session.get(
            url, params=params, headers=req_headers, timeout=request_timeout, stream=True,
        )
        try:
            raw = response.raw
            if hasattr(raw, "read1"):
                chunks, gunzip = iter(lambda: raw.read1(65536), b""), True
            else:
                chunks, gunzip = response.iter_content(chunk_size=1), False

            body = bytearray()
            last_poll = 0.0
            for chunk in chunks:
                body.extend(chunk)
                now = time.time()
                if now > deadline:
                    raise RetryableError(self.service_name, "request deadline exceeded")
                if now - last_poll >= 0.1:
                    last_poll = now
                    if abort_flag and abort_flag.is_requested():
                        raise AbortRequested("Request aborted")

            response._content = self._gunzip(response, bytes(body)) if gunzip else bytes(body)
            return response
        finally:
            response.close()

    @staticmethod
    def _gunzip(response, body):
        """Decompress a pinned-gzip body; raw bytes on identity or a bad gzip stream."""
        if body and response.headers.get("Content-Encoding", "").lower() == "gzip":
            try:
                return gzip.decompress(body)
            except OSError:
                pass
        return body

    def _handle_response(
        self,
        response: requests.Response,
        abort_flag=None
    ) -> Optional[Dict[str, Any]]:
        """Handle response, raising appropriate exceptions. Returns JSON dict, or None on 404.

        Raises:
            RateLimitHit: On 429 (caller decides what to do).
            RetryableError: On retryable failures after exhausting retries.
        """
        self._check_abort(abort_flag)

        if response.status_code == 429:
            raise RateLimitHit(
                self.service_name, _parse_retry_after(response.headers.get("Retry-After"))
            )

        if response.status_code == 404:
            log("API", f"{self.service_name}: 404 Not Found", xbmc.LOGDEBUG)
            return None

        if response.status_code >= 400:
            log(
                "API",
                f"{self.service_name}: HTTP {response.status_code} - {response.reason}",
                xbmc.LOGWARNING
            )
            if response.status_code in self.retry_statuses:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is not None:
                    raise RateLimitHit(self.service_name, retry_after)
                raise RetryableError(self.service_name, f"HTTP {response.status_code}")
            return None

        try:
            return response.json()
        except ValueError:
            log("API", f"{self.service_name}: Invalid JSON response", xbmc.LOGWARNING)
            return None

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make GET request. Returns JSON response dict, or None on error.

        Raises:
            RateLimitHit: On 429 response.
            RetryableError: On retryable failures.
            AbortRequested: If abort flag is set.
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        cap = getattr(abort_flag, 'max_request_seconds', None)
        _stamp_request(abort_flag, cap)
        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            log("API", f"{self.service_name}: GET {url.split('?')[0]}", xbmc.LOGDEBUG)

            start = time.time()
            if cap:
                response = self._get_capped(
                    url, params, headers, request_timeout, cap, abort_flag
                )
            else:
                response = self.session.get(
                    url, params=params, headers=headers, timeout=request_timeout
                )

            elapsed = time.time() - start

            if elapsed > 5.0:
                log(
                    "API",
                    f"{self.service_name}: Response took {elapsed:.1f}s "
                    f"(status={response.status_code})",
                    xbmc.LOGWARNING,
                )

            return self._handle_response(response, abort_flag)

        except AbortRequested:
            raise
        except RateLimitHit:
            raise
        except RetryableError:
            raise
        except requests.exceptions.Timeout as e:
            log("API", f"{self.service_name}: Request timed out", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "timeout") from e
        except requests.exceptions.ConnectionError as e:
            log("API", f"{self.service_name}: Connection error: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "connection error") from e
        except Exception as e:
            log("API", f"{self.service_name}: Request failed: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, str(e)) from e

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None,
    ) -> Optional[Any]:
        """Make POST request. Returns JSON response (dict or list), or None on error.

        json_data sets Content-Type: application/json automatically;
        data and json_data are mutually exclusive.

        Raises:
            RateLimitHit: On 429 response.
            RetryableError: On retryable failures.
            AbortRequested: If abort flag is set.
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        _stamp_request(abort_flag, getattr(abort_flag, 'max_request_seconds', None))
        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            log("API", f"{self.service_name}: POST {url.split('?')[0]}", xbmc.LOGDEBUG)

            response = self.session.post(
                url,
                json=json_data,
                data=data,
                params=params,
                headers=headers,
                timeout=request_timeout
            )

            return self._handle_response(response, abort_flag)

        except AbortRequested:
            raise
        except RateLimitHit:
            raise
        except RetryableError:
            raise
        except requests.exceptions.Timeout as e:
            log("API", f"{self.service_name}: Request timed out", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "timeout") from e
        except requests.exceptions.ConnectionError as e:
            log("API", f"{self.service_name}: Connection error: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "connection error") from e
        except Exception as e:
            log("API", f"{self.service_name}: Request failed: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, str(e)) from e

    def get_raw(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None,
        stream: bool = False,
        deadline_seconds: Optional[float] = None,
    ) -> Optional[requests.Response]:
        """Make GET request returning raw Response object.

        Useful for streaming downloads or non-JSON responses.

        Raises:
            RateLimitHit: On 429 response.
            RetryableError: On retryable failures.
            AbortRequested: If abort flag is set.
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        _stamp_request(abort_flag, deadline_seconds)
        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=request_timeout,
                stream=stream
            )

            # A streamed response pins its pooled connection until closed.
            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                response.close()
                raise RateLimitHit(self.service_name, retry_after)

            if response.status_code >= 400:
                log(
                    "API",
                    f"{self.service_name}: HTTP {response.status_code}",
                    xbmc.LOGWARNING
                )
                response.close()
                return None

            return response

        except (AbortRequested, RateLimitHit, RetryableError):
            raise
        except requests.exceptions.Timeout as e:
            raise RetryableError(self.service_name, "timeout") from e
        except requests.exceptions.ConnectionError as e:
            raise RetryableError(self.service_name, f"connection error: {e}") from e
        except Exception as e:
            raise RetryableError(self.service_name, str(e)) from e

    def head(
        self,
        endpoint: str,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None,
    ) -> Optional[requests.Response]:
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        _stamp_request(abort_flag, getattr(abort_flag, 'max_request_seconds', None))
        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            response = self.session.head(
                url,
                timeout=request_timeout,
                allow_redirects=True
            )

            if response.status_code == 429:
                raise RateLimitHit(
                self.service_name, _parse_retry_after(response.headers.get("Retry-After"))
            )

            if response.status_code >= 400:
                log(
                    "API",
                    f"{self.service_name}: HEAD {response.status_code}",
                    xbmc.LOGWARNING
                )
                return None

            return response

        except (AbortRequested, RateLimitHit, RetryableError):
            raise
        except requests.exceptions.Timeout as e:
            raise RetryableError(self.service_name, "timeout") from e
        except requests.exceptions.ConnectionError as e:
            raise RetryableError(self.service_name, f"connection error: {e}") from e
        except Exception as e:
            raise RetryableError(self.service_name, str(e)) from e

    def close(self) -> None:
        """Close the session and release connections."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False
