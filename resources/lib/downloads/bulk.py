"""Bulk artwork download operations for library scopes."""
from __future__ import annotations

import time
from datetime import datetime
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from typing import Optional, List, Dict, Tuple, Any

from resources.lib.kodi import KODI_GET_LIBRARY_METHODS, get_library_items
from resources.lib.downloads.queue import DownloadQueue
from resources.lib.downloads.path_builder import ArtworkPathBuilder
from resources.lib.task_manager import TaskContext
from resources.lib.artwork.helpers import REVIEW_MEDIA_FILTERS, REVIEW_SCOPE_LABELS
from resources.lib.kodi import log_artwork
from resources.lib import database as db

ADDON = xbmcaddon.Addon()

# Log file paths
LOG_DIR = xbmcvfs.translatePath('special://profile/addon_data/script.skin.info.service/')
LOG_FILE = LOG_DIR + 'artwork_download.log'
LOG_FILE_PREVIOUS = LOG_DIR + 'artwork_download_previous.log'
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Valid properties per media type from Kodi JSON-RPC introspect
DOWNLOAD_PROPERTIES = {
    'movie': ['art', 'title', 'file'],
    'tvshow': ['art', 'title', 'file', 'season', 'episode'],
    'episode': ['art', 'title', 'file', 'season', 'episode', 'tvshowid'],
    'musicvideo': ['art', 'title', 'file'],
    'set': ['art', 'title'],
    'season': ['art', 'title', 'season', 'episode', 'tvshowid'],
    'artist': ['art'],
    'album': ['art', 'title'],
}


def _ensure_log_directory() -> None:
    """Create log directory if it doesn't exist."""
    if not xbmcvfs.exists(LOG_DIR):
        xbmcvfs.mkdirs(LOG_DIR)


def _rotate_log_files() -> None:
    """Rotate log files: current -> previous, delete old previous."""
    if xbmcvfs.exists(LOG_FILE):
        if xbmcvfs.exists(LOG_FILE_PREVIOUS):
            xbmcvfs.delete(LOG_FILE_PREVIOUS)
        xbmcvfs.rename(LOG_FILE, LOG_FILE_PREVIOUS)


def write_download_log(
    report_text: str,
    scope: str,
    total_jobs: int,
    stats: Dict,
    mismatch_counts: Optional[Dict[str, int]] = None
) -> Optional[str]:
    """
    Write download report to log file with 2-file rotation.

    Args:
        report_text: Full report text from _show_download_report
        scope: Download scope
        total_jobs: Total number of jobs
        stats: Statistics dict
        mismatch_counts: Optional mismatch counts

    Returns:
        Log file path if successful, None if failed
    """
    try:
        _ensure_log_directory()
        _rotate_log_files()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scope_label = REVIEW_SCOPE_LABELS.get(scope, scope.title())

        header = "=" * 80 + "\n"
        header += f"Artwork Download Report - {timestamp}\n"
        header += f"Scope: {scope_label}\n"
        header += "=" * 80 + "\n\n"

        full_text = header + report_text

        estimated_size = len(full_text.encode('utf-8'))

        if estimated_size > MAX_LOG_SIZE_BYTES:
            folder_stats = stats.get('folder_counts', {})
            if folder_stats:
                max_folders = int((MAX_LOG_SIZE_BYTES * 0.8) / 265)

                sorted_folders = sorted(folder_stats.items(), key=lambda x: x[0])
                truncated_count = len(sorted_folders) - max_folders

                if truncated_count > 0:
                    truncated_text = f"\n(Truncated {truncated_count} folders to fit 5MB size limit)\n"

                    folder_lines = [f"{count} files - {path}" for path, count in sorted_folders[:max_folders]]

                    report_parts = report_text.split("[B]Downloaded Files by Folder[/B]")
                    if len(report_parts) == 2:
                        before_folders = report_parts[0] + "[B]Downloaded Files by Folder[/B]\n\n"
                        after_folders = ""

                        if "[B]Filename Pattern Mismatches" in report_parts[1]:
                            folder_part, mismatch_part = report_parts[1].split("[B]Filename Pattern Mismatches", 1)
                            after_folders = "\n\n[B]Filename Pattern Mismatches" + mismatch_part

                        report_text = before_folders + truncated_text + "\n".join(folder_lines) + after_folders
                        full_text = header + report_text

        with xbmcvfs.File(LOG_FILE, 'w') as f:
            f.write(full_text.encode('utf-8'))

        xbmc.log(f"SkinInfo: Download report saved to {LOG_FILE}", xbmc.LOGDEBUG)
        return LOG_FILE

    except Exception as e:
        xbmc.log(f"SkinInfo: Error writing download log: {str(e)}", xbmc.LOGERROR)
        return None


def get_library_items_for_download(media_types: List[str]) -> List[Dict[str, Any]]:
    """
    Query Kodi library for items with artwork and file paths.

    Args:
        media_types: List of media types to query ('movie', 'tvshow', etc.)

    Returns:
        List of item dicts with keys: dbid, media_type, title, file, art
    """
    def has_artwork(item: Dict[str, Any]) -> bool:
        art = item.get('art', {})
        return bool(art and isinstance(art, dict))

    try:
        log_artwork(f"Querying library for media types: {', '.join(media_types)}")
        all_items: List[Dict[str, Any]] = []

        for media_type in media_types:
            if media_type not in KODI_GET_LIBRARY_METHODS:
                continue

            properties = DOWNLOAD_PROPERTIES.get(media_type, ['art', 'title'])

            items = get_library_items(
                media_types=[media_type],
                properties=properties,
                decode_urls=True,
                filter_func=has_artwork
            )

            all_items.extend(items)

        for item in all_items:
            file_path = item.get("file", "")
            if item['media_type'] == 'set' and not file_path:
                file_path = item.get("title", "")
            item['file'] = file_path

            if 'title' not in item:
                item['title'] = item.get('label', 'Unknown')

        log_artwork(f"Retrieved {len(all_items)} library items with artwork")
        return all_items

    except Exception as e:
        xbmc.log(
            f"SkinInfo: Error querying library for download: {str(e)}",
            xbmc.LOGERROR
        )
        return []


def build_download_jobs(
    items: List[Dict[str, Any]],
    existing_file_mode: str = 'skip'
) -> Tuple[List[Tuple[str, str, str, str, Optional[str], str]], Dict[str, int]]:
    """
    Build download job list from library items.

    Args:
        items: Library items from get_library_items_for_download()
        existing_file_mode: How to handle existing files

    Returns:
        Tuple of (jobs, mismatch_stats):
        - jobs: List of (url, local_path, artwork_type, title, alternate_path, media_type) tuples
        - mismatch_stats: Dict with mismatch counts per media type
    """
    log_artwork(f"Building download jobs from {len(items)} library items")
    jobs = []
    path_builder = ArtworkPathBuilder()

    savewith_basefilename = ADDON.getSettingBool('download.savewith_basefilename')
    savewith_basefilename_mvids = ADDON.getSettingBool('download.savewith_basefilename_mvids')

    mismatch_counts = {'movie_basename_to_folder': 0, 'movie_folder_to_basename': 0,
                       'mvid_basename_to_folder': 0, 'mvid_folder_to_basename': 0}

    skipped_no_path = 0
    failed_build_path = 0

    for item in items:
        media_type = item['media_type']
        title = item['title']
        art = item['art']
        file_path = item.get('file', '')

        if not file_path and media_type not in ('season', 'tvshow', 'set', 'artist', 'album'):
            skipped_no_path += 1
            continue

        use_basename = media_type == 'episode' \
            or media_type == 'movie' and savewith_basefilename \
            or media_type == 'musicvideo' and savewith_basefilename_mvids

        for art_type, url in art.items():
            if not url or not url.startswith('http'):
                continue

            if media_type == 'movie' and art_type.startswith('set.'):
                continue

            local_path = path_builder.build_path(
                media_type=media_type,
                media_file=file_path,
                artwork_type=art_type,
                season_number=item.get('season'),
                episode_number=item.get('episode'),
                use_basename=use_basename
            )

            if not local_path:
                failed_build_path += 1
                continue

            alternate_path = None
            if media_type in ('movie', 'musicvideo'):
                alternate_path = path_builder.build_path(
                    media_type=media_type,
                    media_file=file_path,
                    artwork_type=art_type,
                    season_number=item.get('season'),
                    episode_number=item.get('episode'),
                    use_basename=not use_basename
                )

                if alternate_path:
                    for ext in ['jpg', 'png', 'gif', 'webp']:
                        if xbmcvfs.exists(alternate_path + '.' + ext):
                            if media_type == 'movie':
                                if use_basename:
                                    mismatch_counts['movie_folder_to_basename'] += 1
                                else:
                                    mismatch_counts['movie_basename_to_folder'] += 1
                            else:
                                if use_basename:
                                    mismatch_counts['mvid_folder_to_basename'] += 1
                                else:
                                    mismatch_counts['mvid_basename_to_folder'] += 1
                            break

            jobs.append((url, local_path, art_type, title, alternate_path, media_type))

    total_mismatches = sum(mismatch_counts.values())
    log_artwork(
        f"Built {len(jobs)} download jobs from {len(items)} items "
        f"(skipped: {skipped_no_path} no path, {failed_build_path} path build failed, {total_mismatches} mismatches)"
    )
    return jobs, mismatch_counts


def download_scope_artwork(
    scope: str,
    media_filter: Optional[List[str]] = None,
    use_background: bool = False
) -> None:
    """
    Download all artwork for a scope to filesystem.

    Uses TaskContext for cancellation and progress tracking.

    Args:
        scope: Review scope ('all', 'movies', 'tv', etc.)
        media_filter: Optional list of media types to filter
        use_background: Use DialogProgressBG for background operation (True) or DialogProgress for foreground (False)
    """
    monitor = xbmc.Monitor()

    if media_filter is None:
        media_filter = REVIEW_MEDIA_FILTERS.get(scope, ['movie', 'tvshow', 'episode'])

    media_filter = [mt for mt in media_filter if mt in KODI_GET_LIBRARY_METHODS]

    if not media_filter:
        xbmcgui.Dialog().ok(
            "Download Artwork",
            "No valid media types to download."
        )
        return

    if use_background:
        progress = xbmcgui.DialogProgressBG()
        progress.create("Download Artwork", "Preparing...")
    else:
        progress = xbmcgui.DialogProgress()
        progress.create("Download Artwork", "Preparing...")

    try:
        if use_background:
            progress.update(5, message="Scanning library...")  # type: ignore[call-arg]
        else:
            progress.update(5, "Scanning library...")
        items = get_library_items_for_download(media_filter)

        if not items:
            progress.close()
            xbmcgui.Dialog().ok(
                "Download Artwork",
                "No items found in library."
            )
            return

        if monitor.abortRequested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
            progress.close()
            return

        if use_background:
            progress.update(15, message=f"Building download list from {len(items)} items...")  # type: ignore[call-arg]
        else:
            progress.update(15, f"Building download list from {len(items)} items...")

        existing_file_mode_setting = ADDON.getSetting('download.existing_file_mode')
        existing_file_mode_int = int(existing_file_mode_setting) if existing_file_mode_setting else 0
        existing_file_mode = ['skip', 'overwrite'][existing_file_mode_int]

        jobs, mismatch_counts = build_download_jobs(items, existing_file_mode)

        if existing_file_mode == 'overwrite' and sum(mismatch_counts.values()) > 0:
            progress.close()

            total_mismatches = sum(mismatch_counts.values())
            savewith_basefilename = ADDON.getSettingBool('download.savewith_basefilename')
            savewith_basefilename_mvids = ADDON.getSettingBool('download.savewith_basefilename_mvids')

            pattern_desc = []
            if mismatch_counts.get('movie_folder_to_basename', 0) > 0 or mismatch_counts.get('movie_basename_to_folder', 0) > 0:
                pattern_desc.append(f"Movies: {'basename' if savewith_basefilename else 'folder'} mode")
            if mismatch_counts.get('mvid_folder_to_basename', 0) > 0 or mismatch_counts.get('mvid_basename_to_folder', 0) > 0:
                pattern_desc.append(f"Music videos: {'basename' if savewith_basefilename_mvids else 'folder'} mode")

            pattern_text = ", ".join(pattern_desc)

            confirmed = xbmcgui.Dialog().yesno(
                "Overwrite Mode Warning",
                f"[B]Overwrite mode is enabled[/B][CR][CR]"
                f"Filename pattern: {pattern_text}[CR]"
                f"Mismatches detected: {total_mismatches} files[CR][CR]"
                f"Original artwork will be [B]deleted[/B] after successful download.[CR][CR]",
                nolabel="Cancel",
                yeslabel="Continue"
            )

            if not confirmed:
                return

            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create("Download Artwork", "Preparing...")
            else:
                progress = xbmcgui.DialogProgress()
                progress.create("Download Artwork", "Preparing...")

        if not jobs:
            progress.close()
            xbmcgui.Dialog().ok(
                "Download Artwork",
                f"No HTTP artwork URLs found in {len(items)} library items."
            )
            return

        if monitor.abortRequested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
            progress.close()
            return

        if use_background:
            progress.update(25, message=f"Starting download of {len(jobs)} artwork files...")  # type: ignore[call-arg]
        else:
            progress.update(25, f"Starting download of {len(jobs)} artwork files...")

        with TaskContext("Download Artwork") as ctx:
            queue = DownloadQueue(
                existing_file_mode=existing_file_mode,
                abort_flag=ctx.abort_flag,
                task_context=ctx
            )
            queue.start()

            try:
                for job in jobs:
                    url, local_path, artwork_type, title, alternate_path, media_type = job
                    queue.add_download(url, local_path, artwork_type, title, alternate_path, media_type)

                log_artwork(f"Queued {len(jobs)} download jobs to {queue.num_workers} worker threads")
                last_update_time = time.time()
                loop_start_time = time.time()

                while not queue.queue.empty() or queue.processing_set:
                    if time.time() - loop_start_time > 300:
                        log_artwork("Download loop timeout (5 minutes) - forcing exit")
                        queue.stop(wait=False)
                        break

                    if monitor.abortRequested() or ctx.abort_flag.is_requested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
                        abort_reason = "monitor" if monitor.abortRequested() else "ctx.abort_flag" if ctx.abort_flag.is_requested() else "progress.iscanceled"
                        log_artwork(f"Download cancelled by user ({abort_reason})")
                        queue.stop(wait=False)
                        break

                    current_time = time.time()
                    if current_time - last_update_time >= 0.5:
                        stats = queue.get_stats()
                        total = stats.get('total_queued', 0)
                        completed = stats.get('completed', 0)
                        downloaded = stats.get('downloaded', 0)
                        skipped = stats.get('skipped', 0)
                        failed = stats.get('failed', 0)

                        if total > 0:
                            percent = 25 + int((completed / total) * 75)
                        else:
                            percent = 100

                        bytes_downloaded = stats.get('bytes_downloaded', 0)
                        mb = bytes_downloaded / (1024 * 1024) if bytes_downloaded > 0 else 0

                        if use_background:
                            message = f"Downloaded {downloaded} of {total} ({mb:.2f} MB)"
                            progress.update(percent, message=message)  # type: ignore[call-arg]
                        else:
                            message = (
                                f"Progress: {completed} / {total}[CR]"
                                f"Downloaded: {downloaded} | Skipped: {skipped} | Failed: {failed}[CR]"
                                f"Size: {mb:.2f} MB"
                            )
                            progress.update(percent, message)
                        last_update_time = current_time

                    time.sleep(0.2)

                final_stats = queue.get_stats()

                cancelled = (
                    monitor.abortRequested() or
                    ctx.abort_flag.is_requested() or
                    (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled())
                )

                progress.close()

                db.save_operation_stats('artwork_download', {
                    'total_jobs': len(jobs),
                    'total_items': len(items),
                    'downloaded': final_stats.get('downloaded', 0),
                    'skipped': final_stats.get('skipped', 0),
                    'failed': final_stats.get('failed', 0),
                    'bytes_downloaded': final_stats.get('bytes_downloaded', 0),
                    'cancelled': cancelled,
                    'mismatch_counts': mismatch_counts,
                    'folder_counts': final_stats.get('folder_counts', {})
                }, scope=scope)

                _show_download_report(final_stats, len(jobs), scope=scope, use_background=use_background,
                                     mismatch_counts=mismatch_counts, existing_file_mode=existing_file_mode)

            finally:
                queue.stop(wait=False)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        xbmc.log(
            f"SkinInfo: Download artwork failed: {str(e)}",
            xbmc.LOGERROR
        )
        import traceback
        xbmc.log(
            f"SkinInfo: Download artwork traceback: {traceback.format_exc()}",
            xbmc.LOGERROR
        )


def _show_download_report(
    stats: Dict,
    total_jobs: int,
    scope: str = 'all',
    use_background: bool = False,
    mismatch_counts: Optional[Dict[str, int]] = None,
    existing_file_mode: str = 'skip'
) -> None:
    """
    Show final download report dialog.

    Args:
        stats: Queue statistics dict
        total_jobs: Total number of jobs queued
        scope: Download scope
        use_background: If True, show notification instead of textviewer
        mismatch_counts: Dict with naming mismatch counts
        existing_file_mode: Current file mode setting
    """
    downloaded = stats.get('downloaded', 0)
    skipped = stats.get('skipped', 0)
    failed = stats.get('failed', 0)
    bytes_downloaded = stats.get('bytes_downloaded', 0)

    mb = bytes_downloaded / (1024 * 1024) if bytes_downloaded > 0 else 0

    if use_background:
        xbmcgui.Dialog().notification(
            "Download Complete",
            f"Downloaded {downloaded} files ({mb:.2f} MB)",
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
    else:
        lines = [
            "[B]Download Complete[/B]",
            "",
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

        text = "\n".join(lines)

        log_path = write_download_log(text, scope, total_jobs, stats, mismatch_counts)

        if log_path:
            lines.extend([
                "",
                "",
                f"Full report saved to: {log_path}"
            ])
            text = "\n".join(lines)

        xbmcgui.Dialog().textviewer("Artwork Download Report", text)


def show_download_report() -> None:
    """Show the last download report from operation history."""
    last_report = db.get_last_operation_stats('artwork_download')

    if not last_report:
        xbmcgui.Dialog().ok(
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

    xbmcgui.Dialog().textviewer("Artwork Download Report", text)


def run_download_menu() -> None:
    """
    Show download menu with scope selection and report viewing.

    Allows user to:
    - Select scope and download artwork
    - View last download report
    """
    from resources.lib.artwork.helpers import REVIEW_MEDIA_FILTERS
    from resources.lib import task_manager
    from resources.lib.ui_helper import show_menu_with_cancel

    db.init_database()

    while True:
        action_options: List[Tuple[str, Optional[str]]] = [("Download Artwork", "download")]

        if db.get_last_operation_stats('artwork_download'):
            action_options.append(("View Last Report", "report"))

        action, cancelled = show_menu_with_cancel("Download Artwork", action_options)

        if cancelled or action is None:
            return

        if action == "report":
            show_download_report()
            continue

        scope_options = [
            ("All Media", 'all'),
            ("Movies", 'movies'),
            ("TV Shows", 'tvshows'),
            ("Music", 'music')
        ]

        scope, scope_cancelled = show_menu_with_cancel("Download Artwork - Select Scope", scope_options)

        if scope_cancelled or scope is None:
            continue

        media_filter = None if scope == 'all' else REVIEW_MEDIA_FILTERS.get(scope, None)

        mode_options = [
            ("Show progress dialog (Foreground)", "foreground"),
            ("Run in background", "background")
        ]

        mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

        if mode_cancelled or mode_value is None:
            continue

        use_background = (mode_value == "background")

        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                xbmcgui.Dialog().ok(
                    "Task Already Running",
                    f"Another background task is currently running:[CR]{current_task}[CR][CR]Cannot start download in background."
                )
                continue

        download_scope_artwork(scope=scope, media_filter=media_filter, use_background=use_background)
        return
