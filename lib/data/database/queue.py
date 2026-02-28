"""Queue CRUD operations for artwork review workflow.

Manages art_queue and art_items tables. Handles adding items to queue,
retrieving batches, updating status, and cleanup.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence, Dict, List

from lib.data.database._infrastructure import get_db, DB_PATH, _generate_guid, vacuum_database
from lib.kodi.utils import validate_media_type, validate_dbid
from lib.kodi.client import log

ARTITEM_REVIEW_MISSING = 'missing'

STATUS_PENDING = 'pending'
STATUS_COMPLETED = 'completed'
STATUS_SKIPPED = 'skipped'
STATUS_ERROR = 'error'
STATUS_CANCELLED = 'cancelled'
STATUS_STALE = 'stale'


def _build_placeholders(count: int) -> str:
    """Generate SQL placeholders for IN clause."""
    return ','.join('?' * count)


@dataclass(frozen=True)
class ArtItemEntry:
    """Single art item queued for review or processing."""

    id: int
    queue_id: int
    art_type: str
    selected_url: Optional[str]
    review_mode: str
    requires_manual: bool
    status: str


@dataclass(frozen=True)
class QueueEntry:
    """Top-level queue record representing a library item awaiting review."""

    id: int
    guid: str
    media_type: str
    dbid: int
    title: str
    year: str
    status: str
    scope: str
    scan_session_id: Optional[int]


def _row_to_queue_entry(row: sqlite3.Row) -> QueueEntry:
    """Convert database row to QueueEntry dataclass."""
    return QueueEntry(
        id=row['id'],
        guid=row['guid'] or '',
        media_type=row['media_type'],
        dbid=row['dbid'],
        title=row['title'] or '',
        year=row['year'] or '',
        status=row['status'] or 'pending',
        scope=row['scope'] or '',
        scan_session_id=row['scan_session_id'],
    )


def _row_to_art_item(row: sqlite3.Row) -> ArtItemEntry:
    """Convert database row to ArtItemEntry dataclass."""
    return ArtItemEntry(
        id=row['id'],
        queue_id=row['queue_id'],
        art_type=row['art_type'],
        selected_url=row['selected_url'],
        review_mode=row['review_mode'] or ARTITEM_REVIEW_MISSING,
        requires_manual=bool(row['requires_manual']),
        status=row['status'] or 'pending',
    )


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

    placeholders = _build_placeholders(len(media_types))

    with get_db(DB_PATH) as (conn, cursor):
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
    requires_manual: bool = False,
    scan_session_id: Optional[int] = None,
) -> None:
    """Add art item to queue or update if exists (UPSERT operation)."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            INSERT INTO art_items (queue_id, art_type, review_mode, requires_manual, status, scan_session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(queue_id, art_type) DO UPDATE SET
                review_mode = excluded.review_mode,
                requires_manual = excluded.requires_manual,
                status = excluded.status,
                scan_session_id = excluded.scan_session_id
        ''', (
            queue_id,
            art_type,
            ARTITEM_REVIEW_MISSING,
            int(requires_manual),
            STATUS_PENDING,
            scan_session_id,
        ))


def add_to_queue_batch(items: List[dict]) -> List[int]:
    """
    Add multiple items to queue using UPSERT (3 queries instead of N*3).

    Args:
        items: List of dicts with keys: media_type, dbid, title, year (optional), priority (optional)

    Returns:
        List of queue IDs in same order as input items
    """
    if not items:
        return []

    with get_db(DB_PATH) as (conn, cursor):
        prepared_items = []
        for item in items:
            media_type = item['media_type']
            dbid = item['dbid']
            title = item.get('title', '')
            year = item.get('year', '')
            priority = item.get('priority', 5)
            scope = item.get('scope', '')
            scan_session_id = item.get('scan_session_id')
            guid = item.get('guid') or _generate_guid()

            prepared_items.append((
                media_type, dbid, title, year, priority,
                scope or '', scan_session_id, guid
            ))

        cursor.executemany('''
            INSERT INTO art_queue (media_type, dbid, title, year, priority, scope, scan_session_id, guid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_type, dbid) DO UPDATE SET
                status = 'pending',
                date_processed = NULL,
                scope = COALESCE(NULLIF(excluded.scope, ''), art_queue.scope),
                scan_session_id = COALESCE(excluded.scan_session_id, art_queue.scan_session_id),
                guid = COALESCE(NULLIF(art_queue.guid, ''), excluded.guid)
        ''', prepared_items)

        media_dbid_pairs = [(item['media_type'], item['dbid']) for item in items]

        cursor.execute(f'''
            SELECT id, media_type, dbid
            FROM art_queue
            WHERE (media_type, dbid) IN (VALUES {','.join('(?, ?)' for _ in items)})
        ''', [val for pair in media_dbid_pairs for val in pair])

        rows = cursor.fetchall()
        id_map = {(row['media_type'], row['dbid']): row['id'] for row in rows}

        result = []
        for item in items:
            key = (item['media_type'], item['dbid'])
            queue_id = id_map.get(key)
            if queue_id is None:
                raise RuntimeError(f"UPSERT succeeded but SELECT failed for {key} - database corruption?")
            result.append(queue_id)
        return result


def add_art_items_batch(art_items: List[dict]) -> None:
    """
    Add multiple art items in a single transaction (much faster).

    Args:
        art_items: List of dicts with keys: queue_id, art_type, current_url (optional)
    """
    if not art_items:
        return

    with get_db(DB_PATH) as (conn, cursor):
        queue_ids = list(set(item['queue_id'] for item in art_items))
        placeholders = _build_placeholders(len(queue_ids))
        cursor.execute(f'''
            SELECT id, queue_id, art_type FROM art_items
            WHERE queue_id IN ({placeholders})
        ''', queue_ids)

        existing_rows = cursor.fetchall()
        existing = {(row['queue_id'], row['art_type']): row['id'] for row in existing_rows}

        to_insert = []
        to_update = []

        for item in art_items:
            queue_id = item['queue_id']
            art_type = item['art_type']
            requires_manual = 1 if item.get('requires_manual') else 0
            scan_session_id = item.get('scan_session_id')

            if (queue_id, art_type) not in existing:
                to_insert.append((
                    queue_id,
                    art_type,
                    ARTITEM_REVIEW_MISSING,
                    requires_manual,
                    scan_session_id
                ))
            else:
                to_update.append((
                    ARTITEM_REVIEW_MISSING,
                    requires_manual,
                    scan_session_id,
                    existing[(queue_id, art_type)]
                ))

        if to_insert:
            cursor.executemany('''
                INSERT INTO art_items (queue_id, art_type, review_mode, requires_manual, status, scan_session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [(q, a, r, m, STATUS_PENDING, s) for q, a, r, m, s in to_insert])

        if to_update:
            cursor.executemany('''
                UPDATE art_items
                SET review_mode = ?, requires_manual = ?, scan_session_id = ?, status = ?
                WHERE id = ?
            ''', [(r, m, s, STATUS_PENDING, i) for r, m, s, i in to_update])


def get_next_batch(batch_size: int = 100, status: str = STATUS_PENDING, media_types: Optional[Sequence[str]] = None) -> List[QueueEntry]:
    """
    Get next batch of items to process.

    Args:
        batch_size: Number of items to fetch
        status: Status filter ('pending', 'processing', etc.)
        media_types: Optional list/tuple of media types to limit results

    Returns:
        List of QueueEntry dataclasses
    """
    with get_db(DB_PATH) as (conn, cursor):
        query = '''
            SELECT * FROM art_queue
            WHERE status = ?
        '''
        params: List[Any] = [status]

        if media_types:
            placeholders = _build_placeholders(len(media_types))
            query += f' AND media_type IN ({placeholders})'
            params.extend(media_types)

        query += ' ORDER BY priority ASC, id ASC LIMIT ?'
        params.append(batch_size)

        cursor.execute(query, params)

        return [_row_to_queue_entry(row) for row in cursor.fetchall()]


def get_art_items_for_queue(queue_id: int) -> List[ArtItemEntry]:
    """Get all art items for a queue entry."""
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('''
            SELECT * FROM art_items
            WHERE queue_id = ?
        ''', (queue_id,))

        return [_row_to_art_item(row) for row in cursor.fetchall()]


def get_art_items_for_queue_batch(queue_ids: List[int]) -> Dict[int, List[ArtItemEntry]]:
    """
    Get art items for multiple queue entries in a single query.

    Args:
        queue_ids: List of queue entry IDs

    Returns:
        Dictionary mapping queue_id to list of ArtItemEntry dataclasses
    """
    if not queue_ids:
        return {}

    with get_db(DB_PATH) as (conn, cursor):
        placeholders = _build_placeholders(len(queue_ids))
        cursor.execute(f'''
            SELECT * FROM art_items
            WHERE queue_id IN ({placeholders})
        ''', queue_ids)

        rows = cursor.fetchall()

        result: Dict[int, List[ArtItemEntry]] = {qid: [] for qid in queue_ids}
        for row in rows:
            queue_id = row['queue_id']
            if queue_id in result:
                result[queue_id].append(_row_to_art_item(row))

        return result


def update_queue_status(queue_id: int, status: str) -> None:
    """Update queue item status."""
    with get_db(DB_PATH) as (conn, cursor):
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE art_queue
            SET status = ?, date_processed = ?
            WHERE id = ?
        ''', (status, now, queue_id))


def update_art_item(art_item_id: int, selected_url: str, auto_applied: bool = False) -> None:
    """Update art item with selected URL."""
    with get_db(DB_PATH) as (conn, cursor):
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE art_items
            SET selected_url = ?, auto_applied = ?, status = ?, requires_manual = 0, date_processed = ?
            WHERE id = ?
        ''', (selected_url, int(auto_applied), STATUS_COMPLETED, now, art_item_id))


def update_art_item_status(art_item_id: int, status: str) -> None:
    """Update art item status without changing selected URL."""
    with get_db(DB_PATH) as (conn, cursor):
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE art_items
            SET status = ?, date_processed = COALESCE(date_processed, ?)
            WHERE id = ?
        ''', (status, now, art_item_id))


def get_queue_stats(media_types: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """
    Get queue statistics.

    Returns:
        Dict mapping status -> count (e.g., {'pending': 10, 'completed': 5})
    """
    with get_db(DB_PATH) as (conn, cursor):
        stats = {}

        query = '''
            SELECT status, COUNT(*) as count
            FROM art_queue
        '''
        params: List[Any] = []

        if media_types:
            placeholders = _build_placeholders(len(media_types))
            query += f' WHERE media_type IN ({placeholders})'
            params.extend(media_types)

        query += ' GROUP BY status'

        cursor.execute(query, params)
        for row in cursor.fetchall():
            stats[row['status']] = row['count']

    return stats


def get_queue_breakdown_by_media() -> Dict[str, Dict[str, int]]:
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
            SELECT COUNT(*) as count FROM art_queue WHERE status = ?
        ''', (STATUS_PENDING,))

        row = cursor.fetchone()
        return row['count'] > 0 if row else False


def get_pending_media_counts(status: str = STATUS_PENDING) -> Dict[str, int]:
    """
    Return counts of items grouped by media type.

    Returns:
        Dict mapping media_type -> count (e.g., {'movie': 10, 'tvshow': 5})
    """
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
            WHERE ai.status = ?
              AND ai.review_mode = ?
              AND q.status = ?
        '''
        params: List[Any] = [STATUS_PENDING, ARTITEM_REVIEW_MISSING, STATUS_PENDING]

        if media_types:
            placeholders = _build_placeholders(len(media_types))
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
            placeholders = _build_placeholders(len(media_types))
            query += f' AND media_type IN ({placeholders})'
            params.extend(media_types)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row['count']) if row else 0


def prune_inactive_queue_items(statuses: Optional[Sequence[str]] = None) -> int:
    """Remove queue items in a terminal state that have no pending art entries."""
    active_statuses = tuple(statuses if statuses is not None else (STATUS_COMPLETED, STATUS_SKIPPED, STATUS_CANCELLED, STATUS_ERROR))
    if not active_statuses:
        return 0

    placeholders = _build_placeholders(len(active_statuses))

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
        log("Database", f"Pruned {removed} inactive queue items")
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
            SET status = ?,
                date_processed = NULL
            WHERE status != ?
              AND id IN (
                  SELECT DISTINCT queue_id
                  FROM art_items
                  WHERE status = ?
              )
        '''
        params: List[Any] = [STATUS_PENDING, STATUS_PENDING, STATUS_PENDING]

        if media_types:
            placeholders = _build_placeholders(len(media_types))
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
            WHERE status IN (?, ?, ?)
            AND date_processed IS NOT NULL
            AND date_processed < ?
        ''', (STATUS_COMPLETED, STATUS_SKIPPED, STATUS_ERROR, cutoff_str))

        deleted = cursor.rowcount

    if deleted > 0:
        log("Database", f"Cleaned up {deleted} old queue items")
        vacuum_database()

    return deleted
