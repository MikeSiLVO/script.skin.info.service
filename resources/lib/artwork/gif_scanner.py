"""Find and add animated GIF posters to library items."""
from __future__ import annotations

import os
import json
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from typing import Optional, Dict
from datetime import datetime

from resources.lib.kodi import request
from resources.lib import task_manager
from resources.lib.ui_helper import ProgressDialogHelper, show_menu_with_cancel, format_operation_report
from resources.lib.database import init_database
from resources.lib.database.workflow import save_operation_stats, get_last_operation_stats

ADDON = xbmcaddon.Addon()

CACHE_FILE = xbmcvfs.translatePath(
    "special://profile/addon_data/script.skin.info.service/.gif_scan_cache.json"
)


def run_scanner(scope: Optional[str] = None, scan_mode: Optional[str] = None) -> None:
    """
    Run gif poster scanner with dialog-based options.

    Args:
        scope: "movies", "tvshows", "all", or None (shows dialog)
        scan_mode: "incremental", "full", or None (uses setting)
    """
    init_database()

    last_stats = get_last_operation_stats('gif_scan')

    options = [("Scan for Animated Posters", "scan")]
    if last_stats:
        options.append(("View Last Report", "report"))

    choice, cancelled = show_menu_with_cancel("Animated Art Scanner", options)

    if cancelled:
        return

    if choice is None:
        return

    if choice == "report":
        if last_stats:
            report_text = format_operation_report(
                'gif_scan',
                last_stats['stats'],
                last_stats['timestamp'],
                last_stats.get('scope')
            )
            xbmcgui.Dialog().textviewer("GIF Scanner - Last Run", report_text)
        return

    if scope is None:
        scope = _select_scope()
        if scope is None:
            return

    scope = scope.lower()
    valid_scopes = ("movies", "tvshows", "all")
    if scope not in valid_scopes:
        xbmc.log(
            f"SkinInfo: Invalid scope '{scope}' for gif scanner. Expected one of: {', '.join(valid_scopes)}",
            xbmc.LOGWARNING
        )
        xbmcgui.Dialog().notification(
            "Gif Poster Scanner",
            f"Invalid scope '{scope}'",
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
        xbmc.log(
            f"SkinInfo: Invalid scan mode '{scan_mode}'. Expected one of: {', '.join(valid_modes)}",
            xbmc.LOGWARNING
        )
        xbmcgui.Dialog().notification(
            "Gif Poster Scanner",
            f"Invalid scan mode '{scan_mode}'",
            xbmcgui.NOTIFICATION_WARNING,
            4000
        )
        return

    dialog = xbmcgui.Dialog()

    try:
        if task_manager.is_task_running():
            task_info = task_manager.get_task_info()
            current_task = task_info['name'] if task_info else "Unknown task"

            cancel_it = dialog.yesno(
                "Task Already Running",
                f"[B]{current_task}[/B] is currently running.[CR][CR]Cancel it and start Animated Art Scanner?",
                nolabel="No",
                yeslabel="Yes, Cancel It"
            )

            if not cancel_it:
                return

            task_manager.cancel_task()
            monitor = xbmc.Monitor()
            while task_manager.is_task_running() and not monitor.abortRequested():
                monitor.waitForAbort(0.1)

        with task_manager.TaskContext("Animated Art Scanner") as ctx:
            progress = ProgressDialogHelper(use_background=False, heading="Animated Art Scanner")
            progress.create("[B]CANCEL TO RESUME LATER[/B][CR]Initializing...")

            cancelled = _run_scan_operation(scope, scan_mode, progress, task_context=ctx)

            progress.close()

            if cancelled:
                resume_bg = dialog.yesno(
                    "Scan Cancelled",
                    "Scan paused. Resume in background?",
                    nolabel="Close",
                    yeslabel="Resume in BG"
                )

                if resume_bg:
                    if task_manager.is_task_running():
                        dialog.ok("Task Already Running", "Another background task is currently running.[CR]Cannot resume in background.")
                        return
                    with task_manager.TaskContext("Animated Art Scanner") as bg_ctx:
                        progress_bg = ProgressDialogHelper(use_background=True, heading="Animated Art Scanner")
                        progress_bg.create("Resuming scan...")
                        _run_scan_operation(scope, scan_mode, progress_bg, task_context=bg_ctx)
                        progress_bg.close()

                        dialog.notification(
                            "Animated Art Scanner",
                            "Background scan complete",
                            xbmcgui.NOTIFICATION_INFO,
                            3000
                        )

    except Exception as e:
        xbmc.log(f"SkinInfo GifScanner: Scan failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok("Animated Art Scanner", f"Scan failed:[CR]{str(e)}")


def _run_scan_operation(
    scope: str,
    scan_mode: str,
    progress: ProgressDialogHelper,
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
    enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')

    if enable_debug:
        xbmc.log(f"SkinInfo GifScanner: Starting scan - scope: {scope}, mode: {scan_mode}", xbmc.LOGDEBUG)

    gif_cache: Dict[str, Dict[str, float | str]] = {}
    if not force_full_rescan:
        gif_cache = _load_cache()

    scanner = GifScanner(patterns, force_full_rescan, gif_cache, progress, task_context)

    if scope in ("movies", "all"):
        scanner.scan_movies()
        if scanner.cancelled:
            return True

    if scope in ("tvshows", "all"):
        scanner.scan_tvshows()
        if scanner.cancelled:
            return True

    scanner.show_summary()

    if not scanner.cancelled:
        _save_cache(scanner.gif_cache)

    stats = {
        'found_count': scanner.found_count,
        'scanned_count': scanner.scanned_count,
        'skipped_count': scanner.skipped_count,
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
        ("all", "All (Movies + TV Shows)"),
        ("movies", "Movies Only"),
        ("tvshows", "TV Shows Only")
    ]

    labels = [label for _, label in options]
    choice = xbmcgui.Dialog().select("Scan for Gif Posters", labels)  # type: ignore[arg-type]

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
        cache = _load_cache()
        cache_info = f" ({len(cache)} GIFs cached)" if cache else " (no cache)"

        options = [
            ("incremental", f"Incremental Scan{cache_info}", "Skip unchanged GIFs, detect new/modified ones"),
            ("full", "Full Rescan", "Rescan all items, rebuild cache from scratch")
        ]

        labels = []
        for _, label, desc in options:
            labels.append(f"{label}\n{desc}")

        choice = xbmcgui.Dialog().select("Select scan mode", labels)

        if choice == -1:
            return None

        return options[choice][0]

    if setting_value in ("incremental", "full"):
        return setting_value

    return "incremental"


def _load_cache() -> Dict[str, Dict[str, float | str]]:
    """
    Load GIF cache from JSON file.

    Cache structure:
    {
        "/path/to/movie/poster.gif": {
            "mtime": 1705315200.5,
            "scanned_at": "2025-01-15 10:00:00"
        },
        ...
    }

    Returns:
        Dict of GIF paths to their cached metadata, or empty dict if not found
    """
    try:
        cache_path = xbmcvfs.translatePath(CACHE_FILE)
        if os.path.isfile(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                xbmc.log(f"SkinInfo: Loaded GIF cache with {len(cache)} entries", xbmc.LOGDEBUG)
                return cache
    except json.JSONDecodeError as e:
        xbmc.log(f"SkinInfo: GIF cache corrupted, will rebuild: {str(e)}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"SkinInfo: Error loading GIF cache: {str(e)}", xbmc.LOGDEBUG)

    return {}


def _save_cache(cache: Dict[str, Dict[str, float | str]]) -> None:
    """
    Save GIF cache to JSON file.

    Args:
        cache: Dict of GIF paths to their metadata
    """
    try:
        # Ensure addon_data directory exists
        addon_data_dir = xbmcvfs.translatePath("special://profile/addon_data/script.skin.info.service")
        if not xbmcvfs.exists(addon_data_dir):
            xbmcvfs.mkdirs(addon_data_dir)

        cache_path = xbmcvfs.translatePath(CACHE_FILE)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)

        xbmc.log(f"SkinInfo: Saved GIF cache with {len(cache)} entries", xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f"SkinInfo: Error saving GIF cache: {str(e)}", xbmc.LOGWARNING)


class GifScanner:
    """Scans for gif posters and updates Kodi's art database."""

    def __init__(
        self,
        patterns: list[str],
        force_full_rescan: bool,
        gif_cache: Dict[str, Dict[str, float | str]],
        progress: ProgressDialogHelper,
        task_context=None
    ):
        self.patterns = patterns
        self.force_full_rescan = force_full_rescan
        self.gif_cache = gif_cache
        self.progress = progress
        self.task_context = task_context
        self.found_count = 0
        self.scanned_count = 0
        self.skipped_count = 0
        self.cancelled = False

    def scan_movies(self) -> None:
        """Scan all movies for gif posters."""
        resp = request(
            "VideoLibrary.GetMovies",
            {
                "properties": ["file", "art", "dateadded"],
            }
        )

        if not resp:
            xbmc.log("SkinInfo: Failed to get movies list", xbmc.LOGWARNING)
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
            title = movie.get("label", "Unknown")
            file_path = movie.get("file", "")
            current_art = movie.get("art", {})

            percent = int((idx / total) * 100)
            message = f"Scanning: {title}\nProgress: {idx + 1}/{total} | Found: {self.found_count} | Skipped: {self.skipped_count}"
            self.progress.update(percent, message)

            if not file_path:
                continue

            gif_path = self._find_gif(file_path)

            if gif_path:
                if not self.force_full_rescan and self._should_skip_gif(gif_path):
                    self.skipped_count += 1
                    continue

                self._set_movie_art(movie_id, gif_path)
                self._update_cache(gif_path)
                self.found_count += 1
            elif current_art.get("animatedposter"):
                self.skipped_count += 1

            enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
            if enable_debug and ((idx + 1) % 10 == 0 or idx == total - 1):
                xbmc.log(
                    f"SkinInfo GifScanner: Movies progress: {idx+1}/{total} "
                    f"(found: {self.found_count}, skipped: {self.skipped_count})",
                    xbmc.LOGDEBUG
                )

    def scan_tvshows(self) -> None:
        """Scan all TV shows for gif posters."""
        resp = request(
            "VideoLibrary.GetTVShows",
            {
                "properties": ["file", "art", "dateadded"],
            }
        )

        if not resp:
            xbmc.log("SkinInfo: Failed to get TV shows list", xbmc.LOGWARNING)
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
            title = show.get("label", "Unknown")
            file_path = show.get("file", "")
            current_art = show.get("art", {})

            percent = int((idx / total) * 100)
            message = f"Scanning: {title}\nProgress: {idx + 1}/{total} | Found: {self.found_count} | Skipped: {self.skipped_count}"
            self.progress.update(percent, message)

            if not file_path:
                continue

            gif_path = self._find_gif(file_path)

            if gif_path:
                if not self.force_full_rescan and self._should_skip_gif(gif_path):
                    self.skipped_count += 1
                    continue

                self._set_tvshow_art(show_id, gif_path)
                self._update_cache(gif_path)
                self.found_count += 1
            elif current_art.get("animatedposter"):
                self.skipped_count += 1

            enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
            if enable_debug and ((idx + 1) % 10 == 0 or idx == total - 1):
                xbmc.log(
                    f"SkinInfo GifScanner: TV shows progress: {idx+1}/{total} "
                    f"(found: {self.found_count}, skipped: {self.skipped_count})",
                    xbmc.LOGDEBUG
                )

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
            # Handle both regular paths and stack:// paths
            if file_path.startswith("stack://"):
                file_path = file_path.replace("stack://", "").split(" , ")[0]

            file_path = xbmcvfs.translatePath(file_path)

            folder = os.path.dirname(file_path)

            if not os.path.isdir(folder):
                return None

            # Try exact match first (backwards compatible, fastest)
            for pattern in self.patterns:
                gif_path = os.path.join(folder, pattern)
                if os.path.isfile(gif_path):
                    return gif_path

            # Try suffix match
            try:
                files = os.listdir(folder)
            except OSError:
                return None

            matches = []
            for pattern in self.patterns:
                for filename in files:
                    if filename.lower().endswith(pattern.lower()) and filename.lower().endswith('.gif'):
                        matches.append((filename, len(filename)))

            # Return shortest match (most specific)
            if matches:
                matches.sort(key=lambda x: x[1])
                return os.path.join(folder, matches[0][0])

            return None

        except Exception as e:
            xbmc.log(f"SkinInfo: Error finding gif for '{file_path}': {str(e)}", xbmc.LOGERROR)
            return None

    def _set_movie_art(self, movie_id: int, gif_path: str) -> bool:
        """
        Set animatedposter art for a movie.

        Args:
            movie_id: Kodi movie ID
            gif_path: Path to gif file

        Returns:
            True if successful, False otherwise
        """
        try:
            resp = request(
                "VideoLibrary.SetMovieDetails",
                {
                    "movieid": movie_id,
                    "art": {
                        "animatedposter": gif_path
                    }
                }
            )
            return resp is not None
        except Exception as e:
            xbmc.log(f"SkinInfo: Error setting movie art: {str(e)}", xbmc.LOGERROR)
            return False

    def _set_tvshow_art(self, tvshow_id: int, gif_path: str) -> bool:
        """
        Set animatedposter art for a TV show.

        Args:
            tvshow_id: Kodi TV show ID
            gif_path: Path to gif file

        Returns:
            True if successful, False otherwise
        """
        try:
            resp = request(
                "VideoLibrary.SetTVShowDetails",
                {
                    "tvshowid": tvshow_id,
                    "art": {
                        "animatedposter": gif_path
                    }
                }
            )
            return resp is not None
        except Exception as e:
            xbmc.log(f"SkinInfo: Error setting TV show art: {str(e)}", xbmc.LOGERROR)
            return False

    def _should_skip_gif(self, gif_path: str) -> bool:
        """
        Check if GIF should be skipped in incremental mode.

        Args:
            gif_path: Path to GIF file

        Returns:
            True if GIF is cached and unchanged (safe to skip)
        """
        # Not in cache - needs scanning
        if gif_path not in self.gif_cache:
            return False

        cached_entry = self.gif_cache.get(gif_path, {})
        cached_mtime = cached_entry.get("mtime")
        if cached_mtime is None:
            return False

        try:
            current_mtime = os.path.getmtime(gif_path)
            # Compare mtimes (allow 1 second tolerance for filesystem precision)
            if abs(current_mtime - float(cached_mtime)) < 1.0:
                return True  # Unchanged, skip
        except (OSError, ValueError) as e:
            # If we can't get mtime, err on side of caution and rescan
            xbmc.log(f"SkinInfo: Could not get mtime for '{gif_path}': {str(e)}", xbmc.LOGDEBUG)
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
            self.gif_cache[gif_path] = {
                "mtime": mtime,
                "scanned_at": current_time
            }
        except OSError as e:
            # If we can't get mtime, log warning but continue
            xbmc.log(f"SkinInfo: Could not get mtime for '{gif_path}': {str(e)}", xbmc.LOGWARNING)

    def show_summary(self) -> None:
        """Show completion notification."""
        if self.cancelled:
            message = f"Scan cancelled. Found: {self.found_count} | Skipped: {self.skipped_count}"
        else:
            message = f"Scan complete! Found: {self.found_count} | Skipped: {self.skipped_count}"

        xbmcgui.Dialog().notification(
            "Gif Poster Scanner",
            message,
            xbmcgui.NOTIFICATION_INFO,
            5000
        )
