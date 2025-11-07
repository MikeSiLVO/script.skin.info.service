"""Artwork review workflows for manual review and auto-processing.

Contains:
- ArtReviewer: Manual review workflow
- ArtworkReviewManager: Workflow coordinator

Core functionality is in the artwork package (scanner, processor, api_integration).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import database as db
from resources.lib.database import queue
from resources.lib.kodi import request, extract_result, KODI_GET_DETAILS_METHODS
from resources.lib.dialogs.artwork_selection import show_artwork_selection_dialog
from resources.lib.workflows.queue_repository import ArtQueueRepository, QueueEntry, ArtItemEntry
from resources.lib.kodi import log_artwork
from resources.lib.ui_helper import show_menu_with_cancel

# Import from new artwork package
from resources.lib.artwork.helpers import (
    REVIEW_SCOPE_OPTIONS,
    REVIEW_SCOPE_LABELS,
    REVIEW_MEDIA_FILTERS,
    REVIEW_SCAN_MAP,
    REVIEW_MODE_MISSING,
    REVIEW_MODE_BOTH,
    SESSION_DETAIL_KEYS,
    normalize_review_mode as _normalize_review_mode,
    default_session_stats as _default_session_stats,
    load_session_stats as _load_session_stats,
    serialise_session_stats as _serialise_session_stats,
)
from resources.lib.artwork.scanner import ArtScanner

ADDON = xbmcaddon.Addon()


def _count_pending_for_scope(pending_counts: Dict[str, int], scope: str) -> int:
    """Return total pending items for a given review scope."""
    if scope == 'all':
        return sum(pending_counts.values())
    media_types = REVIEW_MEDIA_FILTERS.get(scope, [])
    return sum(pending_counts.get(mt, 0) for mt in media_types)


def _scan_scope(scope: str, scan_mode: str = REVIEW_MODE_MISSING) -> Optional[ArtScanner]:
    """Run artwork scanner for the selected scope and return the scanner on success."""

    scan_target = REVIEW_SCAN_MAP.get(scope, scope)
    normalized_mode = _normalize_review_mode(scan_mode)
    scanner = ArtScanner(normalized_mode)
    log_artwork(f"Running scan for scope '{scope}' (mode={normalized_mode})")
    result = scanner.scan(scan_target)
    if not result:
        xbmcgui.Dialog().ok(
            "Artwork Review",
            "Scan failed."
        )
        return None
    return scanner


def run_art_fetcher(media_type: Optional[str] = None, dbid: Optional[str] = None, dbtype: Optional[str] = None) -> None:
    """
    Legacy entry point retained for compatibility. Delegates to the artwork reviewer workflow.
    """
    if media_type == "single" or (dbid and dbtype):
        run_art_fetcher_single(dbid, dbtype)
        return

    if media_type:
        run_art_reviewer(media_type)
    else:
        run_art_reviewer()


def _show_session_report(session_row) -> None:
    """
    Display a report for a review session.

    Args:
        session_row: Database row from scan_sessions table
    """
    stats = json.loads(session_row['stats']) if session_row['stats'] else {}
    applied = int(stats.get('applied', 0) or 0)
    skipped = int(stats.get('skipped', 0) or 0)
    auto = int(stats.get('auto', 0) or 0)
    remaining = stats.get('remaining')
    details = stats.get('details')
    if not isinstance(details, dict):
        details = {}
    auto_runs = stats.get('auto_runs')
    if not isinstance(auto_runs, list):
        auto_runs = []

    started = session_row['started']
    last_activity = session_row['last_activity']
    status = session_row['status']
    completed = session_row['completed']

    def _shorten(value: Optional[str], max_len: int = 80) -> str:
        if not value:
            return ''
        if len(value) <= max_len:
            return value
        return value[:max_len - 3] + "..."

    def _append_detail_section(
        lines: List[str],
        header: str,
        entries: List[Dict[str, Any]],
        formatter,
        *,
        indent: str = "    ",
        max_items: int = 20
    ) -> None:
        valid_entries = [entry for entry in entries if isinstance(entry, dict)]
        if not valid_entries:
            return
        lines.append(header)
        to_show = min(max_items, len(valid_entries))
        for entry in valid_entries[:to_show]:
            lines.append(f"{indent}• {formatter(entry)}")
        if len(valid_entries) > max_items:
            lines.append(f"{indent}… {len(valid_entries) - max_items} more")
        lines.append("")

    def _format_entry(
        entry: Dict[str, Any],
        *,
        include_art_type: bool = True,
        include_source: bool = False,
        include_url: bool = False,
        include_reason: bool = False
    ) -> str:
        title = entry.get('title', 'Unknown')
        parts = [title]

        if include_art_type:
            art_type = entry.get('art_type', '?')
            parts[0] = f"{title} – {art_type}"

        if include_source:
            source = entry.get('source')
            if source:
                parts.append(f"[{source}]")

        if include_url:
            url = entry.get('url', '')
            if url:
                parts.append(_shorten(url, 70))

        if include_reason:
            reason = entry.get('reason', 'skipped')
            parts.append(f"({reason})")

        return " ".join(parts)

    def _format_manual_applied(entry: Dict[str, Any]) -> str:
        return _format_entry(entry, include_art_type=True, include_source=True, include_url=True)

    def _format_manual_skipped(entry: Dict[str, Any]) -> str:
        return _format_entry(entry, include_art_type=True, include_reason=True)

    def _format_auto_run_applied(entry: Dict[str, Any]) -> str:
        return _format_entry(entry, include_art_type=True, include_url=True)

    def _format_auto_run_skipped(entry: Dict[str, Any]) -> str:
        return _format_entry(entry, include_art_type=False, include_reason=True)

    session_id = session_row['id']
    session_art_types = db.get_session_art_types(session_id)
    art_types_str = ', '.join(session_art_types) if session_art_types else 'all'

    lines = []
    lines.append("=" * 50)
    lines.append("ARTWORK REVIEW SESSION REPORT")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Status: {status.upper()}")
    lines.append(f"Started: {started}")
    lines.append(f"Last Activity: {last_activity}")
    if status == 'completed' and completed:
        lines.append(f"Completed: {completed}")
    elif status == 'cancelled':
        lines.append(f"Cancelled: {last_activity}")
    lines.append(f"Art Types: {art_types_str}")
    lines.append("")
    lines.append("Statistics:")
    lines.append(f"  Manual Reviewed: {applied + skipped}")
    lines.append(f"    Applied: {applied}")
    lines.append(f"    Skipped: {skipped}")
    lines.append(f"  Auto-Skipped: {auto}")
    if remaining is not None:
        media_types = db.get_session_media_types(session_id)
        missing_count = db.count_pending_missing_art(media_types) if media_types else 0
        if missing_count > 0:
            lines.append(f"  Remaining Pending: {remaining} ({missing_count} missing artwork)")
        else:
            lines.append(f"  Remaining Pending: {remaining}")
    lines.append("")

    manual_applied = details.get('manual_applied', [])
    manual_skipped = details.get('manual_skipped', [])
    manual_auto = details.get('manual_auto', [])
    stale_entries = details.get('stale', [])

    _append_detail_section(
        lines,
        "Manual Applied:",
        manual_applied,
        _format_manual_applied
    )
    _append_detail_section(
        lines,
        "Manual Skipped:",
        manual_skipped,
        _format_manual_skipped
    )
    _append_detail_section(
        lines,
        "Auto-Skipped During Review:",
        manual_auto,
        _format_manual_skipped
    )
    _append_detail_section(
        lines,
        "Stale Items (baseline changed during review):",
        stale_entries,
        _format_manual_skipped
    )

    if auto_runs:
        lines.append("Auto Fetch Runs:")
        for idx, run in enumerate(auto_runs, start=1):
            timestamp = run.get('timestamp')
            if isinstance(timestamp, str):
                ts_display = timestamp.replace('T', ' ')
            else:
                ts_display = "unknown"
            counts = run.get('counts', {})
            processed = counts.get('processed', 0)
            auto_applied = counts.get('auto_applied', 0)
            skipped_auto = counts.get('skipped', 0)
            errors = counts.get('errors', 0)
            pending_after = run.get('pending_after', 'n/a')
            lines.append(f"  Run #{idx} ({ts_display})")
            lines.append(
                f"    Processed: {processed} | Applied: {auto_applied} | Skipped: {skipped_auto} | Errors: {errors}"
            )
            lines.append(f"    Remaining after run: {pending_after}")
            _append_detail_section(
                lines,
                "    Applied:",
                run.get('applied', []),
                _format_auto_run_applied,
                indent="      ",
                max_items=15
            )
            _append_detail_section(
                lines,
                "    Skipped:",
                run.get('skipped', []),
                _format_auto_run_skipped,
                indent="      ",
                max_items=15
            )
        lines.append("")

    lines.append("=" * 50)

    # Show report
    text = "\n".join(lines)
    xbmcgui.Dialog().textviewer("Review Session Report", text)


def run_art_fetcher_single(dbid: Optional[str], dbtype: Optional[str]) -> None:
    """
    Open artwork selection dialog for a single item.

    Args:
        dbid: Database ID of the item (if None, will get from ListItem)
        dbtype: Type of the item (movie, tvshow, episode, etc.)
    """
    if not dbid:
        dbid = xbmc.getInfoLabel("ListItem.DBID")
    if not dbtype:
        dbtype = xbmc.getInfoLabel("ListItem.DBType")

    if not dbid or dbid == "-1" or not dbtype:
        xbmcgui.Dialog().notification(
            "Artwork",
            "No valid item selected",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    dbtype_lower = dbtype.lower()
    dbid_int = int(dbid)

    art_type_options = {
        'movie': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'keyart'],
        'tvshow': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape'],
        'season': ['poster', 'banner', 'landscape', 'fanart'],
        'episode': ['thumb'],
        'musicvideo': ['poster', 'fanart', 'clearlogo', 'clearart', 'banner', 'landscape', 'keyart'],
    }

    art_types = art_type_options.get(dbtype_lower)
    if not art_types:
        xbmcgui.Dialog().notification(
            "Artwork",
            f"Unsupported media type: {dbtype}",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    method_info = KODI_GET_DETAILS_METHODS.get(dbtype_lower)
    if not method_info:
        xbmcgui.Dialog().notification(
            "Artwork",
            f"Unsupported media type: {dbtype}",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    method_name, id_key, result_key = method_info

    properties = ["title", "art"]
    if dbtype_lower in ('movie', 'tvshow', 'musicvideo'):
        properties.append("year")

    details = extract_result(
        request(method_name, {id_key: dbid_int, "properties": properties}),
        result_key
    )

    if not details:
        xbmcgui.Dialog().notification(
            "Artwork",
            f"{dbtype.title()} not found",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    title = details.get("title", "Unknown")
    year = details.get("year", "")
    current_art = details.get("art", {})

    from resources.lib.artwork.api_integration import create_default_fetcher, validate_api_keys
    from resources.lib.artwork.processor import ArtProcessor

    fetcher = create_default_fetcher()
    if not validate_api_keys(fetcher.tmdb_api, fetcher.fanart_api):
        return

    processor = ArtProcessor(source_fetcher=fetcher, use_background=False)

    xbmcgui.Dialog().notification(
        "Artwork",
        "Fetching artwork...",
        xbmcgui.NOTIFICATION_INFO,
        2000
    )

    try:
        all_artwork = fetcher.fetch_all(dbtype_lower, dbid_int)
    except Exception as e:
        xbmc.log(f"SkinInfo [Artwork]: Error fetching artwork: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Artwork",
            "Failed to fetch artwork",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        return

    available_by_type = {art_type: all_artwork.get(art_type, []) for art_type in art_types if all_artwork.get(art_type)}

    if not available_by_type:
        xbmcgui.Dialog().notification(
            "Artwork",
            "No artwork found",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return

    art_type_labels = [f"{art_type.capitalize()} ({len(available_by_type[art_type])})"
                       for art_type in art_types if art_type in available_by_type]

    from resources.lib.art_helpers import filter_artwork_by_language

    while True:
        selected = xbmcgui.Dialog().select(f"Select Artwork Type - {title}", art_type_labels)

        if selected < 0:
            return

        selected_art_type = [art_type for art_type in art_types if art_type in available_by_type][selected]
        full_artwork_list = available_by_type[selected_art_type]

        filtered_art = filter_artwork_by_language(full_artwork_list, art_type=selected_art_type)

        current_url = current_art.get(selected_art_type, "")

        action, selected_art = show_artwork_selection_dialog(
            title=title,
            art_type=selected_art_type,
            available_art=filtered_art,
            full_artwork_list=full_artwork_list,
            media_type=dbtype_lower,
            year=str(year) if year else "",
            current_url=current_url,
            dbid=dbid_int
        )

        if action == "cancel":
            continue

        if action == "selected" and selected_art:
            processor._apply_art(dbtype_lower, dbid_int, {selected_art_type: selected_art.get("url")})
            xbmc.executebuiltin("Container.Refresh")
            xbmcgui.Dialog().notification(
                "Artwork",
                f"{selected_art_type.capitalize()} updated",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return

        elif action == "multiart" and selected_art:
            processor._apply_art(dbtype_lower, dbid_int, selected_art)
            xbmc.executebuiltin("Container.Refresh")
            xbmcgui.Dialog().notification(
                "Artwork",
                "Artwork updated",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return

        elif action == "skip":
            return


class ArtReviewer:
    """Handle manual review of artwork choices."""

    def __init__(
        self,
        session_id: Optional[int] = None,
        media_filter: Optional[List[str]] = None,
        review_mode: str = REVIEW_MODE_BOTH,
        enable_download: bool = False,
    ):

        from resources.lib.artwork.api_integration import create_default_fetcher
        from resources.lib.ui_helper import ProgressDialogHelper
        from resources.lib.artwork.processor import ArtProcessor

        fetcher = create_default_fetcher()
        self.processor = ArtProcessor(source_fetcher=fetcher, enable_download=enable_download)
        self.session_id = session_id  # Resume existing session or None for new
        self.stats = {'applied': 0, 'skipped': 0, 'auto': 0}
        self.media_filter = media_filter or None
        self.repo = ArtQueueRepository()
        self.review_mode = _normalize_review_mode(review_mode)
        self.review_log: Dict[str, List[Dict[str, Any]]] = {key: [] for key in SESSION_DETAIL_KEYS}
        self.remaining_pending: int = 0
        self.loading_progress = ProgressDialogHelper(use_background=False, heading="Artwork Review")
        self.enable_download = enable_download

    def _build_stats_payload(self) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot of review statistics and details."""
        payload = _default_session_stats()

        if self.session_id:
            session_row = db.get_session(self.session_id)
            if session_row and session_row['stats']:
                try:
                    existing_stats = json.loads(session_row['stats'])
                    if 'scanned' in existing_stats:
                        payload['scanned'] = existing_stats['scanned']
                    if 'queued' in existing_stats:
                        payload['queued'] = existing_stats['queued']
                except Exception:
                    pass

        payload['applied'] = self.stats['applied']
        payload['skipped'] = self.stats['skipped']
        payload['auto'] = self.stats['auto']
        payload['remaining'] = self.remaining_pending
        payload['review_mode'] = self.review_mode
        payload['details'] = {
            key: [dict(entry) for entry in self.review_log.get(key, [])]
            for key in SESSION_DETAIL_KEYS
        }
        return payload

    def review_queue(self) -> Optional[Dict[str, Any]]:
        """
        Review pending items with visual artwork selection.
        Drains the queue in batches and validates each item before prompting.

        Returns:
            Dict with keys: status, cancelled, session_id, remaining, stats
            None if queue is empty
        """
        self.repo.prune_inactive_queue()
        pending_check = self.repo.get_queue_batch(
            limit=1,
            status='pending',
            media_types=self.media_filter,
        )

        if not pending_check:
            return

        enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
        if enable_debug:
            pending_count = len(self.repo.get_queue_batch(limit=1000, status='pending', media_types=self.media_filter))
            log_artwork(f"Manual review starting: {pending_count} pending items, media_filter={self.media_filter}")

        self._initialize_session()
        assert self.session_id is not None

        cancelled = False
        self.loading_progress.create("Artwork Review")

        try:
            while not cancelled:
                queue_batch = self.repo.get_queue_batch(
                    limit=25,
                    status='pending',
                    media_types=self.media_filter,
                )

                if not queue_batch:
                    break

                queue_ids = [entry.id for entry in queue_batch]
                art_items_by_queue = self.repo.get_art_items_batch(queue_ids)

                for queue_entry in queue_batch:
                    art_items = art_items_by_queue.get(queue_entry.id, [])
                    pending_art, current_art = self._collect_pending_art_items(queue_entry, art_items)
                    if not pending_art:
                        continue

                    result = self._review_single_item(queue_entry, pending_art, current_art)

                    if result == 'cancel':
                        cancelled = True
                        break
                    elif result == 'applied':
                        self.stats['applied'] += 1
                    elif result == 'skipped':
                        self.stats['skipped'] += 1
                    elif result == 'auto':
                        self.stats['auto'] += 1

                    db.update_session_stats(self.session_id, _serialise_session_stats(self._build_stats_payload()))
        finally:
            self.loading_progress.close()

        enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
        if enable_debug:
            status = "cancelled" if cancelled else "complete"
            log_artwork(
                f"Manual review {status}: applied={self.stats['applied']}, skipped={self.stats['skipped']}, "
                f"auto={self.stats.get('auto', 0)}, session={self.session_id}"
            )

        applied_count = self.stats['applied']
        skipped_count = self.stats['skipped']
        auto_count = self.stats.get('auto', 0)
        manual_total = applied_count + skipped_count
        remaining = queue.count_queue_items(
            status='pending',
            media_types=self.media_filter,
        )
        self.remaining_pending = remaining

        if cancelled:
            db.pause_session(self.session_id, _serialise_session_stats(self._build_stats_payload()))
            heading = f"Artwork Review Paused: manual {manual_total} (applied {applied_count}, skipped {skipped_count})"
            message = f"Auto-skipped: {auto_count}, Remaining: {remaining}"
            xbmcgui.Dialog().notification(heading, message, xbmcgui.NOTIFICATION_INFO, 5000)
        else:
            db.update_session_stats(self.session_id, _serialise_session_stats(self._build_stats_payload()))
            db.complete_session(self.session_id)
            heading = f"Artwork Review Complete: manual {manual_total} (applied {applied_count}, skipped {skipped_count})"
            message = f"Auto-skipped: {auto_count}"
            xbmcgui.Dialog().notification(heading, message, xbmcgui.NOTIFICATION_INFO, 5000)

        outcome = {
            'status': 'paused' if cancelled else 'completed',
            'cancelled': cancelled,
            'session_id': self.session_id,
            'remaining': remaining,
            'stats': self._build_stats_payload()
        }

        self.repo.prune_inactive_queue()
        return outcome

    def _initialize_session(self) -> None:
        """Create or resume the manual review session."""
        if not self.session_id:
            self.session_id = db.create_scan_session(
                scan_type='manual_review',
                media_types=self.media_filter or [],
                art_types=[]
            )
            log_artwork(f"Created review session {self.session_id}")
            return

        log_artwork(f"Resuming review session {self.session_id}")

        paused_sessions = [
            s for s in db.get_paused_sessions()
            if s['scan_type'] == 'manual_review'
        ]
        for session in paused_sessions:
            if session['id'] == self.session_id:
                saved_stats = _load_session_stats(session['stats'])
                self.stats['applied'] = saved_stats['applied']
                self.stats['skipped'] = saved_stats['skipped']
                self.stats['auto'] = saved_stats['auto']
                self.review_mode = _normalize_review_mode(saved_stats['review_mode'])
                self.review_log = {
                    key: [dict(entry) for entry in saved_stats['details'].get(key, [])]
                    for key in SESSION_DETAIL_KEYS
                }
                self.remaining_pending = saved_stats['remaining']
                stored_types = db.get_session_media_types(session['id'])
                self.media_filter = stored_types or self.media_filter
                break

    def _collect_pending_art_items(
        self,
        queue_entry: QueueEntry,
        art_items: Optional[List[ArtItemEntry]] = None
    ) -> Tuple[List[ArtItemEntry], Dict[str, Any]]:
        """Return pending art items plus current artwork state for validation."""
        if art_items is None:
            art_items = self.repo.get_art_items(queue_entry.id)
        current_art = self._get_current_artwork(queue_entry.media_type, queue_entry.dbid)

        pending_items: List[ArtItemEntry] = []
        stale_reasons: List[Tuple[str, str]] = []

        for art_item in art_items:
            if art_item.status not in ('pending', None):
                continue

            if art_item.review_mode == db.ARTITEM_REVIEW_MISSING:
                if current_art.get(art_item.art_type):
                    self.repo.set_art_item_status(art_item.id, 'stale')
                    stale_reasons.append((art_item.art_type, "Artwork already set"))
                    continue
            else:
                current_url = current_art.get(art_item.art_type) or ''
                if art_item.baseline_url and current_url and current_url != art_item.baseline_url:
                    self.repo.set_art_item_status(art_item.id, 'stale')
                    stale_reasons.append((art_item.art_type, "Artwork changed since scan"))
                    continue

            pending_items.append(art_item)

        if not pending_items:
            if stale_reasons:
                self.repo.update_queue_status(queue_entry.id, 'completed')
            return [], current_art

        return pending_items, current_art

    def _get_current_artwork(self, media_type: str, dbid: int) -> Dict[str, Any]:
        """Fetch current artwork assignment from Kodi for validation."""
        if media_type not in KODI_GET_DETAILS_METHODS:
            return {}

        method, id_key, result_key = KODI_GET_DETAILS_METHODS[media_type]

        try:
            resp = request(method, {
                id_key: dbid,
                'properties': ['art']
            })
        except Exception as e:
            xbmc.log(f"SkinInfo ArtReviewer: Failed to get current artwork for {media_type}:{dbid}: {e}", xbmc.LOGERROR)
            return {}

        if not resp:
            return {}

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return {}

        return details.get('art', {}) or {}

    def _verify_baseline_before_apply(
        self,
        queue_entry: QueueEntry,
        art_item: ArtItemEntry,
        baseline_url: str
    ) -> bool:
        """
        Ensure the queued baseline still matches Kodi's state before applying changes.
        """
        latest_art = self._get_current_artwork(queue_entry.media_type, queue_entry.dbid)

        if art_item.review_mode == db.ARTITEM_REVIEW_MISSING:
            # Safe to apply only if artwork is still missing
            return not latest_art.get(art_item.art_type)

        current_url = latest_art.get(art_item.art_type) or ''
        if baseline_url and current_url and current_url != baseline_url:
            return False

        return True

    def _load_available_artwork(self, media_type: str, dbid: int, title: str) -> Dict[str, List[Any]]:
        """Load all available artwork for a media item."""
        self.loading_progress.update(10, f"Loading artwork for {title}...")
        try:
            all_available_art = self.processor.source_fetcher.fetch_all(media_type, dbid)
        except Exception as exc:
            xbmc.log(f"SkinInfo ArtReviewer: Failed to load artwork for {title}: {exc}", xbmc.LOGERROR)
            all_available_art = {}
        return all_available_art

    def _log_review_event(self, category: str, entry_data: Dict[str, Any]) -> None:
        """Add timestamp and log review event."""
        entry_data['timestamp'] = datetime.now().isoformat()
        self.review_log[category].append(entry_data)

    def _handle_user_cancel(self, queue_entry: QueueEntry, applied_any: bool) -> str:
        """Handle user cancellation during review."""
        if applied_any:
            self.repo.update_queue_status(queue_entry.id, 'completed')
            return 'applied'
        else:
            self.repo.update_queue_status(queue_entry.id, 'pending')
            return 'cancel'

    def _apply_selected_artwork(
        self,
        queue_entry: QueueEntry,
        art_item: ArtItemEntry,
        selected_art: Dict[str, Any]
    ) -> bool:
        """Apply selected artwork and log the action. Returns True if applied."""
        media_type = queue_entry.media_type
        dbid = queue_entry.dbid
        art_type = art_item.art_type

        if not self._verify_baseline_before_apply(queue_entry, art_item, art_item.baseline_url):
            self.repo.set_art_item_status(art_item.id, 'stale')
            self._log_review_event('stale', {
                'title': queue_entry.title,
                'art_type': art_type,
                'media_type': media_type,
                'dbid': dbid,
                'guid': queue_entry.guid,
                'reason': 'baseline_changed',
            })
            return False

        self.processor._apply_art(media_type, dbid, {art_type: selected_art['url']})
        self.repo.mark_art_item_selected(art_item.id, selected_art['url'], auto_applied=False)
        self._log_review_event('manual_applied', {
            'title': queue_entry.title,
            'art_type': art_type,
            'media_type': media_type,
            'dbid': dbid,
            'guid': queue_entry.guid,
            'url': selected_art.get('url', ''),
            'source': selected_art.get('source', ''),
        })
        return True

    def _filter_artwork_by_language(self, art_type: str, available: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter artwork options based on language preferences for the art type."""
        from resources.lib.art_helpers import filter_artwork_by_language
        return filter_artwork_by_language(available, art_type=art_type)

    def _log_no_options(self, queue_entry: QueueEntry, art_type: str) -> None:
        """Log when no artwork options are available for an item."""
        self._log_review_event('manual_auto', {
            'title': queue_entry.title,
            'art_type': art_type,
            'media_type': queue_entry.media_type,
            'dbid': queue_entry.dbid,
            'guid': queue_entry.guid,
            'reason': 'no_options',
        })

    def _process_dialog_action(
        self,
        action: str,
        selected_art: Optional[Dict[str, Any]],
        queue_entry: QueueEntry,
        art_item: ArtItemEntry,
        applied_any: bool
    ) -> Tuple[str, bool]:
        """
        Process user action from artwork selection dialog.

        Returns:
            Tuple of (flow_control, applied_any) where flow_control is 'cancel', 'continue', or 'applied'
        """
        if action == 'cancel':
            self._handle_user_cancel(queue_entry, applied_any)
            return ('cancel', applied_any)

        if action == 'skip':
            self.repo.set_art_item_status(art_item.id, 'skipped')
            self._log_review_event('manual_skipped', {
                'title': queue_entry.title,
                'art_type': art_item.art_type,
                'media_type': queue_entry.media_type,
                'dbid': queue_entry.dbid,
                'guid': queue_entry.guid,
                'reason': 'user_skip',
            })
            return ('continue', applied_any)

        if action == 'selected' and selected_art:
            if self._apply_selected_artwork(queue_entry, art_item, selected_art):
                return ('applied', True)

        return ('continue', applied_any)

    def _finalize_review_status(
        self,
        queue_entry: QueueEntry,
        art_items: List[ArtItemEntry],
        applied_any: bool,
        had_options: bool,
        auto_logged: bool
    ) -> str:
        """Finalize queue status and return result after reviewing all art items."""
        if applied_any:
            self.repo.update_queue_status(queue_entry.id, 'completed')
            return 'applied'

        self.repo.update_queue_status(queue_entry.id, 'skipped')
        if not had_options and not auto_logged:
            for art_item in art_items:
                self._log_review_event('manual_auto', {
                    'title': queue_entry.title,
                    'art_type': art_item.art_type,
                    'media_type': queue_entry.media_type,
                    'dbid': queue_entry.dbid,
                    'guid': queue_entry.guid,
                    'reason': 'all_art_types_missing',
                })
        return 'skipped' if had_options else 'auto'

    def _review_single_item(self, queue_entry: QueueEntry, art_items: List[ArtItemEntry], current_art: Dict[str, Any]) -> str:
        """Review a single queue item with visual artwork selection."""
        enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
        if enable_debug:
            art_types = [item.art_type for item in art_items]
            log_artwork(f"Reviewing item: '{queue_entry.title}' ({len(art_items)} art types: {', '.join(art_types)})")

        art_priority = {
            'poster': 1, 'fanart': 2, 'clearlogo': 3, 'clearart': 4,
            'banner': 5, 'landscape': 6, 'characterart': 7, 'discart': 8, 'keyart': 9,
        }
        sorted_items = sorted(art_items, key=lambda item: art_priority.get(item.art_type, 99))

        all_available_art = self._load_available_artwork(queue_entry.media_type, queue_entry.dbid, queue_entry.title)

        applied_any = False
        had_options = False
        auto_logged = False

        for art_item in sorted_items:
            full_available = all_available_art.get(art_item.art_type, [])
            filtered_available = self._filter_artwork_by_language(art_item.art_type, full_available)

            if not filtered_available:
                self._log_no_options(queue_entry, art_item.art_type)
                auto_logged = True
                continue

            had_options = True
            action, selected_art = show_artwork_selection_dialog(
                queue_entry.title, art_item.art_type, filtered_available,
                full_artwork_list=full_available,
                media_type=queue_entry.media_type, year=queue_entry.year or '',
                current_url=art_item.baseline_url,
                dbid=queue_entry.dbid, review_mode=art_item.review_mode
            )

            flow_control, applied_any = self._process_dialog_action(
                action, selected_art, queue_entry, art_item, applied_any
            )

            if flow_control == 'cancel':
                return self._handle_user_cancel(queue_entry, applied_any)
            elif flow_control == 'applied':
                applied_any = True

        result = self._finalize_review_status(queue_entry, art_items, applied_any, had_options, auto_logged)

        enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
        if enable_debug:
            log_artwork(f"Item review complete: '{queue_entry.title}', result={result}")

        return result


class ArtworkReviewManager:
    """Coordinate scan and review workflow for RunScript entrypoint."""

    def __init__(self, scope_arg: Optional[str] = None):
        self.scope_arg = scope_arg.lower().strip() if scope_arg else None
        self.scope: Optional[str] = None
        self.media_filter: Optional[List[str]] = None
        self.session_id: Optional[int] = None
        self.repo = ArtQueueRepository()
        self.review_mode: str = REVIEW_MODE_BOTH

    def run(self) -> None:
        log_artwork("ArtworkReviewManager: starting")

        from resources.lib.artwork.api_integration import create_default_fetcher, validate_api_keys
        fetcher = create_default_fetcher()
        if not validate_api_keys(fetcher.tmdb_api, fetcher.fanart_api):
            return

        db.init_database()
        db.cleanup_old_queue_items()

        if self.scope_arg:
            if not self._handle_scope_arg():
                return
            self.scope_arg = None

        while True:
            intent = self._select_intent()
            if intent is None:
                return

            if intent == 'continue_review':
                if self._handle_continue_review_flow():
                    return
            elif intent == 'manual_review':
                if self._handle_manual_review_flow():
                    return
            elif intent == 'manual_review_download':
                if self._handle_manual_review_flow(enable_download=True):
                    return
            elif intent == 'auto_apply':
                if self._handle_auto_apply_flow():
                    return
            elif intent == 'view_reports':
                self._handle_view_reports_flow()

    def _handle_scope_arg(self) -> bool:
        """Handle pre-selected scope from argument."""
        valid_scopes = {scope for scope, _ in REVIEW_SCOPE_OPTIONS}

        if self.scope_arg not in valid_scopes:
            xbmcgui.Dialog().notification(
                "Artwork Review",
                f"Unknown scope '{self.scope_arg}'.",
                xbmcgui.NOTIFICATION_WARNING,
                4000
            )
            return False

        self.scope = self.scope_arg
        self.media_filter = None if self.scope == 'all' else REVIEW_MEDIA_FILTERS.get(self.scope, None)
        self.session_id = None

        pending_counts = db.get_pending_media_counts()
        pending_for_scope = _count_pending_for_scope(pending_counts, self.scope)
        scope_label = REVIEW_SCOPE_LABELS.get(self.scope, self.scope.title())

        options = []

        if pending_for_scope > 0:
            options.append((f"Continue Review ({pending_for_scope} pending)", 'continue_review'))

        options.append(("Manual Review", 'manual_review'))

        enable_combo = ADDON.getSetting("download.enable_combo_workflows") == "true"
        if enable_combo:
            options.append(("Manual Review + Download to Filesystem", 'manual_review_download'))

        options.append(("Auto-Apply Missing Artwork", 'auto_apply'))
        options.append(("View Last Report", 'view_report'))
        options.append(("Cancel", None))

        action, cancelled = show_menu_with_cancel(f"{scope_label} - Select Action", options)
        if cancelled:
            return self._handle_scope_arg()

        if action is None:
            return False

        if action == 'continue_review':
            return self._handle_resume()
        elif action == 'manual_review':
            return self._handle_manual_review()
        elif action == 'manual_review_download':
            return self._handle_manual_review(enable_download=True)
        elif action == 'auto_apply':
            self._handle_auto_apply_missing()
            return False
        elif action == 'view_report':
            last_session = db.get_last_manual_review_session(self.media_filter)
            if last_session and last_session['stats']:
                _show_session_report(last_session)
            else:
                xbmcgui.Dialog().notification(
                    "View Report",
                    f"No report available for {scope_label}.",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            return self._handle_scope_arg()

        return False

    def _select_intent(self) -> Optional[str]:
        """Show intent-first main menu."""
        pending_counts = db.get_pending_media_counts()
        total_pending = sum(pending_counts.values())

        options = []

        if total_pending > 0:
            options.append((f"Continue Review ({total_pending} pending)", 'continue_review'))

        options.append(("Manual Review", 'manual_review'))

        enable_combo = ADDON.getSetting("download.enable_combo_workflows") == "true"
        if enable_combo:
            options.append(("Manual Review + Download to Filesystem", 'manual_review_download'))

        options.append(("Auto-Apply Missing Artwork", 'auto_apply'))
        options.append(("View Reports", 'view_reports'))
        options.append(("Cancel", None))

        intent, cancelled = show_menu_with_cancel("Artwork Reviewer", options)
        if cancelled:
            return self._select_intent()

        return intent

    def _handle_continue_review_flow(self) -> bool:
        """Handle 'Continue Review' flow with scope selection."""
        pending_counts = db.get_pending_media_counts()

        options = []
        scope_map = {}

        for scope, label in REVIEW_SCOPE_OPTIONS:
            if scope == 'all':
                continue
            count = _count_pending_for_scope(pending_counts, scope)
            if count > 0:
                options.append((f"{label} ({count} pending)", scope))
                scope_map[scope] = count

        if not options:
            xbmcgui.Dialog().notification(
                "Continue Review",
                "No pending items found.",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return False

        total_pending = sum(pending_counts.values())
        options.append((f"All Pending ({total_pending} total)", 'all'))
        options.append(("Cancel", None))

        scope, cancelled = show_menu_with_cancel("Continue Review - Select Scope", options)
        if cancelled:
            return self._handle_continue_review_flow()

        if scope is None:
            return False

        self.scope = scope
        self.media_filter = None if scope == 'all' else REVIEW_MEDIA_FILTERS.get(scope, None)
        self.session_id = None

        return self._handle_resume()

    def _handle_manual_review_flow(self, enable_download: bool = False) -> bool:
        """Handle 'Manual Review' flow with scope selection."""
        options = []

        options.append(("All Media", 'all'))
        for scope, label in REVIEW_SCOPE_OPTIONS:
            if scope != 'all':
                options.append((label, scope))

        options.append(("Cancel", None))

        title = "Manual Review + Download - Select Scope" if enable_download else "Manual Review - Select Scope"
        scope, cancelled = show_menu_with_cancel(title, options)
        if cancelled:
            return self._handle_manual_review_flow(enable_download)

        if scope is None:
            return False

        self.scope = scope
        self.media_filter = None if scope == 'all' else REVIEW_MEDIA_FILTERS.get(scope, None)
        self.session_id = None

        return self._handle_manual_review(enable_download=enable_download)

    def _handle_auto_apply_flow(self) -> bool:
        """Handle 'Auto-Apply Missing Artwork' flow with scope selection."""
        options = []

        options.append(("All Media", 'all'))
        for scope, label in REVIEW_SCOPE_OPTIONS:
            if scope != 'all':
                options.append((label, scope))

        options.append(("Cancel", None))

        scope, cancelled = show_menu_with_cancel("Auto-Apply Missing Artwork - Select Scope", options)
        if cancelled:
            return self._handle_auto_apply_flow()

        if scope is None:
            return False

        self.scope = scope
        self.media_filter = None if scope == 'all' else REVIEW_MEDIA_FILTERS.get(scope, None)
        self.session_id = None

        self._handle_auto_apply_missing()
        return False

    def _handle_view_reports_flow(self) -> None:
        """Handle 'View Reports' flow with scope selection."""
        options = []

        for scope, label in REVIEW_SCOPE_OPTIONS:
            if scope != 'all':
                options.append((label, scope))

        options.append(("Overall Queue Status", 'overall_status'))
        options.append(("Cancel", None))

        scope, cancelled = show_menu_with_cancel("View Reports - Select Scope", options)
        if cancelled:
            return self._handle_view_reports_flow()

        if scope is None:
            return

        if scope == 'overall_status':
            self._show_overall_queue_status()
            return self._handle_view_reports_flow()

        self.scope = scope
        self.media_filter = None if scope == 'all' else REVIEW_MEDIA_FILTERS.get(scope, None)

        last_session = db.get_last_manual_review_session(self.media_filter)

        if last_session and last_session['stats']:
            _show_session_report(last_session)
        else:
            xbmcgui.Dialog().notification(
                "View Reports",
                f"No report available for {REVIEW_SCOPE_LABELS.get(scope, scope)}.",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )

        self._handle_view_reports_flow()

    def _show_overall_queue_status(self) -> None:
        """Display overall queue status across all scopes."""
        breakdown = db.get_queue_breakdown_by_media()

        if not breakdown:
            xbmcgui.Dialog().ok(
                "Artwork Review",
                "No items in queue."
            )
            return

        lines = [
            "[B]Artwork Review - Overall Queue Status[/B]",
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        total_pending = 0

        for media_type, stats in sorted(breakdown.items()):
            label = media_type.title() + 's'

            pending = stats.get('pending', 0)
            completed = stats.get('completed', 0)
            skipped = stats.get('skipped', 0)

            total_pending += pending

            lines.append(f"{label}: {pending} pending, {completed} completed, {skipped} skipped")

        lines.append("")
        lines.append(f"[B]Total: {total_pending} pending items[/B]")

        text = "[CR]".join(lines)
        xbmcgui.Dialog().textviewer("Artwork Review - Queue Status", text)

    def _prompt_scan_mode(self, title: str, default: str = REVIEW_MODE_BOTH) -> Optional[str]:
        default = _normalize_review_mode(default)

        mode_options: List[Tuple[str, Optional[str]]] = [
            ("Missing + upgrades", REVIEW_MODE_BOTH),
            ("Missing artwork only", REVIEW_MODE_MISSING),
        ]

        mode_options.sort(key=lambda opt: 0 if opt[1] == default else 1)

        mode_options.append(("Cancel", None))

        action, cancelled = show_menu_with_cancel(title, mode_options)
        if cancelled:
            return self._prompt_scan_mode(title, default)

        return action

    def _decide_session(self) -> Optional[bool]:
        """
        Decide whether to scan or resume.

        Returns:
            True: Start new scan
            False: Resume existing queue
            None: Cancel
        """
        if not self.scope:
            return None

        pending_counts = db.get_pending_media_counts()
        pending_for_scope = _count_pending_for_scope(pending_counts, self.scope)
        scope_label = REVIEW_SCOPE_LABELS.get(self.scope, self.scope.title())

        session = self._find_matching_session()

        # Use helper to build and show menu based on state
        return self._prompt_user_decision(session, pending_for_scope, scope_label)

    def _prompt_user_decision(
        self,
        session: Optional[sqlite3.Row],
        pending_count: int,
        scope_label: str
    ) -> Optional[bool]:
        """Prompt user for session decision based on current state."""

        while True:
            options = self._build_session_options(session, pending_count)
            action, cancelled = show_menu_with_cancel(f"{scope_label} Review", options)

            if cancelled:
                continue

            if action is None:
                return None

            if action == 'report':
                _show_session_report(session)
                continue

            result = self._handle_session_action(action, session)
            if result is not None:
                return result

    def _build_session_options(
        self,
        session: Optional[sqlite3.Row],
        pending_count: int
    ) -> List[Tuple[str, str]]:
        """Build menu options based on session and pending state."""

        has_pending = pending_count > 0
        options = []

        if session or has_pending:
            options.append(("Start new scan + review (clears queue)", 'new'))
            if session and session['stats']:  # type: ignore[index]
                options.append(("View last report", 'report'))
        else:
            options.append(("Start new scan + review", 'new'))

        options.append(("Cancel", 'cancel'))
        return options

    def _handle_session_action(
        self,
        action: str,
        session: Optional[sqlite3.Row]
    ) -> Optional[bool]:
        """
        Handle user's session action choice.

        Returns:
            True: Start new scan
            False: Resume
            None: Cancel
        """
        if action == 'cancel':
            return None

        if action == 'new':
            if session:
                db.cancel_session(session['id'])
            self._clear_scope_queue()
            self.session_id = None
            return True

        if action == 'resume':
            if session:
                self.session_id = session['id']
                stored_types = db.get_session_media_types(session['id'])
                if stored_types:
                    self.media_filter = stored_types
            else:
                self.session_id = None
            return False

        return None  # Unknown action

    def _find_matching_session(self) -> Optional[sqlite3.Row]:
        target = set(self.media_filter or [])
        for session in db.get_paused_sessions():
            if session['scan_type'] not in ('manual_review', 'missing_art'):
                continue
            stored = set(db.get_session_media_types(session['id']))
            if target == stored:
                return session
        return None

    def _clear_scope_queue(self) -> None:
        if self.media_filter:
            db.clear_queue_for_media(self.media_filter)
        else:
            db.clear_queue()
        log_artwork("Cleared queue for scope")

    def _handle_auto_apply_missing(self) -> None:
        from resources.lib.artwork.processor import ArtProcessor

        if not self.scope:
            return

        scanner = _scan_scope(self.scope, REVIEW_MODE_MISSING)
        if not scanner:
            return
        if scanner.cancelled:
            return

        processor = ArtProcessor(use_background=False, mode=REVIEW_MODE_MISSING)
        processor.process_queue(media_types=self.media_filter)
        db.restore_pending_queue_items(self.media_filter)

    def _handle_resume(self) -> bool:
        paused_session = self._find_matching_session()
        if paused_session:
            self.session_id = paused_session['id']
            stored_types = db.get_session_media_types(paused_session['id'])
            if stored_types:
                self.media_filter = stored_types

        if not self.scope:
            return False

        self.repo.prune_inactive_queue()

        pending_counts = db.get_pending_media_counts()
        pending_total = _count_pending_for_scope(pending_counts, self.scope)

        session_row = db.get_session(self.session_id) if self.session_id else None
        if session_row and session_row['stats']:
            try:
                stats_payload = json.loads(session_row['stats'])
                mode = stats_payload.get('review_mode') if isinstance(stats_payload, dict) else None
                self.review_mode = _normalize_review_mode(mode)
            except Exception:
                self.review_mode = REVIEW_MODE_BOTH
        else:
            self.review_mode = REVIEW_MODE_BOTH

        if pending_total == 0:
            if paused_session and paused_session['scan_type'] == 'missing_art':
                scanner = ArtScanner(self.review_mode)
                result = scanner.scan(self.scope, resume_session_id=paused_session['id'])
                if not result:
                    return False
                if scanner.cancelled:
                    return True

                pending_counts = db.get_pending_media_counts()
                pending_total = _count_pending_for_scope(pending_counts, self.scope)

                if pending_total == 0:
                    return False
            else:
                xbmcgui.Dialog().ok(
                    "Continue Review",
                    "No pending items found in queue."
                )
                return False

        reviewer = ArtReviewer(
            session_id=self.session_id,
            media_filter=self.media_filter,
            review_mode=self.review_mode,
        )
        review_outcome = reviewer.review_queue()
        if not review_outcome:
            return False

        return True

    def _handle_manual_review(self, preset_mode: Optional[str] = None, enable_download: bool = False) -> bool:
        need_scan = self._decide_session()
        if need_scan is None:
            return False

        session_row = db.get_session(self.session_id) if self.session_id else None
        if session_row and session_row['stats']:
            try:
                stats_payload = json.loads(session_row['stats'])
            except Exception:
                stats_payload = {}
            mode = stats_payload.get('review_mode') if isinstance(stats_payload, dict) else None
            self.review_mode = _normalize_review_mode(mode)

        if need_scan or not self.session_id:
            chosen_mode = _normalize_review_mode(preset_mode) if preset_mode else None
            if chosen_mode is None:
                chosen_mode = self._prompt_scan_mode("Manual Review Mode", self.review_mode)
                if chosen_mode not in (REVIEW_MODE_MISSING, REVIEW_MODE_BOTH):
                    return False
            self.review_mode = _normalize_review_mode(chosen_mode)
        elif self.session_id and not session_row:
            # Existing queue without a stored session; default to combined mode
            self.review_mode = REVIEW_MODE_BOTH

        if not self.scope:
            return False

        if need_scan:
            scanner = _scan_scope(self.scope, self.review_mode)
            if not scanner:
                return False
            if scanner.cancelled:
                return True

        self.repo.prune_inactive_queue()

        pending_counts = db.get_pending_media_counts()
        pending_total = _count_pending_for_scope(pending_counts, self.scope)

        if pending_total == 0:
            if need_scan:
                xbmcgui.Dialog().ok(
                    "Artwork Review",
                    "Scan complete. No items need review."
                )
            else:
                xbmcgui.Dialog().notification(
                    "Artwork Review",
                    "No items found to review.",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            return False

        reviewer = ArtReviewer(
            session_id=self.session_id,
            media_filter=self.media_filter,
            review_mode=self.review_mode,
            enable_download=enable_download,
        )
        review_outcome = reviewer.review_queue()
        if not review_outcome:
            return False

        return True

def run_art_reviewer(scope: Optional[str] = None) -> None:
    normalized = scope.lower().strip() if scope else None

    valid_scopes = {s for s, _ in REVIEW_SCOPE_OPTIONS}
    if normalized:
        if normalized == 'single':
            run_art_fetcher_single(None, None)
            return
        if normalized in valid_scopes:
            manager = ArtworkReviewManager(normalized)
            manager.run()
            return
        xbmcgui.Dialog().notification(
            "Artwork Review",
            f"Unknown scope '{normalized}'.",
            xbmcgui.NOTIFICATION_WARNING,
            4000
        )
        return

    manager = ArtworkReviewManager()
    manager.run()
