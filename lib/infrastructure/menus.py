"""Menu helper utilities with automatic navigation and task cancellation support."""
from __future__ import annotations

from typing import Sequence, Tuple, Optional, Any
import time
import xbmcaddon
import xbmcgui

from lib.infrastructure import tasks as task_manager
from lib.kodi.client import log

ADDON = xbmcaddon.Addon()

# Sentinel value to signal "return to main menu" vs "go back one level"
_RETURN_TO_MAIN = object()


class MenuItem:
    """Represents a single menu item with label and action."""

    def __init__(self, label: str, action, loop: bool = False):
        """
        Create a menu item.

        Args:
            label: Display text for the menu item
            action: Action to perform when selected:
                - Callable: Execute function and use return value
                - Menu: Show submenu
                - Any other value: Return that value
            loop: If True, re-show parent menu after action completes
        """
        self.label = label
        self.action = action
        self.loop = loop


class Menu:
    """
    Declarative menu with automatic navigation handling.

    Handles back/cancel/task cancellation automatically and supports
    nested submenus with proper navigation stack.

    Example:
        menu = Menu("Main Menu", [
            MenuItem("Option 1", lambda: do_something()),
            MenuItem("View Report", lambda: show_report(), loop=True),
            MenuItem("Submenu", Menu("Sub", [...])),
        ])
        result = menu.show()
    """

    def __init__(self, title: str, items: Sequence[MenuItem], is_main_menu: bool = False):
        """
        Create a menu.

        Args:
            title: Menu heading/title
            items: List of MenuItem objects
            is_main_menu: If True, this is the main Tools menu (Cancel exits to Kodi)
        """
        self.title = title
        self.items = list(items)
        self.is_main_menu = is_main_menu
        self._last_selected_idx: Optional[int] = None

    def show(self, preselect: Optional[int] = None) -> Any:
        """
        Show menu and handle navigation automatically.

        Args:
            preselect: Index of item to preselect when showing menu

        Returns:
            - Result from selected action
            - None if user pressed back/ESC or cancelled
        """
        while True:
            selected_idx = preselect if preselect is not None else self._last_selected_idx

            options: list[tuple[str, Optional[str]]] = [(item.label, str(idx)) for idx, item in enumerate(self.items)]
            options.append(("Cancel", '__cancel__'))

            choice_str, cancelled = show_menu_with_cancel(self.title, options, preselect=selected_idx)

            if cancelled:
                return None

            if choice_str == '__back__':
                return None

            if choice_str == '__cancel__':
                if self.is_main_menu:
                    return None
                else:
                    return _RETURN_TO_MAIN

            if choice_str is None:
                return None

            try:
                choice = int(choice_str)
            except (ValueError, TypeError):
                return None

            if choice < 0 or choice >= len(self.items):
                return None

            item = self.items[choice]

            self._last_selected_idx = choice

            if isinstance(item.action, Menu):
                result = item.action.show()
                if result is _RETURN_TO_MAIN:
                    if self.is_main_menu:
                        continue
                    else:
                        return _RETURN_TO_MAIN
                continue
            elif callable(item.action):
                result = item.action()
                if result is _RETURN_TO_MAIN:
                    if self.is_main_menu:
                        continue
                    else:
                        return _RETURN_TO_MAIN
                if item.loop:
                    continue
                return result
            else:
                return item.action


def show_menu_with_cancel(
    title: str,
    options: Sequence[Tuple[str, Optional[str]]],
    preselect: Optional[int] = None
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
        - ('__back__', False) - User pressed back/ESC key
        - (None, False) - User selected Cancel option

    Example:
        options = [
            ("Manual Review", "manual"),
            ("Auto Apply", "auto"),
            ("Cancel", None)
        ]
        action, cancelled = show_menu_with_cancel("Review Options", options)
        if cancelled:
            print("Background task was cancelled")
        elif action == '__back__':
            pass
        elif action == "manual":
            pass
        elif action is None:
            pass
    """
    log("General", f"UI Helper: show_menu_with_cancel('{title}') ENTRY")

    task_info = task_manager.get_task_info()
    task_running = task_info is not None
    log("General", f"UI Helper: Task running: {task_running}")

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

    adjusted_preselect = preselect
    if adjusted_preselect is not None and task_info:
        adjusted_preselect += 1

    choice = xbmcgui.Dialog().select(title, display_options, preselect=adjusted_preselect if adjusted_preselect is not None else -1)

    if choice == -1:
        log("General", "UI Helper: User pressed back/ESC")
        return ('__back__', False)

    selected_action = action_map[choice]
    log("General", f"UI Helper: Selected action: {selected_action}")

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
    from lib.infrastructure.dialogs import show_yesno

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

    return show_yesno(
        ADDON.getLocalizedString(32571),
        message,
        nolabel=ADDON.getLocalizedString(32570),
        yeslabel=ADDON.getLocalizedString(32569)
    )
