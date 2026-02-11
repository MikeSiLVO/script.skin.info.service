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
import time
from typing import Optional, Dict, Any, Tuple, List
from collections import deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from lib.kodi.client import log
from lib.rating.source import RetryableError, RateLimitHit


class RateLimiter:
    """Sliding window rate limiter for proactive rate limiting."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: deque = deque()

    def wait_if_needed(self, service_name: str = "API") -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()

        while self.requests and now - self.requests[0] >= self.window:
            self.requests.popleft()

        if len(self.requests) >= self.max_requests:
            oldest = self.requests[0]
            wait_time = self.window - (now - oldest) + 0.1
            if wait_time > 0:
                log(
                    "API",
                    f"{service_name}: Rate limit ({len(self.requests)}/{self.max_requests}), "
                    f"waiting {wait_time:.1f}s"
                )
                monitor = xbmc.Monitor()
                monitor.waitForAbort(wait_time)
                now = time.time()
                while self.requests and now - self.requests[0] >= self.window:
                    self.requests.popleft()

        self.requests.append(now)


class AbortRequested(Exception):
    """Raised when abort flag is set."""
    pass


class ApiSession:
    """
    Robust HTTP client with connection pooling, retry, and abort support.

    Features:
    - Connection pooling via requests.Session
    - Automatic retry with exponential backoff for server errors
    - Separate connect/read timeouts
    - Abort flag integration for cancellation
    - Optional proactive rate limiting
    - GET and POST support with JSON
    - 429 raises RateLimitHit for caller to handle
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
        default_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize API session.

        Args:
            service_name: Name for logging (e.g., "TMDB", "MDBList")
            base_url: Optional base URL prepended to all requests
            max_retries: Maximum retry attempts for retryable errors
            backoff_factor: Exponential backoff multiplier (0.5 = 0.5s, 1s, 2s, ...)
            timeout: Tuple of (connect_timeout, read_timeout) in seconds
            rate_limit: Optional (max_requests, window_seconds) for proactive rate limiting
            retry_statuses: HTTP status codes to retry (default: [500, 502, 503, 504])
            default_headers: Headers included in all requests
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
            connect=0,
            read=0
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if default_headers:
            self.session.headers.update(default_headers)

        self.session.headers.setdefault("User-Agent", "script.skin.info.service/2.0.0")

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}" if self.base_url else endpoint

    def _check_abort(self, abort_flag) -> None:
        """Check abort flag and raise if requested."""
        if abort_flag and abort_flag.is_requested():
            raise AbortRequested("Request aborted by user")

    def _handle_response(
        self,
        response: requests.Response,
        abort_flag=None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle response, raising appropriate exceptions.

        Returns:
            JSON dict on success, None on 404
        Raises:
            RateLimitHit: On 429 (caller decides what to do)
            RetryableError: On retryable failures after exhausting retries
        """
        self._check_abort(abort_flag)

        if response.status_code == 429:
            raise RateLimitHit(self.service_name)

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
        timeout: Optional[Tuple[float, float]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make GET request.

        Args:
            endpoint: URL or path (appended to base_url if relative)
            params: Query parameters
            headers: Additional headers for this request
            abort_flag: Optional abort flag to check for cancellation
            timeout: Override default timeout for this request

        Returns:
            JSON response dict or None on error

        Raises:
            RateLimitHit: On 429 response
            RetryableError: On retryable failures
            AbortRequested: If abort flag is set
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            log("API", f"{self.service_name}: GET {url.split('?')[0]}", xbmc.LOGDEBUG)

            start = time.time()
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=request_timeout
            )

            elapsed = time.time() - start

            if elapsed > 5.0:
                log("API", f"{self.service_name}: Response took {elapsed:.1f}s (status={response.status_code})", xbmc.LOGWARNING)

            return self._handle_response(response, abort_flag)

        except AbortRequested:
            raise
        except RateLimitHit:
            raise
        except RetryableError:
            raise
        except requests.exceptions.Timeout:
            log("API", f"{self.service_name}: Request timed out", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "timeout")
        except requests.exceptions.ConnectionError as e:
            log("API", f"{self.service_name}: Connection error: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "connection error")
        except Exception as e:
            log("API", f"{self.service_name}: Request failed: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, str(e))

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None
    ) -> Optional[Any]:
        """
        Make POST request.

        Args:
            endpoint: URL or path (appended to base_url if relative)
            json_data: JSON body (will set Content-Type: application/json)
            data: Raw body data (mutually exclusive with json_data)
            params: Query parameters
            headers: Additional headers for this request
            abort_flag: Optional abort flag to check for cancellation
            timeout: Override default timeout for this request

        Returns:
            JSON response (dict or list) or None on error

        Raises:
            RateLimitHit: On 429 response
            RetryableError: On retryable failures
            AbortRequested: If abort flag is set
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

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
        except requests.exceptions.Timeout:
            log("API", f"{self.service_name}: Request timed out", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "timeout")
        except requests.exceptions.ConnectionError as e:
            log("API", f"{self.service_name}: Connection error: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, "connection error")
        except Exception as e:
            log("API", f"{self.service_name}: Request failed: {e}", xbmc.LOGWARNING)
            raise RetryableError(self.service_name, str(e))

    def get_raw(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None,
        stream: bool = False
    ) -> Optional[requests.Response]:
        """
        Make GET request returning raw Response object.

        Useful for streaming downloads or non-JSON responses.

        Args:
            endpoint: URL or path
            params: Query parameters
            headers: Additional headers
            abort_flag: Optional abort flag
            timeout: Override default timeout
            stream: If True, don't download content immediately

        Returns:
            Response object or None on error

        Raises:
            RateLimitHit: On 429 response
            RetryableError: On retryable failures
            AbortRequested: If abort flag is set
        """
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

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

            if response.status_code == 429:
                raise RateLimitHit(self.service_name)

            if response.status_code >= 400:
                log(
                    "API",
                    f"{self.service_name}: HTTP {response.status_code}",
                    xbmc.LOGWARNING
                )
                return None

            return response

        except (AbortRequested, RateLimitHit, RetryableError):
            raise
        except requests.exceptions.Timeout:
            raise RetryableError(self.service_name, "timeout")
        except requests.exceptions.ConnectionError as e:
            raise RetryableError(self.service_name, f"connection error: {e}")
        except Exception as e:
            raise RetryableError(self.service_name, str(e))

    def head(
        self,
        endpoint: str,
        abort_flag=None,
        timeout: Optional[Tuple[float, float]] = None
    ) -> Optional[requests.Response]:
        self._check_abort(abort_flag)

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        url = self._build_url(endpoint)
        request_timeout = timeout or self.timeout

        try:
            response = self.session.head(
                url,
                timeout=request_timeout,
                allow_redirects=True
            )

            if response.status_code == 429:
                raise RateLimitHit(self.service_name)

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
        except requests.exceptions.Timeout:
            raise RetryableError(self.service_name, "timeout")
        except requests.exceptions.ConnectionError as e:
            raise RetryableError(self.service_name, f"connection error: {e}")
        except Exception as e:
            raise RetryableError(self.service_name, str(e))

    def close(self) -> None:
        """Close the session and release connections."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False
