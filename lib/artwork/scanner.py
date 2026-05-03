"""Library scanning for missing artwork.

Scans Kodi library for items with missing artwork from APIs.
Builds queue for manual review or auto-processing.
"""
from __future__ import annotations

import xbmc
from time import time
from typing import Optional, List, Tuple, Any, Sequence

from lib.data import database as db
from lib.kodi.client import get_item_details, get_library_items, KODI_GET_DETAILS_METHODS
from lib.kodi.settings import KodiSettings
from lib.kodi.utilities import get_preferred_language_code
from lib.artwork.config import REVIEW_MODE_MISSING
from lib.data.api.artwork import ApiArtworkFetcher
from lib.infrastructure.dialogs import ProgressDialog
from lib.kodi.client import log, ADDON


class ArtworkScanner:
    """Scans library for missing artwork, builds queue for review."""

    def __init__(self, fetcher: Optional[ApiArtworkFetcher] = None):
        self.scan_mode = REVIEW_MODE_MISSING
        self.preferred_language = get_preferred_language_code()
        self.cancelled = False
        self.progress = ProgressDialog(use_background=False, heading=ADDON.getLocalizedString(32273))
        self.scanned_count = 0
        self.queued_count = 0
        self.missing_count = 0
        self._total_items: int = 0
        self._processed_items: int = 0
        self._scan_started_at: Optional[float] = None

        if fetcher:
            self.fetcher = fetcher
        else:
            from lib.data.api.artwork import create_default_fetcher
            self.fetcher = create_default_fetcher()

    def _wait_for_dialog_close(self, dialog_name: str, timeout_ms: int = 1000) -> None:
        """Wait for a Kodi dialog to fully close."""
        monitor = xbmc.Monitor()
        waited = 0
        sleep_interval = 50

        while xbmc.getCondVisibility(f"Window.IsVisible({dialog_name})"):
            if monitor.waitForAbort(sleep_interval / 1000.0):
                break
            waited += sleep_interval
            if waited >= timeout_ms:
                break

    def _begin_scan_progress(self) -> None:
        """Create a single progress dialog for the entire scan."""
        self.progress.create(ADDON.getLocalizedString(32277))
        self._total_items = 0
        self._processed_items = 0
        self._scan_started_at = time()

    def _close_scan_progress(self, heading: str, line1: str, line2: str = "") -> None:
        """Update and close the shared scan progress dialog."""
        message = f"{heading}[CR]{line1}"
        if line2:
            message += f"[CR]{line2}"
        self.progress.update(100, message, force=True)
        self.progress.close()
        self._scan_started_at = None

    def _register_collection_total(self, count: int) -> None:
        """Add the items from a collection to the overall progress total."""
        if count > 0:
            self._total_items += count

    def _update_scan_progress(
        self,
        *,
        progress_title: str,
        title: str,
        year: str,
    ) -> None:
        """Update the shared progress dialog with overall status."""
        overall_index = self._processed_items + 1
        total_items = self._total_items or max(overall_index, 1)
        percent = min(100, int((overall_index * 100) / total_items))

        elapsed = time() - self._scan_started_at if self._scan_started_at else 0.01
        items_per_second = overall_index / elapsed if elapsed > 0 else 0
        remaining_items = total_items - overall_index
        eta_seconds = int(remaining_items / items_per_second) if items_per_second > 0 else 0

        if eta_seconds >= 60:
            eta_str = f"~{eta_seconds // 60}m"
        else:
            eta_str = f"~{eta_seconds}s"

        speed_str = f"{int(items_per_second)}/s" if items_per_second > 0 else "0/s"

        line1 = f"{overall_index}/{total_items} • {progress_title} • {speed_str} • ETA {eta_str}"
        line2 = f"Missing: {self.missing_count} items queued"
        title_display = f"{title} ({year})" if year else title
        line3 = f"Scanning: {title_display}"

        message = f"{line1}[CR]{line2}[CR]{line3}"

        self.progress.update(percent, message)

    # Properties needed per media type for scanning
    _SCAN_PROPERTIES = {
        'movie': ["title", "art", "year"],
        'tvshow': ["title", "art", "year"],
        'episode': ["title", "art", "showtitle", "season", "episode"],
        'season': ["title", "art", "season", "showtitle"],
        'musicvideo': ["title", "art", "artist"],
        'artist': ["artist", "art"],
        'album': ["title", "artist", "art", "year"],
        'set': ["title", "art"],
    }

    def scan_single_item(self, dbid: str, dbtype: str) -> bool:
        """Scan a single item for missing artwork. Returns True if added to queue."""
        from lib.artwork.config import validate_media_type, validate_dbid

        if not validate_dbid(dbid):
            log("Artwork", f"Scanner: Invalid dbid: {dbid}", xbmc.LOGWARNING)
            return False

        if not validate_media_type(dbtype):
            log("Artwork", f"Scanner: Invalid media type: {dbtype}", xbmc.LOGWARNING)
            return False

        if dbtype not in KODI_GET_DETAILS_METHODS:
            return False

        dbid_int = int(dbid)
        art_types = self._get_art_types_to_check(dbtype)
        properties = self._SCAN_PROPERTIES.get(dbtype, ["title", "art"])

        item = get_item_details(dbtype, dbid_int, properties)
        if not isinstance(item, dict):
            return False

        current_art = item.get("art", {})
        missing_art_types: List[str] = []

        for art_type in art_types:
            current_url = current_art.get(art_type)
            if not current_url:
                missing_art_types.append(art_type)

        if missing_art_types:
            title = item.get("title") or item.get("artist") or item.get("label", "Unknown")
            year = str(item.get("year", "")) if item.get("year") else ""
            scope_label = dbtype if dbtype else ''

            queue_id = db.add_to_queue(dbtype, dbid_int, title, year, scope=scope_label)
            for art_type in missing_art_types:
                db.add_art_item(
                    queue_id,
                    art_type,
                    requires_manual=False,
                    scan_session_id=None,
                )

            self.queued_count += 1
            return True

        return False

    def scan(self, media_type: str, resume_session_id: Optional[int] = None) -> bool:
        """Scan library for missing artwork.

        Args:
            media_type: "movies", "tvshows", "music", or "all".
            resume_session_id: Optional session ID to resume from.

        Returns:
            True if scan queued any results or was cancelled gracefully, False on fatal error.
        """
        media_types = []
        if media_type in ("movies", "all"):
            media_types.append("movie")
        if media_type in ("tvshows", "all"):
            media_types.append("tvshow")
        if media_type in ("music", "all"):
            media_types.append("artist")
            media_types.append("album")

        if resume_session_id:
            session_id = resume_session_id
        else:
            all_art_types = self._get_art_types_to_check()
            session_id = db.create_scan_session("missing_art", media_types, all_art_types)

        self._begin_scan_progress()

        had_failure = False

        try:
            scan_steps: List[Tuple[str, Any]] = []

            if "movie" in media_types:
                movie_art_types = self._get_art_types_to_check("movie")
                scan_steps.append((
                    'movies',
                    lambda art_types=movie_art_types: self._scan_movies(art_types, session_id, scope_label='movies')
                ))

            if "tvshow" in media_types:
                tvshow_art_types = self._get_art_types_to_check("tvshow")
                scan_steps.append((
                    'tvshows',
                    lambda art_types=tvshow_art_types: self._scan_tvshows(art_types, session_id, scope_label='tvshows')
                ))

                season_art_types = self._get_art_types_to_check("season")
                scan_steps.append((
                    'seasons',
                    lambda art_types=season_art_types: self._scan_seasons(art_types, session_id, scope_label='seasons')
                ))

            if "artist" in media_types:
                artist_art_types = self._get_art_types_to_check("artist")
                scan_steps.append((
                    'artists',
                    lambda art_types=artist_art_types: self._scan_artists(art_types, session_id, scope_label='artists')
                ))

            if "album" in media_types:
                album_art_types = self._get_art_types_to_check("album")
                scan_steps.append((
                    'albums',
                    lambda art_types=album_art_types: self._scan_albums(art_types, session_id, scope_label='albums')
                ))

            for _, runner in scan_steps:
                if self.cancelled:
                    break

                result = runner()
                if not result:
                    if self.cancelled:
                        break
                    had_failure = True
                    break
        finally:
            summary_heading = "Scan cancelled" if self.cancelled else "Scan complete"
            summary_line1 = f"Items scanned: {self.scanned_count}"
            summary_line2 = f"Queued for selection: {self.queued_count}"
            self._close_scan_progress(summary_heading, summary_line1, summary_line2)

        stats = {
            'scanned': self.scanned_count,
            'queued': self.queued_count
        }

        if self.cancelled:
            db.pause_session(session_id, stats)
            return True

        db.update_session_stats(session_id, stats)

        if had_failure:
            db.cancel_session(session_id)
            return False

        db.complete_session(session_id)
        return True

    def _scan_media_collection(
        self,
        *,
        items: Sequence[dict],
        db_media_type: str,
        id_key: str,
        title_key: str,
        year_key: Optional[str],
        art_types: Sequence[str],
        session_id: int,
        scope_label: str,
        progress_title: str,
    ) -> bool:
        """Scan a collection of media items for missing artwork."""
        if not items:
            return True

        total = len(items)
        self._register_collection_total(total)

        queue_items: List[dict] = []
        art_items: List[dict] = []

        for item in items:
            if self.progress.is_cancelled():
                self.cancelled = True
                break

            self.scanned_count += 1

            title = item.get(title_key) or item.get('label') or 'Unknown'
            year_value = item.get(year_key) if year_key else ''
            year = str(year_value) if year_value else ''
            current_art = item.get('art', {}) or {}

            dbid_value = item.get(id_key)
            if dbid_value is None:
                self._processed_items += 1
                continue
            try:
                dbid_value = int(dbid_value)
            except (TypeError, ValueError):
                self._processed_items += 1
                continue

            missing_art_types: List[str] = []

            for art_type in art_types:
                current_url = current_art.get(art_type)
                if not current_url:
                    missing_art_types.append(art_type)

            if not missing_art_types:
                self._processed_items += 1
                continue

            self.missing_count += 1

            art_requests = []
            for art_type in missing_art_types:
                art_requests.append({
                    'art_type': art_type,
                    'requires_manual': False,
                })

            queue_items.append({
                'media_type': db_media_type,
                'dbid': dbid_value,
                'title': title,
                'year': year,
                'scope': scope_label,
                'scan_session_id': session_id,
                'art_requests': art_requests,
            })

            self._update_scan_progress(
                progress_title=progress_title,
                title=title,
                year=year,
            )

            self._processed_items += 1

        if queue_items:
            queue_ids = db.add_to_queue_batch(queue_items)
            for queue_id, item in zip(queue_ids, queue_items):
                for art_request in item['art_requests']:
                    art_items.append({
                        'queue_id': queue_id,
                        'art_type': art_request['art_type'],
                        'requires_manual': art_request.get('requires_manual', False),
                        'scan_session_id': session_id,
                    })

            if art_items:
                db.add_art_items_batch(art_items)

            self.queued_count += len(queue_items)

        log("Artwork", f"{progress_title}: scanned {total}, queued {len(queue_items)} items ({len(art_items)} art types)")

        return not self.cancelled

    def _get_art_types_to_check(self, media_type: Optional[str] = None) -> List[str]:
        """Get art types to check from settings, filtered to those compatible with media_type."""
        setting_value = KodiSettings.art_types_to_check()
        if setting_value:
            art_types = [t.strip() for t in setting_value.split(",") if t.strip()]
        else:
            defaults = {
                'movie': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'discart', 'keyart'],
                'tvshow': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'characterart', 'keyart'],
                'season': ['poster', 'banner', 'landscape', 'fanart'],
                'episode': ['thumb'],
                'musicvideo': ['thumb', 'fanart'],
                'set': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'discart', 'keyart'],
                'artist': ['thumb', 'fanart', 'clearlogo', 'banner'],
                'album': ['thumb', 'discart'],
            }
            art_types = defaults.get(media_type if media_type else 'movie', ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'discart', 'keyart'])

        if media_type == "season":
            supported = ['poster', 'banner', 'landscape', 'fanart']
            art_types = [t for t in art_types if t in supported]

        return art_types

    # Per-type scan configuration: properties to fetch, title/year keys, progress label.
    # Seasons fetch via tvshow with nested seasons enabled.
    _SCAN_CONFIGS = {
        'movie': {
            'fetch_media_type': 'movie', 'id_key': 'movieid',
            'properties': ["title", "year", "art"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning Movies",
        },
        'tvshow': {
            'fetch_media_type': 'tvshow', 'id_key': 'tvshowid',
            'properties': ["title", "year", "art"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning TV Shows",
        },
        'season': {
            'fetch_media_type': 'tvshow', 'id_key': 'seasonid',
            'properties': ["title", "art"],
            'title_key': 'label', 'year_key': None,
            'progress_title': "Scanning Seasons",
            'include_nested_seasons': True,
            'season_properties': ["title", "art", "season", "showtitle"],
            'filter_after_fetch': 'season',
        },
        'artist': {
            'fetch_media_type': 'artist', 'id_key': 'artistid',
            'properties': ["artist", "art"],
            'title_key': 'artist', 'year_key': None,
            'progress_title': "Scanning Artists",
        },
        'album': {
            'fetch_media_type': 'album', 'id_key': 'albumid',
            'properties': ["title", "artist", "art", "year"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning Albums",
        },
    }

    def _scan_collection(self, media_type: str, art_types: List[str], session_id: int,
                         scope_label: str) -> bool:
        cfg = self._SCAN_CONFIGS[media_type]
        try:
            kwargs = {
                'media_types': [cfg['fetch_media_type']],
                'properties': cfg['properties'],
                'decode_urls': True,
            }
            if cfg.get('include_nested_seasons'):
                kwargs['include_nested_seasons'] = True
                kwargs['season_properties'] = cfg['season_properties']
            items = get_library_items(**kwargs)
        except Exception as e:
            log("Artwork", f"Error fetching {scope_label}: {e}", xbmc.LOGWARNING)
            return True

        post_filter = cfg.get('filter_after_fetch')
        if post_filter:
            items = [it for it in items if it.get('media_type') == post_filter]

        if not items:
            return True

        return self._scan_media_collection(
            items=items,
            db_media_type=media_type,
            id_key=cfg['id_key'],
            title_key=cfg['title_key'],
            year_key=cfg['year_key'],
            art_types=art_types,
            session_id=session_id,
            scope_label=scope_label,
            progress_title=cfg['progress_title'],
        )

    def _scan_movies(self, art_types: List[str], session_id: int, scope_label: str = 'movies') -> bool:
        return self._scan_collection('movie', art_types, session_id, scope_label)

    def _scan_tvshows(self, art_types: List[str], session_id: int, scope_label: str = 'tvshows') -> bool:
        return self._scan_collection('tvshow', art_types, session_id, scope_label)

    def _scan_seasons(self, art_types: List[str], session_id: int, scope_label: str = 'seasons') -> bool:
        return self._scan_collection('season', art_types, session_id, scope_label)

    def _scan_artists(self, art_types: List[str], session_id: int, scope_label: str = 'artists') -> bool:
        return self._scan_collection('artist', art_types, session_id, scope_label)

    def _scan_albums(self, art_types: List[str], session_id: int, scope_label: str = 'albums') -> bool:
        return self._scan_collection('album', art_types, session_id, scope_label)

