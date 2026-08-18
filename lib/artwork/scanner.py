"""Library scanning for missing artwork.

Scans Kodi library for items with missing artwork from APIs.
Builds queue for manual review or auto-processing.
"""
from __future__ import annotations

import xbmc
from time import time
from typing import Optional, List, Tuple, Any, Sequence

from lib.data import database as db
from lib.kodi.client import get_library_items, LibraryScanAborted
from lib.kodi.settings import KodiSettings
from lib.kodi.utilities import get_preferred_language_code
from lib.artwork.config import REVIEW_MODE_MISSING, bulk_art_types
from lib.data.api.artwork import ApiArtworkFetcher
from lib.infrastructure.dialogs import ProgressDialog
from lib.kodi.client import log, ADDON


class ArtworkScanner:
    """Scans library for missing artwork, builds queue for review."""

    def __init__(self, fetcher: Optional[ApiArtworkFetcher] = None,
                 use_background: bool = False, abort_flag=None, task_context=None):
        self.scan_mode = REVIEW_MODE_MISSING
        self.preferred_language = get_preferred_language_code()
        self.cancelled = False
        self._abort_flag = abort_flag
        self._task_context = task_context
        self.progress = ProgressDialog(
            use_background=use_background, heading=ADDON.getLocalizedString(32273))
        self.progress.enable_throttling()
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

    def _cancel_requested(self) -> bool:
        """True if the scan dialog was cancelled or the owning task aborted."""
        if self._abort_flag is not None and self._abort_flag.is_requested():
            return True
        return self.progress.is_cancelled()

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

    def _update_fetch_progress(self, progress_title: str, done: int, total: int) -> None:
        """Keep the bar moving while library data is still being fetched (seasons are per-show)."""
        percent = min(100, int((done * 100) / total)) if total else 0
        self.progress.update(percent, f"{progress_title}[CR]Loading library: {done}/{total}")
        if self._task_context is not None:
            self._task_context.mark_progress()

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

    def scan(self, media_type: str) -> bool:
        """Scan a library scope for missing artwork; False only on fatal error."""
        media_types = []
        if media_type in ("movies", "all"):
            media_types.append("movie")
        if media_type in ("tvshows", "all"):
            media_types.extend(["tvshow", "season", "episode"])
        if media_type in ("musicvideos", "all"):
            media_types.append("musicvideo")
        if media_type in ("music", "all"):
            media_types.extend(["artist", "album"])

        self._sync_feed_changes(media_types)

        art_types_by_type = {mt: self._get_art_types_to_check(mt) for mt in media_types}
        all_art_types = sorted({at for types in art_types_by_type.values() for at in types})
        session_id = db.create_scan_session("missing_art", media_types, all_art_types)

        self._begin_scan_progress()

        had_failure = False

        try:
            scan_steps: List[Tuple[str, Any]] = []

            for scan_type in media_types:
                art_types = art_types_by_type[scan_type]
                if not art_types:
                    log("Artwork", f"No art types enabled for {scan_type}, skipping",
                        xbmc.LOGDEBUG)
                    continue

                scope_label = self._SCAN_CONFIGS[scan_type]['scope_label']
                scan_steps.append((
                    scope_label,
                    lambda mt=scan_type, at=art_types, label=scope_label: self._scan_collection(
                        mt, at, session_id, label)
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
            db.update_session_stats(session_id, stats)
            db.cancel_session(session_id)
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
            if self._cancel_requested():
                self.cancelled = True
                break

            self.scanned_count += 1
            if self._task_context is not None:
                self._task_context.mark_progress()

            title = item.get(title_key) or item.get('label') or 'Unknown'
            year_value = item.get(year_key) if year_key else ''
            year = str(year_value) if year_value else ''
            current_art = item.get('art', {}) or {}

            self._update_scan_progress(
                progress_title=progress_title,
                title=title,
                year=year,
            )

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

        log("Artwork",
            f"{progress_title}: scanned {total}, queued {len(queue_items)} items "
            f"({len(art_items)} art types)")

        return not self.cancelled

    def _sync_feed_changes(self, media_types: List[str]) -> None:
        """Ask fanart.tv what changed since the last scan so only those items are rechecked."""
        from lib.artwork.utilities import FEED_FOR_MEDIA, sync_feed_changes

        feeds = sorted({FEED_FOR_MEDIA[mt] for mt in media_types if mt in FEED_FOR_MEDIA})
        if not feeds:
            return

        try:
            sync_feed_changes(self.fetcher.fanart_api, feeds)
        except Exception as e:
            log("Artwork", f"Feed sync failed, scanning without it: {e}", xbmc.LOGWARNING)

    def _get_art_types_to_check(self, media_type: Optional[str] = None) -> List[str]:
        """Get art types to check from settings, filtered to those the media type can hold."""
        supported = bulk_art_types(media_type or 'movie')
        setting_value = KodiSettings.art_types_to_check()
        enabled = {art_type.strip() for art_type in setting_value.split(",") if art_type.strip()}
        return [art_type for art_type in supported if art_type in enabled]

    # Per-type scan configuration: properties to fetch, title/year keys, progress label.
    # Music sorts by artist so one artist's items queue together and share a single fetch.
    _SCAN_CONFIGS = {
        'movie': {
            'fetch_media_type': 'movie', 'id_key': 'movieid',
            'properties': ["title", "year", "art"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning Movies", 'scope_label': 'movies',
        },
        'tvshow': {
            'fetch_media_type': 'tvshow', 'id_key': 'tvshowid',
            'properties': ["title", "year", "art"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning TV Shows", 'scope_label': 'tvshows',
        },
        'season': {
            'fetch_media_type': 'season', 'id_key': 'seasonid',
            'properties': ["title", "art", "season", "showtitle", "tvshowid"],
            'title_key': 'label', 'year_key': None,
            'progress_title': "Scanning Seasons", 'scope_label': 'seasons',
        },
        'episode': {
            'fetch_media_type': 'episode', 'id_key': 'episodeid',
            'properties': ["title", "art", "season", "episode", "showtitle"],
            'title_key': 'label', 'year_key': None,
            'progress_title': "Scanning Episodes", 'scope_label': 'episodes',
        },
        'musicvideo': {
            'fetch_media_type': 'musicvideo', 'id_key': 'musicvideoid',
            'properties': ["title", "artist", "art", "year", "uniqueid"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning Music Videos", 'scope_label': 'musicvideos',
            'sort': {'method': 'artist', 'order': 'ascending'},
        },
        'artist': {
            'fetch_media_type': 'artist', 'id_key': 'artistid',
            'properties': ["art"],
            'title_key': 'artist', 'year_key': None,
            'progress_title': "Scanning Artists", 'scope_label': 'artists',
        },
        'album': {
            'fetch_media_type': 'album', 'id_key': 'albumid',
            'properties': ["title", "artist", "art", "year"],
            'title_key': 'label', 'year_key': 'year',
            'progress_title': "Scanning Albums", 'scope_label': 'albums',
            'sort': {'method': 'artist', 'order': 'ascending'},
        },
    }

    def _scan_collection(self, media_type: str, art_types: List[str], session_id: int,
                         scope_label: str) -> bool:
        cfg = self._SCAN_CONFIGS[media_type]
        progress_title = cfg['progress_title']
        try:
            kwargs = {
                'media_types': [cfg['fetch_media_type']],
                'properties': cfg['properties'],
                'decode_urls': True,
            }
            if cfg.get('sort'):
                kwargs['sort'] = cfg['sort']
            items = get_library_items(
                **kwargs,
                progress_callback=lambda _, done, total: self._update_fetch_progress(
                    progress_title, done, total),
                abort_check=self._cancel_requested,
            )
        except LibraryScanAborted:
            self.cancelled = True
            return False
        except Exception as e:
            log("Artwork", f"Error fetching {scope_label}: {e}", xbmc.LOGWARNING)
            return True

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


