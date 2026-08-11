"""Music + musicvideo player handler: fetches artist/track/album online data and rotates fanart."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import clear_group, set_prop, batch_set_props
from lib.service.online.fetchers import get_playing_artist_mbids

if TYPE_CHECKING:
    from lib.service.music import MusicOnlineResult
    from lib.service.online.main import OnlineServiceMain


PLAYER_MUSIC_ONLINE_PREFIX = "SkinInfo.Player.Online.Music."
PLAYER_MUSICVIDEO_ONLINE_PREFIX = "SkinInfo.Player.Online.MusicVideo."


@dataclass(frozen=True)
class _Mode:
    """Everything that differs between the audio and musicvideo tracks."""
    condition: str
    player: str
    prefix: str
    fetch_mbids: bool
    log_label: str


@dataclass
class _State:
    """Playback state for one mode."""
    key: Optional[str] = None
    thread: Optional[threading.Thread] = None
    thread_key: Optional[str] = None


_MODES = (
    _Mode(
        condition="Player.HasAudio",
        player="MusicPlayer",
        prefix=PLAYER_MUSIC_ONLINE_PREFIX,
        fetch_mbids=True,
        log_label="Music player",
    ),
    _Mode(
        condition="Player.HasVideo + VideoPlayer.Content(musicvideos)",
        player="VideoPlayer",
        prefix=PLAYER_MUSICVIDEO_ONLINE_PREFIX,
        fetch_mbids=False,
        log_label="Music video player",
    ),
)


class MusicPlayerHandler:
    """Tracks audio and musicvideo playback, fetches online data, rotates fanart."""

    def __init__(self, service: 'OnlineServiceMain'):
        self._service = service
        self._players: Tuple[Tuple[_Mode, _State], ...] = tuple(
            (mode, _State()) for mode in _MODES
        )
        self._fanart_urls: List[str] = []
        self._fanart_index: int = 0
        self._fanart_last_rotate: float = 0.0
        self._active_prefix: str = PLAYER_MUSIC_ONLINE_PREFIX

    def process(self) -> None:
        """Fetch artist online data whenever either player moves to a new artist."""
        for mode, state in self._players:
            self._process(mode, state)

    def rotate_fanart(self) -> None:
        """Cycle through artist fanart URLs at the configured slideshow interval."""
        # snapshot: a fetch worker can swap the list mid-rotation
        urls = self._fanart_urls
        if len(urls) <= 1:
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
        next_index = (self._fanart_index + 1) % len(urls)
        self._fanart_index = next_index
        set_prop(
            f"{self._active_prefix}Artist.FanArt",
            urls[next_index],
        )

    def _process(self, mode: _Mode, state: _State) -> None:
        """Start a fetch thread when this player's artist changes."""
        if not xbmc.getCondVisibility(mode.condition):
            self._reset(mode, state)
            return

        artist_name = xbmc.getInfoLabel(f"{mode.player}.Artist") or ""
        if not artist_name:
            self._reset(mode, state)
            return

        if artist_name == state.key:
            return

        state.key = artist_name
        self._fanart_urls = []
        self._fanart_index = 0

        if state.thread and state.thread.is_alive() and state.thread_key == artist_name:
            return

        state.thread_key = artist_name
        state.thread = threading.Thread(
            target=self._fetch_worker,
            args=(mode, state, artist_name),
            daemon=True,
        )
        state.thread.start()

    def _fetch_worker(self, mode: _Mode, state: _State, artist_name: str) -> None:
        """Off-thread artist fetch, discarded if the artist changed while it ran."""
        try:
            if self._service.abort_flag.is_requested():
                return

            from lib.service.music import fetch_artist_online_data

            mbids = get_playing_artist_mbids() if mode.fetch_mbids else None
            album = xbmc.getInfoLabel(f"{mode.player}.Album") or None
            title = xbmc.getInfoLabel(f"{mode.player}.Title") or None

            result = fetch_artist_online_data(
                artist_name,
                mbids=mbids or None,
                album=album,
                track=title,
                abort_flag=self._service.capped_abort_flag,
            )

            if artist_name != state.key or not result:
                return

            self._apply(mode, artist_name, result, title, album)

        except Exception as e:
            log("Service", f"{mode.log_label} online fetch error: {e}", xbmc.LOGWARNING)

    def _apply(self, mode: _Mode, artist_name: str, result: 'MusicOnlineResult',
               track: Optional[str], album: Optional[str]) -> None:
        """Publish artist, track and album properties under this mode's prefix."""
        from lib.service.music import (
            fill_artist_online_props,
            fill_track_online_props,
            fill_album_online_props,
        )

        self._fanart_urls = result.fanart_urls
        self._fanart_index = 0
        self._fanart_last_rotate = time.time()
        self._active_prefix = mode.prefix

        artist_props: Dict[str, Optional[str]] = {}
        fill_artist_online_props(artist_props, mode.prefix, result, name=artist_name)
        batch_set_props(artist_props)

        if track:
            track_props: Dict[str, Optional[str]] = {}
            fill_track_online_props(track_props, mode.prefix, artist_name, track,
                                    abort_flag=self._service.capped_abort_flag)
            if track_props:
                batch_set_props(track_props)

        if album:
            album_props: Dict[str, Optional[str]] = {}
            fill_album_online_props(album_props, mode.prefix, artist_name, album,
                                    abort_flag=self._service.capped_abort_flag)
            if album_props:
                batch_set_props(album_props)

    def _reset(self, mode: _Mode, state: _State) -> None:
        """Clear this player's properties once it stops."""
        if state.key:
            clear_group(mode.prefix)
            self._fanart_urls = []
            self._fanart_index = 0
            state.key = None
