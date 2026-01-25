"""Shared constants and utility functions for artwork package."""
from __future__ import annotations

import json
from typing import Any

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
        dbid_int = int(dbid)
        return dbid_int > 0
    except (ValueError, TypeError):
        return False


REVIEW_SCOPE_OPTIONS = [
    ('movies', 'Movies'),
    ('tvshows', 'TV Shows'),
    ('music', 'Music'),
    ('all', 'All Types'),
]

REVIEW_SCOPE_LABELS = {scope: label for scope, label in REVIEW_SCOPE_OPTIONS}

REVIEW_MEDIA_FILTERS = {
    'movies': ['movie'],
    'tvshows': ['tvshow', 'episode'],
    'music': ['artist', 'album'],
}

REVIEW_SCAN_MAP = {
    'movies': 'movies',
    'tvshows': 'tvshows',
    'music': 'music',
    'all': 'all',
}

ACTION_RESUME = 'resume'
ACTION_MANUAL = 'manual'
ACTION_MANUAL_DOWNLOAD = 'manual_download'
ACTION_AUTO_APPLY = 'auto_apply_missing'
ACTION_DOWNLOAD = 'download'
ACTION_VIEW_REPORT = 'view_report'
ACTION_CANCEL = 'cancel'

REVIEW_MODE_MISSING = 'missing_only'


FANART_DIMENSIONS_MIN = {
    'poster': (1000, 1426),
    'fanart': (1920, 1080),
    'clearart': (1000, 562),
    'landscape': (1000, 562),
    'banner': (1000, 185),
    'discart': (1000, 1000),
    'clearlogo': (800, 310),
    'characterart': (1000, 1399),
    'keyart': (1000, 1426)
}

FANART_DIMENSIONS_IDEAL = {
    'poster': (2000, 3000),
    'fanart': (3840, 2160),
    'clearart': (1000, 562),
    'landscape': (1000, 562),
    'banner': (1000, 185),
    'discart': (1000, 1000),
    'clearlogo': (800, 310),
    'characterart': (1000, 1000),
    'keyart': (2000, 3000)
}

FANART_DIMENSIONS_VARIANTS = {
    'fanart': [(1920, 1080), (1280, 720), (3840, 2160)],
    'poster': [(1000, 1500), (2000, 3000), (680, 1000)],
    'characterart': [(512, 512), (1000, 1000), (256, 256)],
    'clearlogo': [(800, 310), (400, 155), (1600, 620)],
    'clearart': [(1000, 562), (500, 281), (1500, 843)],
    'banner': [(1000, 185), (758, 140), (1500, 277)],
    'landscape': [(1920, 1080), (1280, 720), (500, 281)],
    'keyart': [(1000, 1500), (2000, 3000), (680, 1000)],
    'discart': [(1000, 1000), (512, 512), (2000, 2000)],
}

FANART_DIMENSIONS = FANART_DIMENSIONS_MIN

# Auto-fetch language policies
AUTO_LANG_REQUIRED_TYPES = {
    'poster',
    'clearlogo',
    'clearart',
    'banner',
    'characterart',
    'discart',
    'landscape',
}

AUTO_NO_LANGUAGE_TYPES = {
    'fanart',
    'keyart',
}

CACHE_ART_TYPES = [
    'poster',
    'fanart',
    'clearlogo',
    'clearart',
    'banner',
    'landscape',
    'keyart',
    'characterart',
    'discart',
]

SESSION_DETAIL_KEYS = (
    'manual_applied',
    'manual_skipped',
    'manual_auto',
    'stale',
)


def default_session_stats() -> dict:
    """
    Create default session statistics structure.

    Returns:
        Dict with default stat values
    """
    return {
        'applied': 0,
        'skipped': 0,
        'auto': 0,
        'remaining': 0,
        'details': {key: [] for key in SESSION_DETAIL_KEYS},
        'auto_runs': [],
        'review_mode': REVIEW_MODE_MISSING,
    }


def load_session_stats(raw: Any) -> dict:
    """
    Load and normalize session statistics from storage.

    Args:
        raw: Raw stats (dict, JSON string, or None)

    Returns:
        Normalized stats dict
    """
    stats = default_session_stats()

    if raw:
        source = raw
        if isinstance(raw, str):
            try:
                source = json.loads(raw)
            except Exception:
                source = {}
        if isinstance(source, dict):
            for key in ('applied', 'skipped', 'auto', 'remaining'):
                value = source.get(key)
                if isinstance(value, (int, float)):
                    stats[key] = int(value)

            details = source.get('details')
            if isinstance(details, dict):
                for key in SESSION_DETAIL_KEYS:
                    entries = details.get(key, [])
                    if isinstance(entries, list):
                        stats['details'][key] = [dict(entry) for entry in entries if isinstance(entry, dict)]

            auto_runs = source.get('auto_runs')
            if isinstance(auto_runs, list):
                stats['auto_runs'] = [dict(run) for run in auto_runs if isinstance(run, dict)]

            stats['review_mode'] = REVIEW_MODE_MISSING

    return stats


def serialise_session_stats(stats: dict) -> dict:
    """
    Serialize session stats (currently just normalizes via load).

    Args:
        stats: Stats dict to serialize

    Returns:
        Normalized stats dict
    """
    return load_session_stats(stats)
