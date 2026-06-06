from __future__ import annotations

from typing import Dict
from lib.dialog.base import DialogBase
from lib.kodi.client import ADDON


ADDON_PATH = ADDON.getAddonInfo('path')


class InfoDialogBase(DialogBase):

    def __init__(self, *args, **kwargs):
        self._set_home_props: bool = kwargs.pop('set_home_props', False)
        super().__init__(*args, **kwargs)

    def _set_window_properties(self, props: Dict[str, str]) -> None:
        self.set_properties(props)
        if self._set_home_props:
            import xbmcgui as _xbmcgui
            home = _xbmcgui.Window(10000)
            for key, value in props.items():
                if value:
                    home.setProperty(key, str(value))

    @staticmethod
    def create(xml_name: str, cls, **kwargs):
        return cls(
            xml_name,
            ADDON_PATH,
            'default',
            '1080i',
            **kwargs
        )
