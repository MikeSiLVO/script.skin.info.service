"""Shared HTTP client with rate limiting and retry logic for all API clients.

Provides:
- RateLimiter: Sliding window rate limiter
- HttpClient: Unified HTTP client with exponential backoff
"""
from __future__ import annotations

import xbmc
import json
import time
from typing import Optional, Dict
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from collections import deque


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = deque()

    def wait_if_needed(self, service_name: str = "API") -> None:
        """Wait if rate limit exceeded."""
        from resources.lib.kodi import log_api
        now = time.time()

        while self.requests and now - self.requests[0] >= self.window:
            self.requests.popleft()

        if len(self.requests) >= self.max_requests:
            oldest = self.requests[0]
            wait_time = self.window - (now - oldest) + 0.1
            if wait_time > 0:
                log_api(f"{service_name} proactive rate limit - {len(self.requests)}/{self.max_requests} requests used, pausing {wait_time:.2f}s to prevent 429 errors")
                time.sleep(wait_time)
                now = time.time()
                while self.requests and now - self.requests[0] >= self.window:
                    self.requests.popleft()

        self.requests.append(now)


class HttpClient:
    """HTTP client with rate limiting and exponential backoff retry."""

    def __init__(self, service_name: str, rate_limiter: Optional[RateLimiter] = None):
        """
        Initialize HTTP client.

        Args:
            service_name: Service name for logging (e.g., "TMDB", "fanart.tv")
            rate_limiter: Optional RateLimiter instance
        """
        self.service_name = service_name
        self.rate_limiter = rate_limiter

    def make_request(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        base_backoff: int = 2,
        timeout: int = 10
    ) -> Optional[dict]:
        """
        Make HTTP JSON request with exponential backoff on 429 errors.

        Args:
            url: Full URL to request
            headers: Dict of HTTP headers to include
            max_retries: Maximum retry attempts on 429
            base_backoff: Base backoff time in seconds (doubles each retry)
            timeout: Request timeout in seconds

        Returns:
            JSON response dict or None on error
        """
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(self.service_name)

        if headers is None:
            headers = {}

        for retry_count in range(max_retries + 1):
            try:
                req = Request(url)
                for key, value in headers.items():
                    req.add_header(key, value)

                with urlopen(req, timeout=timeout) as response:
                    data = response.read().decode('utf-8')
                    return json.loads(data)

            except HTTPError as e:
                from resources.lib.kodi import log_api

                if e.code == 429 and retry_count < max_retries:
                    backoff_time = (2 ** retry_count) * base_backoff
                    log_api(f"{self.service_name} HTTP 429 - retry {retry_count + 1}/{max_retries}, backoff {backoff_time}s")
                    xbmc.log(
                        f"SkinInfo {self.service_name}: Rate limit hit (429), retry {retry_count + 1}/{max_retries} after {backoff_time}s",
                        xbmc.LOGWARNING
                    )
                    time.sleep(backoff_time)
                    continue

                if e.code == 404 and self.service_name == "fanart.tv":
                    log_api(f"{self.service_name} HTTP 404 - no artwork available")
                else:
                    xbmc.log(f"SkinInfo {self.service_name}: HTTP error {e.code}: {e.reason}", xbmc.LOGERROR)
                return None

            except URLError as e:
                xbmc.log(f"SkinInfo {self.service_name}: URL error: {e.reason}", xbmc.LOGERROR)
                return None
            except Exception as e:
                xbmc.log(f"SkinInfo {self.service_name}: Request failed: {str(e)}", xbmc.LOGERROR)
                return None

        return None


def create_rate_limited_client(
    service_name: str,
    max_requests: int,
    window_seconds: float
) -> HttpClient:
    """
    Create HTTP client with rate limiting.

    Args:
        service_name: Service name for logging
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        Configured HttpClient instance
    """
    rate_limiter = RateLimiter(max_requests, window_seconds)
    return HttpClient(service_name, rate_limiter)
