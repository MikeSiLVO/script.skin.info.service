"""Helper classes and utilities for artwork fetching.

Provides OrderedSet for multi-selection tracking and quality comparison functions.
"""
from __future__ import annotations

from typing import Any, List, Optional
import xbmcaddon

from resources.lib.utils import get_preferred_language_code, normalize_language_tag


class OrderedSet:
    """
    Maintains insertion order for multi-selection.
    Used for tracking multi-art selection order (fanart1, fanart2, poster1, poster2, etc.)
    """

    def __init__(self):
        self._dict: dict[Any, None] = {}

    def add(self, item: Any) -> None:
        """Add item to the end if not already present."""
        if item not in self._dict:
            self._dict[item] = None

    def remove(self, item: Any) -> None:
        """Remove item while maintaining order of remaining items."""
        self._dict.pop(item, None)

    def toggle(self, item: Any) -> None:
        """Toggle item presence (add if not present, remove if present)."""
        if item in self._dict:
            self.remove(item)
        else:
            self.add(item)

    def clear(self) -> None:
        """Remove all items."""
        self._dict.clear()

    def get_ordered(self) -> List[Any]:
        """Return items in insertion order."""
        return list(self._dict.keys())

    def get_order(self, item: Any) -> int:
        """
        Get 1-based position of item in selection order.

        Returns:
            Position (1-based) or 0 if item not in set
        """
        try:
            return list(self._dict.keys()).index(item) + 1
        except ValueError:
            return 0

    def __contains__(self, item: Any) -> bool:
        """Check if item is in the set."""
        return item in self._dict

    def __len__(self) -> int:
        """Return number of items."""
        return len(self._dict)

    def __iter__(self):
        """Iterate over items in order."""
        return iter(self._dict)


def compare_art_quality(art_list: List[dict]) -> Optional[dict]:
    """
    Find highest quality artwork from list based on resolution.

    Args:
        art_list: List of art dicts with optional 'width' and 'height' keys

    Returns:
        Best quality art dict or None if list is empty
    """
    if not art_list:
        return None

    if len(art_list) == 1:
        return art_list[0]

    def get_pixel_count(art: dict) -> int:
        width = int(art.get('width', 0) or 0)
        height = int(art.get('height', 0) or 0)
        return width * height

    return max(art_list, key=get_pixel_count)


def sort_artwork_by_popularity(art_list: List[dict], art_type: str = '') -> List[dict]:
    """
    Sort artwork by quality and popularity.

    Sorting priority:
    - For fanart: Language preference only if prefer_fanart_language setting is enabled (default: off)
    - For other art types: Language preference with 3 tiers:
      1. Preferred language (from settings)
      2. Empty/no language (likely text-free or untagged - still usable)
      3. Other languages
    - Then: Resolution (pixel count) - highest first
    - Finally: Popularity (TMDB rating or fanart.tv likes) - highest first

    Args:
        art_list: List of art dicts with optional width, height, rating, likes, language
        art_type: Type of artwork being sorted (e.g., 'fanart', 'poster', 'clearlogo')

    Returns:
        Sorted list (original list is not modified)
    """
    if not art_list or len(art_list) <= 1:
        return art_list

    try:
        addon = xbmcaddon.Addon()
        preferred_lang = get_preferred_language_code()
        prefer_fanart_language = addon.getSettingBool("prefer_fanart_language")
    except Exception:
        preferred_lang = get_preferred_language_code()
        prefer_fanart_language = False

    use_language_preference = True
    if art_type == 'fanart' and not prefer_fanart_language:
        use_language_preference = False

    def get_sort_key(art: dict) -> tuple:
        # Primary: language match (preferred language first) - only if enabled for this art type
        if use_language_preference:
            language = normalize_language_tag(art.get('language'))
            if language == preferred_lang:
                lang_match = 0  # Preferred language first
            elif language == '':
                lang_match = 1  # Empty/no language second (likely text-free or untagged)
            else:
                lang_match = 2  # Other languages last
        else:
            lang_match = 0  # All items equal in language priority (no language preference applied)

        # Secondary: pixel count (higher is better)
        width = int(art.get('width', 0) or 0)
        height = int(art.get('height', 0) or 0)
        pixels = width * height

        # Tertiary: popularity (TMDB rating or fanart.tv likes)
        # TMDB rating: 0-10 float
        # fanart.tv likes: string number (e.g., "123")
        rating = float(art.get('rating', 0) or 0)
        likes = int(art.get('likes', '0') or '0')
        popularity = rating if rating > 0 else likes

        return (lang_match, -pixels, -popularity)

    return sorted(art_list, key=get_sort_key)


def get_available_languages(artwork_list: List[dict]) -> List[str]:
    """
    Extract unique language codes from artwork list.

    Args:
        artwork_list: List of artwork dicts with optional 'language' key

    Returns:
        Sorted list of unique language codes, with empty string (text-free) first if present
    """
    if not artwork_list:
        return []

    languages = set()
    for art in artwork_list:
        lang = normalize_language_tag(art.get('language'))
        languages.add(lang)

    result = sorted(languages)

    if '' in result:
        result.remove('')
        result.insert(0, '')

    return result


def filter_artwork_by_language(
    artwork_list: List[dict],
    art_type: Optional[str] = None,
    language_code: Optional[str] = None,
    include_no_language: bool = True
) -> List[dict]:
    """
    Filter artwork based on art type rules and language preferences.

    Art type filtering rules:
    - AUTO_NO_LANGUAGE_TYPES (fanart, keyart): Only text-free items (unless prefer_fanart_language=True)
    - AUTO_LANG_REQUIRED_TYPES (poster, clearlogo, etc.): Preferred language + text-free, fallback to all
    - Other types or manual language_code: Filter to specified language

    Args:
        artwork_list: List of artwork dicts with optional 'language' key
        art_type: Art type (poster, fanart, etc.) - enables art-type-aware filtering
        language_code: Language code to filter by (None = use preferred language)
        include_no_language: Whether to include items without language tags (text-free)

    Returns:
        Filtered list based on art type rules or language preference
    """
    if not artwork_list:
        return []

    from resources.lib.artwork.helpers import AUTO_LANG_REQUIRED_TYPES, AUTO_NO_LANGUAGE_TYPES

    try:
        addon = xbmcaddon.Addon()
        prefer_fanart_language = addon.getSettingBool("prefer_fanart_language")
    except Exception:
        prefer_fanart_language = False

    if art_type == 'fanart' and prefer_fanart_language:
        pass
    elif art_type in AUTO_NO_LANGUAGE_TYPES:
        return [art for art in artwork_list if not normalize_language_tag(art.get('language'))]

    if language_code is None:
        language_code = get_preferred_language_code()

    filter_code = normalize_language_tag(language_code)

    if art_type in AUTO_LANG_REQUIRED_TYPES and filter_code:
        filtered = []
        for art in artwork_list:
            art_lang = normalize_language_tag(art.get('language'))
            if art_lang == filter_code or art_lang == '':
                filtered.append(art)
        return filtered if filtered else artwork_list

    if art_type == 'fanart' and prefer_fanart_language and filter_code:
        filtered = []
        for art in artwork_list:
            art_lang = normalize_language_tag(art.get('language'))
            if art_lang == filter_code or art_lang == '':
                filtered.append(art)
        return filtered if filtered else artwork_list

    filtered = []
    for art in artwork_list:
        art_lang = normalize_language_tag(art.get('language'))
        if art_lang == filter_code:
            filtered.append(art)
        elif include_no_language and art_lang == '':
            filtered.append(art)

    return filtered


def get_language_display_name(language_code: str) -> str:
    """
    Get human-readable display name for ISO 639-1 language code.

    Args:
        language_code: ISO 639-1 language code (e.g., 'en', 'es')

    Returns:
        Display name (e.g., 'English', 'Spanish') or localized 'Text-free / Untagged' for empty code
    """
    if not language_code or language_code == '':
        return xbmcaddon.Addon().getLocalizedString(32122)

    language_names = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'nl': 'Dutch',
        'sv': 'Swedish',
        'no': 'Norwegian',
        'da': 'Danish',
        'fi': 'Finnish',
        'pl': 'Polish',
        'tr': 'Turkish',
        'el': 'Greek',
        'he': 'Hebrew',
        'th': 'Thai',
        'cs': 'Czech',
        'hu': 'Hungarian',
        'ro': 'Romanian',
        'uk': 'Ukrainian',
        'id': 'Indonesian',
        'vi': 'Vietnamese',
        'ca': 'Catalan',
        'hr': 'Croatian',
        'sr': 'Serbian',
        'sk': 'Slovak',
        'bg': 'Bulgarian',
        'lt': 'Lithuanian',
        'lv': 'Latvian',
        'et': 'Estonian',
        'sl': 'Slovenian',
        'ms': 'Malay',
    }

    return language_names.get(language_code, language_code.upper())


def build_art_slot_name(index: int) -> str:
    """
    Build art slot name from index.

    Args:
        index: 0-based index

    Returns:
        'fanart' for index 0, 'fanart1' for index 1, etc.
    """
    return 'fanart' if index == 0 else f'fanart{index}'


def parse_art_slot_index(slot_name: str) -> int:
    """
    Parse index from art slot name.

    Args:
        slot_name: 'fanart', 'fanart1', 'fanart2', etc.

    Returns:
        0-based index (-1 if not a fanart slot)
    """
    if slot_name == 'fanart':
        return 0
    elif slot_name.startswith('fanart'):
        try:
            return int(slot_name[6:])  # Extract number after 'fanart'
        except (ValueError, IndexError):
            return -1
    return -1
