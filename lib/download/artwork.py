"""Single artwork file downloader with error tracking and retry logic."""
from __future__ import annotations

import os
import urllib.parse
import xbmc
import xbmcvfs
from typing import Optional, Tuple, Dict

from lib.kodi.client import log
from lib.data.api.client import ApiSession
from lib.data.api.client import RetryableError
from lib.infrastructure.paths import vfs_ensure_dir_slash


class DownloadArtwork:
    """Single artwork file downloader with streaming, content-type detection, and per-provider error gating."""

    CONTENT_TYPE_MAP = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp'
    }

    def __init__(self):
        self.provider_errors: Dict[str, int] = {}
        self.file_error_count = 0
        self.max_provider_errors = 3
        self.max_file_errors = 3

        self.session = ApiSession(
            service_name="Artwork",
            timeout=(5.0, 15.0),
            max_retries=2,
            backoff_factor=0.5,
            default_headers={
                "User-Agent": "Kodi Artwork Addon/1.0",
                "Accept": "image/*"
            }
        )

    def download_artwork(
        self,
        url: str,
        local_path: str,
        existing_file_mode: str = 'skip',
        alternate_path: Optional[str] = None,
        abort_flag=None
    ) -> Tuple[bool, Optional[str], int]:
        """Download one artwork file. `local_path` is extension-less; actual extension comes from Content-Type.

        `existing_file_mode` is `skip`/`overwrite`/`use_existing`. Returns `(success, error_or_None, bytes_written)`.
        """
        if not url:
            log("Download", "Empty URL provided", xbmc.LOGERROR)
            return False, "Empty URL", 0

        if not local_path:
            log("Download", "Empty local_path provided", xbmc.LOGERROR)
            return False, "Empty local_path", 0

        hostname = urllib.parse.urlparse(url).netloc

        if self.provider_errors.get(hostname, 0) >= self.max_provider_errors:
            log("Download",
                f"BLOCKING - provider {hostname} exceeded error limit ({self.provider_errors.get(hostname, 0)} >= {self.max_provider_errors})",
                xbmc.LOGERROR
            )
            return False, f"Provider {hostname} exceeded error limit", 0

        if self.file_error_count >= self.max_file_errors:
            log("Download",
                f"BLOCKING ALL DOWNLOADS - file error count ({self.file_error_count}) >= max ({self.max_file_errors}). First error was likely a missing directory.",
                xbmc.LOGERROR
            )
            return False, "Too many file write errors", 0

        if existing_file_mode == 'skip':
            paths_to_check = [local_path]
            if alternate_path:
                paths_to_check.append(alternate_path)

            for check_path in paths_to_check:
                if self._find_existing_with_extension(check_path):
                    return False, None, 0

        try:
            response = self.session.get_raw(
                url,
                abort_flag=abort_flag,
                stream=True
            )

            if response is None:
                self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
                return False, "Download failed", 0

            ext = self._get_extension(response)
            if not ext:
                self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
                response.close()
                return False, "Unknown image type", 0

            full_path = xbmcvfs.validatePath(local_path + '.' + ext)
            parent_dir = os.path.dirname(full_path)
            parent_dir_check = vfs_ensure_dir_slash(parent_dir)
            if not xbmcvfs.exists(parent_dir_check):
                xbmcvfs.mkdirs(parent_dir)
                if not xbmcvfs.exists(parent_dir_check):
                    self.file_error_count += 1
                    log("Download",
                        f"FILE ERROR #{self.file_error_count} - Cannot create directory: {parent_dir}",
                        xbmc.LOGERROR
                    )
                    response.close()
                    return False, f"Cannot create directory: {parent_dir}", 0

            bytes_written = self._write_file_stream(full_path, response, abort_flag)

            if existing_file_mode == 'overwrite' and alternate_path:
                for ext_type in self.CONTENT_TYPE_MAP.values():
                    alt_file = xbmcvfs.validatePath(alternate_path + '.' + ext_type)
                    if xbmcvfs.exists(alt_file):
                        if not xbmcvfs.delete(alt_file):
                            log("Download", f"Failed to delete old pattern file: {alt_file}", xbmc.LOGWARNING)

            self.provider_errors[hostname] = 0
            self.file_error_count = 0

            return True, None, bytes_written

        except RetryableError as e:
            self.provider_errors[hostname] = self.provider_errors.get(hostname, 0) + 1
            log("Download", f"Network error for {url}: {str(e)}", xbmc.LOGWARNING)
            return False, str(e), 0

        except Exception as e:
            self.file_error_count += 1
            log("Download", f"Unexpected error downloading {url}: {str(e)}", xbmc.LOGERROR)
            return False, f"Unexpected error: {str(e)}", 0

    def _find_existing_with_extension(self, base_path: str) -> Optional[str]:
        """Return the first existing file at `base_path.<ext>` for any known extension, or None."""
        for ext_type in self.CONTENT_TYPE_MAP.values():
            test_path = xbmcvfs.validatePath(base_path + '.' + ext_type)
            if xbmcvfs.exists(test_path):
                return test_path
        return None

    def _get_extension(self, response) -> Optional[str]:
        """Extract file extension from the response's Content-Type, or None if unrecognised."""
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        return self.CONTENT_TYPE_MAP.get(content_type)

    def _write_file_stream(self, path: str, response, abort_flag=None) -> int:
        """Stream `response` body to `path` in 8KB chunks.

        Deletes partial file on error. Raises `IOError` on write failure or abort.
        """
        bytes_written = 0
        try:
            f = xbmcvfs.File(path, 'wb')
            if not f:
                raise IOError(f"Failed to open file for writing: {path}")

            with f:
                for chunk in response.iter_content(chunk_size=8192):
                    if abort_flag and abort_flag.is_requested():
                        raise IOError("Download aborted")
                    if chunk:
                        chunk_bytes = bytearray(chunk)
                        written = f.write(chunk_bytes)
                        if not written:
                            raise IOError(f"Failed to write to {path}")
                        bytes_written += len(chunk_bytes)
        except Exception:
            if xbmcvfs.exists(path):
                xbmcvfs.delete(path)
            raise
        finally:
            response.close()
        return bytes_written
