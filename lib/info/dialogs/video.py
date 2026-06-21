from __future__ import annotations

from typing import Dict, Optional

import xbmc
import xbmcgui

from lib.info.dialogs.base import InfoDialogBase, ADDON_PATH
from lib.kodi.client import log

XML_FILE = 'script-skin-info-service-DialogVideoInfo.xml'


class DialogVideoInfo(InfoDialogBase):

    def __init__(self, *args, **kwargs):
        self._media_type: str = kwargs.pop('media_type', '')
        self._dbid: str = kwargs.pop('dbid', '')
        self._tmdb_id: str = kwargs.pop('tmdb_id', '')
        self._imdb_id: str = kwargs.pop('imdb_id', '')
        self._online_props: Dict[str, str] = kwargs.pop('online_props', {})
        super().__init__(*args, **kwargs)

    def onInit(self) -> None:
        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        self._set_video_properties()
        self._bind_containers()

    def _set_video_properties(self) -> None:
        props = dict(self._online_props)
        props['MediaType'] = self._media_type
        if self._dbid:
            props['DBID'] = self._dbid
        if self._tmdb_id:
            props['tmdb_id'] = self._tmdb_id
        if self._imdb_id:
            props['imdb_id'] = self._imdb_id
        self._set_window_properties(props)

    def _bind_containers(self) -> None:
        base_url = 'plugin://script.skin.info.service/'
        containers: Dict[str, str] = {}

        if not self._media_type:
            return

        # tmdb_id takes precedence for online lookups; library dbid is the fallback when present.
        id_args = []
        if self._tmdb_id:
            id_args.append(f"tmdb_id={self._tmdb_id}")
        if self._dbid:
            id_args.append(f"dbid={self._dbid}")
        if not id_args:
            return
        id_query = '&'.join(id_args)

        containers['cast'] = (
            f"{base_url}?action=get_cast"
            f"&dbtype={self._media_type}&online=true&{id_query}"
        )

        if self._media_type in ('movie', 'tvshow'):
            containers['crew'] = f"{base_url}?action=crew&dbtype={self._media_type}&{id_query}"
            containers['recommendations'] = (
                f"{base_url}?action=tmdb_recommendations&dbtype={self._media_type}&{id_query}"
            )
            containers['similar'] = (
                f"{base_url}?action=similar&dbtype={self._media_type}&{id_query}"
            )

        for name, path in containers.items():
            self.setProperty(f"container.{name}.path", path)

    def onAction(self, action: xbmcgui.Action) -> None:
        if self.is_close_action(action):
            self.close()


def open_video_info(
    tmdb_id: str = '',
    imdb_id: str = '',
    media_type: str = '',
    dbid: str = '',
    online_props: Optional[Dict[str, str]] = None,
    set_home_props: bool = False,
) -> None:
    if not online_props:
        if not tmdb_id and not imdb_id:
            log("General", "DialogVideoInfo: No tmdb_id or imdb_id", xbmc.LOGWARNING)
            return

        from lib.service.online import fetch_all_online_data
        online_props = fetch_all_online_data(
            media_type=media_type,
            imdb_id=imdb_id,
            tmdb_id=tmdb_id,
        )

        if not online_props:
            log("General", f"DialogVideoInfo: No online data for tmdb={tmdb_id}", xbmc.LOGWARNING)
            return

    dialog = DialogVideoInfo(
        XML_FILE,
        ADDON_PATH,
        'default',
        '1080i',
        media_type=media_type,
        dbid=dbid,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        online_props=online_props,
        set_home_props=set_home_props,
    )
    dialog.doModal()
    del dialog
