"""Container manipulation utilities for skin integration."""
from __future__ import annotations

from typing import Optional
import xbmc
import xbmcgui
import xbmcplugin

from lib.kodi.client import request


def move_to_position(
    main_focus: str,
    main_position: Optional[str] = None,
    main_action: Optional[str] = None,
    next_focus: Optional[str] = None,
    next_position: Optional[str] = None,
    next_action: Optional[str] = None
) -> None:
    """
    Move container to specific position.

    Uses Control.SetFocus with absolute positioning to jump to specific items.
    Works uniformly across all container types (list, panel, wrap, fixed).

    Args:
        main_focus: Container control ID or pipe-separated list (e.g., "90011|90012|90013")
        main_position: Target position for main containers (1-indexed, same as Container.CurrentItem)
                      If None or "0", resets to first item (position 1)
                      Supports pipe-separated values for different positions per container
        main_action: Optional builtin(s) to execute after moving each main container (pipe-separated)
        next_focus: Optional container ID(s) to focus after main containers
                   Unconditional: "90003" or "50|60" (pipe-separated, focus all)
                   Conditional: "condition::focus_id||condition::focus_id||focus_id" (evaluate in order, focus first match)
        next_position: Target position for next containers (1-indexed)
                      If None, just focuses without moving
                      Supports pipe-separated values for different positions per container
                      Only works with unconditional next_focus
        next_action: Optional builtin(s) to execute after focusing/moving each next container (pipe-separated)
                    Only works with unconditional next_focus

    Action behavior:
        - If action contains "|", each part applies to corresponding container by index
        - If action has no "|", same action applies to all containers
        - If fewer actions than containers, remaining containers get no action

    Conditional next_focus (parameter):
        - Format: "condition1::focus_id1||condition2::focus_id2||focus_id3"
        - Blocks separated by "||" are evaluated in order until one succeeds
        - "::" separates condition from focus ID
        - No "::" means unconditional (always focus)
        - First matching condition focuses its control and stops
        - next_position and next_action are ignored in conditional mode

    Conditional focus (properties):
        - Use SkinInfo.CM_Focus.1, SkinInfo.CM_Focus.2, etc. properties on home window for better readability
        - Set properties before RunScript, they auto-clear after use
        - Properties are checked only if next_focus parameter not provided
        - Format same as parameter: "condition::focus_id" or just "focus_id"
        - WARNING: Using both next_focus parameter and SkinInfo.CM_Focus properties logs warning and uses parameter

    Usage:
        # Reset to first item
        move_to_position("90011")

        # Reset multiple containers
        move_to_position("90011|90012|90013")

        # Reset with action on each
        move_to_position("90011|90012", main_action="Action(select)")
        # Result: Reset 90011→select, Reset 90012→select

        # Different actions per container
        move_to_position("90011|90012", main_action="Action(select)|Action(info)")
        # Result: Reset 90011→select, Reset 90012→info

        # Move main, then focus next containers
        move_to_position("90011", main_action="Action(select)", next_focus="50")
        # Result: Reset 90011→select, then Focus(50)

        # Move main to position, focus and move next containers
        move_to_position(
            main_focus="90011",
            main_position="5",
            next_focus="50|60",
            next_position="10|20",
            next_action="Action(select)"
        )
        # Result: Move 90011→5, Move 50→10→select, Move 60→20→select

        # Move to last item (from skin)
        move_to_position("90011", "$INFO[Container(90011).NumItems]")

        move_to_position(
            main_focus="90011|90012",
            next_focus="String.IsEqual(ListItem.Property(item.type),person)::9876||Window.IsActive(Home)::808||90003"
        )

        move_to_position(
            main_focus="90017|90016|90015",
            next_focus="![Window.IsActive(Home) + String.IsEqual(ListItem.DBTYPE,tvshow)]::8||909"
        )

        # Using SkinInfo.CM_Focus properties (more readable for complex conditions)
        <onload>SetProperty(SkinInfo.CM_Focus.1,String.IsEqual(ListItem.Property(item.type),person)::9876,home)</onload>
        <onload>SetProperty(SkinInfo.CM_Focus.2,Window.IsActive(Home) + String.IsEqual(ListItem.DBTYPE,tvshow)::808,home)</onload>
        <onload>SetProperty(SkinInfo.CM_Focus.3,90003,home)</onload>
        <onload>RunScript(script.skin.info.service,action=container_move,main_focus=90017|90016|90015)</onload>
    """
    main_ids = [cid.strip() for cid in main_focus.split('|')]

    main_action_list = [a.strip() for a in main_action.split('|')] if main_action else []
    next_action_list = [a.strip() for a in next_action.split('|')] if next_action else []

    has_pipe_main_action = main_action and '|' in main_action
    has_pipe_next_action = next_action and '|' in next_action

    main_position_list = [p.strip() for p in main_position.split('|')] if main_position and '|' in main_position else []
    has_pipe_main_position = main_position and '|' in main_position

    for idx, cid in enumerate(main_ids):
        if not cid:
            continue

        if not xbmc.getCondVisibility(f'Control.IsVisible({cid})'):
            continue

        if has_pipe_main_position and idx < len(main_position_list):
            position_str = main_position_list[idx]
        else:
            position_str = main_position

        if position_str is None or position_str == "":
            position = 0
            target_1indexed = "1"
        else:
            try:
                position_int = int(position_str)
                position = 0 if position_int <= 0 else position_int - 1
                target_1indexed = "1" if position_int <= 0 else str(position_int)
            except (ValueError, TypeError):
                continue

        is_updating = xbmc.getCondVisibility(f'Container({cid}).IsUpdating')
        if is_updating:
            xbmc.executebuiltin(f'Control.SetFocus({cid}, {position}, absolute)', True)
        else:
            current_item = xbmc.getInfoLabel(f'Container({cid}).CurrentItem')
            if current_item != target_1indexed:
                xbmc.executebuiltin(f'Control.SetFocus({cid}, {position}, absolute)', True)

        if has_pipe_main_action and idx < len(main_action_list) and main_action_list[idx]:
            xbmc.executebuiltin(main_action_list[idx], True)
        elif not has_pipe_main_action and main_action:
            xbmc.executebuiltin(main_action, True)

    properties_found = []
    for i in range(1, 100):
        prop_value = xbmc.getInfoLabel(f'Window(home).Property(SkinInfo.CM_Focus.{i})')
        if prop_value:
            properties_found.append((i, prop_value))
        else:
            break

    if next_focus and properties_found:
        from lib.kodi.client import log
        log("container_move", "Both next_focus parameter and CM_Focus properties set - using parameter, ignoring properties", xbmc.LOGWARNING)
        for i, _ in properties_found:
            xbmc.executebuiltin(f'ClearProperty(SkinInfo.CM_Focus.{i},home)', True)
        properties_found = []

    if next_focus:
        if '::' in next_focus:
            for block in next_focus.split('||'):
                block = block.strip()
                if not block:
                    continue

                if '::' in block:
                    condition, fid = block.split('::', 1)
                    condition = condition.strip()
                    fid = fid.strip()
                else:
                    condition = None
                    fid = block.strip()

                condition_met = True
                if condition:
                    condition_met = xbmc.getCondVisibility(condition)

                if condition_met and fid:
                    xbmc.executebuiltin(f'SetFocus({fid})', True)
                    return
        else:
            next_ids = [fid.strip() for fid in next_focus.split('|')]
            next_position_list = [p.strip() for p in next_position.split('|')] if next_position and '|' in next_position else []
            has_pipe_next_position = next_position and '|' in next_position

            for idx, fid in enumerate(next_ids):
                if not fid:
                    continue

                xbmc.executebuiltin(f'SetFocus({fid})', True)

                if has_pipe_next_position and idx < len(next_position_list):
                    position_str = next_position_list[idx]
                else:
                    position_str = next_position

                if position_str:
                    try:
                        position_int = int(position_str)
                        position = 0 if position_int <= 0 else position_int - 1
                    except (ValueError, TypeError):
                        continue

                    xbmc.executebuiltin(f'Control.SetFocus({fid}, {position}, absolute)', True)

                if has_pipe_next_action and idx < len(next_action_list) and next_action_list[idx]:
                    xbmc.executebuiltin(next_action_list[idx], True)
                elif not has_pipe_next_action and next_action:
                    xbmc.executebuiltin(next_action, True)
    elif properties_found:
        for i, prop_value in properties_found:
            block = prop_value.strip()
            if not block:
                continue

            if '::' in block:
                condition, fid = block.split('::', 1)
                condition = condition.strip()
                fid = fid.strip()
            else:
                condition = None
                fid = block.strip()

            condition_met = True
            if condition:
                condition_met = xbmc.getCondVisibility(condition)

            if condition_met and fid:
                xbmc.executebuiltin(f'SetFocus({fid})', True)
                for j, _ in properties_found:
                    xbmc.executebuiltin(f'ClearProperty(SkinInfo.CM_Focus.{j},home)', True)
                return

        for i, _ in properties_found:
            xbmc.executebuiltin(f'ClearProperty(SkinInfo.CM_Focus.{i},home)', True)


def jump_letter(letter: str, container_id: Optional[str] = None) -> None:
    """
    Jump to item starting with specified letter using Kodi's SMS actions.

    Args:
        letter: Target letter (A-Z) or # for first/last page
        container_id: Container to jump in (optional, uses current if None)

    Executes SMS action repeatedly and checks ListItem.SortLetter until
    the target letter is reached. This is the only reliable method available
    to addons, as direct KEY_UNICODE actions are not exposed via JSON-RPC.
    """
    if container_id:
        xbmc.executebuiltin(f'SetFocus({container_id})', True)

    letter_upper = letter.upper()

    if letter_upper == '#':
        sort_order = xbmc.getInfoLabel('Container.SortOrder')
        action = 'lastpage' if 'descending' in sort_order.lower() else 'firstpage'
        request('Input.ExecuteAction', {'action': action})
        return

    sms_map = {
        'A': 'jumpsms2', 'B': 'jumpsms2', 'C': 'jumpsms2',
        'D': 'jumpsms3', 'E': 'jumpsms3', 'F': 'jumpsms3',
        'G': 'jumpsms4', 'H': 'jumpsms4', 'I': 'jumpsms4',
        'J': 'jumpsms5', 'K': 'jumpsms5', 'L': 'jumpsms5',
        'M': 'jumpsms6', 'N': 'jumpsms6', 'O': 'jumpsms6',
        'P': 'jumpsms7', 'Q': 'jumpsms7', 'R': 'jumpsms7', 'S': 'jumpsms7',
        'T': 'jumpsms8', 'U': 'jumpsms8', 'V': 'jumpsms8',
        'W': 'jumpsms9', 'X': 'jumpsms9', 'Y': 'jumpsms9', 'Z': 'jumpsms9',
    }

    action = sms_map.get(letter_upper)
    if not action:
        return

    for _ in range(5):
        request('Input.ExecuteAction', {'action': action})
        xbmc.sleep(30)

        if xbmc.getInfoLabel('ListItem.SortLetter').upper() == letter_upper:
            break


def handle_letter_jump_list(handle: int, params: dict) -> None:
    """
    Plugin action that returns A-Z letter list for container navigation.

    Automatically reverses order (Z-A) when container is sorted descending.
    Clicking a letter executes jump via RunScript to avoid blocking.

    Args:
        handle: Plugin handle
        params: URL parameters
            target: Container ID to jump in (default: 50)
    """
    target = params.get('target', ['50'])[0]

    sort_order = xbmc.getInfoLabel(f'Container({target}).SortOrder')
    is_descending = 'descending' in sort_order.lower()

    letters = 'ZYXWVUTSRQPONMLKJIHGFEDCBA#' if is_descending else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#'

    current_sort_letter = xbmc.getInfoLabel(f'Container({target}).ListItem.SortLetter').upper()

    for letter in letters:
        listitem = xbmcgui.ListItem(letter, offscreen=True)

        if letter == current_sort_letter:
            url = ''
            listitem.setProperty('IsCurrentLetter', 'true')
        else:
            url = f'plugin://script.skin.info.service/?action=jump_letter_exec&letter={letter}&target={target}'

        xbmcplugin.addDirectoryItem(handle, url, listitem, False)

    xbmcplugin.setContent(handle, '')
    xbmcplugin.endOfDirectory(handle)


def handle_letter_jump_exec(handle: int, params: dict) -> None:
    """
    Execute letter jump action.

    Args:
        handle: Plugin handle
        params: URL parameters
            letter: Letter to jump to (A-Z or #)
            target: Container ID to jump in
    """
    try:
        xbmcplugin.setResolvedUrl(handle, succeeded=False, listitem=xbmcgui.ListItem())
    except Exception:
        pass

    letter = params.get('letter', [''])[0]
    target = params.get('target', [''])[0]

    if not letter:
        return

    current_sort_letter = xbmc.getInfoLabel(f'Container({target}).ListItem.SortLetter').upper()
    if letter.upper() == current_sort_letter:
        return

    jump_letter(letter, target)
