"""Find and add animated GIF posters to library items."""
from __future__ import annotations

import os
import xbmc
import xbmcvfs
from lib.infrastructure.dialogs import show_textviewer, show_select, show_notification, show_yesno
import xbmcgui
from typing import Optional, Dict, List
from datetime import datetime

from lib.kodi.client import request, log, ADDON
from lib.infrastructure import tasks as task_manager
from lib.infrastructure.dialogs import ProgressDialog, format_operation_report
from lib.infrastructure.menus import Menu, MenuItem
from lib.data.database import init_database
from lib.data.database.workflow import save_operation_stats, get_last_operation_stats
from lib.data.database import gif as gif_db


def run_scanner(scope: Optional[str] = None, scan_mode: Optional[str] = None) -> None:
    """
    Run gif poster scanner with dialog-based options.

    Args:
        scope: "movies", "tvshows", "all", or None (shows dialog)
        scan_mode: "incremental", "full", or None (uses setting)
    """
    init_database()

    last_stats = get_last_operation_stats('gif_scan')

    items = [MenuItem(ADDON.getLocalizedString(32540), lambda: _run_scan(scope, scan_mode))]
    if last_stats:
        items.append(MenuItem(ADDON.getLocalizedString(32086), lambda: _view_report(last_stats), loop=True))

    items.extend([
        MenuItem(ADDON.getLocalizedString(32541), _view_cache_stats, loop=True),
        MenuItem(ADDON.getLocalizedString(32542), _clear_cache, loop=True)
    ])

    menu = Menu(ADDON.getLocalizedString(32192), items)
    menu.show()


def _view_report(last_stats: Dict) -> None:
    """Display the last scan report."""
    report_text = format_operation_report(
        'gif_scan',
        last_stats['stats'],
        last_stats['timestamp'],
        last_stats.get('scope')
    )
    show_textviewer(ADDON.getLocalizedString(32543), report_text)


def _view_cache_stats() -> None:
    """Display cache statistics."""
    cache = gif_db.get_all_cached_gifs()

    if not cache:
        show_notification(
            ADDON.getLocalizedString(32547),
            ADDON.getLocalizedString(32073),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return

    lines = []
    lines.append(f"[B]{ADDON.getLocalizedString(32544)}[/B]")
    lines.append("")
    lines.append(ADDON.getLocalizedString(32588).format(len(cache)))
    lines.append("")

    if cache:
        sorted_gifs = sorted(cache.items(), key=lambda x: x[1].get('scanned_at', ''), reverse=True)

        lines.append(f"[B]{ADDON.getLocalizedString(32589).format(20)}[/B]")
        for path, metadata in sorted_gifs[:20]:
            scanned_at = metadata.get('scanned_at', xbmc.getLocalizedString(13205))
            filename = path.split('/')[-1] if '/' in path else path.split('\\')[-1] if '\\' in path else path
            lines.append(f"  {filename}")
            lines.append(f"    Scanned: {scanned_at}")

        if len(cache) > 20:
            lines.append(f"  {ADDON.getLocalizedString(32590).format(len(cache) - 20)}")

    text = "\n".join(lines)
    show_textviewer(ADDON.getLocalizedString(32544), text)


def _clear_cache() -> None:
    """Clear the GIF cache after confirmation."""
    cache = gif_db.get_all_cached_gifs()
    count = len(cache)

    if count == 0:
        show_notification(
            ADDON.getLocalizedString(32547),
            ADDON.getLocalizedString(32549),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return

    confirmed = show_yesno(
        ADDON.getLocalizedString(32542),
        ADDON.getLocalizedString(32546).format(count)
    )

    if not confirmed:
        return

    removed = gif_db.clear_gif_cache()
    show_notification(
        ADDON.getLocalizedString(32547),
        ADDON.getLocalizedString(32548).format(removed),
        xbmcgui.NOTIFICATION_INFO,
        4000
    )


def _run_scan(scope: Optional[str], scan_mode: Optional[str]) -> None:
    """Execute the GIF scan with the given scope and mode."""
    if scope is None:
        scope = _select_scope()
        if scope is None:
            return

    scope = scope.lower()
    valid_scopes = ("movies", "tvshows", "all")
    if scope not in valid_scopes:
        log("Artwork", f"Invalid scope '{scope}' for gif scanner. Expected one of: {', '.join(valid_scopes)}", xbmc.LOGWARNING)
        show_notification(
            ADDON.getLocalizedString(32192),
            ADDON.getLocalizedString(32575).format(scope),
            xbmcgui.NOTIFICATION_WARNING,
            4000
        )
        return

    if scan_mode is None:
        scan_mode = _get_scan_mode_from_setting()
        if scan_mode is None:
            return

    scan_mode = scan_mode.lower()
    valid_modes = ("incremental", "full")
    if scan_mode not in valid_modes:
        log("Artwork", f"Invalid scan mode '{scan_mode}'. Expected one of: {', '.join(valid_modes)}", xbmc.LOGWARNING)
        show_notification(
            ADDON.getLocalizedString(32192),
            ADDON.getLocalizedString(32576).format(scan_mode),
            xbmcgui.NOTIFICATION_WARNING,
            4000
        )
        return

    dialog = xbmcgui.Dialog()

    try:
        if task_manager.is_task_running():
            task_info = task_manager.get_task_info()
            current_task = task_info['name'] if task_info else xbmc.getLocalizedString(13205)

            cancel_it = dialog.yesno(
                ADDON.getLocalizedString(32172),
                f"{ADDON.getLocalizedString(32457).format(current_task)}[CR][CR]{ADDON.getLocalizedString(32592).format(ADDON.getLocalizedString(32192))}",
                nolabel=xbmc.getLocalizedString(106),
                yeslabel=ADDON.getLocalizedString(32569)
            )

            if not cancel_it:
                return

            task_manager.cancel_task()
            monitor = xbmc.Monitor()
            while task_manager.is_task_running() and not monitor.abortRequested():
                monitor.waitForAbort(0.1)

        with task_manager.TaskContext(ADDON.getLocalizedString(32192)) as ctx:
            progress = ProgressDialog(use_background=False, heading=ADDON.getLocalizedString(32192))
            progress.create(f"[B]{ADDON.getLocalizedString(32574).upper()}[/B][CR]{ADDON.getLocalizedString(32278)}")

            cancelled = _run_scan_operation(scope, scan_mode, progress, task_context=ctx)

            progress.close()

            if cancelled:
                resume_bg = dialog.yesno(
                    ADDON.getLocalizedString(32572),
                    ADDON.getLocalizedString(32573),
                    nolabel=xbmc.getLocalizedString(15066),
                    yeslabel=ADDON.getLocalizedString(32568)
                )

                if resume_bg:
                    if task_manager.is_task_running():
                        dialog.ok(ADDON.getLocalizedString(32172), f"{ADDON.getLocalizedString(32173)}.[CR]{ADDON.getLocalizedString(32591)}")
                        return
                    with task_manager.TaskContext(ADDON.getLocalizedString(32192)) as bg_ctx:
                        progress_bg = ProgressDialog(use_background=True, heading=ADDON.getLocalizedString(32192))
                        progress_bg.create(ADDON.getLocalizedString(32577))
                        _run_scan_operation(scope, scan_mode, progress_bg, task_context=bg_ctx)
                        progress_bg.close()

                        dialog.notification(
                            ADDON.getLocalizedString(32192),
                            ADDON.getLocalizedString(32578),
                            xbmcgui.NOTIFICATION_INFO,
                            3000
                        )

    except Exception as e:
        log("Artwork", f"Animated scan failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(ADDON.getLocalizedString(32192), f"{ADDON.getLocalizedString(32274)}:[CR]{str(e)}")


def _run_scan_operation(
    scope: str,
    scan_mode: str,
    progress: ProgressDialog,
    task_context=None
) -> bool:
    """
    Execute the actual scanning operation.

    Args:
        scope: "movies", "tvshows", or "all"
        scan_mode: "incremental" or "full"
        progress: Progress dialog helper
        task_context: Optional TaskContext for progress tracking and cancellation

    Returns:
        True if cancelled, False if completed
    """
    patterns_setting = ADDON.getSetting("gif_patterns")
    if patterns_setting:
        patterns = [p.strip() for p in patterns_setting.split(",") if p.strip()]
    else:
        patterns = ["poster.gif", "animatedposter.gif"]

    force_full_rescan = (scan_mode == "full")

    scanner = ArtworkAnimated(patterns, force_full_rescan, progress, task_context)

    if scope in ("movies", "all"):
        scanner.scan_movies()
        if scanner.cancelled:
            return True

    if scope in ("tvshows", "all"):
        scanner.scan_tvshows()
        if scanner.cancelled:
            return True

    if not scanner.cancelled:
        stale_removed = scanner.cleanup_stale_cache()
        log("Artwork", f"Cleaned {stale_removed} stale GIF cache entries", xbmc.LOGDEBUG)

    scanner.show_summary()

    stats = {
        'found_count': scanner.found_count,
        'scanned_count': scanner.scanned_count,
        'skipped_cached': scanner.skipped_cached,
        'skipped_existing': scanner.skipped_existing,
        'scan_mode': scan_mode,
        'cancelled': scanner.cancelled
    }

    save_operation_stats('gif_scan', stats, scope=scope)

    return scanner.cancelled


def _select_scope() -> Optional[str]:
    """
    Show dialog to select scan scope.

    Returns:
        Selected scope or None if cancelled
    """
    options = [
        ("all", ADDON.getLocalizedString(32579)),
        ("movies", ADDON.getLocalizedString(32580)),
        ("tvshows", ADDON.getLocalizedString(32581))
    ]

    labels = [label for _, label in options]
    choice = show_select(ADDON.getLocalizedString(32552), labels)

    if choice == -1:
        return None

    return options[choice][0]


def _get_scan_mode_from_setting() -> Optional[str]:
    """
    Get scan mode from setting or prompt user if set to 'always_ask'.

    Returns:
        Selected scan mode ('incremental' or 'full') or None if cancelled
    """
    setting_value = ADDON.getSetting("gif_scan.scan_mode")

    if setting_value == "always_ask":
        cache = gif_db.get_all_cached_gifs()
        cache_info = f" ({ADDON.getLocalizedString(32586).format(len(cache))})" if cache else f" ({ADDON.getLocalizedString(32587)})"

        options = [
            ("incremental", f"{ADDON.getLocalizedString(32582)}{cache_info}", ADDON.getLocalizedString(32583)),
            ("full", ADDON.getLocalizedString(32584), ADDON.getLocalizedString(32585))
        ]

        labels = []
        for _, label, desc in options:
            labels.append(f"{label}\n{desc}")

        choice = show_select(ADDON.getLocalizedString(32553), labels)

        if choice == -1:
            return None

        return options[choice][0]

    if setting_value in ("incremental", "full"):
        return setting_value

    return "incremental"


class ArtworkAnimated:
    """Scans for animated gif posters and updates Kodi's art database."""

    def __init__(
        self,
        patterns: List[str],
        force_full_rescan: bool,
        progress: ProgressDialog,
        task_context=None
    ):
        self.patterns = patterns
        self.force_full_rescan = force_full_rescan
        self.progress = progress
        self.task_context = task_context
        self.found_count = 0
        self.scanned_count = 0
        self.skipped_cached = 0
        self.skipped_existing = 0
        self.cancelled = False
        self.accessed_paths = set()

    def scan_movies(self) -> None:
        """Scan all movies for gif posters."""
        resp = request(
            "VideoLibrary.GetMovies",
            {
                "properties": ["file", "art", "dateadded"],
            }
        )

        if not resp:
            log("Artwork", "Failed to get movies list", xbmc.LOGWARNING)
            return

        movies = resp.get("result", {}).get("movies", [])
        if not movies:
            return

        total = len(movies)

        for idx, movie in enumerate(movies):
            if (self.task_context and self.task_context.abort_flag.is_requested()) or self.progress.is_cancelled():
                self.cancelled = True
                break

            self.scanned_count += 1
            movie_id = movie.get("movieid")
            title = movie.get("label", xbmc.getLocalizedString(13205))
            file_path = movie.get("file", "")
            current_art = movie.get("art", {})

            percent = int((idx / total) * 100)
            message = f"Scanning: {title}\nProgress: {idx + 1}/{total} | Found: {self.found_count} | Cached: {self.skipped_cached} | Existing: {self.skipped_existing}"
            self.progress.update(percent, message)

            if not movie_id or not file_path:
                continue

            gif_path = self._find_gif(file_path)

            if gif_path:
                self.accessed_paths.add(gif_path)

                if not self.force_full_rescan and self._should_skip_gif(gif_path):
                    self.skipped_cached += 1
                    log("Artwork", f"GIF scan: Skipped cached GIF for movieid={movie_id} ({title}): {gif_path}", xbmc.LOGDEBUG)
                    continue

                log("Artwork", f"GIF scan: Setting GIF for movieid={movie_id} ({title}): {gif_path}", xbmc.LOGDEBUG)
                if self._set_movie_art(movie_id, title, gif_path):
                    self._update_cache(gif_path)
                    self.found_count += 1
                else:
                    log("Artwork", f"GIF scan: Failed to apply GIF for movieid={movie_id} ({title})", xbmc.LOGWARNING)
            else:
                if current_art.get("animatedposter"):
                    self.skipped_existing += 1
                else:
                    log("Artwork", f"GIF scan: No matching GIF found for movieid={movie_id} ({title}), folder={os.path.dirname(file_path)}", xbmc.LOGDEBUG)


    def scan_tvshows(self) -> None:
        """Scan all TV shows for gif posters."""
        resp = request(
            "VideoLibrary.GetTVShows",
            {
                "properties": ["file", "art", "dateadded"],
            }
        )

        if not resp:
            log("Artwork", "Failed to get TV shows list", xbmc.LOGWARNING)
            return

        tvshows = resp.get("result", {}).get("tvshows", [])
        if not tvshows:
            return

        total = len(tvshows)

        for idx, show in enumerate(tvshows):
            if (self.task_context and self.task_context.abort_flag.is_requested()) or self.progress.is_cancelled():
                self.cancelled = True
                break

            self.scanned_count += 1
            show_id = show.get("tvshowid")
            title = show.get("label", xbmc.getLocalizedString(13205))
            file_path = show.get("file", "")
            current_art = show.get("art", {})

            percent = int((idx / total) * 100)
            message = f"Scanning: {title}\nProgress: {idx + 1}/{total} | Found: {self.found_count} | Cached: {self.skipped_cached} | Existing: {self.skipped_existing}"
            self.progress.update(percent, message)

            if not show_id or not file_path:
                continue

            gif_path = self._find_gif(file_path)

            if gif_path:
                self.accessed_paths.add(gif_path)

                if not self.force_full_rescan and self._should_skip_gif(gif_path):
                    self.skipped_cached += 1
                    log("Artwork", f"GIF scan: Skipped cached GIF for tvshowid={show_id} ({title}): {gif_path}", xbmc.LOGDEBUG)
                    continue

                log("Artwork", f"GIF scan: Setting GIF for tvshowid={show_id} ({title}): {gif_path}", xbmc.LOGDEBUG)
                if self._set_tvshow_art(show_id, title, gif_path):
                    self._update_cache(gif_path)
                    self.found_count += 1
                else:
                    log("Artwork", f"GIF scan: Failed to apply GIF for tvshowid={show_id} ({title})", xbmc.LOGWARNING)
            else:
                if current_art.get("animatedposter"):
                    self.skipped_existing += 1
                else:
                    log("Artwork", f"GIF scan: No matching GIF found for tvshowid={show_id} ({title}), folder={os.path.dirname(file_path)}", xbmc.LOGDEBUG)


    def _find_gif(self, file_path: str) -> Optional[str]:
        """
        Look for gif files in the same folder as the media file.

        Matching strategy:
        1. Try exact match first (e.g., "poster.gif")
        2. Try suffix match (e.g., "movie.poster.gif", "3.10.to.Yuma.2007.poster.gif")
        3. If multiple suffix matches, prioritize shortest filename (most specific)

        Args:
            file_path: Path to media file

        Returns:
            Path to gif file if found, None otherwise
        """
        if not file_path:
            return None

        try:
            if file_path.startswith("stack://"):
                stack_content = file_path.replace("stack://", "")
                if " , " in stack_content:
                    file_path = stack_content.split(" , ")[0]
                else:
                    file_path = stack_content.split(",")[0].strip()

            if file_path.startswith("bluray://"):
                import urllib.parse
                hostname = file_path[9:]
                if "/" in hostname:
                    hostname = hostname.split("/")[0]
                hostname = urllib.parse.unquote(hostname)
                if hostname.startswith("udf://"):
                    file_path = urllib.parse.unquote(hostname[6:])
                else:
                    file_path = hostname

            file_path = xbmcvfs.translatePath(file_path)

            folder = os.path.dirname(file_path)

            if not os.path.isdir(folder):
                return None

            # Try exact match first (backwards compatible, fastest)
            for pattern in self.patterns:
                gif_path = os.path.join(folder, pattern)
                if os.path.isfile(gif_path):
                    return gif_path

            try:
                files = os.listdir(folder)
            except OSError as e:
                log("Artwork", f"Cannot list directory '{folder}': {str(e)}", xbmc.LOGWARNING)
                return None

            matches = []
            for pattern in self.patterns:
                pattern_lower = pattern.lower()
                pattern_base, pattern_ext = os.path.splitext(pattern_lower)

                # If pattern has no extension or wrong extension, treat whole pattern as base
                if pattern_ext != '.gif':
                    pattern_base = pattern_lower

                for filename in files:
                    file_base, file_ext = os.path.splitext(filename)

                    # Must be a .gif file and basename must end with pattern base
                    if file_ext.lower() == '.gif' and file_base.lower().endswith(pattern_base):
                        matches.append((filename, len(filename)))

            # Return shortest match (most specific)
            if matches:
                matches.sort(key=lambda x: x[1])
                return os.path.join(folder, matches[0][0])

            return None

        except Exception as e:
            log("Artwork", f"Error finding gif for '{file_path}': {str(e)}", xbmc.LOGERROR)
            return None

    def _set_movie_art(self, movie_id: int, title: str, gif_path: str) -> bool:
        """
        Set animatedposter art for a movie.

        Args:
            movie_id: Kodi movie ID
            title: Movie title
            gif_path: Path to gif file

        Returns:
            True if successful, False otherwise
        """
        try:
            file_exists = xbmcvfs.exists(gif_path)
            if not file_exists:
                log("Artwork", f"GIF file does not exist for movieid={movie_id} ({title}): {gif_path}", xbmc.LOGWARNING)
                return False

            resp = request(
                "VideoLibrary.SetMovieDetails",
                {
                    "movieid": movie_id,
                    "art": {
                        "animatedposter": gif_path
                    }
                }
            )
            if resp is None:
                log("Artwork", f"JSON-RPC returned None for movieid={movie_id} ({title}), path={gif_path}", xbmc.LOGWARNING)
                return False

            log("Artwork", f"Successfully set animatedposter for movieid={movie_id} ({title}), response: {resp}", xbmc.LOGDEBUG)
            return True
        except Exception as e:
            log("Artwork", f"Exception setting art for movieid={movie_id} ({title}), path={gif_path}: {str(e)}", xbmc.LOGERROR)
            return False

    def _set_tvshow_art(self, tvshow_id: int, title: str, gif_path: str) -> bool:
        """
        Set animatedposter art for a TV show.

        Args:
            tvshow_id: Kodi TV show ID
            title: TV show title
            gif_path: Path to gif file

        Returns:
            True if successful, False otherwise
        """
        try:
            file_exists = xbmcvfs.exists(gif_path)
            if not file_exists:
                log("Artwork", f"GIF file does not exist for tvshowid={tvshow_id} ({title}): {gif_path}", xbmc.LOGWARNING)
                return False

            resp = request(
                "VideoLibrary.SetTVShowDetails",
                {
                    "tvshowid": tvshow_id,
                    "art": {
                        "animatedposter": gif_path
                    }
                }
            )
            if resp is None:
                log("Artwork", f"JSON-RPC returned None for tvshowid={tvshow_id} ({title}), path={gif_path}", xbmc.LOGWARNING)
                return False

            log("Artwork", f"Successfully set animatedposter for tvshowid={tvshow_id} ({title}), response: {resp}", xbmc.LOGDEBUG)
            return True
        except Exception as e:
            log("Artwork", f"Exception setting art for tvshowid={tvshow_id} ({title}), path={gif_path}: {str(e)}", xbmc.LOGERROR)
            return False

    def _should_skip_gif(self, gif_path: str) -> bool:
        """
        Check if GIF should be skipped in incremental mode.

        Args:
            gif_path: Path to GIF file

        Returns:
            True if GIF is cached and unchanged (safe to skip)
        """
        cached_entry = gif_db.get_cached_gif(gif_path)
        if not cached_entry:
            return False

        cached_mtime = cached_entry.get("mtime")
        if cached_mtime is None:
            return False

        try:
            current_mtime = os.path.getmtime(gif_path)
            # Compare mtimes (allow 1 second tolerance for filesystem precision)
            if abs(current_mtime - float(cached_mtime)) < 1.0:
                return True
        except (OSError, ValueError):
            return False

        return False

    def _update_cache(self, gif_path: str) -> None:
        """
        Update cache entry for a GIF file.

        Args:
            gif_path: Path to GIF file
        """
        try:
            mtime = os.path.getmtime(gif_path)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            gif_db.update_gif_cache(gif_path, mtime, current_time)
        except OSError:
            pass

    def cleanup_stale_cache(self) -> int:
        """
        Remove cache entries for GIF files not found during this scan.

        Returns:
            Number of stale entries removed
        """
        return gif_db.cleanup_stale_gifs(self.accessed_paths)

    def show_summary(self) -> None:
        """Show completion notification."""
        if self.cancelled:
            message = ADDON.getLocalizedString(32593).format(self.found_count, self.skipped_cached, self.skipped_existing)
        else:
            message = ADDON.getLocalizedString(32594).format(self.found_count, self.skipped_cached, self.skipped_existing)

        show_notification(
            ADDON.getLocalizedString(32192),
            message,
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
