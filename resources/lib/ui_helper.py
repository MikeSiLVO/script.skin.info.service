"""Shared menu helper utilities.

Provides consistent dialog menu handling with automatic background task cancellation support.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence, Tuple, Optional, Union
import time
import xbmcgui

from resources.lib import task_manager
from resources.lib.kodi import log_general


def show_menu_with_cancel(
    title: str,
    options: Sequence[Tuple[str, Optional[str]]]
) -> Tuple[Optional[str], bool]:
    """
    Show dialog.select() menu with optional "Cancel Current Task" at top.

    Automatically detects if a background task is running and adds a cancel option.
    The cancel option appears at the top in bold formatting.

    Args:
        title: Menu title/heading
        options: List of (label, action) tuples for menu items

    Returns:
        Tuple of (selected_action, was_cancel_pressed):
        - (action_string, False) - User selected a regular menu item
        - (None, True) - User selected "Cancel Current Task" and task was cancelled
        - (None, False) - User pressed back/cancelled the dialog

    Example:
        options = [
            ("Manual Review", "manual"),
            ("Auto Apply", "auto"),
            ("Exit", "exit")
        ]
        action, cancelled = show_menu_with_cancel("Review Options", options)
        if cancelled:
            print("Background task was cancelled")
        elif action == "manual":
            # Handle manual review
        elif action is None:
            # User backed out
    """
    log_general(f"[UI_HELPER] show_menu_with_cancel('{title}') ENTRY")

    task_info = task_manager.get_task_info()
    task_running = task_info is not None
    log_general(f"[UI_HELPER] Task running: {task_running}")

    display_options = []
    action_map = []

    if task_info:
        task_name = task_info['name']
        cancel_label = f"[B]Cancel Current Task: {task_name}[/B]"
        display_options.append(cancel_label)
        action_map.append('__cancel_task__')

    for label, action in options:
        display_options.append(label)
        action_map.append(action)

    choice = xbmcgui.Dialog().select(title, display_options)

    if choice == -1:
        return (None, False)

    selected_action = action_map[choice]
    log_general(f"[UI_HELPER] Selected action: {selected_action}")

    if selected_action == '__cancel_task__':
        task_manager.cancel_task()
        return (None, True)

    return (selected_action, False)


def confirm_cancel_running_task(new_task_name: str) -> bool:
    """
    Show detailed confirmation dialog for cancelling a running task.

    Displays comprehensive task information including:
    - Current task name
    - Duration running
    - Last activity time
    - New task to start
    - Cancellation warning

    Args:
        new_task_name: Name of the new task user wants to start

    Returns:
        True if user confirmed cancellation, False otherwise
    """
    task_info = task_manager.get_task_info()
    if not task_info:
        return True

    current_task = task_info.get('name', 'Unknown task')
    started_at = task_info.get('started_at', time.time())
    last_progress = task_info.get('last_progress', time.time())

    now = time.time()
    duration_seconds = int(now - started_at)
    progress_seconds = int(now - last_progress)

    duration_mins = duration_seconds // 60
    duration_secs = duration_seconds % 60

    progress_mins = progress_seconds // 60
    progress_secs = progress_seconds % 60

    if duration_mins > 0:
        duration_str = f"{duration_mins}m {duration_secs}s"
    else:
        duration_str = f"{duration_secs}s"

    if progress_mins > 0:
        progress_str = f"{progress_mins}m {progress_secs}s"
    else:
        progress_str = f"{progress_secs}s"

    lines = [
        f"[B]Currently Running:[/B] {current_task}",
        f"[B]Duration:[/B] {duration_str}",
        f"[B]Last Activity:[/B] {progress_str} ago",
        "",
        f"[B]New Task:[/B] {new_task_name}",
        "",
        "Cancelling will stop the current task safely.",
        "You can resume it later from the menu."
    ]

    message = "[CR]".join(lines)

    return xbmcgui.Dialog().yesno(
        "Cancel Running Task?",
        message,
        nolabel="No, Keep Running",
        yeslabel="Yes, Cancel It"
    )


class ProgressDialogHelper:
    """
    Unified progress dialog manager supporting both foreground and background dialogs.

    Features:
    - Automatic dialog type selection (DialogProgress or DialogProgressBG)
    - Optional update throttling for performance
    - Flexible message formatting
    - Automatic percent clamping
    """

    def __init__(self, use_background: bool = False, heading: str = "Processing"):
        """
        Initialize progress dialog helper.

        Args:
            use_background: Use DialogProgressBG (True) or DialogProgress (False)
            heading: Dialog heading/title
        """
        self.use_background = use_background
        self.heading = heading
        self.dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
        self.last_percent = -1
        self.throttle_enabled = False
        self.throttle_min_items = 5

    def create(self, message: str = "") -> None:
        """
        Create and show the progress dialog.

        Args:
            message: Initial message to display
        """
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
        """
        Update the progress dialog.

        Args:
            percent: Progress percentage (0-100)
            message: Message to display
            force: Force update even if throttling would skip it
        """
        if not self.dialog:
            return

        percent = max(0, min(100, percent))

        if self.throttle_enabled and not force:
            if percent == self.last_percent:
                return

        self.last_percent = percent

        if self.use_background:
            self.dialog.update(percent, self.heading, message)  # type: ignore[call-arg]
        else:
            self.dialog.update(percent, message)

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
        """
        Check if user cancelled the dialog.

        Returns:
            True if cancelled, False otherwise
        """
        if not self.dialog:
            return False

        if isinstance(self.dialog, xbmcgui.DialogProgressBG):
            return self.dialog.isFinished()
        else:
            return self.dialog.iscanceled()

    def enable_throttling(self, min_items: int = 5) -> None:
        """
        Enable update throttling to reduce UI overhead.

        Args:
            min_items: Minimum number of items between updates
        """
        self.throttle_enabled = True
        self.throttle_min_items = min_items

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False


def format_operation_report(operation: str, stats: dict, timestamp: str, scope: Optional[str] = None) -> str:
    """
    Format operation stats for display in Kodi dialogs.

    Args:
        operation: Operation type ('texture_precache', 'texture_cleanup', 'gif_scan')
        stats: Stats dictionary
        timestamp: ISO format timestamp
        scope: Optional scope string

    Returns:
        Formatted text with [CR] line breaks for Kodi dialogs
    """
    try:
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        formatted_time = timestamp

    lines = []

    if operation == 'texture_precache':
        lines.append("[B]Operation: Pre-Cache Library Artwork[/B]")
        lines.append(f"Completed: {formatted_time}")

        cached = stats.get('cached_count', 0)
        total = stats.get('total_count', 0)
        new = stats.get('new_count', 0)
        lines.append(f"Cached: {cached}/{total} ({new} new)")

        failed = stats.get('failed_count', 0)
        if failed > 0:
            lines.append(f"Failed: {failed}")

        if stats.get('cancelled'):
            lines.append("[B]Status: Cancelled[/B]")

    elif operation == 'texture_cleanup':
        lines.append("[B]Operation: Clean Orphaned Textures[/B]")
        lines.append(f"Completed: {formatted_time}")

        cached = stats.get('cached_count', 0)
        total = stats.get('total_count', 0)
        lines.append(f"Cached: {cached}/{total} in library")

        removed = stats.get('removed_count', 0)
        orphaned = stats.get('orphaned_count', 0)
        lines.append(f"Removed: {removed}/{orphaned} orphaned")

        if stats.get('cancelled'):
            lines.append("[B]Status: Cancelled[/B]")

    elif operation == 'gif_scan':
        lines.append("[B]Operation: Scan for Animated Posters[/B]")

        if scope:
            scope_label = scope.title() if scope != 'all' else 'All'
            lines.append(f"Scope: {scope_label}")

        lines.append(f"Completed: {formatted_time}")

        found = stats.get('found_count', 0)
        lines.append(f"Found: {found} GIFs")

        scanned = stats.get('scanned_count', 0)
        lines.append(f"Scanned: {scanned} items")

        skipped = stats.get('skipped_count', 0)
        lines.append(f"Skipped: {skipped} (cached/unchanged)")

        scan_mode = stats.get('scan_mode', 'incremental')
        mode_label = 'Full' if scan_mode == 'full' else 'Incremental'
        lines.append(f"Mode: {mode_label}")

        if stats.get('cancelled'):
            lines.append("[B]Status: Cancelled[/B]")

    else:
        lines.append(f"[B]Operation: {operation}[/B]")
        lines.append(f"Completed: {formatted_time}")
        lines.append(f"Stats: {stats}")

    return "[CR]".join(lines)


# Settings Action Helpers

def edit_api_key(provider: str) -> None:
    """
    Show keyboard dialog to edit API key.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    import xbmcaddon
    from resources.lib.kodi import API_KEY_CONFIG

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    addon = xbmcaddon.Addon()
    current_key = addon.getSetting(config["setting_path"])

    keyboard = xbmcgui.Dialog().input(
        f"Enter {config['name']} API Key",
        current_key,
        type=xbmcgui.INPUT_ALPHANUM
    )

    if keyboard:
        addon.setSetting(config["setting_path"], keyboard)
        addon.setSetting(f"{provider}_configured", "true")
        addon.setSetting(f"{provider}_api_key_display", keyboard)

        xbmcgui.Dialog().notification(
            "API Key Updated",
            f"{config['name']} API key saved",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )


def clear_api_key(provider: str) -> None:
    """
    Clear API key after confirmation.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    import xbmcaddon
    from resources.lib.kodi import API_KEY_CONFIG

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    if xbmcgui.Dialog().yesno(
        "Clear API Key",
        f"Are you sure you want to clear the {config['name']} API key?"
    ):
        addon = xbmcaddon.Addon()
        addon.setSetting(config["setting_path"], "")
        addon.setSetting(f"{provider}_configured", "false")
        addon.setSetting(f"{provider}_api_key_display", "Not configured")

        import xbmc
        xbmc.executebuiltin('Action(Up)')

        xbmcgui.Dialog().notification(
            "API Key Cleared",
            f"{config['name']} API key removed",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )


def test_api_key(provider: str) -> None:
    """
    Test API key connection.

    Args:
        provider: Provider name (tmdb, mdblist, omdb, fanarttv)
    """
    from resources.lib.kodi import API_KEY_CONFIG
    import xbmcaddon

    config = API_KEY_CONFIG.get(f"{provider}_api_key")
    if not config:
        return

    progress = xbmcgui.DialogProgress()
    progress.create(f"Testing {config['name']}", "Connecting to API...")

    try:
        if provider == "tmdb":
            from resources.lib.api.tmdb import TMDBApi as TMDBRatingsSource
            source = TMDBRatingsSource()
            success = source.test_connection()
        elif provider == "mdblist":
            from resources.lib.api.mdblist import MDBListRatingsSource
            source = MDBListRatingsSource()
            success = source.test_connection()
        elif provider == "omdb":
            from resources.lib.api.omdb import OMDbRatingsSource
            source = OMDbRatingsSource()
            success = source.test_connection()
        elif provider == "fanarttv":
            addon = xbmcaddon.Addon()
            api_key = addon.getSetting("fanarttv_api_key").strip()

            if not api_key:
                progress.close()
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    f"{config['name']} - Connection Test",
                    "No API key configured.\n\nPlease add your Fanart.tv API key first."
                )
                return

            import json
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError, URLError

            url = f"https://webservice.fanart.tv/v3/movies/11?api_key={api_key}"
            request = Request(url)

            try:
                response = urlopen(request, timeout=10)
                data = json.loads(response.read().decode('utf-8'))
                success = data.get('name') is not None
            except HTTPError as e:
                error_data = json.loads(e.read().decode('utf-8'))
                if error_data.get('status') == 'error':
                    success = False
                else:
                    raise
            except URLError:
                success = False
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
    import json
    import time
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from resources.lib.api.trakt import TRAKT_CLIENT_ID, TraktRatingsSource

    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Authorization", "Requesting device code...")

    try:
        data = json.dumps({"client_id": TRAKT_CLIENT_ID}).encode('utf-8')
        req = Request("https://api.trakt.tv/oauth/device/code", data=data)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "script.skin.info.service/2.0.0")

        try:
            with urlopen(req, timeout=10) as response:
                data_dict = json.loads(response.read().decode('utf-8'))
        except HTTPError:
            progress.close()
            xbmcgui.Dialog().ok(
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

        while time.time() - start_time < expires_in:
            remaining = int(expires_in - (time.time() - start_time))

            progress.update(
                0,
                f"1. Visit: {verification_url}\n"
                f"2. Enter code: [B]{user_code}[/B]\n"
                f"3. Click Authorize on the website\n\n"
                f"Waiting for authorization... ({remaining}s remaining)"
            )

            if progress.iscanceled():
                progress.close()
                return

            time.sleep(interval)

            token_data = json.dumps({"code": device_code, "client_id": TRAKT_CLIENT_ID}).encode('utf-8')
            token_req = Request("https://api.trakt.tv/oauth/device/token", data=token_data)
            token_req.add_header("Content-Type", "application/json")
            token_req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            try:
                with urlopen(token_req, timeout=10) as token_response:
                    tokens = json.loads(token_response.read().decode('utf-8'))
                    source = TraktRatingsSource()
                    source._save_tokens(
                        tokens["access_token"],
                        tokens["refresh_token"],
                        tokens.get("expires_in", 86400)
                    )

                    import xbmcaddon
                    addon = xbmcaddon.Addon()
                    addon.setSetting("trakt_configured", "true")

                    progress.close()
                    xbmcgui.Dialog().ok(
                        "Trakt Authorization",
                        "Authorization successful!\n\nTrakt is now connected."
                    )
                    return
            except HTTPError as e:
                if e.code != 400:
                    progress.close()
                    xbmcgui.Dialog().ok(
                        "Trakt Authorization Failed",
                        f"Error: {e.code}"
                    )
                    return

        progress.close()
        xbmcgui.Dialog().ok(
            "Trakt Authorization",
            "Authorization timed out.\n\nPlease try again."
        )

    except Exception as e:
        progress.close()
        xbmcgui.Dialog().ok(
            "Trakt Authorization Failed",
            f"Error:\n\n{str(e)}"
        )


def test_trakt_connection() -> None:
    """Test Trakt API connection."""
    from resources.lib.api.trakt import TraktRatingsSource

    progress = xbmcgui.DialogProgress()
    progress.create("Testing Trakt", "Connecting to API...")

    try:
        source = TraktRatingsSource()
        success = source.test_connection()
        progress.close()

        if success:
            xbmcgui.Dialog().ok(
                "Trakt - Connection Test",
                "Connection successful!\n\nTrakt is authorized and working."
            )
        else:
            xbmcgui.Dialog().ok(
                "Trakt - Connection Test",
                "Connection failed.\n\nPlease authorize Trakt first."
            )

    except Exception as e:
        progress.close()
        xbmcgui.Dialog().ok(
            "Trakt - Connection Test",
            f"Error testing connection:\n\n{str(e)}"
        )


def revoke_trakt_authorization() -> None:
    """Revoke Trakt authorization after confirmation."""
    if xbmcgui.Dialog().yesno(
        "Revoke Trakt Authorization",
        "Are you sure you want to revoke Trakt authorization?\n\n"
        "You will need to re-authorize to use Trakt ratings."
    ):
        import xbmcaddon
        from resources.lib.api.trakt import TraktRatingsSource

        source = TraktRatingsSource()
        source._delete_tokens()

        addon = xbmcaddon.Addon()
        addon.setSetting("trakt_configured", "false")

        xbmcgui.Dialog().notification(
            "Trakt Authorization Revoked",
            "Trakt has been disconnected",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )


def sync_configured_flags() -> None:
    """Sync string configured flags with actual API key/token presence."""
    import xbmcaddon
    from resources.lib.kodi import API_KEY_CONFIG

    addon = xbmcaddon.Addon()

    for provider in ["tmdb", "mdblist", "omdb", "fanarttv"]:
        config = API_KEY_CONFIG.get(f"{provider}_api_key")
        if config:
            key = addon.getSetting(config["setting_path"])
            addon.setSetting(f"{provider}_configured", "true" if key else "false")

    access_token = addon.getSetting("trakt_access_token")
    addon.setSetting("trakt_configured", "true" if access_token else "false")


def clear_blur_cache() -> None:
    """Clear all cached blurred images after confirmation."""
    from resources.lib import blur

    file_count, total_bytes = blur.get_blur_cache_size()

    if file_count == 0:
        xbmcgui.Dialog().notification(
            "Blur Cache Empty",
            "No cached blurred images to delete",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return

    if total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.1f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.1f} MB"

    if xbmcgui.Dialog().yesno(
        "Clear Blur Cache?",
        f"Cache: {file_count} file{'s' if file_count != 1 else ''} ({size_str})\n\nFrees space by deleting blurred backgrounds.\nRecreates automatically but causes brief delays until rebuilt."
    ):
        deleted_count = blur.clear_blur_cache()

        import xbmc
        xbmc.executebuiltin('Action(Up)')

        xbmcgui.Dialog().notification(
            "Blur Cache Cleared",
            f"{deleted_count} file{'s' if deleted_count != 1 else ''} deleted",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
