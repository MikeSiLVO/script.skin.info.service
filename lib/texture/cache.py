"""Texture cache operations for precaching and cleanup.

Manages Kodi's texture cache database for artwork optimization.
"""
from __future__ import annotations

import time
import threading
import xbmc
import xbmcgui
import xbmcvfs
from typing import Optional, List, Dict, Set, Any, Union, Callable

from lib.kodi.client import request, get_library_items
from lib.kodi.client import log
from lib.kodi.client import decode_image_url, encode_image_url
from lib.kodi.settings import KodiSettings
from lib.infrastructure.workers import WorkerQueue
from lib.download.artwork import DownloadArtwork
from lib.infrastructure.paths import PathBuilder
from lib.texture.utilities import should_precache_url, is_library_artwork_url

_cache_lock = threading.Lock()
_cached_urls_set: Optional[Set[str]] = None


def get_cached_textures(url_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get cached textures from Kodi's Textures13.db.

    Args:
        url_filter: Optional URL to filter results (searches for partial match)

    Returns:
        List of texture dicts with keys: textureid, url, cachedurl, width, height, etc.
    """
    params: Dict[str, Any] = {
        "properties": ["url", "cachedurl", "lasthashcheck", "imagehash", "sizes"]
    }

    if url_filter:
        params["filter"] = {
            "field": "url",
            "operator": "contains",
            "value": url_filter
        }

    try:
        resp = request("Textures.GetTextures", params)
        if resp and "result" in resp and "textures" in resp["result"]:
            return resp["result"]["textures"]
        log("Artwork", f"Textures.GetTextures unexpected response: {resp}")
        return []
    except Exception as e:
        log("Texture",f"Error getting textures: {str(e)}", xbmc.LOGERROR)
        return []


def remove_texture(texture_id: int) -> bool:
    """
    Remove a texture from Kodi's cache.
    Kodi will automatically re-cache the image when it's displayed again.

    Args:
        texture_id: The texture ID from Textures.GetTextures

    Returns:
        True if successful, False otherwise
    """
    try:
        resp = request("Textures.RemoveTexture", {"textureid": texture_id})
        return resp is not None
    except Exception as e:
        log("Texture",f"Error removing texture {texture_id}: {str(e)}", xbmc.LOGERROR)
        return False


def get_library_artwork_urls(media_type: str) -> Set[str]:
    """
    Get all current artwork URLs from Kodi library for a media type.

    Args:
        media_type: 'movie', 'tvshow', 'episode', 'musicvideo', etc.

    Returns:
        Set of artwork URLs currently in use (decoded)
    """
    urls = set()

    try:
        items = get_library_items(
            media_types=[media_type],
            properties=["art"],
            decode_urls=True
        )

        for item in items:
            art = item.get('art', {})
            if art and isinstance(art, dict):
                for art_url in art.values():
                    if art_url:
                        urls.add(art_url)

        return urls
    except Exception as e:
        log("Texture",f"Error getting library URLs for {media_type}: {str(e)}", xbmc.LOGERROR)
        return urls


def get_all_library_artwork_urls(
    media_types: Optional[List[str]] = None,
    progress_callback: Optional[Callable] = None
) -> Set[str]:
    """
    Get all artwork URLs from Kodi library across multiple media types.

    Args:
        media_types: List of media types to scan (default: ['movie', 'tvshow', 'episode', 'musicvideo'])
        progress_callback: Optional callback(current, total, media_type) for progress updates

    Returns:
        Set of all artwork URLs in library (decoded)
    """
    if media_types is None:
        media_types = ['movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set', 'artist', 'album']

    all_urls = set()

    try:
        items = get_library_items(
            media_types=media_types,
            properties=["art"],
            decode_urls=True,
            progress_callback=progress_callback
        )

        for item in items:
            art = item.get('art', {})
            if art and isinstance(art, dict):
                for art_url in art.values():
                    if art_url:
                        all_urls.add(art_url)

    except Exception as e:
        log("Texture",f"Error getting all library URLs: {str(e)}", xbmc.LOGERROR)

    return all_urls


def load_cached_urls_once() -> Set[str]:
    """
    Load all cached texture URLs into memory set once per operation.

    Implements "big cache mode" pattern for O(1) URL lookups during pre-cache
    operations instead of repeated database queries.

    Returns:
        Set of decoded cached texture URLs
    """
    global _cached_urls_set

    with _cache_lock:
        if _cached_urls_set is not None:
            return _cached_urls_set

    textures = get_cached_textures()
    new_set = set()

    for texture in textures:
        url = texture.get('url', '')
        if url:
            decoded = decode_image_url(url)
            new_set.add(decoded)

    with _cache_lock:
        if _cached_urls_set is None:
            _cached_urls_set = new_set
        return _cached_urls_set


def clear_cached_urls_cache() -> None:
    """Clear the in-memory cached URLs set to force reload on next operation."""
    global _cached_urls_set
    with _cache_lock:
        _cached_urls_set = None


def _get_library_scan_data(
    media_types: Optional[List[str]] = None,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    operation_name: str = "Texture Cache"
) -> Dict[str, Any]:
    """
    Scan library and cache, return both sets for comparison.

    This shared function eliminates duplicate scanning logic between
    precache_library_artwork() and cleanup_orphaned_textures().

    Args:
        media_types: List of media types to scan
        progress_dialog: Optional progress dialog for updates
        operation_name: Name shown in progress dialog

    Returns:
        Dictionary with keys:
            - library_urls: Set of decoded URLs from library
            - cached_textures: List of texture dicts from Textures.GetTextures
            - cached_urls: Set of cached URLs
            - stats: Dict with total_library and total_cached counts
    """
    if media_types is None:
        media_types = ['movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set', 'artist', 'album']

    # Scan library for artwork URLs with granular progress
    def progress_callback(current: int, total: int, media_type: str):
        if progress_dialog:
            # Spread progress from 10% to 25% across media types
            percent = 10 + int((current / total) * 15)
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(percent, operation_name, f"Scanning {media_type} library")
            else:
                progress_dialog.update(percent, f"[B]CANCEL TO RESUME LATER[/B][CR]Scanning {media_type} library")

    library_urls = get_all_library_artwork_urls(media_types, progress_callback=progress_callback)

    if progress_dialog:
        if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
            progress_dialog.update(25, operation_name, f"Found {len(library_urls)} library URLs")
        else:
            progress_dialog.update(25, f"[B]CANCEL TO RESUME LATER[/B][CR]Found {len(library_urls)} library URLs")

    # Get cached textures from database
    if progress_dialog:
        if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
            progress_dialog.update(30, operation_name, "Checking texture cache...")
        else:
            progress_dialog.update(30, "[B]CANCEL TO RESUME LATER[/B][CR]Checking texture cache...")

    cached_textures = get_cached_textures()
    cached_urls = {t['url'] for t in cached_textures}

    log("Artwork",
        f"Library scan complete - {len(library_urls)} library URLs, {len(cached_textures)} cached textures"
    )

    return {
        'library_urls': library_urls,
        'cached_textures': cached_textures,
        'cached_urls': cached_urls,
        'stats': {
            'total_library': len(library_urls),
            'total_cached': len(cached_textures)
        }
    }


class TextureCache(WorkerQueue):
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

        log("Cache",
            f"TextureCache initialized with {self.num_workers} workers"
        )

    def _on_start(self) -> None:
        """Called when queue starts - load cached URLs if needed."""
        if self.check_cached:
            self._load_cached_urls()

        log("Cache",f"TextureCache started {self.num_workers} worker threads")

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
        log("Cache",f"TextureCache bulk_add: {queued}/{len(urls)} URLs queued")
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
        wrapped_url = encode_image_url(url)

        try:
            with xbmcvfs.File(wrapped_url):
                pass

            return {
                'url': url,
                'success': True
            }

        except Exception as e:
            log("Texture", f"Worker {worker_id} failed to cache URL: {str(e)}", xbmc.LOGWARNING)

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
            response = request('Textures.GetTextures', {'properties': ['url']})

            if response and 'result' in response:
                textures = response.get('result', {}).get('textures', [])
                self.cached_urls_set = {t['url'] for t in textures if 'url' in t}
                log("Cache",
                    f"TextureCache loaded {len(self.cached_urls_set)} cached URLs for deduplication"
                )
            else:
                self.cached_urls_set = set()

        except Exception as e:
            log("Texture", f"Failed to load cached URLs: {str(e)}", xbmc.LOGWARNING)
            self.cached_urls_set = set()


class TextureCacheDownload(WorkerQueue):
    """
    Unified queue that caches URLs and downloads to filesystem.

    Each worker performs BOTH operations per item:
    1. Cache URL via xbmcvfs.File (texture cache)
    2. Download to filesystem if HTTP URL

    This avoids worker coordination issues (max 8 workers total).
    """

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

        log("Cache",
            f"TextureCacheDownload initialized with {self.num_workers} workers"
        )

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
        """
        Queue an item for caching and downloading.

        Args:
            url: Image URL to cache and download
            media_type: Media type ('movie', 'tvshow', etc.)
            media_file: Media file path
            artwork_type: Artwork type ('poster', 'fanart', etc.)
            title: Media title (for logging)
            season: Season number (for seasons/episodes)
            episode: Episode number (for episodes)

        Returns:
            True if queued, False if already processing
        """
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
        url, media_type, media_file, artwork_type, title, season, episode = item

        cache_success = False
        cache_error = None
        download_success = False
        download_error = None
        bytes_downloaded = 0

        wrapped_url = encode_image_url(url)

        try:
            with xbmcvfs.File(wrapped_url):
                pass
            cache_success = True
            self.stats_cached += 1
            log("Cache",f"TextureCacheDownload worker {worker_id} cached URL")
        except Exception as e:
            cache_error = str(e)
            self.stats_cache_failed += 1
            log("Texture",
                f"SkinInfo: TextureCacheDownload worker {worker_id} failed to cache URL: {str(e)}",
                xbmc.LOGWARNING
            )

        if url.startswith('http'):
            local_path = self.path_builder.build_path(
                media_type=media_type,
                media_file=media_file,
                artwork_type=artwork_type,
                season_number=season,
                episode_number=episode,
                use_basename=True
            )

            if local_path:
                if worker_id not in self.artworks:
                    self.artworks[worker_id] = DownloadArtwork()

                downloader = self.artworks[worker_id]

                download_success, download_error, bytes_downloaded = downloader.download_artwork(
                    url=url,
                    local_path=local_path,
                    artwork_type=artwork_type,
                    existing_file_mode=self.existing_file_mode,
                    abort_flag=self.abort_flag
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


def precache_library_artwork(
    media_types: Optional[List[str]] = None,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    task_context=None
) -> Dict[str, int]:
    """
    Pre-cache library artwork URLs not already in texture cache.

    Uses two-pass optimization strategy:
    1. Identify uncached URLs (using big cache mode for O(1) lookups)
    2. Cache the uncached URLs with progress tracking

    Args:
        media_types: List of media types to cache (default: all video & music library types)
        progress_dialog: Optional progress dialog
        task_context: Optional TaskContext for progress tracking and cancellation

    Returns:
        Dict with stats: {'total_urls': 500, 'already_cached': 450, 'needed_caching': 50, 'successfully_cached': 48, 'failed': 2}
    """
    stats = {
        'total_urls': 0,
        'already_cached': 0,
        'needed_caching': 0,
        'successfully_cached': 0,
        'failed': 0,
        'cancelled': False
    }

    monitor = xbmc.Monitor()

    try:
        if media_types is None:
            media_types = ['movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set', 'artist', 'album']

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(0, "Pre-Cache Artwork", "Scanning library for artwork URLs...")
            else:
                progress_dialog.update(0, "[B]CANCEL TO RESUME LATER[/B][CR]Scanning library for artwork URLs...")

        def progress_callback(current: int, total: int, media_type: str):
            if progress_dialog:
                percent = int((current / total) * 10)
                if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                    progress_dialog.update(percent, "Pre-Cache Artwork", f"Scanning {media_type} library")
                else:
                    progress_dialog.update(percent, f"[B]CANCEL TO RESUME LATER[/B][CR]Scanning {media_type} library")

        library_urls = get_all_library_artwork_urls(media_types, progress_callback=progress_callback)

        log("Artwork",f"Pre-cache: found {len(library_urls)} total library artwork URLs")

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(10, "Pre-Cache Artwork", "Loading texture cache...")
            else:
                progress_dialog.update(10, "[B]CANCEL TO RESUME LATER[/B][CR]Loading texture cache...")

        cached_urls_set = load_cached_urls_once()

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(20, "Pre-Cache Artwork", "Identifying uncached artwork...")
            else:
                progress_dialog.update(20, "[B]CANCEL TO RESUME LATER[/B][CR]Identifying uncached artwork...")

        precacheable_urls = []
        urls_to_cache = []

        for url in library_urls:
            if not should_precache_url(url):
                continue

            precacheable_urls.append(url)
            decoded_url = decode_image_url(url)

            if decoded_url not in cached_urls_set:
                urls_to_cache.append(url)

        stats['total_urls'] = len(precacheable_urls)
        stats['already_cached'] = len(precacheable_urls) - len(urls_to_cache)
        stats['needed_caching'] = len(urls_to_cache)

        skipped_count = len(library_urls) - len(precacheable_urls)

        log("Artwork",
            f"Pre-cache: {stats['already_cached']} already cached, "
            f"{stats['needed_caching']} need caching, "
            f"{skipped_count} skipped (system/addon files)"
        )

        if stats['needed_caching'] == 0:
            log("Artwork", "Pre-cache: all URLs already cached, nothing to do")
            return stats

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(25, "Pre-Cache Artwork", f"Pre-caching {len(urls_to_cache)} images...")
            else:
                progress_dialog.update(
                    25,
                    f"[B]CANCEL TO RESUME LATER[/B][CR]Pre-caching {len(urls_to_cache)} images..."
                )

        cache_queue = TextureCache(
            check_cached=False,
            abort_flag=task_context.abort_flag if task_context else None,
            task_context=task_context
        )
        cache_queue.start()

        try:
            queued = cache_queue.bulk_add_urls(urls_to_cache)
            log("Artwork",f"Pre-cache: queued {queued} URLs for background processing")

            last_update_time = time.time()
            last_percent = -1

            while not cache_queue.queue.empty() or cache_queue.processing_set:
                if monitor.abortRequested() or (task_context and task_context.abort_flag.is_requested()) or (isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled()):
                    stats['cancelled'] = True
                    break

                if progress_dialog:
                    progress = cache_queue.get_progress()
                    percent = 25 + int(progress['percent'] * 0.75) if progress['total'] > 0 else 100
                    completed = progress['completed']
                    total = progress['total']
                    remaining = total - completed

                    current_time = time.time()
                    time_since_update = current_time - last_update_time
                    percent_changed = abs(percent - last_percent) >= 1

                    if time_since_update >= 0.5 or percent_changed:
                        if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                            progress_dialog.update(percent, "Pre-Cache Artwork", f"Cached: {completed}/{total} ({remaining} remaining)")
                        else:
                            progress_dialog.update(
                                percent,
                                f"[B]CANCEL TO RESUME LATER[/B][CR]Cached: {completed} of {total}[CR]Remaining: {remaining}"
                            )
                        last_update_time = current_time
                        last_percent = percent

                monitor.waitForAbort(0.2)

            queue_stats = cache_queue.get_stats()
            stats['successfully_cached'] = queue_stats['successful']
            stats['failed'] = queue_stats['failed']

            status = "cancelled" if stats['cancelled'] else "complete"
            log("Artwork",
                f"Pre-cache {status}: {stats['successfully_cached']} cached, {stats['failed']} failed"
            )

        finally:
            cache_queue.stop(wait=False)
            clear_cached_urls_cache()

    except Exception as e:
        log("Texture",f"Pre-cache failed: {str(e)}", xbmc.LOGERROR)
        stats['failed'] = stats['needed_caching']
        clear_cached_urls_cache()

    return stats


def precache_and_download_artwork(
    media_types: Optional[List[str]] = None,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    task_context=None
) -> Dict[str, int]:
    """
    Pre-cache library artwork AND download to filesystem simultaneously.

    Uses unified TextureCacheDownload to avoid worker coordination issues.

    Args:
        media_types: List of media types to process (default: all video & music library types)
        progress_dialog: Optional progress dialog
        task_context: Optional TaskContext for progress tracking and cancellation

    Returns:
        Dict with stats: {'total_items': N, 'cached': N, 'downloaded': N, 'skipped': N, 'failed': N, 'cancelled': False}
    """
    stats = {
        'total_items': 0,
        'total_urls': 0,
        'cached': 0,
        'cache_failed': 0,
        'downloaded': 0,
        'download_skipped': 0,
        'download_failed': 0,
        'bytes_downloaded': 0,
        'cancelled': False
    }

    if media_types is None:
        media_types = ['movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set', 'artist', 'album']

    monitor = xbmc.Monitor()

    try:
        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(5, "Pre-Cache + Download", "Scanning library...")
            else:
                progress_dialog.update(5, "Scanning library...")

        properties = ["art", "title", "file", "season", "episode", "tvshowid"]

        def has_artwork(item: Dict[str, Any]) -> bool:
            art = item.get('art', {})
            return bool(art and isinstance(art, dict))

        try:
            items = get_library_items(
                media_types=media_types,
                properties=properties,
                decode_urls=True,
                filter_func=has_artwork
            )

            for item in items:
                if 'title' not in item:
                    item['title'] = "Unknown"
                if 'file' not in item:
                    item['file'] = ""

        except Exception as e:
            log("Texture",
                f"SkinInfo: Error querying library for precache+download: {str(e)}",
                xbmc.LOGERROR
            )
            items = []

        stats['total_items'] = len(items)

        if not items:
            log("Artwork", "No items found for precache+download")
            return stats

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(15, "Pre-Cache + Download", f"Processing {len(items)} items...")
            else:
                progress_dialog.update(15, f"Processing {len(items)} items...")

        existing_file_mode_setting = KodiSettings.existing_file_mode()
        existing_file_mode_int = int(existing_file_mode_setting) if existing_file_mode_setting else 0
        existing_file_mode = ['skip', 'overwrite', 'use_existing'][existing_file_mode_int]

        queue = TextureCacheDownload(
            existing_file_mode=existing_file_mode,
            abort_flag=task_context.abort_flag if task_context else None,
            task_context=task_context
        )
        queue.start()

        try:
            queued = 0
            for item in items:
                for art_type, url in item['art'].items():
                    if not url:
                        continue

                    queue.add_cache_and_download(
                        url=url,
                        media_type=item['media_type'],
                        media_file=item['file'],
                        artwork_type=art_type,
                        title=item['title'],
                        season=item.get('season'),
                        episode=item.get('episode')
                    )
                    queued += 1

            stats['total_urls'] = queued
            log("Artwork",f"Pre-cache+download: queued {queued} URLs for processing")

            last_update_time = time.time()
            last_percent = -1

            while not queue.queue.empty() or queue.processing_set:
                if monitor.abortRequested() or (task_context and task_context.abort_flag.is_requested()) or (isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled()):
                    stats['cancelled'] = True
                    break

                if progress_dialog:
                    queue_stats = queue.get_stats()
                    completed = queue_stats['completed']
                    total = queue_stats['total']
                    percent = 25 + int((completed / total) * 75) if total > 0 else 100

                    current_time = time.time()
                    time_since_update = current_time - last_update_time
                    percent_changed = abs(percent - last_percent) >= 1

                    if time_since_update >= 0.5 or percent_changed:
                        remaining = total - completed
                        cached = queue_stats['cached']
                        downloaded = queue_stats['downloaded']

                        if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                            progress_dialog.update(
                                percent,
                                "Pre-Cache + Download",
                                f"Processed: {completed}/{total} ({remaining} remaining)"
                            )
                        else:
                            progress_dialog.update(
                                percent,
                                f"[B]CANCEL TO RESUME LATER[/B][CR]Processed: {completed} of {total}[CR]Remaining: {remaining}[CR]Cached: {cached} | Downloaded: {downloaded}"
                            )
                        last_update_time = current_time
                        last_percent = percent

                monitor.waitForAbort(0.2)

            queue_stats = queue.get_stats()
            stats['cached'] = queue_stats['cached']
            stats['cache_failed'] = queue_stats['cache_failed']
            stats['downloaded'] = queue_stats['downloaded']
            stats['download_skipped'] = queue_stats['download_skipped']
            stats['download_failed'] = queue_stats['download_failed']
            stats['bytes_downloaded'] = queue_stats['bytes_downloaded']

            status = "cancelled" if stats['cancelled'] else "complete"
            log("Artwork",
                f"Pre-cache+download {status}: {stats['cached']} cached, {stats['downloaded']} downloaded"
            )

        finally:
            queue.stop(wait=False)
            clear_cached_urls_cache()

    except Exception as e:
        log("Texture",f"Pre-cache+download failed: {str(e)}", xbmc.LOGERROR)
        clear_cached_urls_cache()

    return stats


def cleanup_orphaned_textures(
    media_types: Optional[List[str]] = None,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    task_context=None
) -> Dict[str, int]:
    """
    Scan for and remove orphaned cached textures.
    Orphaned = cached texture URL no longer exists in library.

    Args:
        media_types: List of media types to scan (default: all video & music library types)
        progress_dialog: Optional progress dialog
        task_context: Optional TaskContext for progress tracking and cancellation

    Returns:
        Dict with stats: {'total_cached': 500, 'total_library': 450, 'orphaned_found': 50, 'removed': 48, 'failed': 2}
    """
    stats = {
        'total_cached': 0,
        'total_library': 0,
        'orphaned_found': 0,
        'removed': 0,
        'failed': 0,
        'cancelled': False
    }

    monitor = xbmc.Monitor()

    try:
        log("Artwork",f"Starting orphaned texture cleanup for media types: {media_types}")

        scan_data = _get_library_scan_data(media_types, progress_dialog, "Analyze Texture Cache")

        library_urls = scan_data['library_urls']
        cached_textures = scan_data['cached_textures']

        stats['total_library'] = scan_data['stats']['total_library']
        stats['total_cached'] = scan_data['stats']['total_cached']

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(50, "Analyze Texture Cache", "Finding orphaned textures...")
            else:
                progress_dialog.update(50, "Finding orphaned textures...")

        orphaned = []
        for texture in cached_textures:
            url = texture.get('url', '')
            decoded_cache_url = decode_image_url(url)
            if is_library_artwork_url(url) and decoded_cache_url not in library_urls:
                orphaned.append(texture)

        stats['orphaned_found'] = len(orphaned)

        log("Artwork",f"Found {stats['orphaned_found']} orphaned textures")

        if stats['orphaned_found'] > 0:
            dialog = xbmcgui.Dialog()

            while True:
                result = dialog.yesnocustom(
                    "Confirm Cleanup",
                    f"Found {stats['orphaned_found']} orphaned textures to remove.[CR][CR]"
                    f"Continue with removal?",
                    customlabel="View Report"
                )

                if result == 2:
                    report_lines = [
                        "ORPHANED TEXTURES REPORT",
                        "",
                        f"Total orphaned: {stats['orphaned_found']}",
                        f"Total cached: {stats['total_cached']}",
                        f"Total library: {stats['total_library']}",
                        "",
                        "URLs to be removed:",
                        ""
                    ]
                    for i, texture in enumerate(orphaned, 1):
                        url = texture.get('url', '')
                        report_lines.append(f"{i}. {url}")

                    dialog.textviewer("Orphaned Textures Report", "\n".join(report_lines))
                elif result == 1:
                    break
                else:
                    return stats

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(
                    60,
                    "Clean Orphaned Textures",
                    f"Removing {stats['orphaned_found']} orphaned textures..."
                )
            else:
                progress_dialog.update(60, f"Removing {stats['orphaned_found']} orphaned textures...")

        for idx, texture in enumerate(orphaned):
            if monitor.abortRequested() or (task_context and task_context.abort_flag.is_requested()):
                stats['cancelled'] = True
                break

            texture_id = texture.get('textureid')
            url = texture.get('url', '')

            if texture_id:
                success = remove_texture(texture_id)
                if success:
                    stats['removed'] += 1
                else:
                    stats['failed'] += 1

            if progress_dialog:
                percent = 60 + int(((idx + 1) / len(orphaned)) * 40) if orphaned else 100
                if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                    progress_dialog.update(
                        percent,
                        "Clean Orphaned Textures",
                        f"Removed {idx + 1} / {stats['orphaned_found']}"
                    )
                else:
                    progress_dialog.update(percent, f"Removed {idx + 1} / {stats['orphaned_found']}")

        status = "cancelled" if stats['cancelled'] else "complete"
        log("Artwork",f"Cleanup {status}: {stats['removed']} removed, {stats['failed']} failed")

    except Exception as e:
        log("Texture",f"Orphaned cleanup failed: {str(e)}", xbmc.LOGERROR)

    return stats


