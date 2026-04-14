"""Context menu handler for Skin Info Service."""
from __future__ import annotations

import sys
import xbmc
import xbmcaddon
import xbmcgui


def main() -> None:
    addon: xbmcaddon.Addon = xbmcaddon.Addon()

    listitem = getattr(sys, 'listitem', None)
    if listitem is None:
        return

    db_id: int = 0
    db_type: str = ''

    videotag = listitem.getVideoInfoTag()
    if videotag:
        db_id = videotag.getDbId()
        db_type = videotag.getMediaType()

    if not db_id or not db_type:
        musictag = listitem.getMusicInfoTag()
        if musictag:
            db_id = musictag.getDbId()
            db_type = musictag.getMediaType()

    if not db_id or not db_type:
        return

    menu_items: list[str] = []
    actions: list[str] = []

    artwork_types = ('movie', 'tvshow', 'episode', 'season', 'set', 'musicvideo', 'artist', 'album')
    ratings_types = ('movie', 'tvshow', 'episode')

    if db_type in artwork_types and addon.getSettingBool('context_show_review_artwork'):
        menu_items.append(addon.getLocalizedString(32100))
        actions.append('review_artwork')

    if db_type in artwork_types and addon.getSettingBool('context_show_download_artwork'):
        menu_items.append(addon.getLocalizedString(32290))
        actions.append('download_artwork')

    if db_type in ratings_types and addon.getSettingBool('context_show_update_ratings'):
        menu_items.append(addon.getLocalizedString(32101))
        actions.append('update_ratings')

    if addon.getSettingBool('context_show_edit_metadata'):
        menu_items.append(addon.getLocalizedString(32103))
        actions.append('edit')

    if not menu_items:
        return

    selected: int = xbmcgui.Dialog().contextmenu(menu_items)

    if selected < 0:
        return

    action: str = actions[selected]

    xbmc.executebuiltin(
        f'RunScript(script.skin.info.service,action={action},dbid={db_id},dbtype={db_type})'
    )
