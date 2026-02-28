"""Slideshow pool database operations."""
from __future__ import annotations

from typing import List

from lib.data.database._infrastructure import get_db


def populate_pool(
    movies: List[tuple],
    tvshows: List[tuple],
    artists: List[tuple]
) -> None:
    with get_db() as (_, cursor):
        cursor.execute('DELETE FROM slideshow_pool')

        if movies:
            cursor.executemany('''
                INSERT OR REPLACE INTO slideshow_pool
                (kodi_dbid, media_type, title, fanart, description, year, season, episode, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', movies)

        if tvshows:
            cursor.executemany('''
                INSERT OR REPLACE INTO slideshow_pool
                (kodi_dbid, media_type, title, fanart, description, year, season, episode, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tvshows)

        if artists:
            cursor.executemany('''
                INSERT OR REPLACE INTO slideshow_pool
                (kodi_dbid, media_type, title, fanart, description, year, season, episode, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', artists)


def get_random_fanart_urls(limit: int) -> List[str]:
    with get_db() as (_, cursor):
        cursor.execute('''
            SELECT fanart
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        return [row['fanart'] for row in cursor.fetchall() if row['fanart']]


def get_random_pool_items(
    media_types: List[str],
    fields: List[str],
    limit: int
) -> list:
    select_clause = ', '.join(fields)

    if len(media_types) == 1:
        where_clause = 'WHERE media_type = ?'
        params = (media_types[0],)
    else:
        placeholders = ','.join('?' * len(media_types))
        where_clause = f'WHERE media_type IN ({placeholders})'
        params = tuple(media_types)

    with get_db() as (_, cursor):
        cursor.execute(f'''
            SELECT {select_clause}
            FROM slideshow_pool
            {where_clause}
            ORDER BY RANDOM()
            LIMIT ?
        ''', params + (limit,))
        return cursor.fetchall()


def get_all_pool_items(limit: int) -> list:
    with get_db() as (_, cursor):
        cursor.execute('''
            SELECT media_type, title, fanart, description, year
            FROM slideshow_pool
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()


def is_pool_populated() -> bool:
    with get_db() as (_, cursor):
        cursor.execute('SELECT COUNT(*) as count FROM slideshow_pool')
        row = cursor.fetchone()
        return row['count'] > 0 if row else False
