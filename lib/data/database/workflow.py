"""Workflow tracking for sessions and operations.

Manages scan_sessions table for artwork review workflows and operation_history
table for art tool runs (texture cache, GIF scanner).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Set

from lib.data.database._infrastructure import get_db, DB_PATH


def _insert_session_media_types(cursor: sqlite3.Cursor, session_id: int, media_types: List[str]) -> None:
    """Insert media types for a session into junction table."""
    if not media_types:
        return
    cursor.executemany('''
        INSERT INTO session_media_types (session_id, media_type)
        VALUES (?, ?)
    ''', [(session_id, mt) for mt in media_types])


def _insert_session_art_types(cursor: sqlite3.Cursor, session_id: int, art_types: List[str]) -> None:
    """Insert art types for a session into junction table."""
    if not art_types:
        return
    cursor.executemany('''
        INSERT INTO session_art_types (session_id, art_type)
        VALUES (?, ?)
    ''', [(session_id, at) for at in art_types])


def _get_session_media_types(cursor: sqlite3.Cursor, session_id: int) -> List[str]:
    """Retrieve media types for a session from junction table."""
    cursor.execute('''
        SELECT media_type
        FROM session_media_types
        WHERE session_id = ?
        ORDER BY media_type
    ''', (session_id,))
    return [row[0] for row in cursor.fetchall()]


def _get_session_art_types(cursor: sqlite3.Cursor, session_id: int) -> List[str]:
    """Retrieve art types for a session from junction table."""
    cursor.execute('''
        SELECT art_type
        FROM session_art_types
        WHERE session_id = ?
        ORDER BY art_type
    ''', (session_id,))
    return [row[0] for row in cursor.fetchall()]


def get_session_media_types(session_id: int) -> List[str]:
    """Public wrapper to retrieve media types for a session."""
    with get_db(DB_PATH) as (conn, cursor):
        return _get_session_media_types(cursor, session_id)


def get_session_media_types_batch(session_ids: List[int]) -> Dict[int, List[str]]:
    if not session_ids:
        return {}

    with get_db(DB_PATH) as (conn, cursor):
        placeholders = ','.join('?' * len(session_ids))
        cursor.execute(f'''
            SELECT session_id, media_type
            FROM session_media_types
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, media_type
        ''', session_ids)

        result: Dict[int, List[str]] = {sid: [] for sid in session_ids}
        for row in cursor.fetchall():
            result[row['session_id']].append(row['media_type'])

        return result


def get_session_art_types(session_id: int) -> List[str]:
    """Public wrapper to retrieve art types for a session."""
    with get_db(DB_PATH) as (conn, cursor):
        return _get_session_art_types(cursor, session_id)


def create_scan_session(scan_type: str, media_types: List[str], art_types: List[str]) -> int:
    """
    Create new scan session and return session ID.

    Args:
        scan_type: Type of scan ('manual_review', 'auto_fetch', etc.)
        media_types: List of media types being scanned
        art_types: List of art types being scanned

    Returns:
        Session ID
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT INTO scan_sessions (scan_type, last_activity)
            VALUES (?, ?)
        ''', (
            scan_type,
            datetime.now().isoformat()
        ))

        session_id = cursor.lastrowid
        assert session_id is not None, "Failed to create scan session"

        _insert_session_media_types(cursor, session_id, media_types)
        _insert_session_art_types(cursor, session_id, art_types)

        return session_id


def update_session_stats(session_id: int, stats: dict) -> None:
    """
    Update session statistics.

    Args:
        session_id: Session ID
        stats: Statistics dict to store (will be JSON encoded)
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE scan_sessions
            SET stats = ?, last_activity = ?
            WHERE id = ?
        ''', (json.dumps(stats), datetime.now().isoformat(), session_id))


def complete_session(session_id: int) -> None:
    """Mark session as completed."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE scan_sessions
            SET status = 'completed', completed = ?, last_activity = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), datetime.now().isoformat(), session_id))


def pause_session(session_id: int, stats: dict) -> None:
    """
    Mark session as paused with current stats.

    Args:
        session_id: Session ID
        stats: Current statistics to store before pausing
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE scan_sessions
            SET status = 'paused', stats = ?, last_activity = ?
            WHERE id = ?
        ''', (json.dumps(stats), datetime.now().isoformat(), session_id))


def cancel_session(session_id: int) -> None:
    """Mark session as cancelled and timestamp completion."""
    with get_db(DB_PATH) as (conn, cursor):
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE scan_sessions
            SET status = 'cancelled', last_activity = ?
            WHERE id = ?
        ''', (now, session_id))


def get_paused_sessions() -> List[sqlite3.Row]:
    """Get all paused review sessions."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT * FROM scan_sessions
            WHERE status = 'paused'
            ORDER BY last_activity DESC
        ''')

        return cursor.fetchall()


def get_session(session_id: int) -> Optional[sqlite3.Row]:
    """
    Return a single scan session row by ID.

    Args:
        session_id: Session ID

    Returns:
        Session row or None if not found
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT *
            FROM scan_sessions
            WHERE id = ?
            LIMIT 1
        ''', (session_id,))

        return cursor.fetchone()


def get_last_manual_review_session(media_types: Optional[Sequence[str]] = None) -> Optional[sqlite3.Row]:
    """
    Return most recent manual review session, optionally filtered by media types.

    Args:
        media_types: Optional list of media types to match

    Returns:
        Most recent matching session row or None
    """
    with get_db(DB_PATH) as (conn, cursor):
        if not media_types:
            cursor.execute('''
                SELECT *
                FROM scan_sessions
                WHERE scan_type = 'manual_review'
                ORDER BY last_activity DESC
                LIMIT 1
            ''')
            return cursor.fetchone()

        media_types_set = set(media_types)
        media_count = len(media_types_set)

        # Safe: .format() only inserts '?' placeholders (media_count controls count, no user input)
        cursor.execute('''
            SELECT s.*
            FROM scan_sessions s
            LEFT JOIN session_media_types smt ON s.id = smt.session_id
            WHERE s.scan_type = 'manual_review'
            GROUP BY s.id
            HAVING (
                (? = 0 AND COUNT(smt.media_type) = 0) OR
                (? > 0 AND
                 COUNT(smt.media_type) = ? AND
                 SUM(CASE WHEN smt.media_type IN ({}) THEN 1 ELSE 0 END) = ?)
            )
            ORDER BY s.last_activity DESC
            LIMIT 1
        '''.format(','.join('?' * media_count)),
        (media_count, media_count, media_count, *media_types_set, media_count))

        return cursor.fetchone()


def save_operation_stats(operation: str, stats: dict, scope: Optional[str] = None) -> None:
    """
    Save operation stats to history.

    Args:
        operation: Operation type ('texture_precache', 'texture_cleanup', 'gif_scan')
        stats: Dictionary of operation stats
        scope: Optional scope ('movies', 'tvshows', 'all')
    """
    timestamp = datetime.now().isoformat()
    stats_json = json.dumps(stats)
    completed = 0 if stats.get('cancelled') else 1

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT INTO operation_history (operation, timestamp, stats, completed, scope)
            VALUES (?, ?, ?, ?, ?)
        ''', (operation, timestamp, stats_json, completed, scope))


def get_last_operation_stats(operation: str) -> Optional[dict]:
    """
    Get most recent stats for an operation type.

    Args:
        operation: Operation type ('texture_precache', 'texture_cleanup', 'gif_scan')

    Returns:
        Dict with 'operation', 'timestamp', 'stats', 'completed', 'scope' or None
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT operation, timestamp, stats, completed, scope
            FROM operation_history
            WHERE operation = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (operation,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'operation': row['operation'],
            'timestamp': row['timestamp'],
            'stats': json.loads(row['stats']),
            'completed': bool(row['completed']),
            'scope': row['scope']
        }


def get_imdb_update_progress(media_type: str) -> Optional[Dict]:
    """
    Get saved IMDb update progress for a media type.

    Args:
        media_type: "movie", "tvshow", or "episode"

    Returns:
        Dict with dataset_date, processed_ids (set), total_items, started_at
        or None if no progress saved
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT dataset_date, processed_ids, total_items, started_at
            FROM imdb_update_progress
            WHERE media_type = ?
        ''', (media_type,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'dataset_date': row['dataset_date'],
            'processed_ids': set(json.loads(row['processed_ids'])),
            'total_items': row['total_items'],
            'started_at': row['started_at']
        }


def save_imdb_update_progress(
    media_type: str,
    dataset_date: str,
    processed_ids: Set[int],
    total_items: int
) -> None:
    """
    Save IMDb update progress for resumption.

    Args:
        media_type: "movie", "tvshow", or "episode"
        dataset_date: IMDb dataset last_modified date
        processed_ids: Set of processed database IDs
        total_items: Total number of items to process
    """
    now = datetime.now().isoformat()

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT started_at FROM imdb_update_progress WHERE media_type = ?
        ''', (media_type,))
        row = cursor.fetchone()
        started_at = row['started_at'] if row else now

        cursor.execute('''
            INSERT OR REPLACE INTO imdb_update_progress
            (media_type, dataset_date, processed_ids, total_items, started_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            media_type,
            dataset_date,
            json.dumps(list(processed_ids)),
            total_items,
            started_at,
            now
        ))


def clear_imdb_update_progress(media_type: str) -> None:
    """
    Clear saved IMDb update progress for a media type.

    Called when update completes successfully.

    Args:
        media_type: "movie", "tvshow", or "episode"
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            DELETE FROM imdb_update_progress WHERE media_type = ?
        ''', (media_type,))
