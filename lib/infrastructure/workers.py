"""Worker queue infrastructure for background processing."""
from __future__ import annotations

import time
import threading
import xbmc
import xbmcgui
from queue import Queue, Empty
from typing import Optional, Set, List, Dict, Any, Callable
from multiprocessing import cpu_count
from lib.kodi.client import log


def get_optimal_worker_count() -> int:
    """Calculate optimal number of worker threads based on CPU cores."""
    try:
        cores = cpu_count()
    except (NotImplementedError, AttributeError):
        return 3

    if cores <= 0:
        return 3

    return min(max(3, cores), 8)


class WorkerQueue:
    """
    Generic multi-threaded worker queue base class.

    Provides thread pool management, queue operations, duplicate prevention,
    statistics tracking, and progress callbacks. Subclasses override
    _process_item() to implement specific work logic.
    """

    def __init__(
        self,
        num_workers: Optional[int] = None,
        abort_flag=None,
        task_context=None
    ):
        """
        Initialize worker queue.

        Args:
            num_workers: Number of worker threads (auto-detect if None)
            abort_flag: Optional AbortFlag to check for cancellation
            task_context: Optional TaskContext for progress tracking
        """
        self.num_workers = num_workers or get_optimal_worker_count()
        self.abort_flag = abort_flag
        self.task_context = task_context

        self.queue: Queue = Queue()
        self.processing_set: Set[Any] = set()
        self.processing_lock = threading.Lock()

        self.results: List[Dict] = []
        self.results_lock = threading.Lock()

        self.workers: List[threading.Thread] = []
        self.running = False
        self.total_queued = 0

    def start(self) -> None:
        """Start background worker threads."""
        if self.running:
            return

        self.running = True
        self._on_start()

        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                args=(i,),
                daemon=True,
                name=f"{self.__class__.__name__}-Worker-{i}"
            )
            worker.start()
            self.workers.append(worker)

    def stop(self, wait: bool = True) -> None:
        """
        Stop all worker threads.

        Args:
            wait: If True, wait for workers to finish current tasks
        """
        if not self.running:
            return

        self.running = False

        if not wait:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except Empty:
                    break
            self.processing_set.clear()

        for _ in self.workers:
            self.queue.put(None)

        for i, worker in enumerate(self.workers):
            worker.join(timeout=2.0 if not wait else 5.0)

    def add_item(self, item: Any, dedupe_key: Optional[Any] = None) -> bool:
        """
        Queue an item for background processing.

        Returns immediately (non-blocking).

        Args:
            item: Item to process (passed to _process_item)
            dedupe_key: Optional key for duplicate detection (defaults to item)

        Returns:
            True if queued, False if already processing
        """
        if not self.running:
            log("General", f"{self.__class__.__name__} cannot add item, queue not started", xbmc.LOGWARNING)
            return False

        key = dedupe_key if dedupe_key is not None else item

        with self.processing_lock:
            if key in self.processing_set:
                return False

            if not self._should_process_item(item, key):
                return False

            self.processing_set.add(key)

        self.queue.put((item, key, time.time()))
        self.total_queued += 1
        return True

    def bulk_add_items(self, items: List[Any]) -> int:
        """
        Queue multiple items efficiently.

        Args:
            items: List of items to process

        Returns:
            Number of items successfully queued
        """
        queued = 0
        for item in items:
            if self.add_item(item):
                queued += 1
        return queued

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all queued items to complete.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if completed, False if timeout
        """
        try:
            if timeout:
                start = time.time()
                monitor = xbmc.Monitor()
                while not self.queue.empty() or self.processing_set:
                    if time.time() - start > timeout:
                        return False
                    if monitor.waitForAbort(0.1):
                        return False
            else:
                self.queue.join()
            return True
        except Exception as e:
            log("General", f"{self.__class__.__name__} wait error: {str(e)}", xbmc.LOGERROR)
            return False

    def get_stats(self) -> Dict:
        """
        Get current queue statistics.

        Returns:
            Dict with queue stats
        """
        with self.results_lock:
            successful = sum(1 for r in self.results if r.get('success', False))
            failed = sum(1 for r in self.results if not r.get('success', False))

            return {
                'queued': self.queue.qsize(),
                'processing': len(self.processing_set),
                'completed': len(self.results),
                'successful': successful,
                'failed': failed,
                'total_queued': self.total_queued,
                'num_workers': self.num_workers,
                'results': list(self.results)
            }

    def get_progress(self) -> Dict:
        """
        Get progress as percentage.

        Returns:
            Dict with progress info
        """
        if self.total_queued == 0:
            return {'percent': 0, 'completed': 0, 'total': 0}

        with self.results_lock:
            completed = len(self.results)

        return {
            'percent': int((completed / self.total_queued) * 100),
            'completed': completed,
            'total': self.total_queued
        }

    def _worker(self, worker_id: int) -> None:
        """
        Background worker thread.

        Args:
            worker_id: Worker thread ID
        """
        monitor = xbmc.Monitor()

        while self.running:
            if monitor.abortRequested() or (self.abort_flag and self.abort_flag.is_requested()):
                break

            try:
                item = self.queue.get(timeout=0.1)
                if item is None:
                    break

                item_data, dedupe_key, start_time = item

                if monitor.abortRequested() or (self.abort_flag and self.abort_flag.is_requested()):
                    with self.processing_lock:
                        self.processing_set.discard(dedupe_key)
                    self.queue.task_done()
                    break

                try:
                    result = self._process_item(item_data, worker_id)

                    if result is None:
                        result = {}

                    result['success'] = result.get('success', True)
                    result['elapsed'] = time.time() - start_time
                    result['worker'] = worker_id

                    with self.results_lock:
                        self.results.append(result)

                    self._on_item_complete(item_data, result)

                except Exception as e:
                    elapsed = time.time() - start_time

                    result = {
                        'success': False,
                        'elapsed': elapsed,
                        'worker': worker_id,
                        'error': str(e)
                    }

                    with self.results_lock:
                        self.results.append(result)

                    log("General", f"{self.__class__.__name__} worker {worker_id} error: {str(e)}", xbmc.LOGWARNING)

                    self._on_item_complete(item_data, result)

                finally:
                    with self.processing_lock:
                        self.processing_set.discard(dedupe_key)

                    self.queue.task_done()

                    if self.task_context:
                        self.task_context.mark_progress()

            except Empty:
                continue
            except Exception as e:
                log("General", f"{self.__class__.__name__} worker {worker_id} unexpected error: {str(e)}", xbmc.LOGERROR)

    def _process_item(self, item: Any, worker_id: int) -> Optional[Dict]:
        """
        Process a single item (OVERRIDE IN SUBCLASS).

        Args:
            item: Item to process
            worker_id: ID of worker processing the item

        Returns:
            Dict with result info (must include 'success' key)
        """
        raise NotImplementedError("Subclasses must implement _process_item()")

    def _on_start(self) -> None:
        """Called when queue starts (OPTIONAL OVERRIDE)."""
        pass

    def _should_process_item(self, item: Any, dedupe_key: Any) -> bool:
        """
        Check if item should be processed (OPTIONAL OVERRIDE).

        Args:
            item: Item to check
            dedupe_key: Deduplication key

        Returns:
            True if item should be processed
        """
        return True

    def _on_item_complete(self, item: Any, result: Dict) -> None:
        """
        Called when item processing completes (OPTIONAL OVERRIDE).

        Args:
            item: Completed item
            result: Result dict
        """
        pass


class SingletonWorker:
    """
    Persistent singleton worker thread for background job processing.

    Designed for long-running services that need a single background worker
    to process jobs asynchronously without blocking the main thread.

    Usage:
        worker = SingletonWorker.get_instance()
        worker.start()
        worker.queue_job(lambda: expensive_operation())
        # Later...
        worker.stop()
    """

    _instance: Optional[SingletonWorker] = None
    _lock = threading.Lock()

    def __init__(self):
        self._queue: Queue = Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._monitor = xbmc.Monitor()
        self._window = xbmcgui.Window(10000)

    @classmethod
    def get_instance(cls) -> SingletonWorker:
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """Start background worker thread."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()
            log("Worker", "Singleton worker started", xbmc.LOGDEBUG)

    def stop(self) -> None:
        """Stop background worker thread."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._queue.put(None)
            self._thread.join(timeout=5.0)
            log("Worker", "Singleton worker stopped", xbmc.LOGDEBUG)

    def queue_job(self, job: Callable[[], None]) -> None:
        """
        Queue a job for background processing.

        Args:
            job: Callable that takes no arguments and returns None
        """
        if not self._thread or not self._thread.is_alive():
            log("Worker", "Cannot queue job, worker not running", xbmc.LOGWARNING)
            return

        self._queue.put(job)

    def _worker_loop(self) -> None:
        """Main worker loop - processes jobs from queue."""
        while not self._stop_event.is_set():
            if self._monitor.abortRequested():
                log("Worker", "Abort requested, stopping worker", xbmc.LOGDEBUG)
                break

            try:
                job = self._queue.get(timeout=1.0)

                if job is None:
                    break

                if self._monitor.abortRequested():
                    log("Worker", "Abort requested, skipping job", xbmc.LOGDEBUG)
                    self._queue.task_done()
                    break

                try:
                    job()
                except Exception as e:
                    log("Worker", f"Job error: {str(e)}", xbmc.LOGWARNING)

                self._queue.task_done()

            except Empty:
                continue
            except Exception as e:
                log("Worker", f"Worker loop error: {str(e)}", xbmc.LOGERROR)
