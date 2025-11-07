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

from lib.data.database._infrastructure import get_db, DB_PATH
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

    log("Service",f"Slideshow: Loaded {len(cached_urls)} cached texture URLs")
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

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT fanart
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT ?
        ''', (count * 3,))

        rows = cursor.fetchall()

        for row in rows:
            fanart = row['fanart']
            if fanart and fanart.strip():
                decoded = decode_image_url(fanart)
                if decoded not in cached_urls:
                    uncached.append(fanart)
                    if len(uncached) >= count:
                        break

    return uncached


def _is_url_cached(url: str) -> bool:
    """
    Check if a URL exists in Kodi's texture cache.

    Args:
        url: Image URL (wrapped or decoded)

    Returns:
        True if URL is in texture cache
    """
    if not url:
        return False

    decoded = decode_image_url(url)
    cached_urls = _get_cached_texture_urls()
    return decoded in cached_urls


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
        log("Service",f"Slideshow: Failed to cache URL {url}: {e}", xbmc.LOGWARNING)
        return False


def _insert_pool_records(cursor, media_type: str, items: list, id_key: str, title_key: str,
                         fanart_key: str, description_key: str, current_time: int) -> None:
    """
    Helper to insert records into slideshow_pool.

    Args:
        cursor: Database cursor
        media_type: Type of media ('movie', 'tvshow', 'artist')
        items: List of items from Kodi API
        id_key: Key for database ID in item dict
        title_key: Key for title in item dict
        fanart_key: Key for fanart URL in item dict
        description_key: Key for description in item dict
        current_time: Current timestamp
    """
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

    if records:
        cursor.executemany('''
            INSERT OR REPLACE INTO slideshow_pool
            (kodi_dbid, media_type, title, fanart, description, year, season, episode, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', records)


def populate_slideshow_pool() -> None:
    """
    Populate slideshow_pool table from Kodi library.
    Queries JSON-RPC for all movies, TV shows, and artists with fanart.
    """
    current_time = int(time.time())

    movies = _get_movies_with_fanart()
    tvshows = _get_tvshows_with_fanart()
    artists = _get_artists_with_fanart()

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('DELETE FROM slideshow_pool')

        _insert_pool_records(cursor, 'movie', movies, 'movieid', 'title', 'fanart', 'plot', current_time)
        _insert_pool_records(cursor, 'tvshow', tvshows, 'tvshowid', 'title', 'fanart', 'plot', current_time)
        _insert_pool_records(cursor, 'artist', artists, 'artistid', 'artist', 'fanart', 'description', current_time)

        conn.commit()

    log("Service",f"Slideshow: Pool populated with {len(movies)} movies, {len(tvshows)} TV shows, {len(artists)} artists")


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
    log("Service",f"Slideshow: GetArtists returned {len(all_artists)} total artists")

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

    log("Service",f"Slideshow: Found {len(artists_with_fanart)} artists with fanart")
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

    if len(media_types) == 1:
        where_clause = 'WHERE media_type = ?'
        params = (media_types[0],)
        media_type_label = media_types[0]
    else:
        placeholders = ','.join('?' * len(media_types))
        where_clause = f'WHERE media_type IN ({placeholders})'
        params = tuple(media_types)
        media_type_label = '/'.join(media_types)

    select_clause = ', '.join(select_fields)

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute(f'''
            SELECT {select_clause}
            FROM slideshow_pool
            {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        ''', params + (attempt_count,))

        rows = cursor.fetchall()

        for row in rows:
            fanart = row['fanart']
            if fanart:
                decoded = decode_image_url(fanart)
                if decoded in cached_urls:
                    return {result_mapping[k]: row[k] for k in result_mapping}

        log("Service",f"Slideshow: No cached {media_type_label} fanart found in sample, caching random item")

        cursor.execute(f'''
            SELECT {select_clause}
            FROM slideshow_pool
            {where_clause}
            ORDER BY RANDOM()
            LIMIT 1
        ''', params)

        row = cursor.fetchone()
        if row and row['fanart']:
            if _cache_image_url(row['fanart']):
                with _cache_lock:
                    if _cached_texture_urls is not None:
                        decoded = decode_image_url(row['fanart'])
                        _cached_texture_urls.add(decoded)
                log("Service",f"Slideshow: Cached {media_type_label} fanart: {row['fanart']}")
                return {result_mapping[k]: row[k] for k in result_mapping}
            else:
                log("Service",f"Slideshow: Failed to cache {media_type_label} fanart", xbmc.LOGWARNING)

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
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT media_type, title, fanart, description, year
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT 5000
        ''')
        all_rows = cursor.fetchall()

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
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('SELECT COUNT(*) as count FROM slideshow_pool')
        row = cursor.fetchone()
        return row['count'] > 0 if row else False


class SlideshowMonitor(xbmc.Monitor):
    """Monitor for library changes to sync slideshow pool."""

    def onScanFinished(self, library: str) -> None:
        """Sync slideshow pool when library scan completes."""
        try:
            log("Service",f"Slideshow: Library scan finished ({library}), syncing pool...", xbmc.LOGDEBUG)
            sync_slideshow_pool()
        except Exception as e:
            log("Service",f"Slideshow: Error syncing pool after scan: {str(e)}", xbmc.LOGERROR)

    def onCleanFinished(self, library: str) -> None:
        """Sync slideshow pool when library clean completes."""
        try:
            log("Service",f"Slideshow: Library clean finished ({library}), syncing pool...", xbmc.LOGDEBUG)
            sync_slideshow_pool()
        except Exception as e:
            log("Service",f"Slideshow: Error syncing pool after clean: {str(e)}", xbmc.LOGERROR)
