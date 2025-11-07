"""Texture cache management UI and menu handlers."""
from __future__ import annotations

import xbmc
import xbmcaddon
import xbmcgui
from datetime import datetime
from typing import Optional, List, Union, Dict, Any

from lib.data.database import init_database
from lib.data.database.workflow import save_operation_stats, get_last_operation_stats
from lib.infrastructure.dialogs import format_operation_report, show_ok, show_textviewer
from lib.infrastructure.menus import confirm_cancel_running_task
from lib.kodi.client import log
from lib.kodi.settings import KodiSettings
from lib.texture.cache import (
    get_cached_textures,
    remove_texture,
    precache_library_artwork,
    precache_and_download_artwork,
    cleanup_orphaned_textures,
)
from lib.texture.stats import calculate_texture_statistics, format_statistics_report

ADDON = xbmcaddon.Addon()


def run_texture_maintenance() -> None:
    """
    Show texture cache manager menu and execute selected operations.

    Available operations:
    - Pre-Cache Library Artwork: Cache all library artwork not yet cached
    - Cleanup Textures: Remove orphaned/old/unused textures
    - Statistics & Info: View texture cache statistics
    - View Last Report: Show stats from last completed operation
    """
    from lib.infrastructure.menus import Menu, MenuItem

    init_database()

    precache_stats = get_last_operation_stats('texture_precache')
    cleanup_stats = get_last_operation_stats('texture_cleanup')

    last_stats = None
    if precache_stats and cleanup_stats:
        precache_time = datetime.fromisoformat(precache_stats['timestamp'])
        cleanup_time = datetime.fromisoformat(cleanup_stats['timestamp'])
        last_stats = precache_stats if precache_time > cleanup_time else cleanup_stats
    elif precache_stats:
        last_stats = precache_stats
    elif cleanup_stats:
        last_stats = cleanup_stats

    items = [
        MenuItem(ADDON.getLocalizedString(32083), _handle_precache, loop=True),
    ]

    if KodiSettings.enable_combo_workflows():
        items.append(MenuItem(ADDON.getLocalizedString(32440), _handle_precache_download, loop=True))

    items.extend([
        MenuItem(ADDON.getLocalizedString(32087), _show_cleanup_menu, loop=True),
        MenuItem(ADDON.getLocalizedString(32085), _handle_stats, loop=True),
    ])

    if last_stats:
        items.append(MenuItem(ADDON.getLocalizedString(32086), _show_last_report, loop=True))

    menu = Menu(ADDON.getLocalizedString(32082), items)
    menu.show()


def _handle_precache():
    """Handle pre-cache library artwork operation."""
    from lib.infrastructure.menus import Menu, MenuItem

    scope_menu = Menu(ADDON.getLocalizedString(32441), [
        MenuItem(xbmc.getLocalizedString(593), lambda: _run_precache(None, False)),
        MenuItem(xbmc.getLocalizedString(342), lambda: _run_precache(["movie"], False)),
        MenuItem(xbmc.getLocalizedString(20343), lambda: _run_precache(["tvshow"], False)),
        MenuItem(xbmc.getLocalizedString(33054), lambda: _run_precache(["season"], False)),
        MenuItem(xbmc.getLocalizedString(20360), lambda: _run_precache(["episode"], False)),
        MenuItem(xbmc.getLocalizedString(20389), lambda: _run_precache(["musicvideo"], False)),
        MenuItem(xbmc.getLocalizedString(20434), lambda: _run_precache(["set"], False)),
        MenuItem(xbmc.getLocalizedString(133), lambda: _run_precache(["artist"], False)),
        MenuItem(xbmc.getLocalizedString(132), lambda: _run_precache(["album"], False)),
    ])
    return scope_menu.show()


def _handle_precache_download():
    """Handle pre-cache + download library artwork operation."""
    from lib.infrastructure.menus import Menu, MenuItem

    scope_menu = Menu(ADDON.getLocalizedString(32451), [
        MenuItem(xbmc.getLocalizedString(593), lambda: _run_precache(None, True)),
        MenuItem(xbmc.getLocalizedString(342), lambda: _run_precache(["movie"], True)),
        MenuItem(xbmc.getLocalizedString(20343), lambda: _run_precache(["tvshow"], True)),
        MenuItem(xbmc.getLocalizedString(33054), lambda: _run_precache(["season"], True)),
        MenuItem(xbmc.getLocalizedString(20360), lambda: _run_precache(["episode"], True)),
        MenuItem(xbmc.getLocalizedString(20389), lambda: _run_precache(["musicvideo"], True)),
        MenuItem(xbmc.getLocalizedString(20434), lambda: _run_precache(["set"], True)),
        MenuItem(xbmc.getLocalizedString(133), lambda: _run_precache(["artist"], True)),
        MenuItem(xbmc.getLocalizedString(132), lambda: _run_precache(["album"], True)),
    ])
    return scope_menu.show()


def _run_precache(selected_types: Optional[List[str]], enable_download: bool):
    """Execute precache with selected scope and mode."""
    from lib.infrastructure.menus import Menu, MenuItem

    mode_menu = Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), lambda: _execute_precache(selected_types, enable_download, False)),
        MenuItem(ADDON.getLocalizedString(32412), lambda: _execute_precache(selected_types, enable_download, True)),
    ])
    return mode_menu.show()


def _execute_precache(selected_types: Optional[List[str]], enable_download: bool, use_background: bool) -> None:
    """Execute the actual precache operation."""
    from lib.infrastructure import tasks as task_manager

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    operation_name = ADDON.getLocalizedString(32455)

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    ADDON.getLocalizedString(32172),
                    f"{ADDON.getLocalizedString(32457).format(current_task)}[CR][CR]{ADDON.getLocalizedString(32458)}"
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task(operation_name):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext(operation_name) as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create(operation_name, ADDON.getLocalizedString(32336))
            else:
                progress = xbmcgui.DialogProgress()
                progress.create(operation_name, ADDON.getLocalizedString(32336))

            if enable_download:
                stats = precache_and_download_artwork(progress_dialog=progress, media_types=selected_types, task_context=ctx)
            else:
                stats = precache_library_artwork(progress_dialog=progress, media_types=selected_types, task_context=ctx)

            progress.close()

        cancelled = stats.get('cancelled', False)

        if enable_download:
            total = stats['total_urls']
            cached = stats['cached']
            downloaded = stats['downloaded']
            skipped = stats['download_skipped']
            cache_failed = stats['cache_failed']
            download_failed = stats['download_failed']
            mb = stats['bytes_downloaded'] / (1024 * 1024) if stats['bytes_downloaded'] > 0 else 0

            title = ADDON.getLocalizedString(32459) if cancelled else ADDON.getLocalizedString(32460)

            message_parts = [
                ADDON.getLocalizedString(32463).format(total),
                ADDON.getLocalizedString(32464).format(cached),
                ADDON.getLocalizedString(32465).format(downloaded, mb),
                ADDON.getLocalizedString(32286).format(skipped)
            ]

            if cache_failed > 0 or download_failed > 0:
                message_parts.append(ADDON.getLocalizedString(32467).format(cache_failed, download_failed))
        else:
            save_operation_stats('texture_precache', {
                'cached_count': stats['already_cached'] + stats['successfully_cached'],
                'total_count': stats.get('total_urls', 0),
                'new_count': stats['successfully_cached'],
                'failed_count': stats.get('failed', 0),
                'cancelled': cancelled
            })

            total = stats['total_urls']
            already = stats['already_cached']
            newly = stats['successfully_cached']

            title = ADDON.getLocalizedString(32459) if cancelled else ADDON.getLocalizedString(32460)

            message_parts = [
                ADDON.getLocalizedString(32463).format(total),
                ADDON.getLocalizedString(32468).format(already),
                ADDON.getLocalizedString(32469).format(newly)
            ]

            if stats['failed'] > 0:
                message_parts.append(ADDON.getLocalizedString(32470).format(stats['failed']))

        if cancelled:
            message_parts.append("")
            message_parts.append(f"[B]{ADDON.getLocalizedString(32471)}[/B]")

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        log("Texture",f"Pre-cache failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(operation_name, f"{ADDON.getLocalizedString(32170)}:[CR]{str(e)}")


def _show_cleanup_menu():
    """Show cleanup submenu and handle selection."""
    from lib.infrastructure.menus import Menu, MenuItem

    menu = Menu(ADDON.getLocalizedString(32087), [
        MenuItem(ADDON.getLocalizedString(32088), _handle_standard_cleanup, loop=True),
        MenuItem(ADDON.getLocalizedString(32092), _show_advanced_cleanup_menu, loop=True),
    ])
    return menu.show()


def _show_advanced_cleanup_menu():
    """Show advanced cleanup submenu and handle selection."""
    from lib.infrastructure.menus import Menu, MenuItem

    menu = Menu(ADDON.getLocalizedString(32092), [
        MenuItem(ADDON.getLocalizedString(32089), _handle_age_cleanup, loop=True),
        MenuItem(ADDON.getLocalizedString(32090), _handle_usage_cleanup, loop=True),
        MenuItem(ADDON.getLocalizedString(32091), _handle_pattern_cleanup, loop=True),
    ])
    return menu.show()


def _handle_standard_cleanup():
    """Handle standard orphaned texture cleanup."""
    from lib.infrastructure.menus import Menu, MenuItem

    menu = Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), lambda: _execute_standard_cleanup(False)),
        MenuItem(ADDON.getLocalizedString(32412), lambda: _execute_standard_cleanup(True)),
    ])
    return menu.show()


def _execute_standard_cleanup(use_background: bool) -> None:
    """Execute standard cleanup with selected mode."""
    from lib.infrastructure import tasks as task_manager

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    ADDON.getLocalizedString(32172),
                    f"{ADDON.getLocalizedString(32457).format(current_task)}[CR][CR]{ADDON.getLocalizedString(32458)}"
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task(ADDON.getLocalizedString(32334)):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext(ADDON.getLocalizedString(32334)) as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create(ADDON.getLocalizedString(32334), ADDON.getLocalizedString(32335))
            else:
                progress = xbmcgui.DialogProgress()
                progress.create(ADDON.getLocalizedString(32334), ADDON.getLocalizedString(32335))
            stats = cleanup_orphaned_textures(progress_dialog=progress, media_types=None, task_context=ctx)
            progress.close()

        save_operation_stats('texture_cleanup', {
            'cached_count': stats['total_library'],
            'total_count': stats['total_cached'],
            'removed_count': stats['removed'],
            'orphaned_count': stats['orphaned_found'],
            'cancelled': stats.get('cancelled', False)
        })

        total_cached = stats['total_cached']
        library = stats['total_library']
        orphaned_found = stats['orphaned_found']
        removed = stats['removed']
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = ADDON.getLocalizedString(32461)
        else:
            title = ADDON.getLocalizedString(32462)

        message_parts = [
            ADDON.getLocalizedString(32496).format(total_cached, library),
            ADDON.getLocalizedString(32497).format(orphaned_found, removed)
        ]

        if stats['failed'] > 0:
            message_parts.append(ADDON.getLocalizedString(32470).format(stats['failed']))

        if cancelled:
            message_parts.append(ADDON.getLocalizedString(32471))

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        log("Texture",f"Cleanup failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(ADDON.getLocalizedString(32087), f"{ADDON.getLocalizedString(32170)}:[CR]{str(e)}")


def _handle_stats() -> None:
    """Show texture cache statistics."""
    dialog = xbmcgui.Dialog()
    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32180), ADDON.getLocalizedString(32472))

    try:
        textures = get_cached_textures()
        stats = calculate_texture_statistics(textures, progress)
        progress.close()

        if stats:
            report = format_statistics_report(stats)
            dialog.textviewer(ADDON.getLocalizedString(32180), report)
        else:
            dialog.ok(ADDON.getLocalizedString(32180), ADDON.getLocalizedString(32181))
    except Exception as e:
        progress.close()
        log("Texture",f" Stats failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(ADDON.getLocalizedString(32180), f"{ADDON.getLocalizedString(32170)}:[CR]{str(e)}")


def cleanup_textures_by_age(
    age_days: int,
    progress_dialog: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None,
    task_context: Optional[Any] = None
) -> Dict[str, int]:
    """
    Remove textures not used in specified number of days.

    Args:
        age_days: Remove textures not used in this many days
        progress_dialog: Optional progress dialog
        task_context: Optional task context for cancellation

    Returns:
        Dict with stats: total_textures, old_textures, removed, failed, cancelled
    """
    from datetime import datetime, timedelta

    stats = {
        'total_textures': 0,
        'old_textures': 0,
        'removed': 0,
        'failed': 0,
        'cancelled': False
    }

    try:
        if progress_dialog:
            progress_dialog.update(0, ADDON.getLocalizedString(32490))

        textures = get_cached_textures()
        stats['total_textures'] = len(textures)

        if not textures:
            return stats

        cutoff_date = datetime.now() - timedelta(days=age_days)
        old_textures = []

        if progress_dialog:
            progress_dialog.update(10, ADDON.getLocalizedString(32332).format(len(textures)))

        for i, texture in enumerate(textures):
            if task_context and task_context.is_cancelled():
                stats['cancelled'] = True
                return stats

            if progress_dialog and i % 100 == 0:
                if isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled():
                    stats['cancelled'] = True
                    return stats
                progress_dialog.update(10 + int((i / len(textures)) * 40))

            sizes = texture.get('sizes', [])
            if not sizes:
                continue

            for size in sizes:
                lastusetime = size.get('lastusetime')
                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        if last_used < cutoff_date:
                            old_textures.append(texture)
                            break
                    except Exception:
                        pass

        stats['old_textures'] = len(old_textures)

        if not old_textures:
            return stats

        if progress_dialog:
            progress_dialog.update(50, ADDON.getLocalizedString(32492).format(len(old_textures)))

        for i, texture in enumerate(old_textures):
            if task_context and task_context.is_cancelled():
                stats['cancelled'] = True
                return stats

            if progress_dialog and i % 10 == 0:
                if isinstance(progress_dialog, xbmcgui.DialogProgress) and progress_dialog.iscanceled():
                    stats['cancelled'] = True
                    return stats
                progress_dialog.update(50 + int((i / len(old_textures)) * 50))

            texture_id = texture.get('textureid')
            if texture_id:
                if remove_texture(texture_id):
                    stats['removed'] += 1
                else:
                    stats['failed'] += 1

        if progress_dialog:
            progress_dialog.update(100, ADDON.getLocalizedString(32426))

    except Exception as e:
        log("Texture",f" Age cleanup failed: {str(e)}", xbmc.LOGERROR)
        raise

    return stats


def _handle_age_cleanup():
    """Handle age-based texture cleanup."""
    from lib.infrastructure.menus import Menu, MenuItem

    menu = Menu(ADDON.getLocalizedString(32473), [
        MenuItem(ADDON.getLocalizedString(32474), lambda: _execute_age_cleanup(30)),
        MenuItem(ADDON.getLocalizedString(32475), lambda: _execute_age_cleanup(60)),
        MenuItem(ADDON.getLocalizedString(32476), lambda: _execute_age_cleanup(90)),
        MenuItem(ADDON.getLocalizedString(32477), lambda: _execute_age_cleanup(180)),
        MenuItem(ADDON.getLocalizedString(32478), lambda: _execute_age_cleanup(365)),
    ])
    return menu.show()


def _execute_age_cleanup(age_days: int) -> None:
    """Execute age-based cleanup."""
    dialog = xbmcgui.Dialog()
    progress = xbmcgui.DialogProgress()
    progress.create(ADDON.getLocalizedString(32330), ADDON.getLocalizedString(32331))

    try:
        from datetime import datetime, timedelta

        textures = get_cached_textures()
        total_textures = len(textures)

        if not textures:
            progress.close()
            dialog.ok(ADDON.getLocalizedString(32182), ADDON.getLocalizedString(32182))
            return

        cutoff_date = datetime.now() - timedelta(days=age_days)
        old_textures = []
        oldest_date = None

        progress.update(20, ADDON.getLocalizedString(32332).format(total_textures))

        for i, texture in enumerate(textures):
            if progress.iscanceled():
                progress.close()
                return

            if i % 100 == 0:
                progress.update(20 + int((i / total_textures) * 60))

            sizes = texture.get('sizes', [])
            if not sizes:
                continue

            for size in sizes:
                lastusetime = size.get('lastusetime')
                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        if last_used < cutoff_date:
                            old_textures.append(texture)
                            if oldest_date is None or last_used < oldest_date:
                                oldest_date = last_used
                            break
                    except Exception:
                        pass

        progress.close()

        if not old_textures:
            dialog.ok(
                ADDON.getLocalizedString(32479),
                f"{ADDON.getLocalizedString(32480).format(age_days)}[CR][CR]"
                f"{ADDON.getLocalizedString(32481).format(total_textures)}"
            )
            return

        oldest_str = oldest_date.strftime('%Y-%m-%d') if oldest_date else "Unknown"

        confirm = dialog.yesno(
            ADDON.getLocalizedString(32482),
            f"{ADDON.getLocalizedString(32483).format(len(old_textures), age_days)}[CR]"
            f"{ADDON.getLocalizedString(32484).format(total_textures, oldest_str)}"
        )

        if not confirm:
            return

    except Exception as e:
        progress.close()
        log("Texture",f" Analysis failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(ADDON.getLocalizedString(32184), f"Failed to analyze textures:[CR]{str(e)}")
        return

    from lib.infrastructure.menus import Menu, MenuItem

    menu = Menu(ADDON.getLocalizedString(32410), [
        MenuItem(ADDON.getLocalizedString(32411), lambda: _execute_age_cleanup_with_mode(old_textures, age_days, False)),
        MenuItem(ADDON.getLocalizedString(32412), lambda: _execute_age_cleanup_with_mode(old_textures, age_days, True)),
    ])
    return menu.show()


def _execute_age_cleanup_with_mode(old_textures: List[Dict], age_days: int, use_background: bool) -> None:
    """Execute age cleanup with selected mode."""
    from lib.infrastructure import tasks as task_manager

    progress: Optional[Union[xbmcgui.DialogProgress, xbmcgui.DialogProgressBG]] = None
    dialog = xbmcgui.Dialog()

    try:
        if use_background:
            if task_manager.is_task_running():
                task_info = task_manager.get_task_info()
                current_task = task_info['name'] if task_info else "Unknown task"
                dialog.ok(
                    ADDON.getLocalizedString(32172),
                    f"{ADDON.getLocalizedString(32457).format(current_task)}[CR][CR]{ADDON.getLocalizedString(32458)}"
                )
                return
        else:
            if task_manager.is_task_running():
                if not confirm_cancel_running_task(ADDON.getLocalizedString(32333)):
                    return

                task_manager.cancel_task()
                monitor = xbmc.Monitor()
                while task_manager.is_task_running() and not monitor.abortRequested():
                    monitor.waitForAbort(0.1)

        with task_manager.TaskContext(ADDON.getLocalizedString(32333)) as ctx:
            if use_background:
                progress = xbmcgui.DialogProgressBG()
                progress.create(ADDON.getLocalizedString(32333), ADDON.getLocalizedString(32335))
            else:
                progress = xbmcgui.DialogProgress()
                progress.create(ADDON.getLocalizedString(32333), ADDON.getLocalizedString(32335))
            stats = cleanup_textures_by_age(age_days, progress_dialog=progress, task_context=ctx)
            progress.close()

        save_operation_stats('texture_age_cleanup', {
            'age_days': age_days,
            'total_count': stats['total_textures'],
            'old_count': stats['old_textures'],
            'removed_count': stats['removed'],
            'cancelled': stats.get('cancelled', False)
        })

        total_textures = stats['total_textures']
        old_textures_count = stats['old_textures']
        removed = stats['removed']
        cancelled = stats.get('cancelled', False)

        if cancelled:
            title = ADDON.getLocalizedString(32461)
        else:
            title = ADDON.getLocalizedString(32462)

        message_parts = [
            ADDON.getLocalizedString(32493).format(total_textures),
            ADDON.getLocalizedString(32494).format(age_days, old_textures_count),
            ADDON.getLocalizedString(32495).format(removed)
        ]

        if stats['failed'] > 0:
            message_parts.append(ADDON.getLocalizedString(32470).format(stats['failed']))

        if cancelled:
            message_parts.append(ADDON.getLocalizedString(32471))

        message = "[CR]".join(message_parts)
        dialog.ok(title, message)

    except Exception as e:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        log("Texture",f" Age cleanup failed: {str(e)}", xbmc.LOGERROR)
        dialog.ok(ADDON.getLocalizedString(32087), f"{ADDON.getLocalizedString(32170)}:[CR]{str(e)}")


def _handle_usage_cleanup() -> None:
    """Handle usage-based texture cleanup."""
    show_ok(
        ADDON.getLocalizedString(32485),
        f"{ADDON.getLocalizedString(32486)}[CR][CR]"
        "Will remove textures accessed fewer than N times[CR]"
        "(e.g., never used, used < 5 times)[CR][CR]"
        "Useful for removing rarely-viewed images."
    )


def _handle_pattern_cleanup() -> None:
    """Handle pattern-based force re-cache."""
    show_ok(
        ADDON.getLocalizedString(32487),
        f"{ADDON.getLocalizedString(32486)}[CR][CR]"
        "Will remove textures matching a URL pattern[CR]"
        "(e.g., 'image.tmdb.org/t/p/original/')[CR][CR]"
        "Forces Kodi to re-download matching images."
    )


def _show_last_report() -> None:
    """Show last operation report."""
    precache_stats = get_last_operation_stats('texture_precache')
    cleanup_stats = get_last_operation_stats('texture_cleanup')

    last_stats = None
    if precache_stats and cleanup_stats:
        precache_time = datetime.fromisoformat(precache_stats['timestamp'])
        cleanup_time = datetime.fromisoformat(cleanup_stats['timestamp'])
        last_stats = precache_stats if precache_time > cleanup_time else cleanup_stats
    elif precache_stats:
        last_stats = precache_stats
    elif cleanup_stats:
        last_stats = cleanup_stats

    if last_stats:
        report_text = format_operation_report(
            last_stats['operation'],
            last_stats['stats'],
            last_stats['timestamp']
        )
        show_textviewer(ADDON.getLocalizedString(32488), report_text)
    else:
        show_ok(
            ADDON.getLocalizedString(32086),
            ADDON.getLocalizedString(32489)
        )
