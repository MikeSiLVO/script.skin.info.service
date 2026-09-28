"""Texture cache URL filtering and parsing utilities."""
from __future__ import annotations

import re
import urllib.parse
from lib.kodi.client import decode_image_url

_SYSTEM_PATH_MARKERS = (
    '/addons/', '\\addons\\', '/system/', '\\system\\', '/userdata/', '\\userdata\\',
)


def _parse_image_url(url: str) -> str:
    """Strip the `image://` wrapper and trailing `/`. Returns the input unchanged if not wrapped."""
    if not url or not url.startswith('image://'):
        return url
    return url[8:-1] if url.endswith('/') else url[8:]


def _is_system_artwork(text: str) -> bool:
    """True if the text looks like an add-on or system path, or Kodi's `Default*.png` icon."""
    if any(marker in text for marker in _SYSTEM_PATH_MARKERS):
        return True
    if 'Default' in text and text.endswith('.png'):
        return True
    return False


def should_precache_url(url: str) -> bool:
    """True for library artwork worth caching, not generated thumbs, add-on icons or plugins."""
    if not url:
        return False

    decoded = decode_image_url(url)

    if decoded.startswith('image://video@') or decoded.startswith('image://music@'):
        return False

    if 'plugin://' in decoded:
        return False

    return not _is_system_artwork(decoded)


_LOCAL_PATH_RE = re.compile(r'^([A-Z]:|/)', re.IGNORECASE)


def is_library_artwork_url(url: str) -> bool:
    """True if URL is library artwork; False for addon icons, system files or special folders."""
    if not url:
        return False

    inner_url = _parse_image_url(url) if url.startswith('image://') else url
    decoded_url = urllib.parse.unquote(inner_url)

    if _is_system_artwork(decoded_url):
        return False

    special_folders = (
        '/.actors/', '\\.actors\\',
        '/.extrafanart/', '\\.extrafanart\\',
        '/.extrathumbs/', '\\.extrathumbs\\'
    )
    if any(marker in decoded_url for marker in special_folders):
        return False

    if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
        return True

    if url.startswith('image://') and '@' in inner_url:
        return True

    if _LOCAL_PATH_RE.match(decoded_url):
        return True

    if decoded_url.startswith('\\\\') or decoded_url.startswith('smb://') or decoded_url.startswith('nfs://'):
        return True

    return False
