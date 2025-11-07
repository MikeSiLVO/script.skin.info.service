"""Trakt ratings source with OAuth support."""
from __future__ import annotations

from typing import Optional, Dict
from datetime import datetime, timedelta
import json
import xbmc
import xbmcvfs

from lib.data.api.client import ApiSession
from lib.rating.source import RatingSource, RateLimitHit, RetryableError
from lib.rating import tracker as usage_tracker
from lib.kodi.client import log


TRAKT_CLIENT_ID = "1c5fb1d6d68e895d4b2f735ea76817422fb3334f1e16f314b32385c0e74f7c8d"
TRAKT_CLIENT_SECRET = "9458673bc095ccad27a5cd5b790581e6fd167b9f6a5d2b4efd17ecd4b2c32a5e"


class ApiTrakt(RatingSource):
    """Trakt ratings source implementation with OAuth."""

    BASE_URL = "https://api.trakt.tv"

    def __init__(self):
        super().__init__("trakt")
        self.token_path = xbmcvfs.translatePath(
            "special://profile/addon_data/script.skin.info.service/trakt_tokens.json"
        )
        self.session = ApiSession(
            service_name="Trakt",
            base_url=self.BASE_URL,
            timeout=(5.0, 10.0),
            max_retries=2,
            backoff_factor=1.0,
            default_headers={
                "Content-Type": "application/json",
                "trakt-api-key": TRAKT_CLIENT_ID,
                "trakt-api-version": "2"
            }
        )

    def _load_tokens(self) -> Optional[Dict]:
        """Load tokens from file."""
        if not xbmcvfs.exists(self.token_path):
            return None

        try:
            with open(self.token_path, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_tokens(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """Save tokens to file."""
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }

        try:
            with open(self.token_path, 'w') as f:
                json.dump(tokens, f)
        except Exception as e:
            log("Ratings", f"Failed to save Trakt tokens: {str(e)}", xbmc.LOGERROR)

    def _delete_tokens(self) -> None:
        """Delete token file."""
        if xbmcvfs.exists(self.token_path):
            try:
                xbmcvfs.delete(self.token_path)
            except Exception:
                pass

    def _get_valid_token(self, abort_flag=None) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        tokens = self._load_tokens()
        if not tokens:
            return None

        expires_at = datetime.fromisoformat(tokens["expires_at"])

        if datetime.now() >= expires_at - timedelta(minutes=5):
            try:
                new_tokens = self.session.post(
                    "/oauth/token",
                    json_data={
                        "refresh_token": tokens["refresh_token"],
                        "client_id": TRAKT_CLIENT_ID,
                        "client_secret": TRAKT_CLIENT_SECRET,
                        "grant_type": "refresh_token"
                    },
                    abort_flag=abort_flag
                )

                if new_tokens:
                    self._save_tokens(
                        new_tokens["access_token"],
                        new_tokens["refresh_token"],
                        new_tokens.get("expires_in", 86400)
                    )
                    return new_tokens["access_token"]
                else:
                    self._delete_tokens()
                    return None

            except RateLimitHit:
                raise
            except Exception:
                return None

        return tokens["access_token"]

    def fetch_data(
        self,
        media_type: str,
        ids: Dict[str, str],
        abort_flag=None
    ) -> Optional[dict]:
        """
        Fetch complete Trakt data for an item.

        For movies/shows: Uses extended=full endpoint to get ratings + subgenres + extras.
        For episodes: Uses ratings endpoint (no extra data available).

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug)
            abort_flag: Optional abort flag for cancellation

        Returns:
            Full Trakt response dict or None
        """
        if usage_tracker.is_provider_skipped("trakt"):
            return None

        trakt_id = ids.get("trakt_slug") or ids.get("imdb") or ids.get("tmdb")
        if not trakt_id:
            return None

        cache_key = self._get_cache_key(media_type, ids)
        cached = self.get_cached_data(cache_key)
        if cached:
            return cached

        token = self._get_valid_token(abort_flag)
        if not token:
            return None

        try:
            usage_tracker.increment_usage("trakt")

            if media_type == "movie":
                endpoint = f"/movies/{trakt_id}"
            elif media_type == "tvshow":
                endpoint = f"/shows/{trakt_id}"
            elif media_type == "episode":
                season = ids.get("season")
                episode = ids.get("episode")
                if not season or not episode:
                    return None
                endpoint = f"/shows/{trakt_id}/seasons/{season}/episodes/{episode}"
            else:
                return None

            data = self.session.get(
                endpoint,
                params={"extended": "full"},
                headers={"Authorization": f"Bearer {token}"},
                abort_flag=abort_flag
            )

            if data:
                self.cache_data(cache_key, data)

            return data

        except RateLimitHit:
            raise
        except RetryableError:
            raise
        except Exception as e:
            log("Trakt", f"Fetch error: {str(e)}", xbmc.LOGWARNING)
            return None

    def _get_cache_key(self, media_type: str, ids: Dict[str, str]) -> str:
        """Generate cache key for Trakt data."""
        trakt_id = ids.get("trakt_slug") or ids.get("imdb") or ids.get("tmdb")
        if media_type == "episode":
            season = ids.get("season", "")
            episode = ids.get("episode", "")
            return f"{trakt_id}_s{season}e{episode}"
        return str(trakt_id)

    def get_trakt_data(self, media_type: str, ids: Dict[str, str]) -> Optional[dict]:
        """
        Get full cached Trakt response.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug)

        Returns:
            Full cached Trakt response or None
        """
        cache_key = self._get_cache_key(media_type, ids)
        return self.get_cached_data(cache_key)

    def fetch_ratings(
        self,
        media_type: str,
        ids: Dict[str, str],
        abort_flag=None
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from Trakt (required by RatingSource interface).

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug)
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dictionary with normalized ratings
        """
        data = self.fetch_data(media_type, ids, abort_flag)
        if not data:
            return None

        return self._extract_ratings(data)

    def get_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Extract ratings from cached Trakt data.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug)

        Returns:
            Dictionary with Trakt rating:
            {"trakt": {"rating": 8.4, "votes": 5000}}
        """
        data = self.get_trakt_data(media_type, ids)
        if not data:
            return None

        return self._extract_ratings(data)

    def _extract_ratings(self, data: dict) -> Optional[Dict[str, Dict[str, float]]]:
        """Extract ratings dict from full Trakt response."""
        rating = data.get("rating")
        votes = data.get("votes")

        if rating is None or votes is None:
            return None

        result: Dict[str, Dict[str, float]] = {
            "trakt": {
                "rating": self.normalize_rating(rating, 10),
                "votes": float(votes)
            }
        }
        result["_source"] = "trakt"  # type: ignore[assignment]
        return result

    def get_subgenres(
        self,
        trakt_id: str,
        media_type: str = "movie",
        abort_flag=None
    ) -> Optional[list]:
        """
        Get curated subgenres for a movie or TV show from Trakt.

        Uses the same cached data as fetch_data/fetch_ratings - no extra API call
        if ratings were already fetched.

        Args:
            trakt_id: Trakt slug or IMDb/TMDB ID
            media_type: "movie" or "tvshow"
            abort_flag: Optional abort flag for cancellation

        Returns:
            List of subgenre strings or None
        """
        ids = {"imdb": trakt_id} if trakt_id.startswith("tt") else {"tmdb": trakt_id}

        data = self.get_trakt_data(media_type, ids)
        if not data:
            data = self.fetch_data(media_type, ids, abort_flag)

        if not data:
            return None

        subgenres = data.get("subgenres")
        if subgenres and isinstance(subgenres, list):
            return subgenres

        return None

    def test_connection(self) -> bool:
        """
        Test Trakt API connection.

        Returns:
            True if connection successful
        """
        token = self._get_valid_token()
        if not token:
            return False

        try:
            data = self.session.get(
                "/users/settings",
                headers={"Authorization": f"Bearer {token}"}
            )
            return data is not None
        except Exception as e:
            log("Ratings", f"Trakt test connection error: {str(e)}", xbmc.LOGWARNING)
            return False
