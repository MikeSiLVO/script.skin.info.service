"""API key and authorization management utilities."""
from __future__ import annotations

import xbmc
import xbmcgui

from lib.kodi.client import ADDON


def edit_api_key(provider: str) -> None:
    """
    Show keyboard dialog to edit API key.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    from lib.kodi.client import API_KEY_CONFIG

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    current_key = ADDON.getSetting(config["setting_path"])

    keyboard = xbmcgui.Dialog().input(
        f"Enter {config['name']} API Key",
        current_key,
        type=xbmcgui.INPUT_ALPHANUM
    )

    if keyboard:
        settings = ADDON.getSettings()
        settings.setString(config["setting_path"], keyboard)
        settings.setString(f"{provider}_configured", "true")
        settings.setString(f"{provider}_api_key_display", keyboard)

        ADDON.setSetting(f"{provider}_configured", "true")
        ADDON.setSetting(f"{provider}_api_key_display", keyboard)


def clear_api_key(provider: str) -> None:
    """
    Clear API key after confirmation.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    from lib.kodi.client import API_KEY_CONFIG
    from lib.infrastructure.dialogs import show_yesno

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    if show_yesno(
        "Clear API Key",
        f"Are you sure you want to clear the {config['name']} API key?"
    ):
        settings = ADDON.getSettings()
        settings.setString(config["setting_path"], "")
        settings.setString(f"{provider}_configured", "false")
        settings.setString(f"{provider}_api_key_display", "Not configured")

        ADDON.setSetting(f"{provider}_configured", "false")
        ADDON.setSetting(f"{provider}_api_key_display", "Not configured")

        xbmc.executebuiltin('Action(Up)')


def test_api_key(provider: str) -> None:
    """
    Test API key connection.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    from lib.kodi.client import API_KEY_CONFIG

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32370).format(config['name']), ADDON.getLocalizedString(32371))

    try:
        if provider == "tmdb":
            from lib.data.api.tmdb import ApiTmdb as TMDBRatingsSource
            source = TMDBRatingsSource()
            success = source.test_connection()
        elif provider == "mdblist":
            from lib.data.api.mdblist import ApiMdblist as MDBListRatingsSource
            source = MDBListRatingsSource()
            success = source.test_connection()
        elif provider == "omdb":
            from lib.data.api.omdb import ApiOmdb as OMDbRatingsSource
            source = OMDbRatingsSource()
            success = source.test_connection()
        elif provider == "fanarttv":
            from lib.data.api.fanarttv import ApiFanarttv
            source = ApiFanarttv()
            success = source.test_connection()
        else:
            progress.close()
            return

        progress.close()

        if success:
            dialog = xbmcgui.Dialog()
            dialog.ok(
                f"{config['name']} - Connection Test",
                "Connection successful!\n\nAPI key is valid and working."
            )
        else:
            dialog = xbmcgui.Dialog()
            dialog.ok(
                f"{config['name']} - Connection Test",
                "Connection failed.\n\nPlease check your API key."
            )

    except Exception as e:
        progress.close()
        dialog = xbmcgui.Dialog()
        dialog.ok(
            f"{config['name']} - Connection Test",
            f"Error testing connection:\n\n{str(e)}"
        )


def authorize_trakt() -> None:
    """Authorize Trakt using OAuth device code flow."""
    import time
    from lib.data.api.trakt import TRAKT_CLIENT_ID, ApiTrakt as TraktRatingsSource
    from lib.data.api.client import ApiSession
    from lib.infrastructure.dialogs import show_ok

    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32372), ADDON.getLocalizedString(32373))

    session = ApiSession(
        service_name="Trakt Auth",
        base_url="https://api.trakt.tv",
        timeout=(5.0, 10.0),
        default_headers={
            "Content-Type": "application/json"
        }
    )

    try:
        data_dict = session.post(
            "/oauth/device/code",
            json_data={"client_id": TRAKT_CLIENT_ID}
        )

        if not data_dict:
            progress.close()
            show_ok(
                "Trakt Authorization Failed",
                "Failed to get device code from Trakt."
            )
            return

        device_code = data_dict["device_code"]
        user_code = data_dict["user_code"]
        verification_url = data_dict["verification_url"]
        expires_in = data_dict["expires_in"]
        interval = data_dict.get("interval", 5)

        start_time = time.time()
        monitor = xbmc.Monitor()

        while time.time() - start_time < expires_in:
            remaining = int(expires_in - (time.time() - start_time))

            progress.update(
                0,
                f"1. Visit: {verification_url}\n"
                f"2. Enter code: [B]{user_code}[/B]\n"
                f"3. Click Authorize on the website\n\n"
                f"Waiting for authorization... ({remaining}s remaining)"
            )

            if progress.iscanceled() or monitor.abortRequested():
                progress.close()
                return

            monitor.waitForAbort(interval)

            tokens = session.post(
                "/oauth/device/token",
                json_data={"code": device_code, "client_id": TRAKT_CLIENT_ID}
            )

            if tokens and "access_token" in tokens:
                source = TraktRatingsSource()
                source._save_tokens(
                    tokens["access_token"],
                    tokens["refresh_token"],
                    tokens.get("expires_in", 86400)
                )

                settings = ADDON.getSettings()
                settings.setString("trakt_configured", "true")
                ADDON.setSetting("trakt_configured", "true")

                progress.close()
                show_ok(
                    "Trakt Authorization",
                    "Authorization successful!\n\nTrakt is now connected."
                )
                return

        progress.close()
        show_ok(
            "Trakt Authorization",
            "Authorization timed out.\n\nPlease try again."
        )

    except Exception as e:
        progress.close()
        show_ok(
            "Trakt Authorization Failed",
            f"Error:\n\n{str(e)}"
        )


def test_trakt_connection() -> None:
    """Test Trakt API connection."""
    from lib.data.api.trakt import ApiTrakt as TraktRatingsSource
    from lib.infrastructure.dialogs import show_ok

    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32374), ADDON.getLocalizedString(32371))

    try:
        source = TraktRatingsSource()
        success = source.test_connection()
        progress.close()

        if success:
            show_ok(
                "Trakt - Connection Test",
                "Connection successful!\n\nTrakt is authorized and working."
            )
        else:
            show_ok(
                "Trakt - Connection Test",
                "Connection failed.\n\nPlease authorize Trakt first."
            )

    except Exception as e:
        progress.close()
        show_ok(
            "Trakt - Connection Test",
            f"Error testing connection:\n\n{str(e)}"
        )


def revoke_trakt_authorization() -> None:
    """Revoke Trakt authorization after confirmation."""
    from lib.data.api.trakt import ApiTrakt as TraktRatingsSource
    from lib.infrastructure.dialogs import show_yesno

    if show_yesno(
        "Revoke Trakt Authorization",
        "Are you sure you want to revoke Trakt authorization?\n\n"
        "You will need to re-authorize to use Trakt ratings."
    ):
        source = TraktRatingsSource()
        source._delete_tokens()

        settings = ADDON.getSettings()
        settings.setString("trakt_configured", "false")
        ADDON.setSetting("trakt_configured", "false")


def sync_configured_flags() -> None:
    """Sync string configured flags with actual API key/token presence."""
    import xbmcvfs
    import json
    from lib.kodi.client import API_KEY_CONFIG

    settings = ADDON.getSettings()

    for provider in ["tmdb", "mdblist", "omdb", "fanarttv"]:
        config = API_KEY_CONFIG.get(f"{provider}_api_key")
        if config:
            key = ADDON.getSetting(config["setting_path"])
            value = "true" if key else "false"
            settings.setString(f"{provider}_configured", value)
            ADDON.setSetting(f"{provider}_configured", value)

    token_path = xbmcvfs.translatePath("special://profile/addon_data/script.skin.info.service/trakt_tokens.json")
    has_trakt_token = False
    if xbmcvfs.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                tokens = json.load(f)
                has_trakt_token = bool(tokens.get("access_token"))
        except Exception:
            pass
    value = "true" if has_trakt_token else "false"
    settings.setString("trakt_configured", value)
    ADDON.setSetting("trakt_configured", value)
