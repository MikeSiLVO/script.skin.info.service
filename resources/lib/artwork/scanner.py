"""Library scanning for missing and upgraded artwork.

Scans Kodi library for items with missing artwork or quality upgrades available
from APIs. Builds queue for manual review or auto-processing.
"""
from __future__ import annotations

import xbmc
import xbmcaddon
from time import time
from typing import Optional, List, Tuple, Any, Sequence

from resources.lib import database as db
from resources.lib import task_manager
from resources.lib.kodi import request, extract_result, get_library_items
from resources.lib.utils import get_preferred_language_code, normalize_language_tag
from resources.lib.artwork.helpers import REVIEW_MODE_MISSING, REVIEW_MODE_BOTH, normalize_review_mode
from resources.lib.artwork.api_integration import ArtworkSourceFetcher
from resources.lib.ui_helper import ProgressDialogHelper
from resources.lib.kodi import log_artwork

ADDON = xbmcaddon.Addon()


class ArtScanner:
    """
    Scans library for missing artwork and quality upgrades, builds queue.

    Performance optimization: Uses batch fetching (fetch_all) to get ALL
    art types in a single API call per item, rather than separate calls
    per art type.
    """

    def __init__(self, scan_mode: str = REVIEW_MODE_MISSING, fetcher: Optional[ArtworkSourceFetcher] = None):
        """
        Initialize scanner.

        Args:
            scan_mode: Scanning mode - 'missing_only' or 'both' (missing + upgrades)
            fetcher: Optional artwork fetcher instance (for testing/injection)
        """
        normalized_mode = normalize_review_mode(scan_mode)
        self.scan_mode = normalized_mode
        self.include_missing = normalized_mode in (REVIEW_MODE_MISSING, REVIEW_MODE_BOTH)
        self.include_new = normalized_mode == REVIEW_MODE_BOTH
        self.preferred_language = get_preferred_language_code()
        self.cancelled = False
        self.progress = ProgressDialogHelper(use_background=False, heading="Artwork Review")
        self.scanned_count = 0
        self.queued_count = 0
        self.missing_count = 0
        self.upgrade_count = 0
        self._total_items: int = 0
        self._processed_items: int = 0
        self._scan_started_at: Optional[float] = None
        self._precache_prompt_shown: bool = False

        # Use provided fetcher or create default
        if fetcher:
            self.fetcher = fetcher
        else:
            from resources.lib.artwork.api_integration import create_default_fetcher
            self.fetcher = create_default_fetcher()

    def _wait_for_dialog_close(self, dialog_name: str, timeout_ms: int = 1000) -> None:
        """
        Wait for a Kodi dialog to fully close.

        Args:
            dialog_name: Name of dialog to wait for (e.g., "YesNoDialog", "ProgressDialog")
            timeout_ms: Maximum time to wait in milliseconds
        """
        waited = 0
        sleep_interval = 50

        while xbmc.getCondVisibility(f"Window.IsVisible({dialog_name})"):
            xbmc.sleep(sleep_interval)
            waited += sleep_interval
            if waited >= timeout_ms:
                xbmc.log(
                    f"SkinInfo Scanner: Timeout waiting for {dialog_name} to close",
                    xbmc.LOGWARNING
                )
                break

    def _begin_scan_progress(self) -> None:
        """Create a single progress dialog for the entire scan."""
        self.progress.create("Preparing library scan...")
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
        local_index: int,
        local_total: int,
        title: str,
        year: str,
        missing_art: Sequence[str],
        candidate_art: Sequence[str],
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

        if self.include_missing and self.include_new:
            line2 = f"Missing: {self.missing_count} items • Upgrades: {self.upgrade_count} items"
        elif self.include_missing:
            line2 = f"Missing: {self.missing_count} items queued"
        else:
            line2 = f"Upgrades: {self.upgrade_count} items queued"

        title_display = f"{title} ({year})" if year else title
        line3 = f"Scanning: {title_display}"

        message = f"{line1}[CR]{line2}[CR]{line3}"

        self.progress.update(percent, message)

    def scan_single_item(self, dbid: str, dbtype: str) -> bool:
        """
        Scan a single item for missing artwork.

        Args:
            dbid: Database ID of the item
            dbtype: Type of the item (movie, tvshow, episode, etc.)

        Returns:
            True if item was added to queue, False otherwise
        """
        from resources.lib.artwork.helpers import validate_media_type, validate_dbid

        if not validate_dbid(dbid):
            xbmc.log(f"SkinInfo Scanner: Invalid dbid: {dbid}", xbmc.LOGWARNING)
            return False

        if not validate_media_type(dbtype):
            xbmc.log(f"SkinInfo Scanner: Invalid media type: {dbtype}", xbmc.LOGWARNING)
            return False

        dbid_int = int(dbid)

        art_types = self._get_art_types_to_check(dbtype)

        if dbtype == "movie":
            items = request("VideoLibrary.GetMovieDetails", {
                "movieid": dbid_int,
                "properties": ["title", "art", "year"]
            })
            item = extract_result(items, "moviedetails") if items else None
        elif dbtype == "tvshow":
            items = request("VideoLibrary.GetTVShowDetails", {
                "tvshowid": dbid_int,
                "properties": ["title", "art", "year"]
            })
            item = extract_result(items, "tvshowdetails") if items else None
        elif dbtype == "episode":
            items = request("VideoLibrary.GetEpisodeDetails", {
                "episodeid": dbid_int,
                "properties": ["title", "art", "showtitle", "season", "episode"]
            })
            item = extract_result(items, "episodedetails") if items else None
        elif dbtype == "season":
            items = request("VideoLibrary.GetSeasonDetails", {
                "seasonid": dbid_int,
                "properties": ["title", "art", "season", "showtitle"]
            })
            item = extract_result(items, "seasondetails") if items else None
        elif dbtype == "musicvideo":
            items = request("VideoLibrary.GetMusicVideoDetails", {
                "musicvideoid": dbid_int,
                "properties": ["title", "artist", "art"]
            })
            item = extract_result(items, "musicvideodetails") if items else None
        elif dbtype == "artist":
            items = request("AudioLibrary.GetArtistDetails", {
                "artistid": dbid_int,
                "properties": ["artist", "art"]
            })
            item = extract_result(items, "artistdetails") if items else None
        elif dbtype == "album":
            items = request("AudioLibrary.GetAlbumDetails", {
                "albumid": dbid_int,
                "properties": ["title", "artist", "art", "year"]
            })
            item = extract_result(items, "albumdetails") if items else None
        else:
            return False

        if not isinstance(item, dict):
            return False

        current_art = item.get("art", {})
        missing_art_types: List[str] = []
        candidate_art_types: List[Tuple[str, str]] = []

        # PERFORMANCE FIX: Fetch ALL artwork types in ONE call
        available_artwork = {}
        if self.include_new and dbtype in ('movie', 'tvshow'):
            available_artwork = self.fetcher.fetch_all(dbtype, dbid_int)

        for art_type in art_types:
            current_url = current_art.get(art_type)

            if not current_url:
                if self.include_missing:
                    missing_art_types.append(art_type)
                continue

            if self.include_new and available_artwork:
                if self._check_for_upgrade(
                    dbtype, dbid_int, art_type,
                    current_url,
                    available_artwork.get(art_type, []),
                    self.preferred_language
                ):
                    candidate_art_types.append((art_type, current_url))

        if missing_art_types or candidate_art_types:
            title = item.get("title") or item.get("artist") or item.get("label", "Unknown")
            year = str(item.get("year", "")) if item.get("year") else ""
            scope_label = dbtype if dbtype else ''

            queue_id = db.add_to_queue(dbtype, dbid_int, title, year, scope=scope_label)
            for art_type in missing_art_types:
                db.add_art_item(
                    queue_id,
                    art_type,
                    baseline_url='',
                    review_mode=db.ARTITEM_REVIEW_MISSING,
                    requires_manual=False,
                    scan_session_id=None,
                )

            for art_type, baseline_url in candidate_art_types:
                db.add_art_item(
                    queue_id,
                    art_type,
                    baseline_url=baseline_url,
                    review_mode=db.ARTITEM_REVIEW_CANDIDATE,
                    requires_manual=True,
                    scan_session_id=None,
                )

            self.queued_count += 1
            return True

        return False

    def _check_for_upgrade(
        self,
        media_type: str,
        dbid: int,
        art_type: str,
        current_url: Optional[str],
        fresh_artwork: List[dict],
        language_filter: Optional[str] = None,
    ) -> bool:
        """
        Check if higher quality artwork is available compared to current Kodi artwork.

        Uses hybrid approach:
        1. Try texture cache for current artwork dimensions
        2. Fallback to URL matching in API results
        3. Skip upgrade check if neither works

        Args:
            media_type: Type of media (movie, tvshow, etc.)
            dbid: Database ID
            art_type: Art type to check (poster, fanart, etc.)
            current_url: URL of artwork currently set in Kodi
            fresh_artwork: Pre-fetched artwork list for this art type
            language_filter: Optional language code filter

        Returns:
            True if quality upgrade detected, False otherwise
        """
        try:
            if not fresh_artwork:
                return False

            if not current_url:
                return False

            from resources.lib.kodi import get_texture_dimensions

            filter_code = normalize_language_tag(language_filter)
            filtered_artwork = []
            for art in fresh_artwork:
                url = (art.get('url') or '').strip()
                if not url:
                    continue
                lang = normalize_language_tag(art.get('language'))
                if filter_code and lang != filter_code:
                    continue

                width = int(art.get('width', 0) or 0)
                height = int(art.get('height', 0) or 0)
                pixels = width * height

                rating = float(art.get('rating', 0) or 0)
                likes = int(art.get('likes', '0') or '0')
                popularity = rating if rating > 0 else likes
                source = art.get('source', 'unknown')

                filtered_artwork.append({
                    'url': url,
                    'pixels': pixels,
                    'rating': rating,
                    'likes': likes,
                    'popularity': popularity,
                    'source': source
                })

            if not filtered_artwork:
                return False

            baseline_pixels = 0
            baseline_rating = 0.0
            baseline_likes = 0

            current_width, current_height = get_texture_dimensions(current_url)
            if current_width and current_height:
                baseline_pixels = current_width * current_height
            else:
                for art in filtered_artwork:
                    if art['url'] == current_url:
                        baseline_pixels = art['pixels']
                        baseline_rating = art['rating']
                        baseline_likes = art['likes']
                        break

            if not baseline_pixels:
                return False

            best = max(filtered_artwork, key=lambda x: (x['pixels'], x['popularity']))

            is_upgrade = False

            if best['pixels'] >= baseline_pixels * 1.25:
                is_upgrade = True

            if best['rating'] > 0 and baseline_rating > 0:
                if best['rating'] >= baseline_rating + 0.5:
                    is_upgrade = True

            if best['likes'] > 0 and baseline_likes > 0:
                if best['likes'] >= baseline_likes + 10:
                    is_upgrade = True

            if is_upgrade:
                log_artwork(
                    f"Quality upgrade: {art_type} on {media_type} dbid {dbid} "
                    f"(pixels: {baseline_pixels}→{best['pixels']}, "
                    f"rating: {baseline_rating}→{best['rating']}, "
                    f"likes: {baseline_likes}→{best['likes']})"
                )
                return True

            return False

        except Exception as e:
            xbmc.log(f"SkinInfo Scanner: Error checking upgrade for {media_type} dbid {dbid}: {str(e)}", xbmc.LOGERROR)
            return False

    def scan(self, media_type: str, resume_session_id: Optional[int] = None) -> bool:
        """
        Scan library for missing artwork.

        Args:
            media_type: "movies", "tvshows", "music", "all", or "custom"
            resume_session_id: Optional session ID to resume from

        Returns:
            True if scan queued any results or was cancelled gracefully, False on fatal error
        """
        media_types = []
        if media_type in ("movies", "all"):
            media_types.append("movie")
        if media_type in ("tvshows", "all"):
            media_types.append("tvshow")
        if media_type == "music":
            media_types.extend(["artist", "album"])

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
                    lambda art_types=artist_art_types: self._scan_artists(art_types)
                ))

            if "album" in media_types:
                album_art_types = self._get_art_types_to_check("album")
                scan_steps.append((
                    'albums',
                    lambda art_types=album_art_types: self._scan_albums(art_types)
                ))

            for scope_label, runner in scan_steps:
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
            summary_line2 = f"Queued for review: {self.queued_count}"
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
        """
        Scan a collection of media items for missing artwork and upgrades.

        PERFORMANCE FIX: Fetches ALL artwork for an item in ONE API call
        before checking individual art types.
        """
        if not items:
            return True

        total = len(items)
        self._register_collection_total(total)

        queue_items: List[dict] = []
        art_items: List[dict] = []

        if self.include_new:
            from resources.lib.background_cache import BackgroundCacheQueue

            cacheable_urls: List[str] = []
            for item in items:
                current_art = item.get('art', {}) or {}
                for art_type in art_types:
                    current_url = current_art.get(art_type)
                    if current_url and current_url not in cacheable_urls:
                        cacheable_urls.append(current_url)

            if cacheable_urls and not self._precache_prompt_shown:
                self._precache_prompt_shown = True

                import xbmcgui
                dialog = xbmcgui.Dialog()

                self.progress.close()

                user_confirmed = dialog.yesno(
                    "Upgrade Detection",
                    f"Checking for artwork upgrades requires caching {len(cacheable_urls)} images "
                    f"to compare their quality with available artwork.[CR][CR]"
                    f"This may take awhile depending on amount of uncached textures. Continue?",
                    nolabel="Skip Upgrades",
                    yeslabel="Continue"
                )

                if user_confirmed != 1:
                    self.cancelled = True
                    return True

                self.progress.create("Pre-caching artwork...")
                cache_queue = BackgroundCacheQueue(check_cached=True)
                cache_queue.start()

                queued = cache_queue.bulk_add_urls(cacheable_urls)
                log_artwork(f"{progress_title}: pre-caching {queued} URLs for upgrade detection")

                if queued > 0:
                    precache_cancelled = False
                    try:
                        while not cache_queue.queue.empty() or cache_queue.processing_set:
                            if self.progress.is_cancelled():
                                precache_cancelled = True
                                break

                            progress = cache_queue.get_progress()
                            percent = min(10, int((progress['completed'] / progress['total']) * 10))
                            remaining = progress['total'] - progress['completed']
                            self.progress.update(
                                percent,
                                message=f"Pre-caching artwork for upgrade detection...[CR]{remaining} remaining"
                            )

                            xbmc.sleep(200)

                        if precache_cancelled:
                            queue_stats = cache_queue.get_stats()
                            completed = queue_stats['completed']
                            total = queue_stats['total_queued']

                            self.progress.close()

                            resume_bg = dialog.yesno(
                                "Pre-Cache Cancelled",
                                f"Pre-caching interrupted ({completed}/{total} completed).[CR][CR]"
                                f"Resume in background to enable upgrade detection,[CR]"
                                f"or cancel scan?",
                                nolabel="Cancel Scan",
                                yeslabel="Resume in BG"
                            )

                            if resume_bg:
                                if task_manager.is_task_running():
                                    self.cancelled = True
                                    return True

                                import threading

                                def monitor_background_cache():
                                    try:
                                        with task_manager.TaskContext("Pre-caching artwork") as ctx:
                                            bg_progress = ProgressDialogHelper(use_background=True, heading="Pre-Cache Artwork")
                                            bg_progress.create("Pre-caching artwork in background...")

                                            while not ctx.abort_flag.is_requested() and (not cache_queue.queue.empty() or cache_queue.processing_set):
                                                progress = cache_queue.get_progress()
                                                if progress['total'] > 0:
                                                    percent = int((progress['completed'] / progress['total']) * 100)
                                                    remaining = progress['total'] - progress['completed']
                                                    bg_progress.update(percent, f"{remaining} remaining")
                                                    ctx.mark_progress()
                                                xbmc.sleep(500)

                                            cache_queue.stop(wait=not ctx.abort_flag.is_requested())
                                            if not ctx.abort_flag.is_requested():
                                                queue_stats = cache_queue.get_stats()
                                                log_artwork(
                                                    f"Background pre-cache complete - "
                                                    f"{queue_stats['successful']} successful, {queue_stats['failed']} failed"
                                                )
                                            bg_progress.close()
                                    except Exception as e:
                                        xbmc.log(f"SkinInfo: Background pre-cache monitor error: {str(e)}", xbmc.LOGERROR)

                                monitor_thread = threading.Thread(target=monitor_background_cache, daemon=True)
                                monitor_thread.start()

                                self.cancelled = True
                                return True
                            else:
                                cache_queue.stop(wait=False)
                                self.cancelled = True
                                return True
                        else:
                            cache_queue.stop(wait=True)
                            queue_stats = cache_queue.get_stats()
                            log_artwork(
                                f"{progress_title}: pre-cache complete - "
                                f"{queue_stats['successful']} successful, {queue_stats['failed']} failed"
                            )

                    except Exception as e:
                        xbmc.log(f"SkinInfo: Pre-cache error in {progress_title}: {str(e)}", xbmc.LOGERROR)
                        try:
                            cache_queue.stop(wait=False)
                        except Exception:
                            pass

        for idx, item in enumerate(items):
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
            candidate_art_types: List[Tuple[str, str]] = []

            for art_type in art_types:
                current_url = current_art.get(art_type)
                if not current_url:
                    if self.include_missing:
                        missing_art_types.append(art_type)

            if self.include_missing and not self.include_new:
                if len(missing_art_types) == 0:
                    self._processed_items += 1
                    continue

                self.missing_count += 1

                art_requests = []
                for art_type in missing_art_types:
                    art_requests.append({
                        'art_type': art_type,
                        'baseline_url': '',
                        'review_mode': db.ARTITEM_REVIEW_MISSING,
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
                    local_index=idx + 1,
                    local_total=total,
                    title=title,
                    year=year,
                    missing_art=missing_art_types,
                    candidate_art=[],
                )

                self._processed_items += 1
                continue

            for art_type in art_types:
                current_url = current_art.get(art_type)
                if not current_url:
                    continue

                if self.include_new and self._check_needs_upgrade_local(art_type, current_url):
                    candidate_art_types.append((art_type, current_url))

            if missing_art_types:
                self.missing_count += 1

            if candidate_art_types:
                self.upgrade_count += 1

            self._update_scan_progress(
                progress_title=progress_title,
                local_index=idx + 1,
                local_total=total,
                title=title,
                year=year,
                missing_art=missing_art_types,
                candidate_art=[art_type for art_type, _ in candidate_art_types],
            )

            if not missing_art_types and not candidate_art_types:
                self._processed_items += 1
                continue

            art_requests = []
            for art_type in missing_art_types:
                art_requests.append({
                    'art_type': art_type,
                    'baseline_url': '',
                    'review_mode': db.ARTITEM_REVIEW_MISSING,
                    'requires_manual': False,
                })

            for art_type, baseline_url in candidate_art_types:
                art_requests.append({
                    'art_type': art_type,
                    'baseline_url': baseline_url,
                    'review_mode': db.ARTITEM_REVIEW_CANDIDATE,
                    'requires_manual': True,
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
                        'baseline_url': art_request.get('baseline_url', ''),
                        'current_url': art_request.get('baseline_url', ''),
                        'review_mode': art_request.get('review_mode', db.ARTITEM_REVIEW_MISSING),
                        'requires_manual': art_request.get('requires_manual', False),
                        'scan_session_id': session_id,
                    })

            if art_items:
                db.add_art_items_batch(art_items)

            self.queued_count += len(queue_items)

        log_artwork(f"{progress_title}: scanned {total}, queued {len(queue_items)} items ({len(art_items)} art types)")

        return not self.cancelled

    def _check_needs_upgrade_local(self, art_type: str, current_url: str) -> bool:
        """
        Check if artwork needs upgrade based on local texture cache dimensions.

        Uses quality thresholds without calling external APIs.

        Args:
            art_type: Type of artwork (poster, fanart, etc.)
            current_url: Current artwork URL

        Returns:
            True if below quality threshold and might benefit from upgrade
        """
        if not current_url:
            return False

        from resources.lib.kodi import get_texture_dimensions

        width, height = get_texture_dimensions(current_url)

        if not width or not height:
            return False

        quality_thresholds = {
            'fanart': (3840, 2160),
            'poster': (2000, 3000),
            'clearlogo': (800, 310),
            'clearart': (1000, 562),
            'banner': (1000, 185),
            'landscape': (1000, 562),
            'keyart': (2000, 3000),
            'characterart': (1000, 1000),
            'discart': (1000, 1000),
        }

        threshold = quality_thresholds.get(art_type)
        if not threshold:
            log_artwork(f"No threshold for {art_type}, flagging for upgrade")
            return True

        threshold_width, threshold_height = threshold
        needs_upgrade = width < threshold_width and height < threshold_height

        return needs_upgrade

    def _get_art_types_to_check(self, media_type: Optional[str] = None) -> List[str]:
        """
        Get art types to check from settings.

        Args:
            media_type: Optional media type to filter incompatible art types

        Returns:
            List of art types appropriate for the media type
        """
        setting_value = ADDON.getSetting("art_types_to_check")
        if setting_value:
            art_types = [t.strip() for t in setting_value.split(",") if t.strip()]
        else:
            defaults = {
                'movie': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'keyart'],
                'tvshow': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape'],
                'season': ['poster', 'banner', 'landscape', 'fanart'],
                'episode': ['thumb'],
                'musicvideo': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'keyart'],
                'artist': ['thumb', 'fanart', 'clearlogo', 'banner'],
                'album': ['thumb'],
            }
            art_types = defaults.get(media_type if media_type else 'movie', ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'keyart'])

        if media_type == "tvshow":
            art_types = [t for t in art_types if t != "keyart"]
        elif media_type == "season":
            supported = ['poster', 'banner', 'landscape', 'fanart']
            art_types = [t for t in art_types if t in supported]

        return art_types

    def _scan_movies(self, art_types: List[str], session_id: int, scope_label: str = 'movies') -> bool:
        """Scan movies for missing artwork."""
        try:
            movies = get_library_items(
                media_types=['movie'],
                properties=["title", "year", "art"],
                decode_urls=True
            )
        except Exception:
            return True

        if not movies:
            return True

        return self._scan_media_collection(
            items=movies,
            db_media_type='movie',
            id_key='movieid',
            title_key='label',
            year_key='year',
            art_types=art_types,
            session_id=session_id,
            scope_label=scope_label,
            progress_title="Scanning Movies",
        )

    def _scan_tvshows(self, art_types: List[str], session_id: int, scope_label: str = 'tvshows') -> bool:
        """Scan TV shows for missing artwork."""
        try:
            shows = get_library_items(
                media_types=['tvshow'],
                properties=["title", "year", "art"],
                decode_urls=True
            )
        except Exception:
            return True

        if not shows:
            return True

        return self._scan_media_collection(
            items=shows,
            db_media_type='tvshow',
            id_key='tvshowid',
            title_key='label',
            year_key='year',
            art_types=art_types,
            session_id=session_id,
            scope_label=scope_label,
            progress_title="Scanning TV Shows",
        )

    def _scan_seasons(self, art_types: List[str], session_id: int, scope_label: str = 'seasons') -> bool:
        """Scan all seasons for all TV shows for missing artwork."""
        try:
            all_items = get_library_items(
                media_types=['tvshow'],
                properties=["title", "art"],
                decode_urls=True,
                include_nested_seasons=True,
                season_properties=["title", "art", "season", "showtitle"]
            )
        except Exception:
            return True

        all_seasons = [item for item in all_items if item.get('media_type') == 'season']

        if not all_seasons:
            return True

        return self._scan_media_collection(
            items=all_seasons,
            db_media_type='season',
            id_key='seasonid',
            title_key='label',
            year_key=None,
            art_types=art_types,
            session_id=session_id,
            scope_label=scope_label,
            progress_title="Scanning Seasons",
        )

    def _scan_artists(self, art_types: List[str]) -> bool:
        """Scan artists for missing artwork (stub for future implementation)."""
        return True

    def _scan_albums(self, art_types: List[str]) -> bool:
        """Scan albums for missing artwork (stub for future implementation)."""
        return True
