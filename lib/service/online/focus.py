"""Focus handler: monitors ListItem changes and sets `SkinInfo.Online.*` properties."""
from __future__ import annotations

import threading
import time
from typing import Optional, Set, TYPE_CHECKING

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import (
    clear_group, batch_set_props, gui_transition_settled, modal_dialog_active,
)
from lib.data.database.cache import (
    CacheKey,
    get_cached_online_properties_state,
    online_cache_generation,
    cache_online_properties,
)
from lib.service.online.helpers import (
    get_online_ttl,
    make_cache_key,
    resolve_ids_from,
    resolve_season_ids,
)
from lib.service.online.fetchers import fetch_all_online_data

if TYPE_CHECKING:
    from lib.service.online.main import OnlineServiceMain


ONLINE_PROPERTY_PREFIX = "SkinInfo.Online."

# a fetch that came back empty must not respawn a worker on the next tick
FETCH_BACKOFF_S = 300


class FocusHandler:
    """Tracks focused library items and applies cached/fetched online properties."""

    def __init__(self, service: 'OnlineServiceMain'):
        self._service = service
        self._last_item_key: Optional[CacheKey] = None
        self._last_item_id: Optional[str] = None
        self._last_expires_at: int = 0
        self._last_generation: int = -1
        # guarded by _keys_lock: read+swapped from both the poll thread and fetch workers
        self._last_prop_keys: Set[str] = set()
        self._keys_lock = threading.Lock()
        self._fetch_thread: Optional[threading.Thread] = None
        self._fetch_for_key: Optional[CacheKey] = None
        self._refreshed_for_key: Optional[CacheKey] = None
        self._empty_for_key: Optional[CacheKey] = None
        self._empty_at: float = 0.0
        self._empty_generation: int = -1

    def process(self) -> None:
        """Read focused ListItem; set cached props or kick off a background fetch."""
        if not gui_transition_settled():
            return
        dbid = xbmc.getInfoLabel("ListItem.DBID") or ""
        dbtype = xbmc.getInfoLabel("ListItem.DBType") or ""

        if not dbid or dbtype not in ("movie", "tvshow", "episode", "season"):
            if modal_dialog_active():
                return
            if self._last_item_key:
                self._clear_properties()
                self._last_item_key = None
                self._last_item_id = None
                self._last_expires_at = 0
                self._last_generation = -1
                self._last_prop_keys = set()
                self._empty_for_key = None
            return

        item_id = f"{dbtype}:{dbid}"
        generation = online_cache_generation()
        if (item_id == self._last_item_id and generation == self._last_generation
                and time.time() < self._last_expires_at):
            return

        if dbtype == "season":
            imdb_id, tmdb_id = resolve_season_ids(dbid)
            effective_type = "tvshow"
        else:
            imdb_id, tmdb_id = resolve_ids_from(dbtype, dbid, "ListItem")
            effective_type = dbtype

        if not imdb_id and not tmdb_id:
            return

        cache_key = make_cache_key(effective_type, imdb_id, tmdb_id)
        if not cache_key:
            return

        cached_props, expires_at = get_cached_online_properties_state(cache_key)
        expired = expires_at <= time.time()

        # id resolution lags the focus, so the key can still be the previous item's
        self._last_item_id = None
        self._last_expires_at = 0
        if cache_key != self._refreshed_for_key:
            self._refreshed_for_key = None

        if cache_key == self._last_item_key and cached_props and not expired:
            return

        self._last_item_key = cache_key

        if cached_props:
            props_to_set = {}
            new_keys = set()
            for key, value in cached_props.items():
                if value:
                    props_to_set[f"{ONLINE_PROPERTY_PREFIX}{key}"] = str(value)
                    new_keys.add(key)
            with self._keys_lock:
                stale_keys = self._last_prop_keys - new_keys
                self._last_prop_keys = new_keys
            for old_key in stale_keys:
                props_to_set[f"{ONLINE_PROPERTY_PREFIX}{old_key}"] = ""
            batch_set_props(props_to_set)

            if not expired:
                self._last_item_id = item_id
                self._last_generation = generation
                self._last_expires_at = expires_at
                return
            # row stays expired until the fetch writes it back
            if cache_key == self._refreshed_for_key:
                return
            self._refreshed_for_key = cache_key

        # props persist across items
        elif self._last_prop_keys:
            self._clear_properties()
            with self._keys_lock:
                self._last_prop_keys = set()

        if (self._fetch_thread and self._fetch_thread.is_alive()
                and self._fetch_for_key == cache_key):
            return

        if generation != self._empty_generation:
            self._empty_for_key = None
        if (cache_key == self._empty_for_key
                and time.time() - self._empty_at < FETCH_BACKOFF_S):
            return

        if cache_key in self._service.updater_in_progress:
            return

        self._fetch_for_key = cache_key
        self._fetch_thread = threading.Thread(
            target=self._fetch_worker,
            args=(effective_type, imdb_id, tmdb_id, cache_key),
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
                self._empty_generation = online_cache_generation()
                if cache_key == self._refreshed_for_key:
                    self._refreshed_for_key = None
                return

            ttl_hours = get_online_ttl(media_type, tmdb_id)
            cache_online_properties(cache_key, props, ttl_hours=ttl_hours)

            if cache_key != self._last_item_key:
                return

            props_to_set = {}
            new_keys = set()
            for key, value in props.items():
                if value:
                    props_to_set[f"{ONLINE_PROPERTY_PREFIX}{key}"] = str(value)
                    new_keys.add(key)

            with self._keys_lock:
                stale_keys = self._last_prop_keys - new_keys
                self._last_prop_keys = new_keys
            for old_key in stale_keys:
                props_to_set[f"{ONLINE_PROPERTY_PREFIX}{old_key}"] = ""

            batch_set_props(props_to_set)

        except Exception as e:
            log("Service", f"Online fetch error: {e}", xbmc.LOGWARNING)

    def _clear_properties(self) -> None:
        clear_group(ONLINE_PROPERTY_PREFIX)
