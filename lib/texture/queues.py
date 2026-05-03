"""WorkerQueue subclasses for texture caching: cache-only and unified cache+download."""
from __future__ import annotations

from typing import Optional, List, Dict, Set, Any, Callable

import xbmc
import xbmcvfs

from lib.kodi.client import request, log, extract_result, encode_image_url
from lib.infrastructure.workers import WorkerQueue
from lib.infrastructure.paths import PathBuilder
from lib.download.artwork import DownloadArtwork


def _cache_url_via_xbmcvfs(url: str) -> tuple[bool, Optional[str]]:
    """Trigger Kodi's texture cache for `url` by reading it via `xbmcvfs.File`.

    Returns `(success, error_or_None)`. Caller is responsible for logging/stat updates.
    """
    wrapped_url = encode_image_url(url)
    try:
        f = xbmcvfs.File(wrapped_url)
        cached = f.size() > 0
        f.close()
        if cached:
            return True, None
        return False, "file not found or empty"
    except Exception as e:
        return False, str(e)


class TextureCache(WorkerQueue):
    """Background texture caching queue (cache-only). Simulates Kodi's `BackgroundCacheImage()` via Python threads."""

    def __init__(
        self,
        num_workers: Optional[int] = None,
        on_complete: Optional[Callable] = None,
        check_cached: bool = True,
        abort_flag=None,
        task_context=None
    ):
        super().__init__(
            num_workers=num_workers,
            abort_flag=abort_flag,
            task_context=task_context
        )

        self.on_complete = on_complete
        self.check_cached = check_cached
        self.cached_urls_set: Optional[Set[str]] = None

        log("Cache", f"TextureCache initialized with {self.num_workers} workers")

    def _on_start(self) -> None:
        if self.check_cached:
            self._load_cached_urls()
        log("Cache", f"TextureCache started {self.num_workers} worker threads")

    def add_url(self, url: str) -> bool:
        """Queue a URL for caching. Returns False if already cached or in-flight. Non-blocking."""
        if not url:
            return False
        return self.add_item(url, dedupe_key=url)

    def bulk_add_urls(self, urls: List[str]) -> int:
        """Queue multiple URLs. Returns count successfully queued."""
        queued = self.bulk_add_items(urls)
        log("Cache", f"TextureCache bulk_add: {queued}/{len(urls)} URLs queued")
        return queued

    def _should_process_item(self, item: Any, dedupe_key: Any) -> bool:
        if self.cached_urls_set and dedupe_key in self.cached_urls_set:
            return False
        return True

    def _process_item(self, item: str, worker_id: int) -> Dict:
        """`WorkerQueue` entry point: cache one URL via `xbmcvfs.File` read."""
        url = item
        success, error = _cache_url_via_xbmcvfs(url)
        if not success and error and error != "file not found or empty":
            log("Texture", f"Worker {worker_id} failed to cache URL: {error}", xbmc.LOGWARNING)
        return {'url': url, 'success': success, 'error': error} if not success else {'url': url, 'success': True}

    def _on_item_complete(self, item: str, result: Dict) -> None:
        url = item
        if self.on_complete:
            try:
                self.on_complete(url, result['success'], result['elapsed'])
            except Exception:
                pass

    def _load_cached_urls(self) -> None:
        try:
            response = request('Textures.GetTextures', {'properties': ['url']})
            if response and 'result' in response:
                textures = extract_result(response, 'textures', [])
                self.cached_urls_set = {t['url'] for t in textures if 'url' in t}
                log("Cache", f"TextureCache loaded {len(self.cached_urls_set)} cached URLs for deduplication")
            else:
                self.cached_urls_set = set()
        except Exception as e:
            log("Texture", f"Failed to load cached URLs: {str(e)}", xbmc.LOGWARNING)
            self.cached_urls_set = set()


class TextureCacheDownload(WorkerQueue):
    """Unified queue: cache via `xbmcvfs.File` AND download to filesystem in one worker per item."""

    def __init__(
        self,
        num_workers: Optional[int] = None,
        existing_file_mode: str = 'skip',
        abort_flag=None,
        task_context=None
    ):
        super().__init__(
            num_workers=num_workers,
            abort_flag=abort_flag,
            task_context=task_context
        )

        self.existing_file_mode = existing_file_mode
        self.artworks: Dict[int, DownloadArtwork] = {}
        self.path_builder = PathBuilder()

        self.stats_cached = 0
        self.stats_cache_failed = 0
        self.stats_downloaded = 0
        self.stats_download_skipped = 0
        self.stats_download_failed = 0
        self.stats_bytes = 0

        log("Cache", f"TextureCacheDownload initialized with {self.num_workers} workers")

    def add_cache_and_download(
        self,
        url: str,
        media_type: str,
        media_file: str,
        artwork_type: str,
        title: str,
        season: Optional[int] = None,
        episode: Optional[int] = None
    ) -> bool:
        """Queue an item for caching + downloading. Returns False if already processing."""
        item = (url, media_type, media_file, artwork_type, title, season, episode)
        return self.add_item(item, dedupe_key=url)

    def get_stats(self) -> Dict:
        base_stats = super().get_stats()
        base_stats.update({
            'cached': self.stats_cached,
            'cache_failed': self.stats_cache_failed,
            'downloaded': self.stats_downloaded,
            'download_skipped': self.stats_download_skipped,
            'download_failed': self.stats_download_failed,
            'bytes_downloaded': self.stats_bytes
        })
        return base_stats

    def _process_item(self, item: Any, worker_id: int) -> Dict:
        url, media_type, media_file, artwork_type, title, season, _episode = item

        download_success = False
        download_error = None
        bytes_downloaded = 0

        cache_success, cache_error = _cache_url_via_xbmcvfs(url)
        if cache_success:
            self.stats_cached += 1
        else:
            self.stats_cache_failed += 1
            if cache_error and cache_error != "file not found or empty":
                log("Texture",
                    f"SkinInfo: TextureCacheDownload worker {worker_id} failed to cache URL: {cache_error}",
                    xbmc.LOGWARNING)

        if url.startswith('http'):
            local_path = self.path_builder.build_path(
                media_type=media_type,
                media_file=media_file,
                artwork_type=artwork_type,
                season_number=season,
                use_basename=True
            )

            if local_path:
                if worker_id not in self.artworks:
                    self.artworks[worker_id] = DownloadArtwork()

                downloader = self.artworks[worker_id]

                download_success, download_error, bytes_downloaded = downloader.download_artwork(
                    url=url,
                    local_path=local_path,
                    existing_file_mode=self.existing_file_mode,
                    abort_flag=self.abort_flag,
                )

                if download_success:
                    self.stats_downloaded += 1
                    self.stats_bytes += bytes_downloaded
                elif download_error is None:
                    self.stats_download_skipped += 1
                else:
                    self.stats_download_failed += 1
            else:
                log("Artwork",
                    f"Could not build download path for {media_type} '{title}' {artwork_type}"
                )
                self.stats_download_failed += 1

        return {
            'url': url,
            'media_type': media_type,
            'artwork_type': artwork_type,
            'title': title,
            'cache_success': cache_success,
            'cache_error': cache_error,
            'download_success': download_success,
            'download_error': download_error,
            'bytes_downloaded': bytes_downloaded
        }
