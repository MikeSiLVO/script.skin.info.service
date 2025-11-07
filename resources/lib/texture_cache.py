"""Texture cache operations for precaching and cleanup.

Manages Kodi's texture cache database for artwork optimization.
"""
from __future__ import annotations

import time
import threading
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import urllib.parse
from typing import Optional, List, Dict, Set, Any, Union, Callable
from datetime import datetime

from resources.lib.kodi import request, get_library_items
from resources.lib.kodi import log_artwork, log_cache
from resources.lib.database import init_database
from resources.lib.database.workflow import save_operation_stats, get_last_operation_stats
from resources.lib.ui_helper import format_operation_report, confirm_cancel_running_task
from resources.lib.worker_queue import WorkerQueue
from resources.lib.downloads.downloader import ArtworkDownloader
from resources.lib.downloads.path_builder import ArtworkPathBuilder

ADDON = xbmcaddon.Addon()

_cache_lock = threading.Lock()
_cached_urls_set: Optional[Set[str]] = None


def _parse_image_url(url: str) -> str:
    """
    Extract inner path from image:// wrapper.

    Args:
        url: URL potentially wrapped in image:// format

    Returns:
        Inner path without image:// prefix and trailing /
        Returns original URL if not in image:// format
    """
    if not url or not url.startswith('image://'):
        return url
    return url[8:-1] if url.endswith('/') else url[8:]


def should_precache_url(url: str) -> bool:
    """
    Determine if a URL should be pre-cached.

    Pre-cache library artwork from HTTP sources and local image files.
    Skip auto-generated thumbnails (video@, music@), addon icons, and system files.

    Args:
        url: Artwork URL (wrapped image:// format or decoded)

    Returns:
        True if URL should be pre-cached, False otherwise
    """
    if not url:
        return False

    # Normalize to decoded format for consistent filtering
    # decode_image_url() handles both wrapped and already-decoded URLs
    decoded = decode_image_url(url)

    # Skip video/music thumbnails (auto-generated, stored wrapped)
    if decoded.startswith('image://video@') or decoded.startswith('image://music@'):
        return False

    # Skip addon/plugin paths (browsing cache, not library artwork)
    if 'plugin://' in decoded:
        return False

    # Skip addon icon/fanart files
    addon_markers = ['/addons/', '\\addons\\', '/system/', '\\system\\']
    if any(marker in decoded for marker in addon_markers):
        return False

    # Skip built-in default icons
    if 'Default' in decoded and decoded.endswith('.png'):
        return False

    # Cache everything else: HTTP library artwork, local image files, network shares
    return True


def decode_image_url(url: str) -> str:
    """
    Decode an image:// wrapped URL to match database storage format.

    Database storage is inconsistent:
    - HTTP URLs: stored decoded (https://image.tmdb.org/...)
    - Video thumbnails: stored wrapped (image://video@...)
    - Local files: stored decoded (H:\\Movies\\poster.jpg)

    Args:
        url: URL potentially wrapped in image:// format

    Returns:
        URL in format matching database storage
    """
    if not url or not url.startswith('image://'):
        return url

    inner = _parse_image_url(url)

    # Check for special types (video@, music@, etc.)
    # These are stored WRAPPED in database, so return as-is
    if '@' in inner:
        return url

    # Regular URLs (http/local files) are stored decoded
    return urllib.parse.unquote(inner)


def encode_image_url(decoded_url: str) -> str:
    """
    Wrap a decoded URL back into image:// format for xbmcvfs.File().

    Reverse operation of decode_image_url() - converts decoded URLs back to
    wrapped format that Kodi's texture cache expects.

    Args:
        decoded_url: Decoded URL (https://..., H:\\..., or image://video@...)

    Returns:
        Wrapped URL (image://.../) suitable for Kodi's texture cache
    """
    if not decoded_url:
        return decoded_url

    # Special types are already wrapped
    if decoded_url.startswith('image://'):
        return decoded_url

    # Encode and wrap regular URLs (HTTP, local files, network shares)
    encoded = urllib.parse.quote(decoded_url, safe='')
    return f'image://{encoded}/'


def is_library_artwork_url(url: str) -> bool:
    """
    Determine if a URL represents library artwork vs system files.

    System files include:
    - Addon icons/fanart (in /addons/ or \\addons\\)
    - Kodi system resources (in /system/ or \\system\\)
    - Built-in default icons (DefaultVideo.png, etc.)

    Library artwork includes:
    - HTTP/HTTPS URLs (TMDB, fanart.tv, etc.)
    - image:// wrapped media thumbnails (video@, music@)
    - Local media files on typical media drives

    Args:
        url: Texture URL from cache

    Returns:
        True if URL is library artwork, False if system file
    """
    if not url:
        return False

    inner_url = _parse_image_url(url) if url.startswith('image://') else url
    decoded_url = urllib.parse.unquote(inner_url)

    system_markers = ['/addons/', '\\addons\\', '/system/', '\\system\\']
    if any(marker in decoded_url for marker in system_markers):
        return False

    special_folders = ['/.actors/', '\\.actors\\', '/.extrafanart/', '\\.extrafanart\\', '/.extrathumbs/', '\\.extrathumbs\\']
    if any(marker in decoded_url for marker in special_folders):
        return False

    if 'Default' in decoded_url and decoded_url.endswith('.png'):
        return False

    if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
        return True

    if url.startswith('image://') and '@' in inner_url:
        return True

    if ':' in decoded_url:
        drive = decoded_url.split(':')[0]
        if len(drive) == 1 and drive.upper() in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            return True

    if decoded_url.startswith('\\\\') or decoded_url.startswith('smb://') or decoded_url.startswith('nfs://'):
        return True

    return False


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
        log_artwork(f"Textures.GetTextures unexpected response: {resp}")
        return []
    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Error getting textures: {str(e)}", xbmc.LOGERROR)
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
        xbmc.log(f"SkinInfo TextureCache: Error removing texture {texture_id}: {str(e)}", xbmc.LOGERROR)
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
        xbmc.log(f"SkinInfo TextureCache: Error getting library URLs for {media_type}: {str(e)}", xbmc.LOGERROR)
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
        xbmc.log(f"SkinInfo TextureCache: Error getting all library URLs: {str(e)}", xbmc.LOGERROR)

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

    log_artwork(
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


class CacheAndDownloadQueue(WorkerQueue):
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
        self.downloaders: Dict[int, ArtworkDownloader] = {}
        self.path_builder = ArtworkPathBuilder()

        self.stats_cached = 0
        self.stats_cache_failed = 0
        self.stats_downloaded = 0
        self.stats_download_skipped = 0
        self.stats_download_failed = 0
        self.stats_bytes = 0

        log_cache(
            f"CacheAndDownloadQueue initialized with {self.num_workers} workers"
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
            log_cache(f"CacheAndDownloadQueue worker {worker_id} cached URL")
        except Exception as e:
            cache_error = str(e)
            self.stats_cache_failed += 1
            xbmc.log(
                f"SkinInfo: CacheAndDownloadQueue worker {worker_id} failed to cache URL: {str(e)}",
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
                if worker_id not in self.downloaders:
                    self.downloaders[worker_id] = ArtworkDownloader()

                downloader = self.downloaders[worker_id]

                download_success, download_error, bytes_downloaded = downloader.download_artwork(
                    url=url,
                    local_path=local_path,
                    artwork_type=artwork_type,
                    existing_file_mode=self.existing_file_mode
                )

                if download_success:
                    self.stats_downloaded += 1
                    self.stats_bytes += bytes_downloaded
                elif download_error is None:
                    self.stats_download_skipped += 1
                else:
                    self.stats_download_failed += 1
            else:
                log_artwork(
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

        log_artwork(f"Pre-cache: found {len(library_urls)} total library artwork URLs")

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

        log_artwork(
            f"Pre-cache: {stats['already_cached']} already cached, "
            f"{stats['needed_caching']} need caching, "
            f"{skipped_count} skipped (system/addon files)"
        )

        if stats['needed_caching'] == 0:
            log_artwork("Pre-cache: all URLs already cached, nothing to do")
            return stats

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(25, "Pre-Cache Artwork", f"Pre-caching {len(urls_to_cache)} images...")
            else:
                progress_dialog.update(
                    25,
                    f"[B]CANCEL TO RESUME LATER[/B][CR]Pre-caching {len(urls_to_cache)} images..."
                )

        from resources.lib.background_cache import BackgroundCacheQueue

        cache_queue = BackgroundCacheQueue(
            check_cached=False,
            abort_flag=task_context.abort_flag if task_context else None,
            task_context=task_context
        )
        cache_queue.start()

        try:
            queued = cache_queue.bulk_add_urls(urls_to_cache)
            log_artwork(f"Pre-cache: queued {queued} URLs for background processing")

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

                time.sleep(0.2)

            queue_stats = cache_queue.get_stats()
            stats['successfully_cached'] = queue_stats['successful']
            stats['failed'] = queue_stats['failed']

            status = "cancelled" if stats['cancelled'] else "complete"
            log_artwork(
                f"Pre-cache {status}: {stats['successfully_cached']} cached, {stats['failed']} failed"
            )

        finally:
            cache_queue.stop(wait=False)
            clear_cached_urls_cache()

    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Pre-cache failed: {str(e)}", xbmc.LOGERROR)
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

    Uses unified CacheAndDownloadQueue to avoid worker coordination issues.

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
            xbmc.log(
                f"SkinInfo: Error querying library for precache+download: {str(e)}",
                xbmc.LOGERROR
            )
            items = []

        stats['total_items'] = len(items)

        if not items:
            log_artwork("No items found for precache+download")
            return stats

        if progress_dialog:
            if isinstance(progress_dialog, xbmcgui.DialogProgressBG):
                progress_dialog.update(15, "Pre-Cache + Download", f"Processing {len(items)} items...")
            else:
                progress_dialog.update(15, f"Processing {len(items)} items...")

        existing_file_mode_setting = ADDON.getSetting('download.existing_file_mode')
        existing_file_mode_int = int(existing_file_mode_setting) if existing_file_mode_setting else 0
        existing_file_mode = ['skip', 'overwrite', 'use_existing'][existing_file_mode_int]

        queue = CacheAndDownloadQueue(
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
            log_artwork(f"Pre-cache+download: queued {queued} URLs for processing")

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

                time.sleep(0.2)

            queue_stats = queue.get_stats()
            stats['cached'] = queue_stats['cached']
            stats['cache_failed'] = queue_stats['cache_failed']
            stats['downloaded'] = queue_stats['downloaded']
            stats['download_skipped'] = queue_stats['download_skipped']
            stats['download_failed'] = queue_stats['download_failed']
            stats['bytes_downloaded'] = queue_stats['bytes_downloaded']

            status = "cancelled" if stats['cancelled'] else "complete"
            log_artwork(
                f"Pre-cache+download {status}: {stats['cached']} cached, {stats['downloaded']} downloaded"
            )

        finally:
            queue.stop(wait=False)
            clear_cached_urls_cache()

    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Pre-cache+download failed: {str(e)}", xbmc.LOGERROR)
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
        log_artwork(f"Starting orphaned texture cleanup for media types: {media_types}")

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

        log_artwork(f"Found {stats['orphaned_found']} orphaned textures")

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
        log_artwork(f"Cleanup {status}: {stats['removed']} removed, {stats['failed']} failed")

    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Orphaned cleanup failed: {str(e)}", xbmc.LOGERROR)

    return stats


def run_texture_maintenance() -> None:
    """
    Show texture cache manager menu and execute selected operations.

    Available operations:
    - Pre-Cache Library Artwork: Cache all library artwork not yet cached
    - Cleanup Textures: Remove orphaned/old/unused textures
    - Statistics & Info: View texture cache statistics
    - View Last Report: Show stats from last completed operation
    """
    init_database()

    while True:
        action = _show_main_menu()

        if action is None:
            break
        elif action == "precache":
            _handle_precache()
        elif action == "precache_download":
            _handle_precache_download()
        elif action == "cleanup":
            _show_cleanup_menu()
        elif action == "stats":
            _handle_stats()
        elif action == "report":
            _show_last_report()


def _show_main_menu() -> Optional[str]:
    """Show main texture cache menu and return selected action."""
    from resources.lib.ui_helper import show_menu_with_cancel

    options = [
        (ADDON.getLocalizedString(32083), "precache")
    ]

    enable_combo = ADDON.getSetting("download.enable_combo_workflows") == "true"
    if enable_combo:
        options.append(("Pre-Cache + Download to Filesystem", "precache_download"))

    options.extend([
        (ADDON.getLocalizedString(32087), "cleanup"),
        (ADDON.getLocalizedString(32085), "stats")
    ])

    precache_stats = get_last_operation_stats('texture_precache')
    cleanup_stats = get_last_operation_stats('texture_cleanup')

    last_stats = None
    if precache_stats and cleanup_stats:
        precache_time = datetime.fromisoformat(precache_stats['timestamp'])
        cleanup_time = datetime.fromisoformat(cleanup_stats['timestamp'])
        last_stats = precache_stats if precache_time > cleanup_time else cleanup_stats
    elif precache_stats:
        last_stats = precache_stats
    elif cleanup_stats:
        last_stats = cleanup_stats

    if last_stats:
        options.append((ADDON.getLocalizedString(32086), "report"))

    action, cancelled = show_menu_with_cancel(ADDON.getLocalizedString(32082), options)

    if cancelled:
        xbmcgui.Dialog().notification(
            "Texture Cache",
            "Task cancelled",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return None

    return action


def _handle_precache() -> None:
    """Handle pre-cache library artwork operation."""
    from resources.lib import task_manager
    from resources.lib.ui_helper import show_menu_with_cancel

    media_type_options = [
        ("All Media", "all"),
        ("Movies", "movie"),
        ("TV Shows", "tvshow"),
        ("Seasons", "season"),
        ("Episodes", "episode"),
        ("Music Videos", "musicvideo"),
        ("Movie Sets", "set"),
        ("Artists", "artist"),
        ("Albums", "album")
    ]

    scope_choice, cancelled = show_menu_with_cancel("Pre-Cache Artwork - Select Scope", media_type_options)

    if cancelled or scope_choice is None:
        return

    selected_types: Optional[List[str]] = None if scope_choice == "all" else [scope_choice]

    mode_options = [
        ("Show progress dialog (Foreground)", "foreground"),
        ("Run in background", "background")
    ]

    mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

    if mode_cancelled or mode_value is None:
        return

    use_background = (mode_value == "background")

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    "Task Already Running",
                    f"[B]{current_task}[/B] is currently running.[CR][CR]Cannot start another background task."
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task("Pre-Cache Artwork"):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext("Pre-Cache Artwork") as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create("Pre-Cache Artwork", "Starting pre-cache...")
            else:
                progress = xbmcgui.DialogProgress()
                progress.create("Pre-Cache Artwork", "Starting pre-cache...")
            stats = precache_library_artwork(progress_dialog=progress, media_types=selected_types, task_context=ctx)
            progress.close()

        save_operation_stats('texture_precache', {
            'cached_count': stats['already_cached'] + stats['successfully_cached'],
            'total_count': stats.get('total_urls', 0),
            'new_count': stats['successfully_cached'],
            'failed_count': stats.get('failed', 0),
            'cancelled': stats.get('cancelled', False)
        })

        total = stats['total_urls']
        already = stats['already_cached']
        newly = stats['successfully_cached']
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = "Pre-Cache Cancelled"
        else:
            title = "Pre-Cache Complete"

        message_parts = [
            f"Total: {total}",
            f"Already Cached: {already}",
            f"Newly Cached: {newly}"
        ]

        if stats['failed'] > 0:
            message_parts.append(f"Failed: {stats['failed']}")

        if cancelled:
            message_parts.append("")
            message_parts.append("[B]Status: Cancelled[/B]")

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        xbmc.log(f"SkinInfo TextureCache: Pre-cache failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Pre-Cache Artwork", f"Operation failed:[CR]{str(e)}")


def _handle_precache_download() -> None:
    """Handle pre-cache + download operation."""
    from resources.lib import task_manager
    from resources.lib.ui_helper import show_menu_with_cancel

    media_type_options = [
        ("All Media", "all"),
        ("Movies", "movie"),
        ("TV Shows", "tvshow"),
        ("Seasons", "season"),
        ("Episodes", "episode"),
        ("Music Videos", "musicvideo"),
        ("Movie Sets", "set"),
        ("Artists", "artist"),
        ("Albums", "album")
    ]

    scope_choice, cancelled = show_menu_with_cancel("Pre-Cache + Download - Select Scope", media_type_options)

    if cancelled or scope_choice is None:
        return

    selected_types: Optional[List[str]] = None if scope_choice == "all" else [scope_choice]

    mode_options = [
        ("Show progress dialog (Foreground)", "foreground"),
        ("Run in background", "background")
    ]

    mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

    if mode_cancelled or mode_value is None:
        return

    use_background = (mode_value == "background")

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    "Task Already Running",
                    f"[B]{current_task}[/B] is currently running.[CR][CR]Cannot start another background task."
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task("Pre-Cache + Download"):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext("Pre-Cache + Download Artwork") as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create("Pre-Cache + Download", "Starting...")
            else:
                progress = xbmcgui.DialogProgress()
                progress.create("Pre-Cache + Download", "Starting...")
            stats = precache_and_download_artwork(progress_dialog=progress, media_types=selected_types, task_context=ctx)
            progress.close()

        total = stats['total_urls']
        cached = stats['cached']
        downloaded = stats['downloaded']
        skipped = stats['download_skipped']
        cache_failed = stats['cache_failed']
        download_failed = stats['download_failed']
        mb = stats['bytes_downloaded'] / (1024 * 1024) if stats['bytes_downloaded'] > 0 else 0
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = "Pre-Cache + Download Cancelled"
        else:
            title = "Pre-Cache + Download Complete"

        message_parts = [
            f"Total: {total}",
            f"Cached: {cached}",
            f"Downloaded: {downloaded} ({mb:.1f} MB)",
            f"Skipped: {skipped}"
        ]

        if cache_failed > 0 or download_failed > 0:
            message_parts.append(f"Failed: {cache_failed} cache, {download_failed} download")

        if cancelled:
            message_parts.append("")
            message_parts.append("[B]Status: Cancelled[/B]")

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        xbmc.log(f"SkinInfo TextureCache: Pre-cache+download failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Pre-Cache + Download", f"Operation failed:[CR]{str(e)}")


def _show_cleanup_menu() -> None:
    """Show cleanup submenu and handle selection."""
    from resources.lib.ui_helper import show_menu_with_cancel

    while True:
        options = [
            (ADDON.getLocalizedString(32088), "standard"),
            (ADDON.getLocalizedString(32092), "advanced")
        ]

        action, cancelled = show_menu_with_cancel(ADDON.getLocalizedString(32087), options)

        if cancelled or action is None:
            break

        if action == "standard":
            _handle_standard_cleanup()
        elif action == "advanced":
            _show_advanced_cleanup_menu()


def _show_advanced_cleanup_menu() -> None:
    """Show advanced cleanup submenu and handle selection."""
    from resources.lib.ui_helper import show_menu_with_cancel

    while True:
        options = [
            (ADDON.getLocalizedString(32089), "age"),
            (ADDON.getLocalizedString(32090), "usage"),
            (ADDON.getLocalizedString(32091), "pattern")
        ]

        action, cancelled = show_menu_with_cancel(ADDON.getLocalizedString(32092), options)

        if cancelled or action is None:
            break

        if action == "age":
            _handle_age_cleanup()
        elif action == "usage":
            _handle_usage_cleanup()
        elif action == "pattern":
            _handle_pattern_cleanup()


def _handle_standard_cleanup() -> None:
    """Handle standard orphaned texture cleanup."""
    from resources.lib import task_manager
    from resources.lib.ui_helper import show_menu_with_cancel

    mode_options = [
        ("Show progress dialog (Foreground)", "foreground"),
        ("Run in background", "background")
    ]

    mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

    if mode_cancelled or mode_value is None:
        return

    use_background = (mode_value == "background")

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    "Task Already Running",
                    f"[B]{current_task}[/B] is currently running.[CR][CR]Cannot start another background task."
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task("Clean Orphaned Textures"):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext("Clean Orphaned Textures") as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create("Clean Orphaned Textures", "Starting cleanup...")
            else:
                progress = xbmcgui.DialogProgress()
                progress.create("Clean Orphaned Textures", "Starting cleanup...")
            stats = cleanup_orphaned_textures(progress_dialog=progress, media_types=None, task_context=ctx)
            progress.close()

        save_operation_stats('texture_cleanup', {
            'cached_count': stats['total_library'],
            'total_count': stats['total_cached'],
            'removed_count': stats['removed'],
            'orphaned_count': stats['orphaned_found'],
            'cancelled': stats.get('cancelled', False)
        })

        total_cached = stats['total_cached']
        library = stats['total_library']
        orphaned_found = stats['orphaned_found']
        removed = stats['removed']
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = "Cleanup Cancelled"
        else:
            title = "Cleanup Complete"

        message_parts = [
            f"Total Cached: {total_cached} | Library: {library}",
            f"Orphaned Found: {orphaned_found} | Removed: {removed}"
        ]

        if stats['failed'] > 0:
            message_parts.append(f"Failed: {stats['failed']}")

        if cancelled:
            message_parts.append("Status: Cancelled")

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        xbmc.log(f"SkinInfo TextureCache: Cleanup failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Cleanup Textures", f"Operation failed:[CR]{str(e)}")


def _calculate_texture_statistics(progress: xbmcgui.DialogProgress) -> Optional[Dict[str, Any]]:
    """Calculate comprehensive texture cache statistics."""
    from datetime import datetime
    import os
    import xbmcvfs

    try:
        progress.update(10, "Fetching texture database...")
        textures = get_cached_textures()

        if not textures:
            return None

        total_textures = len(textures)
        total_sizes = 0
        age_buckets = {'0-7': 0, '8-30': 0, '31-90': 0, '91-180': 0, '180+': 0, 'unknown': 0}
        usage_buckets = {'0': 0, '1-5': 0, '6-20': 0, '21-50': 0, '50+': 0}
        type_breakdown = {'library': 0, 'video_thumb': 0, 'music': 0, 'other': 0}

        now = datetime.now()
        thumbnails_path = xbmcvfs.translatePath("special://thumbnails")
        disk_usage = 0

        progress.update(30, f"Analyzing {total_textures} textures...")

        for i, texture in enumerate(textures):
            if progress.iscanceled():
                return None

            if i % 100 == 0:
                progress.update(30 + int((i / total_textures) * 50))

            sizes = texture.get('sizes', [])
            total_sizes += len(sizes)

            url = texture.get('url', '')

            if is_library_artwork_url(url):
                type_breakdown['library'] += 1
            elif 'video@' in url:
                type_breakdown['video_thumb'] += 1
            elif 'music@' in url or 'musicdb://' in url:
                type_breakdown['music'] += 1
            else:
                type_breakdown['other'] += 1

            for size in sizes:
                lastusetime = size.get('lastusetime')
                raw_usecount = size.get('usecount', 0)
                raw_width = size.get('width', 0)

                if raw_width < 256 and raw_usecount >= 256:
                    usecount = raw_width
                else:
                    usecount = raw_usecount

                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        days_ago = (now - last_used).days

                        if days_ago <= 7:
                            age_buckets['0-7'] += 1
                        elif days_ago <= 30:
                            age_buckets['8-30'] += 1
                        elif days_ago <= 90:
                            age_buckets['31-90'] += 1
                        elif days_ago <= 180:
                            age_buckets['91-180'] += 1
                        else:
                            age_buckets['180+'] += 1
                    except Exception:
                        age_buckets['unknown'] += 1
                else:
                    age_buckets['unknown'] += 1

                if usecount == 0:
                    usage_buckets['0'] += 1
                elif usecount <= 5:
                    usage_buckets['1-5'] += 1
                elif usecount <= 20:
                    usage_buckets['6-20'] += 1
                elif usecount <= 50:
                    usage_buckets['21-50'] += 1
                else:
                    usage_buckets['50+'] += 1

        progress.update(80, "Calculating disk usage...")

        try:
            for root, dirs, files in os.walk(thumbnails_path):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        disk_usage += os.path.getsize(filepath)
                    except Exception:
                        pass
        except Exception as e:
            xbmc.log(f"SkinInfo TextureCache: Disk usage calculation failed: {str(e)}", xbmc.LOGWARNING)

        progress.update(100, "Complete")

        return {
            'total_textures': total_textures,
            'total_sizes': total_sizes,
            'disk_usage': disk_usage,
            'age_buckets': age_buckets,
            'usage_buckets': usage_buckets,
            'type_breakdown': type_breakdown
        }

    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Statistics calculation failed: {str(e)}", xbmc.LOGERROR)
        return None


def _format_statistics_report(stats: Dict[str, Any]) -> str:
    """Format statistics into readable report."""
    total_textures = stats['total_textures']
    total_sizes = stats['total_sizes']
    disk_usage = stats['disk_usage']
    age_buckets = stats['age_buckets']
    usage_buckets = stats['usage_buckets']
    type_breakdown = stats['type_breakdown']

    disk_gb = disk_usage / (1024 ** 3)
    disk_mb = disk_usage / (1024 ** 2)

    lines = [
        "=" * 50,
        "   TEXTURE CACHE STATISTICS",
        "=" * 50,
        "",
        "OVERVIEW",
        "-" * 50,
        f"Total Textures:      {total_textures:,}",
        f"Total Cached Sizes:  {total_sizes:,}",
    ]

    if disk_usage > 0:
        if disk_gb >= 0.1:
            lines.append(f"Disk Usage:          {disk_gb:.2f} GB ({disk_usage:,} bytes)")
        else:
            lines.append(f"Disk Usage:          {disk_mb:.2f} MB ({disk_usage:,} bytes)")
    else:
        lines.append("Disk Usage:          Unable to calculate")

    lines.extend([
        "",
        "AGE DISTRIBUTION (by cached size)",
        "-" * 50
    ])

    age_labels = {
        '0-7': 'Last 7 days',
        '8-30': '8-30 days',
        '31-90': '31-90 days',
        '91-180': '91-180 days',
        '180+': 'Over 180 days',
        'unknown': 'Unknown'
    }

    for key in ['0-7', '8-30', '31-90', '91-180', '180+', 'unknown']:
        count = age_buckets.get(key, 0)
        pct = (count / total_sizes * 100) if total_sizes > 0 else 0
        lines.append(f"{age_labels[key]:18s}  {count:6,} sizes ({pct:5.1f}%)")

    lines.extend([
        "",
        "USAGE DISTRIBUTION (by cached size)",
        "-" * 50
    ])

    usage_labels = {
        '0': 'Never used',
        '1-5': '1-5 times',
        '6-20': '6-20 times',
        '21-50': '21-50 times',
        '50+': 'Over 50 times'
    }

    for key in ['0', '1-5', '6-20', '21-50', '50+']:
        count = usage_buckets.get(key, 0)
        pct = (count / total_sizes * 100) if total_sizes > 0 else 0
        lines.append(f"{usage_labels[key]:18s}  {count:6,} sizes ({pct:5.1f}%)")

    lines.extend([
        "",
        "MEDIA TYPE BREAKDOWN (by texture)",
        "-" * 50
    ])

    type_labels = {
        'library': 'Library Artwork',
        'video_thumb': 'Video Thumbnails',
        'music': 'Music Artwork',
        'other': 'Other/System'
    }

    for key in ['library', 'video_thumb', 'music', 'other']:
        count = type_breakdown.get(key, 0)
        pct = (count / total_textures * 100) if total_textures > 0 else 0
        lines.append(f"{type_labels[key]:18s}  {count:6,} textures ({pct:5.1f}%)")

    lines.extend([
        "",
        "=" * 50
    ])

    return "\n".join(lines)


def _handle_stats() -> None:
    """Show texture cache statistics."""
    dialog = xbmcgui.Dialog()
    progress = xbmcgui.DialogProgress()
    progress.create("Texture Cache Statistics", "Gathering statistics...")

    try:
        stats = _calculate_texture_statistics(progress)
        progress.close()

        if stats:
            report = _format_statistics_report(stats)
            dialog.textviewer("Texture Cache Statistics", report)
        else:
            dialog.ok("Texture Cache Statistics", "Failed to gather statistics.")
    except Exception as e:
        progress.close()
        xbmc.log(f"SkinInfo TextureCache: Stats failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Texture Cache Statistics", f"Operation failed:[CR]{str(e)}")


def cleanup_textures_by_age(
    age_days: int,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    task_context: Optional[Any] = None
) -> Dict[str, int]:
    """
    Remove textures not used in specified number of days.

    Args:
        age_days: Remove textures not used in this many days
        progress_dialog: Optional progress dialog
        task_context: Optional task context for cancellation

    Returns:
        Dict with stats: total_textures, old_textures, removed, failed, cancelled
    """
    from datetime import datetime, timedelta

    stats = {
        'total_textures': 0,
        'old_textures': 0,
        'removed': 0,
        'failed': 0,
        'cancelled': False
    }

    try:
        if progress_dialog:
            progress_dialog.update(0, "Fetching texture database...")

        textures = get_cached_textures()
        stats['total_textures'] = len(textures)

        if not textures:
            return stats

        cutoff_date = datetime.now() - timedelta(days=age_days)
        old_textures = []

        if progress_dialog:
            progress_dialog.update(10, f"Analyzing {len(textures)} textures...")

        for i, texture in enumerate(textures):
            if task_context and task_context.is_cancelled():
                stats['cancelled'] = True
                return stats

            if progress_dialog and i % 100 == 0:
                if isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled():
                    stats['cancelled'] = True
                    return stats
                progress_dialog.update(10 + int((i / len(textures)) * 40))

            sizes = texture.get('sizes', [])
            if not sizes:
                continue

            for size in sizes:
                lastusetime = size.get('lastusetime')
                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        if last_used < cutoff_date:
                            old_textures.append(texture)
                            break
                    except Exception:
                        pass

        stats['old_textures'] = len(old_textures)

        if not old_textures:
            return stats

        if progress_dialog:
            progress_dialog.update(50, f"Removing {len(old_textures)} old textures...")

        for i, texture in enumerate(old_textures):
            if task_context and task_context.is_cancelled():
                stats['cancelled'] = True
                return stats

            if progress_dialog and i % 10 == 0:
                if isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled():
                    stats['cancelled'] = True
                    return stats
                progress_dialog.update(50 + int((i / len(old_textures)) * 50))

            texture_id = texture.get('textureid')
            if texture_id:
                if remove_texture(texture_id):
                    stats['removed'] += 1
                else:
                    stats['failed'] += 1

        if progress_dialog:
            progress_dialog.update(100, "Complete")

    except Exception as e:
        xbmc.log(f"SkinInfo TextureCache: Age cleanup failed: {str(e)}", xbmc.LOGERROR)
        raise

    return stats


def _handle_age_cleanup() -> None:
    """Handle age-based texture cleanup."""
    from resources.lib import task_manager
    from resources.lib.ui_helper import show_menu_with_cancel

    age_options = [
        ("30 days", "30"),
        ("60 days", "60"),
        ("90 days", "90"),
        ("180 days", "180"),
        ("365 days (1 year)", "365")
    ]

    age_str, age_cancelled = show_menu_with_cancel("Remove textures not used in...", age_options)

    if age_cancelled or age_str is None:
        return

    age_days = int(age_str)

    dialog = xbmcgui.Dialog()
    progress = xbmcgui.DialogProgress()
    progress.create("Analyzing Textures", "Scanning texture cache...")

    try:
        from datetime import datetime, timedelta

        textures = get_cached_textures()
        total_textures = len(textures)

        if not textures:
            progress.close()
            dialog.ok("No Textures", "No textures found in cache.")
            return

        cutoff_date = datetime.now() - timedelta(days=age_days)
        old_textures = []
        oldest_date = None

        progress.update(20, f"Analyzing {total_textures} textures...")

        for i, texture in enumerate(textures):
            if progress.iscanceled():
                progress.close()
                return

            if i % 100 == 0:
                progress.update(20 + int((i / total_textures) * 60))

            sizes = texture.get('sizes', [])
            if not sizes:
                continue

            for size in sizes:
                lastusetime = size.get('lastusetime')
                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        if last_used < cutoff_date:
                            old_textures.append(texture)
                            if oldest_date is None or last_used < oldest_date:
                                oldest_date = last_used
                            break
                    except Exception:
                        pass

        progress.close()

        if not old_textures:
            dialog.ok(
                "No Old Textures",
                f"No textures found older than {age_days} days.[CR][CR]"
                f"Total textures checked: {total_textures}"
            )
            return

        oldest_str = oldest_date.strftime('%Y-%m-%d') if oldest_date else "Unknown"

        confirm = dialog.yesno(
            "Confirm Cleanup",
            f"Remove {len(old_textures)} textures older than {age_days} days?[CR]"
            f"Total: {total_textures} | Oldest: {oldest_str}"
        )

        if not confirm:
            return

    except Exception as e:
        progress.close()
        xbmc.log(f"SkinInfo TextureCache: Analysis failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Analysis Failed", f"Failed to analyze textures:[CR]{str(e)}")
        return

    mode_options = [
        ("Show progress dialog (Foreground)", "foreground"),
        ("Run in background", "background")
    ]

    mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

    if mode_cancelled or mode_value is None:
        return

    use_background = (mode_value == "background")

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    "Task Already Running",
                    f"[B]{current_task}[/B] is currently running.[CR][CR]Cannot start another background task."
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task(f"Clean Textures Older Than {age_days} Days"):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext(f"Clean Textures Older Than {age_days} Days") as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create("Cleanup Textures by Age", "Starting cleanup...")
            else:
                progress = xbmcgui.DialogProgress()
                progress.create("Cleanup Textures by Age", "Starting cleanup...")
            stats = cleanup_textures_by_age(age_days, progress_dialog=progress, task_context=ctx)
            progress.close()

        save_operation_stats('texture_age_cleanup', {
            'age_days': age_days,
            'total_count': stats['total_textures'],
            'old_count': stats['old_textures'],
            'removed_count': stats['removed'],
            'cancelled': stats.get('cancelled', False)
        })

        total_textures = stats['total_textures']
        old_textures = stats['old_textures']
        removed = stats['removed']
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = "Cleanup Cancelled"
        else:
            title = "Cleanup Complete"

        message_parts = [
            f"Checked: {total_textures} textures",
            f"Older than {age_days} days: {old_textures}",
            f"Removed: {removed}"
        ]

        if stats['failed'] > 0:
            message_parts.append(f"Failed: {stats['failed']}")

        if cancelled:
            message_parts.append("Status: Cancelled")

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        xbmc.log(f"SkinInfo TextureCache: Age cleanup failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Cleanup Textures", f"Operation failed:[CR]{str(e)}")


def _handle_usage_cleanup() -> None:
    """Handle usage-based texture cleanup."""
    xbmcgui.Dialog().ok(
        "Cleanup by Usage",
        "Feature coming soon![CR][CR]"
        "Will remove textures accessed fewer than N times[CR]"
        "(e.g., never used, used < 5 times)[CR][CR]"
        "Useful for removing rarely-viewed images."
    )


def _handle_pattern_cleanup() -> None:
    """Handle pattern-based force re-cache."""
    xbmcgui.Dialog().ok(
        "Force Re-Cache by Pattern",
        "Feature coming soon![CR][CR]"
        "Will remove textures matching a URL pattern[CR]"
        "(e.g., 'image.tmdb.org/t/p/original/')[CR][CR]"
        "Forces Kodi to re-download matching images."
    )


def _show_last_report() -> None:
    """Show last operation report."""
    precache_stats = get_last_operation_stats('texture_precache')
    cleanup_stats = get_last_operation_stats('texture_cleanup')

    last_stats = None
    if precache_stats and cleanup_stats:
        precache_time = datetime.fromisoformat(precache_stats['timestamp'])
        cleanup_time = datetime.fromisoformat(cleanup_stats['timestamp'])
        last_stats = precache_stats if precache_time > cleanup_time else cleanup_stats
    elif precache_stats:
        last_stats = precache_stats
    elif cleanup_stats:
        last_stats = cleanup_stats

    if last_stats:
        report_text = format_operation_report(
            last_stats['operation'],
            last_stats['stats'],
            last_stats['timestamp']
        )
        xbmcgui.Dialog().textviewer("Texture Cache - Last Run", report_text)
    else:
        xbmcgui.Dialog().ok(
            "View Last Report",
            "No previous operations found."
        )
