"""API usage tracking for rate limiting and daily limits."""
from __future__ import annotations

from datetime import date
from typing import Tuple, Sequence
import xbmcgui

from lib.data.database.rating import increment_api_usage, mark_api_limit_hit
from lib.kodi.client import _get_api_key, ADDON


_session_skip_providers = set()


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
    return increment_api_usage(provider, api_key_hash, today)


def mark_limit_hit(provider: str) -> None:
    """
    Mark that provider's daily limit was hit.

    Args:
        provider: Provider name
    """
    api_key_hash = get_api_key_hash(provider)
    today = date.today().isoformat()
    mark_api_limit_hit(provider, api_key_hash, today)


def handle_rate_limit_error(provider: str, current: int, total: int) -> str:
    """
    Show modal dialog when rate limit is hit and get user choice.

    Args:
        provider: Provider name
        current: Current item number
        total: Total items

    Returns:
        User choice: "cancel_batch", "cancel_all", "skip", or "retry"
    """
    mark_limit_hit(provider)

    dialog = xbmcgui.Dialog()
    choices: Sequence[str] = [
        "Wait 60s and Retry",
        "Retry Tomorrow",
        "Stop All Updates",
        f"Continue Without {provider.upper()}"
    ]

    choice = dialog.select(f"{provider.upper()} - Rate Limit", list(choices))

    if choice == 0:
        # Wait 60 seconds then retry
        import xbmc
        monitor = xbmc.Monitor()
        progress = xbmcgui.DialogProgress()
        progress.create(ADDON.getLocalizedString(32313).format(provider.upper()), ADDON.getLocalizedString(32314))
        for i in range(60):
            if progress.iscanceled() or monitor.abortRequested():
                progress.close()
                return "cancel_batch"
            progress.update(int((i / 60) * 100), ADDON.getLocalizedString(32315).format(60 - i))
            monitor.waitForAbort(1)
        progress.close()
        return "retry"
    elif choice == 1:
        return "cancel_batch"
    elif choice == 2:
        return "cancel_all"
    elif choice == 3:
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
