"""Field definitions and media type configuration for metadata editor."""
from __future__ import annotations

from enum import Enum
from typing import TypedDict


class FieldType(Enum):
    """Types of editable fields."""

    TEXT = "text"
    TEXT_LONG = "text_long"
    INTEGER = "integer"
    NUMBER = "number"
    DATE = "date"
    LIST = "list"
    USERRATING = "userrating"
    RATINGS = "ratings"
    STATUS = "status"


class FieldDef(TypedDict):
    """Definition for an editable field."""

    api_name: str
    display_name: str
    field_type: FieldType
    category: str
    get_property: str


CATEGORY_CORE_TEXT = "Core Text"
CATEGORY_DATES_NUMBERS = "Dates & Numbers"
CATEGORY_LISTS = "Lists"
CATEGORY_RATINGS = "Ratings"

FIELD_DEFINITIONS: dict[str, FieldDef] = {
    # Core Text
    "title": {
        "api_name": "title",
        "display_name": "Title",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "title",
    },
    "plot": {
        "api_name": "plot",
        "display_name": "Plot",
        "field_type": FieldType.TEXT_LONG,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "plot",
    },
    "tagline": {
        "api_name": "tagline",
        "display_name": "Tagline",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "tagline",
    },
    "sorttitle": {
        "api_name": "sorttitle",
        "display_name": "Sort Title",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "sorttitle",
    },
    "originaltitle": {
        "api_name": "originaltitle",
        "display_name": "Original Title",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "originaltitle",
    },
    # Dates & Numbers
    "year": {
        "api_name": "year",
        "display_name": "Year",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "year",
    },
    "premiered": {
        "api_name": "premiered",
        "display_name": "Premiered",
        "field_type": FieldType.DATE,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "premiered",
    },
    "firstaired": {
        "api_name": "firstaired",
        "display_name": "First Aired",
        "field_type": FieldType.DATE,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "firstaired",
    },
    "runtime": {
        "api_name": "runtime",
        "display_name": "Runtime",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "runtime",
    },
    "mpaa": {
        "api_name": "mpaa",
        "display_name": "MPAA Rating",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "mpaa",
    },
    "top250": {
        "api_name": "top250",
        "display_name": "Top 250",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "top250",
    },
    # Lists
    "genre": {
        "api_name": "genre",
        "display_name": "Genre",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "genre",
    },
    "studio": {
        "api_name": "studio",
        "display_name": "Studio",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "studio",
    },
    "director": {
        "api_name": "director",
        "display_name": "Director",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "director",
    },
    "writer": {
        "api_name": "writer",
        "display_name": "Writer",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "writer",
    },
    "country": {
        "api_name": "country",
        "display_name": "Country",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "country",
    },
    "tag": {
        "api_name": "tag",
        "display_name": "Tags",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "tag",
    },
    # Ratings
    "userrating": {
        "api_name": "userrating",
        "display_name": "User Rating",
        "field_type": FieldType.USERRATING,
        "category": CATEGORY_RATINGS,
        "get_property": "userrating",
    },
    "ratings": {
        "api_name": "ratings",
        "display_name": "External Ratings",
        "field_type": FieldType.RATINGS,
        "category": CATEGORY_RATINGS,
        "get_property": "ratings",
    },
    # Special
    "status": {
        "api_name": "status",
        "display_name": "Status",
        "field_type": FieldType.STATUS,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "status",
    },
}

MEDIA_TYPE_FIELDS: dict[str, list[str]] = {
    "movie": [
        "title",
        "plot",
        "tagline",
        "sorttitle",
        "originaltitle",
        "year",
        "premiered",
        "runtime",
        "mpaa",
        "top250",
        "genre",
        "studio",
        "director",
        "writer",
        "country",
        "tag",
        "userrating",
        "ratings",
    ],
    "tvshow": [
        "title",
        "plot",
        "sorttitle",
        "originaltitle",
        "premiered",
        "runtime",
        "mpaa",
        "status",
        "genre",
        "studio",
        "tag",
        "userrating",
        "ratings",
    ],
    "episode": [
        "title",
        "plot",
        "originaltitle",
        "firstaired",
        "runtime",
        "director",
        "writer",
        "userrating",
        "ratings",
    ],
    "season": [
        "title",
        "userrating",
    ],
    "musicvideo": [
        "title",
        "plot",
        "year",
        "premiered",
        "runtime",
        "genre",
        "studio",
        "director",
        "tag",
        "userrating",
    ],
}

TVSHOW_STATUS_VALUES = [
    "",
    "returning series",
    "in production",
    "planned",
    "cancelled",
    "ended",
]

CATEGORIES_ORDER = [
    CATEGORY_CORE_TEXT,
    CATEGORY_DATES_NUMBERS,
    CATEGORY_LISTS,
    CATEGORY_RATINGS,
]


def get_fields_for_media_type(media_type: str) -> list[str]:
    """Get list of editable fields for a media type."""
    return MEDIA_TYPE_FIELDS.get(media_type, [])


def get_field_def(field_name: str) -> FieldDef | None:
    """Get field definition by name."""
    return FIELD_DEFINITIONS.get(field_name)


def get_categories_for_media_type(media_type: str) -> list[str]:
    """Get available categories for a media type based on its fields."""
    fields = get_fields_for_media_type(media_type)
    categories = set()
    for field in fields:
        field_def = get_field_def(field)
        if field_def:
            categories.add(field_def["category"])
    return [cat for cat in CATEGORIES_ORDER if cat in categories]


def get_fields_for_category(media_type: str, category: str) -> list[str]:
    """Get fields for a media type filtered by category."""
    fields = get_fields_for_media_type(media_type)
    result = []
    for field in fields:
        field_def = get_field_def(field)
        if field_def and field_def["category"] == category:
            result.append(field)
    return result


def get_properties_for_media_type(media_type: str) -> list[str]:
    """Get JSON-RPC properties to fetch for a media type."""
    fields = get_fields_for_media_type(media_type)
    properties = ["title"]
    for field in fields:
        field_def = get_field_def(field)
        if field_def:
            prop = field_def["get_property"]
            if prop not in properties:
                properties.append(prop)
    return properties
