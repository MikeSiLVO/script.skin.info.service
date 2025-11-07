"""Utility functions for properties, date formatting, and language handling."""
from __future__ import annotations

import threading
import xbmc
import xbmcaddon
import xbmcgui
from typing import Dict, Optional, List
from datetime import datetime
from collections import OrderedDict

ADDON = xbmcaddon.Addon(id="script.skin.info.service")
HOME = xbmcgui.Window(10000)
# Thread safety: Use RLock for reentrant locking (allows same thread to acquire multiple times)
_CACHE_LOCK = threading.RLock()

# LRU cache for property values with max size cap to prevent unbounded growth
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
    """
    normalized = (value or '').strip().lower()

    if normalized in ('00', 'null', 'none', 'xx', 'n/a'):
        return ''

    return normalized


def get_preferred_language_code() -> str:
    """Return the configured preferred language code."""
    try:
        addon = ADDON
    except Exception:
        return DEFAULT_LANGUAGE

    value = normalize_language_tag(addon.getSetting('preferred_language'))

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

    with _CACHE_LOCK:
        existing = _PREV_PROPS.get(key)
        if existing is not None:
            _PREV_PROPS.move_to_end(key)
        if existing != sval:
            HOME.setProperty(key, sval)
            _PREV_PROPS[key] = sval
            _PREV_PROPS.move_to_end(key)
            _enforce_props_size_limit()


def batch_set_props(props: Dict[str, Optional[str]]) -> None:
    """Set multiple properties in batch with thread safety.

    Args:
        props: Dictionary of key-value pairs to set
    """
    with _CACHE_LOCK:
        for key, val in props.items():
            sval = "" if val is None else str(val)
            existing = _PREV_PROPS.get(key)
            if existing is not None:
                _PREV_PROPS.move_to_end(key)
            if existing != sval:
                HOME.setProperty(key, sval)
                _PREV_PROPS[key] = sval
                _PREV_PROPS.move_to_end(key)
        _enforce_props_size_limit()


def clear_prop(key: str) -> None:
    """Clear a single property with thread safety.

    Args:
        key: The property key to clear
    """
    with _CACHE_LOCK:
        if _PREV_PROPS.pop(key, None) is None:
            return
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

        # Cache region formats for performance (they don't change during runtime)
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
        xbmc.log(f"SkinInfo: Unexpected error formatting date '{date_str}': {str(e)}", xbmc.LOGERROR)
        return date_str
