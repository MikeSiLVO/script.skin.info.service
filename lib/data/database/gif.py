"""GIF cache database operations."""
from __future__ import annotations

from typing import Optional, Dict, Set, Union
from lib.data.database._infrastructure import get_db, sql_placeholders

def get_cached_gif(gif_path: str) -> Optional[Dict[str, Union[float, str]]]:
    """Return `{mtime, scanned_at}` for a cached GIF path, or None if not cached."""
    with get_db() as cursor:
        cursor.execute(
            'SELECT mtime, scanned_at FROM gif_cache WHERE path = ?',
            (gif_path,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'mtime': row['mtime'],
                'scanned_at': row['scanned_at']
            }
    return None


def update_gif_cache(gif_path: str, mtime: float, scanned_at: str) -> None:
    """Upsert a GIF cache entry."""
    with get_db() as cursor:
        cursor.execute('''
            INSERT INTO gif_cache (path, mtime, scanned_at)
            VALUES (?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime = excluded.mtime,
                scanned_at = excluded.scanned_at
        ''', (gif_path, mtime, scanned_at))


def get_all_cached_gifs() -> Dict[str, Dict[str, Union[float, str]]]:
    """Return all cached entries as `path -> {mtime, scanned_at}`."""
    cache = {}
    with get_db() as cursor:
        cursor.execute('SELECT path, mtime, scanned_at FROM gif_cache')
        for row in cursor.fetchall():
            cache[row['path']] = {
                'mtime': row['mtime'],
                'scanned_at': row['scanned_at']
            }
    return cache


def cleanup_stale_gifs(accessed_paths: Set[str]) -> int:
    """Remove cache entries whose path isn't in `accessed_paths`. Returns number deleted."""
    with get_db() as cursor:
        if not accessed_paths:
            cursor.execute('DELETE FROM gif_cache')
            return cursor.rowcount

        placeholders = sql_placeholders(len(accessed_paths))
        cursor.execute(
            f'DELETE FROM gif_cache WHERE path NOT IN ({placeholders})',
            tuple(accessed_paths)
        )
        return cursor.rowcount


def clear_gif_cache() -> int:
    """Clear entire GIF cache. Returns number of entries removed."""
    with get_db() as cursor:
        cursor.execute('DELETE FROM gif_cache')
        return cursor.rowcount
