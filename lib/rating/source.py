"""Base class for ratings sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict
import hashlib
from datetime import datetime, timedelta

from lib.data.database.rating import get_provider_cache, save_provider_cache
from lib.kodi.settings import KodiSettings


class RateLimitHit(Exception):
    """Exception raised when a provider's API rate limit is reached."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Rate limit reached for {provider}")


class RetryableError(Exception):
    """Exception raised for transient errors that may succeed on retry (timeouts, connection errors)."""
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider}: {reason}")


class RatingSource(ABC):
    """Abstract base class for ratings sources."""

    def __init__(self, provider_name: str):
        """
        Initialize ratings source.

        Args:
            provider_name: Name of the provider (e.g., "tmdb", "mdblist", "omdb", "trakt")
        """
        self.provider_name = provider_name
        self.addon = KodiSettings._get_addon()

    @abstractmethod
    def fetch_ratings(
        self,
        media_type: str,
        ids: Dict[str, str],
        abort_flag=None,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from the source.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug, etc.)
            abort_flag: Optional abort flag for cancellation
            force_refresh: If True, bypass cache read but still write to cache

        Returns:
            Dictionary mapping source names to rating/votes dicts, e.g.:
            {
                "tmdb": {"rating": 8.3, "votes": 12500},
                "imdb": {"rating": 8.5, "votes": 850000}
            }
            None if no ratings found or error occurred
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to the API.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    def normalize_rating(self, value: float, scale_max: int) -> float:
        """
        Normalize rating to 0-10 scale.

        Args:
            value: Rating value
            scale_max: Maximum value of the scale (10, 100, 5, 4)

        Returns:
            Normalized rating on 0-10 scale
        """
        if scale_max == 10:
            return round(float(value), 1)
        return round(float(value) / float(scale_max) * 10.0, 1)

    def get_cached_data(self, media_id: str) -> Optional[dict]:
        """
        Get cached provider data for a media item.

        Args:
            media_id: Media identifier (IMDB ID, TMDB ID, etc.)

        Returns:
            Cached provider data dict or None if not found/expired
        """
        cache_days = KodiSettings.provider_cache_days()
        if cache_days == 0:
            return None

        cutoff = (datetime.now() - timedelta(days=cache_days)).isoformat()
        return get_provider_cache(self.provider_name, media_id, cutoff)

    def cache_data(self, media_id: str, data: dict, release_date: Optional[str] = None) -> None:
        """
        Cache provider data for a media item.

        Args:
            media_id: Media identifier
            data: Full provider response data to cache
            release_date: Optional YYYY-MM-DD release date for TTL calculation
        """
        save_provider_cache(self.provider_name, media_id, data, release_date)

    def get_api_key_hash(self, api_key: str) -> str:
        """
        Generate hash of API key for tracking purposes.

        Args:
            api_key: The API key to hash

        Returns:
            First 16 characters of SHA256 hash
        """
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
