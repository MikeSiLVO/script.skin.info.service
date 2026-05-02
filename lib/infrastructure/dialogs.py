"""Dialog helper utilities for progress tracking and user interaction."""
from __future__ import annotations

from typing import Optional, Union
import xbmc
import xbmcgui



class ProgressDialog:
    """Context-managed progress dialog wrapper that picks `DialogProgress` or `DialogProgressBG` and clamps percent.

    `fg_message_prefix` is prepended (with a `[CR]`) only in foreground mode — useful for
    cancel-hint banners that don't apply to background dialogs.
    """

    def __init__(self, use_background: bool = False, heading: str = "Processing",
                 fg_message_prefix: str = ""):
        self.use_background = use_background
        self.heading = heading
        self.fg_message_prefix = fg_message_prefix
        self.dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
        self.last_percent = -1
        self.throttle_enabled = False
        self.monitor = xbmc.Monitor()

    def create(self, message: str = "") -> None:
        """Create and show the dialog. Closes any existing dialog first."""
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
        """Update dialog percent/message. Skips no-op updates when throttling is on unless `force=True`."""
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
            full_message = f"{self.fg_message_prefix}[CR]{message}" if self.fg_message_prefix and message else message
            self.dialog.update(percent, full_message)

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
        """True if the user cancelled the dialog or Kodi requested abort."""
        if self.monitor.abortRequested():
            return True

        if not self.dialog:
            return False

        if isinstance(self.dialog, xbmcgui.DialogProgress):
            return self.dialog.iscanceled()

        return False

    def enable_throttling(self) -> None:
        """Enable update throttling to skip updates when percent hasn't changed."""
        self.throttle_enabled = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


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


def show_yesnocustom(heading: str, message: str, customlabel: str,
                     nolabel: str = "", yeslabel: str = "") -> int:
    """Show yes/no/custom dialog. Returns `0`=No, `1`=Yes, `2`=Custom, `-1`=Cancelled."""
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


