"""Slideshow pool population + property update integration."""
from __future__ import annotations

import time

import xbmc

from lib.kodi.client import log


class SlideshowDriver:
    """Drives slideshow pool population (first run) and periodic property refresh."""

    def __init__(self):
        self._pool_populated = False
        self._last_update = 0.0

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

        try:
            from lib.service.slideshow import update_all_slideshow_properties
            update_all_slideshow_properties()
            self._last_update = time.time()

        except Exception as e:
            log("Service", f"Slideshow: Update error: {str(e)}", xbmc.LOGERROR)
