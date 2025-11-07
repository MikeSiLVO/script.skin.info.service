"""Base class for ratings sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict
import hashlib
from datetime import datetime, timedelta
import json
import zlib

from lib.data.database._infrastructure import get_db
from lib.kodi.settings import KodiSettings


def _compress_data(data: dict) -> bytes:
    """Compress JSON data using zlib."""
    json_str = json.dumps(data, separators=(',', ':'))
    return zlib.compress(json_str.encode('utf-8'), level=6)


def _decompress_data(data: bytes) -> dict:
    """Decompress zlib-compressed JSON data."""
    json_str = zlib.decompress(data).decode('utf-8')
    return json.loads(json_str)


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

        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT data FROM provider_cache WHERE provider = ? AND media_id = ? AND cached_at > ?",
                (self.provider_name, media_id, cutoff)
            )
            row = cursor.fetchone()
            if row:
                return _decompress_data(row["data"])

        return None

    def cache_data(self, media_id: str, data: dict, release_date: Optional[str] = None) -> None:
        """
        Cache provider data for a media item.

        Args:
            media_id: Media identifier
            data: Full provider response data to cache
            release_date: Optional YYYY-MM-DD release date for TTL calculation
        """
        with get_db() as (conn, cursor):
            cursor.execute(
                """
                INSERT OR REPLACE INTO provider_cache (provider, media_id, data, release_date, cached_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.provider_name, media_id, _compress_data(data), release_date)
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
