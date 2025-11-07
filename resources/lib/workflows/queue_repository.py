"""
High-level helpers for working with artwork review queue records.

These abstractions keep the database details in one place so the workflow
layer can operate on simple dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from resources.lib import database as db


@dataclass(frozen=True)
class ArtItemEntry:
    """Single art item queued for review or processing."""

    id: int
    queue_id: int
    art_type: str
    baseline_url: str
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


class ArtQueueRepository:
    """Typed convenience wrapper around art queue database helpers."""

    def get_queue_batch(
        self,
        *,
        limit: int = 50,
        status: str = 'pending',
        media_types: Optional[Sequence[str]] = None,
    ) -> list[QueueEntry]:
        rows = db.get_next_batch(batch_size=limit, status=status, media_types=media_types)
        return [self._row_to_queue_entry(row) for row in rows]

    def get_art_items(self, queue_id: int) -> list[ArtItemEntry]:
        rows = db.get_art_items_for_queue(queue_id)
        return [self._row_to_art_item(row) for row in rows]

    def get_art_items_batch(self, queue_ids: list[int]) -> dict[int, list[ArtItemEntry]]:
        """
        Get art items for multiple queue entries in a single query.

        Args:
            queue_ids: List of queue entry IDs

        Returns:
            Dictionary mapping queue_id to list of ArtItemEntry objects
        """
        rows_by_queue = db.get_art_items_for_queue_batch(queue_ids)
        return {
            queue_id: [self._row_to_art_item(row) for row in rows]
            for queue_id, rows in rows_by_queue.items()
        }

    def update_queue_status(self, queue_id: int, status: str) -> None:
        db.update_queue_status(queue_id, status)

    def mark_art_item_selected(self, art_item_id: int, url: str, *, auto_applied: bool = False) -> None:
        db.update_art_item(art_item_id, url, auto_applied=auto_applied)

    def set_art_item_status(self, art_item_id: int, status: str) -> None:
        db.update_art_item_status(art_item_id, status)

    def prune_inactive_queue(self, statuses: Optional[Sequence[str]] = None) -> int:
        return db.prune_inactive_queue_items(statuses)

    @staticmethod
    def _row_to_queue_entry(row) -> QueueEntry:
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

    @staticmethod
    def _row_to_art_item(row) -> ArtItemEntry:
        return ArtItemEntry(
            id=row['id'],
            queue_id=row['queue_id'],
            art_type=row['art_type'],
            baseline_url=row['baseline_url'] or row['current_url'] or '',
            selected_url=row['selected_url'],
            review_mode=row['review_mode'] or db.ARTITEM_REVIEW_MISSING,
            requires_manual=bool(row['requires_manual']),
            status=row['status'] or 'pending',
        )


__all__ = [
    'ArtQueueRepository',
    'QueueEntry',
    'ArtItemEntry',
]
