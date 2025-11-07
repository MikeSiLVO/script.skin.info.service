"""Background texture caching using Python threading to simulate Kodi's BackgroundCacheImage."""
from __future__ import annotations

import xbmc
import xbmcvfs
from typing import Optional, Set, List, Dict, Callable, Any

from resources.lib.kodi import log_cache
from resources.lib.worker_queue import WorkerQueue


class BackgroundCacheQueue(WorkerQueue):
    """
    Background texture caching queue using worker threads.

    Simulates Kodi's C++ BackgroundCacheImage() using Python threading.
    Provides speedup over sequential caching for uncached URLs.
    """

    def __init__(
        self,
        num_workers: Optional[int] = None,
        on_complete: Optional[Callable] = None,
        check_cached: bool = True,
        abort_flag=None,
        task_context=None
    ):
        """
        Initialize background cache queue.

        Args:
            num_workers: Number of worker threads (auto-detect if None)
            on_complete: Optional callback(url, success, elapsed) for each completion
            check_cached: Whether to pre-check if URLs are already cached
            abort_flag: Optional AbortFlag to check for cancellation
            task_context: Optional TaskContext for progress tracking
        """
        super().__init__(
            num_workers=num_workers,
            abort_flag=abort_flag,
            task_context=task_context
        )

        self.on_complete = on_complete
        self.check_cached = check_cached
        self.cached_urls_set: Optional[Set[str]] = None

        log_cache(
            f"BackgroundCacheQueue initialized with {self.num_workers} workers"
        )

    def _on_start(self) -> None:
        """Called when queue starts - load cached URLs if needed."""
        if self.check_cached:
            self._load_cached_urls()

        log_cache(f"BackgroundCacheQueue started {self.num_workers} worker threads")

    def add_url(self, url: str) -> bool:
        """
        Queue a URL for background caching.

        Returns immediately (non-blocking).

        Args:
            url: Image URL to cache

        Returns:
            True if queued, False if already cached/processing
        """
        if not url:
            return False

        return self.add_item(url, dedupe_key=url)

    def bulk_add_urls(self, urls: List[str]) -> int:
        """
        Queue multiple URLs efficiently.

        Args:
            urls: List of image URLs to cache

        Returns:
            Number of URLs successfully queued
        """
        queued = self.bulk_add_items(urls)
        log_cache(f"BackgroundCacheQueue bulk_add: {queued}/{len(urls)} URLs queued")
        return queued

    def _should_process_item(self, item: Any, dedupe_key: Any) -> bool:
        """Check if URL should be cached (skip if already cached)."""
        if self.cached_urls_set and dedupe_key in self.cached_urls_set:
            return False
        return True

    def _process_item(self, item: str, worker_id: int) -> Dict:
        """
        Process a single URL caching operation.

        Args:
            item: Image URL to cache (decoded or wrapped format)
            worker_id: ID of worker processing the item

        Returns:
            Dict with result info
        """
        url = item

        from resources.lib.texture_cache import encode_image_url
        wrapped_url = encode_image_url(url)

        try:
            with xbmcvfs.File(wrapped_url):
                pass

            return {
                'url': url,
                'success': True
            }

        except Exception as e:
            xbmc.log(
                f"SkinInfo: BackgroundCacheQueue worker {worker_id} failed to cache URL: {str(e)}",
                xbmc.LOGWARNING
            )

            return {
                'url': url,
                'success': False,
                'error': str(e)
            }

    def _on_item_complete(self, item: str, result: Dict) -> None:
        """Called when URL caching completes."""
        url = item
        if self.on_complete:
            try:
                self.on_complete(url, result['success'], result['elapsed'])
            except Exception:
                pass

    def _load_cached_urls(self) -> None:
        """Pre-load set of already cached URLs for fast lookup."""
        try:
            from resources.lib.kodi import request

            response = request('Textures.GetTextures', {'properties': ['url']})

            if response and 'result' in response:
                textures = response.get('result', {}).get('textures', [])
                self.cached_urls_set = {t['url'] for t in textures if 'url' in t}
                log_cache(
                    f"BackgroundCacheQueue loaded {len(self.cached_urls_set)} cached URLs for deduplication"
                )
            else:
                self.cached_urls_set = set()

        except Exception as e:
            xbmc.log(
                f"SkinInfo: BackgroundCacheQueue failed to load cached URLs: {str(e)}",
                xbmc.LOGWARNING
            )
            self.cached_urls_set = set()
