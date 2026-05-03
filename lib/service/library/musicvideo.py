"""Music video art handler. Library art runs synchronously; online enrichment is async."""
from __future__ import annotations

import threading
from typing import Dict, Optional, TYPE_CHECKING

import xbmc

from lib.kodi.client import get_item_details, log
from lib.kodi.utilities import batch_set_props

if TYPE_CHECKING:
    from lib.service.music import MusicOnlineResult


_ONLINE_ART_KEYS = (
    "Online.Artist.Bio", "Online.Artist.FanArt", "Online.Artist.FanArt.Count",
    "Online.Artist.Thumb", "Online.Artist.Clearlogo", "Online.Artist.Banner",
    "Online.Track.Wiki", "Online.Track.Tags", "Online.Track.Listeners",
    "Online.Track.Playcount", "Online.Album.Wiki", "Online.Album.Tags",
    "Online.Album.Label",
)


class MusicVideoArt:
    """Owns musicvideo online-data state (last cache key, async fetch thread)."""

    def __init__(self):
        self._online_thread: Optional[threading.Thread] = None
        self._online_key: Optional[str] = None

    def reset_online_key(self) -> None:
        """Drop the last-seen online cache key so the next focus refetches."""
        self._online_key = None

    def set_artist_node(self) -> None:
        """Set art for an artist musicvideo node (DBID-less, name from ListItem.Label)."""
        artist_name = xbmc.getInfoLabel("ListItem.Label") or ""
        if not artist_name:
            return
        details: dict = {"artist": [artist_name], "album": ""}
        self.set_full_art(details)

    def set_album_node(self) -> None:
        """Set art for an album musicvideo node."""
        album_name = xbmc.getInfoLabel("ListItem.Label") or ""
        if not album_name:
            return
        artist_name = xbmc.getInfoLabel("ListItem.Artist") or ""
        details: dict = {
            "artist": [artist_name] if artist_name else [],
            "album": album_name,
        }
        self.set_library_art(details)

    def invalidate_for(self, musicvideoid: int) -> None:
        """Drop cached music data for the artist/track/album of this music video."""
        from lib.service.properties import join_multi
        details = get_item_details(
            'musicvideo', musicvideoid, ["title", "artist", "album"],
            cache_key=f"musicvideo:{musicvideoid}:invalidate",
        )
        if not isinstance(details, dict):
            return
        artist = join_multi(details.get("artist"))
        if not artist:
            return
        from lib.data.database.music import invalidate_music_cache
        invalidate_music_cache(
            artist,
            track=details.get("title", ""),
            album=details.get("album", ""),
        )
        self._online_key = None

    def set_focus_details(self, musicvideoid: str) -> None:
        """Fetch musicvideo details + set library/online art for a focused item."""
        from lib.service.properties import set_musicvideo_properties
        details = get_item_details(
            'musicvideo', int(musicvideoid),
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
        self.set_full_art(details)

    def set_full_art(self, details: dict, prefix: str = "SkinInfo.MusicVideo.") -> None:
        """Library + online art in one batch (single batch prevents stale-prop fallthrough)."""
        from lib.plugin.dbid import get_musicvideo_artist_art
        from lib.service.properties import join_multi

        props: Dict[str, Optional[str]] = {
            f"{prefix}{k}": "" for k in _ONLINE_ART_KEYS
        }

        artist_art, artist_id = get_musicvideo_artist_art(details)
        artist_keys = ("Artist.Fanart", "Artist.Thumb", "Artist.Clearlogo", "Artist.Banner")
        for k in artist_keys:
            props[f"{prefix}{k}"] = artist_art.get(k, "")

        artist_name = join_multi(details.get("artist"))
        cache_hit = False
        if artist_name:
            album = details.get("album") or None
            title = details.get("title") or None
            cache_key = "{}|{}|{}".format(artist_name, title or "", album or "")

            if cache_key == self._online_key:
                for k in _ONLINE_ART_KEYS:
                    props.pop(f"{prefix}{k}", None)
                cache_hit = True
            else:
                self._online_key = cache_key
                from lib.service.music import try_cached_artist_online_data
                cached = try_cached_artist_online_data(artist_name)
                if cached:
                    cache_hit = True
                    self._fill_online_props(props, cached, artist_name, title, album, prefix)

        batch_set_props(props)

        self._defer_album_thumb(details, artist_id, prefix)

        if artist_name and not cache_hit:
            album = details.get("album") or None
            title = details.get("title") or None
            if not (self._online_thread and self._online_thread.is_alive()):
                self._online_thread = threading.Thread(
                    target=self._online_worker,
                    args=(artist_name, album, title),
                    daemon=True,
                )
                self._online_thread.start()

    def set_library_art(self, details: dict, prefix: str = "SkinInfo.MusicVideo.") -> None:
        """Library artist art only — used by player/node contexts where online props don't apply."""
        from lib.plugin.dbid import get_musicvideo_artist_art

        artist_art, artist_id = get_musicvideo_artist_art(details)
        artist_keys = ("Artist.Fanart", "Artist.Thumb", "Artist.Clearlogo", "Artist.Banner")
        props: dict = {f"{prefix}{k}": artist_art.get(k, "") for k in artist_keys}
        batch_set_props(props)
        self._defer_album_thumb(details, artist_id, prefix)

    def _fill_online_props(
        self,
        props: Dict[str, Optional[str]],
        result: "MusicOnlineResult",
        artist_name: str,
        title: Optional[str],
        album: Optional[str],
        prefix: str,
    ) -> None:
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

    @staticmethod
    def _defer_album_thumb(details: dict, artist_id: object, prefix: str) -> None:
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

    def _online_worker(
        self, artist_name: str, album: Optional[str], title: Optional[str]
    ) -> None:
        try:
            from lib.service.music import fetch_artist_online_data

            result = fetch_artist_online_data(artist_name, album=album, track=title)

            expected_key = "{}|{}|{}".format(artist_name, title or "", album or "")
            if expected_key != self._online_key:
                return

            if not result:
                return

            prefix = "SkinInfo.MusicVideo."
            props: Dict[str, Optional[str]] = {
                f"{prefix}{k}": "" for k in _ONLINE_ART_KEYS
            }
            self._fill_online_props(props, result, artist_name, title, album, prefix)
            batch_set_props(props)

        except Exception as e:
            log("Service", f"Music video online artist fetch error: {e}", xbmc.LOGWARNING)
