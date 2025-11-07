"""Field type handlers for metadata editor."""
from __future__ import annotations

from typing import Any

import xbmc
import xbmcaddon
import xbmcgui

from lib.infrastructure.dialogs import show_select, show_yesno
from lib.editor.config import TVSHOW_STATUS_VALUES
from lib.editor.operations import fetch_library_values_for_field
from lib.editor.utilities import (
    format_runtime_for_edit,
    parse_runtime_from_edit,
    validate_date,
    validate_rating,
    validate_runtime,
    validate_top250,
    validate_year,
)

ADDON = xbmcaddon.Addon()


def handle_text(
    field_name: str, current_value: str | None, is_long: bool = False
) -> tuple[str | None, bool]:
    """Handle text input."""
    heading = f"Edit {field_name}"
    default = current_value or ""

    result = xbmcgui.Dialog().input(heading, default)

    if result == "":
        return None, True

    return result, False


def handle_integer(
    field_name: str, current_value: int | None, validator: str | None = None
) -> tuple[int | None, bool]:
    """Handle integer input."""
    heading = f"Edit {field_name}"
    default = str(current_value) if current_value else ""

    result = xbmcgui.Dialog().input(heading, default, type=xbmcgui.INPUT_NUMERIC)

    if not result:
        return None, True

    try:
        value = int(result)
    except ValueError:
        return None, True

    if validator == "year":
        valid, error = validate_year(value)
    elif validator == "runtime":
        valid, error = validate_runtime(value)
    elif validator == "top250":
        valid, error = validate_top250(value)
    else:
        valid, error = True, ""

    if not valid:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(32254), error)
        return None, True

    return value, False


def handle_runtime(
    field_name: str, current_value: int | None
) -> tuple[int | None, bool]:
    """Handle runtime input (edit in minutes, store in seconds)."""
    heading = f"Edit {field_name} (minutes)"
    default = format_runtime_for_edit(current_value or 0)

    result = xbmcgui.Dialog().input(heading, default, type=xbmcgui.INPUT_NUMERIC)

    if not result:
        return None, True

    seconds = parse_runtime_from_edit(result)

    valid, error = validate_runtime(seconds)
    if not valid:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(32254), error)
        return None, True

    return seconds, False


def handle_date(
    field_name: str, current_value: str | None
) -> tuple[str | None, bool]:
    """Handle date input (YYYY-MM-DD)."""
    heading = f"Edit {field_name} (YYYY-MM-DD)"
    default = current_value or ""

    result = xbmcgui.Dialog().input(heading, default)

    if not result:
        return None, True

    valid, error = validate_date(result)
    if not valid:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(32255), error)
        return None, True

    return result, False


def handle_userrating(
    field_name: str, current_value: int | None
) -> tuple[int | None, bool]:
    """Handle 1-10 user rating selection."""
    options = [ADDON.getLocalizedString(32391)] + [str(i) for i in range(1, 11)]
    preselect = current_value if current_value else 0

    choice = show_select(ADDON.getLocalizedString(32556).format(field_name), options, preselect=preselect)

    if choice < 0:
        return None, True

    return choice, False


def handle_status(
    field_name: str, current_value: str | None
) -> tuple[str | None, bool]:
    """Handle TV show status selection."""
    options = [ADDON.getLocalizedString(32392)] + [s.title() for s in TVSHOW_STATUS_VALUES[1:]]

    preselect = 0
    if current_value:
        current_lower = current_value.lower()
        for i, status in enumerate(TVSHOW_STATUS_VALUES):
            if status == current_lower:
                preselect = i
                break

    choice = show_select(ADDON.getLocalizedString(32556).format(field_name), options, preselect=preselect)

    if choice < 0:
        return None, True

    return TVSHOW_STATUS_VALUES[choice], False


def handle_list(
    field_name: str,
    current_values: list[str] | None,
    media_type: str,
    field_key: str
) -> tuple[list[str] | None, bool]:
    """Handle list editing with 3 UX options."""
    values = list(current_values) if current_values else []

    current_display = ", ".join(values) if values else ADDON.getLocalizedString(32392)
    options = [
        ADDON.getLocalizedString(32395).format(current_display),
        ADDON.getLocalizedString(32396),
        ADDON.getLocalizedString(32397),
    ]

    choice = show_select(ADDON.getLocalizedString(32557).format(field_name), options)

    if choice < 0:
        return None, True

    if choice == 0:
        return _quick_edit_list(field_name, values)
    elif choice == 1:
        return _select_from_library(field_name, values, media_type, field_key)
    else:
        return _add_remove_items(field_name, values)


def _quick_edit_list(
    field_name: str, current: list[str]
) -> tuple[list[str] | None, bool]:
    """Edit list as comma-separated string."""
    current_str = ", ".join(current)
    heading = f"Edit {field_name} (comma-separated)"

    result = xbmcgui.Dialog().input(heading, current_str)

    if result is None or result == "":
        return None, True

    parsed = [x.strip() for x in result.split(",") if x.strip()]
    return parsed, False


def _select_from_library(
    field_name: str, current: list[str], media_type: str, field_key: str
) -> tuple[list[str] | None, bool]:
    """Show multiselect with existing library values."""
    library_values = fetch_library_values_for_field(field_key, media_type)

    if not library_values:
        xbmcgui.Dialog().ok(
            ADDON.getLocalizedString(32390),
            f"No existing {field_name} found in library.\n"
            "Use Quick Edit or Add/Remove instead."
        )
        return None, True

    # Add current values that aren't in library
    all_values: list[str] = list(library_values)
    for val in current:
        if val not in all_values:
            all_values.append(val)

    preselect = [i for i, v in enumerate(all_values) if v in current]

    result = xbmcgui.Dialog().multiselect(
        f"Select {field_name}",
        all_values,  # type: ignore[arg-type]
        preselect=preselect
    )

    if result is None:
        return None, True

    return [all_values[i] for i in result], False


def _add_remove_items(
    field_name: str, current: list[str]
) -> tuple[list[str] | None, bool]:
    """Interactive add/remove loop."""
    items = list(current)

    while True:
        options = [f"[+] Add {field_name}"]
        for item in items:
            options.append(f"[-] {item}")
        options.append(f"[{ADDON.getLocalizedString(32393)}]")
        options.append(f"[{xbmc.getLocalizedString(222)}]")

        choice = show_select(ADDON.getLocalizedString(32557).format(field_name), options)

        if choice < 0 or choice == len(options) - 1:
            return None, True

        if choice == 0:
            new_item = xbmcgui.Dialog().input(ADDON.getLocalizedString(32394).format(field_name))
            if new_item and new_item.strip():
                items.append(new_item.strip())

        elif choice == len(options) - 2:
            return items, False

        else:
            item_index = choice - 1
            if 0 <= item_index < len(items):
                del items[item_index]


def handle_ratings(
    field_name: str, current_ratings: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, bool]:
    """Handle external ratings editing. Returns updated ratings after each change."""
    ratings = dict(current_ratings) if current_ratings else {}
    modified = False

    while True:
        options = []
        sources = list(ratings.keys())

        for source in sources:
            data = ratings[source]
            if isinstance(data, dict):
                rating = data.get("rating", 0)
                votes = data.get("votes", 0)
                default_mark = " [Default]" if data.get("default") else ""
                options.append(f"{source}: {rating:.1f} ({votes:,} votes){default_mark}")
            else:
                options.append(f"{source}: {data}")

        options.append("[+] Add Rating Source")

        choice = show_select(ADDON.getLocalizedString(32557).format(field_name), options)

        if choice < 0:
            return (ratings, False) if modified else (None, True)

        if choice == len(sources):
            if _add_rating_source(ratings):
                modified = True
        elif choice < len(sources):
            source = sources[choice]
            if _edit_single_rating(ratings, source):
                modified = True


def _add_rating_source(ratings: dict[str, Any]) -> bool:
    """Add a new rating source. Returns True if added."""
    source = xbmcgui.Dialog().input(ADDON.getLocalizedString(32252))
    if not source or not source.strip():
        return False

    source = source.strip().lower()

    if source in ratings:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(32257), ADDON.getLocalizedString(32564).format(source))
        return False

    rating_str = xbmcgui.Dialog().input(ADDON.getLocalizedString(32565), "0", type=xbmcgui.INPUT_NUMERIC)
    if not rating_str:
        return False

    try:
        rating = float(rating_str)
    except ValueError:
        return False

    valid, error = validate_rating(rating)
    if not valid:
        xbmcgui.Dialog().ok(ADDON.getLocalizedString(32256), error)
        return False

    votes_str = xbmcgui.Dialog().input(ADDON.getLocalizedString(32253), "0", type=xbmcgui.INPUT_NUMERIC)
    votes = int(votes_str) if votes_str else 0

    is_default = not ratings
    ratings[source] = {"rating": rating, "votes": votes, "default": is_default}
    return True


def _edit_single_rating(ratings: dict[str, Any], source: str) -> bool:
    """Edit a single rating source. Returns True if modified."""
    options = [
        "Edit Rating Value",
        f"Edit {ADDON.getLocalizedString(32253)}",
        "Set as Default",
        "Remove This Rating",
    ]

    choice = show_select(ADDON.getLocalizedString(32557).format(source), options)

    if choice < 0:
        return False

    data = ratings[source]
    if not isinstance(data, dict):
        data = {"rating": float(data), "votes": 0, "default": False}
        ratings[source] = data

    if choice == 0:
        current = data.get("rating", 0)
        result = xbmcgui.Dialog().input(
            "Rating (0-10)", f"{current:.1f}", type=xbmcgui.INPUT_NUMERIC
        )
        if result:
            try:
                new_rating = float(result)
                valid, error = validate_rating(new_rating)
                if valid:
                    data["rating"] = new_rating
                    return True
                else:
                    xbmcgui.Dialog().ok(ADDON.getLocalizedString(32256), error)
            except ValueError:
                pass

    elif choice == 1:
        current = data.get("votes", 0)
        result = xbmcgui.Dialog().input(
            ADDON.getLocalizedString(32253), str(current), type=xbmcgui.INPUT_NUMERIC
        )
        if result:
            try:
                data["votes"] = int(result)
                return True
            except ValueError:
                pass

    elif choice == 2:
        for s in ratings:
            if isinstance(ratings[s], dict):
                ratings[s]["default"] = s == source
        return True

    elif choice == 3:
        if show_yesno(ADDON.getLocalizedString(32301), ADDON.getLocalizedString(32302).format(source)):
            del ratings[source]
            return True

    return False
