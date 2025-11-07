"""Single artwork file downloader with error tracking and retry logic."""
from __future__ import annotations

import os
import time
import urllib.request
import urllib.error
import urllib.parse
import xbmc
import xbmcvfs
import xbmcaddon
from typing import Optional, Tuple, Dict

ADDON = xbmcaddon.Addon()


def log_download(message: str, level: int = xbmc.LOGDEBUG) -> None:
    """Log download message if debug enabled."""
    if ADDON.getSettingBool('enable_debug') or level >= xbmc.LOGERROR:
        xbmc.log(f"SkinInfo Download: {message}", level)


class ArtworkDownloader:
    """
    Single artwork file downloader.

    Handles HTTP downloads with content-type detection, error tracking,
    retry logic, and existing file handling. Uses urllib (not requests)
    and xbmcvfs for Kodi compatibility.
    """

    CONTENT_TYPE_MAP = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp'
    }

    def __init__(self):
        """Initialize downloader with error tracking."""
        self.provider_errors: Dict[str, int] = {}
        self.file_error_count = 0
        self.max_provider_errors = 3
        self.max_file_errors = 3

        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [
            ('User-Agent', 'Kodi Artwork Addon/1.0'),
            ('Accept', 'image/*')
        ]

    def download_artwork(
        self,
        url: str,
        local_path: str,
        artwork_type: str,
        existing_file_mode: str = 'skip',
        alternate_path: Optional[str] = None,
        media_type: str = ''
    ) -> Tuple[bool, Optional[str], int]:
        """
        Download single artwork file.

        Args:
            url: Image URL to download
            local_path: Base path WITHOUT extension (extension added based on content-type)
            artwork_type: Type of artwork (for logging)
            existing_file_mode: 'skip', 'overwrite', or 'use_existing'
            alternate_path: Optional alternate naming pattern to check (without extension)
            media_type: Media type (directories only created for 'set')

        Returns:
            Tuple of (success, error_message, bytes_downloaded)
            - success: True if downloaded successfully
            - error_message: None if success, error string if failed
            - bytes_downloaded: Number of bytes written (0 if skipped/failed)
        """
        if not url:
            log_download("Empty URL provided", xbmc.LOGERROR)
            return False, "Empty URL", 0

        hostname = urllib.parse.urlparse(url).netloc

        if self.provider_errors.get(hostname, 0) >= self.max_provider_errors:
            log_download(
                f"BLOCKING - provider {hostname} exceeded error limit ({self.provider_errors.get(hostname, 0)} >= {self.max_provider_errors})",
                xbmc.LOGERROR
            )
            return False, f"Provider {hostname} exceeded error limit", 0

        if self.file_error_count >= self.max_file_errors:
            log_download(
                f"BLOCKING ALL DOWNLOADS - file error count ({self.file_error_count}) >= max ({self.max_file_errors}). First error was likely a missing directory.",
                xbmc.LOGERROR
            )
            return False, "Too many file write errors", 0

        if existing_file_mode == 'skip':
            paths_to_check = [local_path]
            if alternate_path:
                paths_to_check.append(alternate_path)

            for check_path in paths_to_check:
                for ext_type in self.CONTENT_TYPE_MAP.values():
                    test_path = xbmcvfs.validatePath(check_path + '.' + ext_type)
                    if xbmcvfs.exists(test_path):
                        return False, None, 0

        try:
            response = self._download_with_retry(url)

            ext = self._get_extension(response)
            if not ext:
                self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
                return False, "Unknown image type", 0

            full_path = xbmcvfs.validatePath(local_path + '.' + ext)
            parent_dir = os.path.dirname(full_path)
            if not xbmcvfs.mkdirs(parent_dir):
                self.file_error_count += 1
                log_download(
                    f"FILE ERROR #{self.file_error_count} - Cannot create directory: {parent_dir}",
                    xbmc.LOGERROR
                )
                return False, f"Cannot create directory: {parent_dir}", 0

            bytes_written = self._write_file_stream(full_path, response)

            if existing_file_mode == 'overwrite' and alternate_path:
                for ext_type in self.CONTENT_TYPE_MAP.values():
                    alt_file = xbmcvfs.validatePath(alternate_path + '.' + ext_type)
                    if xbmcvfs.exists(alt_file):
                        if not xbmcvfs.delete(alt_file):
                            log_download(f"Failed to delete old pattern file: {alt_file}", xbmc.LOGWARNING)

            self.provider_errors[hostname] = 0
            self.file_error_count = 0

            return True, None, bytes_written

        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 410):
                log_download(f"HTTP {e.code} for {url}", xbmc.LOGDEBUG)
                return False, f"HTTP {e.code}", 0
            else:
                self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
                log_download(f"HTTP {e.code} ({e.reason}) for {url}", xbmc.LOGWARNING)
                return False, f"HTTP {e.code}: {e.reason}", 0

        except (urllib.error.URLError, OSError) as e:
            self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
            log_download(f"Network error for {url}: {str(e)}", xbmc.LOGWARNING)
            return False, str(e), 0

        except Exception as e:
            self.file_error_count += 1
            log_download(f"Unexpected error downloading {url}: {str(e)}", xbmc.LOGERROR)
            return False, f"Unexpected error: {str(e)}", 0

    def _download_with_retry(self, url: str, max_retries: int = 3):
        """
        Download with exponential backoff retry.

        Args:
            url: URL to download
            max_retries: Maximum number of retry attempts

        Returns:
            Response object

        Raises:
            urllib.error.HTTPError: For HTTP errors
            urllib.error.URLError: For network errors
        """
        for attempt in range(max_retries):
            try:
                response = self.opener.open(url, timeout=20)
                return response
            except urllib.error.HTTPError as e:
                if e.code in (404, 403, 410):
                    raise
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, OSError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise urllib.error.URLError("Max retries exceeded")

    def _get_extension(self, response) -> Optional[str]:
        """
        Get file extension from Content-Type header.

        Args:
            response: urllib response object

        Returns:
            Extension string ('jpg', 'png', etc.) or None if unknown
        """
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        return self.CONTENT_TYPE_MAP.get(content_type)

    def _write_file_stream(self, path: str, response) -> int:
        """
        Stream download to file in chunks.

        Args:
            path: Full file path to write
            response: urllib response object

        Returns:
            Number of bytes written

        Raises:
            IOError: If write fails
        """
        bytes_written = 0
        try:
            f = xbmcvfs.File(path, 'wb')
            if not f:
                raise IOError(f"Failed to open file for writing: {path}")

            with f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    chunk_bytes = bytearray(chunk)
                    written = f.write(chunk_bytes)
                    if not written:
                        raise IOError(f"Failed to write to {path}")
                    bytes_written += len(chunk_bytes)
        except Exception:
            if xbmcvfs.exists(path):
                xbmcvfs.delete(path)
            raise
        return bytes_written
