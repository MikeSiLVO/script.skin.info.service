"""Batch executor for parallel ratings fetching with thread management."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import xbmc

from lib.kodi.client import log
from lib.rating.source import RateLimitHit, RetryableError
from lib.rating import tracker as usage_tracker


MAX_WORKERS = 6
MAX_PER_SOURCE = 2
ITEM_TIMEOUT = 30.0
POLL_INTERVAL = 1.0


@dataclass
class FetchJob:
    """Represents a single fetch job for tracking."""
    item_dbid: int
    source_name: str
    future: Future
    submitted_at: float = field(default_factory=time.time)


@dataclass
class ItemState:
    """Tracks state for a single item being processed."""
    dbid: int
    title: str
    year: str
    media_type: str
    item: Dict
    existing_ratings: Dict
    ids: Dict
    pending_sources: Set[str] = field(default_factory=set)
    submitted_sources: Set[str] = field(default_factory=set)
    completed_sources: Set[str] = field(default_factory=set)
    ratings: List[Dict] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    retryable_failures: List[Dict] = field(default_factory=list)
    submitted_at: float = field(default_factory=time.time)
    finalized: bool = False


class RatingBatchExecutor:
    """
    Manages parallel fetching of ratings across a batch of items.

    Uses a single ThreadPoolExecutor for the entire batch with:
    - Hard cap of 6 workers total
    - Per-source cap of 2 concurrent threads
    - Late result handling for slow sources
    """

    def __init__(self, sources: List, abort_flag=None):
        """
        Initialize the batch executor.

        Args:
            sources: List of rating source instances (ApiTmdb, ApiTrakt, etc.)
            abort_flag: Optional abort flag for cancellation
        """
        self.sources = sources
        self.source_names = {
            source: source.__class__.__name__.replace("Api", "").lower()
            for source in sources
        }
        self.abort_flag = abort_flag

        self.executor: Optional[ThreadPoolExecutor] = None
        self.active_per_source: Dict[str, int] = {name: 0 for name in self.source_names.values()}
        self.pending_futures: Dict[Future, FetchJob] = {}
        self.item_states: Dict[int, ItemState] = {}

        self._cancelled = False

    def __enter__(self):
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=False)
        return False

    def is_cancelled(self) -> bool:
        """Check if abort was requested."""
        if self._cancelled:
            return True
        if self.abort_flag and self.abort_flag.is_requested():
            self._cancelled = True
            return True
        return False

    def submit_item(
        self,
        item: Dict,
        dbid: int,
        title: str,
        year: str,
        media_type: str,
        ids: Dict,
        existing_ratings: Dict
    ) -> None:
        """
        Submit fetch jobs for an item.

        Jobs are only submitted for sources that have capacity (< MAX_PER_SOURCE active).
        Sources at capacity are added to pending for later submission.

        Args:
            item: Full item dict from library
            dbid: Database ID
            title: Item title
            year: Item year
            media_type: 'movie', 'tvshow', or 'episode'
            ids: Dict with 'tmdb', 'imdb', etc.
            existing_ratings: Current ratings from Kodi
        """
        if self.is_cancelled() or not self.executor:
            return

        if dbid in self.item_states:
            log("Ratings", f"   WARNING: Item {dbid} ({title}) already submitted, skipping duplicate", xbmc.LOGWARNING)
            return

        state = ItemState(
            dbid=dbid,
            title=title,
            year=year,
            media_type=media_type,
            item=item,
            existing_ratings=existing_ratings,
            ids=ids
        )
        self.item_states[dbid] = state

        for source in self.sources:
            source_name = self.source_names[source]

            if self.active_per_source[source_name] < MAX_PER_SOURCE:
                self._submit_job(state, source, source_name)
            else:
                state.pending_sources.add(source_name)
                log("Ratings", f"   {source_name}: Queued (at capacity)", xbmc.LOGDEBUG)

    def _submit_job(self, state: ItemState, source, source_name: str) -> None:
        """Submit a single fetch job to the executor."""
        if not self.executor:
            return

        if state.finalized:
            log("Ratings", f"   BUG: Trying to submit {source_name} for finalized item {state.title}", xbmc.LOGWARNING)
            return

        if source_name in state.submitted_sources:
            log("Ratings", f"   BUG: Trying to re-submit {source_name} for {state.title}", xbmc.LOGWARNING)
            return

        if source_name in state.completed_sources:
            log("Ratings", f"   BUG: Trying to submit {source_name} for {state.title} but already completed", xbmc.LOGWARNING)
            return

        state.submitted_sources.add(source_name)

        future = self.executor.submit(
            source.fetch_ratings,
            state.media_type,
            state.ids,
            self.abort_flag
        )

        job = FetchJob(
            item_dbid=state.dbid,
            source_name=source_name,
            future=future
        )

        self.pending_futures[future] = job
        self.active_per_source[source_name] += 1

    def collect_results(self, timeout: float = POLL_INTERVAL) -> List[tuple[int, str, Any]]:
        """
        Collect completed results, checking abort periodically.

        Args:
            timeout: How long to wait for results before returning

        Returns:
            List of (dbid, source_name, result_or_exception) tuples
        """
        if not self.pending_futures:
            return []

        results = []

        try:
            for future in as_completed(self.pending_futures.keys(), timeout=timeout):
                job = self.pending_futures.pop(future, None)
                if not job:
                    continue

                source_name = job.source_name
                dbid = job.item_dbid

                self.active_per_source[source_name] -= 1

                try:
                    ratings = future.result()
                    results.append((dbid, source_name, ratings))
                except RateLimitHit as e:
                    results.append((dbid, source_name, e))
                except RetryableError as e:
                    results.append((dbid, source_name, e))
                except Exception as e:
                    results.append((dbid, source_name, e))

        except FuturesTimeoutError:
            pass

        self._submit_pending_jobs()

        return results

    def _submit_pending_jobs(self) -> None:
        """Submit pending jobs for sources that now have capacity."""
        if not self.executor:
            return

        for dbid, state in self.item_states.items():
            if state.finalized:
                continue

            pending_copy = set(state.pending_sources)
            for source_name in pending_copy:
                if self.active_per_source[source_name] < MAX_PER_SOURCE:
                    source = self._get_source_by_name(source_name)
                    if source:
                        state.pending_sources.remove(source_name)
                        self._submit_job(state, source, source_name)

    def _get_source_by_name(self, name: str):
        """Get source instance by name."""
        for source, source_name in self.source_names.items():
            if source_name == name:
                return source
        return None

    def process_result(
        self,
        dbid: int,
        source_name: str,
        result: Any
    ) -> None:
        """
        Process a result and update item state.

        Args:
            dbid: Database ID of the item
            source_name: Name of the source that returned
            result: Ratings dict, or exception
        """
        state = self.item_states.get(dbid)
        if not state:
            log("Ratings", f"   {source_name}: Result for unknown item {dbid}, discarding", xbmc.LOGDEBUG)
            return

        if state.finalized:
            log("Ratings", f"   {source_name}: Late result for {state.title}, discarding", xbmc.LOGDEBUG)
            return

        state.completed_sources.add(source_name)

        if isinstance(result, RateLimitHit):
            action = usage_tracker.handle_rate_limit_error(result.provider, 0, 1)
            if action == "cancel_all":
                if self.abort_flag:
                    self.abort_flag.request()
                self._cancelled = True
            elif action == "cancel_batch":
                self._cancelled = True
            elif action == "retry":
                state.retryable_failures.append({
                    "source": source_name,
                    "reason": "rate limit (user chose wait)"
                })
            log("Ratings", f"   {source_name}: Rate limit reached", xbmc.LOGDEBUG)

        elif isinstance(result, RetryableError):
            log("Ratings", f"   {source_name}: Retryable error: {result.reason}", xbmc.LOGDEBUG)
            state.retryable_failures.append({
                "source": source_name,
                "reason": result.reason
            })

        elif isinstance(result, Exception):
            log("Ratings", f"   {source_name}: Failed: {str(result)}", xbmc.LOGDEBUG)

        elif result:
            state.ratings.append(result)
            state.sources_used.append(source_name)

    def check_item_timeout(self, dbid: int) -> bool:
        """
        Check if an item has exceeded its timeout.

        Args:
            dbid: Database ID to check

        Returns:
            True if timed out
        """
        state = self.item_states.get(dbid)
        if not state or state.finalized:
            return False

        elapsed = time.time() - state.submitted_at
        return elapsed > ITEM_TIMEOUT

    def get_item_state(self, dbid: int) -> Optional[ItemState]:
        """Get the current state of an item."""
        return self.item_states.get(dbid)

    def mark_item_finalized(self, dbid: int) -> None:
        """Mark an item as finalized (ratings applied to Kodi)."""
        state = self.item_states.get(dbid)
        if state:
            log("Ratings", f"   Finalizing {state.title}: completed={state.completed_sources}, pending={state.pending_sources}", xbmc.LOGDEBUG)
            state.finalized = True

            for source_name in state.pending_sources:
                state.retryable_failures.append({
                    "source": source_name,
                    "reason": "timeout (not submitted)"
                })

    def get_pending_count(self) -> int:
        """Get number of pending futures."""
        return len(self.pending_futures)

    def get_unfinalized_items(self) -> List[int]:
        """Get list of item dbids that haven't been finalized."""
        return [
            dbid for dbid, state in self.item_states.items()
            if not state.finalized
        ]

    def timeout_pending_sources(self, dbid: int) -> None:
        """Mark all pending sources for an item as timed out."""
        state = self.item_states.get(dbid)
        if not state:
            return

        all_source_names = set(self.source_names.values())
        incomplete = all_source_names - state.completed_sources

        for source_name in incomplete:
            if source_name not in [f["source"] for f in state.retryable_failures]:
                state.retryable_failures.append({
                    "source": source_name,
                    "reason": "timeout"
                })
                log("Ratings", f"   {source_name}: Timeout for {state.title}", xbmc.LOGDEBUG)
