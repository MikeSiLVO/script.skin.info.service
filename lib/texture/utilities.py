"""Texture cache URL filtering and parsing utilities."""
from __future__ import annotations

import urllib.parse
from lib.kodi.client import decode_image_url


def _parse_image_url(url: str) -> str:
    """
    Extract inner path from image:// wrapper.

    Args:
        url: URL potentially wrapped in image:// format

    Returns:
        Inner path without image:// prefix and trailing /
        Returns original URL if not in image:// format
    """
    if not url or not url.startswith('image://'):
        return url
    return url[8:-1] if url.endswith('/') else url[8:]


def should_precache_url(url: str) -> bool:
    """
    Determine if a URL should be pre-cached.

    Pre-cache library artwork from HTTP sources and local image files.
    Skip auto-generated thumbnails (video@, music@), addon icons, and system files.

    Args:
        url: Artwork URL (wrapped image:// format or decoded)

    Returns:
        True if URL should be pre-cached, False otherwise
    """
    if not url:
        return False

    decoded = decode_image_url(url)

    if decoded.startswith('image://video@') or decoded.startswith('image://music@'):
        return False

    if 'plugin://' in decoded:
        return False

    addon_markers = ['/addons/', '\\addons\\', '/system/', '\\system\\']
    if any(marker in decoded for marker in addon_markers):
        return False

    if 'Default' in decoded and decoded.endswith('.png'):
        return False

    return True


def is_library_artwork_url(url: str) -> bool:
    """
    Determine if a URL represents library artwork vs system files.

    System files include:
    - Addon icons/fanart (in /addons/ or \\addons\\)
    - Kodi system resources (in /system/ or \\system\\)
    - Built-in default icons (DefaultVideo.png, etc.)

    Library artwork includes:
    - HTTP/HTTPS URLs (TMDB, fanart.tv, etc.)
    - image:// wrapped media thumbnails (video@, music@)
    - Local media files on typical media drives

    Args:
        url: Texture URL from cache

    Returns:
        True if URL is library artwork, False if system file
    """
    if not url:
        return False

    inner_url = _parse_image_url(url) if url.startswith('image://') else url
    decoded_url = urllib.parse.unquote(inner_url)

    system_markers = ['/addons/', '\\addons\\', '/system/', '\\system\\']
    if any(marker in decoded_url for marker in system_markers):
        return False

    special_folders = ['/.actors/', '\\.actors\\', '/.extrafanart/', '\\.extrafanart\\', '/.extrathumbs/', '\\.extrathumbs\\']
    if any(marker in decoded_url for marker in special_folders):
        return False

    if 'Default' in decoded_url and decoded_url.endswith('.png'):
        return False

    if decoded_url.startswith('http://') or decoded_url.startswith('https://'):
        return True

    if url.startswith('image://') and '@' in inner_url:
        return True

    if ':' in decoded_url:
        drive = decoded_url.split(':')[0]
        if len(drive) == 1 and drive.upper() in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            return True

    if decoded_url.startswith('\\\\') or decoded_url.startswith('smb://') or decoded_url.startswith('nfs://'):
        return True

    return False
