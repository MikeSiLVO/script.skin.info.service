"""TV show / season runtime cache (storage CRUD)."""
from __future__ import annotations

from typing import Optional, Tuple

from lib.data.database._infrastructure import get_db

# season 0 is specials
_WHOLE_SHOW = -1


def get_show_runtime(tvshowid: int) -> Optional[Tuple[int, int]]:
    """Return (total_runtime_seconds, avg_episode_runtime_seconds) or None if not cached."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT total, avg FROM tvshow_runtime WHERE tvshowid = ? AND season = ?",
            (tvshowid, _WHOLE_SHOW),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row["total"], row["avg"]


def get_season_runtime(tvshowid: int, season: int) -> Optional[int]:
    """Return total_runtime_seconds for a season, or None if not cached."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT total FROM tvshow_runtime WHERE tvshowid = ? AND season = ?",
            (tvshowid, season),
        )
        row = cursor.fetchone()
        return row["total"] if row else None


def save_show_runtime(tvshowid: int, total: int, avg: int, episode_count: int) -> None:
    with get_db() as cursor:
        cursor.execute(
            "INSERT INTO tvshow_runtime (tvshowid, season, total, avg, episodes) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (tvshowid, season) DO UPDATE SET "
            "total = excluded.total, avg = excluded.avg, episodes = excluded.episodes",
            (tvshowid, _WHOLE_SHOW, total, avg, episode_count),
        )


def save_season_runtime(tvshowid: int, season: int, total: int, episode_count: int) -> None:
    with get_db() as cursor:
        cursor.execute(
            "INSERT INTO tvshow_runtime (tvshowid, season, total, avg, episodes) "
            "VALUES (?, ?, ?, 0, ?) "
            "ON CONFLICT (tvshowid, season) DO UPDATE SET "
            "total = excluded.total, episodes = excluded.episodes",
            (tvshowid, season, total, episode_count),
        )


def invalidate_show_runtime(tvshowid: int) -> None:
    """Drop all cached runtime entries for a show (whole + every season)."""
    with get_db() as cursor:
        cursor.execute("DELETE FROM tvshow_runtime WHERE tvshowid = ?", (tvshowid,))


def clear_all_runtime_cache() -> None:
    """Drop every cached runtime entry."""
    with get_db() as cursor:
        cursor.execute("DELETE FROM tvshow_runtime")
