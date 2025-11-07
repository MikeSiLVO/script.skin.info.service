"""Entry point and menu structure for metadata editor."""
from __future__ import annotations

from typing import Any

import xbmc
import xbmcaddon
import xbmcgui

from lib.infrastructure.dialogs import show_notification
from lib.infrastructure.menus import Menu, MenuItem
from lib.kodi.client import log
from lib.editor.config import (
    MEDIA_TYPE_FIELDS,
    FieldType,
    get_field_def,
    get_fields_for_media_type,
)
from lib.editor.handlers import (
    handle_date,
    handle_integer,
    handle_list,
    handle_ratings,
    handle_runtime,
    handle_status,
    handle_text,
    handle_userrating,
)
from lib.editor.operations import get_item_for_editing, save_field
from lib.editor.utilities import (
    format_runtime_value_for_display,
    format_value_for_display,
)

ADDON = xbmcaddon.Addon()


def run_editor(dbid: str | None = None, dbtype: str | None = None) -> None:
    """Main entry point for metadata editor."""
    if not dbid:
        dbid = xbmc.getInfoLabel("ListItem.DBID")
    if not dbtype:
        dbtype = xbmc.getInfoLabel("ListItem.DBType")

    if not dbid or dbid == "-1" or not dbtype:
        show_notification(
            ADDON.getLocalizedString(32258),
            ADDON.getLocalizedString(32259),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    media_type = dbtype.lower()

    if media_type not in MEDIA_TYPE_FIELDS:
        show_notification(
            ADDON.getLocalizedString(32258),
            ADDON.getLocalizedString(32263).format(media_type),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    dbid_int = int(dbid)

    item = get_item_for_editing(dbid_int, media_type)
    if not item:
        show_notification(
            ADDON.getLocalizedString(32258),
            ADDON.getLocalizedString(32262),
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        return

    title = item.get("title", "Unknown")
    log("Editor", f"Editing {media_type} '{title}' (dbid={dbid_int})", xbmc.LOGDEBUG)

    _show_main_menu(dbid_int, media_type, item, title)


def _show_main_menu(
    dbid: int, media_type: str, item: dict[str, Any], title: str
) -> None:
    """Show flattened field menu with all editable fields."""
    fields = get_fields_for_media_type(media_type)

    menu_items = []
    for field in fields:
        field_def = get_field_def(field)
        if not field_def:
            continue

        current = item.get(field_def["get_property"])
        display_name = field_def["display_name"]
        field_type = field_def["field_type"]

        if field == "runtime":
            value_display = format_runtime_value_for_display(current or 0)
        else:
            value_display = format_value_for_display(current, field_type)

        # External Ratings opens submenu, others edit directly
        if field_type == FieldType.RATINGS:
            label = f"{display_name}..."
        else:
            label = f"{display_name}: {value_display}"

        menu_items.append(MenuItem(
            label,
            lambda f=field: _edit_field(dbid, media_type, item, f),
            loop=True
        ))

    menu = Menu(ADDON.getLocalizedString(32560).format(title), menu_items)
    menu.show()


def _edit_field(
    dbid: int, media_type: str, item: dict[str, Any], field: str
) -> None:
    """Edit a single field."""
    field_def = get_field_def(field)
    if not field_def:
        return

    current = item.get(field_def["get_property"])
    display_name = field_def["display_name"]
    field_type = field_def["field_type"]

    new_value: Any
    cancelled: bool

    if field_type == FieldType.TEXT:
        new_value, cancelled = handle_text(display_name, current)

    elif field_type == FieldType.TEXT_LONG:
        new_value, cancelled = handle_text(display_name, current, is_long=True)

    elif field_type == FieldType.INTEGER:
        if field == "runtime":
            new_value, cancelled = handle_runtime(display_name, current)
        elif field == "year":
            new_value, cancelled = handle_integer(display_name, current, validator="year")
        elif field == "top250":
            new_value, cancelled = handle_integer(display_name, current, validator="top250")
        else:
            new_value, cancelled = handle_integer(display_name, current)

    elif field_type == FieldType.NUMBER:
        new_value, cancelled = handle_integer(display_name, current)

    elif field_type == FieldType.DATE:
        new_value, cancelled = handle_date(display_name, current)

    elif field_type == FieldType.LIST:
        new_value, cancelled = handle_list(display_name, current, media_type, field)

    elif field_type == FieldType.USERRATING:
        new_value, cancelled = handle_userrating(display_name, current)

    elif field_type == FieldType.RATINGS:
        new_value, cancelled = handle_ratings(display_name, current)

    elif field_type == FieldType.STATUS:
        new_value, cancelled = handle_status(display_name, current)

    else:
        show_notification(ADDON.getLocalizedString(32258), ADDON.getLocalizedString(32250), xbmcgui.NOTIFICATION_WARNING)
        return

    if cancelled:
        return

    if save_field(dbid, media_type, field, new_value):
        item[field_def["get_property"]] = new_value
        show_notification(ADDON.getLocalizedString(32258), f"{display_name} updated", xbmcgui.NOTIFICATION_INFO, 2000)
        xbmc.executebuiltin("Container.Refresh")
    else:
        show_notification(ADDON.getLocalizedString(32258), ADDON.getLocalizedString(32251), xbmcgui.NOTIFICATION_ERROR, 3000)
