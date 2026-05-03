"""Slideshow pool database operations."""
from __future__ import annotations

from typing import List

from lib.data.database._infrastructure import get_db, sql_placeholders

# Whitelist of columns callers may project via `get_random_pool_items(fields=...)`. Anything
# outside this set is rejected to keep the inline SQL build safe from injection.
_POOL_COLUMNS = {
    'dbid', 'media_type', 'title', 'fanart', 'description', 'year', 'season', 'episode',
    'last_synced',
}

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


def get_random_fanart_urls(limit: int) -> List[str]:
    """Return up to `limit` random fanart URLs from the pool."""
    with get_db() as cursor:
        cursor.execute('''
            SELECT fanart
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        return [row['fanart'] for row in cursor.fetchall() if row['fanart']]


def get_random_pool_items(media_types: List[str], fields: List[str], limit: int) -> list:
    """Return up to `limit` random rows projecting `fields`, filtered to `media_types`.

    `fields` are validated against `_POOL_COLUMNS` to keep the inline SQL build safe.
    """
    invalid = [f for f in fields if f not in _POOL_COLUMNS]
    if invalid:
        raise ValueError(f"Invalid pool columns: {invalid}")
    select_clause = ', '.join(fields)

    if len(media_types) == 1:
        where_clause = 'WHERE media_type = ?'
        params = (media_types[0],)
    else:
        placeholders = sql_placeholders(len(media_types))
        where_clause = f'WHERE media_type IN ({placeholders})'
        params = tuple(media_types)

    with get_db() as cursor:
        cursor.execute(f'''
            SELECT {select_clause}
            FROM slideshow_pool
            {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        ''', params + (limit,))
        return cursor.fetchall()


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
