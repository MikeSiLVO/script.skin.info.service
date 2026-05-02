"""Online data service: coordinator thread composing focus/player/music/updater handlers."""
from __future__ import annotations

import threading

import xbmc

from lib.kodi.client import log
from lib.service.online.focus import FocusHandler
from lib.service.online.player import PlayerHandler
from lib.service.online.musicplayer import MusicPlayerHandler
from lib.service.online.updater import UpdaterHandler


ONLINE_POLL_INTERVAL = 0.10


class ServiceAbortFlag:
    """Lightweight abort flag for online service API calls (Kodi abort + service stop)."""

    def __init__(self, abort_event: threading.Event):
        self._abort_event = abort_event
        self._monitor = xbmc.Monitor()

    def is_requested(self) -> bool:
        if self._monitor.abortRequested():
            return True
        return self._abort_event.is_set()


class OnlineScanMonitor(xbmc.Monitor):
    """Triggers online updater refresh when Kodi finishes a library scan."""

    def __init__(self, online_service: "OnlineServiceMain"):
        super().__init__()
        self._online_service = online_service

    def onNotification(self, sender: str, method: str, data: str) -> None:
        if method == 'VideoLibrary.OnScanFinished':
            self._online_service.request_update()


class OnlineServiceMain(threading.Thread):
    """Coordinator: composes focus/player/music/updater handlers and runs the poll loop."""

    def __init__(self):
        super().__init__(daemon=True)
        self.abort = threading.Event()
        self.abort_flag = ServiceAbortFlag(self.abort)
        # GIL guarantees atomic add/discard/in on CPython sets, no lock needed
        self.updater_in_progress: set = set()
        self.focus = FocusHandler(self)
        self.player = PlayerHandler(self)
        self.music = MusicPlayerHandler(self)
        self.updater = UpdaterHandler(self)

    def request_update(self) -> None:
        """Request the updater to restart its pass (e.g. after library scan)."""
        self.updater.request_restart()

    def run(self) -> None:
        monitor = xbmc.Monitor()
        scan_monitor = OnlineScanMonitor(self)
        log("Service", "Online service started", xbmc.LOGINFO)

        self.updater.start()

        try:
            while not monitor.waitForAbort(ONLINE_POLL_INTERVAL):
                if self.abort.is_set():
                    break
                try:
                    self._loop()
                except Exception as e:
                    log("Service", f"Online service error: {e}", xbmc.LOGWARNING)
        finally:
            del scan_monitor
            log("Service", "Online service stopped", xbmc.LOGINFO)

    def _loop(self) -> None:
        self.focus.process()
        self.player.process()
        self.music.process_audio()
        self.music.process_video()
        self.music.rotate_fanart()
