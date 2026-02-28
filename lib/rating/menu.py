"""Ratings menu entry points, mode selection, and report display."""
from __future__ import annotations

from typing import List, Optional
import xbmc
import xbmcgui

from lib.infrastructure import tasks as task_manager
from lib.kodi.client import request, _get_api_key, log, KODI_GET_DETAILS_METHODS, ADDON
from lib.data.api.tmdb import ApiTmdb as TMDBRatingsSource
from lib.data.api.mdblist import ApiMdblist as MDBListRatingsSource
from lib.data.api.omdb import ApiOmdb as OMDbRatingsSource
from lib.data.api.trakt import ApiTrakt as TraktRatingsSource
from lib.data.api.imdb import get_imdb_dataset
from lib.infrastructure.dialogs import show_ok, show_textviewer, show_notification
from lib.infrastructure.menus import Menu, MenuItem
from lib.data.database import workflow as db
from lib.data.database._infrastructure import init_database
from lib.rating.updater import (
    update_library_ratings,
    update_single_item,
    update_tvshow_episodes,
)


def _initialize_sources() -> List:
    """Initialize all available rating sources."""
    sources = []
    sources.append(TMDBRatingsSource())
    if _get_api_key("mdblist_api_key"):
        sources.append(MDBListRatingsSource())
    if _get_api_key("omdb_api_key"):
        sources.append(OMDbRatingsSource())
    sources.append(TraktRatingsSource())
    return sources


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


def update_single_item_ratings(dbid: Optional[str], dbtype: Optional[str]) -> None:
    """Update ratings for a single item by DBID."""
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

    init_database()

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

    success, item_stats = update_single_item(item, media_type, sources)

    total_added = item_stats.get('added_details', []) if item_stats else []
    total_updated = item_stats.get('updated_details', []) if item_stats else []
    episodes_updated = 0

    if media_type == "tvshow" and success:
        episodes_updated = update_tvshow_episodes(int(dbid), sources)

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

                updated_details = item.get('updated_details', [])
                if updated_details:
                    lines.append(f"  Updated: {', '.join(updated_details)}")

                lines.append("")

    text = "\n".join(lines)

    show_textviewer(ADDON.getLocalizedString(32430), text)
