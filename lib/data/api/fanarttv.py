"""Fanart.tv API client for artwork.

Provides:
- Movie artwork (clearlogos, clearart, banners, discart, etc.)
- TV show artwork (clearlogos, clearart, banners, characterart, etc.)
- Season artwork (posters, banners, thumbs filtered by season number)
- Music artist artwork (fanart, thumb, clearlogo, banner)
- Album artwork (thumb, discart) via artist endpoint
"""
from __future__ import annotations

from typing import Any, Optional, List, Dict

from lib.data.api.client import ApiSession
from lib.kodi.settings import KodiSettings


class ApiFanarttv:
    """Fanart.tv API client with rate limiting."""

    BASE_URL = "https://webservice.fanart.tv/v3.2"

    API_KEY = "1fffa11cc0e558efad9c4da6b9cd2cef"

    def __init__(self):
        self.session = ApiSession(
            service_name="Fanart.tv",
            base_url=self.BASE_URL,
            timeout=(5.0, 15.0),
            max_retries=3,
            backoff_factor=1.0,
            rate_limit=(10, 1.0),
            default_headers={
                "Accept": "application/json"
            }
        )

    def get_api_key(self) -> str:
        """Get fanart.tv project API key."""
        return self.API_KEY.strip()

    def get_client_key(self) -> Optional[str]:
        """Get user's personal API key (client_key) if configured."""
        return KodiSettings.fanarttv_api_key() or None

    def _make_request(self, endpoint: str, abort_flag=None) -> Optional[dict]:
        """Make HTTP request to fanart.tv API with rate limiting and retry."""
        headers = {"api-key": self.get_api_key()}

        client_key = self.get_client_key()
        if client_key:
            headers["client-key"] = client_key

        return self.session.get(
            endpoint,
            headers=headers,
            abort_flag=abort_flag
        )

    def _format_artwork_item(self, item: dict, fanart_type: str) -> dict:
        """Format a fanart.tv artwork item to common format."""
        full_url = item.get('url', '')

        if 'banner' in fanart_type:
            preview = full_url
        else:
            preview = full_url.replace('/fanart/', '/preview/')

        artwork: Dict[str, object] = {
            'url': full_url,
            'previewurl': preview,
            'language': item.get('lang', ''),
            'likes': item.get('likes', '0'),
            'id': item.get('id', ''),
            'source': 'fanart.tv'
        }

        width = item.get('width')
        height = item.get('height')
        if width:
            artwork['width'] = int(width)
        if height:
            artwork['height'] = int(height)

        season = item.get('season')
        if season:
            artwork['season'] = season

        disc = item.get('disc')
        if disc:
            artwork['disc'] = disc
        disc_type = item.get('disc_type')
        if disc_type:
            artwork['disc_type'] = disc_type

        return artwork

    def get_movie_artwork(self, tmdb_id: int, abort_flag=None) -> dict:
        """Get all available artwork for a movie from fanart.tv."""
        data = self._make_request(f"/movies/{tmdb_id}", abort_flag)

        if not data:
            return {}

        result: Dict[str, List[dict]] = {}

        type_map = {
            'movieposter': 'poster',
            'moviebackground': 'fanart',
            'moviebackground4k': 'fanart',
            'hdmovielogo': 'clearlogo',
            'movielogo': 'clearlogo',
            'hdmovieclearart': 'clearart',
            'movieclearart': 'clearart',
            'moviebanner': 'banner',
            'moviedisc': 'discart',
            'moviethumb': 'landscape'
        }

        for fanart_type, kodi_type in type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    artwork = self._format_artwork_item(item, fanart_type)
                    result[kodi_type].append(artwork)

        return result

    def get_tv_artwork(self, tvdb_id: int, abort_flag=None) -> dict:
        """
        Get all available artwork for a TV show from fanart.tv.

        Show-level artwork is returned under standard keys (poster, fanart, etc.).
        Season-specific artwork is returned under prefixed keys (season.poster, etc.)
        with the season number in the artwork dict.
        """
        data = self._make_request(f"/tv/{tvdb_id}", abort_flag)

        if not data:
            return {}

        result: Dict[str, List[dict]] = {}

        show_type_map = {
            'tvposter': 'poster',
            'showbackground': 'fanart',
            'showbackground4k': 'fanart',
            'hdtvlogo': 'clearlogo',
            'clearlogo': 'clearlogo',
            'hdclearart': 'clearart',
            'clearart': 'clearart',
            'tvbanner': 'banner',
            'tvthumb': 'landscape',
            'characterart': 'characterart',
        }

        season_type_map = {
            'seasonposter': 'season.poster',
            'seasonbanner': 'season.banner',
            'seasonthumb': 'season.landscape',
        }

        for fanart_type, kodi_type in show_type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    artwork = self._format_artwork_item(item, fanart_type)
                    result[kodi_type].append(artwork)

        for fanart_type, kodi_type in season_type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    artwork = self._format_artwork_item(item, fanart_type)
                    result[kodi_type].append(artwork)

        return result

    def get_season_artwork(self, tvdb_id: int, season_number: int, abort_flag=None) -> dict:
        """Get artwork for a specific TV season from fanart.tv."""
        data = self._make_request(f"/tv/{tvdb_id}", abort_flag)

        if not data:
            return {}

        result: Dict[str, List[dict]] = {}
        season_str = str(season_number)

        season_type_map = {
            'seasonposter': 'poster',
            'seasonbanner': 'banner',
            'seasonthumb': 'landscape',
        }

        for fanart_type, kodi_type in season_type_map.items():
            if fanart_type in data:
                items = data[fanart_type]

                for item in items:
                    item_season = item.get('season', '')
                    if item_season == season_str or item_season == 'all':
                        if kodi_type not in result:
                            result[kodi_type] = []
                        artwork = self._format_artwork_item(item, fanart_type)
                        result[kodi_type].append(artwork)

        return result

    def get_artist_artwork(self, musicbrainz_id: str, abort_flag=None) -> dict:
        """
        Get all available artwork for a music artist from fanart.tv.

        Returns artist-level artwork and all album artwork nested under 'albums'.
        Album artwork is keyed by MusicBrainz release group ID.

        Artist artwork types:
            fanart: 1920x1080 backgrounds (artistbackground, artist4kbackground)
            thumb: 1000x1000 artist thumbnail
            clearlogo: 800x310 logo (hdmusiclogo, musiclogo)
            banner: 1000x185 banner

        Album artwork types (nested under 'albums'):
            thumb: 1000x1000 album cover (1:1 square, unlike video thumb which is 16:9)
            discart: 1000x1000 CD art

        Args:
            musicbrainz_id: MusicBrainz artist ID (MBID)
            abort_flag: Optional abort flag for cancellation

        Returns:
            Dict with artist artwork types and 'albums' dict keyed by release_group_id
        """
        data = self._make_request(f"/music/{musicbrainz_id}", abort_flag)

        if not data:
            return {}

        result: Dict[str, Any] = {}

        artist_type_map = {
            'artistbackground': 'fanart',
            'artist4kbackground': 'fanart',
            'artistthumb': 'thumb',
            'hdmusiclogo': 'clearlogo',
            'musiclogo': 'clearlogo',
            'musicbanner': 'banner',
        }

        for fanart_type, kodi_type in artist_type_map.items():
            if fanart_type in data:
                items = data[fanart_type]
                if kodi_type not in result:
                    result[kodi_type] = []

                for item in items:
                    artwork = self._format_artwork_item(item, fanart_type)
                    result[kodi_type].append(artwork)

        album_type_map = {
            'albumcover': 'thumb',
            'cdart': 'discart',
        }

        albums_data = data.get('albums', [])
        if albums_data:
            albums_result: Dict[str, Dict[str, List[dict]]] = {}

            for album in albums_data:
                release_group_id = album.get('release_group_id')
                if not release_group_id:
                    continue

                album_artwork: Dict[str, List[dict]] = {}

                for fanart_type, kodi_type in album_type_map.items():
                    if fanart_type in album:
                        items = album[fanart_type]
                        if kodi_type not in album_artwork:
                            album_artwork[kodi_type] = []

                        for item in items:
                            artwork = self._format_artwork_item(item, fanart_type)
                            album_artwork[kodi_type].append(artwork)

                if album_artwork:
                    albums_result[release_group_id] = album_artwork

            if albums_result:
                result['albums'] = albums_result

        return result

    def get_album_artwork(
        self,
        musicbrainz_artist_id: str,
        musicbrainz_release_group_id: str,
        abort_flag=None,
        cached_artist_data: Optional[dict] = None
    ) -> dict:
        """
        Get artwork for a specific album.

        Uses cached artist data if provided, otherwise fetches from API.
        This avoids duplicate API calls when processing multiple albums
        from the same artist.

        Args:
            musicbrainz_artist_id: MusicBrainz artist ID
            musicbrainz_release_group_id: MusicBrainz release group ID for the album
            abort_flag: Optional abort flag for cancellation
            cached_artist_data: Optional pre-fetched artist data from get_artist_artwork()

        Returns:
            Dict with album artwork (thumb, discart). Note: album 'thumb' is 1:1 square,
            unlike video 'thumb' which is 16:9. Dialog should handle format awareness.
        """
        if cached_artist_data is None:
            cached_artist_data = self.get_artist_artwork(musicbrainz_artist_id, abort_flag)

        if not cached_artist_data:
            return {}

        albums = cached_artist_data.get('albums', {})
        return albums.get(musicbrainz_release_group_id, {})

    def test_connection(self) -> bool:
        """Test fanart.tv API connection."""
        try:
            data = self._make_request("/movies/11")
            return data is not None and data.get('name') is not None
        except Exception:
            return False

    @staticmethod
    def get_attribution() -> str:
        """Get required fanart.tv attribution text."""
        return "Artwork provided by fanart.tv"
