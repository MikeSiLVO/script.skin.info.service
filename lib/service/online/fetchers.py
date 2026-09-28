"""Episode ratings for the focused or playing episode, published as properties."""
from __future__ import annotations

import threading
from typing import Dict, Optional, TYPE_CHECKING

import xbmc

from lib.data.online import fetch_trakt_data
from lib.kodi.client import log
from lib.kodi.formatters import format_rating_props
from lib.kodi.utilities import batch_set_props, clear_group

if TYPE_CHECKING:
    pass


def fetch_episode_ratings(show_imdb: str, show_tmdb: str, season: int, episode: int,
                          episode_imdb: str = "", abort_flag=None) -> Dict[str, str]:
    """Fetch one episode's IMDb, TMDB and Trakt ratings as `Rating.*` properties."""
    from lib.data.api.imdb import get_imdb_dataset
    from lib.data.api.tmdb import ApiTmdb

    props: Dict[str, str] = {}
    ids = {"imdb": show_imdb, "tmdb": show_tmdb, "season": str(season), "episode": str(episode)}

    try:
        dataset = get_imdb_dataset()
        if not episode_imdb and show_imdb:
            episode_imdb = dataset.get_episode_imdb_id(show_imdb, season, episode) or ""
        imdb = dataset.get_rating(episode_imdb) if episode_imdb else None
        if imdb:
            props.update(format_rating_props("imdb", imdb["rating"], int(imdb["votes"])))
    except Exception as e:
        log("Service", f"IMDb episode rating error: {e}", xbmc.LOGWARNING)

    if show_tmdb and not (abort_flag and abort_flag.is_requested()):
        try:
            api = ApiTmdb()
            ratings = api.fetch_ratings("episode", ids, abort_flag=abort_flag)
            if not ratings:
                data = api.get_season_details(int(show_tmdb), season, abort_flag,
                                              force_refresh=True)
                if data:
                    api.store_episode_ratings(int(show_tmdb), season, data)
                    ratings = api.fetch_ratings("episode", ids, abort_flag=abort_flag)
            tmdb = (ratings or {}).get("tmdb")
            if tmdb:
                props.update(format_rating_props("tmdb", tmdb["rating"], int(tmdb["votes"])))
        except Exception as e:
            log("Service", f"TMDB episode rating error: {e}", xbmc.LOGWARNING)

    if not (abort_flag and abort_flag.is_requested()):
        props.update({
            k: v for k, v in fetch_trakt_data(
                "episode", show_imdb, show_tmdb, True, season, episode, abort_flag
            ).items() if k.startswith("Rating.")
        })

    return props


class EpisodeRatings:
    """Publishes the focused or playing episode's online ratings under `<prefix>Episode.`."""

    def __init__(self, prefix: str, abort_flag):
        self._prefix = f"{prefix}Episode."
        self._abort_flag = abort_flag
        self._dbid: Optional[str] = None

    def reset(self) -> None:
        """Clear the published ratings once no episode is current."""
        if self._dbid is not None:
            clear_group(self._prefix)
            self._dbid = None

    def forget(self) -> None:
        """Forget the current episode after its properties were cleared elsewhere."""
        self._dbid = None

    def update(self, dbid: str, season: str, episode: str, episode_imdb: str,
               show_imdb: str, show_tmdb: str) -> None:
        """Update the published ratings off-thread when the episode changes."""
        if dbid == self._dbid:
            return
        self.reset()
        if not season.isdigit() or not episode.isdigit():
            return
        self._dbid = dbid
        threading.Thread(
            target=self._worker,
            args=(dbid, int(season), int(episode), episode_imdb, show_imdb, show_tmdb),
            daemon=True,
        ).start()

    def _worker(self, dbid: str, season: int, episode: int, episode_imdb: str,
                show_imdb: str, show_tmdb: str) -> None:
        """Fetch one episode's ratings, publishing them only while it is still current."""
        if not episode_imdb:
            from lib.kodi.client import get_item_details
            details = get_item_details("episode", int(dbid), ["uniqueid"],
                                       cache_key=f"episode:{dbid}:uniqueid")
            if isinstance(details, dict):
                episode_imdb = (details.get("uniqueid") or {}).get("imdb") or ""
        props = fetch_episode_ratings(
            show_imdb, show_tmdb, season, episode, episode_imdb, self._abort_flag)
        if self._dbid != dbid or self._abort_flag.is_requested():
            return
        batch_set_props({f"{self._prefix}{k}": v for k, v in props.items()})
