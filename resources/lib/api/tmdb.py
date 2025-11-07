"""TMDB API client for artwork and ratings.

Provides:
- Movie/TV show artwork (posters, backdrops, logos)
- Movie/TV show/episode ratings
- Rate limit: 39 requests per 10 seconds (TMDB allows 40)
"""
from __future__ import annotations

import xbmc
import xbmcaddon
from typing import Optional, Dict, List

from resources.lib.api.http_client import create_rate_limited_client
from resources.lib.ratings.source import RatingsSource
from resources.lib.ratings import usage_tracker

ADDON = xbmcaddon.Addon()


class TMDBApi(RatingsSource):
    """TMDB API client with rate limiting for artwork and ratings."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/original"

    API_KEY = None

    MAX_REQUESTS_PER_WINDOW = 39
    RATE_LIMIT_WINDOW = 10.0

    def __init__(self):
        super().__init__("tmdb")
        self.http_client = create_rate_limited_client(
            "TMDB",
            self.MAX_REQUESTS_PER_WINDOW,
            self.RATE_LIMIT_WINDOW
        )

    def get_api_key(self) -> Optional[str]:
        """
        Get TMDB API key with priority order:
        1. User's key from addon settings
        2. Built-in key from API_KEY constant
        3. Keys from other Kodi addons (scrapers)

        Returns:
            API key or None if not configured
        """
        user_key = ADDON.getSetting("tmdb_api_key").strip()
        if user_key:
            return user_key

        if self.API_KEY:
            return self.API_KEY.strip()

        try:
            scraper = xbmcaddon.Addon('metadata.tvshows.themoviedb.python')
            api_key = scraper.getSetting('tmdbApiKey')
            if api_key:
                return api_key
        except Exception:
            pass

        try:
            scraper = xbmcaddon.Addon('metadata.themoviedb.org')
            api_key = scraper.getSetting('tmdbApiKey')
            if api_key:
                return api_key
        except Exception:
            pass

        xbmc.log("SkinInfo TMDB: No API key found. Please configure in addon settings.", xbmc.LOGWARNING)
        return None

    def _make_request(self, url: str, api_key: str) -> Optional[dict]:
        """
        Make HTTP request to TMDB API with rate limiting and retry on 429.

        Args:
            url: Full API URL
            api_key: TMDB API key

        Returns:
            JSON response or None on error
        """
        separator = '&' if '?' in url else '?'
        full_url = f"{url}{separator}api_key={api_key}"

        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Kodi/script.skin.info.service'
        }

        return self.http_client.make_request(full_url, headers, max_retries=3, base_backoff=2)

    # Artwork methods

    def get_movie_images(self, tmdb_id: int) -> dict:
        """Get all available images for a movie from TMDB."""
        return self._fetch_images('movie', tmdb_id)

    def get_tv_images(self, tmdb_id: int) -> dict:
        """Get all available images for a TV show from TMDB."""
        return self._fetch_images('tv', tmdb_id)

    def get_season_images(self, tmdb_id: int, season_number: int) -> dict:
        """
        Get all available images for a TV season from TMDB.

        Args:
            tmdb_id: TMDB TV show ID
            season_number: Season number

        Returns:
            Dict with artwork by type: {'poster': [...]}
        """
        api_key = self.get_api_key()
        if not api_key:
            return {}

        url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}/images"
        data = self._make_request(url, api_key)

        if not data:
            return {}

        return self._transform_images(data)

    def get_episode_images(self, tmdb_id: int, season_number: int, episode_number: int) -> dict:
        """
        Get all available images for a TV episode from TMDB.

        Args:
            tmdb_id: TMDB TV show ID
            season_number: Season number
            episode_number: Episode number

        Returns:
            Dict with artwork by type: {'thumb': [...]}
        """
        api_key = self.get_api_key()
        if not api_key:
            return {}

        url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/images"
        data = self._make_request(url, api_key)

        if not data:
            return {}

        stills = data.get('stills', [])
        result = {}
        if stills:
            result['thumb'] = [self._format_image(img, 'w300') for img in stills if self._format_image(img, 'w300')]

        return result

    def _fetch_images(self, media_kind: str, tmdb_id: int) -> dict:
        """Fetch images from TMDB API."""
        api_key = self.get_api_key()
        if not api_key:
            return {}

        url = f"{self.BASE_URL}/{media_kind}/{tmdb_id}/images"
        data = self._make_request(url, api_key)

        if not data:
            return {}

        return self._transform_images(data)

    def _transform_images(self, data: dict) -> dict:
        """Transform TMDB image response to common format."""
        result: Dict[str, List[dict]] = {}

        mapping = (
            ('posters', 'poster', 'w500'),
            ('backdrops', 'fanart', 'w780'),
            ('logos', 'clearlogo', 'w500'),
        )

        for source_key, result_key, preview_size in mapping:
            entries = data.get(source_key) or []
            formatted = [self._format_image(entry, preview_size) for entry in entries]
            formatted = [entry for entry in formatted if entry]
            if formatted:
                result[result_key] = formatted

        return result

    def _format_image(self, image: dict, preview_size: str) -> Optional[dict]:
        """Format TMDB image entry to common format."""
        file_path = image.get('file_path')
        if not file_path:
            return None

        return {
            'url': f"{self.IMAGE_BASE}{file_path}",
            'previewurl': f"https://image.tmdb.org/t/p/{preview_size}{file_path}",
            'width': image.get('width', 0),
            'height': image.get('height', 0),
            'rating': image.get('vote_average', 0),
            'language': image.get('iso_639_1', ''),
            'source': 'TMDB'
        }

    # Ratings methods

    def fetch_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from TMDB.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (must contain "tmdb")

        Returns:
            Dictionary with TMDB ratings:
            {"themoviedb": {"rating": 8.3, "votes": 12500}}
        """
        api_key = self.get_api_key()
        if not api_key:
            return None

        if usage_tracker.is_provider_skipped("tmdb"):
            return None

        tmdb_id = ids.get("tmdb")
        if not tmdb_id:
            return None

        cached = self.get_cached_ratings(tmdb_id)
        if cached:
            return cached

        try:
            count, hit_before = usage_tracker.increment_usage("tmdb")

            if media_type == "movie":
                url = f"{self.BASE_URL}/movie/{tmdb_id}?api_key={api_key}"
            elif media_type == "tvshow":
                url = f"{self.BASE_URL}/tv/{tmdb_id}?api_key={api_key}"
            elif media_type == "episode":
                season = ids.get("season")
                episode = ids.get("episode")
                if not season or not episode:
                    return None
                url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season}/episode/{episode}?api_key={api_key}"
            else:
                return None

            details = self.http_client.make_request(url, headers={
                'Accept': 'application/json',
                'User-Agent': 'Kodi/script.skin.info.service'
            })

            if not details:
                return None

            rating = details.get("vote_average")
            votes = details.get("vote_count")

            if rating is None or votes is None:
                return None

            result = {
                "themoviedb": {
                    "rating": self.normalize_rating(rating, 10),
                    "votes": float(votes)
                },
                "_source": "tmdb"
            }

            self.cache_ratings(tmdb_id, result)
            return result

        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: TMDB fetch error: {str(e)}", xbmc.LOGWARNING)
            return None

    def test_connection(self) -> bool:
        """
        Test TMDB API connection.

        Returns:
            True if connection successful
        """
        api_key = self.get_api_key()
        if not api_key:
            return False

        try:
            url = f"{self.BASE_URL}/movie/550?api_key={api_key}"
            details = self.http_client.make_request(url, headers={
                'Accept': 'application/json',
                'User-Agent': 'Kodi/script.skin.info.service'
            })
            return details is not None
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: TMDB test connection error: {str(e)}", xbmc.LOGWARNING)
            return False

    @staticmethod
    def get_attribution() -> str:
        """Get required TMDB attribution text."""
        return "This product uses the TMDB API but is not endorsed or certified by TMDB."
