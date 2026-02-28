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
    - TV Shows with next_incomplete_episode: cache until that episode's air_date
    - TV Shows with Ended/Canceled status: 168 hours (7 days)
    - TV Shows with active status but no schedule: 72 hours (3 days)
    - Movies by age:
      - <90 days: 24 hours (ratings/info actively updating)
      - 90 days - 6 months: 72 hours (3 days)
      - 6 months - 1 year: 120 hours (5 days)
      - >1 year: 168 hours (7 days, stable content)
    - Unknown: 24 hours (assume active)
    - Adds ±10% random jitter to prevent thundering herd

    Args:
        release_date: Release date in YYYY-MM-DD format
                     - Movies: used to determine age tier
                     - TV Shows: ignored if schedule hint provided
        hints: Optional dictionary of metadata hints for TTL calculation.
               Supported keys:
               - "status": TMDb status string (e.g., "Ended", "Canceled", "Returning Series")
               - "next_incomplete_episode": Air date of first episode missing data (YYYY-MM-DD)
               - Additional keys can be added without changing function signature

    Returns:
        TTL in hours with ±10% jitter
    """
    import random

    hints = hints or {}

    if hints.get("is_library_item") is False:
        return 24

    status = hints.get("status", "").lower() if hints.get("status") else ""
    next_incomplete = hints.get("next_incomplete_episode")

    if next_incomplete:
        try:
            air_date = datetime.fromisoformat(next_incomplete)
            hours_until = (air_date - datetime.now()).total_seconds() / 3600
            if hours_until > 0:
                base_ttl = max(1, int(hours_until))
            else:
                base_ttl = 1
        except (ValueError, AttributeError):
            base_ttl = 24
    elif status:
        if status in ("ended", "canceled"):
            base_ttl = 168  # 7 days - show is done
        else:
            base_ttl = 72  # 3 days - airing but no schedule data
    elif release_date:
        try:
            release = datetime.fromisoformat(release_date)
            days_old = (datetime.now() - release).days
            if days_old < 90:
                base_ttl = 24  # Very new - ratings still settling
            elif days_old < 180:
                base_ttl = 72  # 3 days - moderately stable
            elif days_old < 365:
                base_ttl = 120  # 5 days - mostly stable
            else:
                base_ttl = 168  # 7 days - established content
        except (ValueError, AttributeError):
            base_ttl = 24
    else:
        base_ttl = 24

    jitter = random.uniform(0.9, 1.1)
    return int(base_ttl * jitter)


def get_fanarttv_cache_ttl_hours() -> int:
    """
    Get cache TTL for Fanart.tv based on user's API key tier.

    Returns:
        48 hours if personal key configured (2-day tier)
        168 hours if no key (7-day project tier)
    """
    from lib.kodi.settings import KodiSettings
    if KodiSettings.fanarttv_api_key():
        return 48
    return 168


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


def cache_metadata(media_type: str, tmdb_id: str, data: dict, release_date: Optional[str], hints: Optional[Dict[str, Any]] = None, ttl_hours: Optional[int] = None) -> None:
    """
    Cache extended metadata with dynamic TTL and compression.

    Args:
        media_type: 'movie', 'tvshow', 'episode', 'artist', 'album'
        tmdb_id: TMDb ID or MusicBrainz ID as string
        data: Complete API response dict
        release_date: YYYY-MM-DD from Kodi or API response
        hints: Optional metadata hints for TTL calculation (see get_cache_ttl_hours)
        ttl_hours: Manual TTL override (if None, calculated from release_date/hints)
    """
    if ttl_hours is None:
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
            cursor.execute('DELETE FROM online_properties_cache WHERE item_key = ?', (item_key,))
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to decompress online properties: {e}", xbmc.LOGERROR)
            return None


def get_mb_id_mapping(old_id: str) -> Optional[str]:
    """Get canonical ID for an old/merged MusicBrainz release group ID."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('SELECT canonical_id FROM mb_id_mappings WHERE old_id = ?', (old_id,))
        row = cursor.fetchone()
        return row['canonical_id'] if row else None


def get_mb_id_mappings_by_canonical(canonical_id: str) -> List[str]:
    """Get all known old IDs that redirect to this canonical ID."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('SELECT old_id FROM mb_id_mappings WHERE canonical_id = ?', (canonical_id,))
        return [row['old_id'] for row in cursor.fetchall()]


def save_mb_id_mapping(old_id: str, canonical_id: str) -> None:
    """Store an old->canonical MusicBrainz ID mapping. Permanent — merges never reverse."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute(
            'INSERT OR REPLACE INTO mb_id_mappings (old_id, canonical_id) VALUES (?, ?)',
            (old_id, canonical_id)
        )


def invalidate_online_properties(media_type: str, imdb_id: str = '', tmdb_id: str = '') -> int:
    """Delete cached online properties for a specific item."""
    keys = []
    if tmdb_id:
        keys.append("{}:tmdb:{}".format(media_type, tmdb_id))
    if imdb_id:
        keys.append("{}:imdb:{}".format(media_type, imdb_id))
    if not keys:
        return 0
    total = 0
    with get_db(DB_PATH) as (conn, cursor):
        for key in keys:
            cursor.execute('DELETE FROM online_properties_cache WHERE item_key = ?', (key,))
            total += cursor.rowcount
    if total > 0:
        log("Cache", "Invalidated {} online cache entries for {}".format(total, media_type))
    return total


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
