"""Slideshow pool database operations."""
from __future__ import annotations

from typing import List

from lib.data.database._infrastructure import get_db

_POOL_INSERT_SQL = '''
    INSERT OR REPLACE INTO slideshow_pool
    (dbid, media_type, title, fanart, description, year, season, episode, last_synced)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
'''


def populate_pool(movies: List[tuple], tvshows: List[tuple], artists: List[tuple]) -> None:
    """Replace the slideshow pool with all given rows in one transaction."""
    with get_db() as cursor:
        cursor.execute('DELETE FROM slideshow_pool')
        rows = (movies or []) + (tvshows or []) + (artists or [])
        if rows:
            cursor.executemany(_POOL_INSERT_SQL, rows)


def get_all_pool_items(limit: int) -> list:
    """Return up to `limit` random pool rows with default fields."""
    with get_db() as cursor:
        cursor.execute('''
            SELECT media_type, title, fanart, description, year
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()


def is_pool_populated() -> bool:
    """True if the slideshow pool has any rows."""
    with get_db() as cursor:
        cursor.execute('SELECT 1 FROM slideshow_pool LIMIT 1')
        return cursor.fetchone() is not None
