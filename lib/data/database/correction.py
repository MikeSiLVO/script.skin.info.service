"""ID correction cache for invalid TMDB/IMDB mappings."""
from __future__ import annotations

from typing import Optional

from lib.data.database._infrastructure import get_db


def get_corrected_tmdb_id(imdb_id: str) -> Optional[int]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT tmdb_id FROM id_corrections WHERE imdb_id = ?",
            (imdb_id,)
        )
        row = cursor.fetchone()
        return row["tmdb_id"] if row else None


def save_corrected_tmdb_id(imdb_id: str, tmdb_id: int, media_type: str) -> None:
    with get_db() as (_, cursor):
        cursor.execute(
            """INSERT OR REPLACE INTO id_corrections (imdb_id, tmdb_id, media_type)
               VALUES (?, ?, ?)""",
            (imdb_id, tmdb_id, media_type)
        )
