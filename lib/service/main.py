"""SkinInfo background service for property updates.

Monitors ListItem changes and updates window properties with detailed media information
for Movies, TV shows, Music, and more.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lib.service.music import MusicOnlineResult
import xbmc
import xbmcgui

from lib.kodi.client import request, get_cache_only, extract_result, get_item_details, KODI_MOVIE_PROPERTIES, log, ADDON, decode_image_url
from lib.service.properties import (
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
from lib.service.stinger import StingerMonitor, get_settings as get_stinger_settings
from lib.kodi.utils import clear_group, set_prop, get_prop, clear_prop, extract_media_ids, wait_for_kodi_ready, batch_set_props

SERVICE_POLL_INTERVAL = 0.10
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
    "musicvideo_artist": "SkinInfo.MusicVideo.",
    "musicvideo_album": "SkinInfo.MusicVideo.",
    "player": "SkinInfo.Player.",
}


class LibraryMonitor(xbmc.Monitor):
    """Monitor for library update notifications to trigger widget refresh."""

    def __init__(self, service_main):
        super().__init__()
        self.service_main = service_main

    def onNotification(self, sender: str, method: str, data: str) -> None:
        """Handle Kodi notifications for library updates."""
        if method in ('VideoLibrary.OnUpdate', 'VideoLibrary.OnScanFinished'):
            self.service_main._increment_library_refresh()
        if method in ('AudioLibrary.OnUpdate', 'AudioLibrary.OnScanFinished',
                       'AudioLibrary.OnCleanFinished'):
            from lib.plugin.dbid import clear_musicvideo_library_art_cache
            clear_musicvideo_library_art_cache()


IMDB_CHECK_INTERVAL = 86400  # 24 hours in seconds


class ServiceMain(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()
        self._last_id = None
        self._last_type = None
        self._last_player_id = None
        self._last_player_type = None
        self._blur_thread = None
        self._last_blur_source = None
        self._blur_player_thread = None
        self._last_blur_player_source = None
        self._slideshow_last_update = 0.0
        self._slideshow_pool_populated = False
        self._library_refresh_counter = 0
        self._refresh_timers = {5: 0, 10: 0, 15: 0, 20: 0, 30: 0, 45: 0, 60: 0}
        self._refresh_start_time = None
        self._last_music_artist: Optional[str] = None
        self._musicvideo_online_thread: Optional[threading.Thread] = None
        self._musicvideo_online_key: Optional[str] = None

    def _increment_library_refresh(self) -> None:
        """Increment library refresh counter to trigger widget/path stats refresh."""
        self._library_refresh_counter += 1
        set_prop("SkinInfo.Library.Refreshed", str(self._library_refresh_counter))
        log("Service",f"Library refresh counter incremented to {self._library_refresh_counter}", xbmc.LOGDEBUG)

    def _update_scheduled_refresh(self) -> None:
        """Update scheduled refresh properties based on elapsed time."""
        if self._refresh_start_time is None:
            self._refresh_start_time = time.time()
            for interval in self._refresh_timers:
                set_prop(f"SkinInfo.Refresh.{interval}min", "0")
            return

        elapsed_minutes = int((time.time() - self._refresh_start_time) / 60)

        for interval in self._refresh_timers:
            intervals_passed = elapsed_minutes // interval
            if intervals_passed > self._refresh_timers[interval]:
                self._refresh_timers[interval] = intervals_passed
                set_prop(f"SkinInfo.Refresh.{interval}min", str(intervals_passed))

    def _clear_media_type(self, media_type: str) -> None:
        prefix = _MEDIA_TYPE_PREFIXES.get(media_type)
        if prefix:
            clear_group(prefix)
        if media_type == "season":
            clear_group(_MEDIA_TYPE_PREFIXES["tvshow"])
        if media_type in ("musicvideo", "musicvideo_artist"):
            self._musicvideo_online_key = None

    def run(self) -> None:
        monitor = LibraryMonitor(self)
        if not wait_for_kodi_ready(monitor):
            return

        log("Service", "Library service started", xbmc.LOGINFO)

        try:
            xbmc.executebuiltin('Skin.SetBool(SkinInfo.Service)')
            set_prop("SkinInfo.Service.Running", "true")
        except Exception as e:
            log("Service", f"Error setting service flags: {e}", xbmc.LOGWARNING)

        self._populate_slideshow_pool_if_needed()

        if xbmc.getCondVisibility('Skin.HasSetting(SkinInfo.EnableSlideshow)'):
            try:
                from lib.service.slideshow import update_all_slideshow_properties
                update_all_slideshow_properties()
                self._slideshow_last_update = time.time()
            except Exception as e:
                log("Service",f"Slideshow: Initial update error: {str(e)}", xbmc.LOGERROR)

        consecutive_errors = 0

        try:
            while not monitor.waitForAbort(SERVICE_POLL_INTERVAL):
                if self.abort.is_set():
                    break
                if not xbmc.getCondVisibility('Skin.HasSetting(SkinInfo.Service)'):
                    log("Service", "SkinInfo.Service disabled, stopping", xbmc.LOGINFO)
                    break
                try:
                    self._loop()
                    self._slideshow_update()
                    self._update_scheduled_refresh()
                    consecutive_errors = 0
                except (KeyError, ValueError, TypeError) as e:
                    log("Service", f"Data error in service loop: {e}", xbmc.LOGDEBUG)
                    consecutive_errors += 1
                except Exception as e:
                    import traceback
                    log("Service",f" Unexpected error in service loop: {str(e)}", xbmc.LOGERROR)
                    log("Service", traceback.format_exc(), xbmc.LOGERROR)
                    consecutive_errors += 1

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log("Service",f" Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}), stopping service", xbmc.LOGERROR)
                    break
        finally:
            try:
                clear_prop("SkinInfo.Service.Running")
            except Exception:
                pass
            log("Service", "Library service stopped", xbmc.LOGINFO)

    def _loop(self) -> None:
        self._handle_blur_player()
        self._handle_player()
        self._handle_music_player()

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

        mv_mediatype = ""
        if dbtype in ("actor", "album"):
            mv_mediatype = xbmc.getInfoLabel("ListItem.Property(musicvideomediatype)")

        if dbtype == "actor" and mv_mediatype == "artist":
            cur_type = "musicvideo_artist"
        elif dbtype == "album" and mv_mediatype == "album":
            cur_type = "musicvideo_album"
        elif dbtype in ("set", "movie", "artist", "album", "tvshow", "season", "episode", "musicvideo"):
            cur_type = dbtype
        elif dbid == self._last_id and self._last_type:
            cur_type = self._last_type
        else:
            is_set = xbmc.getCondVisibility(
                "ListItem.IsCollection | String.IsEqual(ListItem.DBType,set)"
            )
            if is_set or xbmc.getCondVisibility("Container.Content(sets)"):
                cur_type = "set"
            elif xbmc.getCondVisibility("Container.Content(movies)"):
                cur_type = "movie"
            elif xbmc.getCondVisibility("Container.Content(artists)"):
                cur_type = "artist"
            elif xbmc.getCondVisibility("Container.Content(albums)"):
                cur_type = "album"
            elif xbmc.getCondVisibility("Container.Content(tvshows)"):
                cur_type = "tvshow"
            elif xbmc.getCondVisibility("Container.Content(seasons)"):
                cur_type = "season"
            elif xbmc.getCondVisibility("Container.Content(episodes)"):
                cur_type = "episode"
            elif xbmc.getCondVisibility("Container.Content(musicvideos)"):
                cur_type = "musicvideo"
            else:
                cur_type = ""

        if self._last_id and dbid != self._last_id:
            if self._last_type and self._last_type != cur_type:
                self._clear_media_type(self._last_type)
            self._last_type = ""

        if dbid == self._last_id and cur_type == self._last_type:
            self._handle_blur()
            return

        if cur_type == "set":
            self._last_id = dbid
            self._last_type = "set"
            self._set_movieset_details(dbid)
            self._handle_blur()
            return

        if cur_type == "movie":
            self._last_id = dbid
            self._last_type = "movie"
            self._set_movie_details(dbid)
            self._handle_blur()
            return

        if cur_type == "artist":
            if self._last_type != "artist":
                self._clear_media_type("album")
            self._last_id = dbid
            self._last_type = "artist"
            self._set_artist_details(dbid)
            self._handle_blur()
            return

        if cur_type == "album":
            if self._last_type != "album":
                self._clear_media_type("artist")
            self._last_id = dbid
            self._last_type = "album"
            self._set_album_details(dbid)
            self._handle_blur()
            return

        if cur_type == "tvshow":
            self._last_id = dbid
            self._last_type = "tvshow"
            self._set_tvshow_details(dbid)
            self._handle_blur()
            return

        if cur_type == "season":
            self._last_id = dbid
            self._last_type = "season"
            self._set_season_details(dbid)
            self._handle_blur()
            return

        if cur_type == "episode":
            self._last_id = dbid
            self._last_type = "episode"
            self._set_episode_details(dbid)
            self._handle_blur()
            return

        if cur_type == "musicvideo_artist":
            self._last_id = dbid
            self._last_type = "musicvideo_artist"
            self._set_musicvideo_artist_node()
            self._handle_blur()
            return

        if cur_type == "musicvideo_album":
            self._last_id = dbid
            self._last_type = "musicvideo_album"
            self._set_musicvideo_album_node()
            self._handle_blur()
            return

        if cur_type == "musicvideo":
            self._last_id = dbid
            self._last_type = "musicvideo"
            self._set_musicvideo_details(dbid)
            self._handle_blur()
            return

        if self._last_type in ("movie", "set", "artist", "album", "tvshow", "season", "episode", "musicvideo", "musicvideo_artist", "musicvideo_album"):
            self._clear_media_type(self._last_type)
        self._last_id = dbid
        self._last_type = ""
        self._handle_blur()

    def _handle_player(self) -> None:
        """Monitor currently playing video and set Player properties."""
        if not xbmc.getCondVisibility("Player.HasVideo"):
            if self._last_player_id:
                self._clear_media_type("player")
                self._last_player_id = None
                self._last_player_type = None
            return

        player_dbid = xbmc.getInfoLabel("VideoPlayer.DBID") or ""
        if not player_dbid:
            if self._last_player_id:
                self._clear_media_type("player")
                self._last_player_id = None
                self._last_player_type = None
            return

        is_movie = xbmc.getCondVisibility("VideoPlayer.Content(movies)")
        is_episode = xbmc.getCondVisibility("VideoPlayer.Content(episodes)")
        is_musicvideo = xbmc.getCondVisibility("VideoPlayer.Content(musicvideos)")

        if is_movie:
            player_type = "movie"
        elif is_episode:
            player_type = "episode"
        elif is_musicvideo:
            player_type = "musicvideo"
        else:
            return

        if player_dbid == self._last_player_id and player_type == self._last_player_type:
            return

        self._last_player_id = player_dbid
        self._last_player_type = player_type

        if player_type == "movie":
            self._set_player_movie_details(player_dbid)
        elif player_type == "episode":
            self._set_player_episode_details(player_dbid)
        elif player_type == "musicvideo":
            self._set_player_musicvideo_details(player_dbid)

    def _set_player_movie_details(self, movieid: str) -> None:
        """Fetch and set Player properties for currently playing movie."""
        details = get_item_details(
            'movie',
            int(movieid),
            KODI_MOVIE_PROPERTIES,
            cache_key=f"player:movie:{movieid}:details",
        )
        if not isinstance(details, dict):
            return

        set_ratings_properties(details, "Player")

    def _set_player_episode_details(self, episodeid: str) -> None:
        """Fetch and set Player properties for currently playing episode."""
        details = get_item_details(
            'episode',
            int(episodeid),
            ["title", "ratings", "tvshowid", "season", "episode", "showtitle"],
            cache_key=f"player:episode:{episodeid}:details",
        )
        if not isinstance(details, dict):
            return

        set_ratings_properties(details, "Player")

        # Also fetch parent TV show details for status, next aired, etc.
        tvshowid = details.get("tvshowid")
        if tvshowid and tvshowid != -1:
            self._set_player_tvshow_details(str(tvshowid))

    def _set_player_tvshow_details(self, tvshowid: str) -> None:
        """Fetch and set Player.TVShow properties for parent TV show."""
        details = get_item_details(
            'tvshow',
            int(tvshowid),
            [
                "title", "plot", "year", "premiered", "rating", "votes",
                "genre", "studio", "mpaa", "runtime", "episode", "season",
                "watchedepisodes", "imdbnumber", "originaltitle",
                "art", "userrating", "ratings", "status",
            ],
            cache_key=f"player:tvshow:{tvshowid}:details",
        )
        if not isinstance(details, dict):
            return

        # Set TV show properties with Player.TVShow prefix
        from lib.service.properties import build_tvshow_data, batch_set_props
        data = build_tvshow_data(details)
        props = {f"SkinInfo.Player.TVShow.{k}": v for k, v in data.items() if not k.startswith("_")}
        batch_set_props(props)

        # Set TV show ratings with Player.TVShow prefix
        set_ratings_properties(details, "Player.TVShow")

    def _set_player_musicvideo_details(self, musicvideoid: str) -> None:
        """Fetch and set Player.MusicVideo properties for currently playing music video."""
        details = get_item_details(
            'musicvideo',
            int(musicvideoid),
            [
                "title", "artist", "album", "genre", "year", "plot", "runtime",
                "director", "studio", "file", "streamdetails", "art", "premiered",
                "tag", "playcount", "lastplayed", "resume", "dateadded",
                "rating", "userrating", "uniqueid", "track",
            ],
            cache_key=f"player:musicvideo:{musicvideoid}:details",
        )
        if not isinstance(details, dict):
            return

        from lib.service.properties import build_musicvideo_data
        data = build_musicvideo_data(details)
        props = {f"SkinInfo.Player.MusicVideo.{k}": v for k, v in data.items() if not k.startswith("_")}
        batch_set_props(props)

        self._set_musicvideo_library_art(details, prefix="SkinInfo.Player.MusicVideo.")

    def _handle_music_player(self) -> None:
        if not xbmc.getCondVisibility("Player.HasAudio"):
            if self._last_music_artist:
                clear_group("SkinInfo.Player.Music.")
                self._last_music_artist = None
            return

        artist_name = xbmc.getInfoLabel("MusicPlayer.Artist") or ""
        if not artist_name:
            if self._last_music_artist:
                clear_group("SkinInfo.Player.Music.")
                self._last_music_artist = None
            return

        if artist_name == self._last_music_artist:
            return

        clear_group("SkinInfo.Player.Music.")
        self._last_music_artist = artist_name
        self._set_music_player_details(artist_name)

    def _set_music_player_details(self, artist_name: str) -> None:

        artists = [a.strip() for a in artist_name.split(" / ")]
        bio = ""
        library_fanart = ""
        all_albums: List[dict] = []

        for name in artists:
            if not name:
                continue

            result = request("AudioLibrary.GetArtists", {
                "filter": {"field": "artist", "operator": "is", "value": name},
                "properties": ["description", "fanart"],
                "limits": {"end": 1},
            })

            if not result:
                continue

            artists_list = result.get("result", {}).get("artists")
            if not artists_list:
                continue

            artist = artists_list[0]
            artist_id = artist.get("artistid")

            if not bio:
                bio = artist.get("description", "") or ""

            if not library_fanart:
                library_fanart = decode_image_url(artist.get("fanart", "") or "")

            if artist_id:
                albums_result = request("AudioLibrary.GetAlbums", {
                    "filter": {"artistid": artist_id},
                    "properties": ["title", "year", "art"],
                    "sort": {"method": "year", "order": "ascending"},
                })
                if albums_result:
                    album_list = albums_result.get("result", {}).get("albums")
                    if isinstance(album_list, list):
                        all_albums.extend(album_list)

        prefix = "SkinInfo.Player.Music."
        props: Dict[str, Optional[str]] = {
            f"{prefix}Artist": artist_name,
            f"{prefix}Bio": bio,
            f"{prefix}FanArt": library_fanart,
        }

        album_count = min(len(all_albums), 20)
        props[f"{prefix}Album.Count"] = str(album_count)

        for i, album in enumerate(all_albums[:20]):
            props[f"{prefix}Album.{i + 1}.Title"] = album.get('title', '')
            year = album.get('year')
            props[f"{prefix}Album.{i + 1}.Year"] = str(year) if year else ''
            props[f"{prefix}Album.{i + 1}.Thumb"] = decode_image_url(album.get('art', {}).get('thumb', ''))

        batch_set_props(props)

    def _clear_blur_props(self, prop_base: str) -> None:
        """Clear blur properties for a given property base."""
        clear_prop(f"{prop_base}BlurredImage")
        clear_prop(f"{prop_base}BlurredImage.Original")

    def _resolve_blur_source_with_fallbacks(self, sources: List[str], is_var: bool) -> str:
        """Resolve blur source with pipe-separated fallbacks.

        Args:
            sources: List of source names (split by |)
            is_var: True if sources are VAR names, False if raw InfoLabels

        Returns:
            First non-empty resolved path, or empty string if all fail
        """
        for source in sources:
            source = source.strip()
            if not source:
                continue

            if is_var:
                resolved = xbmc.getInfoLabel(f"$VAR[{source}]")
            else:
                resolved = xbmc.getInfoLabel(source)

            if resolved:
                return resolved

        return ""

    def _process_blur_generic(
        self,
        setting_check: str,
        source_property: str,
        last_source_attr: str,
        thread_attr: str,
        worker_callback,
        prop_base: str,
        cache_key_suffix: str = ""
    ) -> None:
        """Generic blur processing handler.

        Args:
            setting_check: Skin setting condition to check
            source_property: Window property name for blur source
            last_source_attr: Name of instance attribute tracking last source
            thread_attr: Name of instance attribute for blur thread
            worker_callback: Worker function to call in background thread
            prop_base: Property base for setting properties
            cache_key_suffix: Optional suffix for cache key (e.g., player file path)
        """
        if not xbmc.getCondVisibility(setting_check):
            if getattr(self, last_source_attr) is not None:
                self._clear_blur_props(prop_base)
                setattr(self, last_source_attr, None)
            return

        blur_source_var = xbmcgui.Window(10000).getProperty(source_property + "Var")
        if blur_source_var:
            source_path = self._resolve_blur_source_with_fallbacks(
                blur_source_var.split("|"),
                is_var=True
            )
        else:
            blur_source_infolabel = xbmcgui.Window(10000).getProperty(source_property)
            if not blur_source_infolabel:
                if getattr(self, last_source_attr) is not None:
                    self._clear_blur_props(prop_base)
                    setattr(self, last_source_attr, None)
                return

            if blur_source_infolabel.startswith('$'):
                log("Blur",
                    f"{source_property} should not contain $INFO[], $VAR[], etc. "
                    f"Set raw infolabel instead. Got: {blur_source_infolabel}",
                    xbmc.LOGWARNING
                )

            source_path = self._resolve_blur_source_with_fallbacks(
                blur_source_infolabel.split("|"),
                is_var=False
            )
        if not source_path:
            if getattr(self, last_source_attr) is not None:
                self._clear_blur_props(prop_base)
                setattr(self, last_source_attr, None)
            return

        cache_key = f"{source_path}{cache_key_suffix}"
        if cache_key == getattr(self, last_source_attr):
            return

        thread = getattr(self, thread_attr)
        if thread is not None and thread.is_alive():
            return

        setattr(self, last_source_attr, cache_key)
        new_thread = threading.Thread(
            target=worker_callback,
            args=(source_path, prop_base),
            daemon=True
        )
        setattr(self, thread_attr, new_thread)
        new_thread.start()

    def _blur_worker(self, source: str, prop_base: str, thread_attr: str) -> None:
        """Background worker to blur image and set window properties.

        Args:
            source: Source image path
            prop_base: Property base for setting properties
            thread_attr: Name of instance attribute for blur thread
        """
        try:
            from lib.service import blur

            blur_radius_str = xbmc.getInfoLabel("Skin.String(SkinInfo.BlurRadius)") or "40"
            try:
                blur_radius = int(blur_radius_str)
                if blur_radius < 1:
                    blur_radius = 40
            except (ValueError, TypeError):
                blur_radius = 40

            blurred_path = blur.blur_image(source, blur_radius)

            if blurred_path:
                set_prop(f"{prop_base}BlurredImage", blurred_path)
                set_prop(f"{prop_base}BlurredImage.Original", source)
            else:
                self._clear_blur_props(prop_base)

        except Exception as e:
            log("Blur", f"Failed to blur image: {e}", xbmc.LOGERROR)
            self._clear_blur_props(prop_base)
            # Allow retry after failure
            if thread_attr == "_blur_thread":
                self._last_blur_source = None
            elif thread_attr == "_blur_player_thread":
                self._last_blur_player_source = None
        finally:
            setattr(self, thread_attr, None)

    def _handle_blur(self) -> None:
        """Handle blur processing based on skin settings and properties."""
        if not xbmc.getCondVisibility("Skin.HasSetting(SkinInfo.Blur)"):
            if self._last_blur_source is not None:
                self._clear_blur_props("SkinInfo.")
                self._last_blur_source = None
            return

        prefix = xbmcgui.Window(10000).getProperty("SkinInfo.BlurPrefix") or ""
        prop_base = f"SkinInfo.{prefix}." if prefix else "SkinInfo."

        self._process_blur_generic(
            setting_check="Skin.HasSetting(SkinInfo.Blur)",
            source_property="SkinInfo.BlurSource",
            last_source_attr="_last_blur_source",
            thread_attr="_blur_thread",
            worker_callback=lambda src, pb: self._blur_worker(src, pb, "_blur_thread"),
            prop_base=prop_base
        )

    def _handle_blur_player(self) -> None:
        """Handle player blur processing for audio playback."""
        if not xbmc.getCondVisibility("Player.HasAudio"):
            if self._last_blur_player_source is not None:
                self._clear_blur_props("SkinInfo.Player.")
                self._last_blur_player_source = None
            return

        current_file = xbmc.getInfoLabel("Player.Filenameandpath")

        self._process_blur_generic(
            setting_check="Skin.HasSetting(SkinInfo.Player.Blur)",
            source_property="SkinInfo.Player.BlurSource",
            last_source_attr="_last_blur_player_source",
            thread_attr="_blur_player_thread",
            worker_callback=lambda src, pb: self._blur_worker(src, pb, "_blur_player_thread"),
            prop_base="SkinInfo.Player.",
            cache_key_suffix=f"|{current_file}"
        )

    def _set_movie_details(self, movieid: str) -> None:
        details = get_item_details(
            'movie',
            int(movieid),
            KODI_MOVIE_PROPERTIES,
            cache_key=f"movie:{movieid}:details",
        )
        if not isinstance(details, dict):
            return

        set_movie_properties(details)
        set_ratings_properties(details, "Movie")

    def _set_movieset_details(self, setid: str) -> None:
        cached_full = get_cache_only(f"set:{setid}:details")
        if cached_full:
            details = extract_result(cached_full, "setdetails")
            if isinstance(details, dict):
                set_movieset_properties(details, details.get("movies") or [])
                return

        min_details = get_item_details(
            'set',
            int(setid),
            ["title", "plot", "art"],
            cache_key=f"set:{setid}:min",
            ttl_seconds=CACHE_MOVIESET_TTL,
            movies={
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
        )
        if isinstance(min_details, dict):
            set_movieset_properties(min_details, min_details.get("movies") or [])

        cached_movies = get_cache_only(f"set:{setid}:movies")
        if cached_movies and min_details and isinstance(min_details, dict):
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
        ext_props = [
            "description", "genre", "art", "thumbnail", "fanart",
            "musicbrainzartistid", "born", "formed", "died", "disbanded",
            "yearsactive", "instrument", "style", "mood", "type", "gender",
            "disambiguation", "sortname", "dateadded", "roles", "songgenres",
            "sourceid", "datemodified", "datenew", "compilationartist", "isalbumartist"
        ]
        artist = get_item_details(
            'artist',
            int(artistid),
            ext_props,
            cache_key=f"artist:{artistid}:details",
        )
        if not artist:
            artist = get_item_details(
                'artist',
                int(artistid),
                ["genre", "art", "thumbnail", "fanart", "description"],
                cache_key=f"artist:{artistid}:details:min",
            )
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
        ext_props = [
            "title", "art", "year", "artist", "artistid", "genre",
            "style", "mood", "type", "albumlabel", "playcount", "rating", "userrating",
            "musicbrainzalbumid", "musicbrainzreleasegroupid", "lastplayed", "dateadded",
            "description", "votes", "displayartist", "compilation", "releasetype",
            "sortartist", "songgenres", "totaldiscs", "releasedate", "originaldate", "albumduration",
        ]
        album = get_item_details(
            'album',
            int(albumid),
            ext_props,
            cache_key=f"album:{albumid}:details",
        )
        if not album:
            album = get_item_details(
                'album',
                int(albumid),
                [
                    "title", "art", "year", "artist", "genre", "albumlabel", "playcount", "rating",
                ],
                cache_key=f"album:{albumid}:details:min",
            )
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
        details = get_item_details(
            'tvshow',
            int(tvshowid),
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
            return

        set_tvshow_properties(details)
        set_ratings_properties(details, "TVShow")

    def _set_season_details(self, seasonid: str) -> None:
        details = get_item_details(
            'season',
            int(seasonid),
            [
                "season", "showtitle", "playcount", "episode",
                "tvshowid", "watchedepisodes", "art", "userrating", "title",
            ],
            cache_key=f"season:{seasonid}:details",
        )
        if not isinstance(details, dict):
            return

        set_season_properties(details)

        tvshowid = details.get("tvshowid")
        if tvshowid and tvshowid != -1:
            self._set_tvshow_details(str(tvshowid))

    def _set_episode_details(self, episodeid: str) -> None:
        details = get_item_details(
            'episode',
            int(episodeid),
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
            return

        set_episode_properties(details)
        set_ratings_properties(details, "Episode")

    def _set_musicvideo_artist_node(self) -> None:
        artist_name = xbmc.getInfoLabel("ListItem.Label") or ""
        if not artist_name:
            return

        details: dict = {"artist": [artist_name], "album": ""}
        self._set_musicvideo_art(details)

    def _set_musicvideo_album_node(self) -> None:
        album_name = xbmc.getInfoLabel("ListItem.Label") or ""
        if not album_name:
            return

        artist_name = xbmc.getInfoLabel("ListItem.Artist") or ""
        details: dict = {
            "artist": [artist_name] if artist_name else [],
            "album": album_name,
        }
        self._set_musicvideo_library_art(details)

    def _set_musicvideo_details(self, musicvideoid: str) -> None:
        details = get_item_details(
            'musicvideo',
            int(musicvideoid),
            [
                "title", "artist", "album", "genre", "year", "plot", "runtime",
                "director", "studio", "file", "streamdetails", "art", "premiered",
                "tag", "playcount",
                "lastplayed", "resume", "dateadded", "rating", "userrating", "uniqueid", "track",
            ],
            cache_key=f"musicvideo:{musicvideoid}:details",
        )
        if not isinstance(details, dict):
            return

        set_musicvideo_properties(details)
        self._set_musicvideo_art(details)

    _LIBRARY_ART_KEYS = ("Artist.Fanart", "Artist.Thumb", "Artist.Clearlogo", "Artist.Banner", "Album.Thumb")
    _ONLINE_ART_KEYS = (
        "Online.Artist.Bio", "Online.Artist.FanArt", "Online.Artist.FanArt.Count",
        "Online.Artist.Thumb", "Online.Artist.Clearlogo", "Online.Artist.Banner",
        "Online.Track.Wiki", "Online.Track.Tags", "Online.Track.Listeners",
        "Online.Track.Playcount", "Online.Album.Wiki", "Online.Album.Tags",
        "Online.Album.Label",
    )

    def _set_musicvideo_art(self, details: dict, prefix: str = "SkinInfo.MusicVideo.") -> None:
        """Set library art + online art in a single batch to prevent stale fallthrough."""
        from lib.plugin.dbid import get_musicvideo_artist_art
        from lib.service.properties import _join

        props: Dict[str, Optional[str]] = {
            f"{prefix}{k}": "" for k in self._ONLINE_ART_KEYS
        }

        artist_art, artist_id = get_musicvideo_artist_art(details)
        artist_keys = ("Artist.Fanart", "Artist.Thumb", "Artist.Clearlogo", "Artist.Banner")
        for k in artist_keys:
            props[f"{prefix}{k}"] = artist_art.get(k, "")

        artist_name = _join(details.get("artist"))
        cache_hit = False
        if artist_name:
            album = details.get("album") or None
            title = details.get("title") or None
            cache_key = artist_name

            if cache_key == self._musicvideo_online_key:
                for k in self._ONLINE_ART_KEYS:
                    props.pop(f"{prefix}{k}", None)
                cache_hit = True
            else:
                self._musicvideo_online_key = cache_key
                from lib.service.music import try_cached_artist_online_data
                cached = try_cached_artist_online_data(artist_name)
                if cached:
                    cache_hit = True
                    self._fill_online_props(props, cached, artist_name, title, album, prefix)

        batch_set_props(props)

        # Deferred: album thumb (background thread, not in critical path)
        self._defer_musicvideo_album_thumb(details, artist_id, prefix)

        # Cache miss — spawn async worker to fetch online data
        if artist_name and not cache_hit:
            album = details.get("album") or None
            title = details.get("title") or None
            if not (self._musicvideo_online_thread
                    and self._musicvideo_online_thread.is_alive()):
                self._musicvideo_online_thread = threading.Thread(
                    target=self._musicvideo_online_worker,
                    args=(artist_name, album, title),
                    daemon=True,
                )
                self._musicvideo_online_thread.start()

    def _set_musicvideo_library_art(self, details: dict, prefix: str = "SkinInfo.MusicVideo.") -> None:
        """Set library artist art only (for player/node contexts without online)."""
        from lib.plugin.dbid import get_musicvideo_artist_art

        artist_art, artist_id = get_musicvideo_artist_art(details)
        artist_keys = ("Artist.Fanart", "Artist.Thumb", "Artist.Clearlogo", "Artist.Banner")
        props: dict = {f"{prefix}{k}": artist_art.get(k, "") for k in artist_keys}
        batch_set_props(props)
        self._defer_musicvideo_album_thumb(details, artist_id, prefix)

    def _fill_online_props(
        self,
        props: Dict[str, Optional[str]],
        result: "MusicOnlineResult",
        artist_name: str,
        title: Optional[str],
        album: Optional[str],
        prefix: str,
    ) -> None:
        """Fill online artist/track/album props into an existing props dict."""
        from lib.service.music import (
            fetch_track_online_data,
            fetch_album_online_data,
            extract_track_properties,
            extract_album_properties,
        )

        ap = f"{prefix}Online.Artist."
        props[f"{ap}Bio"] = result.bio or ""
        props[f"{ap}FanArt.Count"] = str(len(result.fanart_urls))
        props[f"{ap}FanArt"] = result.fanart_urls[0] if result.fanart_urls else ""
        for art_type in ('thumb', 'clearlogo', 'banner'):
            key = art_type[0].upper() + art_type[1:]
            props[f"{ap}{key}"] = result.artist_art.get(art_type, '')

        mp = f"{prefix}Online."
        if title:
            fetch_track_online_data(artist_name, title)
            track_props = extract_track_properties(artist_name, title)
            if track_props:
                for k, v in track_props.items():
                    props[f"{mp}Track.{k}"] = v

        if album:
            fetch_album_online_data(artist_name, album)
            album_props = extract_album_properties(artist_name, album)
            if album_props:
                for k, v in album_props.items():
                    props[f"{mp}Album.{k}"] = v

    def _defer_musicvideo_album_thumb(self, details: dict, artist_id: object, prefix: str) -> None:
        """Fetch album thumb in background thread to keep critical path fast."""
        def _worker() -> None:
            try:
                from lib.plugin.dbid import get_musicvideo_album_art
                album_thumb = get_musicvideo_album_art(details, artist_id)
                props: Dict[str, Optional[str]] = {f"{prefix}Album.Thumb": album_thumb}
                batch_set_props(props)
            except Exception as e:
                log("Service", f"Deferred album thumb error: {e}", xbmc.LOGWARNING)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _musicvideo_online_worker(
        self, artist_name: str, album: Optional[str], title: Optional[str]
    ) -> None:
        try:
            from lib.service.music import fetch_artist_online_data

            result = fetch_artist_online_data(
                artist_name, album=album, track=title
            )

            if artist_name != self._musicvideo_online_key:
                return

            if not result:
                return

            prefix = "SkinInfo.MusicVideo."
            props: Dict[str, Optional[str]] = {
                f"{prefix}{k}": "" for k in self._ONLINE_ART_KEYS
            }
            self._fill_online_props(props, result, artist_name, title, album, prefix)
            batch_set_props(props)

        except Exception as e:
            log("Service", f"Music video online artist fetch error: {e}", xbmc.LOGWARNING)

    def _populate_slideshow_pool_if_needed(self) -> None:
        """Populate slideshow pool on first run if empty."""
        if self._slideshow_pool_populated:
            return

        try:
            from lib.service.slideshow import is_pool_populated, populate_slideshow_pool

            if not is_pool_populated():
                log("Service", "Slideshow: Populating pool for first time...", xbmc.LOGINFO)
                populate_slideshow_pool()
                log("Service", "Slideshow: Pool population complete", xbmc.LOGINFO)

            self._slideshow_pool_populated = True
        except Exception as e:
            log("Service",f"Slideshow: Error populating pool: {str(e)}", xbmc.LOGERROR)

    def _slideshow_update(self) -> None:
        """Update slideshow properties if enabled and interval elapsed."""
        if not xbmc.getCondVisibility('Skin.HasSetting(SkinInfo.EnableSlideshow)'):
            return

        interval_str = xbmc.getInfoLabel('Skin.String(SkinInfo.SlideshowRefreshInterval)') or '10'
        try:
            from lib.service.slideshow import MIN_SLIDESHOW_INTERVAL, MAX_SLIDESHOW_INTERVAL
            interval = int(interval_str)
            interval = max(MIN_SLIDESHOW_INTERVAL, min(interval, MAX_SLIDESHOW_INTERVAL))
        except ValueError:
            interval = 10

        now = time.time()
        elapsed = now - self._slideshow_last_update

        if elapsed < interval:
            return

        try:
            from lib.service.slideshow import update_all_slideshow_properties
            update_all_slideshow_properties()
            self._slideshow_last_update = time.time()

        except Exception as e:
            log("Service",f"Slideshow: Update error: {str(e)}", xbmc.LOGERROR)


class ImdbUpdateMonitor(xbmc.Monitor):
    """Monitor for library scan notifications to trigger IMDb dataset refresh."""

    def __init__(self, service: 'ImdbUpdateService'):
        super().__init__()
        self._service = service

    def onNotification(self, sender: str, method: str, data: str) -> None:  # noqa: ARG002
        if method == 'VideoLibrary.OnScanFinished':
            self._service._on_library_scan_finished()


class ImdbUpdateService(threading.Thread):
    """Independent service thread for automatic IMDb rating updates.

    Runs independently of the main SkinInfo service, gated only by
    the imdb_auto_update setting. Handles both periodic dataset checks
    and library-scan-triggered updates.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()
        self._last_check = time.time()
        self._update_lock = threading.Lock()

    def run(self) -> None:
        monitor = ImdbUpdateMonitor(self)
        if not wait_for_kodi_ready(monitor):
            return

        log("Service", "IMDb auto-update service started", xbmc.LOGINFO)

        while not monitor.waitForAbort(10):
            if self.abort.is_set():
                break

            setting = ADDON.getSetting("imdb_auto_update")
            if setting in ("when_updated", "both"):
                now = time.time()
                if (now - self._last_check) >= IMDB_CHECK_INTERVAL:
                    self._last_check = now
                    self._run_update(monitor)

        log("Service", "IMDb auto-update service stopped", xbmc.LOGINFO)

    def _on_library_scan_finished(self) -> None:
        setting = ADDON.getSetting("imdb_auto_update")
        if setting in ("library_scan", "both"):
            threading.Thread(
                target=self._run_update,
                args=(xbmc.Monitor(),),
                daemon=True,
            ).start()

    def _run_update(self, monitor: xbmc.Monitor) -> None:
        if not self._update_lock.acquire(blocking=False):
            log("Service", "IMDb update already in progress, skipping", xbmc.LOGDEBUG)
            return
        try:
            from lib.data.api.imdb import get_imdb_dataset
            from lib.data.database import workflow as db

            dataset = get_imdb_dataset()
            dataset.refresh_if_stale()

            if db.get_synced_items_count() == 0:
                self._run_full_update()
            else:
                self._run_incremental(monitor)
        except Exception as e:
            log("Service", f"IMDb update failed: {e}", xbmc.LOGWARNING)
        finally:
            self._update_lock.release()

    def _run_incremental(self, monitor: xbmc.Monitor) -> None:
        from lib.rating.updater import update_changed_imdb_ratings

        stats = update_changed_imdb_ratings(monitor=monitor)
        updated = stats.get("updated", 0)
        if updated > 0:
            self._notify_when_idle(
                ADDON.getLocalizedString(32300),
                f"{updated} ratings updated",
                monitor,
            )

    def _run_full_update(self) -> None:
        from lib.rating.updater import update_library_ratings

        scope = ADDON.getSetting("imdb_auto_update_scope") or "movies_tvshows"
        log("Service", f"Starting IMDb full auto-update (scope={scope})", xbmc.LOGINFO)

        if scope in ("all", "movies_tvshows", "movies"):
            update_library_ratings("movie", [], use_background=True, source_mode="imdb")
        if scope in ("all", "movies_tvshows"):
            update_library_ratings("tvshow", [], use_background=True, source_mode="imdb")
        if scope == "all":
            update_library_ratings("episode", [], use_background=True, source_mode="imdb")

    def _notify_when_idle(
        self,
        heading: str,
        message: str,
        monitor: xbmc.Monitor,
    ) -> None:
        """Show notification, deferring until playback stops."""
        while xbmc.getCondVisibility("Player.HasVideo"):
            if monitor.waitForAbort(30):
                return
            if self.abort.is_set():
                return

        from lib.infrastructure.dialogs import show_notification
        show_notification(heading, message)


class StingerService(threading.Thread):
    """Independent service for post-credits scene detection during movie playback.

    Polls every 10s for video playback. When a movie is detected, waits one
    tick (~10s) for caches to populate, then fetches movie details and checks
    stinger sources. Subsequent ticks check playback position for notification.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()

    def run(self) -> None:
        monitor = xbmc.Monitor()
        if not wait_for_kodi_ready(monitor):
            return

        log("Service", "Stinger service started", xbmc.LOGINFO)

        stinger = StingerMonitor()
        current_dbid: Optional[str] = None
        fetched = False

        while not monitor.waitForAbort(10):
            if self.abort.is_set():
                break

            movie_playing = (
                get_stinger_settings()["enabled"]
                and xbmc.getCondVisibility("Player.HasVideo")
                and xbmc.getCondVisibility("VideoPlayer.Content(movies)")
            )

            if not movie_playing:
                if current_dbid:
                    stinger.on_playback_stop()
                    current_dbid = None
                    fetched = False
                continue

            dbid = xbmc.getInfoLabel("VideoPlayer.DBID") or ""
            if not dbid or dbid == "-1":
                continue

            if dbid != current_dbid:
                if current_dbid:
                    stinger.reset()
                current_dbid = dbid
                fetched = False
                continue

            if not fetched:
                self._fetch_stinger_info(stinger, dbid)
                fetched = True

            stinger.check_notification()

        log("Service", "Stinger service stopped", xbmc.LOGINFO)

    def _fetch_stinger_info(self, stinger: StingerMonitor, dbid: str) -> None:
        details = get_item_details(
            'movie',
            int(dbid),
            KODI_MOVIE_PROPERTIES,
            cache_key=f"player:movie:{dbid}:details",
        )
        if not isinstance(details, dict):
            return

        ids = extract_media_ids(details)
        stinger.on_playback_start(movie_id=dbid, ids=ids, movie_details=details)


def start_service() -> None:
    if get_prop("SkinInfo.Service.Running"):
        log("Service", "Already running, ignoring duplicate RunScript", xbmc.LOGINFO)
        return

    from lib.data.database._infrastructure import init_database
    from lib.data.database.cache import clear_expired_cache
    from lib.service.slideshow import SlideshowMonitor
    from lib.service.online import OnlineServiceMain
    from lib.data.api.settings import sync_configured_flags

    init_database()
    clear_expired_cache()

    from lib.data.database.music import init_music_database, clear_expired_music_cache
    init_music_database()
    clear_expired_music_cache()

    sync_configured_flags()

    thread = ServiceMain()
    thread.start()

    online_thread = OnlineServiceMain()
    online_thread.start()

    imdb_thread: Optional[ImdbUpdateService] = None
    if ADDON.getSetting("imdb_auto_update") != "off":
        imdb_thread = ImdbUpdateService()
        imdb_thread.start()

    stinger_thread: Optional[StingerService] = None
    if ADDON.getSettingBool("stinger_enabled"):
        stinger_thread = StingerService()
        stinger_thread.start()

    _slideshow_monitor = SlideshowMonitor()
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            thread.abort.set()
            online_thread.abort.set()
            if imdb_thread:
                imdb_thread.abort.set()
            if stinger_thread:
                stinger_thread.abort.set()
            break

    thread.abort.set()
    online_thread.abort.set()
    if imdb_thread:
        imdb_thread.abort.set()
    if stinger_thread:
        stinger_thread.abort.set()

    thread.join(timeout=2)
    online_thread.join(timeout=2)
    if imdb_thread:
        imdb_thread.join(timeout=2)
    if stinger_thread:
        stinger_thread.join(timeout=2)

    log("Service", "All services stopped", xbmc.LOGINFO)
    del _slideshow_monitor


if __name__ == "__main__":
    start_service()
