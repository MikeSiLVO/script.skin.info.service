"""ID correction cache for invalid TMDB/IMDB mappings."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from lib.data.database._infrastructure import get_db

_SUCCESS_TTL_DAYS = 90
_FAILED_TTL_DAYS = 30


def get_corrected_tmdb_id(imdb_id: str) -> Optional[int]:
    with get_db() as cursor:
        cursor.execute(
            "SELECT tmdb_id, cached_at FROM id_corrections WHERE imdb_id = ?",
            (imdb_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        cached_at = datetime.fromisoformat(row["cached_at"])
        age = datetime.now() - cached_at
        ttl = _FAILED_TTL_DAYS if row["tmdb_id"] == 0 else _SUCCESS_TTL_DAYS
        if age > timedelta(days=ttl):
            cursor.execute("DELETE FROM id_corrections WHERE imdb_id = ?", (imdb_id,))
            return None
        return row["tmdb_id"]


def save_corrected_tmdb_id(imdb_id: str, tmdb_id: int, media_type: str) -> None:
    with get_db() as cursor:
        cursor.execute(
            """INSERT OR REPLACE INTO id_corrections (imdb_id, tmdb_id, media_type)
               VALUES (?, ?, ?)""",
            (imdb_id, tmdb_id, media_type)
        )
