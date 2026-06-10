"""Slideshow pool population + property update integration."""
from __future__ import annotations

import threading
import time
from typing import Optional

import xbmc

from lib.kodi.client import log


class SlideshowDriver:
    """Drives slideshow pool population (first run) and periodic property refresh."""

    def __init__(self):
        self._pool_populated = False
        self._last_update = 0.0
        self._update_thread: Optional[threading.Thread] = None
        self._stopping = False

    def populate_pool_if_needed(self) -> None:
        """First-run pool population. Subsequent calls are no-ops."""
        if self._pool_populated:
            return

        try:
            from lib.service.slideshow import is_pool_populated, populate_slideshow_pool

            if not is_pool_populated():
                log("Service", "Slideshow: Populating pool for first time...", xbmc.LOGINFO)
                populate_slideshow_pool()
                log("Service", "Slideshow: Pool population complete", xbmc.LOGINFO)

            self._pool_populated = True
        except Exception as e:
            log("Service", f"Slideshow: Error populating pool: {str(e)}", xbmc.LOGERROR)

    def update(self) -> None:
        """Refresh slideshow props if the skin opted in and the interval has elapsed."""
        if not xbmc.getCondVisibility('Skin.HasSetting(SkinInfo.EnableSlideshow)'):
            return

        interval_str = xbmc.getInfoLabel('Skin.String(SkinInfo.SlideshowRefreshInterval)') or '10'
        try:
            from lib.service.slideshow import MIN_SLIDESHOW_INTERVAL, MAX_SLIDESHOW_INTERVAL
            interval = int(interval_str)
            interval = max(MIN_SLIDESHOW_INTERVAL, min(interval, MAX_SLIDESHOW_INTERVAL))
        except ValueError:
            interval = 10

        now = time.time()
        if (now - self._last_update) < interval:
            return

        # runs on a thread: force-caching fanart does blocking xbmcvfs reads
        # that would stall the 100ms service loop
        if self._update_thread and self._update_thread.is_alive():
            return
        self._update_thread = threading.Thread(target=self._run_update, daemon=True)
        self._update_thread.start()

    def _run_update(self) -> None:
        try:
            if self._stopping:
                return
            from lib.service.slideshow import update_all_slideshow_properties
            update_all_slideshow_properties()
            self._last_update = time.time()
        except Exception as e:
            log("Service", f"Slideshow: Update error: {str(e)}", xbmc.LOGERROR)

    def cleanup(self) -> None:
        """Clear `SkinInfo.Slideshow.*` window properties.

        Waits briefly for an in-flight update so it can't re-set props after the clear.
        """
        try:
            self._stopping = True
            thread = self._update_thread
            if thread and thread.is_alive():
                thread.join(timeout=5)
            from lib.service.slideshow import clear_slideshow_properties
            clear_slideshow_properties()
        except Exception as e:
            log("Service", f"Slideshow: Cleanup error: {str(e)}", xbmc.LOGERROR)
