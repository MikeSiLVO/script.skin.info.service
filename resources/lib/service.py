"""SkinInfo background service for property updates.

Monitors ListItem changes and updates window properties with detailed media information
for Movies, TV shows, Music, and more.
"""
from __future__ import annotations

import threading
import xbmc
import xbmcaddon

from resources.lib.kodi import request, get_cache_only, extract_result, KODI_GET_DETAILS_METHODS, KODI_MOVIE_PROPERTIES  # noqa: E402
from resources.lib.properties import (  # noqa: E402
    set_artist_properties,
    set_album_properties,
    set_movie_properties,
    set_movieset_properties,
    set_tvshow_properties,
    set_season_properties,
    set_episode_properties,
    set_musicvideo_properties,
    set_ratings_properties,
)
from resources.lib.utils import clear_group, set_prop, clear_prop  # noqa: E402

SERVICE_POLL_INTERVAL = 0.25  # Poll interval in seconds (250ms for fast property updates)
SERVICE_STARTUP_WAIT = 1.0
SERVICE_READY_CHECK_INTERVAL = 0.5
MAX_CONSECUTIVE_ERRORS = 10
CACHE_MOVIESET_TTL = 300

_MEDIA_TYPE_PREFIXES = {
    "movie": "SkinInfo.Movie.",
    "set": "SkinInfo.Set.",
    "artist": "SkinInfo.Artist.",
    "album": "SkinInfo.Album.",
    "tvshow": "SkinInfo.TVShow.",
    "season": "SkinInfo.Season.",
    "episode": "SkinInfo.Episode.",
    "musicvideo": "SkinInfo.MusicVideo.",
}


class SkinInfoService(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()
        self._last_id = None
        self._last_type = None
        self._blur_thread = None
        self._last_blur_source = None

    def _clear_media_type(self, media_type: str) -> None:
        prefix = _MEDIA_TYPE_PREFIXES.get(media_type)
        if prefix:
            clear_group(prefix)

    def _set_listitem_properties(self, media_type: str, fields: tuple) -> None:
        """Set ListItem properties for immediate visual feedback.

        Args:
            media_type: The media type (e.g., "Movie", "TVShow")
            fields: Tuple of field names to extract from ListItem
        """
        try:
            art_keys = ("poster", "fanart", "clearlogo", "landscape", "banner",
                       "thumb", "thumbnail", "keyart", "logo", "clearart")

            for field in fields:
                val = xbmc.getInfoLabel(f"ListItem.{field}") or ""
                set_prop(f"SkinInfo.{media_type}.{field}", val)

            for ak in art_keys:
                v = xbmc.getInfoLabel(f"ListItem.Art({ak})") or ""
                if v:
                    set_prop(f"SkinInfo.{media_type}.Art({ak})", v)
                else:
                    clear_prop(f"SkinInfo.{media_type}.Art({ak})")
        except (AttributeError, TypeError):
            pass
        except Exception as e:
            xbmc.log(f"SkinInfo: Unexpected error in _set_listitem_properties for {media_type}: {str(e)}", xbmc.LOGERROR)

    def _ready(self) -> bool:
        """Check if Kodi's JSON-RPC API is ready."""
        try:
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}')
            return "pong" in result.lower()
        except Exception:
            return False

    def run(self) -> None:
        version = xbmcaddon.Addon().getAddonInfo("version")
        xbmc.log(
            f"script.skin.info.service: Starting (version={version}), waiting for Kodi to be ready...",
            xbmc.LOGINFO,
        )
        monitor = xbmc.Monitor()

        if not monitor.waitForAbort(SERVICE_STARTUP_WAIT):
            while not monitor.waitForAbort(SERVICE_READY_CHECK_INTERVAL):
                if self._ready():
                    break

        xbmc.log("script.skin.info.service: Kodi ready, service started", xbmc.LOGINFO)

        try:
            set_prop("SkinInfo.Service.Running", "true")
        except RuntimeError as e:
            xbmc.log(f"SkinInfo: Error setting service running flag: {str(e)}", xbmc.LOGWARNING)
        except Exception as e:
            xbmc.log(f"SkinInfo: Unexpected error setting service flag: {str(e)}", xbmc.LOGERROR)

        consecutive_errors = 0

        try:
            while not monitor.waitForAbort(SERVICE_POLL_INTERVAL):
                if self.abort.is_set():
                    break
                try:
                    self._loop()
                    consecutive_errors = 0
                except (KeyError, ValueError, TypeError):
                    consecutive_errors += 1
                except Exception as e:
                    import traceback
                    xbmc.log(f"SkinInfo: Unexpected error in service loop: {str(e)}", xbmc.LOGERROR)
                    xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
                    consecutive_errors += 1

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    xbmc.log(f"SkinInfo: Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}), stopping service", xbmc.LOGERROR)
                    break
        finally:
            try:
                clear_prop("SkinInfo.Service.Running")
            except Exception:
                pass

    def _loop(self) -> None:
        dbid = xbmc.getInfoLabel("ListItem.DBID") or ""
        if not dbid:
            if self._last_type:
                self._clear_media_type(self._last_type)
                self._last_type = ""
                self._last_id = None
            self._handle_blur()
            return

        dbtype = xbmc.getInfoLabel("ListItem.DBType") or ""
        if dbid == self._last_id and dbtype and dbtype == self._last_type:
            self._handle_blur()
            return

        if dbtype in ("set", "movie", "artist", "album", "tvshow", "season", "episode", "musicvideo"):
            cur_type = dbtype
        else:
            if dbid == self._last_id and self._last_type:
                cur_type = self._last_type
            else:
                is_set = xbmc.getCondVisibility(
                    "ListItem.IsCollection | String.IsEqual(ListItem.DBType,set)"
                )
                in_movies  = xbmc.getCondVisibility("Container.Content(movies)")
                in_sets    = xbmc.getCondVisibility("Container.Content(sets)")
                in_artists = xbmc.getCondVisibility("Container.Content(artists)")
                in_albums  = xbmc.getCondVisibility("Container.Content(albums)")
                in_tvshows = xbmc.getCondVisibility("Container.Content(tvshows)")
                in_seasons = xbmc.getCondVisibility("Container.Content(seasons)")
                in_episodes = xbmc.getCondVisibility("Container.Content(episodes)")
                in_musicvideos = xbmc.getCondVisibility("Container.Content(musicvideos)")

                if is_set or in_sets:
                    cur_type = "set"
                elif in_movies and not is_set:
                    cur_type = "movie"
                elif in_artists:
                    cur_type = "artist"
                elif in_albums:
                    cur_type = "album"
                elif in_tvshows:
                    cur_type = "tvshow"
                elif in_seasons:
                    cur_type = "season"
                elif in_episodes:
                    cur_type = "episode"
                elif in_musicvideos:
                    cur_type = "musicvideo"
                else:
                    cur_type = ""

        if dbid == self._last_id and cur_type == self._last_type:
            self._handle_blur()
            return

        if cur_type == "set":
            self._set_listitem_properties("Set", ("Title", "Plot"))
            self._last_id = dbid
            self._last_type = "set"
            self._set_movieset_details(dbid)
            self._handle_blur()
            return

        if cur_type == "movie":
            self._set_listitem_properties("Movie", ("Title", "Year", "Plot", "Rating"))
            self._last_id = dbid
            self._last_type = "movie"
            self._set_movie_details(dbid)
            self._handle_blur()
            return

        if cur_type == "artist":
            if self._last_type != "artist":
                self._clear_media_type("album")
            self._set_listitem_properties("Artist", ("Title",))
            self._last_id = dbid
            self._last_type = "artist"
            self._set_artist_details(dbid)
            self._handle_blur()
            return

        if cur_type == "album":
            if self._last_type != "album":
                self._clear_media_type("artist")
            self._set_listitem_properties("Album", ("Title", "Year"))
            self._last_id = dbid
            self._last_type = "album"
            self._set_album_details(dbid)
            self._handle_blur()
            return

        if cur_type == "tvshow":
            self._set_listitem_properties("TVShow", ("Title", "Year", "Plot", "Rating"))
            self._last_id = dbid
            self._last_type = "tvshow"
            self._set_tvshow_details(dbid)
            self._handle_blur()
            return

        if cur_type == "season":
            self._set_listitem_properties("Season", ("Title",))
            self._last_id = dbid
            self._last_type = "season"
            self._set_season_details(dbid)
            self._handle_blur()
            return

        if cur_type == "episode":
            self._set_listitem_properties("Episode", ("Title", "Plot", "Rating"))
            self._last_id = dbid
            self._last_type = "episode"
            self._set_episode_details(dbid)
            self._handle_blur()
            return

        if cur_type == "musicvideo":
            self._set_listitem_properties("MusicVideo", ("Title", "Artist", "Year"))
            self._last_id = dbid
            self._last_type = "musicvideo"
            self._set_musicvideo_details(dbid)
            self._handle_blur()
            return

        if self._last_type in ("movie", "set", "artist", "album", "tvshow", "season", "episode", "musicvideo"):
            self._clear_media_type(self._last_type)
        self._last_id = dbid
        self._last_type = ""
        self._handle_blur()

    def _handle_blur(self) -> None:
        """Handle blur processing based on skin settings and properties."""
        import xbmcgui

        if not xbmc.getCondVisibility("Skin.HasSetting(SkinInfo.Blur)"):
            if self._last_blur_source is not None:
                clear_prop("SkinInfo.BlurredImage")
                clear_prop("SkinInfo.BlurredImage.Original")
                self._last_blur_source = None
            return

        blur_source_infolabel = xbmcgui.Window(10000).getProperty("SkinInfo.BlurSource")
        if not blur_source_infolabel:
            if self._last_blur_source is not None:
                clear_prop("SkinInfo.BlurredImage")
                clear_prop("SkinInfo.BlurredImage.Original")
                self._last_blur_source = None
            return

        source_path = xbmc.getInfoLabel(blur_source_infolabel)
        if not source_path:
            if self._last_blur_source is not None:
                clear_prop("SkinInfo.BlurredImage")
                clear_prop("SkinInfo.BlurredImage.Original")
                self._last_blur_source = None
            return

        if source_path == self._last_blur_source:
            return

        if self._blur_thread is not None and self._blur_thread.is_alive():
            return

        self._last_blur_source = source_path
        self._blur_thread = threading.Thread(
            target=self._blur_and_set_property,
            args=(source_path,),
            daemon=True
        )
        self._blur_thread.start()

    def _blur_and_set_property(self, source: str) -> None:
        """Background worker to blur image and set window properties."""
        try:
            from resources.lib import blur

            blur_radius_str = xbmc.getInfoLabel("Skin.String(SkinInfo.BlurRadius)") or "40"
            try:
                blur_radius = int(blur_radius_str)
                if blur_radius < 1:
                    blur_radius = 40
            except (ValueError, TypeError):
                blur_radius = 40

            blurred_path = blur.blur_image(source, blur_radius)

            if blurred_path:
                import xbmcgui
                set_prop("SkinInfo.BlurredImage", blurred_path)
                set_prop("SkinInfo.BlurredImage.Original", source)
            else:
                clear_prop("SkinInfo.BlurredImage")
                clear_prop("SkinInfo.BlurredImage.Original")

        except Exception as e:
            xbmc.log(f"SkinInfo: Failed to blur image: {e}", xbmc.LOGERROR)
            clear_prop("SkinInfo.BlurredImage")
            clear_prop("SkinInfo.BlurredImage.Original")
        finally:
            self._blur_thread = None

    def _set_movie_details(self, movieid: str) -> None:
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
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        set_movie_properties(details)
        set_ratings_properties(details, "Movie")

    def _set_movieset_details(self, setid: str) -> None:
        method, id_key, result_key = KODI_GET_DETAILS_METHODS['set']
        cached_full = get_cache_only(f"set:{setid}:details")
        if cached_full:
            details = extract_result(cached_full, result_key)
            if isinstance(details, dict):
                set_movieset_properties(details, details.get("movies") or [])
                return

        min_payload = {
            id_key: int(setid),
            "properties": ["title", "plot", "art"],
            "movies": {
                "properties": [
                    "title",
                    "year",
                    "runtime",
                    "thumbnail",
                    "art",
                    "file",
                ],
                "sort": {"method": "year", "order": "ascending"},
            },
        }

        min_resp = request(
            method,
            min_payload,
            cache_key=f"set:{setid}:min",
            ttl_seconds=CACHE_MOVIESET_TTL,
        )
        min_details = None
        if min_resp:
            min_details = extract_result(min_resp, result_key)
            if isinstance(min_details, dict):
                set_movieset_properties(min_details, min_details.get("movies") or [])

        cached_movies = get_cache_only(f"set:{setid}:movies")
        if cached_movies and min_resp and isinstance(min_details, dict):
            movies_list = extract_result(cached_movies, "movies")
            if isinstance(movies_list, list):
                set_movieset_properties(min_details, movies_list)

        def _fetch_movies_and_update(current_id: str, base_details: dict) -> None:
            movies_req = {
                "filter": {"setid": int(current_id)},
                "properties": [
                    "title", "year", "runtime", "genre", "director", "studio",
                    "country", "writer", "plot", "plotoutline", "mpaa", "file",
                    "streamdetails", "art", "thumbnail",
                ],
                "sort": {"method": "year", "order": "ascending"},
            }
            mresp = request(
                "VideoLibrary.GetMovies",
                movies_req,
                cache_key=f"set:{current_id}:movies",
                ttl_seconds=CACHE_MOVIESET_TTL,
            )
            if not mresp:
                return
            movies = extract_result(mresp, "movies")
            if not isinstance(movies, list):
                return
            if self._last_id == current_id and self._last_type == "set":
                set_movieset_properties(base_details, movies)

        if isinstance(min_details, dict):
            threading.Thread(target=_fetch_movies_and_update, args=(setid, min_details), daemon=True).start()

    def _set_artist_details(self, artistid: str) -> None:
        method, id_key, result_key = KODI_GET_DETAILS_METHODS['artist']
        ext_props = [
            "description", "genre", "art", "thumbnail", "fanart",
            "musicbrainzartistid", "born", "formed", "died", "disbanded",
            "yearsactive", "instrument", "style", "mood", "type", "gender",
            "disambiguation", "sortname", "dateadded", "roles", "songgenres",
            "sourceid", "datemodified", "datenew", "compilationartist", "isalbumartist"
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
            return

        artist = extract_result(resp, result_key)
        if not isinstance(artist, dict):
            return

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

        set_artist_properties(artist, albums)

    def _set_album_details(self, albumid: str) -> None:
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
                    "properties": [
                        "title", "art", "year", "artist", "genre", "albumlabel", "playcount", "rating",
                    ],
                },
                cache_key=f"album:{albumid}:details:min",
            )
        if not resp:
            return

        album = extract_result(resp, result_key)
        if not isinstance(album, dict):
            return

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

        set_album_properties(album, songs)

    def _set_tvshow_details(self, tvshowid: str) -> None:
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
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        set_tvshow_properties(details)
        set_ratings_properties(details, "TVShow")

    def _set_season_details(self, seasonid: str) -> None:
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
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        set_season_properties(details)

    def _set_episode_details(self, episodeid: str) -> None:
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
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        set_episode_properties(details)
        set_ratings_properties(details, "Episode")

    def _set_musicvideo_details(self, musicvideoid: str) -> None:
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
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        set_musicvideo_properties(details)


def start_service() -> None:
    thread = SkinInfoService()
    thread.start()
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            thread.abort.set()
            break
    thread.join(timeout=2)


if __name__ == "__main__":
    start_service()
