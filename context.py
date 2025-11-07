"""Context menu handler for Skin Info Service."""
import sys
import xbmc
import xbmcaddon
import xbmcgui

if __name__ == '__main__':
    addon = xbmcaddon.Addon()

    listitem = sys.listitem.getVideoInfoTag()
    db_id = listitem.getDbId()
    db_type = listitem.getMediaType()

    if not db_id or not db_type:
        sys.exit()

    menu_items = []
    actions = []

    if addon.getSettingBool('context_show_review_artwork'):
        menu_items.append(addon.getLocalizedString(32100))
        actions.append('review_artwork')

    if db_type in ('movie', 'tvshow', 'episode') and addon.getSettingBool('context_show_update_ratings'):
        menu_items.append(addon.getLocalizedString(32101))
        actions.append('update_ratings')

    if not menu_items:
        sys.exit()

    selected = xbmcgui.Dialog().contextmenu(menu_items)

    if selected < 0:
        sys.exit()

    action = actions[selected]

    xbmc.executebuiltin(
        f'RunScript(script.skin.info.service,{action},dbid={db_id},dbtype={db_type})'
    )
