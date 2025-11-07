"""Fanart.tv API client for artwork.

Provides:
- Movie artwork (clearlogos, clearart, banners, discart, etc.)
- TV show artwork (clearlogos, clearart, banners, characterart, etc.)
- Rate limit: 39 requests per 10 seconds
"""
from __future__ import annotations

import xbmc
import xbmcaddon
from typing import Optional

from resources.lib.api.http_client import create_rate_limited_client

ADDON = xbmcaddon.Addon()


class FanartTVApi:
    """Fanart.tv API client with rate limiting."""

    BASE_URL = "https://webservice.fanart.tv/v3"

    API_KEY = None

    MAX_REQUESTS_PER_WINDOW = 39
    RATE_LIMIT_WINDOW = 10.0

    def __init__(self):
        self.http_client = create_rate_limited_client(
            "fanart.tv",
            self.MAX_REQUESTS_PER_WINDOW,
            self.RATE_LIMIT_WINDOW
        )

    def get_api_key(self) -> Optional[str]:
        """
        Get fanart.tv API key with priority order:
        1. User's key from addon settings
        2. Built-in key from API_KEY constant
        3. Keys from other Kodi addons

        Returns:
            API key or None if not configured
        """
        user_key = ADDON.getSetting("fanarttv_api_key").strip()
        if user_key:
            return user_key

        if self.API_KEY:
            return self.API_KEY.strip()

        try:
            scraper = xbmcaddon.Addon('script.artwork.downloader')
            api_key = scraper.getSetting('fanarttv_personal_apikey')
            if api_key:
                return api_key
        except Exception:
            pass

        xbmc.log("SkinInfo fanart.tv: No API key found. Using public access (limited).", xbmc.LOGWARNING)
        return None

    def _make_request(self, url: str, api_key: Optional[str] = None) -> Optional[dict]:
        """
        Make HTTP request to fanart.tv API with rate limiting and retry on 429.

        Args:
            url: Full API URL
            api_key: fanart.tv API key (optional, but recommended)

        Returns:
            JSON response or None on error
        """
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Kodi/script.skin.info.service'
        }

        if api_key:
            headers['api-key'] = api_key

        return self.http_client.make_request(url, headers, max_retries=5, base_backoff=3)

    def get_movie_artwork(self, tmdb_id: int) -> dict:
        """
        Get all available artwork for a movie from fanart.tv.

        Args:
            tmdb_id: TMDB movie ID

        Returns:
            Dict with artwork by type
        """
        api_key = self.get_api_key()

        url = f"{self.BASE_URL}/movies/{tmdb_id}"
        data = self._make_request(url, api_key)

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

    def get_tv_artwork(self, tvdb_id: int) -> dict:
        """
        Get all available artwork for a TV show from fanart.tv.

        Args:
            tvdb_id: TVDB show ID (fanart.tv uses TVDB IDs for TV shows)

        Returns:
            Dict with artwork by type
        """
        api_key = self.get_api_key()

        url = f"{self.BASE_URL}/tv/{tvdb_id}"
        data = self._make_request(url, api_key)

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
            'showbackground': (1920, 1080),
            'showbackground4k': (3840, 2160),
            'hdtvlogo': (800, 310),
            'clearlogo': (400, 155),
            'hdclearart': (1000, 562),
            'clearart': (1000, 562),
            'tvbanner': (1000, 185),
            'tvthumb': (1000, 562),
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
