"""Base class for ratings sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict
import hashlib
from datetime import datetime, timedelta
import json

from resources.lib.database._infrastructure import get_db
import xbmcaddon


class DailyLimitReached(Exception):
    """Exception raised when a provider's daily API limit is reached."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Daily API limit reached for {provider}")


class RatingsSource(ABC):
    """Abstract base class for ratings sources."""

    def __init__(self, provider_name: str):
        """
        Initialize ratings source.

        Args:
            provider_name: Name of the provider (e.g., "tmdb", "mdblist", "omdb", "trakt")
        """
        self.provider_name = provider_name
        self.addon = xbmcaddon.Addon()

    @abstractmethod
    def fetch_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from the source.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug, etc.)

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

    def get_cached_ratings(self, media_id: str) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Get cached ratings for a media item.

        Args:
            media_id: Media identifier (IMDB ID, TMDB ID, etc.)

        Returns:
            Cached ratings dict or None if not found/expired
        """
        cache_days = int(self.addon.getSetting("ratings_cache_days") or "3")
        if cache_days == 0:
            return None

        cutoff = (datetime.now() - timedelta(days=cache_days)).isoformat()

        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT data FROM ratings_cache WHERE provider = ? AND media_id = ? AND cached_at > ?",
                (self.provider_name, media_id, cutoff)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["data"])

        return None

    def cache_ratings(self, media_id: str, ratings: Dict[str, Dict[str, float]]) -> None:
        """
        Cache ratings for a media item.

        Args:
            media_id: Media identifier
            ratings: Ratings dictionary to cache
        """
        with get_db() as (conn, cursor):
            cursor.execute(
                """
                INSERT OR REPLACE INTO ratings_cache (provider, media_id, data, cached_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.provider_name, media_id, json.dumps(ratings))
            )

    def get_api_key_hash(self, api_key: str) -> str:
        """
        Generate hash of API key for tracking purposes.

        Args:
            api_key: The API key to hash

        Returns:
            First 16 characters of SHA256 hash
        """
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
