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
    with get_db() as cursor:
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
    with get_db() as cursor:
        cursor.execute(
            """
            UPDATE ratings_api_usage
            SET limit_hit = 1
            WHERE provider = ? AND api_key_hash = ? AND date = ?
            """,
            (provider, api_key_hash, today)
        )


def get_provider_cache(provider: str, media_id: str) -> Optional[dict]:
    """Get cached provider data if not expired based on smart TTL."""
    from datetime import datetime, timedelta
    from lib.data.database.cache import get_cache_ttl_hours

    with get_db() as cursor:
        cursor.execute(
            "SELECT data, release_date, cached_at FROM provider_cache WHERE provider = ? AND media_id = ?",
            (provider, media_id)
        )
        row = cursor.fetchone()
        if not row:
            return None

        hints = _get_provider_ttl_hints(media_id)
        release_date = row["release_date"]
        if not release_date and hints:
            release_date = hints.pop("_release_date", None)
        ttl_hours = get_cache_ttl_hours(release_date, hints or None)
        cached_at = datetime.fromisoformat(row["cached_at"])
        if datetime.now() - cached_at > timedelta(hours=ttl_hours):
            return None
        return _decompress_data(row["data"])


def _get_provider_ttl_hints(media_id: str) -> Optional[dict]:
    """Try to derive TTL hints from the mapping + metadata cache."""
    if not media_id or not media_id.startswith("tt"):
        return None

    from lib.data.database.mapping import get_tmdb_id_by_imdb
    for media_type in ("movie", "tvshow"):
        tmdb_id = get_tmdb_id_by_imdb(media_id, media_type)
        if tmdb_id:
            from lib.data.database.cache import get_cached_metadata
            meta = get_cached_metadata(media_type, tmdb_id)
            if not meta:
                return None
            hints: dict = {}
            status = meta.get("status") or ""
            if status:
                hints["status"] = status
            release = meta.get("release_date") or meta.get("first_air_date")
            if release:
                hints["_release_date"] = release
            return hints
    return None


def save_provider_cache(provider: str, media_id: str, data: dict, release_date: Optional[str] = None) -> None:
    with get_db() as cursor:
        cursor.execute(
            """
            INSERT OR REPLACE INTO provider_cache (provider, media_id, data, release_date, cached_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (provider, media_id, _compress_data(data), release_date)
        )
