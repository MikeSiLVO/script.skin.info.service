"""Video player handler: sets `SkinInfo.Player.Online.*` props for the playing movie/episode."""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, TYPE_CHECKING

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import clear_group, batch_set_props, playing_media_type
from lib.data.database.cache import CacheKey
from lib.service.online.helpers import (
    make_cache_key,
    resolve_ids_from,
)
from lib.service.online.fetchers import fetch_all_online_data

if TYPE_CHECKING:
    from lib.service.online.main import OnlineServiceMain


PLAYER_ONLINE_PROPERTY_PREFIX = "SkinInfo.Player.Online."

# a fetch that came back empty must not respawn a worker on the next tick
FETCH_BACKOFF_S = 300


class PlayerHandler:
    """Tracks the playing movie/episode and applies fetched online properties (no cache)."""

    def __init__(self, service: 'OnlineServiceMain'):
        self._service = service
        self._last_key: Optional[CacheKey] = None
        self._player = xbmc.Player()
        self._fetch_thread: Optional[threading.Thread] = None
        self._fetch_for_key: Optional[CacheKey] = None
        self._empty_for_key: Optional[CacheKey] = None
        self._empty_at: float = 0.0

    def process(self) -> None:
        """Read VideoPlayer state; fetch and apply online props for movies/episodes."""
        if not self._player.isPlayingVideo():
            self._clear_if_active()
            return

        dbid = xbmc.getInfoLabel("VideoPlayer.DBID") or ""
        if not dbid:
            self._clear_if_active()
            return

        dbtype = playing_media_type(self._player)
        if dbtype not in ("movie", "episode"):
            self._clear_if_active()
            return

        imdb_id, tmdb_id = resolve_ids_from(dbtype, dbid, "VideoPlayer")

        if not imdb_id and not tmdb_id:
            self._clear_if_active()
            return

        cache_key = make_cache_key(dbtype, imdb_id, tmdb_id, "player")
        if not cache_key:
            return

        if cache_key == self._last_key:
            return

        if (self._fetch_thread and self._fetch_thread.is_alive()
                and self._fetch_for_key == cache_key):
            return

        if (cache_key == self._empty_for_key
                and time.time() - self._empty_at < FETCH_BACKOFF_S):
            return

        self._fetch_for_key = cache_key
        self._fetch_thread = threading.Thread(
            target=self._fetch_worker,
            args=(dbtype, imdb_id, tmdb_id, cache_key),
            daemon=True,
        )
        self._fetch_thread.start()

    def _fetch_worker(self, media_type: str, imdb_id: str, tmdb_id: str,
                      cache_key: CacheKey) -> None:
        try:
            abort_flag = self._service.capped_abort_flag
            if abort_flag.is_requested():
                return

            props = fetch_all_online_data(media_type, imdb_id, tmdb_id, abort_flag)

            if abort_flag.is_requested():
                return
            if not props:
                self._empty_for_key = cache_key
                self._empty_at = time.time()
                return
            if cache_key != self._fetch_for_key:
                return

            props_to_set: Dict[str, Optional[str]] = {
                f"{PLAYER_ONLINE_PROPERTY_PREFIX}{k}": str(v)
                for k, v in props.items() if v
            }
            batch_set_props(props_to_set)
            self._last_key = cache_key

        except Exception as e:
            log("Service", f"Online player fetch error: {e}", xbmc.LOGWARNING)

    def _clear_if_active(self) -> None:
        if self._last_key:
            clear_group(PLAYER_ONLINE_PROPERTY_PREFIX)
            self._last_key = None
        self._empty_for_key = None
