"""Ratings updater coordinator - main entry point for ratings updates."""
from __future__ import annotations

from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import xbmc
import xbmcgui
import xbmcaddon

from resources.lib import task_manager
from resources.lib.kodi import request, get_library_items, _get_api_key
from resources.lib.api.tmdb import TMDBApi as TMDBRatingsSource
from resources.lib.api.mdblist import MDBListRatingsSource
from resources.lib.api.omdb import OMDbRatingsSource
from resources.lib.api.trakt import TraktRatingsSource
from resources.lib.ratings.source import DailyLimitReached
from resources.lib.ratings.merger import merge_ratings, prepare_kodi_ratings
from resources.lib.ratings import usage_tracker
from resources.lib.ui_helper import show_menu_with_cancel
from resources.lib.database import workflow as db
from resources.lib.database._infrastructure import init_database


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
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            "No valid item selected",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    media_type = dbtype.lower()
    if media_type not in ("movie", "tvshow", "episode"):
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            f"Unsupported media type: {media_type}",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    xbmc.log(f"script.skin.info.service: Updating ratings for single item - dbid={dbid}, dbtype={media_type}", xbmc.LOGINFO)

    sources = _initialize_sources()
    if not sources:
        xbmcgui.Dialog().ok(
            "Ratings Updater",
            "No rating sources available. Please configure API keys in settings."
        )
        return

    if media_type == "episode":
        properties = ["title", "season", "episode", "tvshowid", "uniqueid", "ratings"]
    else:
        properties = ["title", "year", "uniqueid", "ratings"]

    method_map = {
        "movie": ("VideoLibrary.GetMovieDetails", "movieid", "moviedetails"),
        "tvshow": ("VideoLibrary.GetTVShowDetails", "tvshowid", "tvshowdetails"),
        "episode": ("VideoLibrary.GetEpisodeDetails", "episodeid", "episodedetails")
    }

    method_info = method_map.get(media_type)
    if not method_info:
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            f"Unsupported media type: {media_type}",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    method_name, id_key, result_key = method_info

    response = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": method_name,
        "params": {
            id_key: int(dbid),
            "properties": properties
        },
        "id": 1
    }))

    result = json.loads(response)
    if "result" not in result or result_key not in result["result"]:
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            f"{media_type.title()} not found",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
        return

    item = result["result"][result_key]
    title = item.get("title", "Unknown")

    xbmcgui.Dialog().notification(
        "Ratings Updater",
        "Updating ratings...",
        xbmcgui.NOTIFICATION_INFO,
        2000
    )

    success, item_stats = _update_single_item(item, media_type, sources, use_background=False)

    if success:
        added_details = item_stats.get('added_details', []) if item_stats else []
        updated_details = item_stats.get('updated_details', []) if item_stats else []

        if added_details or updated_details:
            message_lines = []

            if added_details:
                message_lines.append(f"[B]Added:[/B] {', '.join(added_details)}")

            if updated_details:
                message_lines.append(f"[B]Updated:[/B] {', '.join(updated_details)}")

            xbmcgui.Dialog().ok(f"Ratings Updated - {title}", "[CR]".join(message_lines))
        else:
            xbmcgui.Dialog().notification(
                "Ratings Updater",
                "No changes needed",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )

        xbmc.executebuiltin("Container.Refresh")
    elif success is None:
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            "Item skipped (no IDs or rate limit)",
            xbmcgui.NOTIFICATION_WARNING,
            3000
        )
    else:
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            "Failed to update ratings",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )


def run_ratings_menu() -> None:
    """Show ratings updater menu and route to selected option."""
    sources = {
        "TMDB": _get_api_key("tmdb_api_key"),
        "MDBList": _get_api_key("mdblist_api_key"),
        "OMDb": _get_api_key("omdb_api_key"),
        "Trakt": _get_api_key("trakt_access_token")
    }
    configured = [k for k, v in sources.items() if v]
    missing = [k for k, v in sources.items() if not v]

    if not configured:
        xbmcgui.Dialog().ok("Ratings Updater", "No API keys configured. Configure at least one in settings.")
        return

    if missing:
        message = f"Configured: {', '.join(configured)}\nMissing: {', '.join(missing)}\n\nContinue?"
        if not xbmcgui.Dialog().yesno("Ratings Updater", message):
            return

    init_database()

    while True:
        action_options = [("Update Ratings", "update")]

        if db.get_last_operation_stats('ratings_update'):
            action_options.append(("View Last Report", "report"))

        action, cancelled = show_menu_with_cancel("Ratings Updater", action_options)

        if cancelled or action is None:
            return

        if action == "report":
            show_ratings_report()
            continue

        media_type_options = [
            ("Update All Movie Ratings", "movies"),
            ("Update All TV Show Ratings", "tvshows"),
            ("Update All Episode Ratings", "episodes")
        ]

        media_type_value, media_type_cancelled = show_menu_with_cancel("Ratings Updater - Select Media Type", media_type_options)

        if media_type_cancelled or media_type_value is None:
            continue

        mode_options = [
            ("Show progress dialog (Foreground)", "foreground"),
            ("Run in background", "background")
        ]

        mode_value, mode_cancelled = show_menu_with_cancel("Run Mode", mode_options)

        if mode_cancelled or mode_value is None:
            continue

        use_background = (mode_value == "background")

        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                xbmcgui.Dialog().ok(
                    "Task Already Running",
                    f"Another background task is currently running:[CR]{current_task}[CR][CR]Cannot start ratings update in background."
                )
                continue

        if media_type_value == "movies":
            update_library_ratings("movie", use_background)
        elif media_type_value == "tvshows":
            update_library_ratings("tvshow", use_background)
        elif media_type_value == "episodes":
            update_library_ratings("episode", use_background)

        return


def update_library_ratings(media_type: str, use_background: bool = False) -> Dict[str, int]:
    """
    Update ratings for all items of a media type.

    Args:
        media_type: Type of media ("movie", "tvshow", "episode")
        use_background: Whether to run in background mode

    Returns:
        Dictionary with update statistics
    """
    start_time = time.time()
    usage_tracker.reset_session_skip()

    sources = _initialize_sources()
    if not sources:
        xbmcgui.Dialog().ok(
            "Ratings Updater",
            "No rating sources available. Please configure API keys in settings."
        )
        return {"updated": 0, "failed": 0, "skipped": 0}

    if media_type == "episode":
        properties = ["title", "season", "episode", "tvshowid", "uniqueid", "ratings"]
    else:
        properties = ["title", "year", "uniqueid", "ratings"]

    progress: xbmcgui.DialogProgress | xbmcgui.DialogProgressBG
    if use_background:
        progress = xbmcgui.DialogProgressBG()
        progress.create("Ratings Updater", f"Loading {media_type}s...")
    else:
        progress = xbmcgui.DialogProgress()
        progress.create("Ratings Updater", f"Loading {media_type}s...")

    items = get_library_items([media_type], properties=properties)
    if not items:
        if progress:
            progress.close()
        xbmcgui.Dialog().notification(
            "Ratings Updater",
            f"No {media_type}s found in library",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return {"updated": 0, "failed": 0, "skipped": 0}

    if isinstance(progress, xbmcgui.DialogProgressBG):
        progress.update(0, "Ratings Updater", f"Updating {len(items)} {media_type}s...")
    elif isinstance(progress, xbmcgui.DialogProgress):
        progress.update(0, f"Updating {len(items)} {media_type}s...")

    results = {
        "updated": 0,
        "failed": 0,
        "skipped": 0,
        "total_items": len(items),
        "source_stats": {},
        "item_details": []
    }

    with task_manager.TaskContext("Update Library Ratings") as ctx:
        for i, item in enumerate(items):
            if ctx.abort_flag.is_requested():
                results["cancelled"] = True
                break

            if isinstance(progress, xbmcgui.DialogProgress) and progress.iscanceled():
                results["cancelled"] = True
                break

            percent = int((i / len(items)) * 100)
            title = item.get("title", "Unknown")

            if isinstance(progress, xbmcgui.DialogProgressBG):
                progress.update(percent, "Ratings Updater", f"Updating: {i+1}/{len(items)} - {title} ")
            elif isinstance(progress, xbmcgui.DialogProgress):
                progress.update(percent, f"Updating: {i+1}/{len(items)} items\n{title}")

            success, item_stats = _update_single_item(item, media_type, sources, use_background, ctx.abort_flag)

            if success:
                results["updated"] += 1
            elif success is None:
                results["skipped"] += 1
            else:
                results["failed"] += 1

            if item_stats:
                results["item_details"].append(item_stats)

                for source_name in item_stats.get("sources_used", []):
                    if source_name not in results["source_stats"]:
                        results["source_stats"][source_name] = {"fetched": 0, "failed": 0}
                    results["source_stats"][source_name]["fetched"] += 1

            enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')
            if enable_debug and ((i + 1) % 10 == 0 or i == len(items) - 1):
                xbmc.log(
                    f"SkinInfo [Ratings]: Progress: {i+1}/{len(items)} items "
                    f"(updated: {results['updated']}, failed: {results['failed']}, skipped: {results['skipped']})",
                    xbmc.LOGDEBUG
                )

            ctx.mark_progress()

            xbmc.executebuiltin("Container.Refresh")

    if progress:
        progress.close()

    elapsed_time = time.time() - start_time
    results["elapsed_time"] = elapsed_time

    db.save_operation_stats('ratings_update', results, scope=media_type)

    if not use_background:
        cancelled_text = " (Cancelled)" if results.get("cancelled") else ""
        message = (
            f"Updated: {results['updated']}\n"
            f"Failed: {results['failed']}\n"
            f"Skipped: {results['skipped']}{cancelled_text}"
        )
        xbmcgui.Dialog().ok("Ratings Updater - Complete", message)

    return results


def _initialize_sources() -> List:
    """Initialize available rating sources."""
    sources = []

    if _get_api_key("tmdb_api_key"):
        sources.append(TMDBRatingsSource())

    if _get_api_key("mdblist_api_key"):
        sources.append(MDBListRatingsSource())

    if _get_api_key("omdb_api_key"):
        sources.append(OMDbRatingsSource())

    if _get_api_key("trakt_access_token"):
        sources.append(TraktRatingsSource())

    return sources


def _update_single_item(item: Dict, media_type: str, sources: List, use_background: bool = False, abort_flag=None) -> tuple[Optional[bool], Optional[Dict]]:
    """
    Update ratings for a single item.

    Args:
        item: Library item dictionary
        media_type: Type of media
        sources: List of rating sources
        use_background: Whether running in background mode
        abort_flag: Optional abort flag to check for cancellation

    Returns:
        Tuple of (success status, item stats dict)
        success: True if updated, False if failed, None if skipped
        item_stats: Dictionary with item details and changes
    """
    enable_debug = xbmcaddon.Addon().getSettingBool('enable_debug')

    dbid = item.get("movieid") or item.get("episodeid") or item.get("tvshowid")
    if not dbid:
        return False, None

    title = item.get("title", "Unknown")
    year = item.get("year")
    uniqueid = item.get("uniqueid", {})
    existing_ratings = item.get("ratings", {})

    if media_type == "episode":
        tvshow_dbid = item.get("tvshowid")
        if tvshow_dbid:
            tvshow = xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetTVShowDetails",
                "params": {
                    "tvshowid": tvshow_dbid,
                    "properties": ["uniqueid"]
                },
                "id": 1
            }))
            tvshow_data = json.loads(tvshow)
            if "result" in tvshow_data and "tvshowdetails" in tvshow_data["result"]:
                tvshow_uniqueid = tvshow_data["result"]["tvshowdetails"].get("uniqueid", {})
                ids = {
                    "tmdb": tvshow_uniqueid.get("tmdb"),
                    "imdb": tvshow_uniqueid.get("imdb"),
                    "tvdb": tvshow_uniqueid.get("tvdb"),
                    "season": str(item.get("season", "")),
                    "episode": str(item.get("episode", ""))
                }
            else:
                return None, None
        else:
            return None, None
    else:
        ids = {
            "tmdb": uniqueid.get("tmdb"),
            "imdb": uniqueid.get("imdb"),
            "tvdb": uniqueid.get("tvdb")
        }

    if not ids.get("tmdb") and not ids.get("imdb"):
        return None, None

    if enable_debug:
        id_str = ", ".join([f"{k}={v}" for k, v in ids.items() if v and k in ["tmdb", "imdb", "tvdb"]])
        xbmc.log(f"SkinInfo [Ratings]: [dbid={dbid}] '{title}' ({year}) - {id_str}", xbmc.LOGDEBUG)

    if abort_flag and abort_flag.is_requested():
        return None, None

    all_ratings = []
    sources_used = []
    source_timings = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(source.fetch_ratings, media_type, ids): source for source in sources}

        try:
            for future in as_completed(futures, timeout=1.0):
                if abort_flag and abort_flag.is_requested():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return None, None

                source = futures[future]
                source_name = source.__class__.__name__.replace("RatingsSource", "").lower()

                start_time = time.time() if enable_debug else 0.0

                try:
                    ratings = future.result()

                    elapsed = int((time.time() - start_time) * 1000) if enable_debug else 0
                    if enable_debug:
                        source_timings[source_name] = elapsed

                    if ratings:
                        all_ratings.append(ratings)
                        sources_used.append(source_name)

                except DailyLimitReached as e:
                    action = usage_tracker.handle_rate_limit_error(e.provider, 0, 1)
                    if action in ("cancel_all", "cancel_batch"):
                        return None, None
                    if enable_debug:
                        xbmc.log(f"SkinInfo [Ratings]:   Querying {source_name}... Rate limit reached", xbmc.LOGDEBUG)
                except Exception as e:
                    if enable_debug:
                        elapsed = int((time.time() - start_time) * 1000)
                        xbmc.log(f"SkinInfo [Ratings]:   Querying {source_name}... Failed ({elapsed}ms): {str(e)}", xbmc.LOGDEBUG)
        except TimeoutError:
            if abort_flag and abort_flag.is_requested():
                executor.shutdown(wait=False, cancel_futures=True)
                return None, None

    if not all_ratings:
        if enable_debug:
            xbmc.log("SkinInfo [Ratings]:   No ratings returned from any source", xbmc.LOGDEBUG)
        return False, None

    if enable_debug:
        source_summary = ", ".join([f"{src} ({source_timings.get(src, 0)}ms)" for src in sources_used])
        xbmc.log(f"SkinInfo [Ratings]:   Sources: {source_summary}", xbmc.LOGDEBUG)

    merged = merge_ratings(all_ratings)
    kodi_ratings = prepare_kodi_ratings(merged, default_source="imdb")

    added_ratings = []
    updated_ratings = []
    skipped_ratings = []

    for rating_name, rating_data in merged.items():
        old_rating = existing_ratings.get(rating_name, {})
        old_val = old_rating.get('rating') if old_rating else None
        new_val = rating_data.get('rating')

        if old_val is None:
            added_ratings.append(f"{rating_name} ({new_val:.1f})")
        elif abs(old_val - new_val) > 0.01:
            updated_ratings.append(f"{rating_name} ({old_val:.1f} -> {new_val:.1f})")
        else:
            skipped_ratings.append(f"{rating_name} ({new_val:.1f})")

    if enable_debug and (added_ratings or updated_ratings or skipped_ratings):
        xbmc.log("SkinInfo [Ratings]:   Database changes:", xbmc.LOGDEBUG)
        if added_ratings:
            xbmc.log(f"SkinInfo [Ratings]:     Added: {', '.join(added_ratings)}", xbmc.LOGDEBUG)
        if updated_ratings:
            xbmc.log(f"SkinInfo [Ratings]:     Updated: {', '.join(updated_ratings)}", xbmc.LOGDEBUG)
        if skipped_ratings:
            xbmc.log(f"SkinInfo [Ratings]:     Unchanged: {', '.join(skipped_ratings)}", xbmc.LOGDEBUG)

    method_map = {
        "movie": "VideoLibrary.SetMovieDetails",
        "tvshow": "VideoLibrary.SetTVShowDetails",
        "episode": "VideoLibrary.SetEpisodeDetails"
    }
    id_key_map = {
        "movie": "movieid",
        "tvshow": "tvshowid",
        "episode": "episodeid"
    }

    method = method_map.get(media_type)
    id_key = id_key_map.get(media_type)

    if not method or not id_key:
        return False, None

    response = request(method, {id_key: dbid, "ratings": kodi_ratings})

    if enable_debug:
        status = "Success" if response is not None else "Failed"
        xbmc.log(f"SkinInfo [Ratings]: [dbid={dbid}] Finished updating '{title}' ({year}) - {status}", xbmc.LOGDEBUG)

    item_stats = {
        "title": title,
        "year": year,
        "sources_used": sources_used,
        "ratings_added": len(added_ratings),
        "ratings_updated": len(updated_ratings),
        "added_details": added_ratings,
        "updated_details": updated_ratings
    }

    return response is not None, item_stats


def show_ratings_report() -> None:
    """Show the last ratings update report from operation history."""
    last_report = db.get_last_operation_stats('ratings_update')

    if not last_report:
        xbmcgui.Dialog().ok(
            "Ratings Update Report",
            "No ratings update history found."
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

    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    status = "Cancelled" if cancelled else "Complete"

    lines = [
        f"[B]Ratings Update Report - {status}[/B]",
        "",
        f"Scope: {scope_label}",
        f"Timestamp: {timestamp}",
        f"Duration: {time_str}",
        "",
        "[B]Summary[/B]",
        f"Total items found: {total_items}",
        f"Successfully updated: {updated}",
        f"Failed: {failed}",
        f"Skipped (no IDs): {skipped}",
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

    total_ratings_added = sum(item.get('ratings_added', 0) for item in item_details)
    total_ratings_updated = sum(item.get('ratings_updated', 0) for item in item_details)

    if total_ratings_added > 0 or total_ratings_updated > 0:
        lines.extend([
            "[B]Rating Changes[/B]",
            f"Total ratings added: {total_ratings_added}",
            f"Total ratings updated: {total_ratings_updated}",
            ""
        ])

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

    xbmcgui.Dialog().textviewer("Ratings Update Report", text)
