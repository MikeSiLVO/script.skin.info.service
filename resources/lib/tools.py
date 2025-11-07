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
from resources.lib.ui_helper import show_menu_with_cancel

ADDON = xbmcaddon.Addon()


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
    from resources.lib import task_manager

    task_manager.cleanup_stale_tasks()

    while True:
        options = [
            ("Artwork Reviewer", "artwork"),
            ("Texture Cache Manager", "cache"),
            ("Animated Art Scanner", "animated"),
            ("Download Artwork to Filesystem", "download"),
            ("Ratings Updater", "ratings")
        ]

        action, cancelled = show_menu_with_cancel("Tools", options)

        if cancelled:
            task_running = task_manager.is_task_running()
            if task_running:
                import xbmc
                import time

                task_manager.cancel_task()

                monitor = xbmc.Monitor()
                start_time = time.time()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    elapsed = time.time() - start_time
                    if elapsed > 30:
                        xbmcgui.Dialog().ok("Error", "Task failed to stop after 30 seconds")
                        break
                    monitor.waitForAbort(0.1)

                xbmcgui.Dialog().notification(
                    "Tools",
                    "Background task cancelled",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            return

        if action is None:
            return

        if action == "artwork":
            from resources.lib.art_fetcher import run_art_reviewer
            run_art_reviewer()

        elif action == "cache":
            from resources.lib.texture_cache import run_texture_maintenance
            run_texture_maintenance()

        elif action == "animated":
            from resources.lib.artwork.gif_scanner import run_scanner
            run_scanner()

        elif action == "download":
            from resources.lib.downloads.bulk import run_download_menu
            run_download_menu()

        elif action == "ratings":
            from resources.lib.ratings.updater import run_ratings_menu
            run_ratings_menu()
