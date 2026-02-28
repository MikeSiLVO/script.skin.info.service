"""Get media details by DBID for plugin calls.

Queries Kodi library and returns formatted dictionaries for ListItem properties.
"""
from __future__ import annotations

import xbmc
from typing import List, Optional, Tuple
from lib.kodi.client import request, extract_result, get_item_details, KODI_MOVIE_PROPERTIES, log
from lib.plugin.listitems import (
    build_movie_data,
    build_movieset_data,
    build_tvshow_data,
    build_season_data,
    build_episode_data,
    build_musicvideo_data,
    build_artist_data,
    build_album_data,
)


def get_item_data_by_dbid(media_type: str, dbid: int) -> Optional[dict]:
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
            log("Plugin", f"Unknown media type '{media_type}'", xbmc.LOGWARNING)
            return None
    except Exception as e:
        import traceback
        log("Plugin", f"Error getting data for {media_type} with DBID {dbid}: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return None


def _get_movie_data(movieid: int) -> Optional[dict]:
    """Get movie data as dictionary for ListItem."""
    details = get_item_details(
        'movie',
        movieid,
        KODI_MOVIE_PROPERTIES,
        cache_key=f"movie:{movieid}:details",
    )
    if not isinstance(details, dict):
        return None

    return build_movie_data(details)


def _get_movieset_data(setid: int) -> Optional[dict]:
    """Get movie set data as dictionary for ListItem."""
    details = get_item_details(
        'set',
        setid,
        ["title", "plot", "art"],
        cache_key=f"set:{setid}:details",
        ttl_seconds=300,
        movies={
            "properties": [
                "title", "year", "runtime", "genre", "director", "studio",
                "country", "writer", "plot", "plotoutline", "mpaa", "file",
                "streamdetails", "art", "thumbnail",
            ],
            "sort": {"method": "year", "order": "ascending"},
        },
    )
    if not isinstance(details, dict):
        return None

    movies = details.get("movies") or []
    if not isinstance(movies, list):
        movies = []
    return build_movieset_data(details, movies)


def _get_tvshow_data(tvshowid: int) -> Optional[dict]:
    """Get TV show data as dictionary for ListItem."""
    details = get_item_details(
        'tvshow',
        tvshowid,
        [
            "title", "plot", "year", "premiered", "rating", "votes",
            "genre", "studio", "mpaa", "runtime", "episode", "season",
            "watchedepisodes", "imdbnumber", "originaltitle", "sorttitle",
            "episodeguide", "tag", "art", "userrating", "ratings",
            "cast", "uniqueid", "dateadded", "file", "lastplayed", "playcount",
            "trailer",
        ],
        cache_key=f"tvshow:{tvshowid}:details",
    )
    if not isinstance(details, dict):
        return None

    return build_tvshow_data(details)


def _get_season_data(seasonid: int) -> Optional[dict]:
    """Get season data as dictionary for ListItem."""
    details = get_item_details(
        'season',
        seasonid,
        [
            "season", "showtitle", "playcount", "episode",
            "tvshowid", "watchedepisodes", "art", "userrating", "title",
        ],
        cache_key=f"season:{seasonid}:details",
    )
    if not isinstance(details, dict):
        return None

    return build_season_data(details)


def _get_episode_data(episodeid: int) -> Optional[dict]:
    """Get episode data as dictionary for ListItem."""
    details = get_item_details(
        'episode',
        episodeid,
        [
            "title", "plot", "rating", "votes", "ratings", "season", "episode",
            "showtitle", "firstaired", "runtime", "director", "writer", "file",
            "streamdetails", "art", "productioncode", "originaltitle", "playcount",
            "cast", "lastplayed", "resume", "tvshowid", "dateadded", "uniqueid",
            "userrating", "seasonid", "genre", "studio",
        ],
        cache_key=f"episode:{episodeid}:details",
    )
    if not isinstance(details, dict):
        return None

    return build_episode_data(details)


def _get_musicvideo_data(musicvideoid: int) -> Optional[dict]:
    """Get music video data as dictionary for ListItem."""
    details = get_item_details(
        'musicvideo',
        musicvideoid,
        [
            "title", "artist", "album", "genre", "year", "plot", "runtime",
            "director", "studio", "file", "streamdetails", "art", "premiered",
            "tag", "playcount",
            "lastplayed", "resume", "dateadded", "rating", "userrating", "uniqueid", "track",
        ],
        cache_key=f"musicvideo:{musicvideoid}:details",
    )
    if not isinstance(details, dict):
        return None

    data = build_musicvideo_data(details)
    data.update(get_musicvideo_library_art(details))
    return data


_artist_art_cache: dict = {}
_artist_albums_cache: dict = {}
_MAX_CACHE_ENTRIES = 200


def clear_musicvideo_library_art_cache() -> None:
    """Clear cached artist art lookups (call on library updates)."""
    _artist_art_cache.clear()
    _artist_albums_cache.clear()


def get_musicvideo_library_art(details: dict) -> dict:
    """Query AudioLibrary for artist art and album thumb matching a music video.

    Args:
        details: dict with 'artist' (list of names) and 'album' (string) keys

    Returns:
        Dict with keys like 'Artist.Fanart', 'Artist.Thumb', 'Album.Thumb'
    """
    artist_art, artist_id = get_musicvideo_artist_art(details)
    props = dict(artist_art)
    album_thumb = get_musicvideo_album_art(details, artist_id)
    if album_thumb:
        props["Album.Thumb"] = album_thumb
    return props


def get_musicvideo_artist_art(details: dict) -> tuple:
    """Query AudioLibrary for artist art matching a music video.

    Returns:
        (artist_props dict, artist_id or None)
    """
    from lib.kodi.client import decode_image_url
    from lib.service.properties import _join

    artist_name = _join(details.get("artist"))
    if not artist_name:
        return {}, None

    artist_key = artist_name.lower()

    if artist_key in _artist_art_cache:
        artist_props, artist_id = _artist_art_cache[artist_key]
        return dict(artist_props), artist_id

    result = request("AudioLibrary.GetArtists", {
        "filter": {"field": "artist", "operator": "is", "value": artist_name},
        "properties": ["art"],
        "limits": {"end": 1},
    })

    artists_list = (result or {}).get("result", {}).get("artists")
    if not artists_list:
        if len(_artist_art_cache) >= _MAX_CACHE_ENTRIES:
            _artist_art_cache.clear()
        _artist_art_cache[artist_key] = ({}, None)
        return {}, None

    artist = artists_list[0]
    artist_art_raw = artist.get("art", {})
    artist_id = artist.get("artistid")

    artist_props: dict = {}
    for art_type in ("fanart", "thumb", "clearlogo", "banner"):
        value = artist_art_raw.get(art_type, "")
        if value:
            key = art_type[0].upper() + art_type[1:]
            artist_props[f"Artist.{key}"] = decode_image_url(value)

    if len(_artist_art_cache) >= _MAX_CACHE_ENTRIES:
        _artist_art_cache.clear()
    _artist_art_cache[artist_key] = (artist_props, artist_id)
    return dict(artist_props), artist_id


def get_musicvideo_album_art(details: dict, artist_id: object) -> str:
    """Query AudioLibrary for album thumb matching a music video.

    Returns:
        Album thumb URL or empty string.
    """
    from lib.kodi.client import decode_image_url
    from lib.service.properties import _join

    artist_name = _join(details.get("artist"))
    album_name = details.get("album") or ""
    if not album_name or not artist_id or not artist_name:
        return ""

    artist_key = artist_name.lower()
    album_cache_key = (artist_key, album_name.lower())

    if album_cache_key in _artist_albums_cache:
        return _artist_albums_cache[album_cache_key]

    album_thumb = ""
    albums_result = request("AudioLibrary.GetAlbums", {
        "filter": {"artistid": artist_id},
        "properties": ["title", "art"],
    })
    if albums_result:
        album_list = albums_result.get("result", {}).get("albums")
        if isinstance(album_list, list):
            album_lower = album_name.lower()
            for album in album_list:
                if album.get("title", "").lower() == album_lower:
                    thumb = album.get("art", {}).get("thumb", "")
                    if thumb:
                        album_thumb = decode_image_url(thumb)
                    break
    if len(_artist_albums_cache) >= _MAX_CACHE_ENTRIES:
        _artist_albums_cache.clear()
    _artist_albums_cache[album_cache_key] = album_thumb
    return album_thumb


def get_musicvideo_node_data(artist_name: str, album_name: str = "") -> dict:
    """Get music library art for musicvideo artist/album navigation nodes."""
    if not artist_name:
        return {}
    details: dict = {"artist": [artist_name], "album": album_name}
    return get_musicvideo_library_art(details)


def fetch_artist_details(artistid: int) -> Optional[Tuple[dict, List[dict]]]:
    """Fetch artist and their albums from library. Returns (artist, albums) or None."""
    ext_props = [
        "description", "genre", "art", "thumbnail", "fanart", "musicbrainzartistid",
        "born", "formed", "died", "disbanded", "yearsactive", "instrument",
        "style", "mood", "type", "gender", "disambiguation", "sortname",
        "dateadded", "roles", "songgenres", "sourceid", "datemodified", "datenew",
        "compilationartist", "isalbumartist",
    ]
    artist = get_item_details(
        'artist',
        artistid,
        ext_props,
        cache_key=f"artist:{artistid}:details",
    )
    if not artist:
        artist = get_item_details(
            'artist',
            artistid,
            ["genre", "art", "thumbnail", "fanart", "description"],
            cache_key=f"artist:{artistid}:details:min",
        )
    if not isinstance(artist, dict):
        return None

    albums_req = {
        "filter": {"artistid": artistid},
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

    return artist, albums


def fetch_album_details(albumid: int) -> Optional[Tuple[dict, List[dict]]]:
    """Fetch album and its songs from library. Returns (album, songs) or None."""
    ext_props = [
        "title", "art", "year", "artist", "artistid", "genre",
        "style", "mood", "type", "albumlabel", "playcount", "rating", "userrating",
        "musicbrainzalbumid", "musicbrainzreleasegroupid", "lastplayed", "dateadded",
        "description", "votes", "displayartist", "compilation", "releasetype",
        "sortartist", "songgenres", "totaldiscs", "releasedate", "originaldate", "albumduration",
    ]
    album = get_item_details(
        'album',
        albumid,
        ext_props,
        cache_key=f"album:{albumid}:details",
    )
    if not album:
        album = get_item_details(
            'album',
            albumid,
            ["title", "art", "year", "artist", "genre", "albumlabel", "playcount", "rating"],
            cache_key=f"album:{albumid}:details:min",
        )
    if not isinstance(album, dict):
        return None

    songs_req = {
        "filter": {"albumid": albumid},
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

    return album, songs


def _get_artist_data(artistid: int) -> Optional[dict]:
    """Get artist data as dictionary for ListItem."""
    result = fetch_artist_details(artistid)
    if not result:
        return None
    return build_artist_data(*result)


def _get_album_data(albumid: int) -> Optional[dict]:
    """Get album data as dictionary for ListItem."""
    result = fetch_album_details(albumid)
    if not result:
        return None
    return build_album_data(*result)
