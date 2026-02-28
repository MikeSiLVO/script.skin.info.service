"""Entry point for script.skin.info.service."""
import sys
import xbmc
from typing import Optional
from lib.kodi.client import log
from lib.service import blur


def _blur_image_and_set_property(source: str, prefix: str = "", radius: Optional[int] = None, window: str = "home") -> None:
    """
    Blur image and set window properties.

    Args:
        source: Image path or URL to blur
        prefix: Optional prefix for property names (creates SkinInfo.{prefix}.BlurredImage)
        radius: Optional blur radius override (uses skin setting if None)
        window: Target window name or ID (default "home")
    """
    try:
        prop_base = f"SkinInfo.{prefix}." if prefix else "SkinInfo."

        if not source:
            xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage,{window})')
            xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage.Original,{window})')
            return

        if radius is None:
            blur_radius_str = xbmc.getInfoLabel("Skin.String(SkinInfo.BlurRadius)") or "40"
            try:
                radius = int(blur_radius_str)
                if radius < 1:
                    radius = 40
            except (ValueError, TypeError):
                radius = 40

        blurred_path = blur.blur_image(source, radius)

        if blurred_path:
            log("Blur", f"Setting {prop_base}BlurredImage on window {window} to: {blurred_path}", xbmc.LOGDEBUG)
            xbmc.executebuiltin(f'SetProperty({prop_base}BlurredImage,{blurred_path},{window})')
            xbmc.executebuiltin(f'SetProperty({prop_base}BlurredImage.Original,{source},{window})')
        else:
            log("Blur", "Blur failed, clearing properties", xbmc.LOGDEBUG)
            xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage,{window})')
            xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage.Original,{window})')

    except Exception as e:
        log("Blur", f"RunScript blur failed: {e}", xbmc.LOGERROR)
        prop_base = f"SkinInfo.{prefix}." if prefix else "SkinInfo."
        xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage,{window})')
        xbmc.executebuiltin(f'ClearProperty({prop_base}BlurredImage.Original,{window})')


def _parse_args(start_index: int) -> dict:
    """Parse script arguments supporting both positional and key=value formats.

    Args:
        start_index: Index in sys.argv to start parsing from

    Returns:
        Dictionary of parsed arguments
    """
    args = {}
    positional_index = 0

    for i in range(start_index, len(sys.argv)):
        arg = sys.argv[i]

        if '=' in arg:
            key, value = arg.split('=', 1)
            args[key.strip()] = value.strip()
        else:
            args[positional_index] = arg
            positional_index += 1

    return args


def main() -> None:

    if len(sys.argv) > 1:
        args = _parse_args(1)

        action = args.get('action', '')
        dialog = args.get('dialog', '')

        if not action and not dialog:
            first_arg = sys.argv[1].lower().strip()
            if '=' not in first_arg:
                log("General", f"Invalid syntax '{first_arg}'. Use action=name or dialog=type", xbmc.LOGERROR)
                return

        if dialog:
            from lib.skin.dialogs import (
                dialog_yesno, dialog_yesnocustom, dialog_ok, dialog_select,
                dialog_multiselect, dialog_contextmenu, dialog_input, dialog_numeric,
                dialog_textviewer, dialog_notification, dialog_browse, dialog_colorpicker,
                dialog_progress
            )

            dialog_map = {
                'yesno': dialog_yesno,
                'yesnocustom': dialog_yesnocustom,
                'ok': dialog_ok,
                'select': dialog_select,
                'multiselect': dialog_multiselect,
                'contextmenu': dialog_contextmenu,
                'input': dialog_input,
                'numeric': dialog_numeric,
                'textviewer': dialog_textviewer,
                'notification': dialog_notification,
                'browse': dialog_browse,
                'colorpicker': dialog_colorpicker,
                'progress': dialog_progress,
            }

            dialog_func = dialog_map.get(dialog.lower())
            if dialog_func:
                dialog_func(**args)
            else:
                log("General", f"Unknown dialog type '{dialog}'", xbmc.LOGERROR)
            return

        valid_actions = ("tools", "settings_action", "review_artwork", "download_artwork", "update_ratings", "edit",
                         "arttest", "multiarttest", "blur", "colorpicker",
                         "split_string", "urlencode", "urldecode", "math",
                         "copy_item", "container_labels", "refresh_counter", "file_exists", "json",
                         "container_move", "get_setting", "set_setting", "toggle_setting", "reset_setting",
                         "playall", "playrandom", "person_info", "tmdb_search", "online_fetch",
                         "search_library_person")

        if not action:
            log("General", "No action or dialog specified", xbmc.LOGERROR)
            return

        if action == "colorpicker":
            from lib.skin.colorpicker import colorpicker
            colorpicker(**args)
            return

        elif action == "blur":
            source = args.get('source', "")

            if source.startswith('$'):
                source = xbmc.getInfoLabel(source)

            prefix = args.get('prefix', "Custom")
            window = args.get('window_id', "home")
            radius = args.get('radius')

            if radius is not None:
                try:
                    radius = int(radius)
                except (ValueError, TypeError):
                    radius = None

            _blur_image_and_set_property(source, prefix, radius, window)
            return

        elif action == "split_string":
            from lib.skin.strings import split_string
            string = args.get('string', "")
            if string.startswith('$'):
                string = xbmc.getInfoLabel(string)
            separator = args.get('separator', "|")
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            split_string(string, separator, prefix, window)
            return

        elif action == "urlencode":
            from lib.skin.strings import urlencode
            string = args.get('string', "")
            if string.startswith('$'):
                string = xbmc.getInfoLabel(string)
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            urlencode(string, prefix, window)
            return

        elif action == "urldecode":
            from lib.skin.strings import urldecode
            string = args.get('string', "")
            if string.startswith('$'):
                string = xbmc.getInfoLabel(string)
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            urldecode(string, prefix, window)
            return

        elif action == "math":
            from lib.skin.math import evaluate_math
            expression = args.get('expression', "")
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            evaluate_math(expression, prefix, window)
            return

        elif action == "copy_item":
            from lib.skin.properties import copy_container_item
            container = args.get('container', "")
            infolabels = args.get('infolabels', '')
            artwork = args.get('artwork', '')
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            copy_container_item(container, infolabels, artwork, prefix, window)
            return

        elif action == "container_labels":
            from lib.skin.properties import aggregate_container_labels
            container = args.get('container', "")
            infolabel = args.get('infolabel', "")
            separator = args.get('separator', ' / ')
            prefix = args.get('prefix', 'SkinInfo')
            window = args.get('window', 'home')
            aggregate_container_labels(container, infolabel, separator, prefix, window)
            return

        elif action == "refresh_counter":
            from lib.skin.properties import refresh_counter
            uid = args.get('uid', "")
            prefix = args.get('prefix', 'SkinInfo')
            refresh_counter(uid, prefix)
            return

        elif action == "file_exists":
            from lib.skin.files import check_file_exists
            paths = args.get('paths', "")
            separator = args.get('separator', '|')
            prefix = args.get('prefix', '')
            window = args.get('window', 'home')
            check_file_exists(paths, separator, prefix, window)
            return

        elif action == "json":
            from lib.skin.json import execute_json_presets
            presets = args.get('presets', "")
            execute_json_presets(presets)
            return

        elif action == "container_move":
            from lib.skin.container import move_to_position
            main_focus = args.get('main_focus', "")
            main_position = args.get('main_position')
            main_action = args.get('main_action')
            next_focus = args.get('next_focus')
            next_position = args.get('next_position')
            next_action = args.get('next_action')
            move_to_position(main_focus, main_position, main_action, next_focus, next_position, next_action)
            return

        elif action == "get_setting":
            from lib.skin.settings import get_setting
            setting = args.get('setting', "")
            prefix = args.get('prefix', 'SkinInfo')
            window = args.get('window', 'home')
            get_setting(setting, prefix, window)
            return

        elif action == "set_setting":
            from lib.skin.settings import set_setting
            setting = args.get('setting', "")
            value = args.get('value', "")
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.isdigit():
                value = int(value)
            set_setting(setting, value)
            return

        elif action == "toggle_setting":
            from lib.skin.settings import toggle_setting
            setting = args.get('setting', "")
            toggle_setting(setting)
            return

        elif action == "reset_setting":
            from lib.skin.settings import reset_setting
            setting = args.get('setting', "")
            reset_setting(setting)
            return

        elif action == "update_library_ratings":
            from lib.rating.updater import update_library_ratings
            media_type = args.get('dbtype', 'movie').lower()
            use_background = args.get('background', 'true').lower() == 'true'

            if media_type not in ("movie", "tvshow", "episode"):
                media_type = "movie"

            update_library_ratings(media_type, use_background)
            return

        elif action == "playall":
            from lib.skin.playback import playall
            path = args.get('path', "")
            if path.startswith('$'):
                path = xbmc.getInfoLabel(path)
            playall(path)
            return

        elif action == "playrandom":
            from lib.skin.playback import playrandom
            path = args.get('path', "")
            if path.startswith('$'):
                path = xbmc.getInfoLabel(path)
            playrandom(path)
            return

        elif action == "tools":
            from lib.script.tools import run_tools
            run_tools()
            return

        elif action == "review_artwork":
            from lib.artwork.manager import run_art_fetcher_single
            dbid = args.get('dbid')
            dbtype = args.get('dbtype')
            run_art_fetcher_single(dbid, dbtype)
            return

        elif action == "download_artwork":
            from lib.artwork.manager import download_item_artwork
            dbid = args.get('dbid')
            dbtype = args.get('dbtype')
            download_item_artwork(dbid, dbtype)
            return

        elif action == "update_ratings":
            from lib.rating.menu import update_single_item_ratings
            dbid = args.get('dbid')
            dbtype = args.get('dbtype')
            update_single_item_ratings(dbid, dbtype)
            return

        elif action == "edit":
            from lib.editor.menu import run_editor
            dbid = args.get('dbid')
            dbtype = args.get('dbtype')
            run_editor(dbid, dbtype)
            return

        elif action == "settings_action":
            from lib.data.api import settings as api_settings
            sub_action = args.get('sub_action')
            provider = args.get('provider')

            if sub_action == "edit_api_key" and provider:
                api_settings.edit_api_key(provider)
            elif sub_action == "test_api_key" and provider:
                api_settings.test_api_key(provider)
            elif sub_action == "clear_api_key" and provider:
                api_settings.clear_api_key(provider)
            elif sub_action == "authorize_trakt":
                api_settings.authorize_trakt()
            elif sub_action == "test_trakt_connection":
                api_settings.test_trakt_connection()
            elif sub_action == "revoke_trakt_authorization":
                api_settings.revoke_trakt_authorization()
            return

        elif action == "arttest":
            from lib.script.skintools import test_artwork_selection_dialog
            art_type = args.get('art_type')
            test_artwork_selection_dialog(art_type)
            return

        elif action == "multiarttest":
            from lib.script.skintools import test_multiart_dialog
            art_type = args.get('art_type')
            test_multiart_dialog(art_type)
            return

        elif action == "person_info":
            from lib.data.api import person as person_api
            from lib.data.database._infrastructure import init_database
            import xbmcgui

            init_database()

            xbmc.executebuiltin('ClearProperty(SkinInfo.person_id,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Details,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Images,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Filmography,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Crew,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryMovies,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryTVShows,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.SearchQuery,home)')

            name = args.get('name', '')
            role = args.get('role', '')
            dbid = args.get('dbid')
            dbtype = args.get('dbtype', 'movie')
            auto_search = args.get('auto_search', 'true').lower() == 'true'
            online = args.get('online', 'false').lower() == 'true'
            person_id_str = args.get('person_id')
            open_window = args.get('open_window', '')
            crew = args.get('crew', '')
            separator = args.get('separator', ' / ')

            if person_id_str:
                try:
                    person_id = int(person_id_str)
                    log("General", f"person_info: Using provided person_id {person_id}", xbmc.LOGDEBUG)
                except (ValueError, TypeError):
                    log("General", f"person_info: Invalid person_id '{person_id_str}'", xbmc.LOGERROR)
                    return
            else:
                person_id = None

            if not person_id and crew:
                if crew not in ('director', 'writer', 'creator'):
                    log("General", f"person_info: Invalid crew type '{crew}', expected director/writer/creator", xbmc.LOGERROR)
                    return

                if not dbid:
                    log("General", "person_info: crew mode requires dbid parameter", xbmc.LOGERROR)
                    return

                try:
                    dbid = int(dbid)
                except (ValueError, TypeError):
                    log("General", f"person_info: Invalid dbid '{dbid}'", xbmc.LOGERROR)
                    return

                tmdb_id = person_api.resolve_tmdb_id(dbtype, dbid)
                if not tmdb_id:
                    log("General", f"person_info: Could not resolve TMDB ID for {dbtype} {dbid}", xbmc.LOGERROR)
                    return

                if not name:
                    crew_list = person_api.get_crew_from_tmdb(crew, tmdb_id, dbtype)
                    if not crew_list:
                        log("General", f"person_info: No {crew}s found for {dbtype} {dbid}", xbmc.LOGDEBUG)
                        return

                    if len(crew_list) == 1:
                        person_id = crew_list[0]['id']
                        name = crew_list[0]['name']
                        log("General", f"person_info: Single {crew} found: {name} (person_id={person_id})", xbmc.LOGDEBUG)
                    else:
                        items = []
                        for member in crew_list:
                            item = xbmcgui.ListItem(member['name'], offscreen=True)
                            if member.get('job'):
                                item.setLabel2(member['job'])
                            if member.get('profile_path'):
                                image_url = f"https://image.tmdb.org/t/p/w185{member['profile_path']}"
                                item.setArt({'thumb': image_url, 'icon': image_url})
                            items.append(item)

                        dialog = xbmcgui.Dialog()
                        selected = dialog.select(f"Select {crew.title()}", items, useDetails=True)
                        if selected < 0:
                            log("General", f"person_info: User cancelled {crew} selection", xbmc.LOGDEBUG)
                            return
                        person_id = crew_list[selected]['id']
                        name = crew_list[selected]['name']
                        log("General", f"person_info: User selected {crew}: {name} (person_id={person_id})", xbmc.LOGDEBUG)
                else:
                    names = [n.strip() for n in name.split(separator) if n.strip()]
                    if not names:
                        log("General", "person_info: No valid names after parsing", xbmc.LOGERROR)
                        return

                    if len(names) == 1:
                        selected_name = names[0]
                    else:
                        dialog = xbmcgui.Dialog()
                        selected = dialog.select(f"Select {crew.title()}", names)
                        if selected < 0:
                            log("General", f"person_info: User cancelled {crew} selection", xbmc.LOGDEBUG)
                            return
                        selected_name = names[selected]

                    name = selected_name
                    person_id = person_api.match_crew_to_person_id(selected_name, crew, tmdb_id, dbtype, auto_search=auto_search)
                    if not person_id:
                        log("General", f"person_info: Could not match {crew} '{selected_name}'", xbmc.LOGDEBUG)
                        return

            elif not person_id:
                if not name or not dbid:
                    log("General", "person_info: Missing required parameters (name, dbid)", xbmc.LOGERROR)
                    return

                try:
                    dbid = int(dbid)
                except (ValueError, TypeError):
                    log("General", f"person_info: Invalid dbid '{dbid}'", xbmc.LOGERROR)
                    return

                sourceid = args.get('sourceid')

                if dbtype in ('set', 'season'):
                    if not sourceid:
                        log("General", f"person_info: {dbtype.capitalize()}s require sourceid parameter", xbmc.LOGERROR)
                        return
                    try:
                        source_dbid = int(sourceid)
                        source_dbtype = 'movie' if dbtype == 'set' else 'episode'
                    except (ValueError, TypeError):
                        log("General", f"person_info: Invalid sourceid '{sourceid}'", xbmc.LOGERROR)
                        return

                    resolve_dbtype = source_dbtype
                    resolve_dbid = source_dbid
                else:
                    source_dbid = dbid
                    source_dbtype = dbtype
                    resolve_dbtype = dbtype
                    resolve_dbid = dbid
                tmdb_id = person_api.resolve_tmdb_id(resolve_dbtype, resolve_dbid)
                if not tmdb_id:
                    log("General", f"person_info: Could not resolve TMDB ID for {dbtype} {dbid}", xbmc.LOGERROR)
                    return

                person_id = person_api.match_actor_to_person_id(name, role, tmdb_id, source_dbtype, source_dbid, auto_search=auto_search, online=online)
                if not person_id:
                    if not auto_search:
                        import urllib.parse
                        encoded_name = urllib.parse.quote(name)
                        encoded_role = urllib.parse.quote(role)
                        search_command = f"RunScript(script.skin.info.service,action=person_search,name={encoded_name},role={encoded_role},dbtype={dbtype},dbid={dbid}"
                        if open_window:
                            search_command += f",open_window={open_window}"
                        search_command += ")"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.SearchQuery,{search_command},home)')
                        log("General", f"person_info: Auto-match failed, set SearchQuery property for '{name}'", xbmc.LOGDEBUG)
                    else:
                        log("General", f"person_info: Could not match actor '{name}'", xbmc.LOGDEBUG)
                    return

            base_url = "plugin://script.skin.info.service/"

            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Details,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Images,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Filmography,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Crew,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryMovies,home)')
            xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryTVShows,home)')

            xbmc.executebuiltin(f'SetProperty(SkinInfo.person_id,{person_id},home)')

            details_url = f"{base_url}?action=person_info&info_type=details&person_id={person_id}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Details,{details_url},home)')

            images_url = f"{base_url}?action=person_info&info_type=images&person_id={person_id}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Images,{images_url},home)')

            filmography_url = f"{base_url}?action=person_info&info_type=filmography&person_id={person_id}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Filmography,{filmography_url},home)')

            crew_url = f"{base_url}?action=person_info&info_type=crew&person_id={person_id}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Crew,{crew_url},home)')

            import urllib.parse
            encoded_name = urllib.parse.quote(name)
            library_movies_url = f"{base_url}?action=person_library&info_type=movies&person_name={encoded_name}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryMovies,{library_movies_url},home)')

            library_tvshows_url = f"{base_url}?action=person_library&info_type=tvshows&person_name={encoded_name}"
            xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryTVShows,{library_tvshows_url},home)')

            log("General", f"person_info: Set properties for person_id={person_id} ({name})", xbmc.LOGDEBUG)

            if open_window:
                xbmc.executebuiltin(f'ActivateWindow({open_window})')

            return

        elif action == "person_search":
            from lib.data.api import person as person_api
            from lib.data.database._infrastructure import init_database
            import urllib.parse

            init_database()

            name = urllib.parse.unquote(args.get('name', ''))
            role = urllib.parse.unquote(args.get('role', ''))
            dbid = args.get('dbid')
            dbtype = args.get('dbtype', 'movie')
            open_window = args.get('open_window', '')

            if name and dbid:
                try:
                    dbid = int(dbid)
                except (ValueError, TypeError):
                    log("General", f"person_search: Invalid dbid '{dbid}'", xbmc.LOGERROR)
                    return

                tmdb_id = person_api.resolve_tmdb_id(dbtype, dbid)
                if tmdb_id:
                    person_id = person_api.match_actor_to_person_id(name, role, tmdb_id, dbtype, dbid, auto_search=True)
                    if person_id:
                        from lib.data.api.tmdb import ApiTmdb
                        api = ApiTmdb()
                        person_data = api.get_person_details(person_id)

                        if person_data and person_data.get('profile_path'):
                            profile_url = f"https://image.tmdb.org/t/p/original{person_data['profile_path']}"
                            xbmc.executebuiltin(f'RunScript(script.skin.info.service,action=blur,source={profile_url},prefix=Person,window=home)')

                        base_url = "plugin://script.skin.info.service/"

                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Details,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Images,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Filmography,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Crew,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryMovies,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryTVShows,home)')
                        xbmc.executebuiltin('ClearProperty(SkinInfo.Person.SearchQuery,home)')

                        xbmc.executebuiltin(f'SetProperty(SkinInfo.person_id,{person_id},home)')

                        details_url = f"{base_url}?action=person_info&info_type=details&person_id={person_id}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Details,{details_url},home)')

                        images_url = f"{base_url}?action=person_info&info_type=images&person_id={person_id}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Images,{images_url},home)')

                        filmography_url = f"{base_url}?action=person_info&info_type=filmography&person_id={person_id}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Filmography,{filmography_url},home)')

                        crew_url = f"{base_url}?action=person_info&info_type=crew&person_id={person_id}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Crew,{crew_url},home)')

                        import urllib.parse
                        encoded_name = urllib.parse.quote(name)
                        library_movies_url = f"{base_url}?action=person_library&info_type=movies&person_name={encoded_name}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryMovies,{library_movies_url},home)')

                        library_tvshows_url = f"{base_url}?action=person_library&info_type=tvshows&person_name={encoded_name}"
                        xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryTVShows,{library_tvshows_url},home)')

                        log("General", f"person_search: Set properties for person_id={person_id} ({name})", xbmc.LOGDEBUG)

                        if open_window:
                            xbmc.executebuiltin(f'ActivateWindow({open_window})')

                    return

            query = args.get('query', name)
            if not query:
                log("General", "person_search: No query provided", xbmc.LOGERROR)
                return

            from lib.data.api.tmdb import ApiTmdb
            api = ApiTmdb()
            person_id = person_api._search_with_dialog(query, api)

            if person_id:
                person_data = api.get_person_details(person_id)
                if not person_data:
                    log("General", f"person_search: Failed to get details for person_id={person_id}", xbmc.LOGERROR)
                    return

                if person_data.get('profile_path'):
                    profile_url = f"https://image.tmdb.org/t/p/original{person_data['profile_path']}"
                    xbmc.executebuiltin(f'RunScript(script.skin.info.service,action=blur,source={profile_url},prefix=Person,window=home)')

                base_url = "plugin://script.skin.info.service/"

                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Details,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Images,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Filmography,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.Crew,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryMovies,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.LibraryTVShows,home)')
                xbmc.executebuiltin('ClearProperty(SkinInfo.Person.SearchQuery,home)')

                xbmc.executebuiltin(f'SetProperty(SkinInfo.person_id,{person_id},home)')

                person_name = person_data.get('name', query)

                details_url = f"{base_url}?action=person_info&info_type=details&person_id={person_id}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Details,{details_url},home)')

                images_url = f"{base_url}?action=person_info&info_type=images&person_id={person_id}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Images,{images_url},home)')

                filmography_url = f"{base_url}?action=person_info&info_type=filmography&person_id={person_id}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Filmography,{filmography_url},home)')

                crew_url = f"{base_url}?action=person_info&info_type=crew&person_id={person_id}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.Crew,{crew_url},home)')

                import urllib.parse
                encoded_name = urllib.parse.quote(person_name)
                library_movies_url = f"{base_url}?action=person_library&info_type=movies&person_name={encoded_name}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryMovies,{library_movies_url},home)')

                library_tvshows_url = f"{base_url}?action=person_library&info_type=tvshows&person_name={encoded_name}"
                xbmc.executebuiltin(f'SetProperty(SkinInfo.Person.LibraryTVShows,{library_tvshows_url},home)')

                log("General", f"person_search: Set properties for person_id={person_id} ({person_name})", xbmc.LOGDEBUG)

                if open_window:
                    xbmc.executebuiltin(f'ActivateWindow({open_window})')

            return

        elif action == "tmdb_search":
            import xbmcgui
            import urllib.parse
            import re
            from lib.data.api.tmdb import ApiTmdb

            media_type = args.get('dbtype', 'movie')
            doneaction = args.get('doneaction', '')
            window = args.get('window', 'home')
            property_name = args.get('property', 'SkinInfo.Search.Details')

            if media_type not in ('movie', 'tv', 'person'):
                log("General", f"tmdb_search: Invalid dbtype '{media_type}'", xbmc.LOGERROR)
                return

            log("General", f"tmdb_search: Opening keyboard for {media_type} search", xbmc.LOGDEBUG)

            keyboard = xbmcgui.Dialog().input(heading=f'Search {media_type.upper()}')
            if not keyboard:
                log("General", "tmdb_search: User cancelled keyboard", xbmc.LOGDEBUG)
                return

            query = keyboard.strip()
            if not query:
                log("General", "tmdb_search: Empty query entered", xbmc.LOGDEBUG)
                return

            year = 0
            year_match = re.search(r':(\d{4})$', query)
            if year_match:
                year = int(year_match.group(1))
                query = query[:year_match.start()].strip()
                log("General", f"tmdb_search: Extracted year={year} from query", xbmc.LOGDEBUG)

            log("General", f"tmdb_search: Searching TMDB for '{query}' (type={media_type}, year={year})", xbmc.LOGDEBUG)

            api = ApiTmdb()
            results = api.search(query, media_type, year)

            if not results:
                xbmcgui.Dialog().notification('TMDB Search', 'No results found', xbmcgui.NOTIFICATION_INFO, 3000)
                log("General", f"tmdb_search: No results found for '{query}'", xbmc.LOGDEBUG)
                return

            log("General", f"tmdb_search: Found {len(results)} results", xbmc.LOGDEBUG)

            listitems = []
            for result in results[:20]:
                if media_type == 'movie':
                    title = result.get('title', 'Unknown')
                    year_str = result.get('release_date', '')[:4] if result.get('release_date') else ''
                    label2 = f"{year_str} - {result.get('overview', '')[:100]}" if year_str else result.get('overview', '')[:100]
                    poster = result.get('poster_path', '')
                elif media_type == 'tv':
                    title = result.get('name', 'Unknown')
                    year_str = result.get('first_air_date', '')[:4] if result.get('first_air_date') else ''
                    label2 = f"{year_str} - {result.get('overview', '')[:100]}" if year_str else result.get('overview', '')[:100]
                    poster = result.get('poster_path', '')
                else:
                    title = result.get('name', 'Unknown')
                    label2 = result.get('known_for_department', '')
                    poster = result.get('profile_path', '')

                listitem = xbmcgui.ListItem(label=title, label2=label2, offscreen=True)
                if poster:
                    image_url = f"https://image.tmdb.org/t/p/w500{poster}"
                    listitem.setArt({'icon': image_url, 'thumb': image_url})

                listitem.setProperty('tmdb_id', str(result.get('id', '')))
                listitems.append(listitem)

            selected_index = xbmcgui.Dialog().select(f'Search Results: {query}', listitems, useDetails=True)

            if selected_index < 0:
                log("General", "tmdb_search: User cancelled selection", xbmc.LOGDEBUG)
                return

            tmdb_id = listitems[selected_index].getProperty('tmdb_id')
            log("General", f"tmdb_search: User selected {media_type} with tmdb_id={tmdb_id}", xbmc.LOGDEBUG)

            xbmc.executebuiltin(f'ClearProperty({property_name},{window})')

            details_url = f"plugin://script.skin.info.service/?action=tmdb_details&type={media_type}&tmdb_id={tmdb_id}"
            xbmc.executebuiltin(f'SetProperty({property_name},{details_url},{window})')

            log("General", f"tmdb_search: Set property {property_name}={details_url}", xbmc.LOGDEBUG)

            if doneaction:
                for builtin in doneaction.split('|'):
                    if builtin.strip():
                        log("General", f"tmdb_search: Executing builtin: {builtin.strip()}", xbmc.LOGDEBUG)
                        xbmc.executebuiltin(builtin.strip())

            return

        elif action == "search_library_person":
            import urllib.parse
            import xbmcgui
            from lib.kodi.client import request

            name = urllib.parse.unquote(args.get('name', ''))
            crew = args.get('crew', '')

            if not name:
                log("General", "search_library_person: Missing name", xbmc.LOGERROR)
                return

            if crew and crew not in ('director', 'writer'):
                log("General", f"search_library_person: Invalid crew type '{crew}'", xbmc.LOGERROR)
                return

            field = crew if crew else 'actor'
            if field == 'writer':
                field = 'writers'

            log("General", f"search_library_person: Searching library for {crew or 'actor'} '{name}'", xbmc.LOGDEBUG)

            progress = xbmcgui.DialogProgress()
            progress.create(xbmc.getLocalizedString(194), name)

            movies = request('VideoLibrary.GetMovies', {
                'filter': {'field': field, 'operator': 'is', 'value': name},
                'properties': ['title', 'year', 'art', 'playcount', 'file'],
                'sort': {'method': 'title', 'order': 'ascending'}
            })

            if field == 'writers':
                tvshows = None
                episodes = None
            else:
                tvshows = request('VideoLibrary.GetTVShows', {
                    'filter': {'field': field, 'operator': 'is', 'value': name},
                    'properties': ['title', 'year', 'art', 'watchedepisodes', 'episode'],
                    'sort': {'method': 'title', 'order': 'ascending'}
                })

                episodes = request('VideoLibrary.GetEpisodes', {
                    'filter': {'field': field, 'operator': 'is', 'value': name},
                    'properties': ['title', 'showtitle', 'art', 'playcount', 'file'],
                    'sort': {'method': 'title', 'order': 'ascending'}
                })

            progress.close()

            items = []

            if movies and 'movies' in movies.get('result', {}):
                for movie in movies['result']['movies']:
                    label = movie['title']
                    if movie.get('year'):
                        label += f" ({movie['year']})"
                    items.append({
                        'label': f"[{xbmc.getLocalizedString(20338)}] {label}",
                        'type': 'movie',
                        'id': movie['movieid'],
                        'art': movie.get('art', {}),
                        'playcount': movie.get('playcount', 0),
                        'file': movie.get('file', '')
                    })

            if tvshows and 'tvshows' in tvshows.get('result', {}):
                for show in tvshows['result']['tvshows']:
                    label = show['title']
                    if show.get('year'):
                        label += f" ({show['year']})"
                    items.append({
                        'label': f"[{xbmc.getLocalizedString(20364)}] {label}",
                        'type': 'tvshow',
                        'id': show['tvshowid'],
                        'art': show.get('art', {}),
                        'watchedepisodes': show.get('watchedepisodes', 0),
                        'episode': show.get('episode', 0)
                    })

            if episodes and 'episodes' in episodes.get('result', {}):
                for episode in episodes['result']['episodes']:
                    label = f"{episode['title']} ({episode['showtitle']})"
                    items.append({
                        'label': f"[{xbmc.getLocalizedString(20359)}] {label}",
                        'type': 'episode',
                        'id': episode['episodeid'],
                        'art': episode.get('art', {}),
                        'playcount': episode.get('playcount', 0),
                        'file': episode.get('file', '')
                    })

            if not items:
                xbmcgui.Dialog().ok(xbmc.getLocalizedString(194), xbmc.getLocalizedString(284))
                return

            list_items = []
            for item in items:
                list_item = xbmcgui.ListItem(item['label'], offscreen=True)

                art = item.get('art', {})
                if item['type'] == 'episode' and art.get('thumb'):
                    list_item.setArt({'thumb': art['thumb'], 'icon': art['thumb']})
                elif art.get('poster'):
                    list_item.setArt({'thumb': art['poster'], 'icon': art['poster']})

                if item['type'] == 'tvshow':
                    watched = item.get('watchedepisodes', 0)
                    total = item.get('episode', 0)
                    if watched > 0 and watched == total:
                        list_item.setProperty('overlay', '5')
                        list_item.setLabel2(xbmc.getLocalizedString(16102))
                else:
                    playcount = item.get('playcount', 0)
                    if playcount > 0:
                        list_item.setProperty('overlay', '5')
                        list_item.setLabel2(xbmc.getLocalizedString(16102))

                    video_info = list_item.getVideoInfoTag()
                    video_info.setPlaycount(playcount)
                    if item.get('file'):
                        video_info.setPath(item['file'])

                list_items.append(list_item)

            dialog = xbmcgui.Dialog()
            selected = dialog.select(xbmc.getLocalizedString(283), list_items, useDetails=True)

            if selected >= 0:
                item = items[selected]
                if item['type'] == 'movie':
                    xbmc.executebuiltin(f'ActivateWindow(Videos,videodb://movies/titles/{item["id"]},return)')
                elif item['type'] == 'tvshow':
                    xbmc.executebuiltin(f'ActivateWindow(Videos,videodb://tvshows/titles/{item["id"]},return)')
                elif item['type'] == 'episode':
                    xbmc.executebuiltin(f'ActivateWindow(Videos,videodb://episodes/{item["id"]},return)')

            return

        elif action == "online_fetch":
            from lib.service.online import fetch_all_online_data
            from lib.kodi.client import get_item_details
            from lib.data.api.tmdb import ApiTmdb
            from lib.data.database._infrastructure import init_database

            init_database()

            media_type = args.get("dbtype", "")
            dbid = args.get("dbid", "")
            tmdb_id = args.get("tmdb_id", "")
            imdb_id = args.get("imdb_id", "")
            window = args.get("window", "home")
            property_name = args.get("property", "SkinInfo.Online.Content")

            if not media_type:
                log("General", "online_fetch: Missing required parameter 'dbtype'", xbmc.LOGWARNING)
                return

            media_type = media_type.lower().strip()
            if media_type not in ("movie", "tvshow", "episode"):
                log("General", f"online_fetch: Invalid media type '{media_type}'", xbmc.LOGWARNING)
                return

            is_episode = media_type == "episode"

            tvdb_id = ""

            if tmdb_id or imdb_id:
                pass
            elif dbid:
                try:
                    dbid_int = int(dbid)
                    if dbid_int <= 0:
                        raise ValueError("DBID must be positive")
                except (ValueError, TypeError) as e:
                    log("General", f"online_fetch: Invalid DBID '{dbid}': {e}", xbmc.LOGWARNING)
                    return

                if is_episode:
                    # Get parent tvshow ID from episode, then get show's uniqueids
                    episode_details = get_item_details("episode", dbid_int, ["tvshowid"])
                    if not episode_details or not episode_details.get("tvshowid"):
                        log("General", f"online_fetch: Could not get parent show for episode {dbid}", xbmc.LOGWARNING)
                        return
                    tvshow_dbid = episode_details["tvshowid"]
                    details = get_item_details("tvshow", tvshow_dbid, ["uniqueid"])
                else:
                    details = get_item_details(media_type, dbid_int, ["uniqueid"])

                if not details:
                    log("General", f"online_fetch: Could not get details for {media_type} {dbid}", xbmc.LOGWARNING)
                    return

                uniqueid_dict = details.get("uniqueid") or {}
                imdb_id = uniqueid_dict.get("imdb") or ""
                tmdb_id = uniqueid_dict.get("tmdb") or ""
                tvdb_id = uniqueid_dict.get("tvdb") or ""
            else:
                log("General", "online_fetch: Missing required parameter - provide dbid, tmdb_id, or imdb_id", xbmc.LOGWARNING)
                return

            # Episodes use parent show's data for online lookups
            if is_episode:
                media_type = "tvshow"

            if not imdb_id and not tmdb_id and not tvdb_id:
                log("General", "online_fetch: No valid IDs available", xbmc.LOGWARNING)
                return

            if not tmdb_id:
                tmdb_api = ApiTmdb()
                if imdb_id:
                    resolved_id = tmdb_api.find_by_external_id(imdb_id, "imdb_id", media_type)
                    if resolved_id:
                        tmdb_id = str(resolved_id)
                elif tvdb_id and media_type == "tvshow":
                    resolved_id = tmdb_api.find_by_external_id(tvdb_id, "tvdb_id", media_type)
                    if resolved_id:
                        tmdb_id = str(resolved_id)

            is_library_item = bool(dbid)
            fetch_all_online_data(media_type, imdb_id, tmdb_id, is_library_item=is_library_item)

            plugin_url = f"plugin://script.skin.info.service/?action=online&dbtype={media_type}"
            if tmdb_id:
                plugin_url += f"&tmdb_id={tmdb_id}"
            if imdb_id:
                plugin_url += f"&imdb_id={imdb_id}"

            log("General", f"online_fetch: Setting {property_name}={plugin_url} on {window}", xbmc.LOGDEBUG)
            xbmc.executebuiltin(f"SetProperty({property_name},{plugin_url},{window})")

            return

        else:
            log("General", f"Unknown action '{action}'. Expected one of: {', '.join(valid_actions)}", xbmc.LOGWARNING)
            return

    from lib.service.main import start_service
    start_service()

if __name__ == "__main__":
    main()
