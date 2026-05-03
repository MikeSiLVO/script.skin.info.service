"""Music + musicvideo player handler: fetches artist/track/album online data and rotates fanart."""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, TYPE_CHECKING

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import clear_group, set_prop, batch_set_props
from lib.service.online.fetchers import get_playing_artist_mbids

if TYPE_CHECKING:
    from lib.service.music import MusicOnlineResult
    from lib.service.online.main import OnlineServiceMain


PLAYER_MUSIC_ONLINE_PREFIX = "SkinInfo.Player.Online.Music."
PLAYER_MUSICVIDEO_ONLINE_PREFIX = "SkinInfo.Player.Online.MusicVideo."


class MusicPlayerHandler:
    """Tracks audio and musicvideo playback, fetches online data, rotates fanart."""

    def __init__(self, service: 'OnlineServiceMain'):
        self._service = service
        self._last_audio_key: Optional[str] = None
        self._audio_fetch_thread: Optional[threading.Thread] = None
        self._audio_fetch_for_key: Optional[str] = None
        self._last_video_key: Optional[str] = None
        self._video_fetch_thread: Optional[threading.Thread] = None
        self._video_fetch_for_key: Optional[str] = None
        self._fanart_urls: List[str] = []
        self._fanart_index: int = 0
        self._fanart_last_rotate: float = 0.0
        self._active_prefix: str = PLAYER_MUSIC_ONLINE_PREFIX

    def process_audio(self) -> None:
        """Handle plain audio playback: fetch artist online data on first track of an artist."""
        if not xbmc.getCondVisibility("Player.HasAudio"):
            self._reset_audio()
            return

        artist_name = xbmc.getInfoLabel("MusicPlayer.Artist") or ""
        if not artist_name:
            self._reset_audio()
            return

        if artist_name == self._last_audio_key:
            return

        self._last_audio_key = artist_name
        self._fanart_urls = []
        self._fanart_index = 0

        if (self._audio_fetch_thread and self._audio_fetch_thread.is_alive()
                and self._audio_fetch_for_key == artist_name):
            return

        self._audio_fetch_for_key = artist_name
        self._audio_fetch_thread = threading.Thread(
            target=self._audio_fetch_worker,
            args=(artist_name,),
            daemon=True,
        )
        self._audio_fetch_thread.start()

    def process_video(self) -> None:
        """Handle musicvideo playback: fetch artist online data."""
        is_musicvideo = (
            xbmc.getCondVisibility("Player.HasVideo")
            and xbmc.getCondVisibility("VideoPlayer.Content(musicvideos)")
        )

        if not is_musicvideo:
            self._reset_video()
            return

        artist_name = xbmc.getInfoLabel("VideoPlayer.Artist") or ""
        if not artist_name:
            self._reset_video()
            return

        if artist_name == self._last_video_key:
            return

        self._last_video_key = artist_name
        self._fanart_urls = []
        self._fanart_index = 0

        if (self._video_fetch_thread and self._video_fetch_thread.is_alive()
                and self._video_fetch_for_key == artist_name):
            return

        self._video_fetch_for_key = artist_name
        self._video_fetch_thread = threading.Thread(
            target=self._video_fetch_worker,
            args=(artist_name,),
            daemon=True,
        )
        self._video_fetch_thread.start()

    def rotate_fanart(self) -> None:
        """Cycle through artist fanart URLs at the configured slideshow interval."""
        if len(self._fanart_urls) <= 1:
            return

        now = time.time()

        interval_str = xbmc.getInfoLabel(
            'Skin.String(SkinInfo.SlideshowRefreshInterval)'
        ) or '10'
        try:
            interval = max(5, min(int(interval_str), 3600))
        except ValueError:
            interval = 10

        if now - self._fanart_last_rotate < interval:
            return

        self._fanart_last_rotate = now
        self._fanart_index = (self._fanart_index + 1) % len(self._fanart_urls)
        set_prop(
            f"{self._active_prefix}Artist.FanArt",
            self._fanart_urls[self._fanart_index],
        )

    def _audio_fetch_worker(self, artist_name: str) -> None:
        try:
            if self._service.abort_flag.is_requested():
                return

            from lib.service.music import fetch_artist_online_data

            mbids = get_playing_artist_mbids()
            album = xbmc.getInfoLabel("MusicPlayer.Album") or None
            track = xbmc.getInfoLabel("MusicPlayer.Title") or None

            result = fetch_artist_online_data(
                artist_name,
                mbids=mbids or None,
                album=album,
                track=track,
                abort_flag=self._service.abort_flag,
            )

            if artist_name != self._last_audio_key:
                return
            if not result:
                return

            self._apply(artist_name, result, track, album, PLAYER_MUSIC_ONLINE_PREFIX)

        except Exception as e:
            log("Service", f"Music player online fetch error: {e}", xbmc.LOGWARNING)

    def _video_fetch_worker(self, artist_name: str) -> None:
        try:
            if self._service.abort_flag.is_requested():
                return

            from lib.service.music import fetch_artist_online_data

            album = xbmc.getInfoLabel("VideoPlayer.Album") or None
            track = xbmc.getInfoLabel("VideoPlayer.Title") or None

            result = fetch_artist_online_data(
                artist_name,
                album=album,
                track=track,
                abort_flag=self._service.abort_flag,
            )

            if artist_name != self._last_video_key:
                return
            if not result:
                return

            self._apply(artist_name, result, track, album, PLAYER_MUSICVIDEO_ONLINE_PREFIX)

        except Exception as e:
            log("Service", f"Music video player online fetch error: {e}", xbmc.LOGWARNING)

    def _apply(self, artist_name: str, result: 'MusicOnlineResult',
               track: Optional[str], album: Optional[str], prefix: str) -> None:
        from lib.service.music import (
            fetch_track_online_data,
            fetch_album_online_data,
            extract_track_properties,
            extract_album_properties,
        )

        self._fanart_urls = result.fanart_urls
        self._fanart_index = 0
        self._fanart_last_rotate = time.time()
        self._active_prefix = prefix
        self._set_artist_props(
            artist_name, result.bio, result.fanart_urls, result.artist_art, prefix,
        )

        if track:
            fetch_track_online_data(artist_name, track, abort_flag=self._service.abort_flag)
            track_props = extract_track_properties(artist_name, track)
            if track_props:
                batch_set_props({
                    f"{prefix}Track.{k}": v
                    for k, v in track_props.items()
                })

        if album:
            fetch_album_online_data(artist_name, album, abort_flag=self._service.abort_flag)
            album_props = extract_album_properties(artist_name, album)
            if album_props:
                batch_set_props({
                    f"{prefix}Album.{k}": v
                    for k, v in album_props.items()
                })

    @staticmethod
    def _set_artist_props(artist_name: str, bio: str, fanart_urls: List[str],
                          artist_art: Dict[str, str], prefix: str) -> None:
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

    def _reset_audio(self) -> None:
        if self._last_audio_key:
            clear_group(PLAYER_MUSIC_ONLINE_PREFIX)
            self._fanart_urls = []
            self._fanart_index = 0
            self._last_audio_key = None

    def _reset_video(self) -> None:
        if self._last_video_key:
            clear_group(PLAYER_MUSICVIDEO_ONLINE_PREFIX)
            self._fanart_urls = []
            self._fanart_index = 0
            self._last_video_key = None
