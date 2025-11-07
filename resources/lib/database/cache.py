"""API response caching for TMDB and fanart.tv.

Manages artwork_cache.db with dynamic TTL based on media age.
"""
from __future__ import annotations

import json
import xbmc
from datetime import datetime, timedelta
from typing import Optional

from resources.lib.database._infrastructure import get_db, DB_PATH, vacuum_database
from resources.lib.kodi import log_database

# Cache TTL (Time To Live) - Dynamic based on media age
DEFAULT_CACHE_TTL_HOURS = 168  # 7 days

# Age thresholds and corresponding cache TTLs
AGE_THRESHOLD_VERY_NEW_DAYS = 30
AGE_THRESHOLD_NEW_DAYS = 180
AGE_THRESHOLD_RECENT_DAYS = 730
AGE_THRESHOLD_OLD_YEARS = 10

CACHE_TTL_VERY_NEW_HOURS = 72    # 3 days
CACHE_TTL_NEW_HOURS = 168        # 7 days
CACHE_TTL_RECENT_HOURS = 720     # 30 days
CACHE_TTL_OLD_HOURS = 2160       # 90 days
CACHE_TTL_CLASSIC_HOURS = 4320   # 180 days


def get_cache_ttl_hours(year: int) -> int:
    """
    Calculate cache TTL based on media age.
    Newer content gets shorter cache (artwork changes more often)
    Older content gets longer cache (artwork stable)

    Args:
        year: Release year of the media

    Returns:
        Cache TTL in hours
    """
    if not year or year < 1900:
        return DEFAULT_CACHE_TTL_HOURS

    current_year = datetime.now().year
    age_years = current_year - year
    age_days = age_years * 365

    if age_days < AGE_THRESHOLD_VERY_NEW_DAYS:
        return CACHE_TTL_VERY_NEW_HOURS
    elif age_days < AGE_THRESHOLD_NEW_DAYS:
        return CACHE_TTL_NEW_HOURS
    elif age_days < AGE_THRESHOLD_RECENT_DAYS:
        return CACHE_TTL_RECENT_HOURS
    elif age_years < AGE_THRESHOLD_OLD_YEARS:
        return CACHE_TTL_OLD_HOURS
    else:
        return CACHE_TTL_CLASSIC_HOURS


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
            data = json.loads(row['data'])
            return data
        except Exception as e:
            xbmc.log(f"SkinInfo Cache: Failed to parse cached data: {str(e)}", xbmc.LOGERROR)
            return None


def cache_artwork(media_type: str, media_id: str, source: str, art_type: str, data: list, ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> None:
    """
    Cache artwork data.

    Args:
        media_type: "movie", "tvshow", etc.
        media_id: TMDB ID, TVDB ID, etc. (as string)
        source: "tmdb" or "fanarttv"
        art_type: "poster", "fanart", "clearlogo", etc.
        data: List of artwork dicts to cache
        ttl_hours: How many hours to cache (default 168 = 7 days)
    """
    with get_db(DB_PATH) as (conn, cursor):
        expires_at = datetime.now() + timedelta(hours=ttl_hours)

        cursor.execute('''
            INSERT OR REPLACE INTO artwork_cache (media_type, media_id, source, art_type, data, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (media_type, media_id, source, art_type, json.dumps(data), expires_at.isoformat()))


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

        deleted = cursor.rowcount

    if deleted > 0:
        log_database(f"Cleared {deleted} expired cache entries")
        vacuum_database()

    return deleted
