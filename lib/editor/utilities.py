"""Validation and formatting utilities for metadata editor."""
from __future__ import annotations

import re
from typing import Any

from lib.editor.config import FieldType


def validate_date(value: str) -> tuple[bool, str]:
    """Validate YYYY-MM-DD date format."""
    if not value:
        return True, ""

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return False, "Invalid date format (use YYYY-MM-DD)"

    try:
        year, month, day = map(int, value.split("-"))
        if not (1 <= month <= 12):
            return False, "Month must be 1-12"
        if not (1 <= day <= 31):
            return False, "Day must be 1-31"
        if year < 1800 or year > 2100:
            return False, "Year seems invalid"
    except ValueError:
        return False, "Invalid date"

    return True, ""


def validate_year(value: int) -> tuple[bool, str]:
    """Validate year value."""
    if value == 0:
        return True, ""
    if value < 1800 or value > 2100:
        return False, "Year must be between 1800 and 2100"
    return True, ""


def validate_runtime(value: int) -> tuple[bool, str]:
    """Validate runtime in seconds."""
    if value < 0:
        return False, "Runtime cannot be negative"
    if value > 86400 * 7:
        return False, "Runtime seems too large (max 7 days)"
    return True, ""


def validate_rating(value: float) -> tuple[bool, str]:
    """Validate rating 0-10."""
    if not 0 <= value <= 10:
        return False, "Rating must be 0-10"
    return True, ""


def validate_userrating(value: int) -> tuple[bool, str]:
    """Validate user rating 0-10."""
    if not 0 <= value <= 10:
        return False, "User rating must be 0-10"
    return True, ""


def validate_top250(value: int) -> tuple[bool, str]:
    """Validate top 250 position."""
    if value < 0:
        return False, "Top 250 cannot be negative"
    if value > 250:
        return False, "Top 250 must be 0-250"
    return True, ""


def format_runtime_display(seconds: int) -> str:
    """Format runtime seconds for display."""
    if not seconds:
        return "(not set)"

    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60

    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_runtime_for_edit(seconds: int) -> str:
    """Format runtime seconds as minutes for editing."""
    if not seconds:
        return ""
    return str(seconds // 60)


def parse_runtime_from_edit(minutes_str: str) -> int:
    """Parse minutes string to runtime seconds."""
    if not minutes_str:
        return 0
    try:
        minutes = int(minutes_str)
        return minutes * 60
    except ValueError:
        return 0


def format_list_display(values: list[str] | None, max_items: int = 3) -> str:
    """Format list values for display in menu."""
    if not values:
        return "(not set)"

    if len(values) <= max_items:
        return ", ".join(values)

    shown = ", ".join(values[:max_items])
    return f"{shown} (+{len(values) - max_items} more)"


def format_userrating_display(value: int) -> str:
    """Format user rating for display."""
    if not value:
        return "(not rated)"
    return f"{value}/10"


def format_ratings_display(ratings: dict[str, Any] | None) -> str:
    """Format external ratings dict for display."""
    if not ratings:
        return "(no ratings)"

    parts = []
    for source, data in ratings.items():
        if isinstance(data, dict):
            rating = data.get("rating", 0)
            parts.append(f"{source}: {rating:.1f}")
        else:
            parts.append(f"{source}: {data}")

    if not parts:
        return "(no ratings)"

    return ", ".join(parts[:3])


def format_value_for_display(value: Any, field_type: FieldType) -> str:
    """Format a field value for menu display based on type."""
    if value is None:
        return "(not set)"

    if field_type == FieldType.TEXT or field_type == FieldType.TEXT_LONG:
        if not value:
            return "(not set)"
        text = str(value)
        if len(text) > 50:
            return text[:47] + "..."
        return text

    if field_type == FieldType.INTEGER:
        if not value:
            return "(not set)"
        return str(value)

    if field_type == FieldType.NUMBER:
        if not value:
            return "(not set)"
        return f"{value:.1f}"

    if field_type == FieldType.DATE:
        if not value:
            return "(not set)"
        return str(value)

    if field_type == FieldType.LIST:
        return format_list_display(value)

    if field_type == FieldType.USERRATING:
        return format_userrating_display(value)

    if field_type == FieldType.RATINGS:
        return format_ratings_display(value)

    if field_type == FieldType.STATUS:
        if not value:
            return "(not set)"
        return str(value).title()

    return str(value) if value else "(not set)"


def format_runtime_value_for_display(seconds: int) -> str:
    """Special formatting for runtime field in menu."""
    return format_runtime_display(seconds)
