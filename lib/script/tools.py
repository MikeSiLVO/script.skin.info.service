"""Tools main menu - unified entry point for artwork, cache, and ratings operations.

Provides a single menu for accessing:
- Artwork Reviewer: Manual and automatic artwork fetching/review
- Texture Cache Manager: Pre-caching and cleanup operations
- Animated Art Scanner: Scan for animated GIF posters in media folders
- Download Artwork to Filesystem: Bulk download artwork to local files
- Ratings Updater: Update library ratings from multiple sources
- IMDb Top 250: Update Top 250 rankings from Trakt's official list
"""
from __future__ import annotations

import xbmcgui
from lib.infrastructure.menus import Menu, MenuItem
from lib.kodi.client import ADDON
_HOME = xbmcgui.Window(10000)


def run_tools() -> None:
    """
    Show main Tools menu and route to selected tool.

    Main menu options:
    - Ratings Updater: Update library ratings from multiple sources
    - Missing Artwork: Access artwork scanning, review, and fetching workflows
    - Texture Cache Manager: Pre-cache or clean up texture cache
    - Download Artwork to Filesystem: Bulk download artwork to local files
    - Animated Art Scanner: Scan for animated GIF posters in media folders
    - Add/Fix IMDb & TMDB IDs: Fix missing or invalid library IDs
    - IMDb Top 250: Update Top 250 rankings from Trakt's official list

    If a background task is running, "Cancel Current Task" appears at the top.
    """
    from lib.infrastructure import tasks as task_manager
    from lib.artwork.manager import run_artwork_manager
    from lib.texture.menu import run_texture_maintenance
    from lib.artwork.animated import run_scanner
    from lib.download.menu import run_download_menu
    from lib.rating.menu import run_ratings_menu
    from lib.rating.ids import run_fix_library_ids
    from lib.script.top250 import run_top250_update

    task_manager.cleanup_stale_tasks()

    menu = Menu(ADDON.getLocalizedString(32530), [
        MenuItem(ADDON.getLocalizedString(32300), run_ratings_menu, loop=True),
        MenuItem(ADDON.getLocalizedString(32273), run_artwork_manager, loop=True),
        MenuItem(ADDON.getLocalizedString(32082), run_texture_maintenance, loop=True),
        MenuItem(ADDON.getLocalizedString(32522), run_download_menu, loop=True),
        MenuItem(ADDON.getLocalizedString(32192), run_scanner, loop=True),
        MenuItem(ADDON.getLocalizedString(32532), run_fix_library_ids, loop=True),
        MenuItem(ADDON.getLocalizedString(32600), run_top250_update, loop=True),
    ], is_main_menu=True)

    _HOME.setProperty("SkinInfo.ToolsMenuActive", "true")
    try:
        menu.show()
    finally:
        _HOME.clearProperty("SkinInfo.ToolsMenuActive")
