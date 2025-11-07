"""API usage tracking for rate limiting and daily limits."""
from __future__ import annotations

from datetime import date
from typing import Tuple, Sequence
import xbmcgui

from resources.lib.database._infrastructure import get_db
from resources.lib.kodi import _get_api_key


_session_skip_providers = set()
_session_warned_providers = set()


def get_api_key_hash(provider: str) -> str:
    """
    Get SHA256 hash of API key for tracking.

    Args:
        provider: Provider name ("tmdb", "mdblist", "omdb", "trakt")

    Returns:
        First 16 characters of SHA256 hash
    """
    import hashlib

    key_map = {
        "tmdb": "tmdb_api_key",
        "mdblist": "mdblist_api_key",
        "omdb": "omdb_api_key",
        "trakt": "trakt_access_token"
    }

    key_id = key_map.get(provider)
    if not key_id:
        return ""

    api_key = _get_api_key(key_id)
    if not api_key:
        return ""

    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def increment_usage(provider: str) -> Tuple[int, bool]:
    """
    Increment usage count for provider and return current stats.

    Args:
        provider: Provider name

    Returns:
        Tuple of (current_count, limit_hit_before)
    """
    api_key_hash = get_api_key_hash(provider)
    today = date.today().isoformat()

    with get_db() as (conn, cursor):
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


def mark_limit_hit(provider: str) -> None:
    """
    Mark that provider's daily limit was hit.

    Args:
        provider: Provider name
    """
    api_key_hash = get_api_key_hash(provider)
    today = date.today().isoformat()

    with get_db() as (conn, cursor):
        cursor.execute(
            """
            UPDATE ratings_api_usage
            SET limit_hit = 1
            WHERE provider = ? AND api_key_hash = ? AND date = ?
            """,
            (provider, api_key_hash, today)
        )


def handle_rate_limit_error(provider: str, current: int, total: int) -> str:
    """
    Show modal dialog when rate limit is hit and get user choice.

    Args:
        provider: Provider name
        current: Current item number
        total: Total items

    Returns:
        User choice: "cancel_batch", "cancel_all", or "skip"
    """
    mark_limit_hit(provider)

    dialog = xbmcgui.Dialog()
    choices: Sequence[str] = [
        "Retry Tomorrow",
        "Stop All Updates",
        f"Continue Without {provider.upper()}"
    ]

    choice = dialog.select(f"{provider.upper()} - Rate Limit", list(choices))

    if choice == 0:
        return "cancel_batch"
    elif choice == 1:
        return "cancel_all"
    elif choice == 2:
        _session_skip_providers.add(provider)
        return "skip"

    return "cancel_batch"


def is_provider_skipped(provider: str) -> bool:
    """
    Check if provider is skipped for this session.

    Args:
        provider: Provider name

    Returns:
        True if provider should be skipped
    """
    return provider in _session_skip_providers


def reset_session_skip() -> None:
    """Clear session skip flags."""
    _session_skip_providers.clear()
    _session_warned_providers.clear()
