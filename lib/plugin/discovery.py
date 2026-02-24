"""Discovery widgets for trending, popular, and upcoming content."""
from __future__ import annotations

import traceback
from typing import Dict, List, Optional, Tuple

import xbmc
import xbmcgui
import xbmcplugin

from lib.kodi.client import log, request

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

_genre_cache: Dict[str, Dict[int, str]] = {}

# Trakt wrapped responses nest the media object under "movie" or "show"
_TRAKT_WRAPPED = {"trakt_trending", "trakt_anticipated", "trakt_watched", "trakt_collected", "trakt_boxoffice"}

WIDGET_REGISTRY: Dict[str, dict] = {
    "tmdb_trending":     {"provider": "tmdb", "types": ("movie", "tv"), "label": "TMDB Trending"},
    "tmdb_popular":      {"provider": "tmdb", "types": ("movie", "tv"), "label": "TMDB Popular"},
    "tmdb_top_rated":    {"provider": "tmdb", "types": ("movie", "tv"), "label": "TMDB Top Rated"},
    "tmdb_now_playing":  {"provider": "tmdb", "types": ("movie",),     "label": "TMDB Now Playing"},
    "tmdb_upcoming":     {"provider": "tmdb", "types": ("movie",),     "label": "TMDB Upcoming"},
    "tmdb_airing_today": {"provider": "tmdb", "types": ("tv",),        "label": "TMDB Airing Today"},
    "tmdb_on_the_air":   {"provider": "tmdb", "types": ("tv",),        "label": "TMDB On The Air"},
    "trakt_trending":         {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Trending"},
    "trakt_popular":          {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Popular"},
    "trakt_anticipated":      {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Anticipated"},
    "trakt_watched":          {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Most Watched"},
    "trakt_collected":        {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Most Collected"},
    "trakt_boxoffice":        {"provider": "trakt", "types": ("movie",),      "label": "Trakt Box Office"},
    "trakt_recommendations":  {"provider": "trakt", "types": ("movie", "tv"), "label": "Trakt Recommendations", "auth": "oauth"},
}


def _get_genre_map(media_type: str) -> Dict[int, str]:
    tmdb_type = "movie" if media_type == "movie" else "tv"
    if tmdb_type in _genre_cache:
        return _genre_cache[tmdb_type]
    from lib.data.api.tmdb import ApiTmdb
    api = ApiTmdb()
    mapping = api.get_genre_list(tmdb_type)
    _genre_cache[tmdb_type] = mapping
    return mapping


def _get_library_lookup(media_type: str) -> Dict[str, Dict[str, object]]:
    lookup: Dict[str, Dict[str, object]] = {}

    if media_type == "movie":
        result = request("VideoLibrary.GetMovies", {
            "properties": ["uniqueid", "file"]
        })
        items = result.get("result", {}).get("movies", []) if result else []
        for item in items:
            tmdb_id = (item.get("uniqueid") or {}).get("tmdb")
            if tmdb_id:
                lookup[str(tmdb_id)] = {
                    "dbid": item["movieid"],
                    "file": item.get("file", "")
                }
    else:
        result = request("VideoLibrary.GetTVShows", {
            "properties": ["uniqueid"]
        })
        items = result.get("result", {}).get("tvshows", []) if result else []
        for item in items:
            tmdb_id = (item.get("uniqueid") or {}).get("tmdb")
            if tmdb_id:
                lookup[str(tmdb_id)] = {
                    "dbid": item["tvshowid"],
                    "file": f"videodb://tvshows/titles/{item['tvshowid']}/"
                }

    return lookup


def _normalize_tmdb_item(item: dict, media_type: str, genre_map: Dict[int, str]) -> dict:
    is_movie = media_type == "movie"
    genre_ids = item.get("genre_ids", [])
    genres = [genre_map[gid] for gid in genre_ids if gid in genre_map]

    date_field = "release_date" if is_movie else "first_air_date"
    premiered = item.get(date_field, "") or ""
    year = 0
    if premiered and len(premiered) >= 4:
        try:
            year = int(premiered[:4])
        except (ValueError, TypeError):
            pass

    poster = ""
    if item.get("poster_path"):
        poster = f"{TMDB_IMAGE_BASE}/w500{item['poster_path']}"
    fanart = ""
    if item.get("backdrop_path"):
        fanart = f"{TMDB_IMAGE_BASE}/original{item['backdrop_path']}"

    return {
        "title": item.get("title") if is_movie else item.get("name", ""),
        "original_title": item.get("original_title") if is_movie else item.get("original_name", ""),
        "year": year,
        "overview": item.get("overview", ""),
        "rating": item.get("vote_average", 0.0),
        "votes": item.get("vote_count", 0),
        "genres": genres,
        "premiered": premiered,
        "poster": poster,
        "fanart": fanart,
        "tmdb_id": item.get("id"),
        "media_type": media_type,
    }


def _extract_trakt_media(item: dict, action: str, media_type: str) -> Optional[dict]:
    if action in _TRAKT_WRAPPED:
        key = "movie" if media_type == "movie" else "show"
        return item.get(key)
    return item


def _normalize_trakt_item(media: dict, media_type: str, images: Dict[str, str]) -> dict:
    is_movie = media_type == "movie"
    ids = media.get("ids", {})

    date_field = "released" if is_movie else "first_aired"
    premiered = (media.get(date_field) or "")[:10]
    year = media.get("year", 0) or 0

    genres_raw = media.get("genres", [])
    genres = [g.replace("-", " ").title() for g in genres_raw]

    poster = ""
    if images.get("poster_path"):
        poster = f"{TMDB_IMAGE_BASE}/w500{images['poster_path']}"
    fanart = ""
    if images.get("backdrop_path"):
        fanart = f"{TMDB_IMAGE_BASE}/original{images['backdrop_path']}"

    return {
        "title": media.get("title", ""),
        "original_title": media.get("title", ""),
        "year": year,
        "overview": media.get("overview", ""),
        "rating": media.get("rating", 0.0),
        "votes": media.get("votes", 0),
        "runtime": media.get("runtime", 0),
        "genres": genres,
        "certification": media.get("certification", ""),
        "premiered": premiered,
        "tagline": media.get("tagline", ""),
        "poster": poster,
        "fanart": fanart,
        "tmdb_id": ids.get("tmdb"),
        "imdb_id": ids.get("imdb", ""),
        "media_type": media_type,
    }


def _fetch_trakt_images(items: List[dict], media_type: str) -> Dict[int, Dict[str, str]]:
    from lib.data.api.tmdb import ApiTmdb
    from lib.data import database as db

    tmdb_type = "movie" if media_type == "movie" else "tv"
    result: Dict[int, Dict[str, str]] = {}
    api: Optional[ApiTmdb] = None

    for item in items:
        ids = item.get("ids", {})
        tmdb_id = ids.get("tmdb")
        if not tmdb_id:
            continue

        cached = db.get_cached_metadata(media_type if media_type == "movie" else "tvshow", str(tmdb_id))
        if cached:
            images: Dict[str, str] = {}
            if cached.get("poster_path"):
                images["poster_path"] = cached["poster_path"]
            if cached.get("backdrop_path"):
                images["backdrop_path"] = cached["backdrop_path"]
            if images:
                result[tmdb_id] = images
                continue

        if api is None:
            api = ApiTmdb()
        fetched = api.get_item_images(tmdb_type, tmdb_id)
        if fetched:
            result[tmdb_id] = fetched

    return result


def _create_listitem(
    normalized: dict,
    library_match: Optional[Dict[str, object]]
) -> Tuple[str, xbmcgui.ListItem, bool]:
    title = normalized.get("title", "")
    listitem = xbmcgui.ListItem(title, offscreen=True)
    video_tag = listitem.getVideoInfoTag()

    is_movie = normalized["media_type"] == "movie"
    video_tag.setMediaType("movie" if is_movie else "tvshow")
    video_tag.setTitle(title)

    if normalized.get("original_title"):
        video_tag.setOriginalTitle(normalized["original_title"])
    if normalized.get("year"):
        video_tag.setYear(normalized["year"])
    if normalized.get("overview"):
        video_tag.setPlot(normalized["overview"])
    if normalized.get("rating"):
        video_tag.setRating(float(normalized["rating"]))
    if normalized.get("votes"):
        video_tag.setVotes(int(normalized["votes"]))
    if normalized.get("genres"):
        video_tag.setGenres(normalized["genres"])
    if normalized.get("premiered"):
        video_tag.setPremiered(normalized["premiered"])
    if normalized.get("certification"):
        video_tag.setMpaa(normalized["certification"])
    if normalized.get("tagline"):
        video_tag.setTagLine(normalized["tagline"])
    if normalized.get("runtime"):
        video_tag.setDuration(int(normalized["runtime"]) * 60)
    if normalized.get("imdb_id"):
        video_tag.setIMDBNumber(normalized["imdb_id"])

    art: Dict[str, str] = {}
    if normalized.get("poster"):
        art["poster"] = normalized["poster"]
    if normalized.get("fanart"):
        art["fanart"] = normalized["fanart"]
    if art:
        listitem.setArt(art)

    if normalized.get("tmdb_id"):
        listitem.setProperty("tmdb_id", str(normalized["tmdb_id"]))

    url = ""
    is_folder = not is_movie

    if library_match:
        dbid = int(library_match["dbid"])  # type: ignore[arg-type]
        video_tag.setDbId(dbid)
        listitem.setProperty("IsInLibrary", "true")
        url = str(library_match.get("file", ""))

    return url, listitem, is_folder


def _fetch_tmdb(action: str, media_type: str, page: int, window: str) -> list:
    from lib.data.api.tmdb import ApiTmdb
    api = ApiTmdb()
    tmdb_type = "movie" if media_type == "movie" else "tv"

    dispatch = {
        "tmdb_trending": lambda: api.get_trending(tmdb_type, window=window, page=page),
        "tmdb_popular": lambda: api.get_popular(tmdb_type, page=page),
        "tmdb_top_rated": lambda: api.get_top_rated(tmdb_type, page=page),
        "tmdb_now_playing": lambda: api.get_now_playing(page=page),
        "tmdb_upcoming": lambda: api.get_upcoming(page=page),
        "tmdb_airing_today": lambda: api.get_airing_today(page=page),
        "tmdb_on_the_air": lambda: api.get_on_the_air(page=page),
    }
    return dispatch[action]()


def _fetch_trakt(action: str, media_type: str, limit: int, page: int, period: str) -> list:
    from lib.data.api.trakt import ApiTrakt
    api = ApiTrakt()
    trakt_type = "movie" if media_type == "movie" else "show"

    dispatch = {
        "trakt_trending": lambda: api.get_trending(trakt_type, limit=limit, page=page),
        "trakt_popular": lambda: api.get_popular(trakt_type, limit=limit, page=page),
        "trakt_anticipated": lambda: api.get_anticipated(trakt_type, limit=limit, page=page),
        "trakt_watched": lambda: api.get_most_watched(trakt_type, period=period, limit=limit, page=page),
        "trakt_collected": lambda: api.get_most_collected(trakt_type, period=period, limit=limit, page=page),
        "trakt_boxoffice": lambda: api.get_box_office(limit=limit),
        "trakt_recommendations": lambda: api.get_recommendations(trakt_type, limit=limit, page=page),
    }
    return dispatch[action]()


def handle_discover(handle: int, action: str, params: dict) -> None:
    try:
        config = WIDGET_REGISTRY.get(action)
        if not config:
            log("Plugin", f"Discover: Unknown widget '{action}'", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        media_type = params.get("type", ["movie"])[0]
        valid_types = config["types"]
        if media_type not in valid_types:
            media_type = valid_types[0]

        source = params.get("source", ["online"])[0]
        limit = int(params.get("limit", ["20"])[0])
        page = int(params.get("page", ["1"])[0])
        window = params.get("window", ["week"])[0]
        period = params.get("period", ["weekly"])[0]

        kodi_media_type = "movie" if media_type == "movie" else "tvshow"
        library_lookup = _get_library_lookup(kodi_media_type)

        normalized_items: List[dict] = []

        if config["provider"] == "tmdb":
            genre_map = _get_genre_map(media_type)
            raw_items = _fetch_tmdb(action, media_type, page, window)
            for raw in raw_items[:limit]:
                normalized_items.append(_normalize_tmdb_item(raw, media_type, genre_map))
        else:
            raw_items = _fetch_trakt(action, media_type, limit, page, period)
            medias = []
            for raw in raw_items:
                media_obj = _extract_trakt_media(raw, action, media_type)
                if media_obj:
                    medias.append(media_obj)

            images_map = _fetch_trakt_images(medias, media_type)
            for media_obj in medias:
                tmdb_id = (media_obj.get("ids") or {}).get("tmdb")
                images = images_map.get(tmdb_id, {}) if tmdb_id else {}
                normalized_items.append(_normalize_trakt_item(media_obj, media_type, images))

        items: List[Tuple[str, xbmcgui.ListItem, bool]] = []
        for normalized in normalized_items:
            tmdb_id_str = str(normalized.get("tmdb_id", ""))
            lib_match = library_lookup.get(tmdb_id_str)

            if source == "library" and not lib_match:
                continue

            url, listitem, is_folder = _create_listitem(normalized, lib_match)
            items.append((url, listitem, is_folder))

        for url, listitem, is_folder in items:
            xbmcplugin.addDirectoryItem(handle, url, listitem, is_folder)

        content = "movies" if media_type == "movie" else "tvshows"
        xbmcplugin.setContent(handle, content)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)

        log("Plugin", f"Discover: {action} ({media_type}) returned {len(items)} items", xbmc.LOGINFO)

    except Exception as e:
        log("Plugin", f"Discover: Error - {e}", xbmc.LOGERROR)
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def _discover_url(action: str, media_type: str) -> str:
    return f"plugin://script.skin.info.service/?action={action}&type={media_type}"


def handle_discover_menu(handle: int, params: dict) -> None:
    items = [
        ("Movies", "plugin://script.skin.info.service/?action=discover_movies_menu", "DefaultMovies.png"),
        ("TV Shows", "plugin://script.skin.info.service/?action=discover_tvshows_menu", "DefaultTVShows.png"),
    ]

    for label, path, icon in items:
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({"icon": icon, "thumb": icon})
        xbmcplugin.addDirectoryItem(handle, path, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def handle_discover_movies_menu(handle: int, params: dict) -> None:
    for action, config in WIDGET_REGISTRY.items():
        if "movie" not in config["types"]:
            continue
        label = config["label"]
        if config.get("auth") == "oauth":
            label += " (OAuth)"
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({"icon": "DefaultMovies.png", "thumb": "DefaultMovies.png"})
        xbmcplugin.addDirectoryItem(handle, _discover_url(action, "movie"), li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def handle_discover_tvshows_menu(handle: int, params: dict) -> None:
    for action, config in WIDGET_REGISTRY.items():
        if "tv" not in config["types"]:
            continue
        label = config["label"]
        if config.get("auth") == "oauth":
            label += " (OAuth)"
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({"icon": "DefaultTVShows.png", "thumb": "DefaultTVShows.png"})
        xbmcplugin.addDirectoryItem(handle, _discover_url(action, "tv"), li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, succeeded=True)
