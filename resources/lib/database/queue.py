"""Queue CRUD operations for artwork review workflow.

Manages art_queue and art_items tables. Handles adding items to queue,
retrieving batches, updating status, and cleanup.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence, Dict, List

from resources.lib.database._infrastructure import get_db, DB_PATH, _generate_guid, vacuum_database
from resources.lib.artwork.helpers import validate_media_type, validate_dbid
from resources.lib.kodi import log_database

# Art item review mode constants (values for art_items.review_mode field)
ARTITEM_REVIEW_MISSING = 'missing'
ARTITEM_REVIEW_CANDIDATE = 'candidate'
VALID_ARTITEM_REVIEW_MODES = {ARTITEM_REVIEW_MISSING, ARTITEM_REVIEW_CANDIDATE}


# Queue Management

def clear_queue() -> None:
    """Clear all queue data."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('DELETE FROM art_items')
        cursor.execute('DELETE FROM art_queue')
        cursor.execute('DELETE FROM scan_sessions')

    vacuum_database()


def clear_queue_for_media(media_types: Sequence[str]) -> None:
    """Clear queue entries for specific media types."""
    if not media_types:
        return

    placeholders = ','.join('?' for _ in media_types)

    with get_db(DB_PATH) as (conn, cursor):
        # Safe: placeholders contains only '?' characters, no user input
        cursor.execute(f'''
            DELETE FROM art_queue
            WHERE media_type IN ({placeholders})
        ''', tuple(media_types))


def add_to_queue(
    media_type: str,
    dbid: int,
    title: str,
    year: str = '',
    priority: int = 5,
    scope: str = '',
    scan_session_id: Optional[int] = None,
    guid: Optional[str] = None,
) -> int:
    """
    Add item to queue or return existing ID (wrapper around add_to_queue_batch).
    If item already exists, resets status to 'pending' for re-processing.

    Returns:
        Queue ID
    """
    if not validate_media_type(media_type):
        raise ValueError(f"Invalid media_type: {media_type}")
    if not validate_dbid(dbid):
        raise ValueError(f"Invalid dbid: {dbid} (must be positive integer)")

    items = [{
        'media_type': media_type,
        'dbid': dbid,
        'title': title,
        'year': year,
        'priority': priority,
        'scope': scope,
        'scan_session_id': scan_session_id,
        'guid': guid
    }]

    queue_ids = add_to_queue_batch(items)
    return queue_ids[0]


def add_art_item(
    queue_id: int,
    art_type: str,
    baseline_url: str = '',
    review_mode: str = ARTITEM_REVIEW_MISSING,
    requires_manual: bool = False,
    scan_session_id: Optional[int] = None,
) -> None:
    """Add art item to queue if it doesn't already exist."""
    with get_db(DB_PATH) as (conn, cursor):
        mode = review_mode if review_mode in VALID_ARTITEM_REVIEW_MODES else (
            ARTITEM_REVIEW_MISSING if not baseline_url else ARTITEM_REVIEW_CANDIDATE
        )
        manual_flag = 1 if requires_manual else 0

        cursor.execute('''
            SELECT id FROM art_items WHERE queue_id = ? AND art_type = ?
        ''', (queue_id, art_type))

        existing = cursor.fetchone()

        if not existing:
            # Only insert if doesn't exist
            cursor.execute('''
                INSERT INTO art_items (queue_id, art_type, current_url, baseline_url, review_mode, requires_manual, status, scan_session_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', (
                queue_id,
                art_type,
                baseline_url,
                baseline_url,
                mode,
                manual_flag,
                scan_session_id,
            ))
        else:
            cursor.execute('''
                UPDATE art_items
                SET current_url = ?, baseline_url = ?, review_mode = ?, requires_manual = ?, status = 'pending'
                WHERE id = ?
            ''', (
                baseline_url,
                baseline_url,
                mode,
                manual_flag,
                existing['id'],
            ))


def add_to_queue_batch(items: List[dict]) -> List[int]:
    """
    Add multiple items to queue in a single transaction (much faster).

    Args:
        items: List of dicts with keys: media_type, dbid, title, year (optional), priority (optional)

    Returns:
        List of queue IDs
    """
    if not items:
        return []

    with get_db(DB_PATH) as (conn, cursor):
        queue_ids = []

        for item in items:
            media_type = item['media_type']
            dbid = item['dbid']
            title = item.get('title', '')
            year = item.get('year', '')
            priority = item.get('priority', 5)
            scope = item.get('scope', '')
            scan_session_id = item.get('scan_session_id')
            guid = item.get('guid') or _generate_guid()

            # Try to insert, or get existing ID
            cursor.execute('''
                INSERT OR IGNORE INTO art_queue (media_type, dbid, title, year, priority, scope, scan_session_id, guid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (media_type, dbid, title, year, priority, scope or '', scan_session_id, guid))

            if cursor.lastrowid:
                queue_ids.append(cursor.lastrowid)
            else:
                # Already exists, get ID and reset status
                cursor.execute('''
                    SELECT id, guid FROM art_queue WHERE media_type = ? AND dbid = ?
                ''', (media_type, dbid))
                row = cursor.fetchone()
                queue_id = row['id'] if row else None

                if queue_id:
                    cursor.execute('''
                        UPDATE art_queue SET status = 'pending', date_processed = NULL
                        WHERE id = ?
                    ''', (queue_id,))
                    queue_ids.append(queue_id)

                    updates = []
                    params: List[Any] = []
                    if scope:
                        updates.append('scope = ?')
                        params.append(scope)
                    if scan_session_id is not None:
                        updates.append('scan_session_id = ?')
                        params.append(scan_session_id)
                    if row and not row['guid']:
                        updates.append('guid = ?')
                        params.append(guid)

                    if updates:
                        params.append(queue_id)
                        # Safe: updates list contains only validated column names from internal logic
                        cursor.execute(f'''
                            UPDATE art_queue
                            SET {', '.join(updates)}
                            WHERE id = ?
                        ''', params)

    return queue_ids


def add_art_items_batch(art_items: List[dict]) -> None:
    """
    Add multiple art items in a single transaction (much faster).

    Args:
        art_items: List of dicts with keys: queue_id, art_type, current_url (optional)
    """
    if not art_items:
        return

    with get_db(DB_PATH) as (conn, cursor):
        # First, get all existing art items for these queue_ids
        queue_ids = list(set(item['queue_id'] for item in art_items))
        placeholders = ','.join('?' * len(queue_ids))
        # Safe: placeholders contains only '?' characters, no user input
        cursor.execute(f'''
            SELECT id, queue_id, art_type FROM art_items
            WHERE queue_id IN ({placeholders})
        ''', queue_ids)

        existing_rows = cursor.fetchall()
        existing = {(row['queue_id'], row['art_type']): row['id'] for row in existing_rows}

        # Prepare inserts/updates
        to_insert = []
        to_update = []

        for item in art_items:
            queue_id = item['queue_id']
            art_type = item['art_type']
            baseline_url = item.get('baseline_url')
            current_url = item.get('current_url', baseline_url)
            review_mode = item.get('review_mode', ARTITEM_REVIEW_MISSING)
            requires_manual = 1 if item.get('requires_manual') else 0
            scan_session_id = item.get('scan_session_id')

            mode = review_mode if review_mode in VALID_ARTITEM_REVIEW_MODES else (
                ARTITEM_REVIEW_MISSING if not baseline_url else ARTITEM_REVIEW_CANDIDATE
            )
            baseline_val = baseline_url or current_url or ''
            current_val = current_url or baseline_val

            if (queue_id, art_type) not in existing:
                to_insert.append((
                    queue_id,
                    art_type,
                    current_val,
                    baseline_val,
                    mode,
                    requires_manual,
                    scan_session_id
                ))
            else:
                to_update.append((
                    current_val,
                    baseline_val,
                    mode,
                    requires_manual,
                    scan_session_id,
                    existing[(queue_id, art_type)]
                ))

        if to_insert:
            cursor.executemany('''
                INSERT INTO art_items (queue_id, art_type, current_url, baseline_url, review_mode, requires_manual, status, scan_session_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', to_insert)

        if to_update:
            cursor.executemany('''
                UPDATE art_items
                SET current_url = ?, baseline_url = ?, review_mode = ?, requires_manual = ?, scan_session_id = ?, status = 'pending'
                WHERE id = ?
            ''', to_update)


# Queue Retrieval

def get_next_batch(batch_size: int = 100, status: str = 'pending', media_types: Optional[Sequence[str]] = None) -> List[sqlite3.Row]:
    """
    Get next batch of items to process.

    Args:
        batch_size: Number of items to fetch
        status: Status filter ('pending', 'processing', etc.)
        media_types: Optional list/tuple of media types to limit results

    Returns:
        List of queue rows
    """
    with get_db(DB_PATH) as (conn, cursor):
        query = '''
            SELECT * FROM art_queue
            WHERE status = ?
        '''
        params: List[Any] = [status]

        if media_types:
            placeholders = ','.join('?' for _ in media_types)
            query += f' AND media_type IN ({placeholders})'
            params.extend(media_types)

        query += ' ORDER BY priority ASC, id ASC LIMIT ?'
        params.append(batch_size)

        cursor.execute(query, params)

        return cursor.fetchall()


def get_art_items_for_queue(queue_id: int) -> List[sqlite3.Row]:
    """Get all art items for a queue entry."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT * FROM art_items
            WHERE queue_id = ?
        ''', (queue_id,))

        return cursor.fetchall()


def get_art_items_for_queue_batch(queue_ids: List[int]) -> Dict[int, List[sqlite3.Row]]:
    """
    Get art items for multiple queue entries in a single query.

    Args:
        queue_ids: List of queue entry IDs

    Returns:
        Dictionary mapping queue_id to list of art_items
    """
    if not queue_ids:
        return {}

    with get_db(DB_PATH) as (conn, cursor):
        placeholders = ','.join('?' * len(queue_ids))
        # Safe: placeholders contains only '?' characters, no user input
        cursor.execute(f'''
            SELECT * FROM art_items
            WHERE queue_id IN ({placeholders})
        ''', queue_ids)

        rows = cursor.fetchall()

        result: Dict[int, List[sqlite3.Row]] = {qid: [] for qid in queue_ids}
        for row in rows:
            queue_id = row['queue_id']
            if queue_id in result:
                result[queue_id].append(row)

        return result


# Queue Updates

def update_queue_status(queue_id: int, status: str) -> None:
    """Update queue item status."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE art_queue
            SET status = ?, date_processed = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), queue_id))


def update_art_item(art_item_id: int, selected_url: str, auto_applied: bool = False) -> None:
    """Update art item with selected URL."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE art_items
            SET selected_url = ?, auto_applied = ?, status = 'completed', requires_manual = 0, date_processed = ?
            WHERE id = ?
        ''', (selected_url, 1 if auto_applied else 0, datetime.now().isoformat(), art_item_id))


def update_art_item_status(art_item_id: int, status: str) -> None:
    """Update art item status without changing selected URL."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            UPDATE art_items
            SET status = ?, date_processed = COALESCE(date_processed, ?)
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), art_item_id))


# Queue Statistics

def get_queue_stats(media_types: Optional[Sequence[str]] = None) -> dict:
    """Get queue statistics."""
    with get_db(DB_PATH) as (conn, cursor):
        stats = {}

        # Total items by status
        query = '''
            SELECT status, COUNT(*) as count
            FROM art_queue
        '''
        params: list[Any] = []

        if media_types:
            placeholders = ','.join('?' for _ in media_types)
            query += f' WHERE media_type IN ({placeholders})'
            params.extend(media_types)

        query += ' GROUP BY status'

        cursor.execute(query, params)
        for row in cursor.fetchall():
            stats[row['status']] = row['count']

    return stats


def get_queue_breakdown_by_media() -> dict:
    """
    Get queue statistics broken down by media_type and status.

    Returns:
        Dict mapping media_type -> {status: count}
        Example: {
            'movie': {'pending': 50, 'completed': 20, 'skipped': 5},
            'tvshow': {'pending': 30, 'completed': 10, 'skipped': 2}
        }
    """
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT media_type, status, COUNT(*) as count
            FROM art_queue
            GROUP BY media_type, status
        ''')

        result = {}
        for row in cursor.fetchall():
            media_type = row['media_type']
            status = row['status']
            count = row['count']

            if media_type not in result:
                result[media_type] = {}
            result[media_type][status] = count

        return result


def has_pending_queue() -> bool:
    """Check if there are pending items in queue."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT COUNT(*) as count FROM art_queue WHERE status = 'pending'
        ''')

        row = cursor.fetchone()
        return row['count'] > 0 if row else False


def get_pending_media_counts(status: str = 'pending') -> Dict[str, int]:
    """Return counts of pending items grouped by media type."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT media_type, COUNT(*) as count
            FROM art_queue
            WHERE status = ?
            GROUP BY media_type
        ''', (status,))

        return {row['media_type']: row['count'] for row in cursor.fetchall()}


def count_pending_missing_art(media_types: Optional[Sequence[str]] = None) -> int:
    """
    Count pending art items that represent missing artwork.

    Args:
        media_types: Optional iterable of media types to filter by

    Returns:
        Number of pending art_items with review_mode='missing'
    """
    with get_db(DB_PATH) as (conn, cursor):
        query = '''
            SELECT COUNT(*) AS count
            FROM art_items AS ai
            JOIN art_queue AS q ON ai.queue_id = q.id
            WHERE ai.status = 'pending'
              AND ai.review_mode = ?
              AND q.status = 'pending'
        '''
        params: list[Any] = [ARTITEM_REVIEW_MISSING]

        if media_types:
            placeholders = ','.join('?' for _ in media_types)
            query += f' AND q.media_type IN ({placeholders})'
            params.extend(media_types)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row['count']) if row else 0


def count_queue_items(
    status: Optional[str] = None,
    media_types: Optional[Sequence[str]] = None
) -> int:
    """
    Count queue items matching criteria without fetching records.

    Args:
        status: Optional status to filter by (e.g., 'pending')
        media_types: Optional iterable of media types to filter by

    Returns:
        Number of matching queue items
    """
    with get_db(DB_PATH) as (conn, cursor):
        query = 'SELECT COUNT(*) AS count FROM art_queue WHERE 1=1'
        params: List[Any] = []

        if status:
            query += ' AND status = ?'
            params.append(status)

        if media_types:
            placeholders = ','.join('?' for _ in media_types)
            query += f' AND media_type IN ({placeholders})'
            params.extend(media_types)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row['count']) if row else 0


# Queue Cleanup

def prune_inactive_queue_items(statuses: Optional[Sequence[str]] = None) -> int:
    """Remove queue items in a terminal state that have no pending art entries."""
    active_statuses = tuple(statuses or ('completed', 'skipped', 'cancelled', 'error'))
    if not active_statuses:
        return 0

    placeholders = ','.join('?' for _ in active_statuses)

    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute(
            f'''
            DELETE FROM art_queue
            WHERE status IN ({placeholders})
              AND id NOT IN (
                  SELECT DISTINCT queue_id
                  FROM art_items
                  WHERE status = 'pending'
              )
            ''',
            active_statuses
        )
        removed = cursor.rowcount

    if removed > 0:
        log_database(f"Pruned {removed} inactive queue items")
        vacuum_database()

    return removed


def restore_pending_queue_items(media_types: Optional[Sequence[str]] = None) -> int:
    """
    Reset queue status to 'pending' for items that still have pending art entries.

    Args:
        media_types: Optional iterable of media types to limit the update

    Returns:
        Number of queue rows updated
    """
    with get_db(DB_PATH) as (conn, cursor):
        query = '''
            UPDATE art_queue
            SET status = 'pending',
                date_processed = NULL
            WHERE status != 'pending'
              AND id IN (
                  SELECT DISTINCT queue_id
                  FROM art_items
                  WHERE status = 'pending'
              )
        '''
        params: list[Any] = []

        if media_types:
            placeholders = ','.join('?' for _ in media_types)
            query += f' AND media_type IN ({placeholders})'
            params.extend(media_types)

        cursor.execute(query, params)
        return cursor.rowcount


def cleanup_old_queue_items(days_old: int = 30) -> int:
    """
    Clean up completed/skipped/error queue items older than N days.

    Args:
        days_old: Remove items processed more than this many days ago

    Returns:
        Number of items removed
    """
    with get_db(DB_PATH) as (conn, cursor):
        cutoff = datetime.now() - timedelta(days=days_old)
        cutoff_str = cutoff.isoformat()

        cursor.execute('''
            DELETE FROM art_queue
            WHERE status IN ('completed', 'skipped', 'error')
            AND date_processed IS NOT NULL
            AND date_processed < ?
        ''', (cutoff_str,))

        deleted = cursor.rowcount

    if deleted > 0:
        log_database(f"Cleaned up {deleted} old queue items")
        vacuum_database()

    return deleted
