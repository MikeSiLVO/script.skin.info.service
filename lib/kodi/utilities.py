"""Utility functions for properties, date formatting, and language handling.

The cached property helpers (`set_prop`, `batch_set_props`, `clear_prop`, `clear_group`)
target the home window (`xbmcgui.Window(10000)`) only; they back the service-layer's
high-frequency writes. Skin-action handlers that need to target arbitrary window IDs
should use `xbmc.executebuiltin('SetProperty/ClearProperty')` directly, except where a
property name is also written by the service (route home writes through these helpers
in that case to avoid cache desync).
"""
from __future__ import annotations

import threading
import xbmc
import xbmcgui
from typing import Any, Dict, Optional, List
from datetime import datetime
from collections import OrderedDict

from lib.kodi.settings import KodiSettings
from lib.kodi.client import log
HOME = xbmcgui.Window(10000)

MEDIA_TYPE_LABELS = {
    'movie': 'Movies',
    'tvshow': 'TV Shows',
    'episode': 'Episodes',
    'season': 'Seasons',
    'set': 'Movie Sets',
    'musicvideo': 'Music Videos',
    'artist': 'Artists',
    'album': 'Albums',
}

VALID_MEDIA_TYPES = frozenset(MEDIA_TYPE_LABELS.keys())


def validate_media_type(media_type: str) -> bool:
    """Validate that media_type is a known type."""
    return media_type in VALID_MEDIA_TYPES


def validate_dbid(dbid: Any) -> bool:
    """Validate that dbid is a positive integer."""
    try:
        return int(dbid) > 0
    except (ValueError, TypeError):
        return False


def resolve_infolabel(value: str) -> str:
    """Resolve a single `$INFO[...]` or `$VAR[...]` wrapped string via Kodi. Pass-through otherwise."""
    if value and value.startswith('$'):
        return xbmc.getInfoLabel(value)
    return value


def parse_pipe_list(value: str, separator: str = '|') -> list:
    """Split a separator-delimited string into a stripped, non-empty list."""
    if not value:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]


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

# Kodi convention for joining multi-value strings (genres, directors, cast, etc.).
MULTI_VALUE_SEP = " / "


def normalize_language_tag(value: Optional[str]) -> str:
    """Normalize language code to lowercase ISO 639-1.

    Placeholder codes (`00`, `null`, `xx`, etc.) become empty. Country codes that
    match a language are remapped (`cz` -> `cs`).
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
    """Set a home-window property, skipping the write if the cached value is unchanged."""
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
    """Read a home-window property value (empty string if unset)."""
    return HOME.getProperty(key)


def batch_set_props(props: Dict[str, Optional[str]]) -> None:
    """Set many home-window properties, skipping writes where the cached value is unchanged."""
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
    """Clear a single home-window property."""
    with _CACHE_LOCK:
        _PREV_PROPS.pop(key, None)
    HOME.clearProperty(key)


def clear_group(prefix: str) -> None:
    """Clear all tracked home-window properties whose key starts with `prefix`."""
    with _CACHE_LOCK:
        keys_to_clear = [k for k in _PREV_PROPS.keys() if k.startswith(prefix)]
        for k in keys_to_clear:
            _PREV_PROPS.pop(k, None)

    for k in keys_to_clear:
        HOME.clearProperty(k)


def extract_cast_names(cast_list) -> List[str]:
    """Pull just the `name` fields out of a Kodi cast list."""
    if not cast_list:
        return []
    return [str(c.get("name")) for c in cast_list if isinstance(c, dict) and c.get("name")]


def extract_media_ids(item: dict) -> Dict[str, Optional[str]]:
    """Return `{tmdb, imdb, tvdb, trakt}` IDs from a Kodi item, normalizing to string or None.

    Kodi's TMDB scraper writes the TMDB id into `imdbnumber`, so only the
    `uniqueid` dict is trusted. Callers that need an IMDb id when one isn't present
    should fall back to `lib.rating.ids.get_imdb_id_from_tmdb`.
    """
    uniqueid = item.get("uniqueid", {})

    tmdb_id = uniqueid.get("tmdb") or uniqueid.get("themoviedb")
    imdb_id = uniqueid.get("imdb")
    tvdb_id = uniqueid.get("tvdb")
    trakt_id = uniqueid.get("trakt")

    return {
        "tmdb": str(tmdb_id) if tmdb_id else None,
        "imdb": str(imdb_id) if imdb_id else None,
        "tvdb": str(tvdb_id) if tvdb_id else None,
        "trakt": str(trakt_id) if trakt_id else None,
    }


def format_date(date_str: str, include_time: bool = False) -> str:
    """Reformat an ISO date/datetime into Kodi's region-configured format."""
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


def is_kodi_piers_or_later() -> bool:
    """True if running on Kodi v22 (Piers, build 21.90+) or newer."""
    raw = xbmc.getInfoLabel("System.BuildVersionCode") or "0.0.0"
    parts = raw.split(".")
    try:
        version = tuple(int(p) for p in parts[:3])
    except ValueError:
        return False
    return version >= (21, 90, 0)


def wait_for_kodi_ready(monitor: xbmc.Monitor, initial_wait: float = 0.5,
                        check_interval: float = 0.5) -> bool:
    """Poll `JSONRPC.Ping` until Kodi responds. Returns False if the monitor aborts first."""
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
