"""External API fetching and caching for artwork.

Centralizes retrieval of artwork from TMDB and fanart.tv APIs.
Handles caching, batch fetching, and dimension normalization.
"""
from __future__ import annotations

import xbmc
import xbmcaddon
import xbmcgui
from contextlib import suppress
from typing import Optional, Dict, List, Any, cast

from resources.lib import database as db
from resources.lib.api.tmdb import TMDBApi
from resources.lib.api.fanarttv import FanartTVApi
from resources.lib.kodi import request, extract_result, KODI_GET_DETAILS_METHODS
from resources.lib.art_helpers import sort_artwork_by_popularity
from resources.lib.artwork.helpers import FANART_DIMENSIONS, CACHE_ART_TYPES
from resources.lib.kodi import log_artwork

ADDON = xbmcaddon.Addon()


class ArtworkSourceFetcher:
    """
    Centralized helper for retrieving and caching artwork from external APIs.

    Fetches artwork from TMDB and fanart.tv, caches results with dynamic TTL
    based on media age, and provides batch fetching to minimize API calls.
    """

    def __init__(self, tmdb_api: TMDBApi, fanart_api: FanartTVApi):
        """
        Initialize fetcher with API clients.

        Args:
            tmdb_api: TMDB API client instance
            fanart_api: Fanart.tv API client instance
        """
        self.tmdb_api = tmdb_api
        self.fanart_api = fanart_api

    def get_external_ids(self, media_type: str, dbid: int, *, include_year: bool = False) -> dict:
        """
        Get external IDs (TMDB, TVDB) for a Kodi library item.

        Args:
            media_type: Media type (movie, tvshow, etc.)
            dbid: Kodi database ID
            include_year: Whether to include release year

        Returns:
            Dict with tmdb_id, tvdb_id, and optionally year
        """
        if media_type not in KODI_GET_DETAILS_METHODS:
            return {}

        method, id_key, result_key = KODI_GET_DETAILS_METHODS[media_type]
        properties = ['uniqueid']
        if include_year:
            properties.append('year')

        try:
            resp = request(method, {
                id_key: dbid,
                'properties': properties,
            })
        except Exception as e:
            xbmc.log(f"SkinInfo: Error getting external IDs for {media_type}:{dbid}: {e}", xbmc.LOGERROR)
            return {}

        if not resp:
            return {}

        details = extract_result(resp, result_key)
        if not isinstance(details, dict):
            return {}

        unique_ids = details.get('uniqueid', {}) or {}
        result: Dict[str, Any] = {}

        tmdb_id = unique_ids.get('tmdb')
        tvdb_id = unique_ids.get('tvdb')

        if tmdb_id:
            try:
                result['tmdb_id'] = int(tmdb_id)
            except (TypeError, ValueError):
                pass
        if tvdb_id:
            try:
                result['tvdb_id'] = int(tvdb_id)
            except (TypeError, ValueError):
                pass

        if include_year:
            year = details.get('year')
            if isinstance(year, int):
                result['year'] = year
            elif isinstance(year, str):
                with suppress(ValueError):
                    result['year'] = int(year)

        return result

    def fetch_all(self, media_type: str, dbid: int, season_number: Optional[int] = None, episode_number: Optional[int] = None) -> Dict[str, List[dict]]:
        """
        Fetch ALL artwork types for an item in a single operation.

        This is the PERFORMANCE-CRITICAL method that minimizes API calls by:
        1. Checking cache first (with completion marker)
        2. Fetching ALL art types from TMDB + fanart.tv in one go
        3. Caching all results with dynamic TTL based on media age

        Args:
            media_type: Media type (movie, tvshow, season, episode)
            dbid: Kodi database ID
            season_number: Season number (for seasons/episodes)
            episode_number: Episode number (for episodes)

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        if media_type == 'season':
            return self._fetch_season_artwork(dbid, season_number)
        elif media_type == 'episode':
            return self._fetch_episode_artwork(dbid, season_number, episode_number)
        elif media_type not in ('movie', 'tvshow'):
            return {}

        ids = self.get_external_ids(media_type, dbid, include_year=True)
        tmdb_id = ids.get('tmdb_id')
        tvdb_id = ids.get('tvdb_id')
        year = ids.get('year')

        if not tmdb_id:
            return {}

        ttl_hours = db.get_cache_ttl_hours(year) if year else db.DEFAULT_CACHE_TTL_HOURS
        cache_marker_type = '_full_fetch_complete'
        cached_marker = db.get_cached_artwork(media_type, str(tmdb_id), 'system', cache_marker_type)

        # If we have a completion marker, load all cached artwork
        if cached_marker is not None:
            cached_art = self._load_cached_artwork(media_type, tmdb_id, tvdb_id)
            return self._finalise_artwork(media_type, cached_art)

        all_art: Dict[str, List[dict]] = {}

        # TMDB sources - single API call gets all image types
        tmdb_art = self._fetch_tmdb_art(media_type, tmdb_id)
        for art_type, artworks in tmdb_art.items():
            if artworks:
                db.cache_artwork(media_type, str(tmdb_id), 'tmdb', art_type, artworks, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        # fanart.tv sources - single API call gets all art types
        fanart_items = self._fetch_fanart_art(media_type, tmdb_id, tvdb_id)
        for art_type, artworks in fanart_items.items():
            if artworks:
                cache_id = str(tvdb_id) if tvdb_id and media_type == 'tvshow' else str(tmdb_id)
                db.cache_artwork(media_type, cache_id, 'fanarttv', art_type, artworks, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        # Mark fetch as complete
        if tmdb_id:
            db.cache_artwork(media_type, str(tmdb_id), 'system', cache_marker_type, [{'marker': 'complete'}], ttl_hours)

        finalised = self._finalise_artwork(media_type, all_art)

        total_items = sum(len(v) for v in finalised.values())
        source_summary = [f"{key}:{len(values)}" for key, values in finalised.items()]
        log_artwork(f"Fetched {media_type}:{dbid} - {total_items} art items ({', '.join(source_summary)})")

        return finalised

    def fetch_by_type(self, media_type: str, dbid: int, art_type: str) -> List[dict]:
        """
        Fetch artwork for a single art type.

        Note: This still calls fetch_all() internally to leverage caching.
        Prefer fetch_all() when checking multiple art types for same item.

        Args:
            media_type: Media type
            dbid: Kodi database ID
            art_type: Art type to retrieve

        Returns:
            List of artwork dicts for the requested type
        """
        all_art = self.fetch_all(media_type, dbid)
        return all_art.get(art_type, [])

    def _load_cached_artwork(self, media_type: str, tmdb_id: int, tvdb_id: Optional[int]) -> Dict[str, List[dict]]:
        """Load all cached artwork for an item from database."""
        cached: Dict[str, List[dict]] = {}
        cache_id = str(tvdb_id) if tvdb_id and media_type == 'tvshow' else str(tmdb_id)

        for art_type in CACHE_ART_TYPES:
            tmdb_cached = db.get_cached_artwork(media_type, str(tmdb_id), 'tmdb', art_type)
            if tmdb_cached:
                cached.setdefault(art_type, []).extend(tmdb_cached)

            fanart_cached = db.get_cached_artwork(media_type, cache_id, 'fanarttv', art_type)
            if fanart_cached:
                cached.setdefault(art_type, []).extend(fanart_cached)

        return cached

    def _fetch_tmdb_art(self, media_type: str, tmdb_id: int) -> Dict[str, List[dict]]:
        """Fetch artwork from TMDB API."""
        if media_type == 'movie':
            art = self.tmdb_api.get_movie_images(tmdb_id)
        else:
            art = self.tmdb_api.get_tv_images(tmdb_id)
        return art or {}

    def _fetch_fanart_art(self, media_type: str, tmdb_id: int, tvdb_id: Optional[int]) -> Dict[str, List[dict]]:
        """Fetch artwork from fanart.tv API."""
        if media_type == 'tvshow' and tvdb_id:
            art = self.fanart_api.get_tv_artwork(tvdb_id)
        else:
            art = self.fanart_api.get_movie_artwork(tmdb_id)
        return art or {}

    def _finalise_artwork(self, media_type: str, artwork: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
        """
        Finalize artwork: normalize dimensions and sort by popularity.

        Args:
            media_type: Media type
            artwork: Dict of art type -> list of artwork dicts

        Returns:
            Finalized artwork dict
        """
        if not artwork:
            return {}

        for art_type, artworks in artwork.items():
            # Apply default dimensions for fanart.tv items missing them
            dims = FANART_DIMENSIONS.get(art_type)
            if dims:
                w_default, h_default = dims
                for art in artworks:
                    source = art.get('source', '')
                    if source == 'fanart.tv' or not source:
                        if w_default and not art.get('width'):
                            art['width'] = w_default
                        if h_default and not art.get('height'):
                            art['height'] = h_default

            # Sort by popularity/quality
            artwork[art_type] = sort_artwork_by_popularity(artworks, art_type)

        return artwork

    def _fetch_season_artwork(self, season_dbid: int, season_number: Optional[int] = None) -> Dict[str, List[dict]]:
        """
        Fetch artwork for a TV season.

        Args:
            season_dbid: Kodi season database ID
            season_number: Season number (if None, will be fetched from Kodi)

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        method, id_key, result_key = KODI_GET_DETAILS_METHODS['season']
        resp = request(method, {
            id_key: season_dbid,
            'properties': ['season', 'tvshowid']
        })

        details = cast(Dict[str, Any], extract_result(resp, result_key))
        if not details:
            return {}

        if season_number is None:
            season_number = details.get('season')

        tvshow_id = details.get('tvshowid')
        if not tvshow_id or season_number is None:
            return {}

        tvshow_ids = self.get_external_ids('tvshow', tvshow_id, include_year=False)
        tmdb_id = tvshow_ids.get('tmdb_id')

        if not tmdb_id:
            return {}

        tmdb_art = self.tmdb_api.get_season_images(tmdb_id, season_number)

        return self._finalise_artwork('season', tmdb_art)

    def _fetch_episode_artwork(self, episode_dbid: int, season_number: Optional[int] = None, episode_number: Optional[int] = None) -> Dict[str, List[dict]]:
        """
        Fetch artwork for a TV episode.

        Args:
            episode_dbid: Kodi episode database ID
            season_number: Season number (if None, will be fetched from Kodi)
            episode_number: Episode number (if None, will be fetched from Kodi)

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        method, id_key, result_key = KODI_GET_DETAILS_METHODS['episode']
        resp = request(method, {
            id_key: episode_dbid,
            'properties': ['season', 'episode', 'tvshowid']
        })

        details = cast(Dict[str, Any], extract_result(resp, result_key))
        if not details:
            return {}

        if season_number is None:
            season_number = details.get('season')
        if episode_number is None:
            episode_number = details.get('episode')

        tvshow_id = details.get('tvshowid')
        if not tvshow_id or season_number is None or episode_number is None:
            return {}

        tvshow_ids = self.get_external_ids('tvshow', tvshow_id, include_year=False)
        tmdb_id = tvshow_ids.get('tmdb_id')

        if not tmdb_id:
            return {}

        tmdb_art = self.tmdb_api.get_episode_images(tmdb_id, season_number, episode_number)

        return self._finalise_artwork('episode', tmdb_art)


def validate_api_keys(tmdb_api: TMDBApi, fanart_api: FanartTVApi) -> bool:
    """
    Validate that required API keys are configured.

    Args:
        tmdb_api: TMDB API client
        fanart_api: Fanart.tv API client

    Returns:
        True if keys are valid, False otherwise
    """
    tmdb_key = tmdb_api.get_api_key()

    if not tmdb_key:
        xbmcgui.Dialog().ok(
            "Artwork reviewer - TMDB API key is required",
            "Fanart.tv API key is recommended.[CR]"
            "Settings -> Artwork reviewer -> API Keys[CR]"
            "Get free keys from:[CR]https://www.themoviedb.org/settings/api[CR]"
            "https://fanart.tv/get-an-api-key/"
        )
        return False

    # fanart.tv key is optional, just log a warning
    fanart_key = fanart_api.get_api_key()
    if not fanart_key:
        xbmc.log("SkinInfo ArtFetcher: fanart.tv API key not configured. Only TMDB artwork will be available.", xbmc.LOGWARNING)

    return True


# Global singleton instance for convenience
# Other modules can import this or create their own instance
def create_default_fetcher() -> ArtworkSourceFetcher:
    """Create default fetcher instance with default API clients."""
    from resources.lib.api.tmdb import TMDBApi
    from resources.lib.api.fanarttv import FanartTVApi
    return ArtworkSourceFetcher(TMDBApi(), FanartTVApi())
