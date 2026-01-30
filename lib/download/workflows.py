"""Bulk artwork download workflow coordinators."""
from __future__ import annotations

import time
from datetime import datetime
import xbmc
from lib.infrastructure.dialogs import show_ok, show_textviewer
import xbmcgui
import xbmcvfs
from typing import Optional, List, Dict, Tuple, Any

from lib.kodi.client import KODI_GET_LIBRARY_METHODS, get_library_items
from lib.download.queue import DownloadQueue
from lib.infrastructure.paths import PathBuilder
from lib.infrastructure.tasks import TaskContext
from lib.artwork.config import REVIEW_MEDIA_FILTERS, REVIEW_SCOPE_LABELS
from lib.kodi.client import log, ADDON
from lib.data import database as db

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

        return LOG_FILE

    except Exception as e:
        log("Download", f"Error writing download log: {str(e)}", xbmc.LOGERROR)
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
        log("Artwork", f"Querying library for media types: {', '.join(media_types)}", xbmc.LOGDEBUG)
        all_items: List[Dict[str, Any]] = []

        for media_type in media_types:
            if media_type not in KODI_GET_LIBRARY_METHODS:
                continue

            properties = DOWNLOAD_PROPERTIES.get(media_type, ['art', 'title'])

            include_seasons = media_type == 'tvshow'
            season_props = DOWNLOAD_PROPERTIES.get('season', ['art', 'title', 'season'])

            items = get_library_items(
                media_types=[media_type],
                properties=properties,
                decode_urls=True,
                include_nested_seasons=include_seasons,
                season_properties=season_props,
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

        log("Artwork", f"Retrieved {len(all_items)} library items with artwork", xbmc.LOGDEBUG)
        return all_items

    except Exception as e:
        log("Download", f"Error querying library for download: {str(e)}", xbmc.LOGERROR)
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
    log("Artwork", f"Building download jobs from {len(items)} library items", xbmc.LOGDEBUG)
    jobs = []
    path_builder = PathBuilder()

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

            if media_type == 'episode' and (art_type.startswith('tvshow.') or art_type.startswith('season.')):
                continue

            if media_type == 'season' and art_type.startswith('tvshow.'):
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
                log("Download", f"Failed to build path for {media_type} '{title}' art:{art_type} file:{file_path}", xbmc.LOGWARNING)
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
    log("Artwork", f"Built {len(jobs)} download jobs from {len(items)} items "
        f"(skipped: {skipped_no_path} no path, {failed_build_path} path build failed, {total_mismatches} mismatches)")
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
    from lib.infrastructure.dialogs import show_yesno

    monitor = xbmc.Monitor()

    if media_filter is None:
        media_filter = REVIEW_MEDIA_FILTERS.get(scope, ['movie', 'tvshow', 'episode'])

    if not ADDON.getSettingBool('download.include_episode_thumbs'):
        media_filter = [mt for mt in media_filter if mt != 'episode']

    media_filter = [mt for mt in media_filter if mt in KODI_GET_LIBRARY_METHODS]

    if not media_filter:
        show_ok(
            ADDON.getLocalizedString(32290),
            ADDON.getLocalizedString(32043)
        )
        return

    if use_background:
        progress = xbmcgui.DialogProgressBG()
        progress.create(ADDON.getLocalizedString(32290), ADDON.getLocalizedString(32291))
    else:
        progress = xbmcgui.DialogProgress()
        progress.create(ADDON.getLocalizedString(32290), ADDON.getLocalizedString(32291))

    try:
        if use_background:
            progress.update(5, message=ADDON.getLocalizedString(32292))
        else:
            progress.update(5, ADDON.getLocalizedString(32292))
        items = get_library_items_for_download(media_filter)

        if not items:
            progress.close()
            show_ok(
                ADDON.getLocalizedString(32290),
                ADDON.getLocalizedString(32171)
            )
            return

        if monitor.abortRequested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
            progress.close()
            return

        if use_background:
            progress.update(15, message=ADDON.getLocalizedString(32293).format(len(items)))
        else:
            progress.update(15, ADDON.getLocalizedString(32293).format(len(items)))

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

            confirmed = show_yesno(
                ADDON.getLocalizedString(32119),
                f"[B]Overwrite mode is enabled[/B][CR][CR]"
                f"Filename pattern: {pattern_text}[CR]"
                f"Mismatches detected: {total_mismatches} files[CR][CR]"
                f"Original artwork will be [B]deleted[/B] after successful download.[CR][CR]",
                nolabel=xbmc.getLocalizedString(222),
                yeslabel=ADDON.getLocalizedString(32566)
            )

            if not confirmed:
                return

            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create(ADDON.getLocalizedString(32290), ADDON.getLocalizedString(32291))
            else:
                progress = xbmcgui.DialogProgress()
                progress.create(ADDON.getLocalizedString(32290), ADDON.getLocalizedString(32291))

        if not jobs:
            progress.close()
            show_ok(
                ADDON.getLocalizedString(32290),
                ADDON.getLocalizedString(32118).format(len(items))
            )
            return

        if monitor.abortRequested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
            progress.close()
            return

        if use_background:
            progress.update(25, message=ADDON.getLocalizedString(32294).format(len(jobs)))
        else:
            progress.update(25, ADDON.getLocalizedString(32294).format(len(jobs)))

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

                log("Artwork", f"Queued {len(jobs)} download jobs to {queue.num_workers} worker threads")
                last_update_time = time.time()
                loop_start_time = time.time()

                while not queue.queue.empty() or queue.processing_set:
                    if time.time() - loop_start_time > 300:
                        log("Artwork", "Download loop timeout (5 minutes) - forcing exit")
                        queue.stop(wait=False)
                        break

                    if monitor.abortRequested() or ctx.abort_flag.is_requested() or (isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled()):
                        abort_reason = "monitor" if monitor.abortRequested() else "ctx.abort_flag" if ctx.abort_flag.is_requested() else "progress.iscanceled"
                        log("Artwork", f"Download cancelled by user ({abort_reason})")
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
                            progress.update(percent, message=message)
                        else:
                            message = (
                                f"Progress: {completed} / {total}[CR]"
                                f"Downloaded: {downloaded} | Skipped: {skipped} | Failed: {failed}[CR]"
                                f"Size: {mb:.2f} MB"
                            )
                            progress.update(percent, message)
                        last_update_time = current_time

                    monitor.waitForAbort(0.2)

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
                                     mismatch_counts=mismatch_counts)

            finally:
                queue.stop(wait=False)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        import traceback
        log("Download", f"Download artwork failed: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)


def _show_download_report(
    stats: Dict,
    total_jobs: int,
    scope: str = 'all',
    use_background: bool = False,
    mismatch_counts: Optional[Dict[str, int]] = None
) -> None:
    """
    Show final download report dialog.

    Args:
        stats: Queue statistics dict
        total_jobs: Total number of jobs queued
        scope: Download scope
        use_background: If True, show notification instead of textviewer
        mismatch_counts: Dict with naming mismatch counts
    """
    from lib.infrastructure.dialogs import show_notification

    downloaded = stats.get('downloaded', 0)
    skipped = stats.get('skipped', 0)
    failed = stats.get('failed', 0)
    bytes_downloaded = stats.get('bytes_downloaded', 0)

    mb = bytes_downloaded / (1024 * 1024) if bytes_downloaded > 0 else 0

    if use_background:
        show_notification(
            ADDON.getLocalizedString(32121),
            ADDON.getLocalizedString(32099).format(downloaded, f"{mb:.2f}"),
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
    else:
        lines = [
            f"[B]{ADDON.getLocalizedString(32121)}[/B]",
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

        show_textviewer(ADDON.getLocalizedString(32520), text)
