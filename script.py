"""Entry point for script.skin.info.service."""
import sys
import xbmc


def _parse_args(start_index: int) -> dict:
    """
    Parse script arguments from sys.argv starting at start_index.

    Supports both positional and key=value formats:
    - Positional: arg1, arg2, arg3 -> {0: arg1, 1: arg2, 2: arg3}
    - Key=value: key1=val1, key2=val2 -> {key1: val1, key2: val2}
    - Mixed: Positional args first, then key=value args

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


def main():

    if len(sys.argv) > 1:
        action = sys.argv[1].lower().strip()
        valid_actions = ("tools", "settings_action", "review_artwork", "update_ratings",
                         "arttest", "multiarttest", "testscripts")

        if action == "tools":
            from resources.lib.tools import run_tools
            run_tools()
            return

        elif action == "review_artwork":
            from resources.lib.art_fetcher import run_art_fetcher_single
            args = _parse_args(2)
            dbid = args.get('dbid') or args.get(0)
            dbtype = args.get('dbtype') or args.get(1)
            run_art_fetcher_single(dbid, dbtype)
            return

        elif action == "update_ratings":
            from resources.lib.ratings.updater import update_single_item_ratings
            args = _parse_args(2)
            dbid = args.get('dbid') or args.get(0)
            dbtype = args.get('dbtype') or args.get(1)
            update_single_item_ratings(dbid, dbtype)
            return

        elif action == "settings_action":
            from resources.lib import ui_helper
            sub_action = sys.argv[2] if len(sys.argv) > 2 else None
            provider = sys.argv[3] if len(sys.argv) > 3 else None

            if sub_action == "edit_api_key" and provider:
                ui_helper.edit_api_key(provider)
            elif sub_action == "test_api_key" and provider:
                ui_helper.test_api_key(provider)
            elif sub_action == "clear_api_key" and provider:
                ui_helper.clear_api_key(provider)
            elif sub_action == "authorize_trakt":
                ui_helper.authorize_trakt()
            elif sub_action == "test_trakt_connection":
                ui_helper.test_trakt_connection()
            elif sub_action == "revoke_trakt_authorization":
                ui_helper.revoke_trakt_authorization()
            elif sub_action == "clear_blur_cache":
                ui_helper.clear_blur_cache()
            return

        elif action == "arttest":
            from tests.scripts.test_artwork_dialogs import test_artwork_selection_dialog
            art_type = sys.argv[2] if len(sys.argv) > 2 else 'poster'
            test_artwork_selection_dialog(art_type)
            return

        elif action == "multiarttest":
            from tests.scripts.test_artwork_dialogs import test_multiart_dialog
            art_type = sys.argv[2] if len(sys.argv) > 2 else 'fanart'
            test_multiart_dialog(art_type)
            return

        elif action == "testscripts":
            from tests.scripts.test_runner import run_tests
            run_tests()
            return

        else:
            xbmc.log(f"script.skin.info.service: Unknown action '{action}'. Expected one of: {', '.join(valid_actions)}", xbmc.LOGWARNING)
            return

    xbmc.log("script.skin.info.service: Starting background service", xbmc.LOGINFO)
    from resources.lib.service import start_service
    start_service()

if __name__ == "__main__":
    main()
