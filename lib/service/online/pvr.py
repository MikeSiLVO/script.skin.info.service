"""PVR focus handler: sets `SkinInfo.PVR.*` for the focused live TV programme."""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Set, Tuple, TYPE_CHECKING, Final

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import (
    batch_set_props, clear_group, gui_transition_settled, modal_dialog_active, skin_bool,
)
from lib.data.database.cache import (
    CacheKey, cache_online_properties, get_cached_online_properties_state,
)
from lib.data.database.pvr import (
    PVR_SCOPE, PvrMatch, PvrMatchKey, get_pvr_match, needs_recheck, needs_touch,
    save_pvr_match, touch_pvr_match,
)
from lib.data.online import get_online_ttl
from lib.data.pvr import (
    Programme, PvrLookupFailed, PvrTitle, fetch_programme_props, is_programme_path, is_skipped,
    match_key, match_programme, read_programme,
)

if TYPE_CHECKING:
    from lib.service.online.main import OnlineServiceMain, CancelToken


PVR_PREFIX: Final = "SkinInfo.PVR."
SKIN_BOOL: Final = "SkinInfo.PVR"

_MAX_MISSES: Final = 5000


class PvrFocusHandler:
    """Handler setting `SkinInfo.PVR.*` for the focused guide entry, channel, recording or timer."""

    def __init__(self, service: 'OnlineServiceMain'):
        self._service = service
        self._last_focus: Optional[Tuple[str, str]] = None
        self._last_key: Optional[PvrMatchKey] = None
        self._token: Optional['CancelToken'] = None
        self._published: Set[str] = set()
        self._keys_lock = threading.Lock()
        self._misses: Set[PvrMatchKey] = set()

    def process(self) -> None:
        """Read the focused programme; publish its cached props or start a lookup."""
        if not skin_bool(SKIN_BOOL):
            if self._last_focus is not None:
                self._reset()
            return
        if not gui_transition_settled():
            return
        path = xbmc.getInfoLabel("ListItem.FileNameAndPath")
        title = xbmc.getInfoLabel("ListItem.Title") if path.startswith("pvr://") else ""
        if title and (path, title) == self._last_focus:
            return
        programme = read_programme(title) if is_programme_path(path) else None
        if programme is None:
            if self._last_focus is not None and not modal_dialog_active():
                self._reset()
            return
        # fields are read one call at a time and can straddle a focus move
        if xbmc.getInfoLabel("ListItem.FileNameAndPath") != path:
            return
        self._last_focus = (path, title)

        key = None if is_skipped(programme) else match_key(programme)
        if key == self._last_key:
            return
        self._last_key = key
        self._cancel_pending()
        if key is None:
            self._publish({})
            return

        match = get_pvr_match(key)
        if match:
            if not match.tmdb_id:
                self._publish({})
                return
            props, expires_at = get_cached_online_properties_state(self._cache_key(match))
            self._publish(props or {})
            if props and expires_at > time.time() and not needs_recheck(match):
                if needs_touch(match):
                    touch_pvr_match(key)
                return
        else:
            self._publish({})
            if key in self._misses:
                return

        token = self._service.new_cancel_token()
        self._token = token
        threading.Thread(target=self._worker, args=(programme, key, match, token),
                         daemon=True).start()

    def forget(self) -> None:
        """Forget the focused programme after its match was changed by hand."""
        self._last_focus = None
        self._last_key = None

    @staticmethod
    def _cache_key(title: PvrMatch | PvrTitle) -> CacheKey:
        """Online-properties key of a matched title's PVR props."""
        return CacheKey(title.media_type, str(title.tmdb_id), PVR_SCOPE)

    def _worker(self, programme: Programme, key: PvrMatchKey, match: Optional[PvrMatch],
                token: 'CancelToken') -> None:
        """Match the programme if due, then fetch and cache its props, publishing if current."""
        try:
            title = self._resolve(programme, key, match, token)
            if title is None or token.is_requested():
                return
            cache_key = self._cache_key(title)
            props, expires_at = get_cached_online_properties_state(cache_key)
            if not props or expires_at <= time.time():
                fresh = fetch_programme_props(title, token)
                if fresh:
                    ttl_hours = get_online_ttl(title.media_type, str(title.tmdb_id))
                    cache_online_properties(cache_key, fresh, ttl_hours=ttl_hours)
                    props = fresh
            if props and not token.is_requested() and key == self._last_key:
                self._publish(props)
        except PvrLookupFailed as e:
            log("Service", f"PVR search failed for '{e}'", xbmc.LOGDEBUG)
        except Exception as e:
            log("Service", f"PVR lookup error: {e}", xbmc.LOGWARNING)

    def _resolve(self, programme: Programme, key: PvrMatchKey, match: Optional[PvrMatch],
                 token: 'CancelToken') -> Optional[PvrTitle]:
        """Get the programme's TMDB title, searching and saving when unmatched or due a recheck."""
        if match and not needs_recheck(match):
            if needs_touch(match):
                touch_pvr_match(key)
            return PvrTitle(match.media_type, match.tmdb_id)
        found = match_programme(programme, token)
        if token.is_requested():
            return None
        if found is None:
            if match is None:
                if len(self._misses) >= _MAX_MISSES:
                    self._misses.clear()
                self._misses.add(key)
                return None
            found = PvrTitle(match.media_type, match.tmdb_id)
        save_pvr_match(key, found.media_type, found.tmdb_id)
        return found

    def _publish(self, props: Dict[str, str]) -> None:
        """Publish one programme's props, blanking the previous programme's leftovers."""
        new_keys = {k for k, v in props.items() if v}
        to_set: Dict[str, Optional[str]] = {f"{PVR_PREFIX}{k}": str(props[k]) for k in new_keys}
        with self._keys_lock:
            stale = self._published - new_keys
            self._published = new_keys
        for old in stale:
            to_set[f"{PVR_PREFIX}{old}"] = ""
        if to_set:
            batch_set_props(to_set)

    def _cancel_pending(self) -> None:
        """Cancel the previous programme's lookup so a fast scroll stops piling on."""
        if self._token is not None:
            self._token.cancel()
            self._token = None

    def _reset(self) -> None:
        """Clear every `SkinInfo.PVR.*` property when focus leaves live TV or the skin unsets it."""
        self._cancel_pending()
        clear_group(PVR_PREFIX)
        with self._keys_lock:
            self._published = set()
        self._last_focus = None
        self._last_key = None
