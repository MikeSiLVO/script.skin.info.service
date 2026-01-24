"""Utility functions for properties, date formatting, and language handling."""
from __future__ import annotations

import threading
import xbmc
import xbmcgui
from typing import Dict, Optional, List
from datetime import datetime
from collections import OrderedDict

from lib.kodi.settings import KodiSettings
from lib.kodi.client import log
HOME = xbmcgui.Window(10000)


# Thread safety: Use RLock for reentrant locking (allows same thread to acquire multiple times)
_CACHE_LOCK = threading.RLock()

# LRU cache for property values to avoid redundant setProperty calls
_PREV_PROPS: OrderedDict[str, str] = OrderedDict()
_PREV_PROPS_MAX_SIZE = 500

_DATE_FORMAT_CACHE: Dict[str, str] = {}

LANGUAGE_OPTIONS: List[str] = [
    'en',      # English
    'es',      # Spanish
    'pt-br',   # Portuguese (Brazil)
    'pt',      # Portuguese (Portugal)
    'fr',      # French
    'de',      # German
    'zh-cn',   # Chinese (Simplified)
    'zh-tw',   # Chinese (Traditional)
    'it',      # Italian
    'pl',      # Polish
    'ru',      # Russian
    'nl',      # Dutch
    'sv',      # Swedish
    'ko',      # Korean
    'ja',      # Japanese
]
DEFAULT_LANGUAGE = 'en'


def normalize_language_tag(value: Optional[str]) -> str:
    """
    Return a lowercase ISO language tag or empty string.

    Treats invalid/placeholder codes like '00', 'null', 'xx' as empty string.
    Maps common incorrect country codes to correct ISO 639-1 language codes.
    """
    normalized = (value or '').strip().lower()

    if normalized in ('00', 'null', 'none', 'xx', 'n/a'):
        return ''

    country_to_language_map = {
        'cz': 'cs',
    }

    return country_to_language_map.get(normalized, normalized)


def get_preferred_language_code() -> str:
    """Return the configured preferred language code."""
    try:
        value = normalize_language_tag(KodiSettings.preferred_language())
    except Exception:
        return DEFAULT_LANGUAGE

    if value in LANGUAGE_OPTIONS:
        return value

    if value.isdigit():
        try:
            index = int(value)
            if 0 <= index < len(LANGUAGE_OPTIONS):
                return LANGUAGE_OPTIONS[index]
        except ValueError:
            pass

    return DEFAULT_LANGUAGE


def _enforce_props_size_limit() -> None:
    """Remove oldest entries from _PREV_PROPS when exceeding max size (LRU eviction).

    Note: This should be called while holding _CACHE_LOCK.
    """
    while len(_PREV_PROPS) > _PREV_PROPS_MAX_SIZE:
        _PREV_PROPS.popitem(last=False)


def set_prop(key: str, val: Optional[str]) -> None:
    """Set a property in the Kodi home window with caching and thread safety.

    Args:
        key: The property key
        val: The property value (None will be converted to empty string)
    """
    sval = "" if val is None else str(val)

    needs_update = False
    with _CACHE_LOCK:
        existing = _PREV_PROPS.get(key)
        if existing != sval:
            needs_update = True
        elif existing is not None:
            _PREV_PROPS.move_to_end(key)

    if needs_update:
        HOME.setProperty(key, sval)

        with _CACHE_LOCK:
            _PREV_PROPS[key] = sval
            _PREV_PROPS.move_to_end(key)
            _enforce_props_size_limit()


def get_prop(key: str) -> str:
    return HOME.getProperty(key)


def batch_set_props(props: Dict[str, Optional[str]]) -> None:
    """Set multiple properties in batch with thread safety.

    Args:
        props: Dictionary of key-value pairs to set
    """
    props_to_set = []
    with _CACHE_LOCK:
        for key, val in props.items():
            sval = "" if val is None else str(val)
            existing = _PREV_PROPS.get(key)
            if existing != sval:
                props_to_set.append((key, sval))
            elif existing is not None:
                _PREV_PROPS.move_to_end(key)

    for key, sval in props_to_set:
        HOME.setProperty(key, sval)

    if props_to_set:
        with _CACHE_LOCK:
            for key, sval in props_to_set:
                _PREV_PROPS[key] = sval
                _PREV_PROPS.move_to_end(key)
            _enforce_props_size_limit()


def clear_prop(key: str) -> None:
    """Clear a single property with thread safety.

    Args:
        key: The property key to clear
    """
    with _CACHE_LOCK:
        _PREV_PROPS.pop(key, None)
    HOME.clearProperty(key)


def clear_group(prefix: str) -> None:
    """Clear all properties with a given prefix with thread safety.

    Args:
        prefix: The prefix to match for clearing properties
    """
    with _CACHE_LOCK:
        keys_to_clear = [k for k in _PREV_PROPS.keys() if k.startswith(prefix)]
        for k in keys_to_clear:
            _PREV_PROPS.pop(k, None)

    for k in keys_to_clear:
        HOME.clearProperty(k)


def extract_cast_names(cast_list) -> List[str]:
    """Extract cast names from Kodi cast list structure.

    Args:
        cast_list: List of cast dict objects from Kodi JSON-RPC

    Returns:
        List of cast member names
    """
    if not cast_list:
        return []
    return [str(c.get("name")) for c in cast_list if isinstance(c, dict) and c.get("name")]


def extract_media_ids(item: dict) -> Dict[str, Optional[str]]:
    """Extract all external IDs from a Kodi library item.

    Handles the various places Kodi stores IDs and normalizes them.

    Args:
        item: Library item dict with 'uniqueid' and optionally 'imdbnumber' fields

    Returns:
        Dict with keys: tmdb, imdb, tvdb, trakt (values are str or None)
    """
    uniqueid = item.get("uniqueid", {})

    tmdb_id = uniqueid.get("tmdb") or uniqueid.get("themoviedb")
    imdb_id = item.get("imdbnumber") or uniqueid.get("imdb")
    tvdb_id = uniqueid.get("tvdb")
    trakt_id = uniqueid.get("trakt")

    return {
        "tmdb": str(tmdb_id) if tmdb_id else None,
        "imdb": str(imdb_id) if imdb_id else None,
        "tvdb": str(tvdb_id) if tvdb_id else None,
        "trakt": str(trakt_id) if trakt_id else None,
    }


def format_date(date_str: str, include_time: bool = False) -> str:
    """Format date string according to Kodi region settings.

    Args:
        date_str: ISO format date string (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
        include_time: If True, include time in the formatted output

    Returns:
        Formatted date string according to user's Kodi region settings
    """
    if not date_str:
        return ""

    try:
        if " " in date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")

        if include_time:
            with _CACHE_LOCK:
                if "datetime" not in _DATE_FORMAT_CACHE:
                    date_format = xbmc.getRegion("dateshort")
                    time_format = xbmc.getRegion("time")
                    _DATE_FORMAT_CACHE["datetime"] = f"{date_format} {time_format}"
                format_str = _DATE_FORMAT_CACHE["datetime"]
            return dt.strftime(format_str)
        else:
            with _CACHE_LOCK:
                if "date" not in _DATE_FORMAT_CACHE:
                    _DATE_FORMAT_CACHE["date"] = xbmc.getRegion("dateshort")
                format_str = _DATE_FORMAT_CACHE["date"]
            return dt.strftime(format_str)
    except (ValueError, TypeError):
        return date_str
    except Exception as e:
        log("General", f"Unexpected error formatting date '{date_str}': {str(e)}", xbmc.LOGERROR)
        return date_str


def wait_for_kodi_ready(
    monitor: xbmc.Monitor,
    initial_wait: float = 1.0,
    check_interval: float = 0.5,
) -> bool:
    """
    Wait for Kodi's JSON-RPC to be ready before starting service work.

    Args:
        monitor: xbmc.Monitor instance for abort checking
        initial_wait: Seconds to wait before first check
        check_interval: Seconds between subsequent checks

    Returns:
        True if ready, False if aborted
    """
    if monitor.waitForAbort(initial_wait):
        return False

    while not monitor.waitForAbort(check_interval):
        try:
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}')
            if "pong" in result.lower():
                return True
        except Exception:
            pass

    return False
