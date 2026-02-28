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
from lib.data.api.source import RatingSource
from lib.data.api import tracker as usage_tracker
from lib.kodi.settings import KodiSettings


def _get_metadata_language() -> str:
    """Get language code for TMDb API requests."""
    lang = KodiSettings.online_metadata_language()
    # TMDb expects codes like 'zh-CN', 'pt-BR' (region part uppercase)
    if '-' in lang:
        parts = lang.split('-')
        return f"{parts[0]}-{parts[1].upper()}"
    return lang


def _is_valid_tmdb_id(tmdb_id: str | None) -> bool:
    """Check if a TMDB ID looks valid (numeric only, reasonable length)."""
    if not tmdb_id:
        return False
    return str(tmdb_id).isdigit() and len(str(tmdb_id)) <= 10


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

    from lib.data.database.correction import get_corrected_tmdb_id, save_corrected_tmdb_id
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
        """Transform TMDB image response to common format.

        All backdrops go to landscape, sorted by language preference:
        1. User's configured language
        2. English (if not user's language)
        3. No language (clean images)
        4. Other languages (foreign text least useful)

        Only no-language backdrops go to fanart (text-free backgrounds).
        """
        result: Dict[str, List[dict]] = {}

        logos = data.get('logos') or []
        formatted_logos = [self._format_image(entry, 'w500') for entry in logos]
        formatted_logos = [entry for entry in formatted_logos if entry]
        if formatted_logos:
            result['clearlogo'] = formatted_logos

        posters = data.get('posters') or []
        keyart = []
        all_posters = []
        for poster in posters:
            formatted = self._format_image(poster, 'w500')
            if formatted:
                all_posters.append(formatted)
                if not poster.get('iso_639_1'):
                    keyart.append(formatted)
        if all_posters:
            result['poster'] = all_posters
        if keyart:
            result['keyart'] = keyart

        backdrops = data.get('backdrops') or []
        if not backdrops:
            return result

        user_lang = _get_metadata_language().split('-')[0].lower()

        formatted_backdrops: List[tuple[dict, str | None]] = []
        for backdrop in backdrops:
            formatted = self._format_image(backdrop, 'w780')
            if formatted:
                lang = backdrop.get('iso_639_1')
                formatted_backdrops.append((formatted, lang.lower() if lang else None))

        def lang_sort_key(item: tuple[dict, str | None]) -> tuple[int, str]:
            lang = item[1]
            if lang == user_lang:
                return (0, '')
            if lang == 'en' and user_lang != 'en':
                return (1, '')
            if lang is None or lang == 'xx':
                return (2, '')
            return (3, lang or '')

        formatted_backdrops.sort(key=lang_sort_key)

        all_backdrops = [item[0] for item in formatted_backdrops]

        if all_backdrops:
            result['fanart'] = all_backdrops
            result['landscape'] = all_backdrops

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
            'language': image.get('iso_639_1') or '',
            'source': 'TMDB'
        }

    def fetch_ratings(
        self,
        media_type: str,
        ids: Dict[str, str],
        abort_flag=None,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Fetch ratings from TMDB using centralized fetch.

        Now uses get_complete_data() which returns full movie details
        including ratings. Much more efficient - one API call gets everything.

        Args:
            media_type: Type of media ("movie", "tvshow", "episode")
            ids: Dictionary of available IDs (must contain "tmdb")
            abort_flag: Optional abort flag for cancellation
            force_refresh: If True, bypass cache read but still write to cache

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

            complete_data = self.get_complete_data(
                media_type, int(tmdb_id_str), abort_flag=abort_flag, force_refresh=force_refresh
            )

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

    def get_complete_data(
        self,
        media_type: str,
        tmdb_id: int,
        release_date: Optional[str] = None,
        abort_flag=None,
        force_refresh: bool = False,
        is_library_item: bool = True
    ) -> Optional[dict]:
        """
        Get complete TMDb data - checks cache first, fetches if needed.

        This is the SINGLE entry point for all TMDb data.
        Both artwork reviewer and ratings updater should use this.

        Args:
            media_type: 'movie', 'tvshow', 'episode'
            tmdb_id: TMDb ID
            release_date: Optional release date from Kodi (for TTL calculation)
            abort_flag: Optional abort flag for cancellation
            force_refresh: If True, skip cache read but still write to cache
            is_library_item: If True, use smart TTL and fetch season data.
                           If False, use 24h TTL and skip season fetch.

        Returns:
            Complete TMDb data dict with everything, or None
        """
        if abort_flag and abort_flag.is_requested():
            return None

        from lib.data import database as db

        if not force_refresh:
            cached = db.get_cached_metadata(media_type, str(tmdb_id))
            if cached:
                return cached

        if abort_flag and abort_flag.is_requested():
            return None

        if media_type == 'movie':
            data = self.get_movie_details_extended(tmdb_id, abort_flag)
        elif media_type == 'tvshow':
            data = self.get_tv_details_extended(tmdb_id, abort_flag)
            if data and is_library_item:
                self._attach_current_season_data(data, tmdb_id, abort_flag)
        else:
            return None

        if not data:
            return None

        if not release_date:
            release_date = self._extract_release_date(data, media_type)

        if is_library_item:
            hints = self._build_cache_hints(data, media_type)
        else:
            hints = {"is_library_item": False}

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

    def _attach_current_season_data(self, data: dict, tmdb_id: int, abort_flag=None) -> None:
        """
        Fetch and attach current season's episode data for airing shows.

        Only fetches for actively airing shows (not ended/canceled) since
        ended shows have complete data and don't benefit from episode tracking.
        """
        status = (data.get('status') or '').lower()
        if status in ('ended', 'canceled'):
            return

        next_ep = data.get('next_episode_to_air')
        last_ep = data.get('last_episode_to_air')

        if next_ep:
            season_num = next_ep.get('season_number')
        elif last_ep:
            season_num = last_ep.get('season_number')
        else:
            return

        if not season_num:
            return

        season_data = self.get_season_details(tmdb_id, season_num, abort_flag)
        if season_data and 'episodes' in season_data:
            data['_current_season'] = {
                'season_number': season_num,
                'episodes': season_data['episodes']
            }

    def _build_cache_hints(self, data: dict, media_type: str) -> Dict[str, str]:
        """
        Build cache hints dict for TTL calculation.

        For TV shows with season data, finds the first episode missing
        overview/still and uses its air_date for cache invalidation.
        """
        hints: Dict[str, str] = {}

        if data.get("status"):
            hints["status"] = data["status"]

        if media_type != 'tvshow':
            return hints

        current_season = data.get('_current_season')
        if not current_season:
            return hints

        episodes = current_season.get('episodes', [])
        for ep in episodes:
            overview = ep.get('overview') or ''
            still = ep.get('still_path')
            air_date = ep.get('air_date')

            if air_date and (not overview or not still):
                hints['next_incomplete_episode'] = air_date
                break

        return hints

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
        language = _get_metadata_language()
        lang_code = language.split('-')[0]
        return self.session.get(
            f"/movie/{tmdb_id}",
            params={
                "api_key": api_key,
                "language": language,
                "append_to_response": append,
                "include_image_language": f"{lang_code},en,null"
            },
            abort_flag=abort_flag
        )

    def get_tv_details_extended(self, tmdb_id: int, abort_flag=None) -> Optional[dict]:
        """
        Similar to movies but for TV shows - uses first_air_date.

        Returns base TV details plus appended data.
        """
        append = "credits,videos,keywords,content_ratings,images,external_ids,recommendations"
        api_key = self.get_api_key()
        language = _get_metadata_language()
        lang_code = language.split('-')[0]
        return self.session.get(
            f"/tv/{tmdb_id}",
            params={
                "api_key": api_key,
                "language": language,
                "append_to_response": append,
                "include_image_language": f"{lang_code},en,null"
            },
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
        language = _get_metadata_language()
        return self.session.get(
            f"/tv/{tmdb_id}/season/{season}/episode/{episode}",
            params={"api_key": api_key, "language": language, "append_to_response": append},
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
        language = _get_metadata_language()
        return self.session.get(
            f"/tv/{tmdb_id}/season/{season_number}",
            params={"api_key": api_key, "language": language, "append_to_response": "aggregate_credits"},
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

        cast_check: set[str] = set()
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
                    cast_check.add(name)

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
        language = _get_metadata_language()
        return self.session.get(
            f"/person/{person_id}",
            params={"api_key": api_key, "language": language, "append_to_response": append},
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
        language = _get_metadata_language()

        params: Dict[str, str | int] = {"api_key": api_key, "language": language, "query": query}
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

    def _get_list(
        self,
        endpoint: str,
        page: int = 1,
        extra_params: Optional[Dict[str, str]] = None,
        abort_flag=None
    ) -> list:
        api_key = self.get_api_key()
        language = _get_metadata_language()
        params: Dict[str, str | int] = {
            "api_key": api_key,
            "language": language,
            "page": page
        }
        if extra_params:
            params.update(extra_params)
        data = self.session.get(endpoint, params=params, abort_flag=abort_flag)
        if not data:
            return []
        if isinstance(data, dict):
            return data.get("results", [])
        return []

    def get_trending(self, media_type: str, window: str = 'week', page: int = 1, abort_flag=None) -> list:
        return self._get_list(f"/trending/{media_type}/{window}", page=page, abort_flag=abort_flag)

    def get_popular(self, media_type: str, page: int = 1, abort_flag=None) -> list:
        return self._get_list(f"/{media_type}/popular", page=page, abort_flag=abort_flag)

    def get_top_rated(self, media_type: str, page: int = 1, abort_flag=None) -> list:
        return self._get_list(f"/{media_type}/top_rated", page=page, abort_flag=abort_flag)

    def get_now_playing(self, page: int = 1, abort_flag=None) -> list:
        return self._get_list("/movie/now_playing", page=page, abort_flag=abort_flag)

    def get_upcoming(self, page: int = 1, abort_flag=None) -> list:
        return self._get_list("/movie/upcoming", page=page, abort_flag=abort_flag)

    def get_airing_today(self, page: int = 1, abort_flag=None) -> list:
        return self._get_list("/tv/airing_today", page=page, abort_flag=abort_flag)

    def get_on_the_air(self, page: int = 1, abort_flag=None) -> list:
        return self._get_list("/tv/on_the_air", page=page, abort_flag=abort_flag)

    def get_genre_list(self, media_type: str) -> Dict[int, str]:
        api_key = self.get_api_key()
        language = _get_metadata_language()
        data = self.session.get(
            f"/genre/{media_type}/list",
            params={"api_key": api_key, "language": language}
        )
        if not data or not isinstance(data, dict):
            return {}
        return {g["id"]: g["name"] for g in data.get("genres", []) if "id" in g and "name" in g}

    def get_item_images(self, media_type: str, tmdb_id: int, abort_flag=None) -> Dict[str, str]:
        """Lightweight image fetch - just poster and backdrop paths."""
        api_key = self.get_api_key()
        data = self.session.get(
            f"/{media_type}/{tmdb_id}",
            params={"api_key": api_key},
            abort_flag=abort_flag
        )
        if not data or not isinstance(data, dict):
            return {}
        result: Dict[str, str] = {}
        if data.get("poster_path"):
            result["poster_path"] = data["poster_path"]
        if data.get("backdrop_path"):
            result["backdrop_path"] = data["backdrop_path"]
        return result

    @staticmethod
    def get_attribution() -> str:
        """Get required TMDB attribution text."""
        return "This product uses the TMDB API but is not endorsed or certified by TMDB."
