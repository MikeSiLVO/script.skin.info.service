"""Global background task manager with automatic lifecycle management.

Tracks a single active background task (e.g., pre-caching) with automatic
heartbeat monitoring and stale detection. Uses Kodi Home window properties
for cross-instance persistence.
"""
from __future__ import annotations

import threading
import json
import time
import xbmc
import xbmcgui
from typing import Optional, Dict, Any

HEARTBEAT_INTERVAL = 5
STALE_TIMEOUT = 15
STUCK_TIMEOUT = 60

_lock = threading.Lock()
Home = 10000
_home_window = xbmcgui.Window(Home)
_PROPERTY_TASK = 'SkinInfo.ActiveTask'
_PROPERTY_ABORT = 'SkinInfo.CurrentAbortFlag'


class AbortFlag:
    """Thread-safe abort flag using single shared property.

    All tasks share the same property name. The property value stores the
    task_id, allowing each task to check if abort was requested for it.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def request(self) -> None:
        _home_window.setProperty(_PROPERTY_ABORT, self.task_id)

    def clear(self) -> None:
        current = _home_window.getProperty(_PROPERTY_ABORT)
        if current == self.task_id:
            _home_window.clearProperty(_PROPERTY_ABORT)

    def is_requested(self) -> bool:
        return _home_window.getProperty(_PROPERTY_ABORT) == self.task_id


class TaskContext:
    """Context manager for safe task registration and automatic cleanup.

    Automatically handles:
    - Task registration with fresh AbortFlag
    - Heartbeat thread to prove process is alive
    - Progress tracking to detect stuck operations
    - Task cleanup on exit (even on exceptions)

    Usage:
        with TaskContext("Pre-Cache Artwork") as ctx:
            while working:
                do_work()
                ctx.mark_progress()
                if ctx.abort_flag.is_requested():
                    break
    """

    def __init__(self, name: str) -> None:
        import uuid
        self.name = name
        task_id = str(uuid.uuid4())
        self.abort_flag = AbortFlag(task_id)
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()
        self._progress_lock = threading.Lock()
        self.last_progress = time.time()

    def __enter__(self) -> 'TaskContext':
        if not register_task(self.name, self.abort_flag):
            xbmc.log(f"SkinInfo: Failed to register task '{self.name}'", xbmc.LOGWARNING)
            raise RuntimeError(f"Failed to register task: {self.name}")

        self._stop_heartbeat.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)
            if self._heartbeat_thread.is_alive():
                xbmc.log(f"SkinInfo: Heartbeat thread still alive after join timeout for task '{self.name}'", xbmc.LOGWARNING)

        clear_task()
        return False

    def _heartbeat_loop(self) -> None:
        """Background thread that updates heartbeat and progress timestamps."""
        while not self._stop_heartbeat.wait(HEARTBEAT_INTERVAL):
            with self._progress_lock:
                last_progress = self.last_progress

            task_data = {
                'name': self.name,
                'task_id': self.abort_flag.task_id,
                'started_at': time.time(),
                'last_heartbeat': time.time(),
                'last_progress': last_progress
            }

            with _lock:
                _home_window.setProperty(_PROPERTY_TASK, json.dumps(task_data))

    def mark_progress(self) -> None:
        """Mark that work is actively happening (called by workers)."""
        with self._progress_lock:
            self.last_progress = time.time()


def _is_task_running_unlocked() -> bool:
    """Internal helper that checks task status without acquiring lock."""
    task_json = _home_window.getProperty(_PROPERTY_TASK)
    return bool(task_json)


def register_task(name: str, abort_flag: AbortFlag) -> bool:
    """Register a new background task.

    Args:
        name: Human-readable task name
        abort_flag: AbortFlag instance for cancellation

    Returns:
        True if registered successfully, False if task already running
    """
    with _lock:
        if _is_task_running_unlocked():
            return False

        task_data = json.dumps({
            'name': name,
            'task_id': abort_flag.task_id,
            'started_at': time.time(),
            'last_heartbeat': time.time(),
            'last_progress': time.time()
        })

        _home_window.setProperty(_PROPERTY_TASK, task_data)
        return True


def cancel_task() -> bool:
    """Cancel the currently running task by setting its abort flag.

    Returns:
        True if task was cancelled, False if no task running
    """
    with _lock:
        task_json = _home_window.getProperty(_PROPERTY_TASK)
        if not task_json:
            return False

        try:
            task_data = json.loads(task_json)
            task_id = task_data.get('task_id')

            if task_id:
                abort_flag = AbortFlag(task_id=task_id)
                abort_flag.request()
                return True
            else:
                return False
        except (json.JSONDecodeError, KeyError) as e:
            xbmc.log(f"SkinInfo: Error parsing task data during cancellation: {e}", xbmc.LOGWARNING)
            return False


def get_task_info() -> Optional[Dict[str, Any]]:
    """Get information about the currently running task.

    Returns:
        Dict with task metadata, or None if no task running
    """
    with _lock:
        task_json = _home_window.getProperty(_PROPERTY_TASK)
        if not task_json:
            return None

        try:
            return json.loads(task_json)
        except json.JSONDecodeError:
            return None


def is_task_running() -> bool:
    """Check if a background task is currently running.

    Returns:
        True if task is running, False otherwise
    """
    with _lock:
        return _is_task_running_unlocked()


def clear_task() -> None:
    """Clear the current task registration and abort flag."""
    with _lock:
        task_json = _home_window.getProperty(_PROPERTY_TASK)
        if task_json:
            try:
                task_data = json.loads(task_json)
                task_id = task_data.get('task_id')
                if task_id:
                    abort_flag = AbortFlag(task_id=task_id)
                    abort_flag.clear()
            except (json.JSONDecodeError, KeyError) as e:
                xbmc.log(f"SkinInfo: Error parsing task data during clear: {e}", xbmc.LOGWARNING)

        _home_window.clearProperty(_PROPERTY_TASK)


def cleanup_stale_tasks() -> None:
    """Remove stale task registrations (crashed process or stuck operation).

    Detects two failure modes:
    - No heartbeat: Process died or crashed (15s timeout)
    - No progress: Operation stuck in I/O or infinite loop (60s timeout)

    Safe to call on every script invocation.
    """
    task_info = get_task_info()
    if not task_info:
        return

    now = time.time()

    heartbeat_age = now - task_info.get('last_heartbeat', 0)
    if heartbeat_age > STALE_TIMEOUT:
        xbmc.log(
            f"SkinInfo: Clearing stale task '{task_info['name']}' "
            f"(no heartbeat for {heartbeat_age:.0f}s)",
            xbmc.LOGWARNING
        )
        clear_task()
        return

    progress_age = now - task_info.get('last_progress', 0)
    if progress_age > STUCK_TIMEOUT:
        xbmc.log(
            f"SkinInfo: Clearing stuck task '{task_info['name']}' "
            f"(no progress for {progress_age:.0f}s)",
            xbmc.LOGWARNING
        )
        clear_task()
        return
