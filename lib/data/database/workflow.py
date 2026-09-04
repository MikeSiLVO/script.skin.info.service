"""Scan sessions, operation history, and IMDb sync/resume bookkeeping."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from typing import Optional, Sequence, List, Dict, Set

from lib.data.database._infrastructure import get_db, DB_PATH


def _pack_types(values: Sequence[str]) -> str:
    """Type lists are compared as whole sets, so store them in one canonical order."""
    return ",".join(sorted({v for v in values if v}))


def _unpack_types(packed: Optional[str]) -> List[str]:
    return packed.split(",") if packed else []


def get_session_media_types(session_id: int) -> List[str]:
    """Media types a scan session covers."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT media_types FROM scan_session WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        return _unpack_types(row['media_types'] if row else None)


def get_session_art_types(session_id: int) -> List[str]:
    """Art types a scan session covers."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT art_types FROM scan_session WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        return _unpack_types(row['art_types'] if row else None)


_SESSIONS_KEPT = 2


def create_scan_session(scan_type: str, media_types: List[str], art_types: List[str]) -> int:
    """Create a scan session and return its ID, dropping all but the newest few for its scope."""
    packed_media = _pack_types(media_types)
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'INSERT INTO scan_session (scan_type, started, media_types, art_types) '
            'VALUES (?, ?, ?, ?)',
            (scan_type, int(time.time()), packed_media, _pack_types(art_types)))
        session_id = cursor.lastrowid
        assert session_id is not None, "Failed to create scan session"

        cursor.execute(
            'DELETE FROM scan_session WHERE scan_type = ? AND media_types = ? AND id NOT IN ('
            '  SELECT id FROM scan_session WHERE scan_type = ? AND media_types = ? '
            '  ORDER BY id DESC LIMIT ?)',
            (scan_type, packed_media, scan_type, packed_media, _SESSIONS_KEPT))
        return session_id


def update_session_stats(session_id: int, stats: dict) -> None:
    """Store JSON-encoded `stats` against a session."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('UPDATE scan_session SET stats = ? WHERE id = ?',
                       (json.dumps(stats), session_id))


def complete_session(session_id: int) -> None:
    """Mark session as completed."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            "UPDATE scan_session SET status = 'completed', completed = ? WHERE id = ?",
            (int(time.time()), session_id))


def cancel_session(session_id: int) -> None:
    """Mark session as cancelled."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            "UPDATE scan_session SET status = 'cancelled', completed = ? WHERE id = ?",
            (int(time.time()), session_id))


def get_session(session_id: int) -> Optional[sqlite3.Row]:
    """Return a scan session row by ID, or None."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT * FROM scan_session WHERE id = ?', (session_id,))
        return cursor.fetchone()


def get_last_manual_review_session(
    media_types: Optional[Sequence[str]] = None,
) -> Optional[sqlite3.Row]:
    """Return newest `manual_review` session; if `media_types` given, match its exact set."""
    with get_db(DB_PATH) as cursor:
        if media_types is None:
            cursor.execute(
                "SELECT * FROM scan_session WHERE scan_type = 'manual_review' "
                "ORDER BY id DESC LIMIT 1")
        else:
            cursor.execute(
                "SELECT * FROM scan_session WHERE scan_type = 'manual_review' "
                "AND media_types = ? ORDER BY id DESC LIMIT 1",
                (_pack_types(media_types),))
        return cursor.fetchone()


def save_operation_stats(operation: str, stats: dict, scope: Optional[str] = None) -> None:
    """Record an art tool run, replacing that operation's previous row."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'INSERT INTO operation_history (operation, timestamp, completed, scope, stats) '
            'VALUES (?, ?, ?, ?, ?) '
            'ON CONFLICT (operation) DO UPDATE SET timestamp = excluded.timestamp, '
            'completed = excluded.completed, scope = excluded.scope, stats = excluded.stats',
            (operation, int(time.time()), 0 if stats.get('cancelled') else 1,
             scope, json.dumps(stats)))


def get_last_operation_stats(operation: str) -> Optional[dict]:
    """Return the stored run for an operation as a dict, or None."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'SELECT timestamp, completed, scope, stats FROM operation_history '
            'WHERE operation = ?', (operation,))
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'operation': operation,
            'timestamp': datetime.fromtimestamp(row['timestamp']).isoformat(),
            'stats': json.loads(row['stats']),
            'completed': bool(row['completed']),
            'scope': row['scope'],
        }


def get_imdb_update_progress(media_type: str) -> Optional[Dict]:
    """Return the dbids already processed against a dataset, or None."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'SELECT dataset_date, dbid FROM imdb_run_progress WHERE media_type = ?',
            (media_type,))
        rows = cursor.fetchall()
    if not rows:
        return None
    return {
        'dataset_date': rows[0]['dataset_date'],
        'processed_ids': {row['dbid'] for row in rows},
    }


def save_imdb_update_progress(media_type: str, dataset_date: str,
                              processed_ids: Set[int]) -> None:
    """Save resumable IMDb update progress."""
    with get_db(DB_PATH) as cursor:
        cursor.execute(
            'DELETE FROM imdb_run_progress WHERE media_type = ? AND dataset_date != ?',
            (media_type, dataset_date))
        cursor.executemany(
            'INSERT OR IGNORE INTO imdb_run_progress (media_type, dataset_date, dbid) '
            'VALUES (?, ?, ?)',
            [(media_type, dataset_date, dbid) for dbid in processed_ids])


def clear_imdb_update_progress(media_type: str) -> None:
    """Clear saved IMDb update progress for a media type (called when the update completes)."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('DELETE FROM imdb_run_progress WHERE media_type = ?', (media_type,))


_UPSERT_SYNC = (
    'INSERT INTO imdb_sync (media_type, dbid, imdb_id, rating, votes, synced_at) '
    'VALUES (?, ?, ?, ?, ?, ?) '
    'ON CONFLICT (media_type, dbid) DO UPDATE SET imdb_id = excluded.imdb_id, '
    'rating = excluded.rating, votes = excluded.votes, synced_at = excluded.synced_at'
)


def update_synced_ratings(media_type: str, dbid: int,
                          ratings: Dict[str, Dict[str, float]],
                          external_ids: Optional[Dict[str, str]] = None) -> None:
    """Record the IMDb rating written to Kodi; other sources are not drift-tracked."""
    data = (ratings or {}).get('imdb') or {}
    imdb_id = (external_ids or {}).get('imdb')
    rating = data.get('rating')
    if rating is None or not imdb_id:
        return
    with get_db(DB_PATH) as cursor:
        cursor.execute(_UPSERT_SYNC, (media_type, dbid, imdb_id, rating,
                                      int(data.get('votes', 0)), int(time.time())))


def update_synced_ratings_batch(items: List[tuple]) -> None:
    """Bulk-upsert sync rows, one per `(media_type, dbid, imdb_id, rating, votes)`."""
    if not items:
        return
    now = int(time.time())
    with get_db(DB_PATH) as cursor:
        cursor.executemany(
            _UPSERT_SYNC,
            [(mt, dbid, imdb_id, rating, votes, now)
             for mt, dbid, imdb_id, rating, votes in items if imdb_id])


def get_imdb_changed_items(media_type: Optional[str] = None) -> List[Dict]:
    """Synced items whose IMDb rating or vote count has drifted far enough to rewrite."""
    query = '''
        SELECT s.media_type, s.dbid, s.imdb_id,
               r.rating AS new_rating, r.votes AS new_votes,
               s.rating AS old_rating, s.votes AS old_votes
        FROM imdb_sync s
        JOIN imdb_rating r ON s.imdb_id = r.imdb_id
        WHERE ABS(s.rating - r.rating) >= 0.05
           OR (s.votes = 0 AND r.votes > 0)
           OR (s.votes > 0 AND s.votes < 100 AND r.votes != s.votes)
           OR (s.votes >= 100 AND s.votes < 1000
               AND ABS(r.votes - s.votes) * 1.0 / s.votes > 0.1)
           OR (s.votes >= 1000 AND ABS(r.votes - s.votes) * 1.0 / s.votes > 0.05)
    '''
    with get_db(DB_PATH) as cursor:
        if media_type:
            cursor.execute(f'SELECT * FROM ({query}) WHERE media_type = ?', (media_type,))
        else:
            cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def has_synced_ratings() -> bool:
    """True when any sync row exists; a probe, not a count."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT 1 FROM imdb_sync LIMIT 1')
        return cursor.fetchone() is not None


def get_synced_dbids(media_type: str) -> Set[int]:
    """Return the set of DBIDs that have an IMDb sync entry for the given media type."""
    with get_db(DB_PATH) as cursor:
        cursor.execute('SELECT dbid FROM imdb_sync WHERE media_type = ?', (media_type,))
        return {row['dbid'] for row in cursor.fetchall()}


def clear_synced_ratings(media_type: Optional[str] = None, dbid: Optional[int] = None) -> None:
    """Clear sync tracking. With no args, clears all; `dbid` requires `media_type`."""
    with get_db(DB_PATH) as cursor:
        if media_type and dbid:
            cursor.execute('DELETE FROM imdb_sync WHERE media_type = ? AND dbid = ?',
                           (media_type, dbid))
        elif media_type:
            cursor.execute('DELETE FROM imdb_sync WHERE media_type = ?', (media_type,))
        else:
            cursor.execute('DELETE FROM imdb_sync')
