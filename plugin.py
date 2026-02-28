"""Plugin entry point for on-demand DBID queries.

Returns list items for use in containers.
"""
from __future__ import annotations

import sys
from datetime import datetime
from urllib.parse import parse_qs
import traceback
import xbmc
import xbmcgui
import xbmcplugin

from lib.kodi.client import log
from lib.kodi.formatters import RATING_SOURCE_NORMALIZE
from lib.plugin.dbid import get_item_data_by_dbid

_MAX_CAST_ITEMS = 2000


def _split_multivalue(value: str, separator: str = " / ") -> list[str]:
    """Split multi-value string by separator, or return single-item list."""
    return value.split(separator) if separator in value else [value]


def _set_stream_details(video_tag: xbmc.InfoTagVideo, streamdetails: dict) -> None:
    """Set stream details on VideoInfoTag using native Kodi APIs.

    Args:
        video_tag: The VideoInfoTag to add streams to
        streamdetails: Raw streamdetails dict from JSON-RPC containing video/audio/subtitle arrays
    """
    video_streams = streamdetails.get("video") or []
    audio_streams = streamdetails.get("audio") or []
    subtitle_streams = streamdetails.get("subtitle") or []

    for v in video_streams:
        video_stream = xbmc.VideoStreamDetail(
            width=int(v.get("width") or 0),
            height=int(v.get("height") or 0),
            aspect=float(v.get("aspect") or 0.0),
            duration=int(v.get("duration") or 0),
            codec=v.get("codec") or "",
            stereomode="",
            language="",
            hdrtype=v.get("hdrtype") or "",
        )
        video_tag.addVideoStream(video_stream)

    for a in audio_streams:
        audio_stream = xbmc.AudioStreamDetail(
            channels=int(a.get("channels") or -1),
            codec=a.get("codec") or "",
            language=a.get("language") or "",
        )
        video_tag.addAudioStream(audio_stream)

    for s in subtitle_streams:
        subtitle_stream = xbmc.SubtitleStreamDetail(
            language=s.get("language") or "",
        )
        video_tag.addSubtitleStream(subtitle_stream)


def _deduplicate_cast(items: list) -> list:
    """
    Deduplicate cast from multiple items, maintaining order of first appearance.

    Args:
        items: List of items with 'cast' arrays (items may include 'movieid' or other ID fields)

    Returns:
        Deduplicated list of cast dictionaries with source item ID added
    """
    seen = set()
    unique_cast = []

    for item in items:
        cast = item.get('cast', [])
        item_id = item.get('movieid') or item.get('episodeid')

        for actor in cast:
            name = actor.get('name')
            if name and name not in seen:
                seen.add(name)
                actor_copy = actor.copy()
                if item_id:
                    actor_copy['_source_id'] = item_id
                unique_cast.append(actor_copy)

    if len(unique_cast) > _MAX_CAST_ITEMS:
        unique_cast = unique_cast[:_MAX_CAST_ITEMS]

    return unique_cast


def _create_cast_listitems(handle: int, cast_list: list) -> int:
    """
    Create and add cast ListItems with lazy-loading properties.

    Args:
        handle: Plugin handle
        cast_list: List of deduplicated cast dictionaries

    Returns:
        Number of items added
    """
    items_added = 0
    for actor in cast_list:
        name = actor.get('name', '')
        if not name:
            continue

        role = actor.get('role') or actor.get('character', '')
        if not role and 'roles' in actor and actor['roles']:
            role = actor['roles'][0].get('character', '')

        item = xbmcgui.ListItem(label=name, label2=role, offscreen=True)
        thumb = actor.get('thumbnail') or actor.get('profile_path') or ''

        if thumb.startswith('/'):
            thumb = f"https://image.tmdb.org/t/p/w185{thumb}"

        if thumb:
            item.setArt({'icon': thumb, 'thumb': thumb})
        else:
            item.setArt({'icon': 'DefaultActor.png', 'thumb': 'DefaultActor.png'})

        source_id = actor.get('_source_id')
        if source_id:
            item.setProperty('source_id', str(source_id))

        person_id = actor.get('id')
        if person_id:
            item.setProperty('person_id', str(person_id))

        xbmcplugin.addDirectoryItem(handle, '', item, False)
        items_added += 1

    if items_added > 0:
        xbmcplugin.setContent(handle, 'actors')

    return items_added


def handle_dbid_query(handle: int, params: dict) -> None:
    """
    Handle DBID query action - returns a single ListItem with all properties set.

    Args:
        handle: Plugin handle
        params: Query parameters dictionary containing:
            - dbid: Database ID (required)
            - dbtype: Media type (required)
            - reload: Cache buster (optional, ignored)
    """
    dbid = params.get("dbid", [""])[0]
    media_type = params.get("dbtype", [""])[0]

    if not dbid:
        log("Plugin", "Missing required parameter 'dbid'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    try:
        dbid = int(dbid)
        if dbid <= 0:
            raise ValueError("DBID must be positive")
    except (ValueError, TypeError) as e:
        log("Plugin", f"Invalid DBID '{dbid}': {str(e)}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if not media_type:
        log("Plugin", "Missing required parameter 'dbtype'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Prevent injection by normalizing input
    media_type = media_type.lower().strip()

    if media_type in ("musicvideo_artist", "musicvideo_album"):
        _handle_musicvideo_node(handle, params, media_type)
        return

    valid_types = ("movie", "tvshow", "season", "episode", "musicvideo", "artist", "album", "set")

    if media_type not in valid_types:
        log("Plugin", f"Invalid media type '{media_type}', expected one of: {', '.join(valid_types)}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    log("Plugin", f"Querying {media_type} with DBID {dbid}", xbmc.LOGDEBUG)

    item_data = get_item_data_by_dbid(media_type, dbid)

    if not item_data:
        log("Plugin", f"No data returned for {media_type} {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    list_item = xbmcgui.ListItem(label=item_data.get("Title", ""), offscreen=True)

    is_music = media_type in ("artist", "album", "musicvideo")
    video_tag = list_item.getVideoInfoTag() if not is_music else None

    art_dict = {}
    properties_dict = {"DBID": str(dbid)}

    for key, value in item_data.items():
        if not value:
            continue

        if key.startswith("_"):
            continue

        if key.startswith("Art."):
            art_type = key.replace("Art.", "").lower()
            art_dict[art_type] = value
        else:
            properties_dict[key] = str(value)

    if video_tag:
        video_tag.setMediaType(media_type)
        video_tag.setDbId(dbid)

        if "_ratings" in item_data and isinstance(item_data["_ratings"], dict):
            ratings_dict = item_data["_ratings"]
            if ratings_dict:
                ratings_for_kodi = {}
                default_rating = None

                for rating_type, rating_info in ratings_dict.items():
                    if isinstance(rating_info, dict):
                        rating_val = rating_info.get("rating")
                        votes_val = rating_info.get("votes", 0)
                        max_val = rating_info.get("max", 10)
                        is_default = rating_info.get("default", False)

                        if rating_val is not None:
                            try:
                                ratings_for_kodi[rating_type] = (float(rating_val), int(votes_val))
                                if is_default:
                                    default_rating = rating_type

                                pct = max(0, min(100, round((float(rating_val) / float(max_val)) * 100)))

                                # Normalize RT source names to canonical tomatoes/popcorn
                                output_type = RATING_SOURCE_NORMALIZE.get(rating_type, rating_type)

                                properties_dict[f"Rating.{output_type}.Percent"] = str(pct)

                            except (ValueError, TypeError, ZeroDivisionError):
                                pass

                if ratings_for_kodi:
                    video_tag.setRatings(ratings_for_kodi, default_rating or "")

        if "Title" in item_data:
            video_tag.setTitle(item_data["Title"])
        if "OriginalTitle" in item_data:
            video_tag.setOriginalTitle(item_data["OriginalTitle"])
        if "Year" in item_data:
            try:
                video_tag.setYear(int(item_data["Year"]))
            except (ValueError, TypeError):
                pass
        if "Rating" in item_data:
            try:
                video_tag.setRating(float(item_data["Rating"]))
            except (ValueError, TypeError):
                pass
        if "Votes" in item_data:
            try:
                votes_str = item_data["Votes"].replace(",", "")
                video_tag.setVotes(int(votes_str))
            except (ValueError, TypeError, AttributeError):
                pass
        if "UserRating" in item_data:
            try:
                video_tag.setUserRating(int(item_data["UserRating"]))
            except (ValueError, TypeError):
                pass
        if "Top250" in item_data:
            try:
                video_tag.setTop250(int(item_data["Top250"]))
            except (ValueError, TypeError):
                pass
        if "Playcount" in item_data:
            try:
                video_tag.setPlaycount(int(item_data["Playcount"]))
            except (ValueError, TypeError):
                pass
        if "Plot" in item_data:
            video_tag.setPlot(item_data["Plot"])
        if "PlotOutline" in item_data:
            video_tag.setPlotOutline(item_data["PlotOutline"])
        if "Tagline" in item_data:
            video_tag.setTagLine(item_data["Tagline"])
        if "Runtime" in item_data:
            try:
                video_tag.setDuration(int(item_data["Runtime"]) * 60)
            except (ValueError, TypeError):
                pass
        if "MPAA" in item_data:
            video_tag.setMpaa(item_data["MPAA"])
        if "Premiered" in item_data:
            video_tag.setPremiered(item_data["Premiered"])
        if "Genre" in item_data:
            video_tag.setGenres(_split_multivalue(item_data["Genre"]))
        if "Director" in item_data:
            video_tag.setDirectors(_split_multivalue(item_data["Director"]))
        if "Writer" in item_data:
            video_tag.setWriters(_split_multivalue(item_data["Writer"]))
        if "Studio" in item_data:
            video_tag.setStudios(_split_multivalue(item_data["Studio"]))
        if "Country" in item_data:
            video_tag.setCountries(_split_multivalue(item_data["Country"]))
        if "Trailer" in item_data:
            video_tag.setTrailer(item_data["Trailer"])
        if "LastPlayed" in item_data:
            video_tag.setLastPlayed(item_data["LastPlayed"])
        if "DateAdded" in item_data:
            video_tag.setDateAdded(item_data["DateAdded"])
        if "Tag" in item_data:
            video_tag.setTags(_split_multivalue(item_data["Tag"]))
        if "IMDBNumber" in item_data:
            video_tag.setIMDBNumber(item_data["IMDBNumber"])
        if "ProductionCode" in item_data:
            video_tag.setProductionCode(item_data["ProductionCode"])
        if "FirstAired" in item_data:
            video_tag.setFirstAired(item_data["FirstAired"])
        if "Episode" in item_data:
            try:
                video_tag.setEpisode(int(item_data["Episode"]))
            except (ValueError, TypeError):
                pass
        if "Season" in item_data:
            try:
                video_tag.setSeason(int(item_data["Season"]))
            except (ValueError, TypeError):
                pass
        if "ShowTitle" in item_data:
            video_tag.setTvShowTitle(item_data["ShowTitle"])

        if "_streamdetails" in item_data:
            _set_stream_details(video_tag, item_data["_streamdetails"])

    if art_dict:
        list_item.setArt(art_dict)

    if properties_dict:
        for prop_key, prop_value in properties_dict.items():
            list_item.setProperty(prop_key, prop_value)

    xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def handle_online(handle: int, params: dict) -> None:
    """
    Handle online data fetch - returns a single ListItem with online API properties.

    Fetches data from TMDb, OMDb, MDBList, and Trakt APIs.

    Supports two modes:
    1. Library mode: Provide dbid + type to look up IDs from Kodi library
    2. Direct mode: Provide tmdb_id or imdb_id directly (for non-library content)

    Args:
        handle: Plugin handle
        params: Query parameters dictionary containing:
            - type: Media type - movie or tvshow (required)
            - dbid: Database ID (for library items)
            - tmdb_id: TMDb ID (for non-library items)
            - imdb_id: IMDB ID (for non-library items)
            - reload: Cache buster (optional, ignored)
    """
    from lib.service.online import fetch_all_online_data
    from lib.kodi.client import get_item_details
    from lib.data.api.tmdb import ApiTmdb

    media_type = params.get("dbtype", [""])[0]
    dbid = params.get("dbid", [""])[0]
    tmdb_id = params.get("tmdb_id", [""])[0]
    imdb_id = params.get("imdb_id", [""])[0]

    if not media_type:
        log("Plugin", "Online: Missing required parameter 'dbtype'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    media_type = media_type.lower().strip()

    if media_type == "musicvideo":
        _handle_online_musicvideo(handle, params)
        return

    valid_types = ("movie", "tvshow", "episode")

    if media_type not in valid_types:
        log("Plugin", f"Online: Invalid media type '{media_type}', expected one of: {', '.join(valid_types)}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    is_episode = media_type == "episode"
    tvdb_id = ""

    if tmdb_id or imdb_id:
        log("Plugin", f"Online: Direct mode - TMDB: {tmdb_id}, IMDB: {imdb_id}", xbmc.LOGDEBUG)
    elif dbid:
        try:
            dbid_int = int(dbid)
            if dbid_int <= 0:
                raise ValueError("DBID must be positive")
        except (ValueError, TypeError) as e:
            log("Plugin", f"Online: Invalid DBID '{dbid}': {str(e)}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        log("Plugin", f"Online: Library mode - {media_type} DBID {dbid}", xbmc.LOGDEBUG)

        if is_episode:
            # Get parent tvshow ID from episode, then get show's uniqueids
            episode_details = get_item_details("episode", dbid_int, ["tvshowid"])
            if not episode_details or not episode_details.get("tvshowid"):
                log("Plugin", f"Online: Could not get parent show for episode {dbid}", xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return
            tvshow_dbid = episode_details["tvshowid"]
            details = get_item_details("tvshow", tvshow_dbid, ["uniqueid"])
        else:
            details = get_item_details(media_type, dbid_int, ["uniqueid"])

        if not details:
            log("Plugin", f"Online: Could not get details for {media_type} {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        uniqueid_dict = details.get("uniqueid") or {}
        imdb_id = uniqueid_dict.get("imdb") or ""
        tmdb_id = uniqueid_dict.get("tmdb") or ""
        tvdb_id = uniqueid_dict.get("tvdb") or ""
    else:
        log("Plugin", "Online: Missing required parameter - provide dbid, tmdb_id, or imdb_id", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Episodes use parent show's data for online lookups
    if is_episode:
        media_type = "tvshow"

    if not imdb_id and not tmdb_id and not tvdb_id:
        log("Plugin", "Online: No valid IDs available", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if not tmdb_id:
        tmdb_api = ApiTmdb()
        if imdb_id:
            result = tmdb_api.find_by_external_id(imdb_id, "imdb_id", media_type)
            if result and result.get("id"):
                tmdb_id = str(result["id"])
        elif tvdb_id and media_type == "tvshow":
            result = tmdb_api.find_by_external_id(tvdb_id, "tvdb_id", media_type)
            if result and result.get("id"):
                tmdb_id = str(result["id"])

    log("Plugin", f"Online: Resolved IDs - IMDB: {imdb_id}, TMDB: {tmdb_id}", xbmc.LOGDEBUG)

    is_library_item = bool(dbid)
    online_data = fetch_all_online_data(
        media_type, imdb_id, tmdb_id, is_library_item=is_library_item
    )

    if not online_data:
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return

    list_item = xbmcgui.ListItem(offscreen=True)

    if dbid:
        list_item.setProperty("dbid", str(dbid))

    for prop_key, prop_value in online_data.items():
        if prop_value:
            list_item.setProperty(prop_key, str(prop_value))

    xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _handle_online_musicvideo(handle: int, params: dict) -> None:
    """Fetch online music metadata for a music video and return as ListItem properties."""
    from lib.kodi.client import get_item_details
    from lib.service.music import (
        fetch_artist_online_data,
        fetch_track_online_data,
        fetch_album_online_data,
        extract_track_properties,
        extract_album_properties,
    )
    from lib.service.properties import _join

    dbid = params.get("dbid", [""])[0]
    if not dbid:
        log("Plugin", "Online MusicVideo: Missing required parameter 'dbid'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    try:
        dbid_int = int(dbid)
        if dbid_int <= 0:
            raise ValueError("DBID must be positive")
    except (ValueError, TypeError) as e:
        log("Plugin", f"Online MusicVideo: Invalid DBID '{dbid}': {e}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    details = get_item_details("musicvideo", dbid_int, ["artist", "title", "album"])
    if not details:
        log("Plugin", f"Online MusicVideo: No details for DBID {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    artist_name = _join(details.get("artist"))
    title = details.get("title") or None
    album = details.get("album") or None

    props: dict[str, str] = {}

    if artist_name:
        result = fetch_artist_online_data(artist_name, album=album, track=title)
        if result:
            if result.bio:
                props["Artist.Bio"] = result.bio
            props["Artist.FanArt.Count"] = str(len(result.fanart_urls))
            if result.fanart_urls:
                props["Artist.FanArt"] = result.fanart_urls[0]
            for art_type in ("thumb", "clearlogo", "banner"):
                url = result.artist_art.get(art_type, "")
                if url:
                    key = art_type[0].upper() + art_type[1:]
                    props[f"Artist.{key}"] = url

    if artist_name and title:
        fetch_track_online_data(artist_name, title)
        track_props = extract_track_properties(artist_name, title)
        if track_props:
            for k, v in track_props.items():
                props[f"Track.{k}"] = v

    if artist_name and album:
        fetch_album_online_data(artist_name, album)
        album_props = extract_album_properties(artist_name, album)
        if album_props:
            for k, v in album_props.items():
                props[f"Album.{k}"] = v

    if not props:
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return

    list_item = xbmcgui.ListItem(offscreen=True)
    list_item.setProperty("dbid", str(dbid))

    for prop_key, prop_value in props.items():
        if prop_value:
            list_item.setProperty(prop_key, str(prop_value))

    xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _handle_musicvideo_node(handle: int, params: dict, media_type: str) -> None:
    """Handle musicvideo artist/album node queries using name-based library lookup."""
    from lib.plugin.dbid import get_musicvideo_node_data

    artist_name = params.get("artist", [""])[0]
    album_name = params.get("album", [""])[0]

    if media_type == "musicvideo_artist" and not artist_name:
        log("Plugin", "MusicVideo node: Missing 'artist' parameter", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if media_type == "musicvideo_album" and not album_name:
        log("Plugin", "MusicVideo node: Missing 'album' parameter", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    data = get_musicvideo_node_data(artist_name, album_name)

    label = artist_name if media_type == "musicvideo_artist" else album_name
    list_item = xbmcgui.ListItem(label=label, offscreen=True)

    for prop_key, prop_value in data.items():
        if prop_value:
            list_item.setProperty(prop_key, str(prop_value))

    xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _handle_online_cast(handle: int, dbtype: str, dbid: int) -> int:
    """
    Fetch cast from TMDB for online mode.

    Args:
        handle: Plugin handle
        dbtype: Media type
        dbid: Kodi database ID

    Returns:
        Number of cast items added
    """
    from lib.kodi.client import get_item_details
    from lib.data.api.tmdb import ApiTmdb
    from lib.data.api.person import resolve_tmdb_id

    tmdb_id = resolve_tmdb_id(dbtype, dbid)
    if not tmdb_id:
        log("Plugin", f"Online Cast: Could not resolve TMDB ID for {dbtype} {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return 0

    api = ApiTmdb()
    cast = []

    if dbtype == 'movie':
        data = api.get_movie_details_extended(tmdb_id)
        if data and 'credits' in data:
            cast = data['credits'].get('cast', [])

    elif dbtype == 'tvshow':
        data = api.get_tv_details_extended(tmdb_id)
        if data and 'credits' in data:
            cast = data['credits'].get('cast', [])

    elif dbtype == 'season':
        details = get_item_details(dbtype, dbid, ['season'])
        if not details:
            log("Plugin", f"Online Cast: Failed to get season details for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_num = details.get('season')
        if season_num is None:
            log("Plugin", f"Online Cast: No season number for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_data = api.get_season_details(tmdb_id, season_num)
        if season_data:
            main_cast = season_data.get('aggregate_credits', {}).get('cast', [])
            all_guests = {}
            for episode in season_data.get('episodes', []):
                for guest in episode.get('guest_stars', []):
                    guest_id = guest.get('id')
                    if guest_id and guest_id not in all_guests:
                        all_guests[guest_id] = guest
            cast = main_cast + list(all_guests.values())

    elif dbtype == 'episode':
        details = get_item_details(dbtype, dbid, ['season', 'episode'])
        if not details:
            log("Plugin", f"Online Cast: Failed to get episode details for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_num = details.get('season')
        episode_num = details.get('episode')

        episode_data = api.get_episode_details_extended(tmdb_id, season_num, episode_num)
        if episode_data and 'credits' in episode_data:
            episode_cast = episode_data['credits'].get('cast', [])
            episode_guests = episode_data['credits'].get('guest_stars', [])
            cast = episode_cast + episode_guests

    if not cast:
        log("Plugin", f"Online Cast: No cast found for {dbtype} {dbid}", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return 0

    log("Plugin", f"Online Cast: Found {len(cast)} cast members for {dbtype} {dbid}", xbmc.LOGDEBUG)
    return _create_cast_listitems(handle, cast)


def handle_get_cast(handle: int, params: dict) -> None:
    """
    Get cast for movies, movie sets, TV shows, seasons, or episodes.

    Args:
        handle: Plugin handle
        params: Query parameters dictionary containing:
            - dbid: Database ID (required)
            - dbtype: Media type - "movie", "set", "tvshow", "season", or "episode" (required)
            - online: Fetch from TMDB (true) or use Kodi database (false, default) (optional)
            - reload: Cache buster (optional, ignored)
    """
    try:
        dbid = params.get('dbid', [''])[0]
        dbtype = params.get('dbtype', [''])[0]
        online = params.get('online', ['false'])[0].lower() == 'true'

        if not dbid or not dbtype:
            log("Plugin", "Library Cast: Missing required parameters", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        if dbtype not in ('movie', 'set', 'tvshow', 'season', 'episode'):
            log("Plugin", f'Library Cast: Invalid dbtype "{dbtype}"', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        from lib.kodi.client import get_item_details

        items_added = 0

        if online:
            log("Plugin", f"Library Cast: Using online TMDB data for {dbtype} {dbid}", xbmc.LOGDEBUG)
            items_added = _handle_online_cast(handle, dbtype, int(dbid))
        elif dbtype in ('movie', 'episode', 'tvshow'):
            if dbtype == 'movie':
                details = get_item_details('movie', int(dbid), ['cast'])
            elif dbtype == 'episode':
                details = get_item_details('episode', int(dbid), ['cast'])
            else:
                details = get_item_details('tvshow', int(dbid), ['cast'])

            if not details:
                log("Plugin", f"Library Cast: {dbtype.capitalize()} {dbid} not found", xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return

            cast = details.get('cast', [])
            if not cast:
                log("Plugin", f"Library Cast: No cast found for {dbtype} {dbid}", xbmc.LOGINFO)
                xbmcplugin.endOfDirectory(handle, succeeded=True)
                return

            log("Plugin", f"Library Cast: Processing {dbtype} {dbid} - Found {len(cast)} cast members", xbmc.LOGDEBUG)
            items_added = _create_cast_listitems(handle, cast)

        elif dbtype in ('set', 'season'):
            if dbtype == 'set':
                details = get_item_details(
                    'set',
                    int(dbid),
                    ['title'],
                    movies={
                        'properties': ['cast'],
                        'sort': {'method': 'year', 'order': 'ascending'},
                    }
                )
                items = details.get('movies', []) if details else []

            else:
                from lib.kodi.client import request

                season_details = get_item_details('season', int(dbid), ['season', 'tvshowid'])
                if not season_details:
                    log("Plugin", f"Library Cast: Season {dbid} not found", xbmc.LOGWARNING)
                    xbmcplugin.endOfDirectory(handle, succeeded=False)
                    return

                tvshow_id = season_details.get('tvshowid')
                season_num = season_details.get('season')

                result = request(
                    'VideoLibrary.GetEpisodes',
                    {
                        'tvshowid': tvshow_id,
                        'season': season_num,
                        'properties': ['cast'],
                        'sort': {'method': 'episode', 'order': 'ascending'}
                    }
                )
                items = result.get('result', {}).get('episodes', []) if result else []

            if not items:
                log("Plugin", f"Library Cast: No items found for {dbtype} {dbid}", xbmc.LOGINFO)
                xbmcplugin.endOfDirectory(handle, succeeded=True)
                return

            unique_cast = _deduplicate_cast(items)

            log("Plugin", f"Library Cast: Processing {dbtype} {dbid} - Found {len(items)} items, deduplicated to {len(unique_cast)} unique cast", xbmc.LOGDEBUG)

            items_added = _create_cast_listitems(handle, unique_cast)

        log("Plugin", f"Library Cast: Created {items_added} ListItems", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)

    except Exception as e:
        log("Plugin", f"Library Cast: Error - {e}", xbmc.LOGERROR)
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def handle_get_cast_player(handle: int, params: dict) -> None:
    """
    Get cast for currently playing library item.

    Args:
        handle: Plugin handle
        params: Query parameters dictionary containing:
            - scope: Optional scope for episodes - "episode" (default) or "show"
    """
    try:
        content = xbmc.getInfoLabel('VideoPlayer.Content()')
        dbid = xbmc.getInfoLabel('VideoPlayer.DBID')
        tvshow_dbid = xbmc.getInfoLabel('VideoPlayer.TvShowDBID')

        if not content or not dbid:
            log("Plugin", "Player Cast: No video playing or missing DBID", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        content_type = content.rstrip('s')

        valid_types = ('movie', 'episode', 'musicvideo')
        if content_type not in valid_types:
            log("Plugin",
                f'Player Cast: Unsupported content type "{content_type}"',
                xbmc.LOGWARNING
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        from lib.kodi.client import get_item_details, request

        aggregate = params.get('aggregate', ['false'])[0].lower() == 'true'

        if content_type == 'episode' and aggregate and tvshow_dbid:
            result = request(
                'VideoLibrary.GetEpisodes',
                {
                    'tvshowid': int(tvshow_dbid),
                    'properties': ['cast'],
                    'sort': {'method': 'episode', 'order': 'ascending'}
                }
            )
            items = result.get('result', {}).get('episodes', []) if result else []
            log("Plugin", f"Player Cast: Aggregating cast from entire show (DBID: {tvshow_dbid})", xbmc.LOGDEBUG)

        else:
            details = get_item_details(content_type, int(dbid), ['cast'])
            if not details:
                log("Plugin", f"Player Cast: No details for {content_type} {dbid}", xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return

            items = [details]
            log("Plugin", f"Player Cast: Getting cast for {content_type} {dbid}", xbmc.LOGDEBUG)

        if not items:
            log("Plugin", "Player Cast: No items found", xbmc.LOGINFO)
            xbmcplugin.endOfDirectory(handle, succeeded=True)
            return

        unique_cast = _deduplicate_cast(items)
        log("Plugin", f"Player Cast: Found {len(items)} items, deduplicated to {len(unique_cast)} unique cast", xbmc.LOGDEBUG)

        items_added = _create_cast_listitems(handle, unique_cast)

        log("Plugin", f"Player Cast: Created {items_added} ListItems", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)

    except Exception as e:
        log("Plugin", f"Player Cast: Error - {e}", xbmc.LOGERROR)
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def handle_path_stats(handle: int, params: dict) -> None:
    """
    Calculate and return path statistics as ListItem properties.

    Returns a single invisible ListItem with statistics as properties.
    Designed for use with reload parameter for auto-refresh on library updates.

    Args:
        handle: Plugin handle
        params: Query parameters dictionary containing:
            - path: Path to analyze (required)
            - reload: Cache buster (optional, ignored)

    Properties Set:
        SkinInfo.PathStats.Count - Total items
        SkinInfo.PathStats.Watched - Items with playcount > 0
        SkinInfo.PathStats.Unwatched - Items with playcount == 0 and no resume
        SkinInfo.PathStats.InProgress - Items with playcount == 0 and resume.position > 0
        SkinInfo.PathStats.TVShowCount - For TV show paths: number of shows
        SkinInfo.PathStats.Episodes - For TV show paths: total episodes
        SkinInfo.PathStats.WatchedEpisodes - For TV show paths: watched episodes
        SkinInfo.PathStats.UnWatchedEpisodes - For TV show paths: unwatched episodes
    """
    from lib.plugin.pathstats import get_path_statistics

    path = params.get('path', [''])[0]

    if not path:
        log("Plugin", "Path Statistics: Missing required parameter 'path'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    log("Plugin", f"Path Statistics: Calculating statistics for path: {path}", xbmc.LOGDEBUG)

    stats = get_path_statistics(path)

    # Define properties to set on both Window and ListItem
    properties = [
        ('Count', stats['count']),
        ('Watched', stats['watched']),
        ('Unwatched', stats['unwatched']),
        ('InProgress', stats['in_progress']),
        ('TVShowCount', stats['tvshow_count']),
        ('Episodes', stats['episodes']),
        ('WatchedEpisodes', stats['watched_episodes']),
        ('UnWatchedEpisodes', stats['unwatched_episodes']),
    ]

    # Set Window properties for global access
    window = xbmcgui.Window(10000)
    for prop_name, value in properties:
        window.setProperty(f'SkinInfo.PathStats.{prop_name}', str(value))

    # Also set ListItem properties for container access
    item = xbmcgui.ListItem(offscreen=True)
    for prop_name, value in properties:
        item.setProperty(f'SkinInfo.PathStats.{prop_name}', str(value))

    xbmcplugin.addDirectoryItem(handle, '', item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def handle_wrap(handle: int, params: dict) -> None:
    """
    Wrap XSP-filtered library paths in plugin:// for refresh support.

    Intended for filtered paths and playlists that need dynamic refresh:
    - XSP inline filters: videodb://movies/titles/?xsp={...}
    - XSP playlist files: special://profile/playlists/video/playlist.xsp
    - Smart playlists with InfoLabel filters

    NOT intended for:
    - Full library browsing (videodb://movies/titles/)
    - Regular directory browsing

    Args:
        handle: Plugin handle
        params: URL parameters containing 'path'
    """
    import json
    from lib.kodi.settings import KodiSettings

    path = params.get('path', [''])[0]

    if not path:
        log("Plugin", "Path Wrapper: No path provided", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    enable_debug = KodiSettings.debug_enabled()
    if enable_debug:
        log("Plugin", f"Path Wrapper: Wrapping path: {path}", xbmc.LOGDEBUG)

    json_request = json.dumps({
        'jsonrpc': '2.0',
        'method': 'Files.GetDirectory',
        'params': {
            'directory': path,
            'media': 'video',
            'properties': [
                'title', 'artist', 'genre', 'year', 'rating', 'album', 'track',
                'playcount', 'director', 'trailer', 'tagline', 'plot', 'plotoutline',
                'originaltitle', 'lastplayed', 'writer', 'studio', 'mpaa', 'country',
                'imdbnumber', 'premiered', 'productioncode', 'runtime', 'set', 'setid',
                'top250', 'votes', 'firstaired', 'season', 'episode', 'showtitle',
                'tvshowid', 'watchedepisodes', 'tag', 'art', 'userrating', 'resume',
                'dateadded'
            ]
        },
        'id': 1
    })

    response = xbmc.executeJSONRPC(json_request)
    result = json.loads(response)

    if 'error' in result:
        log("Plugin", f'Path Wrapper: Error - {result["error"]}', xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    files = result.get('result', {}).get('files', [])

    if enable_debug:
        log("Plugin", f"Path Wrapper: Found {len(files)} items", xbmc.LOGDEBUG)

    items = []

    for file_item in files:
        file_path = file_item.get('file', '')
        filetype = file_item.get('filetype', '')

        if filetype == 'directory' and file_path.endswith(('.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm')):
            filetype = 'file'

        li = xbmcgui.ListItem(file_item.get('label', ''), offscreen=True)
        li.setPath(file_path)

        video_tag = li.getVideoInfoTag()

        if 'title' in file_item:
            video_tag.setTitle(file_item['title'])
        if 'year' in file_item:
            year = file_item['year']
            video_tag.setYear(int(year) if isinstance(year, (int, str)) and str(year).isdigit() else 0)
        if 'plot' in file_item:
            video_tag.setPlot(file_item['plot'])
        if 'plotoutline' in file_item:
            video_tag.setPlotOutline(file_item['plotoutline'])
        if 'rating' in file_item:
            video_tag.setRating(float(file_item['rating']) if file_item['rating'] else 0.0)
        if 'votes' in file_item:
            votes = file_item['votes']
            video_tag.setVotes(int(votes) if isinstance(votes, (int, str)) and str(votes).isdigit() else 0)
        if 'playcount' in file_item:
            playcount = file_item['playcount']
            video_tag.setPlaycount(int(playcount) if isinstance(playcount, (int, str)) and str(playcount).isdigit() else 0)
        if 'lastplayed' in file_item:
            video_tag.setLastPlayed(file_item['lastplayed'])
        if 'dateadded' in file_item:
            video_tag.setDateAdded(file_item['dateadded'])
        if 'userrating' in file_item:
            userrating = file_item['userrating']
            video_tag.setUserRating(int(userrating) if isinstance(userrating, (int, str)) and str(userrating).isdigit() else 0)
        if 'runtime' in file_item:
            runtime = file_item['runtime']
            video_tag.setDuration(int(runtime) if isinstance(runtime, (int, str)) and str(runtime).isdigit() else 0)
        if 'director' in file_item:
            video_tag.setDirectors(file_item['director'] if isinstance(file_item['director'], list) else [file_item['director']])
        if 'writer' in file_item:
            video_tag.setWriters(file_item['writer'] if isinstance(file_item['writer'], list) else [file_item['writer']])
        if 'genre' in file_item:
            video_tag.setGenres(file_item['genre'] if isinstance(file_item['genre'], list) else [file_item['genre']])
        if 'studio' in file_item:
            video_tag.setStudios(file_item['studio'] if isinstance(file_item['studio'], list) else [file_item['studio']])
        if 'country' in file_item:
            video_tag.setCountries(file_item['country'] if isinstance(file_item['country'], list) else [file_item['country']])
        if 'mpaa' in file_item:
            video_tag.setMpaa(file_item['mpaa'])
        if 'tagline' in file_item:
            video_tag.setTagLine(file_item['tagline'])
        if 'originaltitle' in file_item:
            video_tag.setOriginalTitle(file_item['originaltitle'])
        if 'premiered' in file_item:
            video_tag.setPremiered(file_item['premiered'])
        if 'trailer' in file_item:
            video_tag.setTrailer(file_item['trailer'])
        if 'imdbnumber' in file_item:
            video_tag.setIMDBNumber(file_item['imdbnumber'])
        if 'top250' in file_item:
            top250 = file_item['top250']
            video_tag.setTop250(int(top250) if isinstance(top250, (int, str)) and str(top250).isdigit() else 0)
        if 'set' in file_item:
            video_tag.setSet(file_item['set'])
        if 'setid' in file_item:
            setid = file_item['setid']
            video_tag.setSetId(int(setid) if isinstance(setid, (int, str)) and str(setid).isdigit() else 0)
        if 'tag' in file_item:
            video_tag.setTags(file_item['tag'] if isinstance(file_item['tag'], list) else [file_item['tag']])
        if 'season' in file_item:
            season = file_item['season']
            video_tag.setSeason(int(season) if isinstance(season, (int, str)) and str(season).isdigit() else 0)
        if 'episode' in file_item:
            episode = file_item['episode']
            video_tag.setEpisode(int(episode) if isinstance(episode, (int, str)) and str(episode).isdigit() else 0)
        if 'showtitle' in file_item:
            video_tag.setTvShowTitle(file_item['showtitle'])
        if 'firstaired' in file_item:
            video_tag.setFirstAired(file_item['firstaired'])
        if 'productioncode' in file_item:
            video_tag.setProductionCode(file_item['productioncode'])
        if 'artist' in file_item:
            video_tag.setArtists(file_item['artist'] if isinstance(file_item['artist'], list) else [file_item['artist']])
        if 'album' in file_item:
            video_tag.setAlbum(file_item['album'])
        if 'track' in file_item:
            track = file_item['track']
            video_tag.setTrackNumber(int(track) if isinstance(track, (int, str)) and str(track).isdigit() else 0)

        if 'type' in file_item:
            video_tag.setMediaType(file_item['type'])

        if 'resume' in file_item:
            resume = file_item['resume']
            if isinstance(resume, dict):
                position = resume.get('position', 0)
                total = resume.get('total', 0)
                if position > 0 and total > 0:
                    video_tag.setResumePoint(position, total)

        if 'art' in file_item:
            li.setArt(file_item['art'])

        is_folder = filetype == 'directory'
        items.append((file_path, li, is_folder))

    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True)

    if enable_debug:
        log("Plugin", f"Path Wrapper: Successfully wrapped {len(items)} items", xbmc.LOGDEBUG)


def handle_person_info(handle: int, params: dict) -> None:
    """
    Handle person info requests.

    URL params:
        person_id: TMDB person ID (required)
        info_type: details/images/filmography/crew (required)

        Filmography/Crew filters:
        sort: popularity/date_desc/date_asc/rating/title (default: popularity)
        dbtype: both/movie/tvshow (default: both)
        min_votes: Minimum vote count (default: 0)
        exclude_unreleased: true/false (default: false)
        limit: Max items to return (default: unlimited)
    """
    from lib.data.api import person as person_api

    try:
        person_id = params.get('person_id', [''])[0]
        info_type = params.get('info_type', [''])[0]

        if not person_id or not info_type:
            log("Plugin", "Person Info: Missing required parameters", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        try:
            person_id = int(person_id)
        except (ValueError, TypeError):
            log("Plugin", f"Person Info: Invalid person_id '{person_id}'", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        person_data = person_api.get_person_data(person_id)
        if not person_data:
            log("Plugin", f"Person Info: No data for person_id={person_id}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        if info_type == 'details':
            _handle_person_details(handle, person_data)
        elif info_type == 'images':
            _handle_person_images(handle, person_data)
        elif info_type == 'filmography':
            _handle_person_filmography(handle, person_data, params)
        elif info_type == 'crew':
            _handle_person_crew(handle, person_data, params)
        else:
            log("Plugin", f"Person Info: Unknown info_type '{info_type}'", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)

    except Exception as e:
        log("Plugin", f"Person Info: Error - {e}", xbmc.LOGERROR)
        import traceback
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def _handle_person_details(handle: int, person_data: dict) -> None:
    """Return single ListItem with all person details."""
    name = person_data.get('name', 'Unknown')
    item = xbmcgui.ListItem(name, offscreen=True)

    item.setProperty('Name', name)

    if person_data.get('biography'):
        item.setProperty('Biography', person_data['biography'])

    birthday = person_data.get('birthday')
    deathday = person_data.get('deathday')

    if birthday:
        item.setProperty('Birthday', birthday)

        try:
            birth_date = datetime.strptime(birthday, '%Y-%m-%d')

            if deathday:
                end_date = datetime.strptime(deathday, '%Y-%m-%d')
            else:
                end_date = datetime.now()

            age = end_date.year - birth_date.year
            if (end_date.month, end_date.day) < (birth_date.month, birth_date.day):
                age -= 1

            item.setProperty('Age', str(age))

            date_format = xbmc.getRegion('dateshort')
            item.setProperty('BirthdayFormatted', birth_date.strftime(date_format))
        except (ValueError, TypeError):
            pass

    if deathday:
        item.setProperty('Deathday', deathday)

        try:
            death_date = datetime.strptime(deathday, '%Y-%m-%d')
            date_format = xbmc.getRegion('dateshort')
            item.setProperty('DeathdayFormatted', death_date.strftime(date_format))
        except (ValueError, TypeError):
            pass

    if person_data.get('place_of_birth'):
        item.setProperty('Birthplace', person_data['place_of_birth'])

    if person_data.get('known_for_department'):
        item.setProperty('KnownFor', person_data['known_for_department'])

    person_id = person_data.get('id')
    if person_id:
        item.setProperty('person_id', str(person_id))

    if person_data.get('imdb_id'):
        item.setProperty('imdb_id', person_data['imdb_id'])

    gender = person_data.get('gender')
    if gender:
        gender_text = {1: 'Female', 2: 'Male'}.get(gender)
        if gender_text:
            item.setProperty('Gender', gender_text)

    external_ids = person_data.get('external_ids', {})
    for key in ['instagram_id', 'twitter_id', 'facebook_id', 'tiktok_id', 'youtube_id']:
        value = external_ids.get(key)
        if value:
            prop_name = key.replace('_id', '').title()
            item.setProperty(prop_name, value)

    profile_path = person_data.get('profile_path')
    if profile_path:
        image_url = f"https://image.tmdb.org/t/p/original{profile_path}"
        item.setArt({'thumb': image_url, 'icon': image_url})

    combined_credits = person_data.get('combined_credits', {})
    cast = combined_credits.get('cast', [])

    if cast:
        movies = [c for c in cast if c.get('media_type') == 'movie']
        tv_shows = [c for c in cast if c.get('media_type') == 'tv']

        movies.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        tv_shows.sort(key=lambda x: x.get('popularity', 0), reverse=True)

        seen_movie_ids = set()
        unique_movies = []
        for m in movies:
            movie_id = m.get('id')
            if movie_id and movie_id not in seen_movie_ids:
                seen_movie_ids.add(movie_id)
                unique_movies.append(m)

        seen_tv_ids = set()
        unique_tv = []
        for t in tv_shows:
            tv_id = t.get('id')
            if tv_id and tv_id not in seen_tv_ids:
                seen_tv_ids.add(tv_id)
                unique_tv.append(t)

        top_movies = ' / '.join([m.get('title', '') for m in unique_movies[:5] if m.get('title')])
        top_tv = ' / '.join([t.get('name', '') for t in unique_tv[:5] if t.get('name')])

        if top_movies:
            item.setProperty('TopMovies', top_movies)
        if top_tv:
            item.setProperty('TopTVShows', top_tv)

    xbmcplugin.addDirectoryItem(handle, '', item, False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _handle_person_images(handle: int, person_data: dict) -> None:
    """Return multiple ListItems for profile images."""
    images = person_data.get('images', {}).get('profiles', [])

    if not images:
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return

    images.sort(key=lambda x: x.get('vote_average', 0), reverse=True)

    for i, image in enumerate(images):
        file_path = image.get('file_path')
        if not file_path:
            continue

        item = xbmcgui.ListItem(f"Profile Image {i+1}", offscreen=True)

        image_url = f"https://image.tmdb.org/t/p/original{file_path}"
        item.setArt({'thumb': image_url, 'icon': image_url})

        item.setProperty('Width', str(image.get('width', '')))
        item.setProperty('Height', str(image.get('height', '')))

        vote_average = image.get('vote_average')
        if vote_average:
            item.setProperty('Rating', f"{vote_average:.1f}")

        vote_count = image.get('vote_count')
        if vote_count:
            item.setProperty('Votes', str(vote_count))

        item.setProperty('AspectRatio', str(image.get('aspect_ratio', '')))

        xbmcplugin.addDirectoryItem(handle, '', item, False)

    xbmcplugin.setContent(handle, 'images')
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)


def _handle_person_filmography(handle: int, person_data: dict, params: dict) -> None:
    """Return filmography as movie/TV show ListItems."""
    credits = person_data.get('combined_credits', {}).get('cast', [])

    credits = _filter_credits(credits, params)
    credits = _sort_credits(credits, params)

    limit_str = params.get('limit', [''])[0]
    if limit_str:
        try:
            limit = int(limit_str)
            credits = credits[:limit]
        except (ValueError, TypeError):
            pass

    for credit in credits:
        item = _create_credit_listitem(credit)
        xbmcplugin.addDirectoryItem(handle, '', item, False)

    xbmcplugin.setContent(handle, 'movies')
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)


def _handle_person_crew(handle: int, person_data: dict, params: dict) -> None:
    """Return crew credits as ListItems."""
    credits = person_data.get('combined_credits', {}).get('crew', [])

    credits = _filter_credits(credits, params)
    credits = _sort_credits(credits, params)

    limit_str = params.get('limit', [''])[0]
    if limit_str:
        try:
            limit = int(limit_str)
            credits = credits[:limit]
        except (ValueError, TypeError):
            pass

    for credit in credits:
        item = _create_credit_listitem(credit)

        if credit.get('job'):
            item.setProperty('Job', credit['job'])
        if credit.get('department'):
            item.setProperty('Department', credit['department'])

        xbmcplugin.addDirectoryItem(handle, '', item, False)

    xbmcplugin.setContent(handle, 'movies')
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)


def _filter_credits(credits: list, params: dict) -> list:
    """Apply filters to credits list."""
    from datetime import datetime

    dbtype = params.get('dbtype', ['both'])[0]
    if dbtype == 'tvshow':
        dbtype = 'tv'
    if dbtype in ('movie', 'tv'):
        credits = [c for c in credits if c.get('media_type') == dbtype]

    min_votes_str = params.get('min_votes', ['0'])[0]
    try:
        min_votes = int(min_votes_str)
        if min_votes > 0:
            credits = [c for c in credits if c.get('vote_count', 0) >= min_votes]
    except (ValueError, TypeError):
        pass

    exclude_unreleased = params.get('exclude_unreleased', ['false'])[0].lower() == 'true'
    if exclude_unreleased:
        today = datetime.now().strftime('%Y-%m-%d')
        credits = [
            c for c in credits
            if (c.get('release_date') or c.get('first_air_date', '0000')) <= today
        ]

    return credits


def _sort_credits(credits: list, params: dict) -> list:
    """Sort credits list."""
    sort_method = params.get('sort', ['popularity'])[0]

    if sort_method == 'date_desc':
        credits.sort(key=lambda c: c.get('release_date') or c.get('first_air_date', '0000'), reverse=True)
    elif sort_method == 'date_asc':
        credits.sort(key=lambda c: c.get('release_date') or c.get('first_air_date', '9999'))
    elif sort_method == 'rating':
        credits.sort(key=lambda c: c.get('vote_average', 0), reverse=True)
    elif sort_method == 'title':
        credits.sort(key=lambda c: (c.get('title') or c.get('name', '')).lower())

    return credits


def handle_person_library(handle: int, params: dict) -> None:
    """
    Get library items (movies or tvshows) featuring a specific actor.

    Args:
        handle: Plugin handle
        params: Query parameters containing:
            - info_type: "movies" or "tvshows" (required)
            - person_name: Actor name (required)
    """
    try:
        info_type = params.get('info_type', [''])[0]
        person_name = params.get('person_name', [''])[0]

        if not info_type or not person_name:
            log("Plugin", "Person Library: Missing required parameters", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        if info_type not in ('movies', 'tvshows'):
            log("Plugin", f"Person Library: Invalid info_type '{info_type}'", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        from lib.kodi.client import request

        if info_type == 'movies':
            result = request('VideoLibrary.GetMovies', {
                'filter': {
                    'field': 'actor',
                    'operator': 'is',
                    'value': person_name
                },
                'properties': ['title', 'year', 'rating', 'playcount', 'art', 'cast'],
                'sort': {'method': 'sorttitle', 'order': 'ascending'}
            })
            items = result.get('result', {}).get('movies', []) if result else []
        else:
            result = request('VideoLibrary.GetTVShows', {
                'filter': {
                    'field': 'actor',
                    'operator': 'is',
                    'value': person_name
                },
                'properties': ['title', 'year', 'rating', 'playcount', 'art', 'cast'],
                'sort': {'method': 'sorttitle', 'order': 'ascending'}
            })
            items = result.get('result', {}).get('tvshows', []) if result else []

        for item in items:
            title = item.get('title', 'Unknown')
            year = item.get('year', '')

            label = f"{title} ({year})" if year else title
            listitem = xbmcgui.ListItem(label, offscreen=True)

            listitem.setProperty('Title', title)
            if year:
                listitem.setProperty('Year', str(year))

            rating = item.get('rating')
            if rating:
                listitem.setProperty('Rating', str(rating))

            playcount = item.get('playcount')
            if playcount:
                listitem.setProperty('Playcount', str(playcount))

            cast = item.get('cast', [])
            for actor in cast:
                if actor.get('name') == person_name:
                    role = actor.get('role', '')
                    if role:
                        listitem.setProperty('Role', role)
                    break

            art = item.get('art', {})
            if art:
                listitem.setArt(art)

            xbmcplugin.addDirectoryItem(handle, '', listitem, False)

        xbmcplugin.setContent(handle, 'movies' if info_type == 'movies' else 'tvshows')
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)

    except Exception as e:
        log("Plugin", f"Person Library: Error - {e}", xbmc.LOGERROR)
        import traceback
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def _create_credit_listitem(credit: dict) -> xbmcgui.ListItem:
    """Create ListItem from credit entry."""
    title = credit.get('title') or credit.get('name', 'Unknown')
    item = xbmcgui.ListItem(title, offscreen=True)

    video_tag = item.getVideoInfoTag()

    media_type = credit.get('media_type', 'movie')
    video_tag.setMediaType(media_type)

    video_tag.setTitle(title)

    if credit.get('overview'):
        video_tag.setPlot(credit['overview'])

    release_date = credit.get('release_date') or credit.get('first_air_date')
    if release_date:
        try:
            year = int(release_date[:4])
            video_tag.setYear(year)
        except (ValueError, TypeError, IndexError):
            pass

    if credit.get('vote_average'):
        video_tag.setRating(float(credit['vote_average']))

    art = {}
    if credit.get('poster_path'):
        art['poster'] = f"https://image.tmdb.org/t/p/w500{credit['poster_path']}"
    if credit.get('backdrop_path'):
        art['fanart'] = f"https://image.tmdb.org/t/p/w780{credit['backdrop_path']}"
    if art:
        item.setArt(art)

    character = credit.get('character', '')
    item.setProperty('Role', character)
    item.setProperty('ReleaseDate', release_date or '')
    item.setProperty('MediaType', media_type)

    return item


def handle_crew_list(handle: int, params: dict) -> None:
    """
    Get crew members (directors/writers/creators) for a movie or TV show.

    URL params:
        crew_type: director/writer/creator (required)
        dbtype: movie/tvshow (required)
        dbid: Kodi database ID (required)
    """
    from lib.data.api import person as person_api
    from lib.data.api.person import resolve_tmdb_id

    crew_type = params.get('crew_type', [''])[0]
    dbtype = params.get('dbtype', [''])[0]
    dbid_str = params.get('dbid', [''])[0]

    if not crew_type or not dbtype or not dbid_str:
        log("Plugin", "Crew List: Missing required parameters", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if crew_type not in ('director', 'writer', 'creator'):
        log("Plugin", f"Crew List: Invalid crew_type '{crew_type}'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if crew_type == 'creator' and dbtype != 'tvshow':
        log("Plugin", "Crew List: creator only valid for tvshow", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    try:
        dbid = int(dbid_str)
    except (ValueError, TypeError):
        log("Plugin", f"Crew List: Invalid dbid '{dbid_str}'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    tmdb_id = resolve_tmdb_id(dbtype, dbid)
    if not tmdb_id:
        log("Plugin", f"Crew List: Could not resolve TMDB ID for {dbtype} {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    crew_list = person_api.get_crew_from_tmdb(crew_type, tmdb_id, dbtype)

    if not crew_list:
        log("Plugin", f"Crew List: No {crew_type}s found for {dbtype} {dbid}", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return

    for member in crew_list:
        name = member.get('name', 'Unknown')
        item = xbmcgui.ListItem(label=name, offscreen=True)

        if member.get('job'):
            item.setLabel2(member['job'])

        profile_path = member.get('profile_path')
        if profile_path:
            image_url = f"https://image.tmdb.org/t/p/w185{profile_path}"
            item.setArt({'thumb': image_url, 'icon': image_url})
        else:
            item.setArt({'thumb': 'DefaultActor.png', 'icon': 'DefaultActor.png'})

        person_id = member.get('id')
        if person_id:
            item.setProperty('person_id', str(person_id))

        item.setProperty('Job', member.get('job', ''))

        xbmcplugin.addDirectoryItem(handle, '', item, False)

    xbmcplugin.setContent(handle, 'actors')
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)

    log("Plugin", f"Crew List: Returned {len(crew_list)} {crew_type}s for {dbtype} {dbid}", xbmc.LOGDEBUG)


def handle_tmdb_details(handle: int, params: dict) -> None:
    """
    Handle TMDB details requests.

    URL params:
        type: media type (movie/tv/person)
        tmdb_id: TMDB ID
    """
    from lib.data.api.tmdb import ApiTmdb

    media_type = params.get('type', ['movie'])[0]
    tmdb_id_str = params.get('tmdb_id', [''])[0]

    if not tmdb_id_str:
        log("Plugin", "TMDB Details: Missing tmdb_id", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    try:
        tmdb_id = int(tmdb_id_str)
    except (ValueError, TypeError):
        log("Plugin", f"TMDB Details: Invalid tmdb_id '{tmdb_id_str}'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if media_type == 'person':
        from lib.data.api import person as person_api
        person_data = person_api.get_person_data(tmdb_id)
        if not person_data:
            log("Plugin", f"TMDB Details: No person data for tmdb_id={tmdb_id}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        _handle_person_details(handle, person_data)
        return

    api = ApiTmdb()

    if media_type == 'movie':
        data = api.get_movie_details_extended(tmdb_id)
    elif media_type == 'tv':
        data = api.get_tv_details_extended(tmdb_id)
    else:
        log("Plugin", f"TMDB Details: Invalid type '{media_type}'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if not data:
        log("Plugin", f"TMDB Details: No data for {media_type} tmdb_id={tmdb_id}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    title = data.get('title' if media_type == 'movie' else 'name', 'Unknown')
    listitem = xbmcgui.ListItem(title, offscreen=True)

    video_tag = listitem.getVideoInfoTag()
    video_tag.setMediaType(media_type if media_type == 'movie' else 'tvshow')
    video_tag.setTitle(title)

    listitem.setProperty('tmdb_id', str(tmdb_id))

    if data.get('overview'):
        video_tag.setPlot(data['overview'])

    if data.get('tagline'):
        video_tag.setTagLine(data['tagline'])

    if data.get('original_title' if media_type == 'movie' else 'original_name'):
        video_tag.setOriginalTitle(data.get('original_title' if media_type == 'movie' else 'original_name'))

    if media_type == 'movie':
        if data.get('release_date'):
            try:
                year = int(data['release_date'][:4])
                video_tag.setYear(year)
            except (ValueError, TypeError):
                pass
            video_tag.setPremiered(data['release_date'])
        if data.get('runtime'):
            video_tag.setDuration(data['runtime'] * 60)
    else:
        if data.get('first_air_date'):
            try:
                year = int(data['first_air_date'][:4])
                video_tag.setYear(year)
            except (ValueError, TypeError):
                pass
            video_tag.setPremiered(data['first_air_date'])

    if data.get('vote_average'):
        video_tag.setRating(data['vote_average'])
    if data.get('vote_count'):
        video_tag.setVotes(data['vote_count'])

    if data.get('genres'):
        genres = [g['name'] for g in data['genres']]
        video_tag.setGenres(genres)

    if data.get('production_companies'):
        studios = [s['name'] for s in data['production_companies']]
        video_tag.setStudios(studios)

    if data.get('production_countries'):
        countries = [c['name'] for c in data['production_countries']]
        video_tag.setCountries(countries)

    credits = data.get('credits', {})
    if credits.get('cast'):
        cast_list = []
        for person in credits['cast'][:20]:
            cast_member = xbmc.Actor(
                person.get('name', ''),
                person.get('character', ''),
                order=person.get('order', 0),
                thumbnail=f"https://image.tmdb.org/t/p/w500{person['profile_path']}" if person.get('profile_path') else ''
            )
            cast_list.append(cast_member)
        video_tag.setCast(cast_list)

    if credits.get('crew'):
        directors = [c['name'] for c in credits['crew'] if c.get('job') == 'Director']
        if directors:
            video_tag.setDirectors(directors)

        writers = [c['name'] for c in credits['crew'] if c.get('job') in ('Writer', 'Screenplay', 'Story')]
        if writers:
            video_tag.setWriters(writers)

    release_dates = data.get('release_dates' if media_type == 'movie' else 'content_ratings', {})
    if media_type == 'movie' and release_dates.get('results'):
        for country in release_dates['results']:
            if country.get('iso_3166_1') == 'US' and country.get('release_dates'):
                for rd in country['release_dates']:
                    if rd.get('certification'):
                        video_tag.setMpaa(rd['certification'])
                        break
                break
    elif media_type == 'tv' and release_dates.get('results'):
        for rating in release_dates['results']:
            if rating.get('iso_3166_1') == 'US' and rating.get('rating'):
                video_tag.setMpaa(rating['rating'])
                break

    external_ids = data.get('external_ids', {})
    if external_ids.get('imdb_id'):
        video_tag.setIMDBNumber(external_ids['imdb_id'])

    videos = data.get('videos', {})
    if videos.get('results'):
        trailers = [v for v in videos['results'] if v.get('type') == 'Trailer' and v.get('site') == 'YouTube']
        if trailers:
            trailer_url = f"plugin://plugin.video.youtube/play/?video_id={trailers[0]['key']}"
            video_tag.setTrailer(trailer_url)

    if data.get('keywords'):
        if media_type == 'movie':
            keywords = [k['name'] for k in data['keywords'].get('keywords', [])]
        else:
            keywords = [k['name'] for k in data['keywords'].get('results', [])]
        if keywords:
            video_tag.setTags(keywords)

    art = {}
    if data.get('poster_path'):
        art['poster'] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
    if data.get('backdrop_path'):
        art['fanart'] = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"

    images = data.get('images', {})
    if images.get('logos'):
        for logo in images['logos']:
            if logo.get('iso_639_1') in ('en', None):
                art['clearlogo'] = f"https://image.tmdb.org/t/p/original{logo['file_path']}"
                break

    if art:
        listitem.setArt(art)

    xbmcplugin.addDirectoryItem(handle, '', listitem, False)
    xbmcplugin.endOfDirectory(handle)


def _handle_root_menu(handle: int) -> None:
    """Show root menu with Tools, Search, and Widgets folders."""
    items = [
        ("Tools", "plugin://script.skin.info.service/?action=exec_tools", "DefaultAddonProgram.png", False),
        ("Search", "plugin://script.skin.info.service/?action=menu_search", "DefaultAddonsSearch.png", True),
        ("Widgets", "plugin://script.skin.info.service/?action=menu_widgets", "DefaultAddonVideo.png", True),
    ]

    for label, path, icon, is_folder in items:
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, path, li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _handle_search_menu(handle: int) -> None:
    """Show search submenu."""
    items = [
        ("Search Movies", "plugin://script.skin.info.service/?action=exec_search&dbtype=movie", "DefaultMovies.png"),
        ("Search TV Shows", "plugin://script.skin.info.service/?action=exec_search&dbtype=tv", "DefaultTVShows.png"),
        ("Search People", "plugin://script.skin.info.service/?action=exec_search&dbtype=person", "DefaultActor.png"),
    ]

    for label, path, icon in items:
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, path, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _handle_widgets_menu(handle: int) -> None:
    """Show widgets submenu."""
    items = [
        ("Discover", "plugin://script.skin.info.service/?action=discover_menu", "DefaultAddonVideo.png", True),
        ("Next Up", "plugin://script.skin.info.service/?action=next_up", "DefaultInProgressShows.png", True),
        ("Recent Episodes", "plugin://script.skin.info.service/?action=recent_episodes_grouped", "DefaultRecentlyAddedEpisodes.png", True),
        ("Seasonal", "plugin://script.skin.info.service/?action=menu_seasonal", "DefaultYear.png", True),
        ("Recommended Movies", "plugin://script.skin.info.service/?action=recommended&dbtype=movie", "DefaultMovies.png", True),
        ("Recommended TV Shows", "plugin://script.skin.info.service/?action=recommended&dbtype=tvshow", "DefaultTVShows.png", True),
    ]

    for label, path, icon, is_folder in items:
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, path, li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def _handle_seasonal_menu(handle: int) -> None:
    """Show seasonal submenu."""
    items = [
        ("Christmas", "plugin://script.skin.info.service/?action=seasonal&season=christmas", "DefaultYear.png"),
        ("Halloween", "plugin://script.skin.info.service/?action=seasonal&season=halloween", "DefaultYear.png"),
        ("Valentine's Day", "plugin://script.skin.info.service/?action=seasonal&season=valentines", "DefaultYear.png"),
        ("Thanksgiving", "plugin://script.skin.info.service/?action=seasonal&season=thanksgiving", "DefaultYear.png"),
        ("Star Wars Day", "plugin://script.skin.info.service/?action=seasonal&season=starwars", "DefaultYear.png"),
    ]

    for label, path, icon in items:
        li = xbmcgui.ListItem(label, offscreen=True)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, path, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, succeeded=True)


def main() -> None:
    """
    Plugin entry point with action-based routing.

    Supports:
    - action=get_cast: Aggregate cast from movie sets or TV seasons
    - action=get_cast_player: Get cast for currently playing library item
    - No action: Root menu
    """
    try:
        handle = int(sys.argv[1])
    except (ValueError, IndexError) as e:
        log("Plugin", f"Invalid handle provided: {e}", xbmc.LOGERROR)
        return

    if len(sys.argv) < 3 or not sys.argv[2] or sys.argv[2] == "?":
        _handle_root_menu(handle)
        return

    query_string = sys.argv[2]

    if query_string.startswith("?"):
        query_string = query_string[1:]

    import html
    query_string = html.unescape(query_string)

    params = parse_qs(query_string)

    action = params.get('action', [''])[0]

    if action == 'menu_search':
        _handle_search_menu(handle)
    elif action == 'menu_widgets':
        _handle_widgets_menu(handle)
    elif action == 'menu_seasonal':
        _handle_seasonal_menu(handle)
    elif action == 'exec_tools':
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        xbmc.executebuiltin('RunScript(script.skin.info.service,action=tools)')
    elif action == 'exec_search':
        dbtype = params.get('dbtype', ['movie'])[0]
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        xbmc.executebuiltin(f'RunScript(script.skin.info.service,action=tmdb_search,dbtype={dbtype})')
    elif action == 'get_cast':
        handle_get_cast(handle, params)
    elif action == 'get_cast_player':
        handle_get_cast_player(handle, params)
    elif action == 'path_stats':
        handle_path_stats(handle, params)
    elif action == 'wrap':
        handle_wrap(handle, params)
    elif action == 'discover_menu':
        from lib.plugin.discovery import handle_discover_menu
        handle_discover_menu(handle, params)
    elif action == 'discover_movies_menu':
        from lib.plugin.discovery import handle_discover_movies_menu
        handle_discover_movies_menu(handle, params)
    elif action == 'discover_tvshows_menu':
        from lib.plugin.discovery import handle_discover_tvshows_menu
        handle_discover_tvshows_menu(handle, params)
    elif action == 'next_up':
        from lib.plugin.widgets import handle_next_up
        handle_next_up(handle, params)
    elif action == 'recent_episodes_grouped':
        from lib.plugin.widgets import handle_recent_episodes_grouped
        handle_recent_episodes_grouped(handle, params)
    elif action == 'by_actor':
        from lib.plugin.widgets import handle_by_actor
        handle_by_actor(handle, params)
    elif action == 'by_director':
        from lib.plugin.widgets import handle_by_director
        handle_by_director(handle, params)
    elif action == 'similar':
        from lib.plugin.widgets import handle_similar
        handle_similar(handle, params)
    elif action == 'recommended':
        from lib.plugin.widgets import handle_recommended
        handle_recommended(handle, params)
    elif action == 'seasonal':
        from lib.plugin.widgets import handle_seasonal
        handle_seasonal(handle, params)
    elif action == 'similar_artists':
        from lib.plugin.widgets_music import handle_similar_artists
        handle_similar_artists(handle, params)
    elif action == 'artist_albums':
        from lib.plugin.widgets_music import handle_artist_albums
        handle_artist_albums(handle, params)
    elif action == 'artist_musicvideos':
        from lib.plugin.widgets_music import handle_artist_musicvideos
        handle_artist_musicvideos(handle, params)
    elif action == 'genre_artists':
        from lib.plugin.widgets_music import handle_genre_artists
        handle_genre_artists(handle, params)
    elif action == 'letter_jump':
        from lib.skin.container import handle_letter_jump_list
        handle_letter_jump_list(handle, params)
    elif action == 'jump_letter_exec':
        from lib.skin.container import handle_letter_jump_exec
        handle_letter_jump_exec(handle, params)
    elif action == 'person_info':
        handle_person_info(handle, params)
    elif action == 'person_library':
        handle_person_library(handle, params)
    elif action == 'tmdb_details':
        handle_tmdb_details(handle, params)
    elif action == 'online':
        handle_online(handle, params)
    elif action == 'creators':
        params['crew_type'] = ['creator']
        handle_crew_list(handle, params)
    elif action == 'directors':
        params['crew_type'] = ['director']
        handle_crew_list(handle, params)
    elif action == 'writers':
        params['crew_type'] = ['writer']
        handle_crew_list(handle, params)
    elif action == 'crew':
        handle_crew_list(handle, params)
    else:
        from lib.plugin.discovery import WIDGET_REGISTRY, handle_discover
        if action in WIDGET_REGISTRY:
            handle_discover(handle, action, params)
        else:
            handle_dbid_query(handle, params)


if __name__ == "__main__":
    main()
