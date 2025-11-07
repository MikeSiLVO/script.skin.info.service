"""Skinner helper tools for testing dialogs.

This module provides utilities for skin developers to:
- Preview dialogs with mock data
- Test dialog layouts and functionality

Usage:
    RunScript(script.skin.info.service,arttest)              # Shows menu to select art type
    RunScript(script.skin.info.service,arttest,poster)       # Directly opens poster dialog
    RunScript(script.skin.info.service,multiarttest)         # Shows menu to select art type
    RunScript(script.skin.info.service,multiarttest,fanart)  # Directly opens fanart dialog
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import xbmcgui

# Art types available for testing
_ART_TYPES = [
    'poster',
    'fanart',
    'clearlogo',
    'clearart',
    'landscape',
    'banner',
    'characterart',
    'discart',
    'keyart',
    'thumb',
]


def _select_art_type_menu(dialog_type: str, preselect: int = 0) -> tuple[Optional[str], int]:
    """
    Show menu to select art type for testing.

    Args:
        dialog_type: Type of dialog being tested ('artwork' or 'multiart')
        preselect: Index of item to preselect in menu

    Returns:
        Tuple of (selected art type or None if cancelled, selected index)
    """

    dialog = xbmcgui.Dialog()
    art_labels = [art.capitalize() for art in _ART_TYPES]

    selected = dialog.select(
        f'Select Art Type for {dialog_type.capitalize()} Dialog Test',
        art_labels,
        preselect=preselect
    )

    if selected < 0:
        return None, -1

    return _ART_TYPES[selected], selected


def test_artwork_selection_dialog(art_type: Optional[str] = None) -> None:
    """
    Show artwork selection dialog with mock data for skinner testing.

    Args:
        art_type: Art type to test ('poster', 'fanart', 'clearlogo', etc.)
                  If None, shows menu to select art type and loops back after each test
    """
    from lib.artwork.dialogs.select import show_artwork_selection_dialog
    from lib.kodi.client import log

    show_menu = art_type is None
    last_selected_index = 0

    while True:
        if show_menu:
            art_type, last_selected_index = _select_art_type_menu('artwork', last_selected_index)
            if art_type is None:
                return

        if art_type is None:
            return

        log("General", f"Skinner Test: Opening artwork selection dialog for art_type={art_type}")

        mock_art_items = _generate_mock_art_items(art_type, count=12)

        result = show_artwork_selection_dialog(
            title='Test Movie (2024)',
            art_type=art_type,
            available_art=mock_art_items,
            media_type='movie',
            year='2024',
            current_url='https://image.tmdb.org/t/p/original/current_artwork.jpg',
            dbid=1,
            test_mode=True
        )

        log("General", f"Skinner Test: Dialog result = {result}")

        if not show_menu:
            return


def test_multiart_dialog(art_type: Optional[str] = None) -> None:
    """
    Show multi-art selection dialog with mock data for skinner testing.

    Args:
        art_type: Art type to test ('fanart', 'poster', 'clearlogo', etc.)
                  If None, shows menu to select art type and loops back after each test
    """
    from lib.artwork.dialogs.multi import show_multiart_dialog
    from lib.kodi.client import log

    show_menu = art_type is None
    last_selected_index = 0

    while True:
        if show_menu:
            art_type, last_selected_index = _select_art_type_menu('multiart', last_selected_index)
            if art_type is None:
                return

        if art_type is None:
            return

        log("General", f"Skinner Test: Opening multi-art dialog for art_type={art_type}")

        result = show_multiart_dialog(
            media_type='movie',
            dbid=1,
            title='Test Movie (2024)',
            art_type=art_type,
            test_mode=True
        )

        log("General", f"Skinner Test: Multi-art dialog result = {result}")

        if not show_menu:
            return


def _generate_mock_art_items(art_type: str, count: int = 12) -> List[Dict[str, Any]]:
    """
    Generate mock art items for dialog testing.

    Args:
        art_type: Art type to generate
        count: Number of mock items to generate

    Returns:
        List of mock art item dictionaries
    """
    import xbmcvfs

    # Map art types to test images and dimensions
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

    image_file, dimensions = art_type_map.get(art_type.lower(), ('artwork_test_poster.png', (1000, 1500)))
    test_image = xbmcvfs.translatePath(f'special://home/addons/script.skin.info.service/resources/media/artwork_test/{image_file}')

    mock_items = []

    sources = ['tmdb', 'fanarttv', 'tmdb', 'fanarttv']
    languages = ['en', 'en', 'es', 'fr', 'de', None, None, None]

    for i in range(count):
        source = sources[i % len(sources)]
        language = languages[i % len(languages)]

        item = {
            'url': test_image,
            'preview_url': test_image,
            'previewurl': test_image,
            'source': source,
            'rating': 8.5 - (i * 0.3),
            'votes': 1000 - (i * 50),
            'language': language,
            'width': dimensions[0],
            'height': dimensions[1],
        }

        if art_type.lower() in ('clearlogo', 'clearart', 'banner'):
            item['language'] = language

        mock_items.append(item)

    return mock_items
