"""Base dialog class with shared artwork functionality"""

from __future__ import annotations

from typing import List
import xbmcgui
from lib.artwork.utilities import get_language_display_name
from lib.kodi.client import decode_image_url, ADDON


class ArtworkDialogBase(xbmcgui.WindowXMLDialog):
    """Base class for artwork dialogs.

    Subclasses must define `BUTTON_SORT`, `BUTTON_SOURCE_PREF` control IDs and
    state vars `full_artwork_list`, `sort_mode`, `source_pref`, plus implement
    `_resort_artwork()`.
    """

    # Placeholders for subclass-supplied values (declared here so the helpers below typecheck).
    BUTTON_SORT: int = 0
    BUTTON_SOURCE_PREF: int = 0
    full_artwork_list: list = []
    sort_mode: str = 'popularity'
    source_pref: str = 'all'

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison; collapses fanart.tv paths to filename only."""
        if not url:
            return ''
        decoded = decode_image_url(url)
        if 'assets.fanart.tv' in decoded:
            return decoded.split('/')[-1]
        return decoded

    def _get_available_sources(self) -> set:
        """Get set of unique sources in the full artwork list."""
        sources = set()
        for art in self.full_artwork_list:
            source = art.get('source', '').lower()
            if source in ('tmdb', 'fanart.tv', 'fanarttv'):
                sources.add('tmdb' if source == 'tmdb' else 'fanart')
        return sources

    def _get_available_resolutions(self) -> set:
        """Get set of unique resolutions in the full artwork list."""
        resolutions = set()
        for art in self.full_artwork_list:
            width = art.get('width')
            height = art.get('height')
            if width and height:
                resolutions.add((width, height))
        return resolutions

    def _toggle_sort_mode(self) -> None:
        """Toggle between popularity and resolution sort modes."""
        self.sort_mode = 'resolution' if self.sort_mode == 'popularity' else 'popularity'
        self._resort_artwork()
        self._update_sort_button_label()

    def _update_sort_button_label(self) -> None:
        """Update sort button label to show current mode."""
        try:
            button = self.getControl(self.BUTTON_SORT)
            if self.sort_mode == 'popularity':
                button.setLabel('Sort: Popularity')
            else:
                button.setLabel('Sort: Resolution')
        except Exception:
            pass

    def _toggle_source_pref(self) -> None:
        """Toggle between source filters: all -> tmdb -> fanart -> all."""
        if self.source_pref == 'all':
            self.source_pref = 'tmdb'
        elif self.source_pref == 'tmdb':
            self.source_pref = 'fanart'
        else:
            self.source_pref = 'all'
        self._resort_artwork()
        self._update_source_pref_button_label()

    def _update_source_pref_button_label(self) -> None:
        """Update source filter button label to show current filter."""
        try:
            button = self.getControl(self.BUTTON_SOURCE_PREF)
            if self.source_pref == 'all':
                button.setLabel(ADDON.getLocalizedString(32132))
            elif self.source_pref == 'tmdb':
                button.setLabel(ADDON.getLocalizedString(32133))
            else:
                button.setLabel(ADDON.getLocalizedString(32134))
        except Exception:
            pass

    def _resort_artwork(self) -> None:
        """Subclasses must implement: re-sort `full_artwork_list` honoring sort_mode/source_pref/language."""
        raise NotImplementedError

    def create_artwork_listitem(
        self,
        art_info: dict,
        index: int
    ) -> xbmcgui.ListItem:
        """Create ListItem from artwork info dict.

        Properties (accessible in dialog skin XML via ListItem.Property):
        - dimensions: Width x Height (e.g., "1920x1080")
        - width: Image width in pixels
        - height: Image height in pixels
        - source: Source name (e.g., "TMDB", "fanart.tv")
        - language: Display name (e.g., "English")
        - language_short: Language code (e.g., "en")
        - season: Season number (when available)
        - fullurl: Full resolution image URL
        """
        url = art_info.get('url', '')
        preview = art_info.get('previewurl', url)
        width = art_info.get('width', 0)
        height = art_info.get('height', 0)
        language = art_info.get('language', '')
        season = art_info.get('season', '')
        source = art_info.get('source', '')

        label = f"Option {index + 1}"

        item = xbmcgui.ListItem(label=label)
        item.setArt({'thumb': preview, 'icon': preview})
        item.setProperty('fullurl', url)
        item.setProperty('index', str(index))

        if width:
            item.setProperty('width', str(width))
        if height:
            item.setProperty('height', str(height))
        if width and height:
            item.setProperty('dimensions', f"{width}x{height}")
        if language:
            item.setProperty('language_short', language)
            item.setProperty('language', get_language_display_name(language))
        if season:
            item.setProperty('season', str(season))
        if source:
            item.setProperty('source', source)

        return item

    def populate_list_batch(self, control, items: List[xbmcgui.ListItem]) -> None:
        """Add items to list control via addItems() - much faster than addItem() in a loop."""
        control.reset()
        if items:
            control.addItems(items)
