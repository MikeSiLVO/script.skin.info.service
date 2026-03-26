"""API response caching for TMDB and fanart.tv.

Manages cache tables with dynamic TTL based on media age.
"""
from __future__ import annotations

import json
import random
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


def _tv_show_ttl(hints: Dict[str, Any]) -> int:
    """Calculate TTL for TV shows based on schedule and status hints.

    Airing — Complete (next ep has name + overview + air_date):
        < 7 days out:   random 24-48h
        7-30 days out:  random 3-6 days
        30+ days out:   random 14-30 days

    Airing — Incomplete (next ep missing name/overview):
        < 7 days out:   24h
        7-30 days out:  random 2-4 days
        30-90 days out: random 3-6 days
        > 90 days out:  random 7-14 days

    Air date passed:        12h
    Active, no schedule:    random 3-7 days

    Ended — Complete (aired_data_complete):
        Any age:        random 14-30 days

    Ended — Incomplete:
        < 14 days:      random 24-72h
        14-30 days:     random 3-6 days
        30+ days:       random 7-14 days
    """
    aired_data_complete = hints.get("aired_data_complete") == "true"
    status = hints.get("status", "").lower() if hints.get("status") else ""
    next_air = hints.get("next_episode_air_date")
    next_air_incomplete = hints.get("next_episode_air_date_incomplete")
    last_air = hints.get("last_air_date")

    air_date_str = next_air or next_air_incomplete
    if air_date_str:
        try:
            days_until = (datetime.fromisoformat(air_date_str) - datetime.now()).total_seconds() / 86400
        except (ValueError, AttributeError):
            days_until = None

        if days_until is not None:
            if days_until <= 0:
                return 12
            if next_air:
                if days_until <= 7:
                    return random.randint(24, 48)
                if days_until <= 30:
                    return random.randint(3, 6) * 24
                return random.randint(14, 30) * 24
            if days_until <= 7:
                return 24
            if days_until <= 30:
                return random.randint(2, 4) * 24
            if days_until <= 90:
                return random.randint(3, 6) * 24
            return random.randint(7, 14) * 24

    if status in ("ended", "canceled"):
        if aired_data_complete:
            return random.randint(14, 30) * 24

        days_since_last = None
        if last_air:
            try:
                days_since_last = (datetime.now() - datetime.fromisoformat(last_air)).days
            except (ValueError, AttributeError):
                pass

        if days_since_last is not None and days_since_last < 14:
            return random.randint(24, 72)
        if days_since_last is not None and days_since_last < 30:
            return random.randint(3, 6) * 24
        return random.randint(7, 14) * 24

    return random.randint(3, 7) * 24


def get_cache_ttl_hours(release_date: Optional[str], hints: Optional[Dict[str, Any]] = None) -> int:
    """
    Dynamic cache TTL based on content status and metadata hints.

    Strategy:
    - Movies by age (random range, no jitter):
      - <90 days: random 24-48h
      - 90 days - 1 year: random 3-6 days
      - 1-2 years: random 7-14 days
      - >2 years: random 14-30 days
    - Unknown: random 24-48h

    Args:
        release_date: Release date in YYYY-MM-DD format
                     - Movies: used to determine age tier
                     - TV Shows: ignored (schedule hints used instead)
        hints: Optional dictionary of metadata hints for TTL calculation.
               Supported keys:
               - "status": TMDb status string (e.g., "Ended", "Canceled", "Returning Series")
               - "next_episode_air_date": Air date of next ep with complete data (YYYY-MM-DD)
               - "next_episode_air_date_incomplete": Air date of next ep missing name/overview
               - "last_air_date": Air date of last episode (YYYY-MM-DD)
               - "aired_data_complete": "true" if TV show core fields are filled (overview, cast, IDs, content ratings, last ep)
               - "is_library_item": False for non-library items (fixed 24h TTL)

    Returns:
        TTL in hours
    """

    hints = hints or {}

    if hints.get("is_library_item") is False:
        return 24

    status = hints.get("status", "").lower() if hints.get("status") else ""
    has_tv_hints = (
        hints.get("next_episode_air_date")
        or hints.get("next_episode_air_date_incomplete")
        or status in ("ended", "canceled", "returning series", "in production", "planned", "pilot")
    )

    if has_tv_hints:
        return _tv_show_ttl(hints)

    if release_date:
        try:
            release = datetime.fromisoformat(release_date)
            days_old = (datetime.now() - release).days
            if days_old < 90:
                return random.randint(24, 48)
            if days_old < 365:
                return random.randint(3, 6) * 24
            if days_old < 730:
                return random.randint(7, 14) * 24
            return random.randint(14, 30) * 24
        except (ValueError, AttributeError):
            return random.randint(24, 48)
    return random.randint(24, 48)


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
    with get_db(DB_PATH) as cursor:
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

    with get_db(DB_PATH) as cursor:
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

    with get_db(DB_PATH) as cursor:
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
    with get_db(DB_PATH) as cursor:
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

    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            INSERT OR REPLACE INTO metadata_cache
            (media_type, tmdb_id, data, release_date, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (media_type, tmdb_id, compressed, release_date, expires_at.isoformat()))

    if media_type in ('movie', 'tvshow') and isinstance(data.get('external_ids'), dict):
        from lib.data.database.mapping import save_id_mapping
        ext = data['external_ids']
        save_id_mapping(
            tmdb_id, media_type,
            imdb_id=ext.get('imdb_id') or None,
            tvdb_id=str(ext['tvdb_id']) if ext.get('tvdb_id') else None,
        )


def expire_metadata(media_type: str, tmdb_id: str, ttl_hours: int = 12) -> None:
    """Shorten metadata cache TTL so the next fetch gets fresh data.

    Only shortens — if the entry already expires sooner, it's left alone.
    """
    new_expires = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            UPDATE metadata_cache
            SET expires_at = MIN(expires_at, ?)
            WHERE media_type = ? AND tmdb_id = ?
        ''', (new_expires, media_type, tmdb_id))


def clear_expired_cache() -> int:
    """
    Remove expired cache entries.

    Returns:
        Number of entries removed
    """
    now = datetime.now()
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'DELETE FROM artwork_cache WHERE expires_at < ?',
            (now.isoformat(),)
        )
        artwork_deleted = cursor.rowcount

        cursor.execute(
            'DELETE FROM metadata_cache WHERE expires_at < ?',
            (now.isoformat(),)
        )
        metadata_deleted = cursor.rowcount

        # Stale online props served until refreshed, but purge very old entries
        cutoff = (now - timedelta(days=180)).isoformat()
        cursor.execute(
            'DELETE FROM online_properties_cache WHERE expires_at < ?',
            (cutoff,)
        )
        online_deleted = cursor.rowcount

        deleted = artwork_deleted + metadata_deleted + online_deleted

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

    with get_db(DB_PATH) as cursor:
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

    with get_db(DB_PATH) as cursor:
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


def get_cached_online_keys() -> set:
    """Get all non-expired item_keys from online_properties_cache."""
    with get_db(DB_PATH) as cursor:
        now = datetime.now().isoformat()
        cursor.execute(
            'SELECT item_key FROM online_properties_cache WHERE expires_at > ?',
            (now,)
        )
        return {row['item_key'] for row in cursor.fetchall()}


def get_cached_online_properties(item_key: str) -> Optional[Dict[str, str]]:
    """Get cached online properties, serving stale data until refreshed.

    Returns:
        Cached properties dict or None if not cached
    """
    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            SELECT data FROM online_properties_cache
            WHERE item_key = ?
        ''', (item_key,))

        row = cursor.fetchone()
        if not row:
            return None

        try:
            return _decompress_data(row['data'])
        except Exception as e:
            log("Cache", f"Failed to decompress online properties: {e}", xbmc.LOGERROR)
            return None


def get_mb_id_mapping(old_id: str) -> Optional[str]:
    """Get canonical ID for an old/merged MusicBrainz release group ID."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT canonical_id FROM mb_id_mappings WHERE old_id = ?', (old_id,))
        row = cursor.fetchone()
        return row['canonical_id'] if row else None


def get_mb_id_mappings_by_canonical(canonical_id: str) -> List[str]:
    """Get all known old IDs that redirect to this canonical ID."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT old_id FROM mb_id_mappings WHERE canonical_id = ?', (canonical_id,))
        return [row['old_id'] for row in cursor.fetchall()]


def save_mb_id_mapping(old_id: str, canonical_id: str) -> None:
    """Store an old->canonical MusicBrainz ID mapping. Permanent — merges never reverse."""
    with get_db(DB_PATH) as cursor:
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
    with get_db(DB_PATH) as cursor:
        for key in keys:
            cursor.execute('DELETE FROM online_properties_cache WHERE item_key = ?', (key,))
            total += cursor.rowcount
    if total > 0:
        log("Cache", "Invalidated {} online cache entries for {}".format(total, media_type))
    return total


def invalidate_online_properties_by_keys(keys: List[str]) -> int:
    """Delete cached online properties by exact cache keys."""
    if not keys:
        return 0
    total = 0
    with get_db(DB_PATH) as cursor:
        for key in keys:
            cursor.execute('DELETE FROM online_properties_cache WHERE item_key = ?', (key,))
            total += cursor.rowcount
    if total > 0:
        log("Cache", f"Invalidated {total} stale online cache entries")
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

    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            INSERT OR REPLACE INTO online_properties_cache
            (item_key, data, expires_at)
            VALUES (?, ?, ?)
        ''', (item_key, compressed, expires_at.isoformat()))
