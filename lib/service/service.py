"""Service entry point for script.skin.info.service."""
from __future__ import annotations

import threading

import xbmc

from lib.kodi.client import ADDON, log
from lib.kodi.utils import clear_prop, set_prop, wait_for_kodi_ready

SKIN_BOOL = "SkinInfo.Service"
POLL_INTERVAL = 1.0


class OrchestratorMonitor(xbmc.Monitor):
    """Monitor that flags when addon settings change."""

    def __init__(self) -> None:
        super().__init__()
        self.settings_dirty = True  # force initial evaluation

    def onSettingsChanged(self) -> None:
        self.settings_dirty = True


class Orchestrator:
    """Manages start/stop of all service threads based on skin bool and settings."""

    def __init__(self, monitor: OrchestratorMonitor) -> None:
        self.monitor = monitor
        self._online_thread = None
        self._library_thread = None
        self._imdb_thread = None
        self._stinger_thread = None

    def run(self) -> None:
        from lib.data.database._infrastructure import init_database
        from lib.data.database.music import init_music_database
        from lib.service.slideshow import SlideshowMonitor

        init_database()
        init_music_database()

        if not wait_for_kodi_ready(self.monitor):
            return

        self._start_housekeeping()

        slideshow_monitor = SlideshowMonitor()

        version = ADDON.getAddonInfo("version")
        kodi_ver = xbmc.getInfoLabel("System.BuildVersionCode") or "0.0.0"
        log("Service", f"Orchestrator started (version={version}, kodi={kodi_ver})", xbmc.LOGINFO)

        try:
            while not self.monitor.abortRequested():
                self._evaluate()
                if self.monitor.waitForAbort(POLL_INTERVAL):
                    break
        finally:
            self._stop_all()
            del slideshow_monitor
            log("Service", "Orchestrator stopped", xbmc.LOGINFO)

    def _start_housekeeping(self) -> None:
        """Expired cache cleanup in a daemon thread after startup."""
        def _run() -> None:
            # Delay so services get DB access first; avoids competing for locks during startup
            if self.monitor.waitForAbort(30):
                return
            from lib.data.database.cache import clear_expired_cache
            from lib.data.database.music import clear_expired_music_cache
            clear_expired_cache()
            clear_expired_music_cache()

        threading.Thread(target=_run, daemon=True).start()

    def _evaluate(self) -> None:
        skin_enabled = xbmc.getCondVisibility(f'Skin.HasSetting({SKIN_BOOL})')
        self._manage_skin_services(skin_enabled)

        if self.monitor.settings_dirty:
            self.monitor.settings_dirty = False
            self._manage_setting_services()

    def _manage_skin_services(self, enabled: bool) -> None:
        if enabled:
            if self._library_thread is None or not self._library_thread.is_alive():
                self._start_library()
            if self._online_thread is None or not self._online_thread.is_alive():
                self._start_online()
            set_prop("SkinInfo.Service.Running", "true")
        else:
            if self._online_thread is not None:
                self._stop_online()
            if self._library_thread is not None:
                self._stop_library()
            clear_prop("SkinInfo.Service.Running")

    def _manage_setting_services(self) -> None:
        imdb_enabled = ADDON.getSetting("imdb_auto_update") != "off"
        stinger_enabled = ADDON.getSettingBool("stinger_enabled")

        if imdb_enabled:
            if self._imdb_thread is None or not self._imdb_thread.is_alive():
                self._start_imdb()
        elif self._imdb_thread is not None:
            self._stop_imdb()

        if stinger_enabled:
            if self._stinger_thread is None or not self._stinger_thread.is_alive():
                self._start_stinger()
        elif self._stinger_thread is not None:
            self._stop_stinger()

    def _start_online(self) -> None:
        from lib.service.online import OnlineServiceMain
        self._online_thread = OnlineServiceMain()
        self._online_thread.start()

    def _stop_online(self) -> None:
        if self._online_thread is None:
            return
        self._online_thread.abort.set()
        self._online_thread.join(timeout=2)
        self._online_thread = None

    def _start_library(self) -> None:
        from lib.service.main import ServiceMain
        self._library_thread = ServiceMain()
        self._library_thread.start()

    def _stop_library(self) -> None:
        if self._library_thread is None:
            return
        self._library_thread.abort.set()
        self._library_thread.join(timeout=2)
        self._library_thread = None

    def _start_imdb(self) -> None:
        from lib.service.main import ImdbUpdateService
        self._imdb_thread = ImdbUpdateService()
        self._imdb_thread.start()

    def _stop_imdb(self) -> None:
        if self._imdb_thread is None:
            return
        self._imdb_thread.abort.set()
        self._imdb_thread.join(timeout=2)
        self._imdb_thread = None

    def _start_stinger(self) -> None:
        from lib.service.main import StingerService
        self._stinger_thread = StingerService()
        self._stinger_thread.start()

    def _stop_stinger(self) -> None:
        if self._stinger_thread is None:
            return
        self._stinger_thread.abort.set()
        self._stinger_thread.join(timeout=2)
        self._stinger_thread = None

    def _stop_all(self) -> None:
        for thread in (self._stinger_thread, self._imdb_thread, self._online_thread, self._library_thread):
            if thread is not None:
                thread.abort.set()
        for attr in ('_stinger_thread', '_imdb_thread', '_online_thread', '_library_thread'):
            thread = getattr(self, attr)
            if thread is not None:
                thread.join(timeout=2)
                setattr(self, attr, None)


def main() -> None:
    monitor = OrchestratorMonitor()
    Orchestrator(monitor).run()


if __name__ == "__main__":
    main()
