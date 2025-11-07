"""MDBList ratings source."""
from __future__ import annotations

from typing import Optional, Dict
import json
import xbmc
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

from resources.lib.ratings.source import RatingsSource, DailyLimitReached
from resources.lib.ratings import usage_tracker
from resources.lib.kodi import _get_api_key


class MDBListRatingsSource(RatingsSource):
    """MDBList ratings source implementation."""

    BASE_URL = "https://api.mdblist.com"

    def __init__(self):
        super().__init__("mdblist")
        self.api_key = _get_api_key("mdblist_api_key")

    def fetch_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from MDBList.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (prefers "tmdb", falls back to "imdb")

        Returns:
            Dictionary with multiple source ratings:
            {
                "imdb": {"rating": 8.5, "votes": 750000},
                "themoviedb": {"rating": 8.3, "votes": 12000},
                "trakt": {"rating": 8.4, "votes": 5000},
                "metacritic": {"rating": 8.5, "votes": 45},
                "letterboxd": {"rating": 8.4, "votes": 15000},
                "tomatometerallcritics": {"rating": 9.7, "votes": 102},
                "tomatometerallaudience": {"rating": 8.5, "votes": 1000},
                "rogerebert": {"rating": 8.8, "votes": 2}
            }

        Note:
            MDBList API returns ratings with both 'value' (original scale) and 'score' (normalized).
            We use 'value' to maintain the original rating scales:
            - imdb, tmdb, trakt: 0-10
            - metacritic, tomatoes: 0-100
            - letterboxd: 0-5
            - rogerebert: 0-4
        """
        if not self.api_key:
            return None

        if usage_tracker.is_provider_skipped("mdblist"):
            return None

        if media_type == "episode":
            return None

        # Prefer TMDB ID, fall back to IMDb ID
        media_id = ids.get("tmdb")
        if media_id:
            provider = "tmdb"
            cache_key = f"tmdb_{media_id}"
        else:
            media_id = ids.get("imdb")
            if not media_id:
                return None
            provider = "imdb"
            cache_key = media_id

        cached = self.get_cached_ratings(cache_key)
        if cached:
            return cached

        try:
            usage_tracker.increment_usage("mdblist")

            endpoint_type = "show" if media_type == "tvshow" else "movie"
            url = f"{self.BASE_URL}/{provider}/{endpoint_type}/{media_id}?{urlencode({'apikey': self.api_key})}"

            req = Request(url)
            req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            try:
                with urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except HTTPError as e:
                if e.code == 429:
                    raise DailyLimitReached("mdblist")
                xbmc.log(f"SkinInfo [Ratings]: MDBList returned {e.code}", xbmc.LOGWARNING)
                return None

            result = {}

            ratings_data = data.get("ratings", [])
            if isinstance(ratings_data, list):
                for rating_entry in ratings_data:
                    if not isinstance(rating_entry, dict):
                        continue

                    source = rating_entry.get("source", "").lower()
                    rating = rating_entry.get("value")
                    votes = rating_entry.get("votes") or rating_entry.get("vote_count")

                    if not source or rating is None:
                        continue

                    if source == "imdb":
                        result["imdb"] = {
                            "rating": self.normalize_rating(rating, 10),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "tmdb" or source == "themoviedb":
                        result["themoviedb"] = {
                            "rating": self.normalize_rating(rating, 100),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "trakt":
                        result["trakt"] = {
                            "rating": self.normalize_rating(rating, 100),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "metacritic":
                        result["metacritic"] = {
                            "rating": self.normalize_rating(rating, 100),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "letterboxd":
                        result["letterboxd"] = {
                            "rating": self.normalize_rating(rating, 5),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "tomatoes" or source == "rottentomatoes":
                        result["tomatometerallcritics"] = {
                            "rating": self.normalize_rating(rating, 100),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "tomatoesaudience" or source == "audience" or source == "popcorn":
                        result["tomatometerallaudience"] = {
                            "rating": self.normalize_rating(rating, 100),
                            "votes": float(votes) if votes else 0.0
                        }
                    elif source == "rogerebert":
                        result["rogerebert"] = {
                            "rating": self.normalize_rating(rating, 4),
                            "votes": float(votes) if votes else 0.0
                        }

            if result:
                result["_source"] = "mdblist"
                self.cache_ratings(cache_key, result)
                return result

            return None

        except DailyLimitReached:
            raise
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: MDBList fetch error: {str(e)}", xbmc.LOGWARNING)
            return None

    def test_connection(self) -> bool:
        """
        Test MDBList API connection.

        Returns:
            True if connection successful
        """
        if not self.api_key:
            return False

        try:
            url = f"{self.BASE_URL}/imdb/movie/tt0133093?{urlencode({'apikey': self.api_key})}"
            req = Request(url)
            req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return 'title' in data and 'ratings' in data
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: MDBList test connection error: {str(e)}", xbmc.LOGWARNING)
            return False
