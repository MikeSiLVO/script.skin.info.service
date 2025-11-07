"""Get media details by DBID for plugin calls.

Queries Kodi library and returns formatted dictionaries for ListItem properties.
"""
from __future__ import annotations

import xbmc
from typing import Optional
from resources.lib.kodi import request, extract_result, KODI_GET_DETAILS_METHODS, KODI_MOVIE_PROPERTIES
from resources.lib.listitem_builder import (
    build_movie_data,
    build_movieset_data,
    build_tvshow_data,
    build_season_data,
    build_episode_data,
    build_musicvideo_data,
    build_artist_data,
    build_album_data,
)


def get_item_data_by_dbid(media_type: str, dbid: str) -> Optional[dict]:
    """
    Query media details by DBID and return as dictionary for ListItem properties.

    Args:
        media_type: Type of media (movie, tvshow, season, episode, musicvideo, artist, album, set)
        dbid: Database ID of the item

    Returns:
        Dictionary of properties to set on a ListItem, or None if query fails
    """

    try:
        if media_type == "movie":
            return _get_movie_data(dbid)
        elif media_type == "set":
            return _get_movieset_data(dbid)
        elif media_type == "tvshow":
            return _get_tvshow_data(dbid)
        elif media_type == "season":
            return _get_season_data(dbid)
        elif media_type == "episode":
            return _get_episode_data(dbid)
        elif media_type == "musicvideo":
            return _get_musicvideo_data(dbid)
        elif media_type == "artist":
            return _get_artist_data(dbid)
        elif media_type == "album":
            return _get_album_data(dbid)
        else:
            xbmc.log(f"SkinInfo: Unknown media type '{media_type}'", xbmc.LOGWARNING)
            return None
    except Exception as e:
        xbmc.log(f"SkinInfo: Error getting data for {media_type} with DBID {dbid}: {str(e)}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return None


def _get_movie_data(movieid: str) -> Optional[dict]:
    """Get movie data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['movie']
    payload = {
        id_key: int(movieid),
        "properties": KODI_MOVIE_PROPERTIES,
    }
    resp = request(
        method,
        payload,
        cache_key=f"movie:{movieid}:details",
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    return build_movie_data(details)


def _get_movieset_data(setid: str) -> Optional[dict]:
    """Get movie set data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['set']
    payload = {
        id_key: int(setid),
        "properties": ["title", "plot", "art"],
        "movies": {
            "properties": [
                "title", "year", "runtime", "genre", "director", "studio",
                "country", "writer", "plot", "plotoutline", "mpaa", "file",
                "streamdetails", "art", "thumbnail",
            ],
            "sort": {"method": "year", "order": "ascending"},
        },
    }

    resp = request(
        method,
        payload,
        cache_key=f"set:{setid}:details",
        ttl_seconds=300,
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    movies = details.get("movies") or []
    if not isinstance(movies, list):
        movies = []
    return build_movieset_data(details, movies)


def _get_tvshow_data(tvshowid: str) -> Optional[dict]:
    """Get TV show data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['tvshow']
    payload = {
        id_key: int(tvshowid),
        "properties": [
            "title", "plot", "year", "premiered", "rating", "votes",
            "genre", "studio", "mpaa", "runtime", "episode", "season",
            "watchedepisodes", "imdbnumber", "originaltitle", "sorttitle",
            "episodeguide", "tag", "art", "userrating", "ratings",
            "cast", "uniqueid", "dateadded", "file", "lastplayed", "playcount",
            "trailer",
        ],
    }
    resp = request(
        method,
        payload,
        cache_key=f"tvshow:{tvshowid}:details",
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    return build_tvshow_data(details)


def _get_season_data(seasonid: str) -> Optional[dict]:
    """Get season data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['season']
    payload = {
        id_key: int(seasonid),
        "properties": [
            "season", "showtitle", "playcount", "episode",
            "tvshowid", "watchedepisodes", "art", "userrating", "title",
        ],
    }
    resp = request(
        method,
        payload,
        cache_key=f"season:{seasonid}:details",
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    return build_season_data(details)


def _get_episode_data(episodeid: str) -> Optional[dict]:
    """Get episode data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['episode']
    payload = {
        id_key: int(episodeid),
        "properties": [
            "title", "plot", "rating", "votes", "ratings", "season", "episode",
            "showtitle", "firstaired", "runtime", "director", "writer", "file",
            "streamdetails", "art", "productioncode", "originaltitle", "playcount",
            "cast", "lastplayed", "resume", "tvshowid", "dateadded", "uniqueid",
            "userrating", "seasonid", "genre", "studio",
        ],
    }
    resp = request(
        method,
        payload,
        cache_key=f"episode:{episodeid}:details",
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    return build_episode_data(details)


def _get_musicvideo_data(musicvideoid: str) -> Optional[dict]:
    """Get music video data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['musicvideo']
    payload = {
        id_key: int(musicvideoid),
        "properties": [
            "title", "artist", "album", "genre", "year", "plot", "runtime",
            "director", "studio", "file", "streamdetails", "art", "premiered",
            "tag", "playcount",
            "lastplayed", "resume", "dateadded", "rating", "userrating", "uniqueid", "track",
        ],
    }
    resp = request(
        method,
        payload,
        cache_key=f"musicvideo:{musicvideoid}:details",
    )
    if not resp:
        return None

    details = extract_result(resp, result_key)
    if not isinstance(details, dict):
        return None

    return build_musicvideo_data(details)


def _get_artist_data(artistid: str) -> Optional[dict]:
    """Get artist data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['artist']
    ext_props = [
        "description", "genre", "art", "thumbnail", "fanart", "musicbrainzartistid",
        "born", "formed", "died", "disbanded", "yearsactive", "instrument",
        "style", "mood", "type", "gender", "disambiguation", "sortname",
        "dateadded", "roles", "songgenres", "sourceid", "datemodified", "datenew",
        "compilationartist", "isalbumartist",
    ]
    resp = request(
        method,
        {id_key: int(artistid), "properties": ext_props},
        cache_key=f"artist:{artistid}:details",
    )
    if not resp:
        resp = request(
            method,
            {id_key: int(artistid), "properties": ["genre", "art", "thumbnail", "fanart", "description"]},
            cache_key=f"artist:{artistid}:details:min",
        )
    if not resp:
        return None

    artist = extract_result(resp, result_key)
    if not isinstance(artist, dict):
        return None

    albums_req = {
        "filter": {"artistid": int(artistid)},
        "properties": [
            "title", "year", "artist", "artistid",
            "genre", "art", "albumlabel", "playcount", "rating",
        ],
        "sort": {"method": "year", "order": "ascending"},
    }
    albums_resp = request(
        "AudioLibrary.GetAlbums",
        albums_req,
        cache_key=f"artist:{artistid}:albums",
    )
    albums = extract_result(albums_resp, "albums") if albums_resp else []
    if not isinstance(albums, list):
        albums = []

    return build_artist_data(artist, albums)


def _get_album_data(albumid: str) -> Optional[dict]:
    """Get album data as dictionary for ListItem."""
    method, id_key, result_key = KODI_GET_DETAILS_METHODS['album']
    ext_props = [
        "title", "art", "year", "artist", "artistid", "genre",
        "style", "mood", "type", "albumlabel", "playcount", "rating", "userrating",
        "musicbrainzalbumid", "musicbrainzreleasegroupid", "lastplayed", "dateadded",
        "description", "votes", "displayartist", "compilation", "releasetype",
        "sortartist", "songgenres", "totaldiscs", "releasedate", "originaldate", "albumduration",
    ]
    resp = request(
        method,
        {id_key: int(albumid), "properties": ext_props},
        cache_key=f"album:{albumid}:details",
    )
    if not resp:
        resp = request(
            method,
            {
                id_key: int(albumid),
                "properties": ["title", "art", "year", "artist", "genre", "albumlabel", "playcount", "rating"],
            },
            cache_key=f"album:{albumid}:details:min",
        )
    if not resp:
        return None

    album = extract_result(resp, result_key)
    if not isinstance(album, dict):
        return None

    songs_req = {
        "filter": {"albumid": int(albumid)},
        "properties": ["title", "duration", "track", "disc", "file", "art", "thumbnail"],
        "sort": {"method": "track", "order": "ascending"},
    }
    songs_resp = request(
        "AudioLibrary.GetSongs",
        songs_req,
        cache_key=f"album:{albumid}:songs",
    )
    songs = extract_result(songs_resp, "songs") if songs_resp else []
    if not isinstance(songs, list):
        songs = []

    return build_album_data(album, songs)
