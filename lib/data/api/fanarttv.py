"""Fanart.tv API client for artwork.

Provides:
- Movie artwork (clearlogos, clearart, banners, discart, etc.)
- TV show artwork (clearlogos, clearart, banners, characterart, etc.)
"""
from __future__ import annotations

from typing import Optional

from lib.data.api.client import ApiSession
from lib.kodi.settings import KodiSettings


class ApiFanarttv:
    """Fanart.tv API client with rate limiting."""

    BASE_URL = "https://webservice.fanart.tv/v3"

    API_KEY = None

    def __init__(self):
        self.session = ApiSession(
            service_name="Fanart.tv",
            base_url=self.BASE_URL,
            timeout=(5.0, 15.0),
            max_retries=3,
            backoff_factor=1.0,
            rate_limit=(10, 1.0),
            default_headers={
                "Accept": "application/json"
            }
        )

    def get_api_key(self) -> Optional[str]:
        """
        Get fanart.tv API key with priority order:
        1. User's key from addon settings
        2. Built-in key from API_KEY constant

        Returns:
            API key or None if not configured
        """
        user_key = KodiSettings.fanarttv_api_key()
        if user_key:
            return user_key

        if self.API_KEY:
            return self.API_KEY.strip()

        return None

    def _make_request(self, endpoint: str, abort_flag=None) -> Optional[dict]:
        """
        Make HTTP request to fanart.tv API with rate limiting and retry.

        Args:
            endpoint: API endpoint (relative to BASE_URL)
            abort_flag: Optional abort flag for cancellation

        Returns:
            JSON response or None on error
        """
        api_key = self.get_api_key()
        headers = {"api-key": api_key} if api_key else None

        return self.session.get(
            endpoint,
            headers=headers,
            abort_flag=abort_flag
        )

    def get_movie_artwork(self, tmdb_id: int, abort_flag=None) -> dict:
        """
        Get all available artwork for a movie from fanart.tv.

        Args:
            tmdb_id: TMDB movie ID
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dict with artwork by type
        """
        data = self._make_request(f"/movies/{tmdb_id}", abort_flag)

        if not data:
            return {}

        result = {}

        type_map = {
            'movieposter': 'poster',
            'moviebackground': 'fanart',
            'moviebackground4k': 'fanart',
            'hdmovielogo': 'clearlogo',
            'movielogo': 'clearlogo',
            'hdmovieclearart': 'clearart',
            'movieclearart': 'clearart',
            'moviebanner': 'banner',
            'moviedisc': 'discart',
            'moviethumb': 'landscape'
        }

        dimensions_map = {
            'movieposter': (1000, 1426),
            'moviebackground': (1920, 1080),
            'moviebackground4k': (3840, 2160),
            'hdmovielogo': (800, 310),
            'movielogo': (400, 155),
            'hdmovieclearart': (1000, 562),
            'movieclearart': (1000, 562),
            'moviebanner': (1000, 185),
            'moviedisc': (1000, 1000),
            'moviethumb': (1000, 562)
        }

        for fanart_type, kodi_type in type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    full_url = item.get('url', '')

                    if fanart_type == 'moviebanner':
                        preview = full_url
                    else:
                        preview = item.get('url_thumb') or full_url.replace('/fanart/', '/preview/')

                    artwork = {
                        'url': full_url,
                        'previewurl': preview,
                        'language': item.get('lang', ''),
                        'likes': item.get('likes', '0'),
                        'id': item.get('id', ''),
                        'source': 'fanart.tv'
                    }

                    if fanart_type in dimensions_map:
                        artwork['width'], artwork['height'] = dimensions_map[fanart_type]

                    result[kodi_type].append(artwork)

        return result

    def get_tv_artwork(self, tvdb_id: int, abort_flag=None) -> dict:
        """
        Get all available artwork for a TV show from fanart.tv.

        Args:
            tvdb_id: TVDB show ID (fanart.tv uses TVDB IDs for TV shows)
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dict with artwork by type
        """
        data = self._make_request(f"/tv/{tvdb_id}", abort_flag)

        if not data:
            return {}

        result = {}

        type_map = {
            'tvposter': 'poster',
            'showbackground': 'fanart',
            'showbackground4k': 'fanart',
            'hdtvlogo': 'clearlogo',
            'clearlogo': 'clearlogo',
            'hdclearart': 'clearart',
            'clearart': 'clearart',
            'tvbanner': 'banner',
            'tvthumb': 'landscape',
            'characterart': 'characterart',
            'seasonposter': 'poster',
            'seasonbanner': 'banner',
            'seasonthumb': 'landscape'
        }

        dimensions_map = {
            'tvposter': (1000, 1426),
            'showbackground': (1920, 1080),
            'showbackground4k': (3840, 2160),
            'hdtvlogo': (800, 310),
            'clearlogo': (400, 155),
            'hdclearart': (1000, 562),
            'clearart': (1000, 562),
            'tvbanner': (1000, 185),
            'tvthumb': (1000, 562),
            'characterart': (1000, 1399),
            'seasonposter': (1000, 1426),
            'seasonbanner': (1000, 185),
            'seasonthumb': (1000, 562)
        }

        for fanart_type, kodi_type in type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    full_url = item.get('url', '')

                    if fanart_type in ('tvbanner', 'seasonbanner'):
                        preview = full_url
                    else:
                        preview = item.get('url_thumb') or full_url.replace('/fanart/', '/preview/')

                    artwork = {
                        'url': full_url,
                        'previewurl': preview,
                        'language': item.get('lang', ''),
                        'likes': item.get('likes', '0'),
                        'id': item.get('id', ''),
                        'season': item.get('season', ''),
                        'source': 'fanart.tv'
                    }

                    if fanart_type in dimensions_map:
                        artwork['width'], artwork['height'] = dimensions_map[fanart_type]

                    result[kodi_type].append(artwork)

        return result

    @staticmethod
    def get_attribution() -> str:
        """Get required fanart.tv attribution text."""
        return "Artwork provided by fanart.tv"
