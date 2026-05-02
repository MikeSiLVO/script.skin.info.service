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

def field(api: str, display: str, ftype: FieldType, category: str) -> FieldDef:
    """Build a FieldDef. `get_property` always mirrors `api`."""
    return {
        "api_name": api,
        "display_name": display,
        "field_type": ftype,
        "category": category,
        "get_property": api,
    }


FIELD_DEFINITIONS: dict[str, FieldDef] = {
    # Core Text
    "title": field("title", "Title", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "artist": field("artist", "Artist Name", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "plot": field("plot", "Plot", FieldType.TEXT_LONG, CATEGORY_CORE_TEXT),
    "tagline": field("tagline", "Tagline", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "sorttitle": field("sorttitle", "Sort Title", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "sortname": field("sortname", "Sort Name", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "description": field("description", "Description", FieldType.TEXT_LONG, CATEGORY_CORE_TEXT),
    "disambiguation": field("disambiguation", "Disambiguation", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "displayartist": field("displayartist", "Display Artist", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "sortartist": field("sortartist", "Sort Artist", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "albumlabel": field("albumlabel", "Record Label", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "comment": field("comment", "Comment", FieldType.TEXT_LONG, CATEGORY_CORE_TEXT),
    "songmood": field("mood", "Mood", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "disctitle": field("disctitle", "Disc Title", FieldType.TEXT, CATEGORY_CORE_TEXT),
    "originaltitle": field("originaltitle", "Original Title", FieldType.TEXT, CATEGORY_CORE_TEXT),
    # Dates Numbers
    "year": field("year", "Year", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "premiered": field("premiered", "Premiered", FieldType.DATE, CATEGORY_DATES_NUMBERS),
    "firstaired": field("firstaired", "First Aired", FieldType.DATE, CATEGORY_DATES_NUMBERS),
    "runtime": field("runtime", "Runtime", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "mpaa": field("mpaa", "MPAA Rating", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "born": field("born", "Born", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "formed": field("formed", "Formed", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "died": field("died", "Died", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "disbanded": field("disbanded", "Disbanded", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "artisttype": field("type", "Type", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "gender": field("gender", "Gender", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "top250": field("top250", "Top 250", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "track": field("track", "Track Number", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "disc": field("disc", "Disc Number", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "duration": field("duration", "Duration", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "bpm": field("bpm", "BPM", FieldType.INTEGER, CATEGORY_DATES_NUMBERS),
    "releasedate": field("releasedate", "Release Date", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "originaldate": field("originaldate", "Original Date", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    "albumtype": field("type", "Album Type", FieldType.TEXT, CATEGORY_DATES_NUMBERS),
    # Lists
    "genre": field("genre", "Genre", FieldType.LIST, CATEGORY_LISTS),
    "studio": field("studio", "Studio", FieldType.LIST, CATEGORY_LISTS),
    "director": field("director", "Director", FieldType.LIST, CATEGORY_LISTS),
    "writer": field("writer", "Writer", FieldType.LIST, CATEGORY_LISTS),
    "country": field("country", "Country", FieldType.LIST, CATEGORY_LISTS),
    "tag": field("tag", "Tags", FieldType.LIST, CATEGORY_LISTS),
    "style": field("style", "Style", FieldType.LIST, CATEGORY_LISTS),
    "mood": field("mood", "Mood", FieldType.LIST, CATEGORY_LISTS),
    "instrument": field("instrument", "Instrument", FieldType.LIST, CATEGORY_LISTS),
    "yearsactive": field("yearsactive", "Years Active", FieldType.LIST, CATEGORY_LISTS),
    "theme": field("theme", "Theme", FieldType.LIST, CATEGORY_LISTS),
    "artistlist": field("artist", "Artist", FieldType.LIST, CATEGORY_LISTS),
    # Ratings
    "userrating": field("userrating", "User Rating", FieldType.USERRATING, CATEGORY_RATINGS),
    "ratings": field("ratings", "External Ratings", FieldType.RATINGS, CATEGORY_RATINGS),
    # Dates Numbers
    "status": field("status", "Status", FieldType.STATUS, CATEGORY_DATES_NUMBERS),
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


_DEFAULT_PROPERTIES: dict[str, list[str]] = {
    "artist": ["artist"],  # artist endpoint requires "artist" rather than "title"
}


def get_properties_for_media_type(media_type: str) -> list[str]:
    """Get JSON-RPC properties to fetch for a media type."""
    properties = list(_DEFAULT_PROPERTIES.get(media_type, ["title"]))
    for field_name in get_fields_for_media_type(media_type):
        field_def = get_field_def(field_name)
        if field_def:
            prop = field_def["get_property"]
            if prop not in properties:
                properties.append(prop)
    return properties


# Validate at module load that every name in MEDIA_TYPE_FIELDS exists in FIELD_DEFINITIONS.
for _mt, _fields in MEDIA_TYPE_FIELDS.items():
    for _f in _fields:
        if _f not in FIELD_DEFINITIONS:
            raise ValueError(
                f"MEDIA_TYPE_FIELDS[{_mt!r}] references unknown field {_f!r}"
            )
