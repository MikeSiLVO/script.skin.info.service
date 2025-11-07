"""GIF cache database operations."""
from __future__ import annotations

from typing import Optional, Dict
from lib.data.database._infrastructure import get_db

def get_cached_gif(gif_path: str) -> Optional[Dict[str, float | str]]:
    """
    Get cached GIF metadata.

    Args:
        gif_path: Full path to GIF file

    Returns:
        Dict with 'mtime' and 'scanned_at', or None if not cached
    """
    with get_db() as (conn, cursor):
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
    """
    Update or insert GIF cache entry.

    Args:
        gif_path: Full path to GIF file
        mtime: File modification time
        scanned_at: Timestamp when scanned
    """
    with get_db() as (conn, cursor):
        cursor.execute('''
            INSERT INTO gif_cache (path, mtime, scanned_at)
            VALUES (?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime = excluded.mtime,
                scanned_at = excluded.scanned_at
        ''', (gif_path, mtime, scanned_at))


def get_all_cached_gifs() -> Dict[str, Dict[str, float | str]]:
    """
    Get all cached GIF entries.

    Returns:
        Dict mapping paths to metadata dicts
    """
    cache = {}
    with get_db() as (conn, cursor):
        cursor.execute('SELECT path, mtime, scanned_at FROM gif_cache')
        for row in cursor.fetchall():
            cache[row['path']] = {
                'mtime': row['mtime'],
                'scanned_at': row['scanned_at']
            }
    return cache


def cleanup_stale_gifs(accessed_paths: set[str]) -> int:
    """
    Remove GIF cache entries not in the accessed set.

    Args:
        accessed_paths: Set of paths that were found during scan

    Returns:
        Number of stale entries removed
    """
    with get_db() as (conn, cursor):
        if not accessed_paths:
            cursor.execute('SELECT COUNT(*) as count FROM gif_cache')
            count = cursor.fetchone()['count']
            cursor.execute('DELETE FROM gif_cache')
            return count

        placeholders = ','.join('?' * len(accessed_paths))
        cursor.execute(
            f'DELETE FROM gif_cache WHERE path NOT IN ({placeholders})',
            tuple(accessed_paths)
        )
        return cursor.rowcount


def clear_gif_cache() -> int:
    """
    Clear entire GIF cache.

    Returns:
        Number of entries removed
    """
    with get_db() as (conn, cursor):
        cursor.execute('SELECT COUNT(*) as count FROM gif_cache')
        count = cursor.fetchone()['count']
        cursor.execute('DELETE FROM gif_cache')
        return count
