"""OMDb ratings source."""
from __future__ import annotations

from typing import Optional, Dict
import json
import xbmc
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from resources.lib.ratings.source import RatingsSource, DailyLimitReached
from resources.lib.ratings import usage_tracker
from resources.lib.kodi import _get_api_key


class OMDbRatingsSource(RatingsSource):
    """OMDb ratings source implementation."""

    BASE_URL = "http://www.omdbapi.com/"

    def __init__(self):
        super().__init__("omdb")
        self.api_key = _get_api_key("omdb_api_key")

    def fetch_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from OMDb.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (must contain "imdb")

        Returns:
            Dictionary with ratings:
            {
                "imdb": {"rating": 8.5, "votes": 850000},
                "metacritic": {"rating": 8.5, "votes": 0},
                "tomatometerallcritics": {"rating": 8.8, "votes": 102},
                "tomatometeravgcritics": {"rating": 8.3, "votes": 102},
                "tomatometerallaudience": {"rating": 8.5, "votes": 1000},
                "tomatometeravgaudience": {"rating": 4.2, "votes": 1000}
            }

        Note:
            OMDb tomato fields (tomatoMeter, tomatoRating, etc.) may return "N/A".
            Falls back to Ratings array if direct fields are unavailable.
        """
        if not self.api_key:
            return None

        if usage_tracker.is_provider_skipped("omdb"):
            return None

        imdb_id = ids.get("imdb")
        if not imdb_id:
            return None

        cached = self.get_cached_ratings(imdb_id)
        if cached:
            return cached

        try:
            usage_tracker.increment_usage("omdb")

            params = {"i": imdb_id, "apikey": self.api_key, "tomatoes": "true"}
            url = f"{self.BASE_URL}?{urlencode(params)}"

            req = Request(url)
            req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get("Response") == "False":
                error = data.get("Error", "Unknown error")
                if "limit" in error.lower():
                    raise DailyLimitReached("omdb")
                return None

            result = {}

            imdb_rating = data.get("imdbRating")
            imdb_votes = data.get("imdbVotes")
            if imdb_rating and imdb_rating != "N/A":
                try:
                    rating_val = float(imdb_rating)
                    votes_val = float(imdb_votes.replace(",", "")) if imdb_votes and imdb_votes != "N/A" else 0.0
                    result["imdb"] = {
                        "rating": self.normalize_rating(rating_val, 10),
                        "votes": votes_val
                    }
                except (ValueError, AttributeError):
                    pass

            tomato_meter = data.get("tomatoMeter", "").replace("N/A", "")
            tomato_rating = data.get("tomatoRating", "").replace("N/A", "")
            tomato_reviews = data.get("tomatoReviews", "0").replace("N/A", "0").replace(",", "")

            if tomato_meter:
                try:
                    result["tomatometerallcritics"] = {
                        "rating": self.normalize_rating(float(tomato_meter), 100),
                        "votes": float(tomato_reviews)
                    }
                except (ValueError, AttributeError):
                    pass

            if tomato_rating:
                try:
                    result["tomatometeravgcritics"] = {
                        "rating": self.normalize_rating(float(tomato_rating), 10),
                        "votes": float(tomato_reviews)
                    }
                except (ValueError, AttributeError):
                    pass

            tomato_user_meter = data.get("tomatoUserMeter", "").replace("N/A", "")
            tomato_user_rating = data.get("tomatoUserRating", "").replace("N/A", "")
            tomato_user_reviews = data.get("tomatoUserReviews", "0").replace("N/A", "0").replace(",", "")

            if tomato_user_meter:
                try:
                    result["tomatometerallaudience"] = {
                        "rating": self.normalize_rating(float(tomato_user_meter), 100),
                        "votes": float(tomato_user_reviews)
                    }
                except (ValueError, AttributeError):
                    pass

            if tomato_user_rating:
                try:
                    result["tomatometeravgaudience"] = {
                        "rating": self.normalize_rating(float(tomato_user_rating), 10),
                        "votes": float(tomato_user_reviews)
                    }
                except (ValueError, AttributeError):
                    pass

            metascore = data.get("Metascore", "").replace("N/A", "")
            if metascore:
                try:
                    result["metacritic"] = {
                        "rating": self.normalize_rating(float(metascore), 100),
                        "votes": 0.0
                    }
                except (ValueError, AttributeError):
                    pass

            ratings_list = data.get("Ratings", [])
            if isinstance(ratings_list, list):
                for rating_entry in ratings_list:
                    if not isinstance(rating_entry, dict):
                        continue

                    source = rating_entry.get("Source", "")
                    value = rating_entry.get("Value", "")

                    if "Rotten Tomatoes" in source and value and value != "N/A" and "tomatometerallcritics" not in result:
                        try:
                            rt_value = float(value.rstrip("%"))
                            result["tomatometerallcritics"] = {
                                "rating": self.normalize_rating(rt_value, 100),
                                "votes": 0.0
                            }
                        except ValueError:
                            pass

                    elif "Metacritic" in source and value and value != "N/A" and "metacritic" not in result:
                        try:
                            parts = value.split("/")
                            if len(parts) >= 1:
                                mc_value = float(parts[0])
                                result["metacritic"] = {
                                    "rating": self.normalize_rating(mc_value, 100),
                                    "votes": 0.0
                                }
                        except ValueError:
                            pass

            if result:
                result["_source"] = "omdb"
                self.cache_ratings(imdb_id, result)
                return result

            return None

        except DailyLimitReached:
            raise
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: OMDb fetch error: {str(e)}", xbmc.LOGWARNING)
            return None

    def test_connection(self) -> bool:
        """
        Test OMDb API connection.

        Returns:
            True if connection successful
        """
        if not self.api_key:
            return False

        try:
            params = {"i": "tt0133093", "apikey": self.api_key, "tomatoes": "true"}
            url = f"{self.BASE_URL}?{urlencode(params)}"

            req = Request(url)
            req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("Response") == "True"
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: OMDb test connection error: {str(e)}", xbmc.LOGWARNING)
            return False
