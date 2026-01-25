"""Stinger (post-credits scene) detection for movies.

Detects and notifies about post-credits scenes during movie playback.
Uses TMDB keywords as primary source, Trakt as fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple

import xbmc
import xbmcgui
import xbmcvfs

from lib.kodi.client import log, ADDON

# Default icon path (skinners can override via Skin.String)
DEFAULT_STINGER_ICON = xbmcvfs.translatePath(
    "special://home/addons/script.skin.info.service/resources/icons/stinger.png"
)


class StingerType(Enum):
    """Type of post-credits scene."""
    NONE = "none"
    DURING = "during"
    AFTER = "after"
    BOTH = "both"


@dataclass
class StingerInfo:
    """Information about post-credits scenes for a movie."""
    has_during: bool = False
    has_after: bool = False
    source: str = ""

    @property
    def stinger_type(self) -> StingerType:
        """Get the combined stinger type."""
        if self.has_during and self.has_after:
            return StingerType.BOTH
        if self.has_during:
            return StingerType.DURING
        if self.has_after:
            return StingerType.AFTER
        return StingerType.NONE

    @property
    def has_stinger(self) -> bool:
        """Check if any stinger exists."""
        return self.has_during or self.has_after


# TMDB keyword names for stinger detection
TMDB_KEYWORD_DURING = "duringcreditsstinger"
TMDB_KEYWORD_AFTER = "aftercreditsstinger"

# String IDs for notifications
STR_HEADING = 32162  # "Post-Credits Scene"
STR_DURING = 32163   # "Stay for scene during credits"
STR_AFTER = 32164    # "Stay for scene after credits"
STR_BOTH = 32165     # "Stay for scenes during and after credits"


def get_settings() -> Dict[str, Any]:
    """Get stinger detection settings.

    Returns:
        Dictionary with settings:
        - enabled: bool
        - minutes_before_end: int
        - notification_duration: int (seconds)
    """
    return {
        "enabled": ADDON.getSettingBool("stinger_enabled"),
        "minutes_before_end": ADDON.getSettingInt("stinger_minutes_before_end") or 8,
        "notification_duration": ADDON.getSettingInt("stinger_notification_duration") or 4,
    }


def is_trakt_configured() -> bool:
    """Check if Trakt has a valid token configured."""
    token_path = xbmcvfs.translatePath(
        "special://profile/addon_data/script.skin.info.service/trakt_tokens.json"
    )
    return xbmcvfs.exists(token_path)


def get_stinger_from_properties(window_id: int = 12901) -> Optional[StingerInfo]:
    """
    Read stinger info from window properties (set by online service).

    Args:
        window_id: Window ID to read from (default: fullscreenvideo)

    Returns:
        StingerInfo if properties indicate stinger found, None otherwise
    """
    window = xbmcgui.Window(window_id)
    stinger_type = window.getProperty("SkinInfo.Stinger.Type")

    if not stinger_type or stinger_type == "none":
        return None

    source = window.getProperty("SkinInfo.Stinger.Source")
    has_during = window.getProperty("SkinInfo.Stinger.HasDuring") == "true"
    has_after = window.getProperty("SkinInfo.Stinger.HasAfter") == "true"

    if has_during or has_after:
        return StingerInfo(has_during=has_during, has_after=has_after, source=source)

    return None


def get_stinger_from_trakt(ids: Dict[str, Optional[str]]) -> Optional[StingerInfo]:
    """Check Trakt for stinger information.

    Args:
        ids: Dictionary with tmdb, imdb, or trakt_slug IDs

    Returns:
        StingerInfo if found, None otherwise
    """
    from lib.data.api.trakt import ApiTrakt

    # Filter out None values for Trakt API
    clean_ids = {k: v for k, v in ids.items() if v is not None}
    if not clean_ids:
        return None

    trakt = ApiTrakt()
    data = trakt.fetch_data("movie", clean_ids)

    if not data:
        return None

    has_during = data.get("during_credits", False)
    has_after = data.get("after_credits", False)

    if has_during or has_after:
        return StingerInfo(has_during=has_during, has_after=has_after, source="trakt")

    return None


def get_stinger_from_kodi_tags(movie_details: Dict[str, Any]) -> Optional[StingerInfo]:
    """Check Kodi library tags for stinger keywords.

    Args:
        movie_details: Movie details dict from Kodi JSON-RPC

    Returns:
        StingerInfo if tags found, None otherwise
    """
    tags = movie_details.get("tag", [])
    if not tags:
        return None

    tag_names = {t.lower() for t in tags if isinstance(t, str)}

    has_during = TMDB_KEYWORD_DURING in tag_names
    has_after = TMDB_KEYWORD_AFTER in tag_names

    if has_during or has_after:
        return StingerInfo(has_during=has_during, has_after=has_after, source="kodi_tags")

    return None


def get_stinger_info(
    ids: Optional[Dict[str, Optional[str]]] = None,
    movie_details: Optional[Dict[str, Any]] = None
) -> Optional[StingerInfo]:
    """Get stinger information from fallback sources.

    Note: TMDB is handled by online service which sets properties directly.
    This function checks fallback sources:
    1. Kodi library tags
    2. Trakt (if configured)

    Args:
        ids: Dictionary of IDs for Trakt lookup
        movie_details: Kodi movie details for tag check

    Returns:
        StingerInfo or None if no stinger data found
    """
    # Try Kodi tags
    if movie_details:
        info = get_stinger_from_kodi_tags(movie_details)
        if info:
            log("Service", f"Stinger info from Kodi tags: {info.stinger_type.value}", xbmc.LOGDEBUG)
            return info

    # Try Trakt if configured
    if ids and is_trakt_configured():
        info = get_stinger_from_trakt(ids)
        if info:
            log("Service", f"Stinger info from Trakt: {info.stinger_type.value}", xbmc.LOGDEBUG)
            return info

    return None


def set_stinger_properties(info: Optional[StingerInfo], window_id: int = 12901) -> None:
    """Set window properties for stinger information.

    Properties set on fullscreenvideo window (12901):
    - SkinInfo.Stinger.HasDuring: "true" or ""
    - SkinInfo.Stinger.HasAfter: "true" or ""
    - SkinInfo.Stinger.Type: "during", "after", "both", or "none"
    - SkinInfo.Stinger.Source: "tmdb", "trakt", "kodi_tags", or ""

    Args:
        info: StingerInfo object or None to clear
        window_id: Window ID to set properties on (default: fullscreenvideo)
    """
    window = xbmcgui.Window(window_id)

    if info and info.has_stinger:
        window.setProperty("SkinInfo.Stinger.HasDuring", "true" if info.has_during else "")
        window.setProperty("SkinInfo.Stinger.HasAfter", "true" if info.has_after else "")
        window.setProperty("SkinInfo.Stinger.Type", info.stinger_type.value)
        window.setProperty("SkinInfo.Stinger.Source", info.source)
    else:
        window.clearProperty("SkinInfo.Stinger.HasDuring")
        window.clearProperty("SkinInfo.Stinger.HasAfter")
        window.clearProperty("SkinInfo.Stinger.Type")
        window.clearProperty("SkinInfo.Stinger.Source")


def clear_stinger_properties(window_id: int = 12901) -> None:
    """Clear all stinger properties from window.

    Args:
        window_id: Window ID to clear properties from
    """
    set_stinger_properties(None, window_id)


def set_notify_property(show: bool, window_id: int = 12901) -> None:
    """Set the ShowNotify property to trigger skin notification display.

    Args:
        show: Whether to show notification
        window_id: Window ID to set property on
    """
    window = xbmcgui.Window(window_id)
    if show:
        window.setProperty("SkinInfo.Stinger.ShowNotify", "true")
    else:
        window.clearProperty("SkinInfo.Stinger.ShowNotify")


def _get_notification_icon() -> str:
    """Get notification icon path, checking skin override first.

    Skinners can override via: Skin.String(SkinInfo.Stinger.NotificationIcon)

    Returns:
        Icon path or empty string to use Kodi default
    """
    skin_icon = xbmc.getInfoLabel("Skin.String(SkinInfo.Stinger.NotificationIcon)")
    if skin_icon and xbmcvfs.exists(skin_icon):
        return skin_icon

    if xbmcvfs.exists(DEFAULT_STINGER_ICON):
        return DEFAULT_STINGER_ICON

    return ""


def _get_notification_text(stinger_type: StingerType) -> Tuple[str, str]:
    """Get notification heading and message, checking skin overrides first.

    Skinners can override via:
    - Skin.String(SkinInfo.Stinger.Heading)
    - Skin.String(SkinInfo.Stinger.MessageDuring)
    - Skin.String(SkinInfo.Stinger.MessageAfter)
    - Skin.String(SkinInfo.Stinger.MessageBoth)

    Args:
        stinger_type: Type of stinger scene

    Returns:
        Tuple of (heading, message)
    """
    skin_heading = xbmc.getInfoLabel("Skin.String(SkinInfo.Stinger.Heading)")
    heading = skin_heading if skin_heading else ADDON.getLocalizedString(STR_HEADING)

    if stinger_type == StingerType.BOTH:
        skin_msg = xbmc.getInfoLabel("Skin.String(SkinInfo.Stinger.MessageBoth)")
        message = skin_msg if skin_msg else ADDON.getLocalizedString(STR_BOTH)
    elif stinger_type == StingerType.DURING:
        skin_msg = xbmc.getInfoLabel("Skin.String(SkinInfo.Stinger.MessageDuring)")
        message = skin_msg if skin_msg else ADDON.getLocalizedString(STR_DURING)
    elif stinger_type == StingerType.AFTER:
        skin_msg = xbmc.getInfoLabel("Skin.String(SkinInfo.Stinger.MessageAfter)")
        message = skin_msg if skin_msg else ADDON.getLocalizedString(STR_AFTER)
    else:
        message = ""

    return heading, message


def _skin_handles_notification() -> bool:
    """Check if skin has opted in to handle stinger notifications.

    Skins can opt in by setting: Skin.SetBool(SkinInfo.Stinger.CustomNotification)

    When opted in, the addon skips Dialog().notification() and the skin
    handles display using window properties (SkinInfo.Stinger.ShowNotify, etc).

    Returns:
        True if skin handles notifications, False to use Kodi notification
    """
    return xbmc.getCondVisibility("Skin.HasSetting(SkinInfo.Stinger.CustomNotification)")


def show_notification(info: StingerInfo, duration_seconds: int = 4) -> None:
    """Show Kodi notification for stinger.

    If skin has opted in via Skin.SetBool(SkinInfo.Stinger.CustomNotification),
    skips Kodi notification and relies on skin to display using properties.

    Otherwise, skinners can customize the Kodi notification via Skin.String:
    - SkinInfo.Stinger.NotificationIcon: Custom icon path
    - SkinInfo.Stinger.Heading: Custom heading text
    - SkinInfo.Stinger.MessageDuring: Custom message for during-credits scene
    - SkinInfo.Stinger.MessageAfter: Custom message for after-credits scene
    - SkinInfo.Stinger.MessageBoth: Custom message for both types

    Args:
        info: StingerInfo with stinger details
        duration_seconds: How long to show notification
    """
    if info.stinger_type == StingerType.NONE:
        return

    # Skin handles its own notification display
    if _skin_handles_notification():
        log("Service", "Skin handles stinger notification, skipping Kodi dialog", xbmc.LOGDEBUG)
        return

    heading, message = _get_notification_text(info.stinger_type)
    if not message:
        return

    icon = _get_notification_icon()

    xbmcgui.Dialog().notification(
        heading,
        message,
        icon if icon else xbmcgui.NOTIFICATION_INFO,
        duration_seconds * 1000
    )


def is_near_credits(minutes_before_end: int = 8) -> bool:
    """Check if playback is near the end (credits).

    Uses chapter detection if available, falls back to time-based.

    Args:
        minutes_before_end: Minutes before end to trigger (for chapterless files)

    Returns:
        True if near credits, False otherwise
    """
    # Try chapter-based detection first
    try:
        chapter_count_str = xbmc.getInfoLabel("Player.ChapterCount")
        if chapter_count_str:
            chapter_count = int(chapter_count_str)
            if chapter_count > 0:
                current_chapter_str = xbmc.getInfoLabel("Player.Chapter")
                if current_chapter_str:
                    current_chapter = int(current_chapter_str)
                    if current_chapter == chapter_count:
                        return True
                    return False
    except (ValueError, TypeError):
        pass

    # Fall back to time-based detection
    player = xbmc.Player()
    if not player.isPlayingVideo():
        return False

    try:
        total_time = player.getTotalTime()
        current_time = player.getTime()

        if total_time <= 0:
            return False

        time_remaining_minutes = (total_time - current_time) / 60
        return time_remaining_minutes < minutes_before_end
    except Exception as e:
        log("Service", f"Error checking playback position: {e}", xbmc.LOGDEBUG)
        return False


class StingerMonitor:
    """Monitors playback for stinger notification timing."""

    def __init__(self):
        self.current_movie_id: Optional[str] = None
        self.stinger_info: Optional[StingerInfo] = None
        self.notified: bool = False
        self._settings: Optional[Dict[str, Any]] = None

    def reset(self) -> None:
        """Reset state for new playback."""
        self.current_movie_id = None
        self.stinger_info = None
        self.notified = False
        self._settings = None
        clear_stinger_properties()
        set_notify_property(False)

    @property
    def settings(self) -> Dict[str, Any]:
        """Get cached settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def on_playback_start(
        self,
        movie_id: str,
        ids: Optional[Dict[str, Optional[str]]] = None,
        movie_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle movie playback start.

        Note: TMDB stinger detection is handled by online service.
        This checks fallback sources (Kodi tags, Trakt).

        Args:
            movie_id: Kodi movie ID
            ids: Additional IDs for Trakt lookup
            movie_details: Kodi movie details
        """
        if not self.settings["enabled"]:
            return

        if movie_id == self.current_movie_id:
            return

        self.reset()
        self.current_movie_id = movie_id

        self.stinger_info = get_stinger_info(ids=ids, movie_details=movie_details)

        if self.stinger_info and self.stinger_info.has_stinger:
            set_stinger_properties(self.stinger_info)
            log("Service", f"Stinger detected (fallback): {self.stinger_info.stinger_type.value}", xbmc.LOGDEBUG)

    def check_notification(self) -> None:
        """Check if notification should be shown based on playback position."""
        if not self.settings["enabled"]:
            return

        if self.notified:
            return

        if not self.stinger_info or not self.stinger_info.has_stinger:
            self.stinger_info = get_stinger_from_properties()

        if not self.stinger_info or not self.stinger_info.has_stinger:
            return

        if not is_near_credits(self.settings["minutes_before_end"]):
            return

        self.notified = True
        set_notify_property(True)
        show_notification(self.stinger_info, self.settings["notification_duration"])

    def on_playback_stop(self) -> None:
        """Handle playback stop."""
        self.reset()
