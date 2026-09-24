from __future__ import annotations

from typing import cast

import xbmc
import xbmcgui

from lib.dialog.base import InfoDialogBase, ADDON_PATH

XML_FILE = 'script-skin-info-service-DialogImageViewer.xml'

_IMAGES_CONTROL_ID = 1520


class DialogImageViewer(InfoDialogBase):
    """Image browser bound to a plugin path, opened at the chosen item."""

    def __init__(self, *args, **kwargs):
        self._images_path: str = kwargs.pop('images_path', '')
        self._selected_index: int = kwargs.pop('selected_index', 0)
        super().__init__(*args, **kwargs)
        if self._images_path:
            self.setProperty('container.viewer.path', self._images_path)

    def onInit(self) -> None:
        """Mark topmost and jump the list to the item that was opened."""
        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        self.mark_topmost()
        try:
            control = cast(xbmcgui.ControlList, self.getControl(_IMAGES_CONTROL_ID))
            control.selectItem(self._selected_index)
        except Exception:
            pass


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
