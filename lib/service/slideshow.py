"""Slideshow functionality for rotating fanart backgrounds.

Provides window properties with random fanart from library for skin slideshows.
"""
from __future__ import annotations

import random
import time
import threading
import xbmc
import xbmcvfs
from typing import Optional, Dict, Any, Set, List

from lib.data.database import slideshow as db_slideshow
from lib.kodi.utils import set_prop, clear_prop
from lib.kodi.client import decode_image_url, log, request

MIN_SLIDESHOW_INTERVAL = 5
MAX_SLIDESHOW_INTERVAL = 3600
DEFAULT_SLIDESHOW_INTERVAL = 10

_cached_texture_urls: Optional[Set[str]] = None
_cache_lock = threading.Lock()


def _get_cached_texture_urls() -> Set[str]:
    """
    Get all cached texture URLs from Kodi's texture cache via JSON-RPC.
    Results are cached in memory for performance.

    Returns:
        Set of decoded texture URLs that exist in cache
    """
    global _cached_texture_urls

    with _cache_lock:
        if _cached_texture_urls is not None:
            return _cached_texture_urls

    response = request("Textures.GetTextures", {"properties": ["url"]})

    cached_urls = set()
    if response and 'textures' in response.get('result', {}):
        for texture in response['result']['textures']:
            url = texture.get('url', '')
            if url:
                decoded = decode_image_url(url)
                cached_urls.add(decoded)

    with _cache_lock:
        _cached_texture_urls = cached_urls

    log("Service", f"Slideshow: Loaded {len(cached_urls)} cached texture URLs")
    return cached_urls


def clear_cached_texture_urls() -> None:
    """Clear the cached texture URLs set to force reload on next query."""
    global _cached_texture_urls
    with _cache_lock:
        _cached_texture_urls = None


def get_random_uncached_fanart_urls(count: int = 20) -> List[str]:
    """
    Get random uncached fanart URLs from slideshow pool for background pre-caching.

    Args:
        count: Number of URLs to retrieve

    Returns:
        List of uncached fanart URLs
    """
    cached_urls = _get_cached_texture_urls()
    uncached = []

    urls = db_slideshow.get_random_fanart_urls(count * 3)
    for fanart in urls:
        if fanart.strip():
            decoded = decode_image_url(fanart)
            if decoded not in cached_urls:
                uncached.append(fanart)
                if len(uncached) >= count:
                    break

    return uncached


def _cache_image_url(url: str) -> bool:
    """
    Force Kodi to cache an image URL.

    Args:
        url: Image URL (wrapped or decoded)

    Returns:
        True if successfully cached
    """
    if not url:
        return False

    from lib.kodi.client import encode_image_url
    wrapped_url = encode_image_url(url) if not url.startswith('image://') else url

    try:
        with xbmcvfs.File(wrapped_url):
            pass
        return True
    except Exception as e:
        log("Service", f"Slideshow: Failed to cache URL {url}: {e}", xbmc.LOGWARNING)
        return False


def _build_pool_records(media_type: str, items: list, id_key: str, title_key: str,
                        fanart_key: str, description_key: str, current_time: int) -> List[tuple]:
    records = []
    for item in items:
        if media_type == 'artist':
            fanart = item.get(fanart_key, '')
            year = None
        else:
            fanart = item.get('art', {}).get(fanart_key, '')
            year = item.get('year')

        records.append((
            item[id_key],
            media_type,
            item.get(title_key, ''),
            fanart,
            item.get(description_key, ''),
            year,
            None,
            None,
            current_time
        ))
    return records


def populate_slideshow_pool() -> None:
    """
    Populate slideshow_pool table from Kodi library.
    Queries JSON-RPC for all movies, TV shows, and artists with fanart.
    """
    current_time = int(time.time())

    movies = _get_movies_with_fanart()
    tvshows = _get_tvshows_with_fanart()
    artists = _get_artists_with_fanart()

    movie_records = _build_pool_records('movie', movies, 'movieid', 'title', 'fanart', 'plot', current_time)
    tvshow_records = _build_pool_records('tvshow', tvshows, 'tvshowid', 'title', 'fanart', 'plot', current_time)
    artist_records = _build_pool_records('artist', artists, 'artistid', 'artist', 'fanart', 'description', current_time)

    db_slideshow.populate_pool(movie_records, tvshow_records, artist_records)

    log("Service", f"Slideshow: Pool populated with {len(movies)} movies, {len(tvshows)} TV shows, {len(artists)} artists")


def sync_slideshow_pool() -> None:
    """
    Sync slideshow_pool with current library state.
    For now, does full rebuild. Future: incremental sync.
    """
    populate_slideshow_pool()


def _get_movies_with_fanart() -> list:
    """Query Kodi for movies with fanart."""
    response = request("VideoLibrary.GetMovies", {
        "properties": ["title", "art", "year", "plot"]
    })

    if response and 'movies' in response.get('result', {}):
        return [m for m in response['result']['movies']
                if m.get('art', {}).get('fanart', '').strip()]
    return []


def _get_tvshows_with_fanart() -> list:
    """Query Kodi for TV shows with fanart."""
    response = request("VideoLibrary.GetTVShows", {
        "properties": ["title", "art", "year", "plot"]
    })

    if response and 'tvshows' in response.get('result', {}):
        return [s for s in response['result']['tvshows']
                if s.get('art', {}).get('fanart', '').strip()]
    return []




def _get_artists_with_fanart() -> list:
    """Query Kodi for artists with fanart."""
    response = request("AudioLibrary.GetArtists", {
        "properties": ["fanart", "description"]
    })

    if not response or 'artists' not in response.get('result', {}):
        log("Service", "Slideshow: GetArtists returned no results", xbmc.LOGWARNING)
        return []

    all_artists = response['result']['artists']
    log("Service", f"Slideshow: GetArtists returned {len(all_artists)} total artists")

    artists_with_fanart = []

    for artist in all_artists:
        fanart = artist.get('fanart', '').strip()

        if fanart:
            artists_with_fanart.append({
                'artistid': artist.get('artistid'),
                'artist': artist.get('artist', ''),
                'fanart': fanart,
                'description': artist.get('description', '')
            })

    log("Service", f"Slideshow: Found {len(artists_with_fanart)} artists with fanart")
    return artists_with_fanart


def _get_random_item(media_types: List[str], select_fields: List[str], result_mapping: Dict[str, str], attempt_count: int = 10) -> Optional[Dict[str, Any]]:
    """
    Generic random item getter with cached fanart preference.
    Ensures fanart is cached before returning.

    Args:
        media_types: List of media types to query (e.g., ['movie'], ['movie', 'tvshow'])
        select_fields: Database fields to SELECT
        result_mapping: Maps database field names to result dict keys
        attempt_count: Number of random rows to check for cached fanart

    Returns:
        Random item with cached or newly-cached fanart, or None
    """
    cached_urls = _get_cached_texture_urls()
    media_type_label = '/'.join(media_types)

    rows = db_slideshow.get_random_pool_items(media_types, select_fields, attempt_count)

    for row in rows:
        fanart = row['fanart']
        if fanart:
            decoded = decode_image_url(fanart)
            if decoded in cached_urls:
                return {result_mapping[k]: row[k] for k in result_mapping}

    log("Service", f"Slideshow: No cached {media_type_label} fanart found in sample, caching random item")

    fallback_rows = db_slideshow.get_random_pool_items(media_types, select_fields, 1)
    row = fallback_rows[0] if fallback_rows else None
    if row and row['fanart']:
        if _cache_image_url(row['fanart']):
            with _cache_lock:
                if _cached_texture_urls is not None:
                    decoded = decode_image_url(row['fanart'])
                    _cached_texture_urls.add(decoded)
            log("Service", f"Slideshow: Cached {media_type_label} fanart: {row['fanart']}")
            return {result_mapping[k]: row[k] for k in result_mapping}
        else:
            log("Service", f"Slideshow: Failed to cache {media_type_label} fanart", xbmc.LOGWARNING)

    return None


def get_random_movie() -> Optional[Dict[str, Any]]:
    """
    Get random movie from slideshow pool, preferring cached fanart.
    Caches synchronously if no cached items found.
    """
    return _get_random_item(
        media_types=['movie'],
        select_fields=['title', 'fanart', 'description', 'year'],
        result_mapping={
            'title': 'title',
            'fanart': 'fanart',
            'description': 'plot',
            'year': 'year'
        }
    )


def get_random_tvshow() -> Optional[Dict[str, Any]]:
    """
    Get random TV show from slideshow pool, preferring cached fanart.
    Caches synchronously if no cached items found.
    """
    return _get_random_item(
        media_types=['tvshow'],
        select_fields=['title', 'fanart', 'description', 'year'],
        result_mapping={
            'title': 'title',
            'fanart': 'fanart',
            'description': 'plot',
            'year': 'year'
        }
    )




def get_random_artist() -> Optional[Dict[str, Any]]:
    """
    Get random artist from slideshow pool, preferring cached fanart.
    Caches synchronously if no cached items found.
    """
    return _get_random_item(
        media_types=['artist'],
        select_fields=['title', 'fanart', 'description'],
        result_mapping={
            'title': 'artist',
            'fanart': 'fanart',
            'description': 'description'
        }
    )


def get_random_video() -> Optional[Dict[str, Any]]:
    """
    Get random video (movie or tvshow) from slideshow pool, preferring cached fanart.
    Caches synchronously if no cached items found.
    """
    return _get_random_item(
        media_types=['movie', 'tvshow'],
        select_fields=['title', 'fanart', 'description', 'media_type', 'year'],
        result_mapping={
            'title': 'title',
            'fanart': 'fanart',
            'description': 'plot',
            'media_type': 'media_type',
            'year': 'year'
        }
    )


def get_random_global() -> Optional[Dict[str, Any]]:
    """
    Get random item from any media type in slideshow pool, preferring cached fanart.
    Caches synchronously if no cached items found.
    """
    return _get_random_item(
        media_types=['movie', 'tvshow', 'artist'],
        select_fields=['title', 'fanart', 'description', 'media_type'],
        result_mapping={
            'title': 'title',
            'fanart': 'fanart',
            'description': 'description',
            'media_type': 'media_type'
        }
    )


def set_movie_slideshow_properties(item: Dict[str, Any]) -> None:
    """Set SkinInfo.Slideshow.Movie.* properties."""
    set_prop('SkinInfo.Slideshow.Movie.Title', item.get('title', ''))
    set_prop('SkinInfo.Slideshow.Movie.FanArt', item.get('fanart', ''))
    set_prop('SkinInfo.Slideshow.Movie.Plot', item.get('plot', ''))
    set_prop('SkinInfo.Slideshow.Movie.Year', str(item.get('year', '')) if item.get('year') else '')


def set_tv_slideshow_properties(item: Dict[str, Any]) -> None:
    """Set SkinInfo.Slideshow.TV.* properties."""
    set_prop('SkinInfo.Slideshow.TV.Title', item.get('title', ''))
    set_prop('SkinInfo.Slideshow.TV.FanArt', item.get('fanart', ''))
    set_prop('SkinInfo.Slideshow.TV.Plot', item.get('plot', ''))
    set_prop('SkinInfo.Slideshow.TV.Year', str(item.get('year', '')) if item.get('year') else '')




def set_video_slideshow_properties(item: Dict[str, Any]) -> None:
    """Set SkinInfo.Slideshow.Video.* properties."""
    set_prop('SkinInfo.Slideshow.Video.Title', item.get('title', ''))
    set_prop('SkinInfo.Slideshow.Video.FanArt', item.get('fanart', ''))
    set_prop('SkinInfo.Slideshow.Video.Plot', item.get('plot', ''))
    set_prop('SkinInfo.Slideshow.Video.Year', str(item.get('year', '')) if item.get('year') else '')


def set_music_slideshow_properties(item: Dict[str, Any]) -> None:
    """Set SkinInfo.Slideshow.Music.* properties."""
    set_prop('SkinInfo.Slideshow.Music.Artist', item.get('artist', ''))
    set_prop('SkinInfo.Slideshow.Music.FanArt', item.get('fanart', ''))
    set_prop('SkinInfo.Slideshow.Music.Description', item.get('description', ''))


def set_global_slideshow_properties(item: Dict[str, Any]) -> None:
    """Set SkinInfo.Slideshow.Global.* properties."""
    set_prop('SkinInfo.Slideshow.Global.Title', item.get('title', ''))
    set_prop('SkinInfo.Slideshow.Global.FanArt', item.get('fanart', ''))
    set_prop('SkinInfo.Slideshow.Global.Description', item.get('description', ''))


def clear_slideshow_properties() -> None:
    """Clear all slideshow properties."""
    categories = {
        'Movie': ['Title', 'FanArt', 'Plot', 'Year'],
        'TV': ['Title', 'FanArt', 'Plot', 'Year'],
        'Video': ['Title', 'FanArt', 'Plot', 'Year'],
        'Music': ['Artist', 'FanArt', 'Description'],
        'Global': ['Title', 'FanArt', 'Description']
    }

    for category, props in categories.items():
        for prop in props:
            clear_prop(f'SkinInfo.Slideshow.{category}.{prop}')


def update_all_slideshow_properties() -> None:
    """
    Main update function - queries and sets all slideshow properties.
    Uses single optimized query for maximum performance.
    Called by service on configured interval.
    """
    all_rows = db_slideshow.get_all_pool_items(5000)

    random.shuffle(all_rows)

    movies = [r for r in all_rows if r['media_type'] == 'movie']
    tvshows = [r for r in all_rows if r['media_type'] == 'tvshow']
    artists = [r for r in all_rows if r['media_type'] == 'artist']
    videos = movies + tvshows
    random.shuffle(videos)

    def pick_item(items: List) -> Optional[Dict[str, Any]]:
        """Pick random item from list and cache its fanart."""
        if not items:
            return None

        item = random.choice(items)
        if item['fanart']:
            if _cache_image_url(item['fanart']):
                with _cache_lock:
                    if _cached_texture_urls is not None:
                        decoded = decode_image_url(item['fanart'])
                        _cached_texture_urls.add(decoded)
                return item

        return None

    movie = pick_item(movies)
    if movie:
        set_movie_slideshow_properties({
            'title': movie['title'],
            'fanart': movie['fanart'],
            'plot': movie['description'],
            'year': movie['year']
        })

    tvshow = pick_item(tvshows)
    if tvshow:
        set_tv_slideshow_properties({
            'title': tvshow['title'],
            'fanart': tvshow['fanart'],
            'plot': tvshow['description'],
            'year': tvshow['year']
        })

    video = random.choice(videos) if videos else None
    if video:
        set_video_slideshow_properties({
            'title': video['title'],
            'fanart': video['fanart'],
            'plot': video['description'],
            'year': video['year'] if 'year' in video.keys() else None
        })

    artist = pick_item(artists)
    if artist:
        set_music_slideshow_properties({
            'artist': artist['title'],
            'fanart': artist['fanart'],
            'description': artist['description']
        })

    global_item = pick_item(all_rows)
    if global_item:
        set_global_slideshow_properties({
            'title': global_item['title'],
            'fanart': global_item['fanart'],
            'description': global_item['description']
        })


def is_pool_populated() -> bool:
    """Check if slideshow pool has any items."""
    return db_slideshow.is_pool_populated()


class SlideshowMonitor(xbmc.Monitor):
    """Monitor for library changes to sync slideshow pool."""

    def onScanFinished(self, library: str) -> None:
        """Sync slideshow pool when library scan completes."""
        try:
            log("Service", f"Slideshow: Library scan finished ({library}), syncing pool...", xbmc.LOGDEBUG)
            sync_slideshow_pool()
        except Exception as e:
            log("Service", f"Slideshow: Error syncing pool after scan: {e}", xbmc.LOGERROR)

    def onCleanFinished(self, library: str) -> None:
        """Sync slideshow pool when library clean completes."""
        try:
            log("Service", f"Slideshow: Library clean finished ({library}), syncing pool...", xbmc.LOGDEBUG)
            sync_slideshow_pool()
        except Exception as e:
            log("Service", f"Slideshow: Error syncing pool after clean: {e}", xbmc.LOGERROR)
