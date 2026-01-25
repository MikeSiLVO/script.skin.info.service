"""Playback helpers for skin RunScript calls.

Provides playall and playrandom functionality using JSON-RPC Playlist methods.
"""
from __future__ import annotations

import xbmc
import xbmcgui

from lib.kodi.client import request, ADDON
from lib.infrastructure.dialogs import show_notification


def _detect_media_type(path: str) -> str:
    """
    Detect media type from path.

    Args:
        path: Directory path

    Returns:
        'music' or 'video' based on path prefix
    """
    path_lower = path.lower()
    if path_lower.startswith(('musicdb://', 'library://music')):
        return 'music'
    return 'video'


def playall(path: str) -> None:
    """
    Play all items from a directory path.

    Args:
        path: Virtual file system path (e.g., videodb://movies/titles/, musicdb://artists/)

    Uses JSON-RPC Playlist methods to add all items from the directory
    and start playback in order. Auto-detects media type (music vs video).
    """
    if not path:
        show_notification(xbmc.getLocalizedString(257), ADDON.getLocalizedString(32270), xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    media_type = _detect_media_type(path)
    playlistid = 0 if media_type == 'music' else 1

    items = request('Files.GetDirectory', {
        'directory': path,
        'media': media_type
    })

    if not items or 'files' not in items or not items['files']:
        show_notification(xbmc.getLocalizedString(257), ADDON.getLocalizedString(32271), xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    request('Playlist.Clear', {'playlistid': playlistid})

    request('Playlist.Add', {
        'playlistid': playlistid,
        'item': {
            'directory': path,
            'recursive': True
        }
    })

    request('Player.Open', {
        'item': {'playlistid': playlistid},
        'options': {'shuffled': False}
    })


def playrandom(path: str) -> None:
    """
    Play all items from a directory path in random order.

    Args:
        path: Virtual file system path (e.g., videodb://movies/titles/, musicdb://artists/)

    Uses JSON-RPC Playlist methods to add all items from the directory
    and start playback shuffled. Auto-detects media type (music vs video).
    """
    if not path:
        show_notification(xbmc.getLocalizedString(257), ADDON.getLocalizedString(32270), xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    media_type = _detect_media_type(path)
    playlistid = 0 if media_type == 'music' else 1

    items = request('Files.GetDirectory', {
        'directory': path,
        'media': media_type
    })

    if not items or 'files' not in items or not items['files']:
        show_notification(xbmc.getLocalizedString(257), ADDON.getLocalizedString(32271), xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    request('Playlist.Clear', {'playlistid': playlistid})

    request('Playlist.Add', {
        'playlistid': playlistid,
        'item': {
            'directory': path,
            'recursive': True
        }
    })

    request('Player.Open', {
        'item': {'playlistid': playlistid},
        'options': {'shuffled': True}
    })
