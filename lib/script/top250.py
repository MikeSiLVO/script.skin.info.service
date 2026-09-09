"""Update IMDb Top 250 rankings in Kodi library via Trakt's official list."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, NamedTuple, Optional, Tuple

import xbmc

from lib.kodi.client import (
    request,
    batch_request,
    ADDON,
    log,
    KODI_SET_DETAILS_METHODS,
    extract_result,
)
from lib.infrastructure.dialogs import ProgressDialog, show_ok, show_yesno

_BATCH_SIZE = 50


class TraktRanks(NamedTuple):
    """Trakt's Top 250 indexed by id, with a content digest and the list's rebuild time."""
    by_imdb: Dict[str, int]
    by_tmdb: Dict[str, int]
    digest: str
    rebuilt_at: float


class UpdateStats(NamedTuple):
    """Outcome of one rank-writing pass."""
    updated: int
    cleared: int
    failed: int
    already_correct: int
    cancelled: bool


def _rebuilt_at(items: List[dict]) -> float:
    """Find the newest `listed_at` as an epoch; Trakt restamps every item on a rebuild."""
    newest = 0.0
    for item in items:
        try:
            parsed = datetime.strptime(item.get("listed_at") or "", "%Y-%m-%dT%H:%M:%S.%fZ")
        except (ValueError, TypeError):
            continue
        newest = max(newest, parsed.replace(tzinfo=timezone.utc).timestamp())
    return newest


def fetch_ranks(abort_flag=None) -> Optional[TraktRanks]:
    """Fetch Trakt's list and index it by IMDb and TMDB id."""
    from lib.data.api.trakt import fetch_top250_list

    items = fetch_top250_list(abort_flag=abort_flag)
    if not items:
        return None

    by_imdb: Dict[str, int] = {}
    by_tmdb: Dict[str, int] = {}
    for item in items:
        rank = item["rank"]
        ids = item["movie"]["ids"]
        if ids.get("imdb"):
            by_imdb[ids["imdb"]] = rank
        if ids.get("tmdb"):
            by_tmdb[str(ids["tmdb"])] = rank

    ordered = sorted((rank, imdb) for imdb, rank in by_imdb.items())
    digest = hashlib.sha1(repr(ordered).encode()).hexdigest()

    log("General", f"Top 250: fetched {len(items)} items from Trakt", xbmc.LOGINFO)
    return TraktRanks(by_imdb, by_tmdb, digest, _rebuilt_at(items))


def compute_updates(ranks: TraktRanks) -> Optional[Tuple[List[Tuple[int, int, str]], int]]:
    """Compute which library rows need a `top250` write, and how many already match."""
    resp = request("VideoLibrary.GetMovies", {
        "properties": ["title", "uniqueid", "top250"]
    })
    movies = extract_result(resp, "movies", [])
    if not movies:
        return None

    updates: List[Tuple[int, int, str]] = []
    already_correct = 0

    for movie in movies:
        uniqueid = movie.get("uniqueid", {})
        current = movie.get("top250", 0)
        movieid = movie.get("movieid")
        title = movie.get("title", "")

        new_rank = None
        imdb_id = uniqueid.get("imdb")
        tmdb_id = uniqueid.get("tmdb")
        if imdb_id:
            new_rank = ranks.by_imdb.get(imdb_id)
        if new_rank is None and tmdb_id:
            new_rank = ranks.by_tmdb.get(str(tmdb_id))

        if new_rank is not None:
            if current != new_rank:
                updates.append((movieid, new_rank, title))
            else:
                already_correct += 1
        elif current > 0:
            updates.append((movieid, 0, title))

    return updates, already_correct


def apply_updates(updates: List[Tuple[int, int, str]], already_correct: int,
                  progress: ProgressDialog) -> UpdateStats:
    """Write each row's rank in batches, reporting progress as it goes."""
    set_method, set_id_key = KODI_SET_DETAILS_METHODS["movie"]
    updated = 0
    cleared = 0
    failed = 0
    cancelled = False

    for batch_start in range(0, len(updates), _BATCH_SIZE):
        if progress.is_cancelled():
            cancelled = True
            break

        batch = updates[batch_start:batch_start + _BATCH_SIZE]
        calls = [{
            "method": set_method,
            "params": {set_id_key: movieid, "top250": rank}
        } for movieid, rank, _ in batch]

        responses = batch_request(calls)

        for i, r in enumerate(responses):
            _, rank, title = batch[i]
            if r is not None and "error" not in r:
                if rank > 0:
                    updated += 1
                    log("General", f"Top 250: #{rank} {title}", xbmc.LOGDEBUG)
                else:
                    cleared += 1
                    log("General", f"Top 250: cleared {title}", xbmc.LOGDEBUG)
            else:
                failed += 1
                log("General", f"Top 250: failed to update {title}", xbmc.LOGWARNING)

        current = min(batch_start + _BATCH_SIZE, len(updates))
        progress.update(
            int(current * 100 / len(updates)),
            ADDON.getLocalizedString(32604).format(current, len(updates))
        )

    status = "cancelled" if cancelled else "complete"
    log(
        "General",
        f"Top 250 update {status}: {updated} set, {cleared} cleared, "
        f"{failed} failed, {already_correct} unchanged",
        xbmc.LOGINFO,
    )
    return UpdateStats(updated, cleared, failed, already_correct, cancelled)


def run_top250_update() -> None:
    """Update IMDb Top 250 rankings from Trakt's official list."""
    heading = ADDON.getLocalizedString(32600)

    try:
        with ProgressDialog(heading=heading) as progress:
            progress.create(ADDON.getLocalizedString(32601))
            ranks = fetch_ranks()
            if ranks is None:
                progress.close()
                show_ok(heading, ADDON.getLocalizedString(32607))
                return
            if progress.is_cancelled():
                return

            progress.update(25, ADDON.getLocalizedString(32602))
            computed = compute_updates(ranks)
            if computed is None:
                progress.close()
                show_ok(heading, ADDON.getLocalizedString(32608))
                return
            if progress.is_cancelled():
                return
            progress.update(50, ADDON.getLocalizedString(32603))

        updates, already_correct = computed

        if not updates:
            show_ok(
                ADDON.getLocalizedString(32605),
                ADDON.getLocalizedString(32606).format(0, 0, already_correct)
            )
            return

        set_count = sum(1 for _, rank, _ in updates if rank > 0)
        clear_count = len(updates) - set_count

        if not show_yesno(
            ADDON.getLocalizedString(32609),
            ADDON.getLocalizedString(32610).format(set_count, clear_count, already_correct)
        ):
            return

        with ProgressDialog(heading=heading) as progress:
            progress.create()
            stats = apply_updates(updates, already_correct, progress)

        if stats.cancelled:
            show_ok(
                heading,
                ADDON.getLocalizedString(32611).format(stats.updated, stats.cleared)
            )
        else:
            show_ok(
                ADDON.getLocalizedString(32605),
                ADDON.getLocalizedString(32606).format(
                    stats.updated, stats.cleared, stats.already_correct)
            )

    except Exception as e:
        log("General", f"Top 250 update error: {e}", xbmc.LOGERROR)
        show_ok(heading, str(e))
