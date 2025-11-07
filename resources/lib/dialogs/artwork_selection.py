"""Visual artwork chooser for manual review.

SKINNER XML INTEGRATION:

Control IDs:
  100 - Artwork list control (displays available options, click to select)
  201 - Skip button
  202 - Cancel button
  203 - Multi-Art button (visibility controlled automatically by script)
  204 - Change Language button (visibility controlled by show_change_language property)
  300 - Title label
  301 - Info label

Window Properties Available:
  - arttype: Art type being selected (e.g., "poster", "fanart")
  - itemtitle: Item title (e.g., "The Matrix")
  - optioncount: Number of available options (string)
  - mediatype: Media type (movie, tvshow, etc.)
  - year: Release year
  - hascurrentart: "true" or "false" - whether item already has this art type
  - currentarturl: URL of current artwork (if any)
  - showmultiart: "true" or "false" - multi-art button availability
  - current_language: Current language filter code (e.g., "en")
  - language_display: Display name for current language (e.g., "English")
  - showing_count: Number of filtered items shown (string)
  - total_count: Total number of items before filtering (string)
  - show_change_language: "true" or "false" - whether to show Change Language button
"""
from __future__ import annotations

import xbmc
import xbmcaddon
from typing import Optional
from resources.lib.dialogs.base import BaseArtworkDialog
from resources.lib.dialogs.multiart import show_multiart_dialog


class ArtworkSelectionDialog(BaseArtworkDialog):
    """
    Dialog for selecting artwork from multiple options with visual preview.
    Shows thumbnails of available artwork options with metadata.
    """

    ARTWORK_LIST = 100
    BUTTON_SKIP = 201
    BUTTON_CANCEL = 202
    BUTTON_MULTIART = 203
    BUTTON_CHANGE_LANGUAGE = 204
    LABEL_TITLE = 300
    LABEL_INFO = 301

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = kwargs.get('title', '')
        self.art_type = kwargs.get('art_type', '')
        self.available_art = kwargs.get('available_art', [])
        self.media_type = kwargs.get('media_type', '')
        self.year = kwargs.get('year', '')
        self.current_url = kwargs.get('current_url', '')
        self.dbid = kwargs.get('dbid', 0)
        self.test_mode = kwargs.get('test_mode', False)
        self.review_mode = kwargs.get('review_mode', 'missing')

        self.selected_index = None
        self.result = None
        self.multiart_result = None

        self.full_artwork_list = kwargs.get('full_artwork_list', [])
        self.current_language = None
        self.available_languages = []

    def onInit(self):
        """Called when dialog opens."""
        from resources.lib.art_helpers import get_available_languages, get_language_display_name
        from resources.lib.utils import get_preferred_language_code

        if not self.full_artwork_list:
            self.full_artwork_list = self.available_art

        self.available_languages = get_available_languages(self.full_artwork_list)

        if self.current_language is None:
            self.current_language = get_preferred_language_code()

        self.setProperty('arttype', self.art_type)
        self.setProperty('itemtitle', self.title)
        self.setProperty('optioncount', str(len(self.available_art)))
        self.setProperty('mediatype', self.media_type)
        self.setProperty('year', self.year)
        self.setProperty('hascurrentart', 'true' if self.current_url else 'false')
        self.setProperty('currentarturl', self.current_url)
        self.setProperty('showmultiart', 'true' if self.art_type == 'fanart' else 'false')
        self.setProperty('reviewmode', self.review_mode)

        self.setProperty('current_language', self.current_language)
        self.setProperty('language_display', get_language_display_name(self.current_language))
        self.setProperty('showing_count', str(len(self.available_art)))
        self.setProperty('total_count', str(len(self.full_artwork_list)))
        self.setProperty('show_change_language', 'true' if len(self.available_languages) > 1 else 'false')

        state_text = "Missing artwork" if self.review_mode == 'missing' else "Replace existing artwork"
        self.setProperty('state_label', state_text)

        try:
            button = self.getControl(self.BUTTON_MULTIART)
            button.setVisible(self.art_type == 'fanart')
        except Exception:
            pass

        try:
            self.getControl(self.LABEL_TITLE).setLabel(f"{self.title}")  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            info_text = (
                f"Select {self.art_type} ({len(self.available_art)} options available)"
                f"[CR]{state_text}"
            )
            self.getControl(self.LABEL_INFO).setLabel(info_text)  # type: ignore[attr-defined]
        except Exception:
            pass

        self._populate_artwork_list()

        if self.available_art:
            try:
                self.setFocusId(self.ARTWORK_LIST)
            except Exception:
                try:
                    self.setFocusId(self.BUTTON_SKIP)
                except Exception:
                    pass
        else:
            try:
                self.setFocusId(self.BUTTON_SKIP)
            except Exception:
                pass

    def _populate_artwork_list(self) -> None:
        """Populate list with available artwork options using batch operation."""
        try:
            control = self.getControl(self.ARTWORK_LIST)
        except Exception:
            return

        items = [
            self.create_artwork_listitem(art_info, idx)
            for idx, art_info in enumerate(self.available_art)
        ]

        self.populate_list_batch(control, items)

    def onClick(self, controlId):
        """Handle button/list clicks."""
        if controlId == self.ARTWORK_LIST:
            self._select_current()

        elif controlId == self.BUTTON_SKIP:
            self.result = 'skip'
            self.close()

        elif controlId == self.BUTTON_CANCEL:
            self.result = None
            self.close()

        elif controlId == self.BUTTON_MULTIART:
            self._launch_multiart()

        elif controlId == self.BUTTON_CHANGE_LANGUAGE:
            self._show_language_picker()

    def onAction(self, action):
        """Handle keyboard/remote actions."""
        if action.getId() in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.result = None
            self.close()

    def _select_current(self) -> None:
        """Select currently focused artwork."""
        try:
            control = self.getControl(self.ARTWORK_LIST)
            item = control.getSelectedItem()  # type: ignore[attr-defined]
            if not item:
                return

            self.selected_index = int(item.getProperty('index'))
            self.result = 'selected'
            self.close()

        except Exception as e:
            xbmc.log(f"SkinInfo: Error selecting artwork: {str(e)}", xbmc.LOGERROR)

    def _launch_multiart(self) -> None:
        """Launch multi-art selection dialog."""
        if self.art_type != 'fanart':
            return

        if not self.dbid and not self.test_mode:
            xbmc.log("SkinInfo: Cannot launch multi-art - no dbid provided", xbmc.LOGWARNING)
            return

        result = show_multiart_dialog(
            media_type=self.media_type,
            dbid=self.dbid,
            title=self.title,
            art_type='fanart',
            test_mode=self.test_mode
        )

        if result:
            self.multiart_result = result
            self.result = 'multiart'
            self.close()

    def _show_language_picker(self) -> None:
        """Show dialog to select language filter."""
        import xbmcgui
        from resources.lib.art_helpers import get_language_display_name

        if not self.available_languages or len(self.available_languages) <= 1:
            return

        def count_language(lang: str) -> int:
            from resources.lib.utils import normalize_language_tag
            return sum(1 for art in self.full_artwork_list if normalize_language_tag(art.get('language')) == lang)

        labels = [
            f"{get_language_display_name(lang)} ({count_language(lang)})"
            for lang in self.available_languages
        ]

        selected = xbmcgui.Dialog().select("Select Language", labels)
        if selected < 0:
            return

        new_language = self.available_languages[selected]
        if new_language != self.current_language:
            self._switch_language(new_language)

    def _switch_language(self, new_language: str) -> None:
        """Refresh list control with new language filter."""
        from resources.lib.art_helpers import filter_artwork_by_language, get_language_display_name

        self.current_language = new_language
        self.available_art = filter_artwork_by_language(
            self.full_artwork_list,
            art_type=self.art_type,
            language_code=new_language
        )

        self.setProperty('current_language', self.current_language)
        self.setProperty('language_display', get_language_display_name(self.current_language))
        self.setProperty('showing_count', str(len(self.available_art)))
        self.setProperty('optioncount', str(len(self.available_art)))

        info_text = (
            f"Select {self.art_type} ({len(self.available_art)} options available)"
            f"[CR]{self.getProperty('state_label')}"
        )
        try:
            self.getControl(self.LABEL_INFO).setLabel(info_text)
        except Exception:
            pass

        try:
            control = self.getControl(self.ARTWORK_LIST)
            control.reset()

            items = [
                self.create_artwork_listitem(art_info, idx)
                for idx, art_info in enumerate(self.available_art)
            ]

            control.addItems(items)
        except Exception as e:
            xbmc.log(f"SkinInfo: Error refreshing artwork list: {str(e)}", xbmc.LOGERROR)


def show_artwork_selection_dialog(
    title: str,
    art_type: str,
    available_art: list[dict],
    full_artwork_list: Optional[list[dict]] = None,
    media_type: str = '',
    year: str = '',
    current_url: str = '',
    dbid: int = 0,
    test_mode: bool = False,
    review_mode: str = 'missing'
) -> tuple[str, Optional[dict]]:
    """
    Show artwork selection dialog and return result.

    Args:
        title: Item title (e.g., "The Matrix")
        art_type: Art type being selected (e.g., "poster", "fanart")
        available_art: List of artwork dicts (filtered) to display initially
        full_artwork_list: Complete unfiltered list for language switching (optional)
        media_type: Media type (movie, tvshow, episode, etc.) - optional
        year: Release year (e.g., "1999") - optional
        current_url: URL of existing artwork if any - optional
        dbid: Database ID for item (required for multi-art) - optional
        test_mode: Enable test mode (launches multiart in test mode) - optional
        review_mode: "missing" or "candidate" context for the review

    Returns:
        Tuple of (action, artwork):
        - ('selected', artwork_dict) - User selected artwork
        - ('multiart', multiart_dict) - User selected multi-art images
        - ('skip', None) - User skipped this art type
        - ('cancel', None) - User cancelled review entirely
    """
    if not available_art:
        return ('skip', None)

    addon = xbmcaddon.Addon('script.skin.info.service')
    addon_path = addon.getAddonInfo('path')

    dialog = ArtworkSelectionDialog(
        'script.skin.info.service-ArtworkSelection.xml',
        addon_path,
        'default',
        '1080i',
        title=title,
        art_type=art_type,
        available_art=available_art,
        full_artwork_list=full_artwork_list or available_art,
        media_type=media_type,
        year=year,
        current_url=current_url,
        dbid=dbid,
        test_mode=test_mode,
        review_mode=review_mode
    )

    dialog.doModal()
    result = dialog.result
    selected_index = dialog.selected_index
    multiart_result = dialog.multiart_result
    del dialog

    if result == 'selected' and selected_index is not None:
        return ('selected', available_art[selected_index])
    elif result == 'multiart' and multiart_result is not None:
        return ('multiart', multiart_result)
    elif result == 'skip':
        return ('skip', None)
    else:
        return ('cancel', None)


def _generate_dummy_artwork(art_type: str) -> list[dict]:
    """
    Generate dummy artwork data for testing dialog layouts.

    Args:
        art_type: Type of artwork (poster, fanart, clearlogo, etc.)

    Returns:
        List of dummy artwork dicts with all possible fields populated
    """
    addon = xbmcaddon.Addon('script.skin.info.service')
    addon_path = addon.getAddonInfo('path')
    import os
    test_image_path = os.path.join(addon_path, 'resources', 'media', 'artwork_test.png')

    art_dimensions = {
        'poster': [
            (2000, 3000), (1400, 2100), (1000, 1500), (680, 1000),
            (2000, 2963), (1382, 2048), (1000, 1481), (675, 1000),
            (1944, 2880), (1350, 2000), (972, 1440), (650, 963),
            (2025, 3000), (1458, 2160), (1013, 1500), (690, 1022),
            (2100, 3000), (1500, 2143), (1080, 1543), (720, 1029),
            (1980, 2970), (1425, 2138), (990, 1485), (660, 990)
        ],
        'fanart': [
            (3840, 2160), (1920, 1080), (1280, 720), (1600, 900),
            (3840, 2160), (2560, 1440), (1920, 1080), (1366, 768),
            (3840, 2160), (2048, 1152), (1920, 1080), (1440, 810),
            (3840, 2160), (2732, 1536), (1920, 1080), (1600, 900),
            (3840, 2160), (2400, 1350), (1920, 1080), (1280, 720),
            (3840, 2160), (2880, 1620), (1920, 1080), (1536, 864)
        ],
        'clearlogo': [
            (800, 310), (800, 371), (400, 155), (800, 310),
            (800, 320), (800, 350), (400, 160), (800, 300),
            (800, 330), (800, 360), (400, 165), (800, 340),
            (800, 315), (800, 380), (400, 150), (800, 325),
            (800, 335), (800, 390), (400, 170), (800, 345)
        ],
        'clearart': [
            (1000, 562), (1000, 1426), (500, 281), (1000, 800),
            (1000, 600), (1000, 1400), (500, 300), (1000, 750),
            (1000, 650), (1000, 1450), (500, 325), (1000, 700),
            (1000, 580), (1000, 1420), (500, 290), (1000, 850),
            (1000, 620), (1000, 1440), (500, 310), (1000, 780)
        ],
        'banner': [
            (1000, 185), (758, 140), (500, 92), (1000, 185),
            (1000, 190), (760, 145), (500, 95), (1000, 180),
            (1000, 188), (755, 142), (500, 94), (1000, 187),
            (1000, 192), (765, 148), (500, 96), (1000, 183),
            (1000, 186), (762, 143), (500, 93), (1000, 189)
        ],
        'landscape': [
            (1920, 1080), (1280, 720), (960, 540), (1600, 900),
            (1920, 1080), (1366, 768), (1024, 576), (1440, 810),
            (1920, 1080), (1536, 864), (1152, 648), (1600, 900),
            (1920, 1080), (1280, 720), (1088, 612), (1536, 864),
            (1920, 1080), (1366, 768), (960, 540), (1440, 810)
        ],
        'keyart': [
            (2000, 3000), (1000, 1500), (1400, 2100), (2000, 3000),
            (2025, 3000), (1013, 1500), (1458, 2160), (2100, 3000),
            (1980, 2970), (990, 1485), (1425, 2138), (1944, 2880),
            (2000, 2963), (1000, 1481), (1382, 2048), (2000, 3000),
            (2100, 3000), (1080, 1543), (1500, 2143), (1980, 2970)
        ],
        'characterart': [
            (512, 512), (1000, 1426), (512, 512), (1000, 1400),
            (512, 512), (1000, 1450), (512, 512), (1000, 1420),
            (512, 512), (1000, 1440), (512, 512), (1000, 1430),
            (512, 512), (1000, 1410), (512, 512), (1000, 1445),
            (512, 512), (1000, 1435), (512, 512), (1000, 1425)
        ],
        'discart': [
            (1000, 1000), (512, 512), (1000, 1000), (512, 512),
            (1000, 1000), (512, 512), (1000, 1000), (512, 512),
            (1000, 1000), (512, 512), (1000, 1000), (512, 512),
            (1000, 1000), (512, 512), (1000, 1000), (512, 512),
            (1000, 1000), (512, 512), (1000, 1000), (512, 512)
        ]
    }

    dimensions = art_dimensions.get(art_type, art_dimensions['poster'])
    languages = ['en', 'en', 'en', 'fr', 'de', 'es', 'it', 'ja', 'pt', 'ru', 'zh', 'ko', '']

    num_items = min(len(dimensions), 30)
    dummy_art = []
    for idx in range(num_items):
        width, height = dimensions[idx]

        art = {
            'url': test_image_path,
            'previewurl': test_image_path,
            'width': width,
            'height': height,
            'rating': round(10 - (idx * 0.2), 1),
            'language': languages[idx % len(languages)],
            'likes': str(max(50, 1000 - (idx * 30))),
            'label': f'{art_type.title()} Option {idx + 1}'
        }

        if art_type in ('poster', 'landscape', 'banner') and idx < 10:
            art['season'] = str((idx % 5) + 1)

        dummy_art.append(art)

    return dummy_art
