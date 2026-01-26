"""Visual artwork chooser for manual review.

SKINNER XML INTEGRATION:

Control IDs:
  100 - Artwork list control (displays available options, click to select)
  201 - Skip button
  202 - Cancel button
  203 - Multi-Art button (visibility controlled automatically by script)
  204 - Change Language button (visibility controlled by show_change_language property)
  205 - Sort button (visibility controlled by show_sort_button property)
  206 - Source button (visibility controlled by show_source_button property)
Window Properties Available:
  - property(heading): Title (e.g., "The Matrix")
  - property(arttype): Art type being selected (e.g., "Poster", "Fanart")
  - property(mediatype): Media type (movie, tvshow, etc.)
  - property(year): Release year
  - property(hascurrentart): "true" or "false" - whether item already has this art type
  - property(currentarturl): URL of current artwork (if any)
  - property(show_multiart): "true" or "false" - multi-art button availability
  - property(language_short): Current language filter code (e.g., "en")
  - property(language): Display name for current language (e.g., "English")
  - property(count): Smart display string ("58 available" or "24 of 58 available (English)")
  - property(count_filtered): Raw number of filtered items (string)
  - property(count_total): Raw number of total items (string)
  - property(show_change_language): "true" or "false" - whether to show Change Language button
  - property(show_sort_button): "true" or "false" - whether to show Sort button (hidden when only one resolution available)
  - property(show_source_button): "true" or "false" - whether to show Source filter button (hidden when only one source available)
ListItem Properties Available (for control 100):
  - ListItem.Property(is_current): "true" if this artwork is currently assigned (use for highlighting)
  - ListItem.Property(dimensions): Width x Height (e.g., "1920x1080")
  - ListItem.Property(source): Source name (e.g., "TMDB", "fanart.tv")
  - ListItem.Property(language): Display name for artwork's language
  - ListItem.Property(fullurl): Full resolution image URL
"""
from __future__ import annotations

import xbmc
from lib.infrastructure.dialogs import show_select
from typing import Optional, List, Tuple
from lib.artwork.dialogs.base import ArtworkDialogBase
from lib.artwork.dialogs.multi import show_multiart_dialog
from lib.kodi.settings import KodiSettings
from lib.kodi.client import decode_image_url, log, ADDON


class ArtworkDialogSelect(ArtworkDialogBase):
    """
    Dialog for selecting artwork from multiple options with visual preview.
    Shows thumbnails of available artwork options with metadata.
    """

    ARTWORK_LIST = 100
    BUTTON_SKIP = 201
    BUTTON_CANCEL = 202
    BUTTON_MULTIART = 203
    BUTTON_CHANGE_LANGUAGE = 204
    BUTTON_SORT = 205
    BUTTON_SOURCE_PREF = 206

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
        self.queued_multiart = None

        self.full_artwork_list = kwargs.get('full_artwork_list', [])
        self.current_language = None
        self.available_languages = []
        self.sort_mode = 'popularity'
        self.source_pref = 'all'

    def onInit(self):
        """Called when dialog opens."""
        from lib.artwork.utilities import get_available_languages, get_language_display_name
        from lib.kodi.utils import get_preferred_language_code

        if not self.full_artwork_list:
            self.full_artwork_list = self.available_art

        self.available_languages = get_available_languages(self.full_artwork_list)

        if self.current_language is None:
            self.current_language = get_preferred_language_code()

        self.setProperty('heading', self.title)
        self.setProperty('year', self.year)
        self.setProperty('mediatype', self.media_type)
        self.setProperty('arttype', self.art_type.capitalize())
        self.setProperty('hascurrentart', 'true' if self.current_url else 'false')
        self.setProperty('currentarturl', decode_image_url(self.current_url) if self.current_url else '')
        self.setProperty('count_total', str(len(self.full_artwork_list)))
        self.setProperty('count_filtered', str(len(self.available_art)))

        try:
            prefer_fanart_language = KodiSettings.prefer_fanart_language()
        except Exception:
            prefer_fanart_language = False

        is_fanart_no_lang_filter = self.art_type == 'fanart' and not prefer_fanart_language

        language_display = get_language_display_name(self.current_language)

        if len(self.available_art) != len(self.full_artwork_list):
            if is_fanart_no_lang_filter:
                count_text = f"{len(self.available_art)} of {len(self.full_artwork_list)} available (Text-free)"
            else:
                count_text = f"{len(self.available_art)} of {len(self.full_artwork_list)} available ({language_display})"
        else:
            count_text = f"{len(self.full_artwork_list)} available"
        self.setProperty('count', count_text)

        self.setProperty('language', language_display)
        self.setProperty('language_short', self.current_language)
        # Show button if multiple languages OR if filtering reduced the list (user needs "All" option)
        show_lang_button = len(self.available_languages) > 1 or len(self.available_art) != len(self.full_artwork_list)
        self.setProperty('show_change_language', 'true' if show_lang_button else 'false')
        self.setProperty('show_multiart', 'true' if self.art_type == 'fanart' else 'false')

        available_sources = self._get_available_sources()
        self.setProperty('show_source_button', 'true' if len(available_sources) > 1 else 'false')

        available_resolutions = self._get_available_resolutions()
        self.setProperty('show_sort_button', 'true' if len(available_resolutions) > 1 else 'false')

        try:
            button = self.getControl(self.BUTTON_MULTIART)
            button.setVisible(self.art_type == 'fanart')
        except Exception:
            pass

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

        from lib.artwork.utilities import sort_artwork_by_popularity
        self.available_art = sort_artwork_by_popularity(
            self.available_art,
            art_type=self.art_type,
            sort_mode=self.sort_mode,
            source_pref=self.source_pref
        )

        self._populate_artwork_list()
        self._update_sort_button_label()
        self._update_source_pref_button_label()

        if self.available_art:
            try:
                self.setFocusId(self.ARTWORK_LIST)
            except Exception:
                try:
                    self.setFocusId(self.BUTTON_SKIP)
                except Exception:
                    pass
        elif self.full_artwork_list:
            # Filtered list empty but artwork exists - focus Change Language
            try:
                self.setFocusId(self.BUTTON_CHANGE_LANGUAGE)
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

        normalized_current = self._normalize_url(self.current_url) if self.current_url else None

        items = []
        for idx, art_info in enumerate(self.available_art):
            item = self.create_artwork_listitem(art_info, idx)
            if normalized_current:
                art_url = art_info.get('url', '')
                normalized_art = self._normalize_url(art_url) if art_url else ''
                if normalized_current == normalized_art:
                    item.setProperty('is_current', 'true')
            items.append(item)

        self.populate_list_batch(control, items)

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison by stripping image:// wrapper and decoding.

        Kodi cached images use format: image://http%3a%2f%2fexample.com%2fimage.jpg/
        This strips the wrapper and decodes to: http://example.com/image.jpg

        For fanart.tv URLs, compares just the filename since paths can vary:
        - Old: https://assets.fanart.tv/fanart/movies/ID/movieposter/filename.jpg
        - New: https://assets.fanart.tv/fanart/filename.jpg
        Both normalize to just the filename for comparison.
        """
        if not url:
            return ''

        decoded = decode_image_url(url)

        if 'assets.fanart.tv' in decoded:
            return decoded.split('/')[-1]

        return decoded

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

        elif controlId == self.BUTTON_SORT:
            self._toggle_sort_mode()

        elif controlId == self.BUTTON_SOURCE_PREF:
            self._toggle_source_pref()

    def onAction(self, action):
        """Handle keyboard/remote actions."""
        if action.getId() in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.result = None
            self.close()

    def _select_current(self) -> None:
        """Select currently focused artwork."""
        try:
            control = self.getControl(self.ARTWORK_LIST)
            item = control.getSelectedItem()
            if not item:
                return

            self.selected_index = int(item.getProperty('index'))
            self.result = 'selected'
            self.close()

        except Exception as e:
            log("Artwork", f"Error selecting artwork: {str(e)}", xbmc.LOGERROR)

    def _launch_multiart(self) -> None:
        """Launch multi-art selection dialog.

        Queues multi-art result instead of closing immediately.
        The queued result is applied when the main dialog closes.
        """
        if self.art_type != 'fanart':
            return

        if not self.dbid and not self.test_mode:
            log("Artwork", "Cannot launch multi-art - no dbid provided", xbmc.LOGWARNING)
            return

        result = show_multiart_dialog(
            media_type=self.media_type,
            dbid=self.dbid,
            title=self.title,
            art_type='fanart',
            test_mode=self.test_mode
        )

        if result:
            self.queued_multiart = result
            self.setProperty('multiart_queued', 'true')

    def _show_language_picker(self) -> None:
        """Show dialog to select language filter."""
        from lib.artwork.utilities import get_language_display_name
        from lib.kodi.utils import get_preferred_language_code, normalize_language_tag

        is_filtered = len(self.available_art) != len(self.full_artwork_list)
        # Allow picker if multiple languages OR if filtering is active (need "All" option)
        if not self.available_languages or (len(self.available_languages) <= 1 and not is_filtered):
            return

        def count_language(lang: str) -> int:
            return sum(1 for art in self.full_artwork_list if normalize_language_tag(art.get('language')) == lang)

        preferred_lang = get_preferred_language_code()
        is_filtered = len(self.available_art) != len(self.full_artwork_list)

        sorted_languages = []
        other_languages = []

        for lang in self.available_languages:
            if lang == preferred_lang:
                continue
            if lang == '':
                continue
            other_languages.append((lang, count_language(lang)))

        other_languages.sort(key=lambda x: x[1], reverse=True)

        if preferred_lang in self.available_languages:
            sorted_languages.append(preferred_lang)

        if '' in self.available_languages:
            sorted_languages.append('')

        sorted_languages.extend([lang for lang, _ in other_languages])

        # Only show "All languages" if it would combine multiple language options
        if is_filtered and len(sorted_languages) > 1:
            sorted_languages.append('all')

        labels = []
        for lang in sorted_languages:
            if lang == 'all':
                labels.append(f"All languages ({len(self.full_artwork_list)})")
            else:
                count = count_language(lang)
                display = "Text-free" if lang == '' else get_language_display_name(lang)
                labels.append(f"{display} ({count})")

        selected = show_select(ADDON.getLocalizedString(32554), labels)
        if selected < 0:
            return

        new_language = sorted_languages[selected]
        # Always apply - even if same language, switches from art-type filtering to simple filtering
        if new_language == 'all':
            self.current_language = 'all'
        else:
            self.current_language = new_language
        self._resort_artwork()

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

    def _resort_artwork(self) -> None:
        """Re-sort and filter artwork from full list, then refresh UI."""
        from lib.artwork.utilities import sort_artwork_by_popularity
        from lib.kodi.utils import normalize_language_tag

        # 'all' bypasses filtering entirely
        if self.current_language == 'all':
            filtered = self.full_artwork_list
        elif self.current_language is not None:
            # User explicitly selected a language - simple filter without art-type rules
            filtered = [
                art for art in self.full_artwork_list
                if normalize_language_tag(art.get('language')) == self.current_language
            ]
        else:
            # Initial load - use art-type-aware filtering
            from lib.artwork.utilities import filter_artwork_by_language
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
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Update UI properties and repopulate list without filtering."""
        from lib.artwork.utilities import get_language_display_name

        self.setProperty('count_filtered', str(len(self.available_art)))

        try:
            prefer_fanart_language = KodiSettings.prefer_fanart_language()
        except Exception:
            prefer_fanart_language = False

        is_fanart_no_lang_filter = self.art_type == 'fanart' and not prefer_fanart_language

        if self.current_language == 'all':
            language_display = 'All languages'
        else:
            language_display = get_language_display_name(self.current_language or '')

        if len(self.available_art) != len(self.full_artwork_list):
            if is_fanart_no_lang_filter:
                count_text = f"{len(self.available_art)} of {len(self.full_artwork_list)} available (Text-free)"
            else:
                count_text = f"{len(self.available_art)} of {len(self.full_artwork_list)} available ({language_display})"
        else:
            count_text = f"{len(self.full_artwork_list)} available"
        self.setProperty('count', count_text)
        self.setProperty('language', language_display)
        self.setProperty('language_short', self.current_language or '')

        # Update Change Language button visibility
        show_lang_button = len(self.available_languages) > 1 or len(self.available_art) != len(self.full_artwork_list)
        self.setProperty('show_change_language', 'true' if show_lang_button else 'false')

        self._populate_artwork_list()

    def _switch_language(self, new_language: str) -> None:
        """Refresh list control with new language filter."""
        self.current_language = new_language
        self._resort_artwork()


def show_artwork_selection_dialog(
    title: str,
    art_type: str,
    available_art: List[dict],
    full_artwork_list: Optional[List[dict]] = None,
    media_type: str = '',
    year: str = '',
    current_url: str = '',
    dbid: int = 0,
    test_mode: bool = False,
    review_mode: str = 'missing'
) -> Tuple[str, Optional[dict], Optional[dict]]:
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
        review_mode: Review context ("missing" for missing artwork)

    Returns:
        Tuple of (action, artwork, queued_multiart):
        - ('selected', artwork_dict, queued_multiart) - User selected artwork
        - ('skip', None, queued_multiart) - User skipped this art type
        - ('cancel', None, queued_multiart) - User cancelled review entirely

        queued_multiart is a dict of multi-art assignments or None.
    """
    # Only skip if no artwork at all (not just filtered empty)
    if not available_art and not full_artwork_list:
        return ('skip', None, None)

    addon_path = ADDON.getAddonInfo('path')

    dialog = ArtworkDialogSelect(
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
    queued_multiart = dialog.queued_multiart
    del dialog

    if result == 'selected' and selected_index is not None:
        return ('selected', available_art[selected_index], queued_multiart)
    elif result == 'skip':
        return ('skip', None, queued_multiart)
    else:
        return ('cancel', None, queued_multiart)
