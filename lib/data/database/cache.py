"""API response caching for TMDB and fanart.tv.

Manages skininfo_v1.db cache tables with dynamic TTL based on media age.
"""
from __future__ import annotations

import json
import zlib
import xbmc
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Tuple

from lib.data.database._infrastructure import get_db, DB_PATH, vacuum_database
from lib.kodi.client import log


def _compress_data(data: Any) -> bytes:
    """Compress JSON data using zlib."""
    json_str = json.dumps(data, separators=(',', ':'))
    return zlib.compress(json_str.encode('utf-8'), level=6)


def _decompress_data(data: bytes) -> Any:
    """Decompress zlib-compressed JSON data."""
    json_str = zlib.decompress(data).decode('utf-8')
    return json.loads(json_str)


def get_cache_ttl_hours(release_date: Optional[str], hints: Optional[Dict[str, Any]] = None) -> int:
    """
    Dynamic cache TTL based on content status and metadata hints.

    Strategy:
    - TV Shows with Ended/Canceled status: 168 hours (7 days)
    - TV Shows with active status: 24 hours (daily updates for new episodes)
    - Movies older than 90 days: 168 hours (7 days, stable content)
    - Movies newer than 90 days: 24 hours (ratings/info may still update)
    - Unknown: 24 hours (assume active)
    - Adds ±10% random jitter to prevent thundering herd

    Args:
        release_date: Release date in YYYY-MM-DD format
                     - Movies: used to determine if new vs established
                     - TV Shows: ignored if status hint provided
        hints: Optional dictionary of metadata hints for TTL calculation.
               Supported keys:
               - "status": TMDb status string (e.g., "Ended", "Canceled", "Returning Series")
               - "next_air_date": Next episode air date (YYYY-MM-DD) - for future use
               - Additional keys can be added without changing function signature

    Returns:
        TTL in hours with ±10% jitter
    """
    import random

    hints = hints or {}
    status = hints.get("status", "").lower() if hints.get("status") else ""

    # If we have status info (TV shows), use that
    if status:
        if status in ("ended", "canceled"):
            base_ttl = 168  # 7 days - show is done
        else:
            base_ttl = 24  # Active show - check daily
    # No status (movies) - use release date
    elif release_date:
        try:
            release = datetime.fromisoformat(release_date)
            days_old = (datetime.now() - release).days
            # New movies may still get rating updates; old movies are stable
            base_ttl = 24 if days_old < 90 else 72
        except (ValueError, AttributeError):
            base_ttl = 24
    else:
        # Unknown - check daily
        base_ttl = 24

    jitter = random.uniform(0.9, 1.1)
    return int(base_ttl * jitter)


def get_cached_artwork(media_type: str, media_id: str, source: str, art_type: str) -> Optional[list]:
    """
    Get cached artwork if available and not expired.

    Args:
        media_type: "movie", "tvshow", etc.
        media_id: TMDB ID, TVDB ID, etc. (as string)
        source: "tmdb" or "fanarttv"
        art_type: "poster", "fanart", "clearlogo", etc.

    Returns:
        List of artwork dicts or None if not cached/expired
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT data, expires_at FROM artwork_cache
            WHERE media_type = ? AND media_id = ? AND source = ? AND art_type = ?
        ''', (media_type, media_id, source, art_type))

        row = cursor.fetchone()

        if not row:
            return None

        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at:
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to parse cached data: {str(e)}", xbmc.LOGERROR)
            return None


def get_cached_artwork_batch(
    media_type: str,
    media_ids: Dict[str, str],
    art_types: List[str]
) -> Dict[Tuple[str, str], list]:
    if not media_ids or not art_types:
        return {}

    conditions = []
    params = []

    for source, media_id in media_ids.items():
        if media_id:
            conditions.append("(source = ? AND media_id = ?)")
            params.append(source)
            params.append(media_id)

    if not conditions:
        return {}

    art_type_placeholders = ','.join('?' * len(art_types))

    query = f'''
        SELECT source, art_type, data, expires_at
        FROM artwork_cache
        WHERE media_type = ?
          AND ({' OR '.join(conditions)})
          AND art_type IN ({art_type_placeholders})
    '''

    query_params = [media_type] + params + art_types

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute(query, query_params)
        rows = cursor.fetchall()

        results: Dict[Tuple[str, str], list] = {}
        now = datetime.now()

        for row in rows:
            expires_at = datetime.fromisoformat(row['expires_at'])

            if now > expires_at:
                continue

            try:
                key = (row['source'], row['art_type'])
                results[key] = _decompress_data(row['data'])
            except Exception as e:
                log("Cache", f"Failed to parse cached data: {str(e)}", xbmc.LOGERROR)
                continue

        return results


def cache_artwork(media_type: str, media_id: str, source: str, art_type: str, data: list, release_date: Optional[str] = None, ttl_hours: Optional[int] = None) -> None:
    """
    Cache artwork data.

    Args:
        media_type: "movie", "tvshow", etc.
        media_id: TMDB ID, TVDB ID, etc. (as string)
        source: "tmdb" or "fanarttv"
        art_type: "poster", "fanart", "clearlogo", etc.
        data: List of artwork dicts to cache
        release_date: YYYY-MM-DD release date for TTL calculation
        ttl_hours: Manual TTL override (if None, calculated from release_date)
    """
    if ttl_hours is None:
        ttl_hours = get_cache_ttl_hours(release_date)

    with get_db(DB_PATH) as (conn, cursor):
        expires_at = datetime.now() + timedelta(hours=ttl_hours)

        cursor.execute('''
            INSERT OR REPLACE INTO artwork_cache (media_type, media_id, source, art_type, data, release_date, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (media_type, media_id, source, art_type, _compress_data(data), release_date, expires_at.isoformat()))


def get_cached_metadata(media_type: str, tmdb_id: str) -> Optional[dict]:
    """
    Get cached extended metadata if not expired.

    Args:
        media_type: 'movie', 'tvshow', 'episode'
        tmdb_id: TMDb ID as string

    Returns:
        Cached metadata dict or None if not cached/expired
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT data, expires_at FROM metadata_cache
            WHERE media_type = ? AND tmdb_id = ?
        ''', (media_type, tmdb_id))

        row = cursor.fetchone()
        if not row:
            return None

        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at:
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to decompress metadata: {e}", xbmc.LOGERROR)
            return None


def cache_metadata(media_type: str, tmdb_id: str, data: dict, release_date: Optional[str], hints: Optional[Dict[str, Any]] = None) -> None:
    """
    Cache extended metadata with dynamic TTL and compression.

    Args:
        media_type: 'movie', 'tvshow', 'episode'
        tmdb_id: TMDb ID as string
        data: Complete TMDb response dict
        release_date: YYYY-MM-DD from Kodi or TMDb response
        hints: Optional metadata hints for TTL calculation (see get_cache_ttl_hours)
    """
    ttl_hours = get_cache_ttl_hours(release_date, hints)
    expires_at = datetime.now() + timedelta(hours=ttl_hours)
    compressed = _compress_data(data)

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT OR REPLACE INTO metadata_cache
            (media_type, tmdb_id, data, release_date, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (media_type, tmdb_id, compressed, release_date, expires_at.isoformat()))


def clear_expired_cache() -> int:
    """
    Remove expired cache entries.

    Returns:
        Number of entries removed
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            DELETE FROM artwork_cache WHERE expires_at < ?
        ''', (datetime.now().isoformat(),))
        artwork_deleted = cursor.rowcount

        cursor.execute('''
            DELETE FROM metadata_cache WHERE expires_at < ?
        ''', (datetime.now().isoformat(),))
        metadata_deleted = cursor.rowcount

        deleted = artwork_deleted + metadata_deleted

    if deleted > 0:
        log("Database", f"Cleared {deleted} expired cache entries")
        vacuum_database()

    return deleted


def cache_person_data(person_id: int, data: dict, ttl_days: int = 30) -> None:
    """
    Cache complete TMDB person data.

    Args:
        person_id: TMDB person ID
        data: Complete person data from TMDB API
        ttl_days: Time to live in days (default: 30)
    """
    import time

    now = int(time.time())
    expires = now + (ttl_days * 86400)

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT OR REPLACE INTO person_cache (person_id, data, cached_at, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (person_id, _compress_data(data), now, expires))


def get_cached_person_data(person_id: int) -> Optional[dict]:
    """
    Get cached person data if not expired.

    Args:
        person_id: TMDB person ID

    Returns:
        Cached person data or None if not cached/expired
    """
    import time

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT data FROM person_cache
            WHERE person_id = ? AND expires_at > ?
        ''', (person_id, int(time.time())))

        row = cursor.fetchone()

        if not row:
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to parse cached person data: {str(e)}", xbmc.LOGERROR)
            return None


def get_cached_online_properties(item_key: str) -> Optional[Dict[str, str]]:
    """
    Get cached online properties if not expired.

    Args:
        item_key: Unique key for the item (e.g., "movie:123:tt1234567:456")

    Returns:
        Cached properties dict or None if not cached/expired
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT data, expires_at FROM online_properties_cache
            WHERE item_key = ?
        ''', (item_key,))

        row = cursor.fetchone()
        if not row:
            return None

        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at:
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to decompress online properties: {e}", xbmc.LOGERROR)
            return None


def cache_online_properties(item_key: str, props: Dict[str, str], ttl_hours: int = 1) -> None:
    """
    Cache online properties.

    Args:
        item_key: Unique key for the item (e.g., "movie:123:tt1234567:456")
        props: Dictionary of property key -> value pairs
        ttl_hours: Time to live in hours (default: 1 hour)
    """
    expires_at = datetime.now() + timedelta(hours=ttl_hours)
    compressed = _compress_data(props)

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT OR REPLACE INTO online_properties_cache
            (item_key, data, expires_at)
            VALUES (?, ?, ?)
        ''', (item_key, compressed, expires_at.isoformat()))
