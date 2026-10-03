from __future__ import annotations

import threading
from typing import cast, Final

import xbmc
import xbmcgui

from lib.dialog.base import InfoDialogBase, ADDON_PATH

XML_FILE: Final = 'script-skin-info-service-DialogImageViewer.xml'

_IMAGES_CONTROL_ID: Final = 1520
_LOAD_POLLS: Final = 50


class DialogImageViewer(InfoDialogBase):
    """Image browser bound to a plugin path, opened at the chosen item."""

    def __init__(self, *args, **kwargs):
        self._images_path: str = kwargs.pop('images_path', '')
        self._selected_index: int = kwargs.pop('selected_index', 0)
        super().__init__(*args, **kwargs)
        if self._images_path:
            self.setProperty('container.viewer.path', self._images_path)

    def onInit(self) -> None:
        """Mark topmost and jump the list to the item that was opened once it loads."""
        xbmc.executebuiltin('Dialog.Close(busydialognocancel,true)')
        self.mark_topmost()
        threading.Thread(target=self._select_when_loaded, daemon=True).start()

    def _select_when_loaded(self) -> None:
        """Select the opened item once the list has loaded, then flag the viewer ready."""
        monitor = xbmc.Monitor()
        loaded = (f'Integer.IsGreater(Container({_IMAGES_CONTROL_ID}).NumItems,0)'
                  f' + !Container({_IMAGES_CONTROL_ID}).IsUpdating')
        for _ in range(_LOAD_POLLS):
            if self._closing or monitor.abortRequested():
                return
            if xbmc.getCondVisibility(loaded):
                break
            monitor.waitForAbort(0.1)
        if self._selected_index:
            try:
                control = cast(xbmcgui.ControlList, self.getControl(_IMAGES_CONTROL_ID))
                control.selectItem(self._selected_index)
            except Exception:
                pass
        self.setProperty('viewer_ready', 'true')


def open_image_viewer(
    images_path: str,
    selected_index: int = 0,
) -> None:
    """Open the image viewer on a plugin path; an empty path opens nothing."""
    if not images_path:
        return

    dialog = DialogImageViewer(
        XML_FILE,
        ADDON_PATH,
        'default',
        '1080i',
        images_path=images_path,
        selected_index=selected_index,
    )
    dialog.doModal()
    del dialog
