"""Trakt ratings source with OAuth support."""
from __future__ import annotations

from typing import Optional, Dict
from datetime import datetime, timedelta
import json
import xbmc
import xbmcvfs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from resources.lib.ratings.source import RatingsSource
from resources.lib.ratings import usage_tracker


TRAKT_CLIENT_ID = "1c5fb1d6d68e895d4b2f735ea76817422fb3334f1e16f314b32385c0e74f7c8d"
TRAKT_CLIENT_SECRET = "9458673bc095ccad27a5cd5b790581e6fd167b9f6a5d2b4efd17ecd4b2c32a5e"


class TraktRatingsSource(RatingsSource):
    """Trakt ratings source implementation with OAuth."""

    BASE_URL = "https://api.trakt.tv"

    def __init__(self):
        super().__init__("trakt")
        self.token_path = xbmcvfs.translatePath(
            "special://profile/addon_data/script.skin.info.service/trakt_tokens.json"
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
            xbmc.log(f"SkinInfo [Ratings]: Failed to save Trakt tokens: {str(e)}", xbmc.LOGERROR)

    def _delete_tokens(self) -> None:
        """Delete token file."""
        if xbmcvfs.exists(self.token_path):
            try:
                xbmcvfs.delete(self.token_path)
            except Exception:
                pass

    def _get_valid_token(self) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        tokens = self._load_tokens()
        if not tokens:
            return None

        expires_at = datetime.fromisoformat(tokens["expires_at"])

        if datetime.now() >= expires_at - timedelta(minutes=5):
            data = json.dumps({
                "refresh_token": tokens["refresh_token"],
                "client_id": TRAKT_CLIENT_ID,
                "client_secret": TRAKT_CLIENT_SECRET,
                "grant_type": "refresh_token"
            }).encode('utf-8')

            req = Request(f"{self.BASE_URL}/oauth/token", data=data)
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "script.skin.info.service/2.0.0")

            try:
                with urlopen(req, timeout=10) as response:
                    new_tokens = json.loads(response.read().decode('utf-8'))
                    self._save_tokens(
                        new_tokens["access_token"],
                        new_tokens["refresh_token"],
                        new_tokens.get("expires_in", 86400)
                    )
                    return new_tokens["access_token"]
            except HTTPError as e:
                if e.code in (401, 403):
                    self._delete_tokens()
                return None
            except Exception:
                return None

        return tokens["access_token"]

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "script.skin.info.service/2.0.0",
            "trakt-api-key": TRAKT_CLIENT_ID,
            "trakt-api-version": "2"
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def fetch_ratings(self, media_type: str, ids: Dict[str, str]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from Trakt.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (tmdb, imdb, trakt_slug)

        Returns:
            Dictionary with Trakt rating:
            {"trakt": {"rating": 8.4, "votes": 5000}}
        """
        if usage_tracker.is_provider_skipped("trakt"):
            return None

        trakt_id = ids.get("trakt_slug") or ids.get("imdb") or ids.get("tmdb")
        if not trakt_id:
            return None

        cached = self.get_cached_ratings(trakt_id)
        if cached:
            return cached

        token = self._get_valid_token()
        if not token:
            return None

        try:
            count, hit_before = usage_tracker.increment_usage("trakt")

            if media_type == "movie":
                endpoint = f"/movies/{trakt_id}/ratings"
            elif media_type == "tvshow":
                endpoint = f"/shows/{trakt_id}/ratings"
            elif media_type == "episode":
                season = ids.get("season")
                episode = ids.get("episode")
                if not season or not episode:
                    return None
                endpoint = f"/shows/{trakt_id}/seasons/{season}/episodes/{episode}/ratings"
            else:
                return None

            req = Request(f"{self.BASE_URL}{endpoint}")
            for key, value in self._get_headers(token).items():
                req.add_header(key, value)

            try:
                with urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except HTTPError as e:
                if e.code == 429:
                    retry_after = int(e.headers.get("Retry-After", 60))
                    xbmc.sleep(retry_after * 1000)

                    req = Request(f"{self.BASE_URL}{endpoint}")
                    for key, value in self._get_headers(token).items():
                        req.add_header(key, value)

                    with urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode('utf-8'))
                else:
                    xbmc.log(f"SkinInfo [Ratings]: Trakt returned {e.code}", xbmc.LOGWARNING)
                    return None

            rating = data.get("rating")
            votes = data.get("votes")

            if rating is None or votes is None:
                return None

            result = {
                "trakt": {
                    "rating": self.normalize_rating(rating, 10),
                    "votes": float(votes)
                },
                "_source": "trakt"
            }

            self.cache_ratings(trakt_id, result)
            return result

        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: Trakt fetch error: {str(e)}", xbmc.LOGWARNING)
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
            req = Request(f"{self.BASE_URL}/users/settings")
            for key, value in self._get_headers(token).items():
                req.add_header(key, value)

            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            xbmc.log(f"SkinInfo [Ratings]: Trakt test connection error: {str(e)}", xbmc.LOGWARNING)
            return False
