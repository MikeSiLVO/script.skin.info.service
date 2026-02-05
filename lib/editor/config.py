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
    "artist": {
        "api_name": "artist",
        "display_name": "Artist Name",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "artist",
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
    "sortname": {
        "api_name": "sortname",
        "display_name": "Sort Name",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "sortname",
    },
    "description": {
        "api_name": "description",
        "display_name": "Description",
        "field_type": FieldType.TEXT_LONG,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "description",
    },
    "disambiguation": {
        "api_name": "disambiguation",
        "display_name": "Disambiguation",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "disambiguation",
    },
    "displayartist": {
        "api_name": "displayartist",
        "display_name": "Display Artist",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "displayartist",
    },
    "sortartist": {
        "api_name": "sortartist",
        "display_name": "Sort Artist",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "sortartist",
    },
    "albumlabel": {
        "api_name": "albumlabel",
        "display_name": "Record Label",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "albumlabel",
    },
    "comment": {
        "api_name": "comment",
        "display_name": "Comment",
        "field_type": FieldType.TEXT_LONG,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "comment",
    },
    "songmood": {
        "api_name": "mood",
        "display_name": "Mood",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "mood",
    },
    "disctitle": {
        "api_name": "disctitle",
        "display_name": "Disc Title",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_CORE_TEXT,
        "get_property": "disctitle",
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
    "born": {
        "api_name": "born",
        "display_name": "Born",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "born",
    },
    "formed": {
        "api_name": "formed",
        "display_name": "Formed",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "formed",
    },
    "died": {
        "api_name": "died",
        "display_name": "Died",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "died",
    },
    "disbanded": {
        "api_name": "disbanded",
        "display_name": "Disbanded",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "disbanded",
    },
    "artisttype": {
        "api_name": "type",
        "display_name": "Type",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "type",
    },
    "gender": {
        "api_name": "gender",
        "display_name": "Gender",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "gender",
    },
    "top250": {
        "api_name": "top250",
        "display_name": "Top 250",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "top250",
    },
    "track": {
        "api_name": "track",
        "display_name": "Track Number",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "track",
    },
    "disc": {
        "api_name": "disc",
        "display_name": "Disc Number",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "disc",
    },
    "duration": {
        "api_name": "duration",
        "display_name": "Duration",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "duration",
    },
    "bpm": {
        "api_name": "bpm",
        "display_name": "BPM",
        "field_type": FieldType.INTEGER,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "bpm",
    },
    "releasedate": {
        "api_name": "releasedate",
        "display_name": "Release Date",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "releasedate",
    },
    "originaldate": {
        "api_name": "originaldate",
        "display_name": "Original Date",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "originaldate",
    },
    "albumtype": {
        "api_name": "type",
        "display_name": "Album Type",
        "field_type": FieldType.TEXT,
        "category": CATEGORY_DATES_NUMBERS,
        "get_property": "type",
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
    "style": {
        "api_name": "style",
        "display_name": "Style",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "style",
    },
    "mood": {
        "api_name": "mood",
        "display_name": "Mood",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "mood",
    },
    "instrument": {
        "api_name": "instrument",
        "display_name": "Instrument",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "instrument",
    },
    "yearsactive": {
        "api_name": "yearsactive",
        "display_name": "Years Active",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "yearsactive",
    },
    "theme": {
        "api_name": "theme",
        "display_name": "Theme",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "theme",
    },
    "artistlist": {
        "api_name": "artist",
        "display_name": "Artist",
        "field_type": FieldType.LIST,
        "category": CATEGORY_LISTS,
        "get_property": "artist",
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
    "artist": [
        "artist",
        "sortname",
        "description",
        "disambiguation",
        "born",
        "formed",
        "died",
        "disbanded",
        "artisttype",
        "gender",
        "genre",
        "style",
        "mood",
        "instrument",
        "yearsactive",
    ],
    "album": [
        "title",
        "description",
        "displayartist",
        "sortartist",
        "albumlabel",
        "albumtype",
        "year",
        "releasedate",
        "originaldate",
        "genre",
        "theme",
        "mood",
        "style",
        "artistlist",
        "userrating",
    ],
    "song": [
        "title",
        "displayartist",
        "sortartist",
        "comment",
        "songmood",
        "disctitle",
        "year",
        "track",
        "disc",
        "duration",
        "releasedate",
        "originaldate",
        "bpm",
        "genre",
        "artistlist",
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


ALWAYS_RETURNED_PROPERTIES: dict[str, set[str]] = {
    "artist": {"artist"},
}


def get_properties_for_media_type(media_type: str) -> list[str]:
    """Get JSON-RPC properties to fetch for a media type."""
    fields = get_fields_for_media_type(media_type)
    skip = ALWAYS_RETURNED_PROPERTIES.get(media_type, set())
    properties: list[str] = [] if media_type == "artist" else ["title"]
    for field in fields:
        field_def = get_field_def(field)
        if field_def:
            prop = field_def["get_property"]
            if prop not in properties and prop not in skip:
                properties.append(prop)
    return properties
