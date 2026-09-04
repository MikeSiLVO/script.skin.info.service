"""Slideshow pool database operations."""
from __future__ import annotations

from typing import List, Optional

from lib.data.database._infrastructure import get_db, sql_placeholders

_POOL_INSERT_SQL = '''
    INSERT INTO slideshow_pool (media_type, dbid, title, fanart, plot, year, artist)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (media_type, dbid) DO UPDATE SET
        title = excluded.title, fanart = excluded.fanart, plot = excluded.plot,
        year = excluded.year, artist = excluded.artist
'''

# Bumped after each repopulate (post-swap) so cursors rebuild against a whole pool, not a partial.
_pool_generation = 0


def _bump_generation() -> None:
    global _pool_generation
    _pool_generation += 1


def populate_pool(*record_sets: List[tuple]) -> None:
    """Replace the slideshow pool with all given row sets in one transaction."""
    with get_db() as cursor:
        cursor.execute('DELETE FROM slideshow_pool')
        rows = [row for records in record_sets for row in (records or [])]
        if rows:
            cursor.executemany(_POOL_INSERT_SQL, rows)
    _bump_generation()


def upsert_pool_item(media_type: str, dbid: int, title: str, fanart: str,
                     plot: str, year: Optional[int], artist: str = '') -> None:
    """Insert or replace one pool row (keyed on media_type+dbid), then bump generation."""
    with get_db() as cursor:
        cursor.execute(_POOL_INSERT_SQL,
                       (media_type, dbid, title, fanart, plot, year, artist))
    _bump_generation()


def delete_pool_item(media_type: str, dbid: int) -> None:
    """Drop one pool row (its fanart was cleared); bump generation only if a row was removed."""
    with get_db() as cursor:
        cursor.execute('DELETE FROM slideshow_pool WHERE media_type = ? AND dbid = ?',
                       (media_type, dbid))
        removed = cursor.rowcount > 0
    if removed:
        _bump_generation()


def get_pool_compare_fields(media_types: tuple) -> dict:
    """`(media_type, dbid) -> (title, fanart, plot, year, artist)`, for the reconcile diff."""
    if not media_types:
        return {}
    placeholders = sql_placeholders(len(media_types))
    with get_db() as cursor:
        cursor.execute(
            'SELECT media_type, dbid, title, fanart, plot, year, artist FROM slideshow_pool '
            f'WHERE media_type IN ({placeholders})',
            tuple(media_types))
        return {(r[0], r[1]): (r[2], r[3], r[4], r[5], r[6]) for r in cursor.fetchall()}


def apply_pool_diff(upserts: List[tuple], deletes: List[tuple]) -> None:
    """Apply a reconcile diff in one transaction; bump generation once iff anything changed.

    `upserts` are full pool-row tuples; `deletes` are (media_type, dbid) keys.
    """
    if not upserts and not deletes:
        return
    with get_db() as cursor:
        if upserts:
            cursor.executemany(_POOL_INSERT_SQL, upserts)
        for media_type, dbid in deletes:
            cursor.execute('DELETE FROM slideshow_pool WHERE media_type = ? AND dbid = ?',
                           (media_type, dbid))
    _bump_generation()


def pool_generation() -> int:
    """Monotonic counter that changes whenever the pool is repopulated."""
    return _pool_generation


def get_all_pool_rows() -> list:
    """Return every pool row (all types), for building in-memory rotation cursors."""
    with get_db() as cursor:
        cursor.execute('SELECT media_type, title, fanart, plot, year, artist FROM slideshow_pool')
        return cursor.fetchall()


def get_artist_description(dbid: int) -> str:
    """Cached artist bio, for a song/album background carrying no description of its own."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT plot FROM slideshow_pool WHERE media_type = 'artist' AND dbid = ?",
            (dbid,))
        row = cursor.fetchone()
    return (row[0] or '') if row else ''


def is_pool_populated() -> bool:
    """True if the slideshow pool has any rows."""
    with get_db() as cursor:
        cursor.execute('SELECT 1 FROM slideshow_pool LIMIT 1')
        return cursor.fetchone() is not None


def pool_predates_artist() -> bool:
    """True while rows predate the artist column, so a pool built before music video support
    gets one reconcile instead of waiting for a library scan."""
    with get_db() as cursor:
        cursor.execute('SELECT 1 FROM slideshow_pool WHERE artist IS NULL LIMIT 1')
        return cursor.fetchone() is not None
