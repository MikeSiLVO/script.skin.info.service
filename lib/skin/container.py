"""Container manipulation utilities for skin integration."""
from __future__ import annotations

from typing import Optional
import xbmc
import xbmcgui
import xbmcplugin

from lib.kodi.client import log, request


_SMS_MAP = {
    'A': 'jumpsms2', 'B': 'jumpsms2', 'C': 'jumpsms2',
    'D': 'jumpsms3', 'E': 'jumpsms3', 'F': 'jumpsms3',
    'G': 'jumpsms4', 'H': 'jumpsms4', 'I': 'jumpsms4',
    'J': 'jumpsms5', 'K': 'jumpsms5', 'L': 'jumpsms5',
    'M': 'jumpsms6', 'N': 'jumpsms6', 'O': 'jumpsms6',
    'P': 'jumpsms7', 'Q': 'jumpsms7', 'R': 'jumpsms7', 'S': 'jumpsms7',
    'T': 'jumpsms8', 'U': 'jumpsms8', 'V': 'jumpsms8',
    'W': 'jumpsms9', 'X': 'jumpsms9', 'Y': 'jumpsms9', 'Z': 'jumpsms9',
}


def _evaluate_conditional_focus(blocks: list[str]) -> None:
    """Evaluate condition::focus_id blocks in order, focusing first match."""
    for block in blocks:
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

        if condition and not xbmc.getCondVisibility(condition):
            continue

        if fid:
            xbmc.executebuiltin(f'SetFocus({fid})', True)
            return


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
        main_position: Target position for main containers (1-indexed, same as
                      Container.CurrentItem)
                      If None or "0", resets to first item (position 1)
                      Supports pipe-separated values for different positions per container
        main_action: Optional builtin(s) to execute after moving each main container
                     (pipe-separated)
        next_focus: Optional container ID(s) to focus after main containers
                   Unconditional: "90003" or "50|60" (pipe-separated, focus all)
                   Conditional: "condition::focus_id||condition::focus_id||focus_id"
                   (evaluate in order, focus first match)
        next_position: Target position for next containers (1-indexed)
                      If None, just focuses without moving
                      Supports pipe-separated values for different positions per container
                      Only works with unconditional next_focus
        next_action: Optional builtin(s) to execute after focusing/moving each next
                    container (pipe-separated)
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
        - Use SkinInfo.CM_Focus.1, SkinInfo.CM_Focus.2, etc. properties on home window
          for better readability
        - Set properties before RunScript, they auto-clear after use
        - Properties are checked only if next_focus parameter not provided
        - Format same as parameter: "condition::focus_id" or just "focus_id"
        - WARNING: Using both next_focus parameter and SkinInfo.CM_Focus properties logs
          warning and uses parameter

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
        <onload>SetProperty(SkinInfo.CM_Focus.2,Window.IsActive(Home) +
                 String.IsEqual(ListItem.DBTYPE,tvshow)::808,home)</onload>
        <onload>SetProperty(SkinInfo.CM_Focus.3,90003,home)</onload>
        <onload>RunScript(script.skin.info.service,action=container_move,main_focus=90017|90016|90015)</onload>
    """
    _move_main_containers(main_focus, main_position, main_action)
    _handle_next_focus(next_focus, next_position, next_action)


def _move_main_containers(main_focus: str, main_position: Optional[str],
                          main_action: Optional[str]) -> None:
    """Reset each visible control in `main_focus` to its target, skipping any already there.

    List containers reset to their target item (guarded by `CurrentItem`); non-list controls
    (buttons) get focus (guarded by `HasFocus`). Applying the position guard to a button was the
    bug: it has no item position, so `CurrentItem` is always empty and it re-focused every call.
    """
    main_ids = [cid.strip() for cid in main_focus.split('|')]
    main_action_list = [a.strip() for a in main_action.split('|')] if main_action else []
    has_pipe_main_action = main_action and '|' in main_action
    main_position_list = (
        [p.strip() for p in main_position.split('|')]
        if main_position and '|' in main_position else []
    )
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

        try:
            item_count = int(xbmc.getInfoLabel(f'Container({cid}).NumItems') or 0)
        except ValueError:
            item_count = 0

        if item_count > 0:
            should_move = (
                xbmc.getInfoLabel(f'Container({cid}).CurrentItem') != target_1indexed
            )
        else:
            should_move = not xbmc.getCondVisibility(f'Control.HasFocus({cid})')

        if should_move:
            xbmc.executebuiltin(f'Control.SetFocus({cid}, {position}, absolute)', True)

        if has_pipe_main_action and idx < len(main_action_list) and main_action_list[idx]:
            xbmc.executebuiltin(main_action_list[idx], True)
        elif not has_pipe_main_action and main_action:
            xbmc.executebuiltin(main_action, True)


def _handle_next_focus(next_focus: Optional[str], next_position: Optional[str],
                       next_action: Optional[str]) -> None:
    """Resolve next-focus from parameter (preferred), else `SkinInfo.CM_Focus.*` properties."""
    properties_found = []
    for i in range(1, 100):
        prop_value = xbmc.getInfoLabel(f'Window(home).Property(SkinInfo.CM_Focus.{i})')
        if prop_value:
            properties_found.append((i, prop_value))
        else:
            break

    if next_focus and properties_found:
        log(
            "ContainerMove",
            "Both next_focus parameter and CM_Focus properties set - "
            "using parameter, ignoring properties",
            xbmc.LOGWARNING,
        )
        _clear_cm_focus_props(properties_found)
        properties_found = []

    if next_focus:
        if '::' in next_focus:
            _evaluate_conditional_focus(next_focus.split('||'))
            return
        _focus_next_containers(next_focus, next_position, next_action)
    elif properties_found:
        _evaluate_conditional_focus([prop_value for _, prop_value in properties_found])
        _clear_cm_focus_props(properties_found)


def _focus_next_containers(next_focus: str, next_position: Optional[str],
                          next_action: Optional[str]) -> None:
    """Focus and optionally position each container in `next_focus` (pipe-separated IDs)."""
    next_ids = [fid.strip() for fid in next_focus.split('|')]
    next_action_list = [a.strip() for a in next_action.split('|')] if next_action else []
    has_pipe_next_action = next_action and '|' in next_action
    next_position_list = (
        [p.strip() for p in next_position.split('|')]
        if next_position and '|' in next_position else []
    )
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


def _clear_cm_focus_props(properties_found: list) -> None:
    """Clear `SkinInfo.CM_Focus.{i}` for each `(i, _)` in `properties_found`."""
    for i, _ in properties_found:
        xbmc.executebuiltin(f'ClearProperty(SkinInfo.CM_Focus.{i},home)', True)


def jump_letter(letter: str, container_id: Optional[str] = None) -> None:
    """Jump to an item starting with `letter` (A-Z or `#`) via Kodi's SMS actions."""
    if container_id:
        xbmc.executebuiltin(f'SetFocus({container_id})', True)

    letter_upper = letter.upper()

    if letter_upper == '#':
        is_descending = xbmc.getCondVisibility('Container.SortDirection(descending)')
        action = 'lastpage' if is_descending else 'firstpage'
        request('Input.ExecuteAction', {'action': action})
        return

    action = _SMS_MAP.get(letter_upper)
    if not action:
        return

    for _ in range(5):
        request('Input.ExecuteAction', {'action': action})
        xbmc.sleep(30)

        if xbmc.getInfoLabel('ListItem.SortLetter').upper() == letter_upper:
            break


_SCAN_CHUNK = 1000


def _available_sort_letters(target: str) -> set[str]:
    """Jump letters (A-Z plus '#') that have at least one item in the target container.

    Reads the items' SortLetter in batched `GetInfoLabels` calls (a chunk per request) rather
    than one round-trip per item, so a big container costs a handful of calls, not thousands.
    Reads the live container, so active filters and the current sort are honoured. Non-alphabetic
    sort letters (digits, symbols) collapse to '#'.
    """
    try:
        count = int(xbmc.getInfoLabel(f'Container({target}).NumItems') or 0)
    except ValueError:
        count = 0

    found: set[str] = set()
    for start in range(0, count, _SCAN_CHUNK):
        labels = [
            f'Container({target}).ListItemAbsolute({i}).SortLetter'
            for i in range(start, min(start + _SCAN_CHUNK, count))
        ]
        response = request('XBMC.GetInfoLabels', {'labels': labels})
        for value in (response.get('result', {}) if response else {}).values():
            if not value:
                continue
            first = value[0].upper()
            found.add(first if 'A' <= first <= 'Z' else '#')
        if len(found) >= 27:
            break
    return found


def handle_letter_jump_list(handle: int, params: dict) -> None:
    """Return A-Z ListItems for container letter-jump (reversed to Z-A when sorted descending).

    Letters that have an item in the target container get `IsAvailable` set so skins can dim the
    empty ones. Pass `showall=false` to drop the empty letters entirely (compact bar) instead.
    """
    target = params.get('target', ['50'])[0]
    showall = params.get('showall', ['true'])[0].lower() != 'false'

    is_descending = xbmc.getCondVisibility(f'Container({target}).SortDirection(descending)')

    letters = 'ZYXWVUTSRQPONMLKJIHGFEDCBA#' if is_descending else 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#'

    available = _available_sort_letters(target)

    current_sort_letter = xbmc.getInfoLabel(f'Container({target}).ListItem.SortLetter').upper()

    for letter in letters:
        is_available = letter in available
        if not showall and not is_available:
            continue

        listitem = xbmcgui.ListItem(letter, offscreen=True)

        if letter == current_sort_letter:
            url = ''
            listitem.setProperty('IsCurrentLetter', 'true')
        else:
            url = f'plugin://script.skin.info.service/?action=jump_letter_exec&letter={letter}&target={target}'

        if is_available:
            listitem.setProperty('IsAvailable', 'true')

        xbmcplugin.addDirectoryItem(handle, url, listitem, False)

    xbmcplugin.setContent(handle, '')
    xbmcplugin.endOfDirectory(handle)


def handle_letter_jump_exec(handle: int, params: dict) -> None:
    """Execute letter jump from `?action=jump_letter_exec&letter=X&target=N`."""
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
