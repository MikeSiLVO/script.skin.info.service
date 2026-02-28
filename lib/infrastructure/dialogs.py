"""Dialog helper utilities for progress tracking and user interaction."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Union
import xbmc
import xbmcgui



class ProgressDialog:
    """
    Unified progress dialog manager supporting both foreground and background dialogs.

    Features:
    - Automatic dialog type selection (DialogProgress or DialogProgressBG)
    - Optional update throttling for performance
    - Flexible message formatting
    - Automatic percent clamping
    """

    def __init__(self, use_background: bool = False, heading: str = "Processing"):
        """
        Initialize progress dialog helper.

        Args:
            use_background: Use DialogProgressBG (True) or DialogProgress (False)
            heading: Dialog heading/title
        """
        self.use_background = use_background
        self.heading = heading
        self.dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
        self.last_percent = -1
        self.throttle_enabled = False
        self.throttle_min_items = 5
        self.monitor = xbmc.Monitor()

    def create(self, message: str = "") -> None:
        """
        Create and show the progress dialog.

        Args:
            message: Initial message to display
        """
        if self.dialog:
            try:
                self.dialog.close()
            except Exception:
                pass

        if self.use_background:
            self.dialog = xbmcgui.DialogProgressBG()
            self.dialog.create(self.heading, message)
        else:
            self.dialog = xbmcgui.DialogProgress()
            self.dialog.create(self.heading, message)

        self.last_percent = -1

    def update(self, percent: int, message: str = "", force: bool = False) -> None:
        """
        Update the progress dialog.

        Args:
            percent: Progress percentage (0-100)
            message: Message to display
            force: Force update even if throttling would skip it
        """
        if not self.dialog:
            return

        percent = max(0, min(100, percent))

        if self.throttle_enabled and not force:
            if percent == self.last_percent:
                return

        self.last_percent = percent

        if self.use_background:
            assert isinstance(self.dialog, xbmcgui.DialogProgressBG)
            self.dialog.update(percent, self.heading, message)
        else:
            assert isinstance(self.dialog, xbmcgui.DialogProgress)
            self.dialog.update(percent, message)

    def close(self) -> None:
        """Close the progress dialog."""
        if self.dialog:
            try:
                self.dialog.close()
            except Exception:
                pass
            finally:
                self.dialog = None
                self.last_percent = -1

    def is_cancelled(self) -> bool:
        """
        Check if user cancelled the dialog or Kodi requested abort.

        Returns:
            True if cancelled or abort requested, False otherwise
        """
        if self.monitor.abortRequested():
            return True

        if not self.dialog:
            return False

        if isinstance(self.dialog, xbmcgui.DialogProgress):
            return self.dialog.iscanceled()

        return False

    def enable_throttling(self, min_items: int = 5) -> None:
        """
        Enable update throttling to reduce UI overhead.

        Args:
            min_items: Minimum number of items between updates
        """
        self.throttle_enabled = True
        self.throttle_min_items = min_items

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False


def format_operation_report(operation: str, stats: dict, timestamp: str, scope: Optional[str] = None) -> str:
    """
    Format operation stats for display in Kodi dialogs.

    Args:
        operation: Operation type ('texture_precache', 'texture_cleanup', 'gif_scan')
        stats: Stats dictionary
        timestamp: ISO format timestamp
        scope: Optional scope string

    Returns:
        Formatted text with [CR] line breaks for Kodi dialogs
    """
    try:
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        formatted_time = timestamp

    lines = []

    if operation == 'texture_precache':
        lines.append("[B]Operation: Pre-Cache Library Artwork[/B]")
        lines.append(f"Completed: {formatted_time}")

        cached = stats.get('cached_count', 0)
        total = stats.get('total_count', 0)
        new = stats.get('new_count', 0)
        lines.append(f"Cached: {cached}/{total} ({new} new)")

        failed = stats.get('failed_count', 0)
        if failed > 0:
            lines.append(f"Failed: {failed}")

        if stats.get('cancelled'):
            lines.append("[B]Status: Cancelled[/B]")

    elif operation == 'texture_cleanup':
        lines.append("[B]Operation: Clean Orphaned Textures[/B]")
        lines.append(f"Completed: {formatted_time}")

        cached = stats.get('cached_count', 0)
        total = stats.get('total_count', 0)
        lines.append(f"Cached: {cached}/{total} in library")

        removed = stats.get('removed_count', 0)
        orphaned = stats.get('orphaned_count', 0)
        lines.append(f"Removed: {removed}/{orphaned} orphaned")

        if stats.get('cancelled'):
            lines.append("[B]Status: Cancelled[/B]")

    elif operation == 'gif_scan':
        lines.append("[B]Operation: Scan for Animated Posters[/B]")

        if scope:
            scope_label = scope.title() if scope != 'all' else 'All'
            lines.append(f"Scope: {scope_label}")

        lines.append(f"Completed: {formatted_time}")
        lines.append("")

        scan_mode = stats.get('scan_mode', 'incremental')
        mode_label = 'Full' if scan_mode == 'full' else 'Incremental'
        lines.append(f"Mode: {mode_label}")

        scanned = stats.get('scanned_count', 0)
        lines.append(f"Items Scanned: {scanned}")
        lines.append("")

        found = stats.get('found_count', 0)
        skipped_cached = stats.get('skipped_cached', stats.get('skipped_count', 0))
        skipped_existing = stats.get('skipped_existing', 0)

        lines.append("[B]Results:[/B]")
        lines.append(f"  New GIFs Added: {found}")
        lines.append(f"  Cached (Unchanged): {skipped_cached}")
        lines.append(f"  Already Set: {skipped_existing}")

        total_processed = found + skipped_cached + skipped_existing
        lines.append(f"  Total Processed: {total_processed}")

        if stats.get('cancelled'):
            lines.append("")
            lines.append("[B]Status: Cancelled[/B]")

    else:
        lines.append(f"[B]Operation: {operation}[/B]")
        lines.append(f"Completed: {formatted_time}")
        lines.append(f"Stats: {stats}")

    return "[CR]".join(lines)


def show_notification(
    heading: str,
    message: str,
    icon: int = xbmcgui.NOTIFICATION_INFO,
    duration: int = 3000
) -> None:
    """Show notification dialog."""
    xbmcgui.Dialog().notification(heading, message, icon, duration)


def show_ok(heading: str, message: str) -> None:
    """Show OK dialog."""
    xbmcgui.Dialog().ok(heading, message)


def show_yesno(
    heading: str,
    message: str,
    nolabel: str | None = None,
    yeslabel: str | None = None
) -> bool:
    """Show yes/no dialog."""
    kwargs = {}
    if nolabel is not None:
        kwargs['nolabel'] = nolabel
    if yeslabel is not None:
        kwargs['yeslabel'] = yeslabel
    return xbmcgui.Dialog().yesno(heading, message, **kwargs)


def show_yesnocustom(
    heading: str,
    message: str,
    customlabel: str,
    nolabel: str = "",
    yeslabel: str = ""
) -> int:
    """
    Show yes/no/custom dialog.

    Returns:
        0 = No button
        1 = Yes button
        2 = Custom button
        -1 = Cancelled
    """
    return xbmcgui.Dialog().yesnocustom(
        heading,
        message,
        customlabel=customlabel,
        nolabel=nolabel or "No",
        yeslabel=yeslabel or "Yes"
    )


def show_textviewer(heading: str, text: str) -> None:
    """Show text viewer dialog."""
    xbmcgui.Dialog().textviewer(heading, text)


def show_select(
    heading: str,
    options: list[str],
    preselect: int = -1
) -> int:
    """Show select dialog."""
    return xbmcgui.Dialog().select(heading, options, preselect=preselect)


def show_input(
    heading: str,
    default: str = "",
    input_type: int = xbmcgui.INPUT_ALPHANUM
) -> str:
    """Show input dialog."""
    return xbmcgui.Dialog().input(heading, default, type=input_type)


def show_error(message: str) -> None:
    """Show error notification."""
    show_notification(xbmc.getLocalizedString(257), message, xbmcgui.NOTIFICATION_ERROR, 5000)


def show_warning(message: str) -> None:
    """Show warning notification."""
    show_notification(xbmc.getLocalizedString(14117), message, xbmcgui.NOTIFICATION_WARNING, 4000)


def show_info(message: str) -> None:
    """Show info notification."""
    show_notification(xbmc.getLocalizedString(29915), message, xbmcgui.NOTIFICATION_INFO, 3000)


