"""TV schedule database operations for airing show tracking."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from lib.data.database._infrastructure import DB_PATH, get_db


def upsert_schedule(
    tmdb_id: str,
    tvshowid: int,
    title: str,
    status: str,
    next_ep: Optional[dict] = None,
    last_ep: Optional[dict] = None,
) -> None:
    """Insert or update a TV show's schedule entry from TMDB data."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            INSERT OR REPLACE INTO tv_schedule (
                tmdb_id, tvshowid, title, status,
                next_episode_air_date, next_episode_title,
                next_episode_season, next_episode_number,
                last_episode_air_date, last_episode_title,
                last_episode_season, last_episode_number,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tmdb_id, tvshowid, title, status,
            (next_ep.get("air_date") or "") if next_ep else "",
            (next_ep.get("name") or "") if next_ep else "",
            next_ep.get("season_number") if next_ep else None,
            next_ep.get("episode_number") if next_ep else None,
            (last_ep.get("air_date") or "") if last_ep else "",
            (last_ep.get("name") or "") if last_ep else "",
            last_ep.get("season_number") if last_ep else None,
            last_ep.get("episode_number") if last_ep else None,
            datetime.now().isoformat(),
        ))


def get_schedule_by_date_range(
    start_date: str,
    end_date: str,
) -> List[Dict]:
    """Get shows with next episodes airing in a date range.

    Args:
        start_date: YYYY-MM-DD start (inclusive)
        end_date: YYYY-MM-DD end (inclusive)
    """
    with get_db(DB_PATH) as cursor:
        cursor.execute('''
            SELECT * FROM tv_schedule
            WHERE next_episode_air_date >= ? AND next_episode_air_date <= ?
            ORDER BY next_episode_air_date ASC
        ''', (start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]


def get_all_schedule() -> List[Dict]:
    """Get all schedule entries."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT * FROM tv_schedule ORDER BY next_episode_air_date ASC')
        return [dict(row) for row in cursor.fetchall()]


def remove_schedule(tmdb_id: str) -> None:
    """Remove a show from the schedule."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('DELETE FROM tv_schedule WHERE tmdb_id = ?', (tmdb_id,))
