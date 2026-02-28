"""API usage tracking and provider response caching for ratings."""
from __future__ import annotations

import json
import zlib
from typing import Optional, Tuple

from lib.data.database._infrastructure import get_db


def _compress_data(data: dict) -> bytes:
    json_str = json.dumps(data, separators=(',', ':'))
    return zlib.compress(json_str.encode('utf-8'), level=6)


def _decompress_data(data: bytes) -> dict:
    json_str = zlib.decompress(data).decode('utf-8')
    return json.loads(json_str)


def increment_api_usage(provider: str, api_key_hash: str, today: str) -> Tuple[int, bool]:
    with get_db() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO ratings_api_usage (provider, api_key_hash, date, request_count, limit_hit)
            VALUES (?, ?, ?, 1, 0)
            ON CONFLICT(provider, api_key_hash, date)
            DO UPDATE SET request_count = request_count + 1
            """,
            (provider, api_key_hash, today)
        )

        cursor.execute(
            "SELECT request_count, limit_hit FROM ratings_api_usage WHERE provider = ? AND api_key_hash = ? AND date = ?",
            (provider, api_key_hash, today)
        )
        row = cursor.fetchone()
        if row:
            return row["request_count"], bool(row["limit_hit"])

    return 1, False


def mark_api_limit_hit(provider: str, api_key_hash: str, today: str) -> None:
    with get_db() as (_, cursor):
        cursor.execute(
            """
            UPDATE ratings_api_usage
            SET limit_hit = 1
            WHERE provider = ? AND api_key_hash = ? AND date = ?
            """,
            (provider, api_key_hash, today)
        )


def get_provider_cache(provider: str, media_id: str, cutoff_iso: str) -> Optional[dict]:
    with get_db() as (_, cursor):
        cursor.execute(
            "SELECT data FROM provider_cache WHERE provider = ? AND media_id = ? AND cached_at > ?",
            (provider, media_id, cutoff_iso)
        )
        row = cursor.fetchone()
        if row:
            return _decompress_data(row["data"])
    return None


def save_provider_cache(provider: str, media_id: str, data: dict, release_date: Optional[str] = None) -> None:
    with get_db() as (_, cursor):
        cursor.execute(
            """
            INSERT OR REPLACE INTO provider_cache (provider, media_id, data, release_date, cached_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (provider, media_id, _compress_data(data), release_date)
        )
