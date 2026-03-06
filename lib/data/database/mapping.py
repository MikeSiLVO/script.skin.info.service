"""Cross-provider ID mapping table for instant ID lookups."""
from __future__ import annotations

from typing import Dict, Optional

from lib.data.database._infrastructure import get_db


def save_id_mapping(
    tmdb_id: str,
    media_type: str,
    imdb_id: Optional[str] = None,
    tvdb_id: Optional[str] = None,
) -> None:
    """Store or update an ID mapping from TMDB data."""
    if not tmdb_id or not media_type:
        return
    with get_db() as cursor:
        cursor.execute(
            """INSERT INTO id_mappings (tmdb_id, media_type, imdb_id, tvdb_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tmdb_id, media_type) DO UPDATE SET
                   imdb_id = COALESCE(excluded.imdb_id, imdb_id),
                   tvdb_id = COALESCE(excluded.tvdb_id, tvdb_id),
                   updated_at = CURRENT_TIMESTAMP""",
            (tmdb_id, media_type, imdb_id or None, tvdb_id or None),
        )


def get_imdb_id(tmdb_id: str, media_type: str) -> Optional[str]:
    """Look up imdb_id from tmdb_id."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT imdb_id FROM id_mappings WHERE tmdb_id = ? AND media_type = ?",
            (tmdb_id, media_type),
        )
        row = cursor.fetchone()
        return row["imdb_id"] if row and row["imdb_id"] else None


def get_imdb_ids_batch(tmdb_ids: set, media_type: str) -> Dict[str, str]:
    """Look up imdb_ids for multiple tmdb_ids in one query."""
    if not tmdb_ids:
        return {}
    with get_db() as cursor:
        placeholders = ','.join('?' * len(tmdb_ids))
        params = list(tmdb_ids) + [media_type]
        cursor.execute(
            f"SELECT tmdb_id, imdb_id FROM id_mappings WHERE tmdb_id IN ({placeholders}) AND media_type = ?",
            params,
        )
        return {row["tmdb_id"]: row["imdb_id"] for row in cursor.fetchall() if row["imdb_id"]}


def get_tmdb_id_by_imdb(imdb_id: str, media_type: str) -> Optional[str]:
    """Look up tmdb_id from imdb_id."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT tmdb_id FROM id_mappings WHERE imdb_id = ? AND media_type = ?",
            (imdb_id, media_type),
        )
        row = cursor.fetchone()
        return row["tmdb_id"] if row else None


def get_tmdb_id_by_tvdb(tvdb_id: str, media_type: str) -> Optional[str]:
    """Look up tmdb_id from tvdb_id."""
    with get_db() as cursor:
        cursor.execute(
            "SELECT tmdb_id FROM id_mappings WHERE tvdb_id = ? AND media_type = ?",
            (tvdb_id, media_type),
        )
        row = cursor.fetchone()
        return row["tmdb_id"] if row else None
