"""External API fetching and caching for artwork.

Centralizes retrieval of artwork from TMDB and fanart.tv APIs.
Handles caching, batch fetching, and dimension normalization.
"""
from __future__ import annotations

import xbmc
from typing import Optional, Dict, List, Any

from lib.data import database as db
from lib.data.api.tmdb import ApiTmdb
from lib.data.api.fanarttv import ApiFanarttv
from lib.kodi.client import get_item_details, KODI_GET_DETAILS_METHODS
from lib.artwork.utilities import sort_artwork_by_popularity
from lib.artwork.config import CACHE_ART_TYPES
from lib.kodi.client import log


class ApiArtworkFetcher:
    """
    Centralized helper for retrieving and caching artwork from external APIs.

    Fetches artwork from TMDB and fanart.tv, caches results with dynamic TTL
    based on media age, and provides batch fetching to minimize API calls.
    """

    def __init__(self, tmdb_api: ApiTmdb, fanart_api: ApiFanarttv):
        """
        Initialize fetcher with API clients.

        Args:
            tmdb_api: TMDB API client instance
            fanart_api: Fanart.tv API client instance
        """
        self.tmdb_api = tmdb_api
        self.fanart_api = fanart_api

    def get_external_ids(self, media_type: str, dbid: int) -> dict:
        """
        Get external IDs AND release date from Kodi library.

        Args:
            media_type: Media type (movie, tvshow, episode, etc.)
            dbid: Kodi database ID

        Returns:
            {
                'tmdb_id': int,
                'tvdb_id': int,
                'release_date': str  # YYYY-MM-DD from Kodi
            }
        """
        if media_type not in KODI_GET_DETAILS_METHODS:
            return {}

        properties = ['uniqueid']

        if media_type in ('movie', 'tvshow', 'set'):
            properties.append('premiered')
        elif media_type == 'episode':
            properties.append('firstaired')

        try:
            details = get_item_details(media_type, dbid, properties)
        except Exception as e:
            log("API", f"Error getting external IDs for {media_type}:{dbid}: {e}", xbmc.LOGERROR)
            return {}

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

        result['release_date'] = details.get('premiered') or details.get('firstaired')

        return result

    def fetch_all(self, media_type: str, dbid: int, season_number: Optional[int] = None, episode_number: Optional[int] = None, bypass_cache: bool = False) -> Dict[str, List[dict]]:
        """
        Fetch ALL artwork types for an item in a single operation.

        This is the PERFORMANCE-CRITICAL method that minimizes API calls by:
        1. Checking cache first (with completion marker) unless bypass_cache=True
        2. Fetching ALL art types from TMDB + fanart.tv in one go
        3. Caching all results with simplified dynamic TTL (24hr/3day/7day based on age)

        Args:
            media_type: Media type (movie, tvshow, season, episode, set)
            dbid: Kodi database ID
            season_number: Season number (for seasons/episodes)
            episode_number: Episode number (for episodes)
            bypass_cache: If True, skip cache check and fetch fresh data (for manual review)

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        if media_type == 'season':
            return self._fetch_season_artwork(dbid, season_number)
        elif media_type == 'episode':
            return self._fetch_episode_artwork(dbid, season_number, episode_number)
        elif media_type == 'set':
            return self._fetch_movieset_artwork(dbid)
        elif media_type == 'artist':
            return self._fetch_artist_artwork(dbid, bypass_cache=bypass_cache)
        elif media_type == 'album':
            return self._fetch_album_artwork(dbid, bypass_cache=bypass_cache)
        elif media_type not in ('movie', 'tvshow'):
            return {}

        ids = self.get_external_ids(media_type, dbid)
        tmdb_id = ids.get('tmdb_id')
        tvdb_id = ids.get('tvdb_id')
        release_date = ids.get('release_date')

        if not tmdb_id:
            return {}

        ttl_hours = db.get_cache_ttl_hours(release_date)
        cache_marker_type = '_full_fetch_complete'

        if not bypass_cache:
            cached_marker = db.get_cached_artwork(media_type, str(tmdb_id), 'system', cache_marker_type)

            if cached_marker is not None:
                cached_art = self._load_cached_artwork(media_type, tmdb_id, tvdb_id)
                return self._finalise_artwork(media_type, cached_art)

        all_art: Dict[str, List[dict]] = {}

        complete_data = self.tmdb_api.get_complete_data(
            media_type, tmdb_id, release_date, force_refresh=bypass_cache
        )

        if complete_data and 'images' in complete_data:
            images = complete_data['images']
            tmdb_art = self._transform_complete_images(images)
            for art_type, artworks in tmdb_art.items():
                all_art.setdefault(art_type, []).extend(artworks)

        fanart_items = self._fetch_fanart_art(media_type, tmdb_id, tvdb_id)
        for art_type, artworks in fanart_items.items():
            if artworks:
                cache_id = str(tvdb_id) if tvdb_id and media_type == 'tvshow' else str(tmdb_id)
                db.cache_artwork(media_type, cache_id, 'fanarttv', art_type, artworks, release_date, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        if tmdb_id:
            db.cache_artwork(media_type, str(tmdb_id), 'system', cache_marker_type, [{'marker': 'complete'}], release_date, ttl_hours)

        finalised = self._finalise_artwork(media_type, all_art)

        total_items = sum(len(v) for v in finalised.values())
        source_summary = [f"{key}:{len(values)}" for key, values in finalised.items()]
        log("Artwork", f"Fetched {media_type}:{dbid} - {total_items} art items ({', '.join(source_summary)})")

        return finalised

    def fetch_by_type(self, media_type: str, dbid: int, art_type: str) -> List[dict]:
        """
        Fetch artwork for a single art type.

        Note: This still calls fetch_all() internally for efficiency.

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
        cache_id = str(tvdb_id) if tvdb_id and media_type == 'tvshow' else str(tmdb_id)

        media_ids = {
            'tmdb': str(tmdb_id),
            'fanarttv': cache_id
        }

        batch_results = db.get_cached_artwork_batch(media_type, media_ids, CACHE_ART_TYPES)

        cached: Dict[str, List[dict]] = {}
        for (_source, art_type), artworks in batch_results.items():
            cached.setdefault(art_type, []).extend(artworks)

        return cached

    def _load_music_cached_artwork(self, media_type: str, mbid: str) -> Dict[str, List[dict]]:
        music_art_types = ['thumb', 'fanart', 'clearlogo', 'banner', 'discart']
        media_ids = {'fanarttv': mbid, 'theaudiodb': mbid}

        batch_results = db.get_cached_artwork_batch(media_type, media_ids, music_art_types)

        cached: Dict[str, List[dict]] = {}
        for (_source, art_type), artworks in batch_results.items():
            cached.setdefault(art_type, []).extend(artworks)

        return cached

    def _transform_complete_images(self, images: dict) -> Dict[str, List[dict]]:
        """
        Transform images from complete_data response to artwork format.

        Raw TMDB images have file_path but need url/previewurl/source for the dialog.

        All backdrops go to landscape, sorted by language preference:
        1. User's configured language
        2. English (if not user's language)
        3. No language (clean images)
        4. Other languages (foreign text least useful)

        Only no-language backdrops go to fanart (text-free backgrounds).
        """
        from lib.kodi.settings import KodiSettings

        result: Dict[str, List[dict]] = {}

        mapping = (
            ('posters', 'poster', 'w500'),
            ('logos', 'clearlogo', 'w500'),
        )

        for source_key, result_key, preview_size in mapping:
            entries = images.get(source_key) or []
            formatted = [self._format_tmdb_image(entry, preview_size) for entry in entries]
            formatted = [entry for entry in formatted if entry]
            if formatted:
                result[result_key] = formatted

        backdrops = images.get('backdrops') or []
        if not backdrops:
            return result

        user_lang = KodiSettings.online_metadata_language().split('-')[0].lower()

        formatted_backdrops: List[tuple[dict, str | None]] = []
        for backdrop in backdrops:
            formatted = self._format_tmdb_image(backdrop, 'w780')
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

    def _format_tmdb_image(self, image: dict, preview_size: str) -> Optional[dict]:
        """Format raw TMDB image entry to common artwork format."""
        file_path = image.get('file_path')
        if not file_path:
            return None

        # Skip SVG files - Kodi cannot render them
        if file_path.lower().endswith('.svg'):
            return None

        return {
            'url': f"https://image.tmdb.org/t/p/original{file_path}",
            'previewurl': f"https://image.tmdb.org/t/p/{preview_size}{file_path}",
            'width': image.get('width', 0),
            'height': image.get('height', 0),
            'rating': image.get('vote_average', 0),
            'language': image.get('iso_639_1') or '',
            'source': 'TMDB'
        }

    def _fetch_tmdb_art(self, media_type: str, tmdb_id: int) -> Dict[str, List[dict]]:
        if media_type == 'movie':
            art = self.tmdb_api.get_movie_images(tmdb_id)
        else:
            art = self.tmdb_api.get_tv_images(tmdb_id)
        return art or {}

    def _fetch_fanart_art(self, media_type: str, tmdb_id: int, tvdb_id: Optional[int]) -> Dict[str, List[dict]]:
        if media_type == 'tvshow' and tvdb_id:
            art = self.fanart_api.get_tv_artwork(tvdb_id)
        else:
            art = self.fanart_api.get_movie_artwork(tmdb_id)
        return art or {}

    def _finalise_artwork(self, _media_type: str, artwork: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
        """
        Finalize artwork: sort by popularity.

        Args:
            media_type: Media type
            artwork: Dict of art type -> list of artwork dicts

        Returns:
            Finalized artwork dict
        """
        if not artwork:
            return {}

        for art_type, artworks in artwork.items():
            artwork[art_type] = sort_artwork_by_popularity(artworks, art_type)

        return artwork

    def _fetch_season_artwork(self, season_dbid: int, season_number: Optional[int] = None) -> Dict[str, List[dict]]:
        """Fetch artwork for a TV season from TMDB and fanart.tv."""
        details = get_item_details('season', season_dbid, ['season', 'tvshowid'])
        if not isinstance(details, dict):
            return {}

        if season_number is None:
            season_number = details.get('season')

        tvshow_id = details.get('tvshowid')
        if not tvshow_id or season_number is None:
            return {}

        tvshow_ids = self.get_external_ids('tvshow', tvshow_id)
        tmdb_id = tvshow_ids.get('tmdb_id')
        tvdb_id = tvshow_ids.get('tvdb_id')

        if not tmdb_id:
            return {}

        all_art: Dict[str, List[dict]] = {}

        tmdb_art = self.tmdb_api.get_season_images(tmdb_id, season_number)
        for art_type, artworks in tmdb_art.items():
            all_art.setdefault(art_type, []).extend(artworks)

        if tvdb_id:
            fanart_art = self.fanart_api.get_season_artwork(tvdb_id, season_number)
            for art_type, artworks in fanart_art.items():
                all_art.setdefault(art_type, []).extend(artworks)

        return self._finalise_artwork('season', all_art)

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
        details = get_item_details('episode', episode_dbid, ['season', 'episode', 'tvshowid'])
        if not isinstance(details, dict):
            return {}

        if season_number is None:
            season_number = details.get('season')
        if episode_number is None:
            episode_number = details.get('episode')

        tvshow_id = details.get('tvshowid')
        if not tvshow_id or season_number is None or episode_number is None:
            return {}

        tvshow_ids = self.get_external_ids('tvshow', tvshow_id)
        tmdb_id = tvshow_ids.get('tmdb_id')

        if not tmdb_id:
            return {}

        tmdb_art = self.tmdb_api.get_episode_images(tmdb_id, season_number, episode_number)

        return self._finalise_artwork('episode', tmdb_art)

    def _fetch_movieset_artwork(self, set_dbid: int) -> Dict[str, List[dict]]:
        """
        Fetch artwork for a movie set (collection).

        Args:
            set_dbid: Kodi set database ID

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        details = get_item_details(
            'set',
            set_dbid,
            ['title'],
            movies={
                'properties': ['uniqueid'],
                'limits': {'end': 1}
            }
        )
        if not isinstance(details, dict):
            return {}

        movies = details.get('movies', [])
        if not movies:
            return {}

        first_movie_ids = movies[0].get('uniqueid', {})
        movie_tmdb_id = first_movie_ids.get('tmdb')

        if not movie_tmdb_id:
            return {}

        movie_details = self.tmdb_api._make_request(f"/movie/{movie_tmdb_id}")

        if not movie_details:
            return {}

        belongs_to = movie_details.get('belongs_to_collection')
        if not belongs_to:
            return {}

        collection_id = belongs_to.get('id')
        if not collection_id:
            return {}

        all_art: Dict[str, List[dict]] = {}

        tmdb_art = self.tmdb_api.get_collection_images(collection_id)
        for art_type, artworks in tmdb_art.items():
            if artworks:
                all_art.setdefault(art_type, []).extend(artworks)

        fanart_art = self.fanart_api.get_movie_artwork(collection_id)
        for art_type, artworks in fanart_art.items():
            if artworks:
                all_art.setdefault(art_type, []).extend(artworks)

        return self._finalise_artwork('set', all_art)

    def _fetch_artist_artwork(self, artist_dbid: int, bypass_cache: bool = False) -> Dict[str, List[dict]]:
        """
        Fetch artwork for a music artist from fanart.tv.

        Args:
            artist_dbid: Kodi artist database ID
            bypass_cache: Skip cache check and fetch fresh data

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        details = get_item_details('artist', artist_dbid, ['musicbrainzartistid'])
        if not isinstance(details, dict):
            return {}

        mbid = details.get('musicbrainzartistid')
        if not mbid:
            log("Artwork", f"No MusicBrainz ID for artist {artist_dbid}", xbmc.LOGWARNING)
            return {}

        if isinstance(mbid, list):
            mbid = mbid[0] if mbid else None
        if not mbid:
            return {}

        ttl_hours = db.get_fanarttv_cache_ttl_hours()
        cache_marker_type = '_full_fetch_complete'

        if not bypass_cache:
            cached_marker = db.get_cached_artwork('artist', mbid, 'system', cache_marker_type)
            if cached_marker is not None:
                cached_art = self._load_music_cached_artwork('artist', mbid)
                return self._finalise_artwork('artist', cached_art)

        all_art: Dict[str, List[dict]] = {}

        fanart_art = self.fanart_api.get_artist_artwork(mbid)
        for art_type, artworks in fanart_art.items():
            if art_type != 'albums' and artworks:
                db.cache_artwork('artist', mbid, 'fanarttv', art_type, artworks, None, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        from lib.data.api.audiodb import ApiAudioDb
        audiodb = ApiAudioDb()
        audiodb_art = audiodb.get_artist_artwork(mbid)
        for art_type, artworks in audiodb_art.items():
            if artworks:
                db.cache_artwork('artist', mbid, 'theaudiodb', art_type, artworks, None, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        db.cache_artwork('artist', mbid, 'system', cache_marker_type, [{'marker': 'complete'}], None, ttl_hours)

        return self._finalise_artwork('artist', all_art)

    def _fetch_album_artwork(self, album_dbid: int, bypass_cache: bool = False) -> Dict[str, List[dict]]:
        """
        Fetch artwork for a music album from fanart.tv and TheAudioDB.

        Uses artist endpoint and extracts album-specific artwork by release group ID.
        Falls back to TheAudioDB name search if the release group ID is stale (merged
        on MusicBrainz but not updated on artwork services).

        Args:
            album_dbid: Kodi album database ID
            bypass_cache: Skip cache check and fetch fresh data

        Returns:
            Dict mapping art types to lists of artwork dicts
        """
        details = get_item_details('album', album_dbid, [
            'musicbrainzalbumartistid',
            'musicbrainzreleasegroupid',
            'title',
            'displayartist'
        ])
        if not isinstance(details, dict):
            return {}

        artist_mbid = details.get('musicbrainzalbumartistid')
        release_group_id = details.get('musicbrainzreleasegroupid')

        if isinstance(artist_mbid, list):
            artist_mbid = artist_mbid[0] if artist_mbid else None
        if not artist_mbid:
            log("Artwork", f"No MusicBrainz artist ID for album {album_dbid}", xbmc.LOGWARNING)
            return {}

        if not release_group_id:
            log("Artwork", f"No MusicBrainz release group ID for album {album_dbid}", xbmc.LOGWARNING)
            return {}

        ttl_hours = db.get_fanarttv_cache_ttl_hours()
        cache_marker_type = '_full_fetch_complete'

        if not bypass_cache:
            cached_marker = db.get_cached_artwork('album', release_group_id, 'system', cache_marker_type)
            if cached_marker is not None:
                cached_art = self._load_music_cached_artwork('album', release_group_id)
                return self._finalise_artwork('album', cached_art)

        all_art: Dict[str, List[dict]] = {}

        log("Artwork", f"Album {album_dbid}: looking up release_group={release_group_id}, artist={artist_mbid}", xbmc.LOGDEBUG)

        artist_data = self.fanart_api.get_artist_artwork(artist_mbid)
        albums = artist_data.get('albums', {})
        album_art = albums.get(release_group_id, {})

        # Stale ID fallback: try cached mapping or TheAudioDB name search
        resolved_old_id: Optional[str] = None
        audiodb_search_result: Optional[dict] = None

        if not album_art and albums:
            resolved_old_id, audiodb_search_result = self._resolve_album_id_mismatch(
                album_dbid, release_group_id, albums, details
            )
            if resolved_old_id:
                album_art = albums.get(resolved_old_id, {})

        if not album_art and not albums:
            log("Artwork", f"Album {album_dbid}: no album artwork on Fanart.tv for artist {artist_mbid}", xbmc.LOGDEBUG)

        for art_type, artworks in album_art.items():
            if artworks:
                db.cache_artwork('album', release_group_id, 'fanarttv', art_type, artworks, None, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        from lib.data.api.audiodb import ApiAudioDb
        audiodb = ApiAudioDb()

        album_data: Optional[dict] = None
        if audiodb_search_result:
            album_data = audiodb_search_result
        else:
            lookup_id = resolved_old_id or release_group_id
            album_data = audiodb.get_album(lookup_id)
            if not album_data and resolved_old_id:
                album_data = audiodb.get_album(release_group_id)

        audiodb_art: Dict[str, List[dict]] = {}
        if album_data:
            audiodb_art = audiodb.get_album_artwork_from_data(album_data)
        else:
            log("Artwork", f"Album {album_dbid}: no data on TheAudioDB for release_group={release_group_id}", xbmc.LOGDEBUG)

        for art_type, artworks in audiodb_art.items():
            if artworks:
                db.cache_artwork('album', release_group_id, 'theaudiodb', art_type, artworks, None, ttl_hours)
                all_art.setdefault(art_type, []).extend(artworks)

        db.cache_artwork('album', release_group_id, 'system', cache_marker_type, [{'marker': 'complete'}], None, ttl_hours)

        return self._finalise_artwork('album', all_art)

    def _resolve_album_id_mismatch(
        self,
        album_dbid: int,
        canonical_id: str,
        fanart_albums: Dict[str, Any],
        album_details: dict
    ) -> tuple:
        """
        Resolve stale MusicBrainz release group ID via cached mapping or TheAudioDB name search.

        Returns:
            Tuple of (old_id or None, audiodb_search_result or None)
        """
        # Check cached mapping first
        cached_old_ids = db.get_mb_id_mappings_by_canonical(canonical_id)
        for old_id in cached_old_ids:
            if old_id in fanart_albums:
                log("Artwork", f"Album {album_dbid}: resolved via cached mapping {old_id} -> {canonical_id}", xbmc.LOGDEBUG)
                return old_id, None

        # Fall back to TheAudioDB name search
        album_title = album_details.get('title', '')
        artist_name = album_details.get('displayartist', '')
        if not album_title or not artist_name:
            log("Artwork", f"Album {album_dbid}: release_group={canonical_id} not found on Fanart.tv, "
                "cannot search (missing title/artist)", xbmc.LOGDEBUG)
            return None, None

        log("Artwork", f"Album {album_dbid}: ID mismatch, searching TheAudioDB for '{artist_name}' - '{album_title}'", xbmc.LOGDEBUG)

        from lib.data.api.audiodb import ApiAudioDb
        audiodb = ApiAudioDb()

        try:
            search_result = audiodb.search_album(artist_name, album_title)
        except Exception as e:
            log("Artwork", f"Album {album_dbid}: TheAudioDB search failed: {e}", xbmc.LOGWARNING)
            return None, None

        if not search_result:
            log("Artwork", f"Album {album_dbid}: not found on TheAudioDB by name search", xbmc.LOGDEBUG)
            return None, None

        tadb_mbid = search_result.get('strMusicBrainzID', '')
        if not tadb_mbid or tadb_mbid == canonical_id:
            return None, search_result

        # Found an old ID — cache the mapping
        db.save_mb_id_mapping(tadb_mbid, canonical_id)
        log("Artwork", f"Album {album_dbid}: resolved stale ID {tadb_mbid} -> {canonical_id} via TheAudioDB", xbmc.LOGINFO)

        if tadb_mbid in fanart_albums:
            return tadb_mbid, search_result

        log("Artwork", f"Album {album_dbid}: TheAudioDB has ID {tadb_mbid} but not found on Fanart.tv either", xbmc.LOGDEBUG)
        return None, search_result


# Global singleton instance for convenience
# Other modules can import this or create their own instance
def create_default_fetcher() -> ApiArtworkFetcher:
    """Create default fetcher instance with default API clients."""
    from lib.data.api.tmdb import ApiTmdb
    from lib.data.api.fanarttv import ApiFanarttv
    return ApiArtworkFetcher(ApiTmdb(), ApiFanarttv())
