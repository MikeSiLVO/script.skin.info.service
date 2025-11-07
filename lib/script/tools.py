"""Tools main menu - unified entry point for artwork, cache, and ratings operations.

Provides a single menu for accessing:
- Artwork Reviewer: Manual and automatic artwork fetching/review
- Texture Cache Manager: Pre-caching and cleanup operations
- Animated Art Scanner: Scan for animated GIF posters in media folders
- Download Artwork to Filesystem: Bulk download artwork to local files
- Ratings Updater: Update library ratings from multiple sources
"""
from __future__ import annotations

import xbmcaddon
import xbmcgui
from lib.infrastructure.menus import Menu, MenuItem

ADDON = xbmcaddon.Addon()
_HOME = xbmcgui.Window(10000)


def run_tools() -> None:
    """
    Show main Tools menu and route to selected tool.

    Main menu options:
    - Artwork Reviewer: Access artwork scanning, review, and fetching workflows
    - Texture Cache Manager: Pre-cache or clean up texture cache
    - Animated Art Scanner: Scan for animated GIF posters in media folders
    - Download Artwork to Filesystem: Bulk download artwork to local files
    - Ratings Updater: Update library ratings from multiple sources

    If a background task is running, "Cancel Current Task" appears at the top.
    """
    from lib.infrastructure import tasks as task_manager
    from lib.artwork.manager import run_artwork_manager
    from lib.texture.menu import run_texture_maintenance
    from lib.artwork.animated import run_scanner
    from lib.download.menu import run_download_menu
    from lib.rating.updater import run_ratings_menu
    from lib.rating.ids import run_fix_library_ids

    task_manager.cleanup_stale_tasks()

    menu = Menu(ADDON.getLocalizedString(32530), [
        MenuItem(ADDON.getLocalizedString(32300), run_ratings_menu, loop=True),
        MenuItem(ADDON.getLocalizedString(32273), run_artwork_manager, loop=True),
        MenuItem(ADDON.getLocalizedString(32082), run_texture_maintenance, loop=True),
        MenuItem(ADDON.getLocalizedString(32522), run_download_menu, loop=True),
        MenuItem(ADDON.getLocalizedString(32192), run_scanner, loop=True),
        MenuItem(ADDON.getLocalizedString(32532), run_fix_library_ids, loop=True),
    ], is_main_menu=True)

    _HOME.setProperty("SkinInfo.ToolsMenuActive", "true")
    try:
        menu.show()
    finally:
        _HOME.clearProperty("SkinInfo.ToolsMenuActive")
