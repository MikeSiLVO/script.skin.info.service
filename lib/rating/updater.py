"""Ratings updater coordinator - main entry point for ratings updates."""
from __future__ import annotations

from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import time
import xbmc
import xbmcgui

from lib.infrastructure import tasks as task_manager
from lib.kodi.client import (
    request, batch_request, get_library_items, _get_api_key, log,
    KODI_GET_DETAILS_METHODS, KODI_SET_DETAILS_METHODS, ADDON
)
from lib.data.api.tmdb import ApiTmdb as TMDBRatingsSource, resolve_tmdb_id
from lib.data.api.mdblist import ApiMdblist as MDBListRatingsSource, BATCH_SIZE as MDBLIST_BATCH_SIZE
from lib.data.api.omdb import ApiOmdb as OMDbRatingsSource
from lib.data.api.trakt import ApiTrakt as TraktRatingsSource
from lib.data.api.imdb import get_imdb_dataset
from lib.rating.source import RateLimitHit, RetryableError
from lib.rating.merger import merge_ratings, prepare_kodi_ratings
from lib.rating import tracker as usage_tracker
from lib.infrastructure.dialogs import show_ok, show_textviewer, show_notification, show_yesnocustom
from lib.infrastructure.menus import Menu, MenuItem
from lib.data.database import workflow as db
from lib.data.database._infrastructure import init_database, get_db
from lib.rating.executor import RatingBatchExecutor, ItemState
from lib.rating.ids import get_imdb_id_from_tmdb, update_kodi_uniqueid

PROGRESS_SAVE_INTERVAL = 50

_tvshow_uniqueid_cache: Dict[int, Dict[str, str]] = {}


def _preserve_other_ratings(existing_ratings: Dict, kodi_ratings: Dict) -> None:
    """Copy non-imdb ratings from existing to kodi_ratings format."""
    for source_name, rating_data in existing_ratings.items():
        if source_name != "imdb" and isinstance(rating_data, dict):
            kodi_ratings[source_name] = {
                "rating": rating_data.get("rating", 0),
                "votes": int(rating_data.get("votes", 0)),
                "default": False
            }


def _build_external_ids(ids: Dict) -> Dict[str, str]:
    """Build external_ids dict from ids for database sync."""
    external_ids: Dict[str, str] = {}
    imdb_id = ids.get("imdb_episode") or ids.get("imdb")
    if imdb_id:
        external_ids["imdb"] = str(imdb_id)
    tmdb_id = ids.get("tmdb")
    if tmdb_id:
        external_ids["themoviedb"] = str(tmdb_id)
        external_ids["tmdb"] = str(tmdb_id)
    return external_ids


def _clear_tvshow_uniqueid_cache() -> None:
    """Clear the tvshow uniqueid cache. Call at start of batch operations."""
    _tvshow_uniqueid_cache.clear()


def _prefetch_tvshow_uniqueids() -> None:
    """Pre-fetch all TV show uniqueids in one request to populate cache."""
    response = request("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]})
    if not response:
        return
    shows = response.get("result", {}).get("tvshows", [])
    for show in shows:
        tvshowid = show.get("tvshowid")
        uniqueid = show.get("uniqueid", {})
        if tvshowid:
            _tvshow_uniqueid_cache[tvshowid] = uniqueid
    log("Ratings", f"Pre-fetched uniqueids for {len(shows)} TV shows", xbmc.LOGDEBUG)


def _get_tvshow_uniqueid(tvshow_dbid: int) -> Dict[str, str]:
    """Fetch TV show uniqueid dict from Kodi library.

    Uses module-level cache to avoid redundant requests when processing
    multiple episodes from the same show.

    Args:
        tvshow_dbid: TV show database ID

    Returns:
        Dict of uniqueid values (tmdb, imdb, tvdb, etc.) or empty dict on failure
    """
    if tvshow_dbid in _tvshow_uniqueid_cache:
        return _tvshow_uniqueid_cache[tvshow_dbid]

    response = request("VideoLibrary.GetTVShowDetails", {
        "tvshowid": tvshow_dbid,
        "properties": ["uniqueid"]
    })
    if response and "tvshowdetails" in response.get("result", {}):
        uniqueid = response["result"]["tvshowdetails"].get("uniqueid", {})
        _tvshow_uniqueid_cache[tvshow_dbid] = uniqueid
        return uniqueid

    _tvshow_uniqueid_cache[tvshow_dbid] = {}
    return {}


def _update_tvshow_episodes(tvshow_dbid: int, sources: List) -> int:
    """
    Update ratings for all episodes of a TV show.

    Args:
        tvshow_dbid: Database ID of the TV show
        sources: List of rating sources to use

    Returns:
        Number of episodes that were updated
    """
    response = request("VideoLibrary.GetEpisodes", {
        "tvshowid": tvshow_dbid,
        "properties": ["title", "season", "episode", "tvshowid", "uniqueid", "ratings"]
    })

    if not response or "episodes" not in response.get("result", {}):
        return 0

    episodes = response["result"]["episodes"]
    if not episodes:
        return 0

    log("Ratings", f"Updating ratings for {len(episodes)} episodes", xbmc.LOGINFO)

    updated_count = 0
    for episode in episodes:
        success, _ = _update_single_item(episode, "episode", sources)
        if success:
            updated_count += 1

    return updated_count


def update_single_item_ratings(dbid: Optional[str], dbtype: Optional[str]) -> None:
    """
    Update ratings for a single item by DBID.

    Args:
        dbid: Database ID of the item
        dbtype: Type of the item (movie, tvshow, episode)
    """
    if not dbid:
        dbid = xbmc.getInfoLabel("ListItem.DBID")
    if not dbtype:
        dbtype = xbmc.getInfoLabel("ListItem.DBType")

    if not dbid or dbid == "-1" or not dbtype:
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32259),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    media_type = dbtype.lower()
    if media_type not in ("movie", "tvshow", "episode"):
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32263).format(media_type),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    log("Ratings", f"Updating ratings for single item - dbid={dbid}, dbtype={media_type}", xbmc.LOGINFO)

    # Check if IMDb dataset needs refresh
    imdb_dataset = get_imdb_dataset()
    imdb_dataset.refresh_if_stale()

    sources = _initialize_sources()
    if not sources:
        show_ok(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32400)
        )
        return

    if media_type == "episode":
        properties = ["title", "season", "episode", "tvshowid", "uniqueid", "ratings"]
    else:
        properties = ["title", "year", "uniqueid", "ratings"]

    method_info = KODI_GET_DETAILS_METHODS.get(media_type)
    if not method_info:
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32263).format(media_type),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    method_name, id_key, result_key = method_info

    response = request(method_name, {id_key: int(dbid), "properties": properties})
    if not response or result_key not in response.get("result", {}):
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32401).format(media_type.title()),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    item = response["result"][result_key]
    title = item.get("title", "Unknown")

    show_notification(
        ADDON.getLocalizedString(32300),
        ADDON.getLocalizedString(32402),
        xbmcgui.NOTIFICATION_INFO,
        2000
    )

    success, item_stats = _update_single_item(item, media_type, sources)

    total_added = item_stats.get('added_details', []) if item_stats else []
    total_updated = item_stats.get('updated_details', []) if item_stats else []
    episodes_updated = 0

    if media_type == "tvshow" and success:
        episodes_updated = _update_tvshow_episodes(int(dbid), sources)

    if success:
        if total_added or total_updated or episodes_updated > 0:
            message_lines = []

            if total_added:
                message_lines.append(f"[B]Added:[/B] {', '.join(total_added)}")

            if total_updated:
                message_lines.append(f"[B]Updated:[/B] {', '.join(total_updated)}")

            if episodes_updated > 0:
                message_lines.append(f"[B]Episodes:[/B] {episodes_updated} updated")

            show_ok(ADDON.getLocalizedString(32316).format(title), "[CR]".join(message_lines))
        else:
            show_notification(
                ADDON.getLocalizedString(32300),
                ADDON.getLocalizedString(32403),
                xbmcgui.NOTIFICATION_INFO,
                3000
            )

        xbmc.executebuiltin("Container.Refresh")
    elif success is None:
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32404),
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
    else:
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32405),
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def run_ratings_menu() -> None:
    """Show ratings updater menu."""
    init_database()

    items = [
        MenuItem(ADDON.getLocalizedString(32406), lambda: _run_update("movie")),
        MenuItem(ADDON.getLocalizedString(32407), lambda: _run_update("tvshow")),
        MenuItem(ADDON.getLocalizedString(32408), lambda: _run_update("episode")),
        MenuItem(ADDON.getLocalizedString(32409), _run_update_all),
    ]

    if db.get_last_operation_stats('ratings_update'):
        items.append(MenuItem(ADDON.getLocalizedString(32086), show_ratings_report, loop=True))

    menu = Menu(ADDON.getLocalizedString(32300), items)
    menu.show()


def _run_update(media_type: str) -> None:
    """Run ratings update for a media type."""
    _select_mode_and_run(media_type, _initialize_sources(), "multi_source")


def _run_update_all() -> None:
    """Run ratings update for all media types."""
    sources = _initialize_sources()

    def run_foreground():
        update_library_ratings("movie", sources, use_background=False, source_mode="multi_source")
        update_library_ratings("tvshow", sources, use_background=False, source_mode="multi_source")
        update_library_ratings("episode", sources, use_background=False, source_mode="multi_source")

    def run_background():
        if task_manager.is_task_running():
            task_info = task_manager.get_task_info()
            current_task = task_info['name'] if task_info else "Unknown task"
            show_ok(ADDON.getLocalizedString(32172), f"{ADDON.getLocalizedString(32173)}:[CR]{current_task}")
            return
        update_library_ratings("movie", sources, use_background=True, source_mode="multi_source")
        update_library_ratings("tvshow", sources, use_background=True, source_mode="multi_source")
        update_library_ratings("episode", sources, use_background=True, source_mode="multi_source")

    Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), run_foreground),
        MenuItem(ADDON.getLocalizedString(32412), run_background),
    ]).show()


def _select_mode_and_run(media_type: str, sources: List, source_mode: str) -> None:
    """Select run mode and execute ratings update."""
    def run_foreground():
        update_library_ratings(media_type, sources, use_background=False, source_mode=source_mode)

    def run_background():
        if task_manager.is_task_running():
            task_info = task_manager.get_task_info()
            current_task = task_info['name'] if task_info else "Unknown task"
            show_ok(ADDON.getLocalizedString(32172), f"{ADDON.getLocalizedString(32173)}:[CR]{current_task}")
            return
        update_library_ratings(media_type, sources, use_background=True, source_mode=source_mode)

    Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), run_foreground),
        MenuItem(ADDON.getLocalizedString(32412), run_background),
    ]).show()


RATINGS_BATCH_MIN = 100
RATINGS_BATCH_MAX = 1000
RATINGS_BATCH_PERCENT = 5  # 5% of total items
BATCH_DELAY_MS = 100


def _get_batch_size(total_items: int) -> int:
    """Calculate batch size as percentage of total, clamped to min/max."""
    calculated = int(total_items * RATINGS_BATCH_PERCENT / 100)
    return max(RATINGS_BATCH_MIN, min(calculated, RATINGS_BATCH_MAX))


def update_changed_imdb_ratings(media_type: str = "") -> Dict[str, int]:
    """
    Incremental update - only sync items where IMDb rating has changed.

    Uses SQL join between ratings_synced and imdb_ratings to find items
    needing update, then updates only those items in batches to avoid
    overwhelming Kodi.

    Args:
        media_type: Optional filter for "movie", "tvshow", or "episode".
                   Empty string means all types.

    Returns:
        Stats dict with updated/skipped/failed counts
    """
    stats = {"updated": 0, "skipped": 0, "failed": 0}

    changed_items = db.get_imdb_changed_items(media_type if media_type else None)

    if not changed_items:
        return stats

    log("Ratings", f"Found {len(changed_items)} items with changed IMDb ratings", xbmc.LOGINFO)

    items_by_type: Dict[str, List[Dict]] = {}
    for item in changed_items:
        item_media_type = item["media_type"]
        if item_media_type not in items_by_type:
            items_by_type[item_media_type] = []
        items_by_type[item_media_type].append(item)

    for item_media_type, type_items in items_by_type.items():
        type_stats = _update_changed_ratings_batched(item_media_type, type_items)
        stats["updated"] += type_stats["updated"]
        stats["skipped"] += type_stats["skipped"]
        stats["failed"] += type_stats["failed"]

    log("Ratings", f"Incremental update complete: {stats['updated']} updated, {stats['skipped']} skipped, {stats['failed']} failed", xbmc.LOGINFO)
    return stats


def _update_changed_ratings_batched(
    item_media_type: str,
    items: List[Dict]
) -> Dict[str, int]:
    """
    Update ratings for a batch of items of the same media type.

    Args:
        item_media_type: Media type (movie, tvshow, episode)
        items: List of changed item dicts

    Returns:
        Stats dict with updated/skipped/failed counts
    """
    stats = {"updated": 0, "skipped": 0, "failed": 0}

    details_method = KODI_GET_DETAILS_METHODS.get(item_media_type)
    set_method_info = KODI_SET_DETAILS_METHODS.get(item_media_type)

    if not details_method or not set_method_info:
        stats["failed"] = len(items)
        return stats

    get_method, get_id_key, result_key = details_method
    set_method, set_id_key = set_method_info
    batch_size = _get_batch_size(len(items))

    for batch_start in range(0, len(items), batch_size):
        batch_end = min(batch_start + batch_size, len(items))
        batch = items[batch_start:batch_end]

        valid_items = []
        for item in batch:
            if item.get("imdb_id"):
                valid_items.append(item)
            else:
                stats["skipped"] += 1

        if not valid_items:
            continue

        get_calls = []
        for item in valid_items:
            get_calls.append({
                "method": get_method,
                "params": {get_id_key: item["dbid"], "properties": ["title", "ratings"]}
            })

        get_responses = batch_request(get_calls)

        xbmc.sleep(BATCH_DELAY_MS)

        set_calls = []
        items_to_update = []

        for i, item in enumerate(valid_items):
            response = get_responses[i] if i < len(get_responses) else None

            if not response:
                stats["failed"] += 1
                continue

            item_data = response.get("result", {}).get(result_key, {})
            existing_ratings = item_data.get("ratings", {})

            kodi_ratings = {
                "imdb": {
                    "rating": item["new_rating"],
                    "votes": item["new_votes"],
                    "default": True
                }
            }

            _preserve_other_ratings(existing_ratings, kodi_ratings)

            set_calls.append({
                "method": set_method,
                "params": {set_id_key: item["dbid"], "ratings": kodi_ratings}
            })
            items_to_update.append({
                "item": item,
                "title": item_data.get("title", "Unknown")
            })

        if not set_calls:
            continue

        set_responses = batch_request(set_calls)

        xbmc.sleep(BATCH_DELAY_MS)

        for i, update_info in enumerate(items_to_update):
            response = set_responses[i] if i < len(set_responses) else None
            item = update_info["item"]
            title = update_info["title"]

            if response is not None and "error" not in response:
                db.update_synced_ratings(
                    item_media_type, item["dbid"],
                    {"imdb": {"rating": item["new_rating"], "votes": float(item["new_votes"])}},
                    {"imdb": item["imdb_id"]}
                )
                log("Ratings", f"Updated {title}: imdb ({item['old_rating']:.1f} -> {item['new_rating']:.1f})", xbmc.LOGDEBUG)
                stats["updated"] += 1
            else:
                stats["failed"] += 1

    return stats


def update_library_ratings(
    media_type: str,
    sources: List,
    use_background: bool = False,
    source_mode: str = "multi_source"
) -> Dict[str, int]:
    """
    Update ratings for all items of a media type.

    Args:
        media_type: Type of media ("movie", "tvshow", "episode")
        sources: List of API rating sources to use
        use_background: Whether to run in background mode
        source_mode: Source mode identifier for reporting ("imdb", "tmdb", etc.)

    Returns:
        Dictionary with update statistics
    """
    start_time = time.time()
    usage_tracker.reset_session_skip()

    if media_type == "episode":
        _clear_tvshow_uniqueid_cache()
        properties = ["title", "season", "episode", "tvshowid", "uniqueid", "ratings"]
    else:
        properties = ["title", "year", "uniqueid", "ratings"]

    progress: xbmcgui.DialogProgress | xbmcgui.DialogProgressBG
    if use_background:
        progress = xbmcgui.DialogProgressBG()
        progress.create(ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32303).format(media_type))
    else:
        progress = xbmcgui.DialogProgress()
        progress.create(ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32303).format(media_type))

    items = get_library_items([media_type], properties=properties)
    if not items:
        if progress:
            progress.close()
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32413).format(media_type),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return {"updated": 0, "failed": 0, "skipped": 0}

    if isinstance(progress, xbmcgui.DialogProgressBG):
        progress.update(0, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32304).format(len(items), media_type))
    elif isinstance(progress, xbmcgui.DialogProgress):
        progress.update(0, ADDON.getLocalizedString(32304).format(len(items), media_type))

    results: Dict = {
        "updated": 0,
        "failed": 0,
        "skipped": 0,
        "total_items": len(items),
        "source_stats": {},
        "item_details": [],
        "total_ratings_added": 0,
        "total_ratings_updated": 0,
        "imdb_ids_added": 0,
        "imdb_ids_corrected": 0,
        "pending_corrections": [],
        "source_mode": source_mode
    }

    retry_queue: List[Dict] = []

    dataset_date: str = ""
    processed_ids: Set[int] = set()
    resume_count = 0

    if source_mode == "imdb":
        dataset = get_imdb_dataset()
        if not dataset.is_dataset_available():
            if isinstance(progress, xbmcgui.DialogProgressBG):
                progress.update(0, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32305))
            elif isinstance(progress, xbmcgui.DialogProgress):
                progress.update(0, ADDON.getLocalizedString(32305))
            dataset.force_download()

        stats = dataset.get_stats()
        dataset_date = str(stats.get("last_modified") or "")

        saved_progress = db.get_imdb_update_progress(media_type)
        if saved_progress:
            if saved_progress["dataset_date"] == dataset_date:
                processed_ids = saved_progress["processed_ids"]
                resume_count = len(processed_ids)
                log("Ratings", f"Resuming IMDb update for {media_type}: {resume_count}/{len(items)} already processed")
            else:
                db.clear_imdb_update_progress(media_type)
                log("Ratings", f"New IMDb dataset detected, starting fresh for {media_type}")

    mdblist_fetcher: MdblistBatchFetcher | None = None
    if source_mode == "multi_source" and media_type in ("movie", "tvshow"):
        mdblist_fetcher = MdblistBatchFetcher(items, media_type)

    if media_type == "episode":
        _ensure_episode_dataset(progress)
        _prefetch_tvshow_uniqueids()

    def process_item(item, ctx, db_cursor=None):
        """Process a single item and return (success, item_stats)."""
        if source_mode == "imdb":
            return _update_single_item_imdb(item, media_type, ctx.abort_flag, db_cursor)
        else:
            return _update_single_item(item, media_type, sources, ctx.abort_flag)

    def update_results(item, success, item_stats):
        """Update results dict with item outcome."""
        if success:
            results["updated"] += 1
        elif success is None:
            results["skipped"] += 1
        else:
            results["failed"] += 1

        if item_stats:
            results["total_ratings_added"] += item_stats.get("ratings_added", 0)
            results["total_ratings_updated"] += item_stats.get("ratings_updated", 0)
            if item_stats.get("imdb_id_added"):
                results["imdb_ids_added"] += 1
            if item_stats.get("pending_correction"):
                results["pending_corrections"].append(item_stats["pending_correction"])

            for source_name in item_stats.get("sources_used", []):
                if source_name not in results["source_stats"]:
                    results["source_stats"][source_name] = {"fetched": 0, "failed": 0}
                results["source_stats"][source_name]["fetched"] += 1

            if item_stats.get("ratings_added", 0) > 0 or item_stats.get("ratings_updated", 0) > 0:
                results["item_details"].append(item_stats)
                if len(results["item_details"]) > 20:
                    results["item_details"].pop(0)

            retryable = item_stats.get("retryable_failures", [])
            if retryable:
                retry_queue.append({
                    "item": item,
                    "title": item_stats.get("title", "Unknown"),
                    "year": item_stats.get("year", ""),
                    "failures": retryable
                })

    monitor = xbmc.Monitor()

    with task_manager.TaskContext("Update Library Ratings") as ctx:

        def _should_abort() -> bool:
            return ctx.abort_flag.is_requested() or monitor.abortRequested()
        if source_mode == "imdb":
            log("Ratings", f"Using BATCHED IMDb update for {len(items)} {media_type} items", xbmc.LOGINFO)
            batch_items_prepared = 0
            batch_items_skipped = 0
            id_key = "movieid" if media_type == "movie" else "tvshowid" if media_type == "tvshow" else "episodeid"
            set_method_info = KODI_SET_DETAILS_METHODS.get(media_type)
            if not set_method_info:
                log("Ratings", f"Unknown media type for SET: {media_type}", xbmc.LOGERROR)
            else:
                set_method, set_id_key = set_method_info
                items_since_save = 0
                dataset = get_imdb_dataset()
                batch_size = _get_batch_size(len(items))
                log("Ratings", f"Batch size: {batch_size} for {len(items)} items", xbmc.LOGDEBUG)

                with get_db() as (_, db_cursor):
                    for batch_start in range(0, len(items), batch_size):
                        if _should_abort():
                            results["cancelled"] = True
                            break

                        if isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled():
                            results["cancelled"] = True
                            break

                        batch_end = min(batch_start + batch_size, len(items))
                        batch = items[batch_start:batch_end]

                        set_calls = []
                        items_to_update = []

                        for item in batch:
                            if _should_abort():
                                log("Ratings", "Abort requested during item preparation", xbmc.LOGINFO)
                                results["cancelled"] = True
                                break

                            dbid = item.get(id_key)
                            if dbid and dbid in processed_ids:
                                continue

                            prepared = _prepare_imdb_update(item, media_type, dataset, db_cursor)
                            if prepared is None:
                                results["skipped"] += 1
                                batch_items_skipped += 1
                                if dbid:
                                    processed_ids.add(dbid)
                                continue

                            batch_items_prepared += 1
                            dbid, kodi_ratings, imdb_id, new_rating, new_votes, title, year, is_add = prepared

                            set_calls.append({
                                "method": set_method,
                                "params": {set_id_key: dbid, "ratings": kodi_ratings}
                            })
                            items_to_update.append({
                                "dbid": dbid,
                                "imdb_id": imdb_id,
                                "new_rating": new_rating,
                                "new_votes": new_votes,
                                "title": title,
                                "year": year,
                                "is_add": is_add
                            })

                        if results.get("cancelled"):
                            break

                        if set_calls:
                            set_responses = batch_request(set_calls)

                            if _should_abort():
                                log("Ratings", "Abort requested after batch_request", xbmc.LOGINFO)
                                results["cancelled"] = True
                                break

                            for i, update_info in enumerate(items_to_update):
                                if _should_abort():
                                    log("Ratings", "Abort requested during DB update loop", xbmc.LOGINFO)
                                    results["cancelled"] = True
                                    break

                                response = set_responses[i] if i < len(set_responses) else None
                                dbid = update_info["dbid"]

                                if response is not None and "error" not in response:
                                    db.update_synced_ratings(
                                        media_type, dbid,
                                        {"imdb": {"rating": update_info["new_rating"], "votes": update_info["new_votes"]}},
                                        {"imdb": update_info["imdb_id"]}
                                    )
                                    action = "Added" if update_info["is_add"] else "Updated"
                                    log("Ratings", f"{action} {update_info['title']}: imdb ({update_info['new_rating']:.1f})", xbmc.LOGDEBUG)
                                    results["updated"] += 1
                                    if update_info["is_add"]:
                                        results["total_ratings_added"] += 1
                                    else:
                                        results["total_ratings_updated"] += 1
                                else:
                                    results["failed"] += 1

                                processed_ids.add(dbid)
                                items_since_save += 1

                            if results.get("cancelled"):
                                break

                            xbmc.sleep(BATCH_DELAY_MS)

                        current_count = len(processed_ids)
                        percent = int((current_count / len(items)) * 100)
                        if isinstance(progress, xbmcgui.DialogProgressBG):
                            progress.update(percent, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32308).format(current_count, len(items)))
                        elif isinstance(progress, xbmcgui.DialogProgress):
                            progress.update(percent, ADDON.getLocalizedString(32309).format(current_count, len(items)))

                        ctx.mark_progress()

                        if items_since_save >= PROGRESS_SAVE_INTERVAL:
                            db.save_imdb_update_progress(media_type, dataset_date, processed_ids, len(items))
                            items_since_save = 0

                log("Ratings", f"BATCHED complete: {batch_items_prepared} to update, {batch_items_skipped} skipped", xbmc.LOGINFO)

                if not results.get("cancelled") and source_mode == "imdb":
                    db.clear_imdb_update_progress(media_type)
                elif results.get("cancelled") and source_mode == "imdb" and dataset_date:
                    db.save_imdb_update_progress(media_type, dataset_date, processed_ids, len(items))
        else:
            with RatingBatchExecutor(sources, ctx.abort_flag) as executor:
                items_submitted = 0
                items_finalized = 0
                item_to_index: Dict[int, int] = {}

                for i, item in enumerate(items):
                    if executor.is_cancelled():
                        results["cancelled"] = True
                        break

                    if isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled():
                        results["cancelled"] = True
                        break

                    if mdblist_fetcher:
                        mdblist_fetcher.fetch_batch_for_index(i, progress)

                    prepared = _prepare_item_for_batch(item, media_type)
                    dbid, title, year, ids, existing_ratings, initial_ratings, initial_sources = prepared

                    if dbid is None or title is None or ids is None or existing_ratings is None:
                        results["skipped"] += 1
                        continue

                    item_to_index[dbid] = i
                    executor.submit_item(
                        item=item,
                        dbid=dbid,
                        title=title,
                        year=year or "",
                        media_type=media_type,
                        ids=ids,
                        existing_ratings=existing_ratings
                    )

                    state = executor.get_item_state(dbid)
                    if state and initial_ratings and initial_sources:
                        state.ratings.extend(initial_ratings)
                        state.sources_used.extend(initial_sources)

                    items_submitted += 1

                    percent = int((i / len(items)) * 100)
                    if isinstance(progress, xbmcgui.DialogProgressBG):
                        progress.update(percent, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32306).format(i+1, len(items), title))
                    elif isinstance(progress, xbmcgui.DialogProgress):
                        progress.update(percent, f"{ADDON.getLocalizedString(32307).format(i+1, len(items))}\n{title}")

                    collected = executor.collect_results(timeout=0.1)
                    for result_dbid, source_name, result in collected:
                        executor.process_result(result_dbid, source_name, result)

                    for check_dbid in executor.get_unfinalized_items():
                        check_state = executor.get_item_state(check_dbid)
                        if not check_state:
                            continue

                        all_sources_done = len(check_state.completed_sources) >= len(sources)
                        timed_out = executor.check_item_timeout(check_dbid)

                        if all_sources_done or timed_out:
                            if timed_out and not all_sources_done:
                                executor.timeout_pending_sources(check_dbid)

                            success, item_stats = _finalize_item_ratings(check_state, media_type)
                            executor.mark_item_finalized(check_dbid)
                            update_results(check_state.item, success, item_stats)
                            items_finalized += 1
                            ctx.mark_progress()

                while executor.get_pending_count() > 0 or executor.get_unfinalized_items():
                    if executor.is_cancelled():
                        results["cancelled"] = True
                        break

                    if isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled():
                        results["cancelled"] = True
                        break

                    collected = executor.collect_results(timeout=1.0)
                    for result_dbid, source_name, result in collected:
                        executor.process_result(result_dbid, source_name, result)

                    for check_dbid in executor.get_unfinalized_items():
                        check_state = executor.get_item_state(check_dbid)
                        if not check_state:
                            continue

                        all_sources_done = len(check_state.completed_sources) >= len(sources)
                        timed_out = executor.check_item_timeout(check_dbid)

                        if all_sources_done or timed_out:
                            if timed_out and not all_sources_done:
                                executor.timeout_pending_sources(check_dbid)

                            success, item_stats = _finalize_item_ratings(check_state, media_type)
                            executor.mark_item_finalized(check_dbid)
                            update_results(check_state.item, success, item_stats)
                            items_finalized += 1
                            ctx.mark_progress()

                            percent = int((items_finalized / len(items)) * 100)
                            if isinstance(progress, xbmcgui.DialogProgressBG):
                                progress.update(percent, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32308).format(items_finalized, len(items)))
                            elif isinstance(progress, xbmcgui.DialogProgress):
                                progress.update(percent, ADDON.getLocalizedString(32309).format(items_finalized, len(items)))

    if progress:
        progress.close()

    if retry_queue and not use_background and not results.get("cancelled"):
        retry_count = _prompt_and_process_retries(
            retry_queue, media_type, sources, source_mode
        )
        if retry_count > 0:
            results["retried"] = retry_count

    elapsed_time = time.time() - start_time
    results["elapsed_time"] = elapsed_time

    pending = results.get("pending_corrections", [])
    if pending and not use_background:
        results["imdb_ids_corrected"] = _prompt_imdb_corrections(pending)
    elif pending:
        log("Ratings", f"{len(pending)} IMDb ID redirects found but not corrected (background mode)", xbmc.LOGINFO)

    results.pop("pending_corrections", None)

    db.save_operation_stats('ratings_update', results, scope=media_type)

    if not use_background:
        cancelled_text = " (Cancelled)" if results.get("cancelled") else ""
        imdb_ids_text = f"\nIMDb IDs added: {results['imdb_ids_added']}" if results["imdb_ids_added"] > 0 else ""
        imdb_ids_corrected_text = f"\nIMDb IDs corrected: {results['imdb_ids_corrected']}" if results["imdb_ids_corrected"] > 0 else ""
        message = (
            f"Updated: {results['updated']}\n"
            f"Failed: {results['failed']}\n"
            f"Skipped: {results['skipped']}{cancelled_text}{imdb_ids_text}{imdb_ids_corrected_text}"
        )
        show_ok(ADDON.getLocalizedString(32317), message)

    xbmc.executebuiltin("Container.Refresh")

    return results


def _initialize_sources() -> List:
    """Initialize all available rating sources."""
    sources = []

    sources.append(TMDBRatingsSource())

    if _get_api_key("mdblist_api_key"):
        sources.append(MDBListRatingsSource())

    if _get_api_key("omdb_api_key"):
        sources.append(OMDbRatingsSource())

    if _get_api_key("trakt_access_token"):
        sources.append(TraktRatingsSource())

    return sources


class MdblistBatchFetcher:
    """
    Manages just-in-time batch fetching of MDBList data.

    Fetches 200 items at a time, triggered when main loop reaches batch boundaries.
    Data is stored in SQLite cache for item-by-item retrieval.
    """

    def __init__(self, items: List[Dict], media_type: str):
        self.media_type = media_type
        self.mdblist = MDBListRatingsSource() if _get_api_key("mdblist_api_key") else None
        self.daily_limit_reached = False

        self.tmdb_ids: list[str] = []
        for item in items:
            uniqueid = item.get("uniqueid", {})
            raw_tmdb = uniqueid.get("tmdb")
            imdb_id = uniqueid.get("imdb")
            resolved = resolve_tmdb_id(str(raw_tmdb) if raw_tmdb else None, imdb_id, media_type)
            self.tmdb_ids.append(resolved or "")

        self.total_items = len(self.tmdb_ids)
        self.batches_fetched = 0

    def fetch_batch_for_index(
        self,
        index: int,
        progress: xbmcgui.DialogProgress | xbmcgui.DialogProgressBG | None = None
    ) -> None:
        """
        Fetch MDBList batch if needed for the given item index.

        Called at the start of processing each item. Only fetches when:
        - Item is at a batch boundary (0, 200, 400, etc.)
        - MDBList is configured and not rate limited
        - Media type supports MDBList (not episodes)

        Args:
            index: Current item index in the processing loop
            progress: Optional progress dialog to update
        """
        if not self.mdblist or self.daily_limit_reached:
            return

        if self.media_type == "episode":
            return

        if index % MDBLIST_BATCH_SIZE != 0:
            return

        batch_start = index
        batch_end = min(index + MDBLIST_BATCH_SIZE, self.total_items)

        batch_ids = [
            {"id": tmdb_id}
            for tmdb_id in self.tmdb_ids[batch_start:batch_end]
            if tmdb_id
        ]

        if not batch_ids:
            return

        batch_num = (index // MDBLIST_BATCH_SIZE) + 1
        total_batches = (self.total_items + MDBLIST_BATCH_SIZE - 1) // MDBLIST_BATCH_SIZE

        log("Ratings", f"Fetching MDBList batch {batch_num}/{total_batches} ({len(batch_ids)} items)", xbmc.LOGDEBUG)

        if progress:
            if isinstance(progress, xbmcgui.DialogProgressBG):
                progress.update(
                    int((index / self.total_items) * 100),
                    ADDON.getLocalizedString(32300),
                    ADDON.getLocalizedString(32414).format(batch_num, total_batches)
                )
            elif isinstance(progress, xbmcgui.DialogProgress):
                progress.update(
                    int((index / self.total_items) * 100),
                    ADDON.getLocalizedString(32414).format(batch_num, total_batches)
                )

        try:
            self.mdblist.fetch_batch(self.media_type, batch_ids, provider="tmdb")
            self.batches_fetched += 1
        except RateLimitHit:
            log("Ratings", "MDBList daily limit reached", xbmc.LOGWARNING)
            self.daily_limit_reached = True


def _prompt_and_process_retries(
    retry_queue: List[Dict],
    media_type: str,
    sources: List,
    source_mode: str
) -> int:
    """
    Show retry dialog and process items with transient failures.

    Args:
        retry_queue: List of items with retryable failures
        media_type: Type of media being processed
        sources: List of rating sources
        source_mode: Source mode identifier

    Returns:
        Number of items successfully retried
    """
    count = len(retry_queue)

    failure_summary: Dict[str, int] = {}
    for entry in retry_queue:
        for failure in entry.get("failures", []):
            source = failure.get("source", "unknown")
            failure_summary[source] = failure_summary.get(source, 0) + 1

    summary_parts = [f"{source}: {cnt}" for source, cnt in sorted(failure_summary.items())]
    summary_text = ", ".join(summary_parts)

    message = (
        f"{ADDON.getLocalizedString(32416).format(count)}\n"
        f"({summary_text})\n\n"
        f"{ADDON.getLocalizedString(32417)}"
    )

    while True:
        result = show_yesnocustom(
            ADDON.getLocalizedString(32415),
            message,
            customlabel=ADDON.getLocalizedString(32427),
            nolabel=ADDON.getLocalizedString(32128),
            yeslabel=ADDON.getLocalizedString(32429)
        )

        if result == 2:
            lines = [f"[B]{ADDON.getLocalizedString(32419)}[/B]", ""]
            for entry in retry_queue:
                title = entry.get("title", "Unknown")
                year = entry.get("year", "")
                year_str = f" ({year})" if year else ""
                lines.append(f"{title}{year_str}")

                for failure in entry.get("failures", []):
                    source = failure.get("source", "unknown")
                    reason = failure.get("reason", "unknown error")
                    lines.append(f"  {source}: {reason}")
                lines.append("")

            show_textviewer(ADDON.getLocalizedString(32418), "\n".join(lines))

        elif result == 1:
            return _process_retry_queue(retry_queue, media_type, sources, source_mode)

        else:
            log("Ratings", f"User skipped retry of {count} item{'s' if count > 1 else ''}", xbmc.LOGINFO)
            return 0


def _process_retry_queue(
    retry_queue: List[Dict],
    media_type: str,
    sources: List,
    source_mode: str
) -> int:
    """
    Process retry queue items.

    Args:
        retry_queue: List of items to retry
        media_type: Type of media
        sources: List of rating sources
        source_mode: Source mode identifier

    Returns:
        Number of items successfully updated on retry
    """
    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32310))

    success_count = 0
    total = len(retry_queue)

    for i, entry in enumerate(retry_queue):
        if progress.iscanceled():
            break

        item = entry["item"]
        title = entry.get("title", "Unknown")

        percent = int((i / total) * 100)
        progress.update(percent, f"{ADDON.getLocalizedString(32311).format(i+1, total)}\n{title}")

        if source_mode == "imdb":
            success, _ = _update_single_item_imdb(item, media_type)
        else:
            success, _ = _update_single_item(item, media_type, sources)

        if success:
            success_count += 1
            log("Ratings", f"Retry succeeded: {title}", xbmc.LOGDEBUG)
        else:
            log("Ratings", f"Retry failed: {title}", xbmc.LOGDEBUG)

    progress.close()

    if success_count > 0:
        show_notification(
            ADDON.getLocalizedString(32300),
            ADDON.getLocalizedString(32420).format(success_count, total),
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

    return success_count


def _ensure_episode_dataset(
    progress: xbmcgui.DialogProgress | xbmcgui.DialogProgressBG | None = None
) -> None:
    """
    Ensure episode IMDb ID dataset is up to date.

    Silently refreshes the dataset if library episode count changed
    or IMDb published an update. Does nothing if already current.
    """
    library_ep_count_str = xbmc.getInfoLabel('Window(Home).Property(Episodes.Count)')
    try:
        library_ep_count = int(library_ep_count_str) if library_ep_count_str else 0
    except ValueError:
        library_ep_count = 0

    if library_ep_count == 0:
        return

    dataset = get_imdb_dataset()

    if not dataset.needs_episode_refresh(library_ep_count):
        return

    shows = get_library_items(["tvshow"], properties=["uniqueid"])
    user_show_ids: set[str] = set()
    for show in shows:
        imdb_id = show.get("uniqueid", {}).get("imdb")
        if imdb_id:
            user_show_ids.add(imdb_id)

    if not user_show_ids:
        log("Ratings", "No TV shows with IMDb IDs, skipping episode dataset refresh")
        return

    if progress:
        if isinstance(progress, xbmcgui.DialogProgressBG):
            progress.update(0, ADDON.getLocalizedString(32300), ADDON.getLocalizedString(32312))
        elif isinstance(progress, xbmcgui.DialogProgress):
            progress.update(0, ADDON.getLocalizedString(32312))

    def progress_callback(status: str) -> None:
        if progress:
            if isinstance(progress, xbmcgui.DialogProgressBG):
                progress.update(0, ADDON.getLocalizedString(32300), status)
            elif isinstance(progress, xbmcgui.DialogProgress):
                progress.update(0, status)

    dataset.refresh_episode_dataset(user_show_ids, library_ep_count, progress_callback)


def _prompt_imdb_corrections(pending: List[Dict]) -> int:
    """
    Prompt user to correct outdated IMDb IDs.

    Shows a 3-button dialog: Show (view list), Yes (apply all), No (skip)

    Args:
        pending: List of pending correction dicts

    Returns:
        Number of corrections applied
    """
    count = len(pending)
    message = f"{ADDON.getLocalizedString(32422).format(count)}\n\n{ADDON.getLocalizedString(32423)}"

    while True:
        result = show_yesnocustom(
            ADDON.getLocalizedString(32421),
            message,
            customlabel=ADDON.getLocalizedString(32427),
            nolabel=xbmc.getLocalizedString(106),
            yeslabel=xbmc.getLocalizedString(107)
        )

        if result == 2:
            lines = [f"[B]{ADDON.getLocalizedString(32421)}[/B]", ""]
            for item in pending:
                title = item.get("title", "Unknown")
                year = item.get("year", "")
                year_str = f" ({year})" if year else ""
                old_id = item.get("old_id", "")
                new_id = item.get("new_id", "")
                lines.append(f"{title}{year_str}")
                lines.append(f"  {old_id} -> {new_id}")
                lines.append("")

            show_textviewer(ADDON.getLocalizedString(32421), "\n".join(lines))

        elif result == 1:
            corrected = 0
            for item in pending:
                success = update_kodi_uniqueid(
                    item["media_type"],
                    item["dbid"],
                    item["uniqueid"],
                    item["new_id"]
                )
                if success:
                    corrected += 1
                    log("Ratings", f"Corrected IMDb ID: {item['old_id']} -> {item['new_id']} for {item['title']}", xbmc.LOGINFO)

            return corrected

        else:
            log("Ratings", f"User skipped {count} IMDb ID correction{'s' if count > 1 else ''}", xbmc.LOGINFO)
            return 0


def _prepare_imdb_update(
    item: Dict,
    media_type: str,
    dataset,
    db_cursor=None
) -> Optional[Tuple[int, Dict, str, float, int, str, str, bool]]:
    """
    Prepare an item for batched IMDb rating update.

    Args:
        item: Library item dictionary with ratings already fetched
        media_type: Type of media
        dataset: IMDb dataset instance
        db_cursor: Optional database cursor for bulk operations

    Returns:
        Tuple of (dbid, kodi_ratings, imdb_id, new_rating, new_votes, title, year, is_add)
        or None if item should be skipped
    """
    dbid = item.get("movieid") or item.get("episodeid") or item.get("tvshowid")
    if not dbid:
        return None

    title = item.get("title", "Unknown")
    year = item.get("year", "")
    uniqueid = item.get("uniqueid", {})
    existing_ratings = item.get("ratings", {})

    lookup_uniqueid = uniqueid

    if media_type == "episode":
        season_num = item.get("season")
        episode_num = item.get("episode")
        tvshow_dbid = item.get("tvshowid")
        if tvshow_dbid:
            tvshow_uniqueid = _get_tvshow_uniqueid(tvshow_dbid)
            if tvshow_uniqueid:
                lookup_uniqueid = tvshow_uniqueid

        imdb_id = uniqueid.get("imdb")
        if not imdb_id:
            show_imdb = lookup_uniqueid.get("imdb")
            if show_imdb and season_num is not None and episode_num is not None:
                imdb_id = dataset.get_episode_imdb_id(show_imdb, season_num, episode_num)
    else:
        imdb_id = uniqueid.get("imdb")

    if not imdb_id:
        return None

    imdb_rating = dataset.get_rating(imdb_id, cursor=db_cursor)
    if not imdb_rating:
        return None

    new_rating = imdb_rating["rating"]
    new_votes = imdb_rating["votes"]

    existing_imdb = existing_ratings.get("imdb", {})
    old_rating = existing_imdb.get("rating") if existing_imdb else None

    is_add = old_rating is None
    if not is_add and abs(old_rating - new_rating) <= 0.01:
        return None

    kodi_ratings = {
        "imdb": {
            "rating": new_rating,
            "votes": new_votes,
            "default": True
        }
    }
    _preserve_other_ratings(existing_ratings, kodi_ratings)

    return (dbid, kodi_ratings, imdb_id, new_rating, new_votes, title, str(year) if year else "", is_add)


def _update_single_item_imdb(
    item: Dict,
    media_type: str,
    abort_flag=None,
    db_cursor=None
) -> tuple[Optional[bool], Optional[Dict]]:
    """
    Update IMDb ratings for a single item using the dataset.

    Args:
        item: Library item dictionary
        media_type: Type of media
        abort_flag: Optional abort flag to check for cancellation
        db_cursor: Optional database cursor for bulk operations (avoids connection overhead)

    Returns:
        Tuple of (success status, item stats dict)
    """
    dbid = item.get("movieid") or item.get("episodeid") or item.get("tvshowid")
    if not dbid:
        return False, None

    title = item.get("title", "Unknown")
    year = item.get("year")
    uniqueid = item.get("uniqueid", {})
    existing_ratings = item.get("ratings", {})

    season_num: Optional[int] = None
    episode_num: Optional[int] = None
    lookup_uniqueid = uniqueid

    if media_type == "episode":
        season_num = item.get("season")
        episode_num = item.get("episode")
        tvshow_dbid = item.get("tvshowid")
        if tvshow_dbid:
            tvshow_uniqueid = _get_tvshow_uniqueid(tvshow_dbid)
            if tvshow_uniqueid:
                lookup_uniqueid = tvshow_uniqueid

    imdb_id = uniqueid.get("imdb") or None

    if not imdb_id and media_type == "episode":
        show_imdb = lookup_uniqueid.get("imdb")
        if show_imdb and season_num is not None and episode_num is not None:
            dataset = get_imdb_dataset()
            imdb_id = dataset.get_episode_imdb_id(show_imdb, season_num, episode_num)

    if not imdb_id:
        log("Ratings", f"Skipped (no IMDb ID): {title} ({year})", xbmc.LOGDEBUG)
        return None, None

    if abort_flag and abort_flag.is_requested():
        return None, None

    dataset = get_imdb_dataset()
    imdb_rating = dataset.get_rating(imdb_id, cursor=db_cursor)

    if not imdb_rating:
        log("Ratings", f"Skipped (no rating data): {title} ({year}) - {imdb_id}", xbmc.LOGDEBUG)
        return None, None

    new_rating = imdb_rating["rating"]
    new_votes = imdb_rating["votes"]

    existing_imdb = existing_ratings.get("imdb", {})
    old_rating = existing_imdb.get("rating") if existing_imdb else None

    added_ratings = []
    updated_ratings = []

    if old_rating is None:
        added_ratings.append(f"imdb ({new_rating:.1f})")
    elif abs(old_rating - new_rating) > 0.01:
        updated_ratings.append(f"imdb ({old_rating:.1f} -> {new_rating:.1f})")
    else:
        return True, None

    kodi_ratings = {
        "imdb": {
            "rating": new_rating,
            "votes": new_votes,
            "default": True
        }
    }

    _preserve_other_ratings(existing_ratings, kodi_ratings)

    method_info = KODI_SET_DETAILS_METHODS.get(media_type)
    if not method_info:
        return False, None
    method, id_key = method_info

    response = request(method, {id_key: dbid, "ratings": kodi_ratings})

    if response is not None:
        db.update_synced_ratings(
            media_type, dbid,
            {"imdb": {"rating": new_rating, "votes": new_votes}},
            {"imdb": imdb_id}
        )

    item_stats = {
        "title": title,
        "year": year,
        "sources_used": ["imdb_dataset"],
        "ratings_added": len(added_ratings),
        "ratings_updated": len(updated_ratings),
        "added_details": added_ratings,
        "updated_details": updated_ratings,
    }

    return response is not None, item_stats


def _prepare_item_for_batch(
    item: Dict,
    media_type: str
) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[Dict], Optional[Dict], Optional[List[Dict]], Optional[List[str]]]:
    """
    Prepare an item for batch processing by extracting IDs and fetching IMDb dataset rating.

    Returns:
        Tuple of (dbid, title, year, ids, existing_ratings, initial_ratings, initial_sources)
        Returns (None, None, None, None, None, None, None) if item should be skipped
    """
    dbid = item.get("movieid") or item.get("episodeid") or item.get("tvshowid")
    if not dbid:
        return None, None, None, None, None, None, None

    title = item.get("title", "Unknown")
    year = item.get("year", "")
    uniqueid = item.get("uniqueid", {})
    existing_ratings = item.get("ratings", {})

    if media_type == "episode":
        tvshow_dbid = item.get("tvshowid")
        if not tvshow_dbid:
            return None, None, None, None, None, None, None
        tvshow_uniqueid = _get_tvshow_uniqueid(tvshow_dbid)
        if not tvshow_uniqueid:
            return None, None, None, None, None, None, None
        show_imdb = tvshow_uniqueid.get("imdb")
        episode_imdb = uniqueid.get("imdb")
        season_num = item.get("season")
        episode_num = item.get("episode")
        if not episode_imdb and show_imdb:
            dataset = get_imdb_dataset()
            episode_imdb = dataset.get_episode_imdb_id(
                show_imdb,
                season_num or 0,
                episode_num or 0
            )
        # TMDB fallback if episode dataset didn't have the IMDb ID
        if not episode_imdb:
            episode_imdb = get_imdb_id_from_tmdb(
                media_type, tvshow_uniqueid, season_num, episode_num
            )
        ids = {
            "tmdb": tvshow_uniqueid.get("tmdb"),
            "imdb": show_imdb,
            "imdb_episode": episode_imdb,
            "tvdb": tvshow_uniqueid.get("tvdb"),
            "season": str(item.get("season", "")),
            "episode": str(item.get("episode", ""))
        }
    else:
        raw_tmdb = uniqueid.get("tmdb")
        raw_imdb = uniqueid.get("imdb")
        ids = {
            "tmdb": resolve_tmdb_id(raw_tmdb, raw_imdb, media_type),
            "imdb": raw_imdb,
            "tvdb": uniqueid.get("tvdb")
        }

    if not ids.get("tmdb") and not ids.get("imdb"):
        return None, None, None, None, None, None, None

    initial_ratings: List[Dict] = []
    initial_sources: List[str] = []

    # For episodes, only use episode-specific IMDb ID (don't fall back to show's IMDb)
    imdb_id = ids.get("imdb_episode") if media_type == "episode" else ids.get("imdb")
    if imdb_id:
        imdb_dataset = get_imdb_dataset()
        imdb_rating = imdb_dataset.get_rating(imdb_id)
        if imdb_rating:
            initial_ratings.append({
                "imdb": imdb_rating,
                "_source": "imdb_dataset"
            })
            initial_sources.append("imdb_dataset")

    return dbid, title, str(year) if year else "", ids, existing_ratings, initial_ratings, initial_sources


def _finalize_item_ratings(
    state: ItemState,
    media_type: str
) -> Tuple[Optional[bool], Optional[Dict]]:
    """
    Finalize ratings for an item by merging and applying to Kodi.

    Args:
        state: ItemState from batch executor
        media_type: Type of media

    Returns:
        Tuple of (success status, item stats dict)
    """
    all_ratings = state.ratings
    sources_used = state.sources_used
    retryable_failures = state.retryable_failures
    title = state.title
    year = state.year
    dbid = state.dbid
    existing_ratings = state.existing_ratings
    ids = state.ids

    if not all_ratings:
        log("Ratings", "No ratings returned from any source", xbmc.LOGDEBUG)
        if retryable_failures:
            return False, {
                "title": title,
                "year": year,
                "sources_used": [],
                "ratings_added": 0,
                "ratings_updated": 0,
                "added_details": [],
                "updated_details": [],
                "retryable_failures": retryable_failures
            }
        return False, None

    merged = merge_ratings(all_ratings)

    # Start with existing ratings as base to preserve them
    final_ratings: Dict[str, Dict[str, float]] = {}
    for rating_name, rating_data in existing_ratings.items():
        if isinstance(rating_data, dict) and rating_data.get("rating") is not None:
            final_ratings[rating_name] = {
                "rating": rating_data["rating"],
                "votes": float(rating_data.get("votes", 0))
            }

    # Merge in new ratings, only overwriting if higher vote count
    added_ratings = []
    updated_ratings = []
    for rating_name, rating_data in merged.items():
        new_val = rating_data.get("rating")
        if new_val is None:
            continue
        new_votes = float(rating_data.get("votes", 0))

        if rating_name in final_ratings:
            old_val = final_ratings[rating_name]["rating"]
            old_votes = final_ratings[rating_name]["votes"]

            # Only update if new rating has higher votes
            if new_votes > old_votes:
                final_ratings[rating_name] = {"rating": new_val, "votes": new_votes}
                if abs(old_val - new_val) > 0.01:
                    updated_ratings.append(f"{rating_name} ({old_val:.1f} -> {new_val:.1f})")
        else:
            # New rating, add it
            final_ratings[rating_name] = {"rating": new_val, "votes": new_votes}
            added_ratings.append(f"{rating_name} ({new_val:.1f})")

    kodi_ratings = prepare_kodi_ratings(final_ratings, default_source="imdb")

    if added_ratings:
        log("Ratings", f"Added ratings: {', '.join(added_ratings)}", xbmc.LOGDEBUG)
    if updated_ratings:
        log("Ratings", f"Updated ratings: {', '.join(updated_ratings)}", xbmc.LOGDEBUG)

    if not added_ratings and not updated_ratings:
        db.update_synced_ratings(media_type, dbid, final_ratings, _build_external_ids(ids))

        return True, {
            "title": title,
            "year": year,
            "sources_used": sources_used,
            "ratings_added": 0,
            "ratings_updated": 0,
            "added_details": [],
            "updated_details": [],
            "retryable_failures": retryable_failures
        }

    method_info = KODI_SET_DETAILS_METHODS.get(media_type)
    if not method_info:
        return False, None
    method, id_key = method_info

    response = request(method, {id_key: dbid, "ratings": kodi_ratings})

    if response is not None:
        db.update_synced_ratings(media_type, dbid, final_ratings, _build_external_ids(state.ids))

    item_stats = {
        "title": title,
        "year": year,
        "sources_used": sources_used,
        "ratings_added": len(added_ratings),
        "ratings_updated": len(updated_ratings),
        "added_details": added_ratings,
        "updated_details": updated_ratings,
        "retryable_failures": retryable_failures
    }

    return response is not None, item_stats


def _update_single_item(
    item: Dict,
    media_type: str,
    sources: List,
    abort_flag=None,
    force_refresh: bool = True
) -> tuple[Optional[bool], Optional[Dict]]:
    """
    Update ratings for a single item from API sources.

    Note: This is kept for single-item updates (e.g., from context menu).
    For batch updates, use RatingBatchExecutor instead.

    Args:
        item: Library item dictionary
        media_type: Type of media
        sources: List of rating sources
        abort_flag: Optional abort flag to check for cancellation
        force_refresh: If True, bypass cache read (default True for context menu)

    Returns:
        Tuple of (success status, item stats dict)
        success: True if updated, False if failed, None if skipped
        item_stats: Dictionary with item details and changes
    """
    dbid = item.get("movieid") or item.get("episodeid") or item.get("tvshowid")
    if not dbid:
        return False, None

    title = item.get("title", "Unknown")
    year = item.get("year")
    uniqueid = item.get("uniqueid", {})
    existing_ratings = item.get("ratings", {})

    if media_type == "episode":
        tvshow_dbid = item.get("tvshowid")
        if not tvshow_dbid:
            return None, None
        tvshow_uniqueid = _get_tvshow_uniqueid(tvshow_dbid)
        if not tvshow_uniqueid:
            return None, None
        show_imdb = tvshow_uniqueid.get("imdb")
        episode_imdb = uniqueid.get("imdb")
        season_num = item.get("season")
        episode_num = item.get("episode")
        if not episode_imdb and show_imdb:
            dataset = get_imdb_dataset()
            episode_imdb = dataset.get_episode_imdb_id(
                show_imdb,
                season_num or 0,
                episode_num or 0
            )
        # TMDB fallback if episode dataset didn't have the IMDb ID
        if not episode_imdb:
            episode_imdb = get_imdb_id_from_tmdb(
                media_type, tvshow_uniqueid, season_num, episode_num
            )
        ids = {
            "tmdb": tvshow_uniqueid.get("tmdb"),
            "imdb": show_imdb,
            "imdb_episode": episode_imdb,
            "tvdb": tvshow_uniqueid.get("tvdb"),
            "season": str(item.get("season", "")),
            "episode": str(item.get("episode", ""))
        }
    else:
        raw_tmdb = uniqueid.get("tmdb")
        raw_imdb = uniqueid.get("imdb")
        ids = {
            "tmdb": resolve_tmdb_id(raw_tmdb, raw_imdb, media_type),
            "imdb": raw_imdb,
            "tvdb": uniqueid.get("tvdb")
        }

    if not ids.get("tmdb") and not ids.get("imdb"):
        return None, None

    if abort_flag and abort_flag.is_requested():
        return None, None

    all_ratings = []
    sources_used = []

    # For episodes, only use episode-specific IMDb ID (don't fall back to show's IMDb)
    imdb_id = ids.get("imdb_episode") if media_type == "episode" else ids.get("imdb")
    if imdb_id:
        imdb_dataset = get_imdb_dataset()
        imdb_rating = imdb_dataset.get_rating(imdb_id)
        if imdb_rating:
            all_ratings.append({
                "imdb": imdb_rating,
                "_source": "imdb_dataset"
            })
            sources_used.append("imdb_dataset")

    retryable_failures: list[dict] = []

    MAX_TOTAL_WAIT = 30.0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {
            executor.submit(source.fetch_ratings, media_type, ids, abort_flag, force_refresh): source
            for source in sources
        }
        pending = set(futures.keys())

        while pending:
            if abort_flag and abort_flag.is_requested():
                executor.shutdown(wait=False)
                return None, None

            if (time.time() - start_time) > MAX_TOTAL_WAIT:
                for future in pending:
                    source = futures[future]
                    source_name = source.__class__.__name__.replace("Api", "").lower()
                    retryable_failures.append({"source": source_name, "reason": "timeout"})
                    log("Ratings", f"   {source_name}: Timeout after {MAX_TOTAL_WAIT}s", xbmc.LOGDEBUG)
                executor.shutdown(wait=False)
                break

            try:
                done = set()
                for future in as_completed(pending, timeout=1.0):
                    done.add(future)
                    source = futures[future]
                    source_name = source.__class__.__name__.replace("Api", "").lower()

                    try:
                        ratings = future.result()
                        if ratings:
                            all_ratings.append(ratings)
                            sources_used.append(source_name)
                    except RateLimitHit as e:
                        action = usage_tracker.handle_rate_limit_error(e.provider, 0, 1)
                        if action == "cancel_all":
                            if abort_flag:
                                abort_flag.request()
                            executor.shutdown(wait=False)
                            return None, None
                        if action == "cancel_batch":
                            executor.shutdown(wait=False)
                            return None, None
                        if action == "retry":
                            retryable_failures.append({"source": source_name, "reason": "rate limit (user chose wait)"})
                        log("Ratings", f"   {source_name}: Rate limit reached", xbmc.LOGDEBUG)
                    except RetryableError as e:
                        log("Ratings", f"   {source_name}: Retryable error: {e.reason}", xbmc.LOGDEBUG)
                        retryable_failures.append({"source": source_name, "reason": e.reason})
                    except Exception as e:
                        log("Ratings", f"   {source_name}: Failed: {str(e)}", xbmc.LOGDEBUG)

                pending -= done

            except FuturesTimeoutError:
                continue

    if not all_ratings:
        log("Ratings", "No ratings returned from any source", xbmc.LOGDEBUG)
        if retryable_failures:
            return False, {
                "title": title,
                "year": year,
                "sources_used": [],
                "ratings_added": 0,
                "ratings_updated": 0,
                "added_details": [],
                "updated_details": [],
                "retryable_failures": retryable_failures
            }
        return False, None

    merged = merge_ratings(all_ratings)

    # Start with existing ratings as base to preserve them
    final_ratings: Dict[str, Dict[str, float]] = {}
    for rating_name, rating_data in existing_ratings.items():
        if isinstance(rating_data, dict) and rating_data.get("rating") is not None:
            final_ratings[rating_name] = {
                "rating": rating_data["rating"],
                "votes": float(rating_data.get("votes", 0))
            }

    # Merge in new ratings, only overwriting if higher vote count
    added_ratings = []
    updated_ratings = []
    for rating_name, rating_data in merged.items():
        new_val = rating_data.get("rating")
        if new_val is None:
            continue
        new_votes = float(rating_data.get("votes", 0))

        if rating_name in final_ratings:
            old_val = final_ratings[rating_name]["rating"]
            old_votes = final_ratings[rating_name]["votes"]

            # Only update if new rating has higher votes
            if new_votes > old_votes:
                final_ratings[rating_name] = {"rating": new_val, "votes": new_votes}
                if abs(old_val - new_val) > 0.01:
                    updated_ratings.append(f"{rating_name} ({old_val:.1f} -> {new_val:.1f})")
        else:
            # New rating, add it
            final_ratings[rating_name] = {"rating": new_val, "votes": new_votes}
            added_ratings.append(f"{rating_name} ({new_val:.1f})")

    kodi_ratings = prepare_kodi_ratings(final_ratings, default_source="imdb")

    if added_ratings:
        log("Ratings", f"Added ratings: {', '.join(added_ratings)}", xbmc.LOGDEBUG)
    if updated_ratings:
        log("Ratings", f"Updated ratings: {', '.join(updated_ratings)}", xbmc.LOGDEBUG)

    if not added_ratings and not updated_ratings:
        db.update_synced_ratings(media_type, dbid, final_ratings, _build_external_ids(ids))

        return True, {
            "title": title,
            "year": year,
            "sources_used": sources_used,
            "ratings_added": 0,
            "ratings_updated": 0,
            "added_details": [],
            "updated_details": [],
            "retryable_failures": retryable_failures
        }

    method_info = KODI_SET_DETAILS_METHODS.get(media_type)
    if not method_info:
        return False, None
    method, id_key = method_info

    response = request(method, {id_key: dbid, "ratings": kodi_ratings})

    if response is not None:
        db.update_synced_ratings(media_type, dbid, final_ratings, _build_external_ids(ids))

    item_stats = {
        "title": title,
        "year": year,
        "sources_used": sources_used,
        "ratings_added": len(added_ratings),
        "ratings_updated": len(updated_ratings),
        "added_details": added_ratings,
        "updated_details": updated_ratings,
        "retryable_failures": retryable_failures
    }

    return response is not None, item_stats


def show_ratings_report() -> None:
    """Show the last ratings update report from operation history."""
    last_report = db.get_last_operation_stats('ratings_update')

    if not last_report:
        show_ok(
            ADDON.getLocalizedString(32430),
            ADDON.getLocalizedString(32424)
        )
        return

    stats = last_report['stats']
    scope = last_report.get('scope', 'unknown')
    timestamp = last_report['timestamp']

    scope_label_map = {
        "movie": "Movies",
        "tvshow": "TV Shows",
        "episode": "Episodes"
    }
    scope_label = scope_label_map.get(scope, scope.title())

    updated = stats.get('updated', 0)
    failed = stats.get('failed', 0)
    skipped = stats.get('skipped', 0)
    total_items = stats.get('total_items', 0)
    elapsed_time = stats.get('elapsed_time', 0)
    cancelled = stats.get('cancelled', False)
    source_stats = stats.get('source_stats', {})
    item_details = stats.get('item_details', [])
    source_mode = stats.get('source_mode', 'multi_source')

    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    status = "Cancelled" if cancelled else "Complete"

    source_mode_labels = {
        "imdb": "IMDb Dataset",
        "tmdb": "TMDB",
        "trakt": "Trakt",
        "aggregators": "Aggregators (MDBList, OMDB)",
        "multi_source": "All Sources"
    }
    source_label = source_mode_labels.get(source_mode, source_mode)

    lines = [
        f"[B]Ratings Update Report - {status}[/B]",
        "",
        f"Source: {source_label}",
        f"Scope: {scope_label}",
        f"Timestamp: {timestamp}",
        f"Duration: {time_str}",
        "",
        "[B]Summary[/B]",
        f"Total items found: {total_items}",
        f"Successfully updated: {updated}",
        f"Failed: {failed}",
        f"Skipped (no rating data): {skipped}",
        ""
    ]

    if source_stats:
        lines.extend([
            "[B]Source Statistics[/B]",
            ""
        ])

        sorted_sources = sorted(source_stats.items(), key=lambda x: x[0])
        for source_name, source_data in sorted_sources:
            fetched = source_data.get('fetched', 0)
            lines.append(f"{source_name.upper()}: {fetched} items fetched")

        lines.append("")

    total_ratings_added = stats.get('total_ratings_added', 0)
    total_ratings_updated = stats.get('total_ratings_updated', 0)
    imdb_ids_added = stats.get('imdb_ids_added', 0)
    imdb_ids_corrected = stats.get('imdb_ids_corrected', 0)

    if total_ratings_added > 0 or total_ratings_updated > 0 or imdb_ids_added > 0 or imdb_ids_corrected > 0:
        lines.extend([
            "[B]Rating Changes[/B]",
            f"Total ratings added: {total_ratings_added}",
            f"Total ratings updated: {total_ratings_updated}",
        ])
        if imdb_ids_added > 0:
            lines.append(f"IMDb IDs added to library: {imdb_ids_added}")
        if imdb_ids_corrected > 0:
            lines.append(f"IMDb IDs corrected (redirects): {imdb_ids_corrected}")
        lines.append("")

    if item_details and len(item_details) <= 20:
        lines.extend([
            "[B]Detailed Changes[/B]",
            ""
        ])

        for item in item_details:
            if item.get('ratings_added', 0) > 0 or item.get('ratings_updated', 0) > 0:
                title = item.get('title', 'Unknown')
                year = item.get('year', '')
                year_str = f" ({year})" if year else ""

                lines.append(f"{title}{year_str}:")

                added = item.get('added_details', [])
                if added:
                    lines.append(f"  Added: {', '.join(added)}")

                updated = item.get('updated_details', [])
                if updated:
                    lines.append(f"  Updated: {', '.join(updated)}")

                lines.append("")

    text = "\n".join(lines)

    show_textviewer(ADDON.getLocalizedString(32430), text)
