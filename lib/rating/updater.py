"""Ratings updater orchestrator: full-library update, per-show update, batch coordination."""
from __future__ import annotations

from typing import Dict, List, Set
import time

import xbmc
import xbmcgui

from lib.infrastructure import tasks as task_manager
from lib.kodi.client import request, get_library_items, log, ADDON
from lib.data.api.imdb import get_imdb_dataset
from lib.data.api import tracker as usage_tracker
from lib.data.api.trakt import ApiTrakt
from lib.data.database import workflow as db
from lib.infrastructure.dialogs import show_ok, show_notification
from lib.rating.executor import RetryPoolEntry
from lib.rating.ids import (
    clear_tvshow_uniqueid_cache,
    prefetch_tvshow_uniqueids,
    get_tvshow_uniqueid,
)
from lib.rating.single import update_single_item
from lib.rating.imdb import (
    run_imdb_batch,
    ensure_episode_dataset,
    prompt_imdb_corrections,
)
from lib.rating.batch import MdblistBatchFetcher, run_multi_source_batch
from lib.rating.retry import prompt_and_process_retries


def _prefetch_trakt_seasons(
    tvshow_dbid: int, episodes: List[Dict], sources: List
) -> None:
    """Prefetch Trakt episode data per-season for a show's episodes."""
    trakt_source = next((s for s in sources if isinstance(s, ApiTrakt)), None)
    if not trakt_source:
        return

    show_uniqueid = get_tvshow_uniqueid(tvshow_dbid)
    show_imdb = show_uniqueid.get("imdb")
    if not show_imdb:
        return

    seasons: Set[int] = set()
    for ep in episodes:
        s = ep.get("season")
        if s is not None:
            seasons.add(s)
    for season in sorted(seasons):
        trakt_source.prefetch_season(show_imdb, season)


def _prefetch_trakt_seasons_batch(
    items: List[Dict], sources: List
) -> None:
    """Prefetch Trakt episode data for all show+season combos in a batch."""
    trakt_source = next((s for s in sources if isinstance(s, ApiTrakt)), None)
    if not trakt_source:
        return

    show_seasons: Dict[int, Set[int]] = {}
    for item in items:
        tvshow_dbid = item.get("tvshowid")
        season = item.get("season")
        if tvshow_dbid and season is not None:
            show_seasons.setdefault(tvshow_dbid, set()).add(season)

    for tvshow_dbid, seasons in show_seasons.items():
        show_uniqueid = get_tvshow_uniqueid(tvshow_dbid)
        show_imdb = show_uniqueid.get("imdb")
        if not show_imdb:
            continue
        for season in sorted(seasons):
            trakt_source.prefetch_season(show_imdb, season)


def update_tvshow_episodes(tvshow_dbid: int, sources: List) -> int:
    """Update ratings for every episode of a show. Returns count actually updated."""
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

    _prefetch_trakt_seasons(tvshow_dbid, episodes, sources)

    updated_count = 0
    for episode in episodes:
        success, _ = update_single_item(episode, "episode", sources, force_refresh=False)
        if success:
            updated_count += 1

    return updated_count




def update_library_ratings(
    media_type: str,
    sources: List,
    use_background: bool = False,
    source_mode: str = "multi_source"
) -> Dict[str, int]:
    """Update ratings for all items of a media type."""
    start_time = time.time()
    usage_tracker.reset_session_skip()

    if media_type == "episode":
        clear_tvshow_uniqueid_cache()
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
        "updated": 0, "failed": 0, "skipped": 0,
        "total_items": len(items), "source_stats": {}, "item_details": [],
        "total_ratings_added": 0, "total_ratings_updated": 0,
        "imdb_ids_added": 0, "imdb_ids_corrected": 0,
        "pending_corrections": [], "source_mode": source_mode,
    }

    retry_queue: List[RetryPoolEntry] = []
    dataset_date: str = ""
    processed_ids: Set[int] = set()

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
                log("Ratings", f"Resuming IMDb update for {media_type}: {len(processed_ids)}/{len(items)} already processed")
            else:
                db.clear_imdb_update_progress(media_type)
                log("Ratings", f"New IMDb dataset detected, starting fresh for {media_type}")

    mdblist_fetcher: MdblistBatchFetcher | None = None
    if source_mode == "multi_source" and media_type in ("movie", "tvshow"):
        mdblist_fetcher = MdblistBatchFetcher(items, media_type)

    if media_type == "episode":
        ensure_episode_dataset(progress)
        prefetch_tvshow_uniqueids()
        if source_mode == "multi_source":
            _prefetch_trakt_seasons_batch(items, sources)

    monitor = xbmc.Monitor()

    with task_manager.TaskContext("Update Library Ratings") as ctx:
        if source_mode == "imdb":
            run_imdb_batch(media_type, items, progress, results, ctx, monitor, dataset_date, processed_ids)
        else:
            run_multi_source_batch(media_type, items, sources, progress, results, retry_queue, ctx, mdblist_fetcher)

    if progress:
        progress.close()

    if retry_queue and not use_background and not results.get("cancelled"):
        retry_count = prompt_and_process_retries(
            retry_queue, media_type, sources, source_mode
        )
        if retry_count > 0:
            results["retried"] = retry_count

    elapsed_time = time.time() - start_time
    results["elapsed_time"] = elapsed_time

    pending = results.get("pending_corrections", [])
    if pending and not use_background:
        results["imdb_ids_corrected"] = prompt_imdb_corrections(pending)
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

