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
  400 - Header label (shows art type header, e.g., "Multi-Art Fanart Manager")
  401 - Item title label (shows media item title, e.g., "The Matrix")
  402 - Count label (e.g., "3 images in working set")

List 100 items show labels: "fanart1", "fanart2", "fanart3"... based on position (1-based)
List 200 items show labels: "Option 1 - 1920x1080 - [en]", etc. (with available metadata)

Window Properties Available:
  - multiart_dialog_active: "true" when dialog is open, cleared when closed
"""
from __future__ import annotations

import xbmc
import xbmcgui
import xbmcaddon
from typing import Optional
from resources.lib.dialogs.base import BaseArtworkDialog
from resources.lib.art_helpers import parse_art_slot_index
from resources.lib.kodi import request, extract_result, KODI_GET_DETAILS_METHODS, KODI_ID_KEYS


class MultiArtDialog(BaseArtworkDialog):
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
    LABEL_HEADER = 400
    LABEL_ITEM_TITLE = 401
    LABEL_SELECTION_COUNT = 402

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_type = kwargs.get('media_type', 'movie')
        self.dbid = kwargs.get('dbid', 0)
        self.title = kwargs.get('title', '')
        self.art_type = kwargs.get('art_type', 'fanart')
        self.test_mode = kwargs.get('test_mode', False)

        self.current_extra_art = {}
        self.available_art = []
        self.working_art = []
        self.result = None

    def onInit(self):
        """Called when dialog opens."""
        self.setProperty('multiart_dialog_active', 'true')

        try:
            art_label = f"Multi-Art {self.art_type.title()}" if self.art_type != 'fanart' else "Multi-Art Fanart"
            self.getControl(self.LABEL_HEADER).setLabel(f"[B]{art_label} Manager[/B]")  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            self.getControl(self.LABEL_ITEM_TITLE).setLabel(self.title)  # type: ignore[attr-defined]
        except Exception:
            pass

        if self.test_mode:
            self._load_test_data()
        else:
            self._load_current_extra_art()
            self._fetch_available_art()

        self._populate_current_art()
        self._populate_available_art()
        self._update_selection_count()

    def _load_current_extra_art(self) -> None:
        """Load current extra art URLs from library (numbered slots only)."""
        if self.media_type not in KODI_GET_DETAILS_METHODS:
            return

        method, id_key, result_key = KODI_GET_DETAILS_METHODS[self.media_type]

        resp = request(method, {id_key: self.dbid, 'properties': ['art']})
        if not resp:
            return

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return

        art = details.get('art', {})

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
        """Fetch available art from scrapers using GetAvailableArt."""
        if self.media_type not in KODI_ID_KEYS:
            return

        id_key = KODI_ID_KEYS[self.media_type]

        resp = request(
            'VideoLibrary.GetAvailableArt',
            {
                'item': {id_key: self.dbid},
                'arttype': self.art_type
            }
        )

        if not resp:
            return

        available = extract_result(resp, 'availableart', [])
        self.available_art = available

    def _load_test_data(self) -> None:
        """Load dummy test data for skinning preview."""
        addon = xbmcaddon.Addon('script.skin.info.service')
        addon_path = addon.getAddonInfo('path')
        import os
        test_image_path = os.path.join(addon_path, 'resources', 'media', 'artwork_test.png')

        self.current_extra_art = {
            f'{self.art_type}1': test_image_path,
            f'{self.art_type}2': test_image_path,
        }

        self.working_art = [test_image_path, test_image_path]

        dimensions_map = {
            'fanart': [(1920, 1080), (1280, 720), (3840, 2160)],
            'poster': [(1000, 1500), (2000, 3000), (680, 1000)],
            'characterart': [(512, 512), (1000, 1000), (256, 256)],
            'clearlogo': [(800, 310), (400, 155), (1200, 465)],
            'clearart': [(1000, 562), (500, 281), (1500, 843)],
            'banner': [(1000, 185), (758, 140), (1500, 277)],
            'landscape': [(1920, 1080), (1280, 720), (500, 281)],
            'keyart': [(1000, 1500), (2000, 3000), (680, 1000)],
            'discart': [(1000, 1000), (512, 512), (2000, 2000)],
        }

        base_dims = dimensions_map.get(self.art_type, [(1920, 1080), (1280, 720), (3840, 2160)])

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
            display_url = url.split('#')[0]

            item = xbmcgui.ListItem(label=slot)
            item.setArt({'thumb': display_url})
            item.setProperty('url', url)
            item.setProperty('index', str(idx))
            items.append(item)

        self.populate_list_batch(control, items)

    def _populate_available_art(self) -> None:
        """
        Populate AVAILABLE_ART_LIST with available options NOT in working set.

        Uses shared create_artwork_listitem() method and batch operation.
        """
        try:
            control = self.getControl(self.AVAILABLE_ART_LIST)
        except Exception:
            return

        working_urls = set(self.working_art)

        items = [
            self.create_artwork_listitem(art_info, idx)
            for idx, art_info in enumerate(self.available_art)
            if art_info.get('url', '') not in working_urls
        ]

        self.populate_list_batch(control, items)

    def _update_selection_count(self) -> None:
        """Update selection count label."""
        try:
            label_control = self.getControl(self.LABEL_SELECTION_COUNT)
            count = len(self.working_art)
            if count == 0:
                label_control.setLabel("No images in working set")  # type: ignore[attr-defined]
            elif count == 1:
                label_control.setLabel("1 image in working set")  # type: ignore[attr-defined]
            else:
                label_control.setLabel(f"{count} images in working set")  # type: ignore[attr-defined]
        except Exception:
            pass

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

    def _add_from_available(self) -> None:
        """Add selected item from available art to working set."""
        try:
            control = self.getControl(self.AVAILABLE_ART_LIST)
            item = control.getSelectedItem()  # type: ignore[attr-defined]
            if not item:
                return

            url = item.getProperty('url')
            self.working_art.append(url)

            self._populate_current_art()
            self._populate_available_art()
            self._update_selection_count()

        except Exception as e:
            xbmc.log(f"SkinInfo: Error adding from available: {str(e)}", xbmc.LOGERROR)

    def _remove_from_current(self) -> None:
        """Remove selected item from working set."""
        try:
            control = self.getControl(self.CURRENT_ART_LIST)
            item = control.getSelectedItem()  # type: ignore[attr-defined]
            if not item:
                return

            index = int(item.getProperty('index'))

            if 0 <= index < len(self.working_art):
                self.working_art.pop(index)

            self._populate_current_art()
            self._populate_available_art()
            self._update_selection_count()

        except Exception as e:
            xbmc.log(f"SkinInfo: Error removing from current: {str(e)}", xbmc.LOGERROR)

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
                art_dict[slot] = ""

        self.result = art_dict
        self.close()

    def close(self) -> None:
        """Override close to clear active dialog property."""
        self.setProperty('multiart_dialog_active', '')
        super().close()


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

    dialog = MultiArtDialog(
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
