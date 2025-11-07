"""TMDB API client for artwork and ratings.

Provides:
- Movie/TV show artwork (posters, backdrops, logos)
- Movie/TV show/episode ratings
"""
from __future__ import annotations

import xbmc
from typing import Optional, Dict, List

from lib.data.api.client import ApiSession
from lib.kodi.client import log
from lib.rating.source import RatingSource
from lib.rating import tracker as usage_tracker
from lib.kodi.settings import KodiSettings


def _is_valid_tmdb_id(tmdb_id: str | None) -> bool:
    """Check if a TMDB ID looks valid (numeric only, reasonable length)."""
    if not tmdb_id:
        return False
    return str(tmdb_id).isdigit() and len(str(tmdb_id)) <= 10


def get_corrected_tmdb_id(imdb_id: str) -> int | None:
    """Get cached TMDB ID correction for an IMDB ID."""
    from lib.data.database._infrastructure import get_db
    with get_db() as (conn, cursor):
        cursor.execute(
            "SELECT tmdb_id FROM id_corrections WHERE imdb_id = ?",
            (imdb_id,)
        )
        row = cursor.fetchone()
        return row["tmdb_id"] if row else None


def save_corrected_tmdb_id(imdb_id: str, tmdb_id: int, media_type: str) -> None:
    """Cache a corrected TMDB ID for an IMDB ID."""
    from lib.data.database._infrastructure import get_db
    with get_db() as (conn, cursor):
        cursor.execute(
            """INSERT OR REPLACE INTO id_corrections (imdb_id, tmdb_id, media_type)
               VALUES (?, ?, ?)""",
            (imdb_id, tmdb_id, media_type)
        )


def resolve_tmdb_id(tmdb_id: str | None, imdb_id: str | None, media_type: str) -> str | None:
    """
    Resolve a valid TMDB ID, correcting invalid ones if possible.

    Args:
        tmdb_id: TMDB ID from library (may be invalid)
        imdb_id: IMDB ID from library (used for correction lookup)
        media_type: "movie" or "tvshow"

    Returns:
        Valid TMDB ID string, or None if unresolvable
    """
    if _is_valid_tmdb_id(tmdb_id):
        return tmdb_id

    if not imdb_id:
        return None

    corrected = get_corrected_tmdb_id(imdb_id)
    if corrected:
        return str(corrected)

    api = ApiTmdb()
    found_id = api.find_by_imdb(imdb_id, media_type)
    if found_id:
        save_corrected_tmdb_id(imdb_id, found_id, media_type)
        log("TMDB", f"Corrected invalid TMDB ID for {imdb_id} -> {found_id}", xbmc.LOGDEBUG)
        return str(found_id)

    return None


class ApiTmdb(RatingSource):
    """TMDB API client with rate limiting for artwork and ratings."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/original"

    API_KEY = "0142a22c560ce3efb1cfd6f3b2faab77"

    def __init__(self):
        super().__init__("tmdb")
        self.session = ApiSession(
            service_name="TMDB",
            base_url=self.BASE_URL,
            timeout=(5.0, 10.0),
            max_retries=3,
            backoff_factor=0.5,
            rate_limit=(35, 1.0),
            default_headers={
                "Accept": "application/json"
            }
        )

    def get_api_key(self) -> str:
        """
        Get TMDB API key with priority order:
        1. User's key from addon settings (if custom key enabled)
        2. Built-in key from API_KEY constant

        Returns:
            API key (always available via built-in key)
        """
        use_custom = KodiSettings.tmdb_use_custom_key()
        if use_custom:
            user_key = KodiSettings.tmdb_api_key()
            if user_key:
                return user_key

        return self.API_KEY.strip()

    def _make_request(
        self,
        endpoint: str,
        abort_flag=None
    ) -> Optional[dict]:
        """
        Make HTTP request to TMDB API with rate limiting and retry.

        Args:
            endpoint: API endpoint (relative to BASE_URL)
            abort_flag: Optional abort flag for cancellation

        Returns:
            JSON response or None on error
        """
        api_key = self.get_api_key()
        return self.session.get(
            endpoint,
            params={"api_key": api_key},
            abort_flag=abort_flag
        )

    def get_movie_images(self, tmdb_id: int) -> dict:
        """Get all available images for a movie from TMDB."""
        return self._fetch_images('movie', tmdb_id)

    def get_tv_images(self, tmdb_id: int) -> dict:
        """Get all available images for a TV show from TMDB."""
        return self._fetch_images('tv', tmdb_id)

    def get_collection_images(self, collection_id: int) -> dict:
        """Get all available images for a movie collection from TMDB."""
        return self._fetch_images('collection', collection_id)

    def get_season_images(self, tmdb_id: int, season_number: int, abort_flag=None) -> dict:
        """
        Get all available images for a TV season from TMDB.

        Args:
            tmdb_id: TMDB TV show ID
            season_number: Season number
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dict with artwork by type: {'poster': [...]}
        """
        data = self._make_request(
            f"/tv/{tmdb_id}/season/{season_number}/images",
            abort_flag
        )

        if not data:
            return {}

        return self._transform_images(data)

    def get_episode_images(
        self,
        tmdb_id: int,
        season_number: int,
        episode_number: int,
        abort_flag=None
    ) -> dict:
        """
        Get all available images for a TV episode from TMDB.

        Args:
            tmdb_id: TMDB TV show ID
            season_number: Season number
            episode_number: Episode number
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dict with artwork by type: {'thumb': [...]}
        """
        data = self._make_request(
            f"/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/images",
            abort_flag
        )

        if not data:
            return {}

        stills = data.get('stills', [])
        result = {}
        if stills:
            result['thumb'] = [self._format_image(img, 'w300') for img in stills if self._format_image(img, 'w300')]

        return result

    def _fetch_images(self, media_kind: str, tmdb_id: int, abort_flag=None) -> dict:
        """Fetch images from TMDB API."""
        data = self._make_request(f"/{media_kind}/{tmdb_id}/images", abort_flag)

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

        # Skip SVG files - Kodi cannot render them
        if file_path.lower().endswith('.svg'):
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

    def fetch_ratings(self, media_type: str, ids: Dict[str, str], abort_flag=None) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from TMDB using centralized fetch.

        Now uses get_complete_data() which returns full movie details
        including ratings. Much more efficient - one API call gets everything.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (must contain "tmdb")
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dictionary with TMDB ratings:
            {"themoviedb": {"rating": 8.3, "votes": 12500}}
        """
        if abort_flag and abort_flag.is_requested():
            return None

        if usage_tracker.is_provider_skipped("tmdb"):
            return None

        tmdb_id_str = ids.get("tmdb") or ""
        if not _is_valid_tmdb_id(tmdb_id_str):
            return None

        try:
            usage_tracker.increment_usage("tmdb")

            complete_data = self.get_complete_data(media_type, int(tmdb_id_str), abort_flag=abort_flag)

            if not complete_data:
                return None

            rating = complete_data.get("vote_average")
            votes = complete_data.get("vote_count")

            if rating is None or votes is None:
                return None

            rating_key = "themoviedb" if media_type == "movie" else "tmdb"
            result = {
                rating_key: {
                    "rating": self.normalize_rating(rating, 10),
                    "votes": float(votes)
                },
                "_source": "tmdb"
            }

            return result

        except Exception as e:
            log("Ratings", f"TMDB fetch error: {str(e)}", xbmc.LOGWARNING)
            return None

    def test_connection(self) -> bool:
        """
        Test TMDB API connection.

        Returns:
            True if connection successful
        """
        try:
            details = self._make_request("/movie/550")
            return details is not None
        except Exception as e:
            log("Ratings", f"TMDB test connection error: {str(e)}", xbmc.LOGWARNING)
            return False

    def find_by_imdb(self, imdb_id: str, media_type: str, abort_flag=None) -> int | None:
        """
        Find TMDB ID by IMDB ID using TMDB's find endpoint.

        Args:
            imdb_id: IMDB ID (e.g., "tt0111161")
            media_type: "movie" or "tvshow"
            abort_flag: Optional abort flag for cancellation

        Returns:
            TMDB ID if found, None otherwise
        """
        if not imdb_id or not imdb_id.startswith("tt"):
            return None

        try:
            api_key = self.get_api_key()
            data = self.session.get(
                f"/find/{imdb_id}",
                params={"api_key": api_key, "external_source": "imdb_id"},
                abort_flag=abort_flag
            )
            if not data:
                return None

            if media_type == "movie":
                results = data.get("movie_results", [])
            else:
                results = data.get("tv_results", [])

            if results:
                return results[0].get("id")

            return None
        except Exception as e:
            log("TMDB", f"Find by IMDB error: {str(e)}", xbmc.LOGWARNING)
            return None

    def get_complete_data(self, media_type: str, tmdb_id: int, release_date: Optional[str] = None, abort_flag=None) -> Optional[dict]:
        """
        Get complete TMDb data - checks cache first, fetches if needed.

        This is the SINGLE entry point for all TMDb data.
        Both artwork reviewer and ratings updater should use this.

        Args:
            media_type: 'movie', 'tvshow', 'episode'
            tmdb_id: TMDb ID
            release_date: Optional release date from Kodi (for TTL calculation)
            abort_flag: Optional abort flag for cancellation

        Returns:
            Complete TMDb data dict with everything, or None
        """
        if abort_flag and abort_flag.is_requested():
            return None

        from lib.data import database as db

        cached = db.get_cached_metadata(media_type, str(tmdb_id))
        if cached:
            return cached

        if abort_flag and abort_flag.is_requested():
            return None

        if media_type == 'movie':
            data = self.get_movie_details_extended(tmdb_id, abort_flag)
        elif media_type == 'tvshow':
            data = self.get_tv_details_extended(tmdb_id, abort_flag)
        else:
            return None

        if not data:
            return None

        if not release_date:
            release_date = self._extract_release_date(data, media_type)

        # Build cache hints from metadata
        hints = {}
        if data.get("status"):
            hints["status"] = data["status"]

        db.cache_metadata(media_type, str(tmdb_id), data, release_date, hints)

        self._cache_components(media_type, tmdb_id, data, release_date, hints)

        return data

    def _extract_release_date(self, data: dict, media_type: str) -> Optional[str]:
        """Extract appropriate date field from TMDb response."""
        if media_type == 'movie':
            return data.get('release_date')
        elif media_type == 'tvshow':
            return data.get('first_air_date')
        elif media_type == 'episode':
            return data.get('air_date')
        return None

    def _cache_components(self, media_type: str, tmdb_id: int, data: dict, release_date: Optional[str], hints: Optional[dict] = None) -> None:
        """
        Cache individual components from complete response.
        Maintains compatibility with existing artwork_cache and ratings_cache tables.
        """
        from lib.data import database as db

        ttl_hours = db.get_cache_ttl_hours(release_date, hints)

        if 'images' in data:
            images = data['images']
            posters = images.get('posters', [])
            backdrops = images.get('backdrops', [])
            logos = images.get('logos', [])

            if posters:
                formatted_posters = [self._format_image(img, 'w500') for img in posters]
                formatted_posters = [img for img in formatted_posters if img]
                if formatted_posters:
                    db.cache_artwork(media_type, str(tmdb_id), 'tmdb', 'poster',
                                   formatted_posters, release_date, ttl_hours)

            if backdrops:
                formatted_backdrops = [self._format_image(img, 'w780') for img in backdrops]
                formatted_backdrops = [img for img in formatted_backdrops if img]
                if formatted_backdrops:
                    db.cache_artwork(media_type, str(tmdb_id), 'tmdb', 'fanart',
                                   formatted_backdrops, release_date, ttl_hours)

            if logos:
                formatted_logos = [self._format_image(img, 'w500') for img in logos]
                formatted_logos = [img for img in formatted_logos if img]
                if formatted_logos:
                    db.cache_artwork(media_type, str(tmdb_id), 'tmdb', 'clearlogo',
                                   formatted_logos, release_date, ttl_hours)


    def get_movie_details_extended(self, tmdb_id: int, abort_flag=None) -> Optional[dict]:
        """
        Fetch complete movie data in ONE API call using append_to_response.

        Returns base movie details plus:
        - credits: cast and crew
        - videos: trailers, clips
        - keywords: genre keywords
        - release_dates: certifications by country
        - images: all posters, backdrops, logos
        - external_ids: IMDB, TVDB, etc.
        - recommendations: recommended similar movies

        Args:
            tmdb_id: TMDb movie ID
            abort_flag: Optional abort flag for cancellation

        Returns:
            Complete movie data dict or None on error
        """
        append = "credits,videos,keywords,release_dates,images,external_ids,recommendations"
        api_key = self.get_api_key()
        return self.session.get(
            f"/movie/{tmdb_id}",
            params={"api_key": api_key, "append_to_response": append},
            abort_flag=abort_flag
        )

    def get_tv_details_extended(self, tmdb_id: int, abort_flag=None) -> Optional[dict]:
        """
        Similar to movies but for TV shows - uses first_air_date.

        Returns base TV details plus appended data.
        """
        append = "credits,videos,keywords,content_ratings,images,external_ids,recommendations"
        api_key = self.get_api_key()
        return self.session.get(
            f"/tv/{tmdb_id}",
            params={"api_key": api_key, "append_to_response": append},
            abort_flag=abort_flag
        )

    def get_episode_details_extended(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        abort_flag=None
    ) -> Optional[dict]:
        """
        Similar for episodes - uses air_date.

        Returns base episode details plus appended data.
        """
        append = "credits,videos,images,external_ids"
        api_key = self.get_api_key()
        return self.session.get(
            f"/tv/{tmdb_id}/season/{season}/episode/{episode}",
            params={"api_key": api_key, "append_to_response": append},
            abort_flag=abort_flag
        )

    def get_season_details(self, tmdb_id: int, season_number: int, abort_flag=None) -> Optional[dict]:
        """
        Get season details including episodes with guest stars and aggregate credits.

        Uses append_to_response to get everything in one API call.

        Args:
            tmdb_id: TMDB TV show ID
            season_number: Season number
            abort_flag: Optional abort flag for cancellation

        Returns:
            Season data with:
            - episodes array (each episode includes guest_stars)
            - aggregate_credits (main cast for the season)
        """
        api_key = self.get_api_key()
        return self.session.get(
            f"/tv/{tmdb_id}/season/{season_number}",
            params={"api_key": api_key, "append_to_response": "aggregate_credits"},
            abort_flag=abort_flag
        )

    def get_kodi_tv_scraper_combined_cast(self, tmdb_id: int, abort_flag=None) -> list[dict]:
        """
        Get combined deduplicated cast from ALL seasons, matching Kodi TMDB scraper behavior.

        The Kodi TMDB scraper fetches each season's credits.cast and combines them in reverse
        order with deduplication. This replicates that exact behavior for compatibility with
        Kodi's database when using online=false mode.

        Args:
            tmdb_id: TMDB TV show ID
            abort_flag: Optional abort flag for cancellation

        Returns:
            Deduplicated list of cast members from all seasons
        """
        api_key = self.get_api_key()

        show_data = self.session.get(
            f"/tv/{tmdb_id}",
            params={"api_key": api_key},
            abort_flag=abort_flag
        )

        if not show_data:
            return []

        seasons = show_data.get('seasons', [])
        if not seasons:
            return []

        cast_check: list[str] = []
        combined_cast: list[dict] = []

        for season in reversed(seasons):
            season_num = season.get('season_number', 0)
            season_data = self.session.get(
                f"/tv/{tmdb_id}/season/{season_num}",
                params={"api_key": api_key, "append_to_response": "credits"},
                abort_flag=abort_flag
            )

            if not season_data:
                continue

            season_cast = season_data.get('credits', {}).get('cast', [])

            for cast_member in season_cast:
                name = cast_member.get('name', '')
                if name and name not in cast_check:
                    combined_cast.append(cast_member)
                    cast_check.append(name)

        return combined_cast

    def get_person_details(self, person_id: int, abort_flag=None) -> Optional[dict]:
        """
        Get complete person details from TMDB.

        Includes biography, birthday, filmography, images, social media.
        Uses append_to_response for single API call.

        Args:
            person_id: TMDB person ID
            abort_flag: Optional abort flag for cancellation

        Returns:
            Complete person data or None on error
        """
        append = "images,combined_credits,external_ids"
        api_key = self.get_api_key()
        return self.session.get(
            f"/person/{person_id}",
            params={"api_key": api_key, "append_to_response": append},
            abort_flag=abort_flag
        )

    def find_by_external_id(
        self,
        external_id: str,
        source: str,
        media_type: str = "movie",
        abort_flag=None
    ) -> Optional[dict]:
        """
        Find TMDB entry using external ID (IMDB, TVDB).

        Args:
            external_id: External ID (e.g., "tt0137523", "81189")
            source: Source type ("imdb_id" or "tvdb_id")
            media_type: Type to look for ("movie", "tvshow", "episode")
            abort_flag: Optional abort flag for cancellation

        Returns:
            Result dict with 'id' (TMDB ID) and other fields, or None if not found
        """
        api_key = self.get_api_key()
        data = self.session.get(
            f"/find/{external_id}",
            params={"api_key": api_key, "external_source": source},
            abort_flag=abort_flag
        )
        if not data:
            return None

        result_key_map = {
            "movie": "movie_results",
            "tvshow": "tv_results",
            "episode": "tv_episode_results"
        }
        result_key = result_key_map.get(media_type, "movie_results")
        results = data.get(result_key, [])
        return results[0] if results else None

    def search(
        self,
        query: str,
        media_type: str = 'movie',
        year: int = 0,
        abort_flag=None
    ) -> list[dict]:
        """
        Search TMDB for movies, TV shows, or people.

        Args:
            query: Search query string
            media_type: Type to search (movie, tv, person)
            year: Optional year filter (movie/tv only)
            abort_flag: Optional abort flag for cancellation

        Returns:
            List of search results
        """
        endpoint_map = {
            'movie': '/search/movie',
            'tv': '/search/tv',
            'person': '/search/person',
        }

        endpoint = endpoint_map.get(media_type, '/search/movie')
        api_key = self.get_api_key()

        params: Dict[str, str | int] = {"api_key": api_key, "query": query}
        if year > 0 and media_type in ('movie', 'tv'):
            year_param = 'year' if media_type == 'movie' else 'first_air_date_year'
            params[year_param] = year

        data = self.session.get(endpoint, params=params, abort_flag=abort_flag)
        return data.get('results', []) if data else []

    def search_person(self, name: str) -> list[dict]:
        """
        Search for person by name.

        Args:
            name: Person name to search

        Returns:
            List of search results with id, name, known_for_department, profile_path
        """
        return self.search(name, 'person')

    @staticmethod
    def get_attribution() -> str:
        """Get required TMDB attribution text."""
        return "This product uses the TMDB API but is not endorsed or certified by TMDB."
