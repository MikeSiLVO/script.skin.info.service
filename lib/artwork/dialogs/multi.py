"""Multi-select ordered image chooser for extra art slots.

Handles EXTRA art slots only (fanart1/fanart2, poster1/poster2, etc.).
Main art slot (fanart, poster, etc.) is handled by dialogs/artwork_selection.py

SKINNER XML INTEGRATION:

Control IDs (must match these IDs in your XML):
  100 - Current/Working art list (shows working set, click to remove)
  200 - Available art list (shows options NOT in working set, click to add)
  300 - Confirm/Apply button (applies working set and closes)
  301 - Cancel button
  302 - Clear All button (resets to original state)

List 100 items show labels: "fanart1", "fanart2", "fanart3"... based on position (1-based)
List 200 items show labels: "Option 1 - 1920x1080 - [en]", etc. (with available metadata)

Window Properties Available (use $INFO[Window.Property(name)]):
  - heading: Media item title (e.g., "The Matrix")
  - arttype: Art type being managed (e.g., "Multi-Art Fanart")
  - mediatype: Media type (movie, tvshow, etc.)
  - count: Selection count text (e.g., "3 images selected")
  - count_total: Total available images (string)
  - count_selected: Number of selected images (string)
  - multiart_dialog_active: "true" when dialog is open, cleared when closed

ListItem Properties Available (for control 200):
  - ListItem.Property(is_current): "true" if this artwork is currently set as main art (e.g., fanart, poster)
  - ListItem.Property(dimensions): Width x Height (e.g., "1920x1080")
  - ListItem.Property(source): Source name (e.g., "TMDB", "fanart.tv")
  - ListItem.Property(language): Display name for artwork's language
  - ListItem.Property(fullurl): Full resolution image URL
"""
from __future__ import annotations

import xbmc
import xbmcgui
import xbmcaddon
from typing import Optional
from lib.artwork.dialogs.base import ArtworkDialogBase
from lib.artwork.utilities import parse_art_slot_index
from lib.artwork.config import FANART_DIMENSIONS_VARIANTS
from lib.kodi.client import get_item_details, KODI_GET_DETAILS_METHODS, log


class ArtworkDialogMulti(ArtworkDialogBase):
    """
    Custom dialog for multi-art management (extra art slots only).

    Uses a "working set" approach:
    - List 100: Working set (click to remove)
    - List 200: Available art not in working set (click to add)
    - Apply: Saves working set as fanart1, fanart2, etc.

    Note: Main art slot (fanart, poster, etc.) is handled separately by artwork_selection_dialog.
    This dialog only manages the "extra" numbered slots.
    """

    CURRENT_ART_LIST = 100
    AVAILABLE_ART_LIST = 200
    BUTTON_APPLY = 300
    BUTTON_CANCEL = 301
    BUTTON_CLEAR_ALL = 302
    BUTTON_SORT = 303
    BUTTON_SOURCE_PREF = 304

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_type = kwargs.get('media_type', 'movie')
        self.dbid = kwargs.get('dbid', 0)
        self.title = kwargs.get('title', '')
        self.art_type = kwargs.get('art_type', 'fanart')
        self.test_mode = kwargs.get('test_mode', False)

        self.current_extra_art = {}
        self.current_main_art = None
        self.available_art = []
        self.full_artwork_list = []
        self.working_art = []
        self.result = None
        self.sort_mode = 'popularity'
        self.source_pref = 'all'

    def onInit(self):
        """Called when dialog opens."""
        self.setProperty('multiart_dialog_active', 'true')

        if self.test_mode:
            self._load_test_data()
        else:
            self._load_current_extra_art()
            self._fetch_available_art()

        # Set window properties for XML
        art_label = f"Multi-Art {self.art_type.title()}" if self.art_type != 'fanart' else "Multi-Art Fanart"
        self.setProperty('heading', self.title)
        self.setProperty('arttype', art_label)
        self.setProperty('mediatype', self.media_type)

        self._populate_current_art()
        self._populate_available_art()
        self._update_selection_count()

        available_sources = self._get_available_sources()
        self.setProperty('show_source_button', 'true' if len(available_sources) > 1 else 'false')

        available_resolutions = self._get_available_resolutions()
        self.setProperty('show_sort_button', 'true' if len(available_resolutions) > 1 else 'false')

        try:
            button = self.getControl(self.BUTTON_SOURCE_PREF)
            button.setVisible(len(available_sources) > 1)
        except Exception:
            pass

        try:
            button = self.getControl(self.BUTTON_SORT)
            button.setVisible(len(available_resolutions) > 1)
        except Exception:
            pass

        self._update_sort_button_label()
        self._update_source_pref_button_label()

    def _load_current_extra_art(self) -> None:
        """Load current extra art URLs from library (numbered slots only) and main art."""
        if self.media_type not in KODI_GET_DETAILS_METHODS:
            return

        details = get_item_details(self.media_type, self.dbid, ['art'])
        if not isinstance(details, dict):
            return

        art = details.get('art', {})

        # Load main art slot (e.g., 'fanart', 'poster')
        self.current_main_art = art.get(self.art_type)

        for key, url in art.items():
            if key.startswith(self.art_type) and key != self.art_type:
                suffix = key[len(self.art_type):]
                if suffix and suffix.isdigit():
                    if url:
                        self.current_extra_art[key] = url

        sorted_slots = sorted(
            self.current_extra_art.items(),
            key=lambda x: parse_art_slot_index(x[0])
        )
        self.working_art = [url for _, url in sorted_slots if url]

    def _fetch_available_art(self) -> None:
        """Fetch available art from online sources (TMDB, fanart.tv)."""
        from lib.data.api.artwork import create_default_fetcher
        from lib.artwork.utilities import sort_artwork_by_popularity, filter_artwork_by_language

        try:
            fetcher = create_default_fetcher()
            all_art = fetcher.fetch_all(self.media_type, self.dbid)
            self.full_artwork_list = all_art.get(self.art_type, [])

            filtered = filter_artwork_by_language(
                self.full_artwork_list,
                art_type=self.art_type,
                language_code=None
            )

            self.available_art = sort_artwork_by_popularity(
                filtered,
                art_type=self.art_type,
                sort_mode=self.sort_mode,
                source_pref=self.source_pref
            )
        except Exception as e:
            import traceback
            log("Artwork", f"Error fetching available art: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
            self.available_art = []
            self.full_artwork_list = []

    def _load_test_data(self) -> None:
        """Load dummy test data for skinning preview."""
        import xbmcvfs

        art_type_map = {
            'poster': ('artwork_test_poster.png', (1000, 1500)),
            'keyart': ('artwork_test_poster.png', (1000, 1500)),
            'fanart': ('artwork_test_fanart.png', (1920, 1080)),
            'clearlogo': ('artwork_test_clearlogo.png', (800, 310)),
            'clearart': ('artwork_test_landscape.png', (1000, 562)),
            'landscape': ('artwork_test_landscape.png', (1000, 562)),
            'thumb': ('artwork_test_landscape.png', (1000, 562)),
            'banner': ('artwork_test_banner.png', (1000, 185)),
            'characterart': ('artwork_test_characterart.png', (1000, 1399)),
            'discart': ('artwork_test_square.png', (1000, 1000)),
        }

        image_file, _ = art_type_map.get(self.art_type.lower(), ('artwork_test_poster.png', (1000, 1500)))
        test_image_path = xbmcvfs.translatePath(f'special://home/addons/script.skin.info.service/resources/media/artwork_test/{image_file}')

        self.current_extra_art = {
            f'{self.art_type}1': test_image_path,
            f'{self.art_type}2': test_image_path,
        }

        self.working_art = [test_image_path, test_image_path]

        base_dims = FANART_DIMENSIONS_VARIANTS.get(self.art_type, [(1920, 1080), (1280, 720), (3840, 2160)])

        self.available_art = []
        for i in range(20):
            width, height = base_dims[i % len(base_dims)]

            self.available_art.append({
                'url': f'{test_image_path}#{i}',
                'previewurl': test_image_path,
                'width': width,
                'height': height,
            })

    def _populate_current_art(self) -> None:
        """
        Populate CURRENT_ART_LIST with working art set (click to remove).

        Uses batch operation for better performance.
        """
        try:
            control = self.getControl(self.CURRENT_ART_LIST)
        except Exception:
            return

        items = []
        for idx, url in enumerate(self.working_art):
            if not url:
                continue

            slot = f"{self.art_type}{idx + 1}"

            item = xbmcgui.ListItem(label=slot)
            item.setProperty('url', url)
            item.setProperty('index', str(idx))

            # Find artwork info to get preview URL and dimensions
            art_info = next((art for art in self.full_artwork_list if art.get('url') == url), None)
            if art_info:
                preview = art_info.get('previewurl', url)
                item.setArt({'thumb': preview})

                width = art_info.get('width')
                height = art_info.get('height')
                if width and height:
                    item.setProperty('dimensions', f"{width}x{height}")
                    item.setProperty('width', str(width))
                    item.setProperty('height', str(height))
            else:
                item.setArt({'thumb': url})

            items.append(item)

        self.populate_list_batch(control, items)

    def create_artwork_listitem(self, art_info: dict, index: int) -> xbmcgui.ListItem:
        """
        Override to add is_current property for main art highlighting.

        Marks artwork that is currently set as the main art slot (e.g., fanart, poster).
        """
        item = super().create_artwork_listitem(art_info, index)

        if self.current_main_art:

            url = art_info.get('url', '')
            normalized_current = self._normalize_url(self.current_main_art)
            normalized_art = self._normalize_url(url)

            if normalized_current == normalized_art:
                item.setProperty('is_current', 'true')
            else:
                item.setProperty('is_current', 'false')
        else:
            item.setProperty('is_current', 'false')

        return item

    def _populate_available_art(self) -> None:
        """
        Populate AVAILABLE_ART_LIST with available options NOT in working set.

        Uses shared create_artwork_listitem() method and batch operation.
        """
        try:
            control = self.getControl(self.AVAILABLE_ART_LIST)
        except Exception:
            return

        normalized_working_urls = {self._normalize_url(url) for url in self.working_art}

        items = [
            self.create_artwork_listitem(art_info, idx)
            for idx, art_info in enumerate(self.available_art)
            if self._normalize_url(art_info.get('url', '')) not in normalized_working_urls
        ]

        self.populate_list_batch(control, items)

    def _update_selection_count(self) -> None:
        """Update selection count property (matches regular artwork dialog format)."""
        count = len(self.working_art)
        if count == 0:
            count_text = "No images selected"
        elif count == 1:
            count_text = "1 image selected"
        else:
            count_text = f"{count} images selected"

        self.setProperty('count', count_text)
        self.setProperty('count_total', str(len(self.available_art)))
        self.setProperty('count_selected', str(count))

    def onClick(self, controlId):
        """Handle button/list clicks."""
        if controlId == self.AVAILABLE_ART_LIST:
            self._add_from_available()

        elif controlId == self.CURRENT_ART_LIST:
            self._remove_from_current()

        elif controlId == self.BUTTON_APPLY:
            self._apply_changes()

        elif controlId == self.BUTTON_CANCEL:
            self.result = None
            self.close()

        elif controlId == self.BUTTON_CLEAR_ALL:
            self._clear_all()

        elif controlId == self.BUTTON_SORT:
            self._toggle_sort_mode()

        elif controlId == self.BUTTON_SOURCE_PREF:
            self._toggle_source_pref()

    def _add_from_available(self) -> None:
        """Add selected item from available art to working set."""
        try:
            control = self.getControl(self.AVAILABLE_ART_LIST)
            item = control.getSelectedItem()
            if not item:
                return

            url = item.getProperty('fullurl')
            if url:
                self.working_art.append(url)

                self._populate_current_art()
                self._populate_available_art()
                self._update_selection_count()

        except Exception as e:
            log("Artwork", f"Error adding from available: {str(e)}", xbmc.LOGERROR)

    def _remove_from_current(self) -> None:
        """Remove selected item from working set."""
        try:
            control = self.getControl(self.CURRENT_ART_LIST)
            item = control.getSelectedItem()
            if not item:
                return

            index = int(item.getProperty('index'))

            if 0 <= index < len(self.working_art):
                self.working_art.pop(index)

            self._populate_current_art()
            self._populate_available_art()
            self._update_selection_count()

        except Exception as e:
            log("Artwork", f"Error removing from current: {str(e)}", xbmc.LOGERROR)

    def _clear_all(self) -> None:
        """Clear working set back to original state."""
        sorted_slots = sorted(
            self.current_extra_art.items(),
            key=lambda x: parse_art_slot_index(x[0])
        )
        self.working_art = [url for _, url in sorted_slots if url]

        self._populate_current_art()
        self._populate_available_art()
        self._update_selection_count()

    def _apply_changes(self) -> None:
        """Apply working set as final extra art assignments."""
        art_dict = {}
        for idx, url in enumerate(self.working_art):
            slot = f"{self.art_type}{idx + 1}"
            art_dict[slot] = url

        for slot in self.current_extra_art.keys():
            if slot not in art_dict:
                art_dict[slot] = None

        self.result = art_dict
        self.close()

    def close(self) -> None:
        """Override close to clear active dialog property."""
        self.setProperty('multiart_dialog_active', '')
        super().close()

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
        if self.sort_mode == 'popularity':
            self.sort_mode = 'resolution'
        else:
            self.sort_mode = 'popularity'

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
                button.setLabel('Source: All')
            elif self.source_pref == 'tmdb':
                button.setLabel('Source: TMDB')
            else:
                button.setLabel('Source: Fanart.tv')
        except Exception:
            pass

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison by stripping image:// wrapper and decoding.

        For fanart.tv URLs, compares just the filename since paths can vary.
        """
        if not url:
            return ''

        from lib.kodi.client import decode_image_url

        decoded = decode_image_url(url)

        if 'assets.fanart.tv' in decoded:
            return decoded.split('/')[-1]

        return decoded

    def _resort_artwork(self) -> None:
        """Re-sort and filter artwork from full list, then refresh available panel."""
        from lib.artwork.utilities import sort_artwork_by_popularity, filter_artwork_by_language

        filtered = filter_artwork_by_language(
            self.full_artwork_list,
            art_type=self.art_type,
            language_code=None
        )

        self.available_art = sort_artwork_by_popularity(
            filtered,
            art_type=self.art_type,
            sort_mode=self.sort_mode,
            source_pref=self.source_pref
        )

        self._populate_available_art()
        self._update_selection_count()


def show_multiart_dialog(media_type: str, dbid: int, title: str, art_type: str = 'fanart', test_mode: bool = False) -> Optional[dict]:
    """
    Show multi-art dialog and return selected art dict (extra slots only).

    Args:
        media_type: Media type (movie, tvshow, etc.)
        dbid: Database ID
        title: Item title for display
        art_type: Art type for extra slots (fanart, poster, characterart, etc.)
                  Manages numbered slots only (fanart1+, poster1+, etc.)
        test_mode: Enable test mode (uses dummy data) - optional

    Returns:
        Dict of art assignments or None if cancelled
        Example: {'fanart1': 'url1', 'fanart2': 'url2'}
    """
    addon = xbmcaddon.Addon('script.skin.info.service')
    addon_path = addon.getAddonInfo('path')

    dialog = ArtworkDialogMulti(
        'script.skin.info.service-MultiArtSelection.xml',
        addon_path,
        'default',
        '1080i',
        media_type=media_type,
        dbid=dbid,
        title=title,
        art_type=art_type,
        test_mode=test_mode
    )

    dialog.doModal()
    result = dialog.result
    del dialog

    return result
