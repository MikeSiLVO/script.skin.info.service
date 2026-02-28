"""IMDb dataset database operations for ratings, episodes, and metadata."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Generator, Callable

from lib.data.database._infrastructure import get_db


# --- Rating lookups ---

def get_rating(imdb_id: str) -> Optional[Dict[str, float | int]]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT rating, votes FROM imdb_ratings WHERE imdb_id = ?",
            (imdb_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"rating": row["rating"], "votes": row["votes"]}
    return None


def get_rating_with_cursor(imdb_id: str, cursor: sqlite3.Cursor) -> Optional[Dict[str, float | int]]:
    cursor.execute(
        "SELECT rating, votes FROM imdb_ratings WHERE imdb_id = ?",
        (imdb_id,)
    )
    row = cursor.fetchone()
    if row:
        return {"rating": row["rating"], "votes": row["votes"]}
    return None


def get_ratings_batch(imdb_ids: List[str]) -> Dict[str, Dict[str, float | int]]:
    if not imdb_ids:
        return {}

    CHUNK_SIZE = 900
    results: Dict[str, Dict[str, float | int]] = {}
    with get_db() as (_, cursor):
        for start in range(0, len(imdb_ids), CHUNK_SIZE):
            chunk = imdb_ids[start:start + CHUNK_SIZE]
            placeholders = ",".join(["?" for _ in chunk])
            cursor.execute(
                f"SELECT imdb_id, rating, votes FROM imdb_ratings WHERE imdb_id IN ({placeholders})",
                chunk
            )
            for row in cursor.fetchall():
                results[row["imdb_id"]] = {"rating": row["rating"], "votes": row["votes"]}
    return results


# --- Episode lookups ---

def get_episode_imdb_id(show_imdb_id: str, season: int, episode: int) -> Optional[str]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT episode_id FROM imdb_episodes WHERE parent_id = ? AND season = ? AND episode = ?",
            (show_imdb_id, season, episode)
        )
        row = cursor.fetchone()
        return row["episode_id"] if row else None


def get_episode_imdb_id_with_cursor(
    show_imdb_id: str, season: int, episode: int, cursor: sqlite3.Cursor
) -> Optional[str]:
    cursor.execute(
        "SELECT episode_id FROM imdb_episodes WHERE parent_id = ? AND season = ? AND episode = ?",
        (show_imdb_id, season, episode)
    )
    row = cursor.fetchone()
    return row["episode_id"] if row else None


def get_episodes_for_show(show_imdb_id: str) -> Dict[Tuple[int, int], str]:
    result: Dict[Tuple[int, int], str] = {}
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT season, episode, episode_id FROM imdb_episodes WHERE parent_id = ?",
            (show_imdb_id,)
        )
        for row in cursor.fetchall():
            result[(row["season"], row["episode"])] = row["episode_id"]
    return result


@contextmanager
def bulk_episode_lookup() -> Generator[Callable[..., Optional[str]], None, None]:
    """Context manager yielding a lookup function with a shared connection."""
    with get_db() as (_, cursor):
        def lookup(show_imdb_id: str, season: int, episode: int) -> Optional[str]:
            cursor.execute(
                "SELECT episode_id FROM imdb_episodes WHERE parent_id = ? AND season = ? AND episode = ?",
                (show_imdb_id, season, episode)
            )
            row = cursor.fetchone()
            return row["episode_id"] if row else None
        yield lookup


# --- Dataset availability/stats ---

def is_dataset_available() -> bool:
    with get_db() as (_, cursor):
        cursor.execute("SELECT COUNT(*) as cnt FROM imdb_ratings")
        row = cursor.fetchone()
        return row["cnt"] > 0 if row else False


def get_dataset_stats() -> Dict[str, int | float | str | bool | None]:
    stats: Dict[str, int | float | str | bool | None] = {
        "entries": 0,
        "last_modified": None,
        "downloaded_at": None,
    }
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT last_modified, downloaded_at, entry_count FROM imdb_meta WHERE dataset = ?",
            ("ratings",)
        )
        row = cursor.fetchone()
        if row:
            stats["last_modified"] = row["last_modified"]
            stats["downloaded_at"] = row["downloaded_at"]
            stats["entries"] = row["entry_count"] or 0
    return stats


def is_episode_dataset_available() -> bool:
    with get_db() as (_, cursor):
        cursor.execute("SELECT COUNT(*) as cnt FROM imdb_episodes")
        row = cursor.fetchone()
        return row["cnt"] > 0 if row else False


def get_episode_dataset_stats() -> Dict[str, int | str | None]:
    stats: Dict[str, int | str | None] = {
        "entries": 0,
        "last_modified": None,
        "downloaded_at": None,
    }
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT last_modified, downloaded_at, entry_count FROM imdb_meta WHERE dataset = ?",
            ("episodes",)
        )
        row = cursor.fetchone()
        if row:
            stats["last_modified"] = row["last_modified"]
            stats["downloaded_at"] = row["downloaded_at"]
            stats["entries"] = row["entry_count"] or 0
    return stats


# --- Meta operations ---

def get_meta_last_modified(dataset: str) -> Optional[str]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT last_modified FROM imdb_meta WHERE dataset = ?",
            (dataset,)
        )
        row = cursor.fetchone()
        if row and row["last_modified"]:
            return row["last_modified"]
    return None


def save_meta(
    dataset: str,
    last_mod: str,
    entry_count: int = 0,
    library_episode_count: Optional[int] = None
) -> None:
    with get_db() as (_, cursor):
        if library_episode_count is not None:
            cursor.execute(
                """INSERT OR REPLACE INTO imdb_meta
                   (dataset, last_modified, downloaded_at, entry_count, library_episode_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (dataset, last_mod, datetime.now().isoformat(), entry_count, library_episode_count)
            )
        else:
            cursor.execute(
                """INSERT OR REPLACE INTO imdb_meta
                   (dataset, last_modified, downloaded_at, entry_count)
                   VALUES (?, ?, ?, ?)""",
                (dataset, last_mod, datetime.now().isoformat(), entry_count)
            )


def clear_meta(dataset: str) -> None:
    with get_db() as (_, cursor):
        cursor.execute("DELETE FROM imdb_meta WHERE dataset = ?", (dataset,))


def get_episode_meta() -> Tuple[Optional[str], int]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT last_modified, library_episode_count FROM imdb_meta WHERE dataset = ?",
            ("episodes",)
        )
        row = cursor.fetchone()
        if row:
            return row["last_modified"], row["library_episode_count"] or 0
        return None, 0


# --- Bulk import helpers (cursor-accepting, called from streaming import) ---

def import_ratings_begin(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("DROP TABLE IF EXISTS imdb_ratings")
    cursor.execute('''
        CREATE TABLE imdb_ratings (
            imdb_id TEXT PRIMARY KEY,
            rating REAL NOT NULL,
            votes INTEGER NOT NULL
        )
    ''')


def import_ratings_batch(cursor: sqlite3.Cursor, batch: List[Tuple[str, float, int]]) -> None:
    cursor.executemany(
        "INSERT INTO imdb_ratings (imdb_id, rating, votes) VALUES (?, ?, ?)",
        batch
    )


def import_episodes_begin(cursor: sqlite3.Cursor) -> None:
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("DROP TABLE IF EXISTS imdb_episodes")
    cursor.execute('''
        CREATE TABLE imdb_episodes (
            parent_id TEXT NOT NULL,
            season INTEGER NOT NULL,
            episode INTEGER NOT NULL,
            episode_id TEXT NOT NULL,
            PRIMARY KEY (parent_id, season, episode)
        )
    ''')


def import_episodes_batch(cursor: sqlite3.Cursor, batch: List[Tuple[str, int, int, str]]) -> None:
    cursor.executemany(
        "INSERT OR REPLACE INTO imdb_episodes (parent_id, season, episode, episode_id) VALUES (?, ?, ?, ?)",
        batch
    )


def import_episodes_finalize(cursor: sqlite3.Cursor) -> None:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imdb_episodes_parent ON imdb_episodes(parent_id)")
