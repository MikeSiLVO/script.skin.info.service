"""Download artwork menu UI handlers."""
from __future__ import annotations

import xbmc
from typing import Optional, List

from lib.infrastructure.dialogs import show_ok, show_textviewer
from lib.artwork.config import REVIEW_MEDIA_FILTERS, REVIEW_SCOPE_LABELS

from lib.data import database as db
from lib.download.workflows import LOG_DIR, download_scope_artwork
from lib.kodi.client import ADDON


def show_download_report() -> None:
    """Show the last download report from operation history."""
    last_report = db.get_last_operation_stats('artwork_download')

    if not last_report:
        show_ok(
            "Download Report",
            "No download history found."
        )
        return

    stats = last_report['stats']
    scope = last_report.get('scope', 'unknown')
    timestamp = last_report['timestamp']

    scope_label = REVIEW_SCOPE_LABELS.get(scope, scope.title())

    downloaded = stats.get('downloaded', 0)
    skipped = stats.get('skipped', 0)
    failed = stats.get('failed', 0)
    total_jobs = stats.get('total_jobs', 0)
    total_items = stats.get('total_items', 0)
    bytes_downloaded = stats.get('bytes_downloaded', 0)
    cancelled = stats.get('cancelled', False)
    mismatch_counts = stats.get('mismatch_counts', {})

    mb = bytes_downloaded / (1024 * 1024) if bytes_downloaded > 0 else 0

    status = "Cancelled" if cancelled else "Complete"

    lines = [
        f"[B]Artwork Download Report - {status}[/B]",
        "",
        f"Scope: {scope_label}",
        f"Timestamp: {timestamp}",
        "",
        f"Library items scanned: {total_items}",
        f"Total artwork URLs: {total_jobs}",
        f"Downloaded: {downloaded}",
        f"Skipped (already exists): {skipped}",
        f"Failed: {failed}",
        "",
        f"Total size: {mb:.2f} MB"
    ]

    folder_stats = stats.get('folder_counts', {})
    if folder_stats:
        sorted_folders = sorted(folder_stats.items(), key=lambda x: x[0])

        lines.extend([
            "",
            "[B]Downloaded Files by Folder[/B]",
            ""
        ])

        for folder_path, count in sorted_folders:
            lines.append(f"{count} files - {folder_path}")

    if mismatch_counts:
        total_mismatches = sum(mismatch_counts.values())
        if total_mismatches > 0:
            lines.extend([
                "",
                "[B]File Handling Mismatches Detected[/B]",
                ""
            ])

            if mismatch_counts.get('movie_folder_to_basename', 0) > 0:
                lines.append(f"{mismatch_counts['movie_folder_to_basename']} movie artwork files saved as 'poster.jpg' in movie folder")
                lines.append("  Setting 'Use Movie Filename Prefix' is ON (expects 'MovieTitle-poster.jpg')")
            if mismatch_counts.get('movie_basename_to_folder', 0) > 0:
                lines.append(f"{mismatch_counts['movie_basename_to_folder']} movie artwork files saved as 'MovieTitle-poster.jpg'")
                lines.append("  Setting 'Use Movie Filename Prefix' is OFF (expects 'poster.jpg')")
            if mismatch_counts.get('mvid_folder_to_basename', 0) > 0:
                lines.append(f"{mismatch_counts['mvid_folder_to_basename']} music video artwork files saved as 'poster.jpg' in video folder")
                lines.append("  Setting 'Use Music Video Filename Prefix' is ON (expects 'VideoTitle-poster.jpg')")
            if mismatch_counts.get('mvid_basename_to_folder', 0) > 0:
                lines.append(f"{mismatch_counts['mvid_basename_to_folder']} music video artwork files saved as 'VideoTitle-poster.jpg'")
                lines.append("  Setting 'Use Music Video Filename Prefix' is OFF (expects 'poster.jpg')")

    lines.extend([
        "",
        "",
        f"Log files location: {LOG_DIR}",
        "(Most recent downloads saved to artwork_download.log)"
    ])

    text = "\n".join(lines)

    show_textviewer(ADDON.getLocalizedString(32520), text)


def run_download_menu() -> None:
    """
    Show download menu with scope selection and report viewing.

    Allows user to:
    - Select scope and download artwork
    - View last download report
    """
    from lib.infrastructure.menus import Menu, MenuItem

    db.init_database()

    items = [MenuItem(ADDON.getLocalizedString(32290), _handle_download, loop=True)]

    if db.get_last_operation_stats('artwork_download'):
        items.append(MenuItem(ADDON.getLocalizedString(32086), show_download_report, loop=True))

    menu = Menu(ADDON.getLocalizedString(32522), items)
    menu.show()


def _handle_download():
    """Handle download artwork workflow."""
    from lib.infrastructure.menus import Menu, MenuItem

    scope_menu = Menu(ADDON.getLocalizedString(32523), [
        MenuItem(xbmc.getLocalizedString(593), lambda: _select_mode('all', None)),
        MenuItem(xbmc.getLocalizedString(342), lambda: _select_mode('movies', REVIEW_MEDIA_FILTERS.get('movies'))),
        MenuItem(xbmc.getLocalizedString(20343), lambda: _select_mode('tvshows', REVIEW_MEDIA_FILTERS.get('tvshows'))),
        MenuItem(xbmc.getLocalizedString(2), lambda: _select_mode('music', REVIEW_MEDIA_FILTERS.get('music'))),
    ])
    return scope_menu.show()


def _select_mode(scope: str, media_filter: Optional[List[str]]):
    """Select run mode and execute download."""
    from lib.infrastructure import tasks as task_manager
    from lib.infrastructure.menus import Menu, MenuItem

    def run_foreground():
        download_scope_artwork(scope=scope, media_filter=media_filter, use_background=False)

    def run_background():
        if task_manager.is_task_running():
            task_info = task_manager.get_task_info()
            current_task = task_info['name'] if task_info else "Unknown task"
            show_ok(
                ADDON.getLocalizedString(32172),
                f"{ADDON.getLocalizedString(32457).format(current_task)}[CR][CR]{ADDON.getLocalizedString(32458)}"
            )
            return
        download_scope_artwork(scope=scope, media_filter=media_filter, use_background=True)

    mode_menu = Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), run_foreground),
        MenuItem(ADDON.getLocalizedString(32412), run_background),
    ])
    return mode_menu.show()
