"""Build dictionaries for ListItem properties from Kodi library data."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from resources.lib.properties import (
    build_movie_data as _build_movie_base,
    build_movieset_data as _build_movieset_base,
    build_tvshow_data as _build_tvshow_base,
    build_season_data as _build_season_base,
    build_episode_data as _build_episode_base,
    build_musicvideo_data as _build_musicvideo_base,
    build_artist_data as _build_artist_base,
    build_album_data as _build_album_base,
    _VIDEO_ART_KEYS,
    _MOVIE_ART_KEYS,
    _SET_ART_KEYS,
    _AUDIO_ART_KEYS,
)


def _build_art_dict(art: Optional[dict], keys: Tuple[str, ...], fallbacks: Optional[dict] = None) -> Dict[str, str]:
    """Build art properties dictionary."""
    art = art or {}
    fallbacks = fallbacks or {}

    art_dict = {}
    for key in keys:
        val = art.get(key) or fallbacks.get(key) or ""
        if val:
            art_dict[f"Art.{key}"] = val

    return art_dict


def build_movie_data(details: dict) -> dict:
    """Build movie data dictionary for ListItem properties."""
    data = _build_movie_base(details)
    data.update(_build_art_dict(details.get("art"), _MOVIE_ART_KEYS))
    return data


def build_movieset_data(set_details: dict, movies: list[dict]) -> dict:
    """Build movie set data dictionary for ListItem properties."""
    data = _build_movieset_base(set_details, movies)
    data.pop("_metadata", None)

    data.update(_build_art_dict(set_details.get("art"), _SET_ART_KEYS))

    for idx, m in enumerate(movies, 1):
        movie_art = _build_art_dict(
            m.get("art"),
            _MOVIE_ART_KEYS,
            fallbacks={"thumbnail": m.get("thumbnail") or ""}
        )
        for art_key, art_val in movie_art.items():
            data[f"Movie.{idx}.{art_key}"] = art_val

    return data


def build_tvshow_data(details: dict) -> dict:
    """Build TV show data dictionary for ListItem properties."""
    data = _build_tvshow_base(details)
    data.update(_build_art_dict(details.get("art"), _VIDEO_ART_KEYS))
    return data


def build_season_data(details: dict) -> dict:
    """Build season data dictionary for ListItem properties."""
    data = _build_season_base(details)
    data.update(_build_art_dict(details.get("art"), _VIDEO_ART_KEYS))
    return data


def build_episode_data(details: dict) -> dict:
    """Build episode data dictionary for ListItem properties."""
    data = _build_episode_base(details)
    data.update(_build_art_dict(details.get("art"), _VIDEO_ART_KEYS))
    return data


def build_musicvideo_data(details: dict) -> dict:
    """Build music video data dictionary for ListItem properties."""
    data = _build_musicvideo_base(details)
    data.update(_build_art_dict(details.get("art"), _VIDEO_ART_KEYS))
    return data


def build_artist_data(artist: dict, albums: list[dict]) -> dict:
    """Build artist data dictionary for ListItem properties."""
    data = _build_artist_base(artist, albums)
    data.pop("_metadata", None)

    data.update(_build_art_dict(
        artist.get("art"),
        ("thumb", "fanart"),
        fallbacks={
            "thumb": artist.get("thumbnail") or "",
            "fanart": artist.get("fanart") or "",
        }
    ))

    for idx, a in enumerate(albums, 1):
        album_art = _build_art_dict(
            a.get("art"),
            ("thumb", "discart"),
            fallbacks={"thumb": a.get("thumbnail") or ""}
        )
        for art_key, art_val in album_art.items():
            data[f"Album.{idx}.{art_key}"] = art_val

    return data


def build_album_data(album: dict, songs: list[dict]) -> dict:
    """Build album data dictionary for ListItem properties."""
    data = _build_album_base(album, songs)
    data.pop("_metadata", None)

    data.update(_build_art_dict(
        album.get("art"),
        _AUDIO_ART_KEYS,
        fallbacks={
            "thumb": album.get("thumbnail") or "",
            "fanart": album.get("fanart") or "",
        }
    ))

    return data
