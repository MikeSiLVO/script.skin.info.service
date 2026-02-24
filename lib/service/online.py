"""Online data service for external API properties.

Monitors focused items and fetches metadata from external APIs (TMDb, OMDb, MDBList, Trakt).
Sets properties with SkinInfo.Online.* prefix on Home window.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import xbmc

from lib.kodi.client import log
from lib.kodi.utils import clear_group, get_prop, set_prop, wait_for_kodi_ready, batch_set_props
from lib.data.database.cache import get_cached_online_properties, cache_online_properties

_MEMORY_CACHE: OrderedDict[str, Dict[str, str]] = OrderedDict()
_MEMORY_CACHE_MAX = 20

ONLINE_POLL_INTERVAL = 0.10
ONLINE_PROPERTY_PREFIX = "SkinInfo.Online."
PLAYER_ONLINE_PROPERTY_PREFIX = "SkinInfo.Player.Online."
PLAYER_MUSIC_ONLINE_PREFIX = "SkinInfo.Player.Online.Music."
PLAYER_MUSICVIDEO_ONLINE_PREFIX = "SkinInfo.Player.Online.MusicVideo."

_SKININFO_PREFIX_MAP = {
    "movie": "SkinInfo.Movie",
    "tvshow": "SkinInfo.TVShow",
    "episode": "SkinInfo.Episode",
}

_PLAYER_SKININFO_PREFIX_MAP = {
    "movie": "SkinInfo.Player",
    "episode": "SkinInfo.Player",
}


def _make_cache_key(media_type: str, imdb_id: str, tmdb_id: str) -> str:
    """Create a stable cache key using the best available ID.

    Priority: TMDb (available earlier, consistent) > IMDb
    Format: "{media_type}:{id_type}:{id_value}"
    """
    if tmdb_id:
        return f"{media_type}:tmdb:{tmdb_id}"
    if imdb_id:
        return f"{media_type}:imdb:{imdb_id}"
    return ""


def _resolve_ids(dbtype: str, dbid: str) -> Tuple[str, str]:
    """
    Resolve IMDb and TMDb IDs using multiple fallback sources.

    Tries in order:
    1. ListItem.UniqueID(imdb/tmdb)
    2. ListItem.IMDBNumber if starts with "tt"
    3. SkinInfo.{MediaType}.UniqueID.IMDB/TMDB
    4. Metadata cache via TMDb ID
    5. JSON-RPC lookup
    """
    imdb_id = xbmc.getInfoLabel("ListItem.UniqueID(imdb)") or ""
    tmdb_id = xbmc.getInfoLabel("ListItem.UniqueID(tmdb)") or ""

    if not imdb_id:
        imdbnumber = xbmc.getInfoLabel("ListItem.IMDBNumber") or ""
        if imdbnumber.startswith("tt"):
            imdb_id = imdbnumber

    if not imdb_id or not tmdb_id:
        prefix = _SKININFO_PREFIX_MAP.get(dbtype, "")
        if prefix:
            if not imdb_id:
                imdb_id = get_prop(f"{prefix}.UniqueID.IMDB") or ""
            if not tmdb_id:
                tmdb_id = get_prop(f"{prefix}.UniqueID.TMDB") or ""

    if not imdb_id and tmdb_id:
        from lib.data.database import cache as db_cache
        cache_type = "tvshow" if dbtype == "episode" else dbtype
        cached = db_cache.get_cached_metadata(cache_type, tmdb_id)
        if cached:
            imdb_id = cached.get("external_ids", {}).get("imdb_id") or ""

    if not imdb_id and not tmdb_id:
        imdb_id, tmdb_id = _jsonrpc_get_uniqueids(dbtype, dbid)

    return imdb_id, tmdb_id


def _jsonrpc_get_uniqueids(dbtype: str, dbid: str) -> Tuple[str, str]:
    from lib.kodi.client import request

    method_map = {
        "movie": ("VideoLibrary.GetMovieDetails", "movieid", "moviedetails"),
        "tvshow": ("VideoLibrary.GetTVShowDetails", "tvshowid", "tvshowdetails"),
        "episode": ("VideoLibrary.GetEpisodeDetails", "episodeid", "episodedetails"),
    }

    if dbtype not in method_map:
        return "", ""

    method, id_key, result_key = method_map[dbtype]

    try:
        result = request(method, {id_key: int(dbid), "properties": ["uniqueid"]})
        inner = result.get("result", {}) if result else {}
        if inner and result_key in inner:
            uniqueid = inner[result_key].get("uniqueid", {})
            return uniqueid.get("imdb", ""), str(uniqueid.get("tmdb", "") or "")
    except Exception as e:
        log("Service", f"JSON-RPC uniqueid lookup failed: {e}", xbmc.LOGDEBUG)

    return "", ""


def _resolve_season_ids(seasonid: str) -> Tuple[str, str]:
    """Resolve IMDb/TMDb IDs for a season via its parent tvshow."""
    from lib.kodi.client import get_item_details
    details = get_item_details('season', int(seasonid), ["tvshowid"])
    if not details or not isinstance(details, dict):
        return "", ""
    tvshowid = details.get("tvshowid")
    if not tvshowid or tvshowid == -1:
        return "", ""
    return _jsonrpc_get_uniqueids("tvshow", str(tvshowid))


def _resolve_player_ids(dbtype: str, dbid: str) -> Tuple[str, str]:
    """
    Resolve IMDb and TMDb IDs for currently playing video.

    Tries in order:
    1. VideoPlayer.UniqueID(imdb/tmdb)
    2. VideoPlayer.IMDBNumber if starts with "tt"
    3. SkinInfo.Player.UniqueID.IMDB/TMDB
    4. Metadata cache via TMDb ID
    5. JSON-RPC lookup
    """
    imdb_id = xbmc.getInfoLabel("VideoPlayer.UniqueID(imdb)") or ""
    tmdb_id = xbmc.getInfoLabel("VideoPlayer.UniqueID(tmdb)") or ""

    if not imdb_id:
        imdbnumber = xbmc.getInfoLabel("VideoPlayer.IMDBNumber") or ""
        if imdbnumber.startswith("tt"):
            imdb_id = imdbnumber

    if not imdb_id or not tmdb_id:
        prefix = _PLAYER_SKININFO_PREFIX_MAP.get(dbtype, "")
        if prefix:
            if not imdb_id:
                imdb_id = get_prop(f"{prefix}.UniqueID.IMDB") or ""
            if not tmdb_id:
                tmdb_id = get_prop(f"{prefix}.UniqueID.TMDB") or ""

    if not imdb_id and tmdb_id:
        from lib.data.database import cache as db_cache
        cache_type = "tvshow" if dbtype == "episode" else dbtype
        cached = db_cache.get_cached_metadata(cache_type, tmdb_id)
        if cached:
            imdb_id = cached.get("external_ids", {}).get("imdb_id") or ""

    if not imdb_id and not tmdb_id:
        imdb_id, tmdb_id = _jsonrpc_get_uniqueids(dbtype, dbid)

    return imdb_id, tmdb_id


class ServiceAbortFlag:
    """Lightweight abort flag for online service API calls."""

    def __init__(self, abort_event: threading.Event):
        self._abort_event = abort_event
        self._monitor = xbmc.Monitor()

    def is_requested(self) -> bool:
        if self._monitor.abortRequested():
            return True
        return self._abort_event.is_set()


class OnlineServiceMain(threading.Thread):
    """Service thread for fetching and setting online API data."""

    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()
        self._abort_flag = ServiceAbortFlag(self.abort)
        self._last_item_key: Optional[str] = None
        self._fetch_thread: Optional[threading.Thread] = None
        self._fetch_for_key: Optional[str] = None
        self._last_player_key: Optional[str] = None
        self._player_fetch_thread: Optional[threading.Thread] = None
        self._player_fetch_for_key: Optional[str] = None
        self._last_prop_keys: set = set()
        self._last_music_key: Optional[str] = None
        self._music_fetch_thread: Optional[threading.Thread] = None
        self._music_fetch_for_key: Optional[str] = None
        self._music_fanart_urls: List[str] = []
        self._music_fanart_index: int = 0
        self._music_fanart_last_rotate: float = 0.0
        self._active_music_online_prefix: str = PLAYER_MUSIC_ONLINE_PREFIX
        self._last_musicvideo_player_key: Optional[str] = None
        self._musicvideo_player_fetch_thread: Optional[threading.Thread] = None
        self._musicvideo_player_fetch_for_key: Optional[str] = None

    def run(self) -> None:
        monitor = xbmc.Monitor()

        if not wait_for_kodi_ready(monitor):
            return

        log("Service", "Online service started", xbmc.LOGINFO)

        while not monitor.waitForAbort(ONLINE_POLL_INTERVAL):
            if self.abort.is_set():
                break
            try:
                self._loop()
            except Exception as e:
                log("Service", f"Online service error: {e}", xbmc.LOGWARNING)

        log("Service", "Online service stopped", xbmc.LOGINFO)

    def _loop(self) -> None:
        self._handle_library_item()
        self._handle_player()
        self._handle_music_player()
        self._handle_musicvideo_player()
        self._rotate_music_fanart()

    def _handle_library_item(self) -> None:
        dbid = xbmc.getInfoLabel("ListItem.DBID") or ""
        dbtype = xbmc.getInfoLabel("ListItem.DBType") or ""

        if not dbid or dbtype not in ("movie", "tvshow", "episode", "season"):
            if self._last_item_key:
                self._clear_properties()
                self._last_item_key = None
                self._last_prop_keys = set()
            return

        if dbtype == "season":
            imdb_id, tmdb_id = _resolve_season_ids(dbid)
            effective_type = "tvshow"
        else:
            imdb_id, tmdb_id = _resolve_ids(dbtype, dbid)
            effective_type = dbtype

        if not imdb_id and not tmdb_id:
            return

        cache_key = _make_cache_key(effective_type, imdb_id, tmdb_id)
        if not cache_key:
            return

        if cache_key == self._last_item_key:
            return

        self._last_item_key = cache_key

        cached_props = _MEMORY_CACHE.get(cache_key)
        if cached_props is None:
            cached_props = get_cached_online_properties(cache_key)
            if cached_props:
                _MEMORY_CACHE[cache_key] = cached_props
                if len(_MEMORY_CACHE) > _MEMORY_CACHE_MAX:
                    _MEMORY_CACHE.popitem(last=False)

        if cached_props:
            props_to_set = {}
            new_keys = set()
            for key, value in cached_props.items():
                if value:
                    props_to_set[f"{ONLINE_PROPERTY_PREFIX}{key}"] = str(value)
                    new_keys.add(key)
            for old_key in self._last_prop_keys - new_keys:
                props_to_set[f"{ONLINE_PROPERTY_PREFIX}{old_key}"] = ""
            batch_set_props(props_to_set)
            self._last_prop_keys = new_keys
            return

        if self._fetch_thread and self._fetch_thread.is_alive() and self._fetch_for_key == cache_key:
            return

        self._fetch_for_key = cache_key
        self._fetch_thread = threading.Thread(
            target=self._fetch_worker,
            args=(effective_type, imdb_id, tmdb_id, cache_key, ONLINE_PROPERTY_PREFIX, "_last_item_key", self._abort_flag),
            daemon=True
        )
        self._fetch_thread.start()

    def _handle_player(self) -> None:
        if not xbmc.getCondVisibility("Player.HasVideo"):
            if self._last_player_key:
                self._clear_player_properties()
                self._last_player_key = None
            return

        dbid = xbmc.getInfoLabel("VideoPlayer.DBID") or ""
        if not dbid:
            if self._last_player_key:
                self._clear_player_properties()
                self._last_player_key = None
            return

        is_movie = xbmc.getCondVisibility("VideoPlayer.Content(movies)")
        is_episode = xbmc.getCondVisibility("VideoPlayer.Content(episodes)")

        if is_movie:
            dbtype = "movie"
        elif is_episode:
            dbtype = "episode"
        else:
            if self._last_player_key:
                self._clear_player_properties()
                self._last_player_key = None
            return

        imdb_id, tmdb_id = _resolve_player_ids(dbtype, dbid)

        if not imdb_id and not tmdb_id:
            if self._last_player_key:
                self._clear_player_properties()
                self._last_player_key = None
            return

        cache_key = f"player:{_make_cache_key(dbtype, imdb_id, tmdb_id)}"
        if cache_key == "player:":
            return

        if cache_key == self._last_player_key:
            return

        self._last_player_key = cache_key

        if self._player_fetch_thread and self._player_fetch_thread.is_alive() and self._player_fetch_for_key == cache_key:
            return

        self._player_fetch_for_key = cache_key
        self._player_fetch_thread = threading.Thread(
            target=self._fetch_worker,
            args=(dbtype, imdb_id, tmdb_id, cache_key, PLAYER_ONLINE_PROPERTY_PREFIX, "_last_player_key", self._abort_flag),
            daemon=True
        )
        self._player_fetch_thread.start()

    def _clear_properties(self) -> None:
        clear_group(ONLINE_PROPERTY_PREFIX)

    def _clear_player_properties(self) -> None:
        clear_group(PLAYER_ONLINE_PROPERTY_PREFIX)

    def _handle_music_player(self) -> None:
        if not xbmc.getCondVisibility("Player.HasAudio"):
            if self._last_music_key:
                self._clear_music_properties()
                self._last_music_key = None
            return

        artist_name = xbmc.getInfoLabel("MusicPlayer.Artist") or ""
        if not artist_name:
            if self._last_music_key:
                self._clear_music_properties()
                self._last_music_key = None
            return

        if artist_name == self._last_music_key:
            return

        self._last_music_key = artist_name
        self._music_fanart_urls = []
        self._music_fanart_index = 0

        if (self._music_fetch_thread and self._music_fetch_thread.is_alive()
                and self._music_fetch_for_key == artist_name):
            return

        self._music_fetch_for_key = artist_name
        self._music_fetch_thread = threading.Thread(
            target=self._music_fetch_worker,
            args=(artist_name,),
            daemon=True,
        )
        self._music_fetch_thread.start()

    def _music_fetch_worker(self, artist_name: str) -> None:
        try:
            if self._abort_flag.is_requested():
                return

            from lib.service.music import fetch_artist_online_data

            mbids = _get_playing_artist_mbids()
            album = xbmc.getInfoLabel("MusicPlayer.Album") or None
            track = xbmc.getInfoLabel("MusicPlayer.Title") or None

            result = fetch_artist_online_data(
                artist_name,
                mbids=mbids or None,
                album=album,
                track=track,
                abort_flag=self._abort_flag,
            )

            if artist_name != self._last_music_key:
                return
            if not result:
                return

            self._apply_music_online_result(artist_name, result, track, album, PLAYER_MUSIC_ONLINE_PREFIX)

        except Exception as e:
            log("Service", f"Music player online fetch error: {e}", xbmc.LOGWARNING)

    def _handle_musicvideo_player(self) -> None:
        """Handle music video playback — set artist online data."""
        is_musicvideo = (
            xbmc.getCondVisibility("Player.HasVideo")
            and xbmc.getCondVisibility("VideoPlayer.Content(musicvideos)")
        )

        if not is_musicvideo:
            if self._last_musicvideo_player_key:
                self._clear_musicvideo_online_properties()
                self._last_musicvideo_player_key = None
            return

        artist_name = xbmc.getInfoLabel("VideoPlayer.Artist") or ""
        if not artist_name:
            if self._last_musicvideo_player_key:
                self._clear_musicvideo_online_properties()
                self._last_musicvideo_player_key = None
            return

        if artist_name == self._last_musicvideo_player_key:
            return

        self._last_musicvideo_player_key = artist_name
        self._music_fanart_urls = []
        self._music_fanart_index = 0

        if (self._musicvideo_player_fetch_thread
                and self._musicvideo_player_fetch_thread.is_alive()
                and self._musicvideo_player_fetch_for_key == artist_name):
            return

        self._musicvideo_player_fetch_for_key = artist_name
        self._musicvideo_player_fetch_thread = threading.Thread(
            target=self._musicvideo_player_fetch_worker,
            args=(artist_name,),
            daemon=True,
        )
        self._musicvideo_player_fetch_thread.start()

    def _musicvideo_player_fetch_worker(self, artist_name: str) -> None:
        try:
            if self._abort_flag.is_requested():
                return

            from lib.service.music import fetch_artist_online_data

            album = xbmc.getInfoLabel("VideoPlayer.Album") or None
            track = xbmc.getInfoLabel("VideoPlayer.Title") or None

            result = fetch_artist_online_data(
                artist_name,
                album=album,
                track=track,
                abort_flag=self._abort_flag,
            )

            if artist_name != self._last_musicvideo_player_key:
                return
            if not result:
                return

            self._apply_music_online_result(artist_name, result, track, album, PLAYER_MUSICVIDEO_ONLINE_PREFIX)

        except Exception as e:
            log("Service", f"Music video player online fetch error: {e}", xbmc.LOGWARNING)

    def _apply_music_online_result(
        self,
        artist_name: str,
        result: object,
        track: Optional[str],
        album: Optional[str],
        prefix: str,
    ) -> None:
        """Apply fetched music online data to window properties."""
        from lib.service.music import (
            fetch_track_online_data,
            fetch_album_online_data,
            extract_track_properties,
            extract_album_properties,
        )

        self._music_fanart_urls = result.fanart_urls  # type: ignore[attr-defined]
        self._music_fanart_index = 0
        self._music_fanart_last_rotate = time.time()
        self._active_music_online_prefix = prefix
        self._set_music_online_properties(
            artist_name, result.bio, result.fanart_urls, result.artist_art,  # type: ignore[attr-defined]
            prefix,
        )

        if track:
            fetch_track_online_data(artist_name, track, abort_flag=self._abort_flag)
            track_props = extract_track_properties(artist_name, track)
            if track_props:
                batch_set_props({
                    f"{prefix}Track.{k}": v
                    for k, v in track_props.items()
                })

        if album:
            fetch_album_online_data(artist_name, album, abort_flag=self._abort_flag)
            album_props = extract_album_properties(artist_name, album)
            if album_props:
                batch_set_props({
                    f"{prefix}Album.{k}": v
                    for k, v in album_props.items()
                })

    def _set_music_online_properties(self, artist_name: str, bio: str,
                                     fanart_urls: List[str],
                                     artist_art: Dict[str, str],
                                     prefix: str) -> None:
        ap = f"{prefix}Artist."
        props: Dict[str, Optional[str]] = {
            f"{ap}Name": artist_name,
            f"{ap}FanArt.Count": str(len(fanart_urls)),
            f"{ap}FanArt": fanart_urls[0] if fanart_urls else "",
            f"{ap}Bio": bio or "",
        }

        for art_type in ('thumb', 'clearlogo', 'banner'):
            key = art_type[0].upper() + art_type[1:]
            props[f"{ap}{key}"] = artist_art.get(art_type, '')

        batch_set_props(props)

    def _rotate_music_fanart(self) -> None:
        if len(self._music_fanart_urls) <= 1:
            return

        now = time.time()

        interval_str = xbmc.getInfoLabel(
            'Skin.String(SkinInfo.SlideshowRefreshInterval)'
        ) or '10'
        try:
            interval = int(interval_str)
            interval = max(5, min(interval, 3600))
        except ValueError:
            interval = 10

        if now - self._music_fanart_last_rotate < interval:
            return

        self._music_fanart_last_rotate = now
        self._music_fanart_index = (
            (self._music_fanart_index + 1) % len(self._music_fanart_urls)
        )
        set_prop(
            f"{self._active_music_online_prefix}Artist.FanArt",
            self._music_fanart_urls[self._music_fanart_index],
        )

    def _clear_music_properties(self) -> None:
        clear_group(PLAYER_MUSIC_ONLINE_PREFIX)
        self._music_fanart_urls = []
        self._music_fanart_index = 0

    def _clear_musicvideo_online_properties(self) -> None:
        clear_group(PLAYER_MUSICVIDEO_ONLINE_PREFIX)
        self._music_fanart_urls = []
        self._music_fanart_index = 0

    def _fetch_worker(
        self,
        media_type: str,
        imdb_id: str,
        tmdb_id: str,
        cache_key: str,
        prop_prefix: str,
        key_attr: str,
        abort_flag: ServiceAbortFlag
    ) -> None:
        try:
            if abort_flag.is_requested():
                return

            is_player = key_attr == "_last_player_key"
            props = fetch_all_online_data(media_type, imdb_id, tmdb_id, abort_flag, is_player)

            if abort_flag.is_requested():
                return

            if not props:
                return

            if cache_key != getattr(self, key_attr):
                return

            if abort_flag.is_requested():
                return

            props_to_set = {}
            new_keys = set()
            for key, value in props.items():
                if value:
                    props_to_set[f"{prop_prefix}{key}"] = str(value)
                    new_keys.add(key)

            if not is_player:
                for old_key in self._last_prop_keys - new_keys:
                    props_to_set[f"{prop_prefix}{old_key}"] = ""
                self._last_prop_keys = new_keys

            batch_set_props(props_to_set)

            if not is_player:
                _MEMORY_CACHE[cache_key] = props
                if len(_MEMORY_CACHE) > _MEMORY_CACHE_MAX:
                    _MEMORY_CACHE.popitem(last=False)
                from lib.kodi.settings import KodiSettings
                ttl_hours = KodiSettings.provider_cache_days() * 24
                cache_online_properties(cache_key, props, ttl_hours=ttl_hours)

        except Exception as e:
            log("Service", f"Online fetch error: {e}", xbmc.LOGWARNING)


def fetch_all_online_data(
    media_type: str,
    imdb_id: str,
    tmdb_id: str,
    abort_flag: Optional[ServiceAbortFlag] = None,
    is_player: bool = False,
    is_library_item: bool = True
) -> Dict[str, str]:
    """
    Fetch all online data and return as property dictionary.

    Combines:
    - Full TMDb metadata (title, plot, cast, etc.)
    - Ratings from all sources
    - Awards from OMDb
    - Common Sense from MDBList
    - RT status from MDBList
    - Trakt subgenres

    Args:
        media_type: "movie", "tvshow", or "episode"
        imdb_id: IMDb ID
        tmdb_id: TMDb ID
        abort_flag: Optional abort flag for cancellation
        is_player: If True, also set stinger properties for movies
        is_library_item: If True, use smart TTL. If False, 24h TTL and skip season fetch.

    Returns:
        Dictionary of property key -> value pairs
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from lib.data.api.tmdb import resolve_tmdb_id
    from lib.plugin.online import (
        _fetch_omdb_data,
        _fetch_mdblist_data,
        _fetch_trakt_data,
    )

    props: Dict[str, str] = {}
    is_episode = media_type == "episode"

    if abort_flag and abort_flag.is_requested():
        return props

    resolved_tmdb_id = resolve_tmdb_id(
        tmdb_id,
        imdb_id,
        "tvshow" if is_episode else media_type
    )

    if not imdb_id and not resolved_tmdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        if resolved_tmdb_id and not is_episode:
            futures[executor.submit(
                _fetch_tmdb_full_data,
                media_type,
                resolved_tmdb_id,
                abort_flag,
                is_player,
                is_library_item
            )] = "tmdb"

        if imdb_id:
            futures[executor.submit(
                _fetch_omdb_data,
                imdb_id,
                abort_flag
            )] = "omdb"

        if imdb_id or resolved_tmdb_id:
            futures[executor.submit(
                _fetch_mdblist_data,
                media_type,
                imdb_id,
                resolved_tmdb_id or "",
                is_episode,
                abort_flag
            )] = "mdblist"

            futures[executor.submit(
                _fetch_trakt_data,
                media_type,
                imdb_id,
                resolved_tmdb_id or "",
                is_episode,
                None,
                None,
                abort_flag
            )] = "trakt"

        for future in as_completed(futures):
            if abort_flag and abort_flag.is_requested():
                executor.shutdown(wait=False, cancel_futures=True)
                return props

            source = futures[future]
            try:
                result = future.result()
                if result:
                    props.update(result)
            except Exception as e:
                log("Service", f"Online fetch error ({source}): {e}", xbmc.LOGWARNING)

    return props


def _fetch_tmdb_full_data(
    media_type: str,
    tmdb_id: str,
    abort_flag: Optional[ServiceAbortFlag] = None,
    is_player: bool = False,
    is_library_item: bool = True
) -> Dict[str, str]:
    """
    Fetch full TMDb metadata and format as properties.

    Args:
        media_type: "movie" or "tvshow"
        tmdb_id: TMDb ID
        abort_flag: Optional abort flag for cancellation
        is_player: If True, also set stinger properties for movies
        is_library_item: If True, use smart TTL. If False, 24h TTL and skip season fetch.

    Returns:
        Dictionary of property key -> value pairs
    """
    from lib.data.api.tmdb import ApiTmdb
    from lib.kodi.formatters import (
        format_rating_props,
        format_movie_props,
        format_tvshow_props,
        format_credits_props,
        format_images_props,
        format_extra_props,
    )

    props: Dict[str, str] = {}

    if abort_flag and abort_flag.is_requested():
        return props

    try:
        api = ApiTmdb()
        data = api.get_complete_data(
            media_type, int(tmdb_id), abort_flag=abort_flag, is_library_item=is_library_item
        )

        if abort_flag and abort_flag.is_requested():
            return props

        if not data:
            return props

        if media_type == "movie":
            props.update(format_movie_props(data))
            if is_player:
                set_stinger_properties_from_tmdb(data)
        else:
            props.update(format_tvshow_props(data))

        vote_avg = data.get("vote_average")
        vote_cnt = data.get("vote_count")
        if vote_avg is not None and vote_cnt is not None:
            props.update(format_rating_props("tmdb", float(vote_avg), int(vote_cnt)))

        props.update(format_credits_props(data))
        props.update(format_images_props(data))
        props.update(format_extra_props(data))

    except Exception as e:
        log("Service", f"TMDb full fetch error: {e}", xbmc.LOGWARNING)

    return props


def set_stinger_properties_from_tmdb(data: dict) -> bool:
    """
    Check TMDB data for stinger keywords and set window properties.

    Sets properties on fullscreenvideo window (12901):
    - SkinInfo.Stinger.HasDuring
    - SkinInfo.Stinger.HasAfter
    - SkinInfo.Stinger.Type
    - SkinInfo.Stinger.Source

    Args:
        data: Complete TMDB movie data with keywords

    Returns:
        True if stinger found, False otherwise
    """
    import xbmcgui

    keywords = data.get("keywords") or {}
    keyword_list = keywords.get("keywords") or []

    if not keyword_list:
        return False

    keyword_names = {kw.get("name", "").lower() for kw in keyword_list if isinstance(kw, dict)}

    has_during = "duringcreditsstinger" in keyword_names
    has_after = "aftercreditsstinger" in keyword_names

    if not has_during and not has_after:
        return False

    if has_during and has_after:
        stinger_type = "both"
    elif has_during:
        stinger_type = "during"
    else:
        stinger_type = "after"

    window = xbmcgui.Window(12901)
    window.setProperty("SkinInfo.Stinger.HasDuring", "true" if has_during else "")
    window.setProperty("SkinInfo.Stinger.HasAfter", "true" if has_after else "")
    window.setProperty("SkinInfo.Stinger.Type", stinger_type)
    window.setProperty("SkinInfo.Stinger.Source", "tmdb")

    log("Service", f"Stinger detected from TMDB: {stinger_type}", xbmc.LOGDEBUG)
    return True


def _get_playing_artist_mbids() -> List[str]:
    try:
        player = xbmc.Player()
        if not player.isPlayingAudio():
            return []
        tag = player.getMusicInfoTag()
        mbids = tag.getMusicBrainzArtistID()
        if isinstance(mbids, list):
            return [m for m in mbids if m]
        return []
    except Exception:
        return []


