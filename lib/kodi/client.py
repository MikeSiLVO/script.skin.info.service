"""Kodi JSON-RPC interface with caching and rate limiting."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple, List, Callable
from time import monotonic
import threading
import urllib.parse

import xbmc
import xbmcaddon
from lib.kodi.settings import KodiSettings

# Shared addon instance - import this instead of creating new xbmcaddon.Addon()
ADDON = xbmcaddon.Addon()

CACHE_DEFAULT_TTL = 30
CACHE_CLEANUP_INTERVAL = 60
CACHE_CLEANUP_REQUEST_INTERVAL = 50
CACHE_MAX_SIZE = 200

KODI_GET_DETAILS_METHODS = {
    'movie': ('VideoLibrary.GetMovieDetails', 'movieid', 'moviedetails'),
    'tvshow': ('VideoLibrary.GetTVShowDetails', 'tvshowid', 'tvshowdetails'),
    'season': ('VideoLibrary.GetSeasonDetails', 'seasonid', 'seasondetails'),
    'episode': ('VideoLibrary.GetEpisodeDetails', 'episodeid', 'episodedetails'),
    'musicvideo': ('VideoLibrary.GetMusicVideoDetails', 'musicvideoid', 'musicvideodetails'),
    'set': ('VideoLibrary.GetMovieSetDetails', 'setid', 'setdetails'),
    'artist': ('AudioLibrary.GetArtistDetails', 'artistid', 'artistdetails'),
    'album': ('AudioLibrary.GetAlbumDetails', 'albumid', 'albumdetails'),
    'song': ('AudioLibrary.GetSongDetails', 'songid', 'songdetails'),
}

KODI_SET_DETAILS_METHODS = {
    'movie': ('VideoLibrary.SetMovieDetails', 'movieid'),
    'tvshow': ('VideoLibrary.SetTVShowDetails', 'tvshowid'),
    'season': ('VideoLibrary.SetSeasonDetails', 'seasonid'),
    'episode': ('VideoLibrary.SetEpisodeDetails', 'episodeid'),
    'musicvideo': ('VideoLibrary.SetMusicVideoDetails', 'musicvideoid'),
    'set': ('VideoLibrary.SetMovieSetDetails', 'setid'),
    'artist': ('AudioLibrary.SetArtistDetails', 'artistid'),
    'album': ('AudioLibrary.SetAlbumDetails', 'albumid'),
    'song': ('AudioLibrary.SetSongDetails', 'songid'),
}

KODI_ID_KEYS = {
    'movie': 'movieid',
    'tvshow': 'tvshowid',
    'season': 'seasonid',
    'episode': 'episodeid',
    'musicvideo': 'musicvideoid',
    'set': 'setid',
    'artist': 'artistid',
    'album': 'albumid',
    'song': 'songid',
}

KODI_GET_LIBRARY_METHODS = {
    'movie': ('VideoLibrary.GetMovies', 'movies'),
    'tvshow': ('VideoLibrary.GetTVShows', 'tvshows'),
    'season': ('VideoLibrary.GetSeasons', 'seasons'),
    'episode': ('VideoLibrary.GetEpisodes', 'episodes'),
    'musicvideo': ('VideoLibrary.GetMusicVideos', 'musicvideos'),
    'set': ('VideoLibrary.GetMovieSets', 'sets'),
    'artist': ('AudioLibrary.GetArtists', 'artists'),
    'album': ('AudioLibrary.GetAlbums', 'albums'),
    'song': ('AudioLibrary.GetSongs', 'songs'),
}

KODI_MOVIE_PROPERTIES = [
    "title", "streamdetails", "set", "setid", "ratings",
    "rating", "votes", "file", "year", "runtime", "mpaa",
    "plot", "plotoutline", "genre", "studio", "country",
    "writer", "director", "art", "tagline", "trailer",
    "originaltitle", "premiered", "lastplayed", "playcount",
    "cast", "imdbnumber", "top250", "resume", "dateadded",
    "tag", "userrating", "uniqueid"
]

_L1: Dict[str, Tuple[float, Any]] = {}
_last_cleanup = monotonic()
_request_count = 0

_CACHE_LOCK = threading.Lock()


def _cleanup_expired_cache(force: bool = False) -> None:
    """Remove expired entries from cache to prevent memory bloat.

    Args:
        force: If True, force cleanup regardless of time since last cleanup
    """
    global _last_cleanup, _request_count
    now = monotonic()

    should_cleanup = (
        force or
        (now - _last_cleanup >= CACHE_CLEANUP_INTERVAL) or
        (_request_count >= CACHE_CLEANUP_REQUEST_INTERVAL) or
        (len(_L1) > CACHE_MAX_SIZE)
    )

    if not should_cleanup:
        return

    with _CACHE_LOCK:
        _last_cleanup = now
        _request_count = 0

        expired = [k for k, v in _L1.items() if v[0] <= now]
        for k in expired:
            _L1.pop(k, None)

        if len(_L1) > CACHE_MAX_SIZE:
            import heapq
            excess = len(_L1) - CACHE_MAX_SIZE
            oldest_keys = heapq.nsmallest(excess, _L1.items(), key=lambda x: x[1][0])
            for k, _ in oldest_keys:
                _L1.pop(k, None)


def get_cache_only(cache_key: str) -> Optional[dict]:
    """Return cached value from the in-memory cache without making a JSON-RPC call.

    Args:
        cache_key: The cache key to lookup

    Returns:
        Cached dictionary if found and not expired, None otherwise
    """
    now = monotonic()
    with _CACHE_LOCK:
        ent = _L1.get(cache_key)
        if ent and ent[0] > now:
            return ent[1]
    return None


def extract_result(resp: Optional[dict], result_key: str, default=None) -> dict | list | Any:
    """Extract nested result[result_key] from JSON-RPC response.

    Args:
        resp: JSON-RPC response dictionary
        result_key: Key to extract from result (e.g., "moviedetails", "movies")
        default: Default value if extraction fails

    Returns:
        Extracted value or default (empty dict/list based on key name if default not specified)
    """
    if default is None:
        default = [] if result_key.endswith("s") and result_key != "details" else {}

    if not resp:
        return default

    result = resp.get("result")
    if not result:
        return default

    value = result.get(result_key)
    if value is None:
        return default

    return value


def request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    cache_key: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
) -> Optional[dict]:
    """Make a JSON-RPC request with caching.

    Args:
        method: The JSON-RPC method to call
        params: Parameters for the method
        cache_key: Optional cache key for storing/retrieving results
        ttl_seconds: Time-to-live for cache entry in seconds (default 30)

    Returns:
        Response dictionary or None on error
    """
    global _request_count
    ttl = CACHE_DEFAULT_TTL if ttl_seconds is None else max(1, int(ttl_seconds))

    if cache_key:
        cached = get_cache_only(cache_key)
        if cached is not None:
            return cached

    _request_count += 1
    _cleanup_expired_cache()

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }

    try:
        raw = xbmc.executeJSONRPC(json.dumps(payload, separators=(",", ":")))
    except (OSError, IOError) as e:
        log("General", f"Network error calling {method}: {str(e)}", xbmc.LOGWARNING)
        return None
    except Exception as e:
        log("General", f"Unexpected error calling {method}: {str(e)}", xbmc.LOGERROR)
        return None

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        log("General", f"JSON decode error for {method}: {str(e)}", xbmc.LOGERROR)
        return None
    except Exception as e:
        log("General", f"Error processing response for {method}: {str(e)}", xbmc.LOGERROR)
        return None

    if not isinstance(data, dict):
        log("General", f"Invalid response type for {method}: {type(data)}", xbmc.LOGWARNING)
        return None

    if "error" in data:
        error = data.get("error", {})
        log("General", f"JSON-RPC error for {method}: {error}", xbmc.LOGWARNING)
        return None

    if cache_key:
        with _CACHE_LOCK:
            try:
                result_only = data.get("result")
                if result_only is not None:
                    _L1[cache_key] = (monotonic() + float(ttl), {"result": result_only})
                else:
                    _L1[cache_key] = (monotonic() + float(ttl), data)
            except Exception as e:
                log("General", f"Failed to cache result for key '{cache_key}': {str(e)}", xbmc.LOGWARNING)

    return data


def batch_request(
    calls: List[Dict[str, Any]],
    ttl_seconds: Optional[int] = None,
) -> List[Optional[dict]]:
    """Execute multiple JSON-RPC requests in a batch.

    Args:
        calls: List of dicts with 'method', 'params', and optional 'cache_key'
        ttl_seconds: Time-to-live for cache entries in seconds

    Returns:
        List of response dictionaries (None for failed requests)
    """
    global _request_count

    if not calls:
        return []

    ttl = CACHE_DEFAULT_TTL if ttl_seconds is None else max(1, int(ttl_seconds))
    all_cached: List[Optional[dict]] = []
    all_hit = True

    for c in calls:
        key = c.get("cache_key")
        if key:
            cached = get_cache_only(key)
            all_cached.append(cached)
            if cached is None:
                all_hit = False
        else:
            all_cached.append(None)
            all_hit = False

    if all_hit:
        return all_cached

    _request_count += len(calls)
    _cleanup_expired_cache()

    payloads = []
    for i, c in enumerate(calls, 1):
        payloads.append({
            "jsonrpc": "2.0",
            "method": c.get("method"),
            "params": c.get("params") or {},
            "id": i,
        })

    try:
        raw = xbmc.executeJSONRPC(json.dumps(payloads, separators=(",", ":")))
    except (OSError, IOError) as e:
        log("General", f"Network error in batch request: {str(e)}", xbmc.LOGWARNING)
        return [None] * len(calls)
    except Exception as e:
        log("General", f"Unexpected error in batch request: {str(e)}", xbmc.LOGERROR)
        return [None] * len(calls)

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        log("General", f"JSON decode error in batch response: {str(e)}", xbmc.LOGERROR)
        return [None] * len(calls)

    if not isinstance(data, list):
        log("General", f"Invalid batch response type: {type(data)}", xbmc.LOGWARNING)
        return [None] * len(calls)

    by_id = {}
    for item in data:
        if isinstance(item, dict) and "id" in item:
            by_id[item["id"]] = item

    results: List[Optional[dict]] = []
    now = monotonic()

    with _CACHE_LOCK:
        for i, c in enumerate(calls, 1):
            resp = by_id.get(i)
            if not resp:
                results.append(None)
                continue

            results.append(resp)

            key = c.get("cache_key")
            if key and "error" not in resp:
                try:
                    result_only = resp.get("result")
                    if result_only is not None:
                        _L1[key] = (now + float(ttl), {"result": result_only})
                    else:
                        _L1[key] = (now + float(ttl), resp)
                except Exception as e:
                    log("General", f"Failed to cache batch result for key '{key}': {str(e)}", xbmc.LOGWARNING)

    return results


def get_item_details(
    media_type: str,
    dbid: int,
    properties: List[str],
    cache_key: str = "",
    ttl_seconds: Optional[int] = None,
    **extra_params: Any
) -> Any:
    """
    Get item details from Kodi library.

    Convenience wrapper around KODI_GET_DETAILS_METHODS dictionary lookups.
    Handles unpacking method info and extracting results.

    Args:
        media_type: Media type ('movie', 'tvshow', 'season', 'episode', etc.)
        dbid: Database ID of the item
        properties: List of properties to fetch
        cache_key: Optional cache key for request caching
        ttl_seconds: Optional cache TTL in seconds
        **extra_params: Additional parameters for the request payload
            (e.g., 'movies' dict for movie sets with nested properties)

    Returns:
        Dictionary of item details, or None if request fails
    """
    method_info = KODI_GET_DETAILS_METHODS.get(media_type)
    if not method_info:
        log("API", f"Unknown media type: {media_type}", xbmc.LOGERROR)
        return None

    method, id_key, result_key = method_info
    payload = {id_key: dbid, 'properties': properties}
    payload.update(extra_params)

    resp = request(method, payload, cache_key=cache_key, ttl_seconds=ttl_seconds)
    if not resp:
        return None

    return extract_result(resp, result_key)


def decode_image_url(url: str) -> str:
    """
    Decode an image:// wrapped URL to match database storage format.

    Database storage is inconsistent:
    - HTTP URLs: stored decoded (https://image.tmdb.org/...)
    - Video thumbnails: stored wrapped (image://video@...)
    - Local files: stored decoded (H:\\Movies\\poster.jpg)

    Args:
        url: URL potentially wrapped in image:// format

    Returns:
        URL in format matching database storage
    """
    if not url or not url.startswith('image://'):
        return url

    inner = url[8:-1] if url.endswith('/') else url[8:]

    if '@' in inner:
        return url

    return urllib.parse.unquote(inner)


def encode_image_url(decoded_url: str) -> str:
    """
    Wrap a decoded URL back into image:// format for xbmcvfs.File().

    Reverse operation of decode_image_url() - converts decoded URLs back to
    wrapped format that Kodi's texture cache expects.

    Args:
        decoded_url: Decoded URL (https://..., H:\\..., or image://video@...)

    Returns:
        Wrapped URL (image://.../) suitable for Kodi's texture cache
    """
    if not decoded_url:
        return decoded_url

    if decoded_url.startswith('image://'):
        return decoded_url

    encoded = urllib.parse.quote(decoded_url, safe='')
    return f'image://{encoded}/'


def _decode_art_dict(art: Dict[str, str]) -> Dict[str, str]:
    """
    Decode URLs in an art dictionary.

    Args:
        art: Dictionary mapping art types to URLs

    Returns:
        New dictionary with decoded URLs
    """
    if not art:
        return art

    decoded = {}
    for art_type, url in art.items():
        result = decode_image_url(url)

        if result.startswith('image://') and '@' in result:
            continue

        decoded[art_type] = result

    return decoded


def get_library_items(
    media_types: List[str],
    properties: List[str],
    *,
    decode_urls: bool = False,
    include_nested_seasons: bool = False,
    season_properties: Optional[List[str]] = None,
    filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch library items with configurable property selection and filtering.

    Args:
        media_types: List of media types to query ('movie', 'tvshow', etc.)
        properties: Properties to request from Kodi
        decode_urls: If True, decode image:// URLs in 'art' dict
        include_nested_seasons: If True, fetch seasons for each TV show
        season_properties: Optional properties to request for nested seasons
        filter_func: Optional function to filter items (return True to include)
        progress_callback: Optional callback(current, total, media_type)

    Returns:
        List of item dicts with standard keys plus requested properties
    """
    all_items: List[Dict[str, Any]] = []

    for idx, media_type in enumerate(media_types, 1):
        if media_type not in KODI_GET_LIBRARY_METHODS:
            continue

        method, result_key = KODI_GET_LIBRARY_METHODS[media_type]
        id_key = KODI_ID_KEYS.get(media_type, 'id')

        if progress_callback:
            progress_callback(idx, len(media_types), media_type)

        resp = request(method, {"properties": properties})
        if not resp:
            log("General", f"Failed to fetch {media_type} from library", xbmc.LOGWARNING)
            continue

        items = extract_result(resp, result_key, [])

        for item in items:
            if not isinstance(item, dict):
                continue

            item['media_type'] = media_type

            dbid = item.get(id_key)
            if dbid:
                item['dbid'] = dbid

            if decode_urls and 'art' in item and isinstance(item['art'], dict):
                item['art'] = _decode_art_dict(item['art'])

            if filter_func and not filter_func(item):
                continue

            all_items.append(item)

            if include_nested_seasons and media_type == 'tvshow' and dbid:
                tvshowid = dbid
                season_props = season_properties or properties
                seasons_resp = request("VideoLibrary.GetSeasons", {
                    "tvshowid": tvshowid,
                    "properties": season_props
                })

                if seasons_resp:
                    seasons = extract_result(seasons_resp, 'seasons', [])
                    for season in seasons:
                        if not isinstance(season, dict):
                            continue

                        season['media_type'] = 'season'
                        season['tvshowid'] = tvshowid

                        if 'file' not in season and 'file' in item:
                            season['file'] = item['file']

                        if 'showtitle' not in season and 'title' in item:
                            season['showtitle'] = item['title']

                        season_id = season.get('seasonid')
                        if season_id:
                            season['dbid'] = season_id

                        if decode_urls and 'art' in season and isinstance(season['art'], dict):
                            season['art'] = _decode_art_dict(season['art'])

                        if filter_func and not filter_func(season):
                            continue

                        all_items.append(season)

    return all_items


API_KEY_CONFIG = {
    "tmdb_api_key": {
        "name": "TMDB",
        "get_url": "https://www.themoviedb.org/settings/api",
        "setting_path": "tmdb_api_key"
    },
    "fanarttv_api_key": {
        "name": "Fanart.tv",
        "get_url": "https://fanart.tv/get-an-api-key/",
        "setting_path": "fanarttv_api_key"
    },
    "mdblist_api_key": {
        "name": "MDBList",
        "get_url": "https://mdblist.com/",
        "setting_path": "mdblist_api_key"
    },
    "omdb_api_key": {
        "name": "OMDb",
        "get_url": "https://www.omdbapi.com/apikey.aspx",
        "setting_path": "omdb_api_key"
    },
    "trakt_access_token": {
        "name": "Trakt",
        "get_url": None,
        "setting_path": "trakt_access_token",
        "token_file": "trakt_tokens.json"
    }
}


def _get_api_key(key_id: str) -> Optional[str]:
    """
    Get API key from settings.

    Args:
        key_id: Key identifier from API_KEY_CONFIG

    Returns:
        API key or None if not found
    """
    config = API_KEY_CONFIG.get(key_id)
    if not config:
        return None

    key = KodiSettings.get_string(config["setting_path"])
    if key:
        return key

    if key_id == "trakt_access_token":
        token_file = config.get("token_file")
        if token_file:
            import xbmcvfs
            token_path = xbmcvfs.translatePath(f"special://profile/addon_data/script.skin.info.service/{token_file}")
            if xbmcvfs.exists(token_path):
                try:
                    with open(token_path, 'r') as f:
                        tokens = json.load(f)
                        return tokens.get("access_token")
                except Exception:
                    pass

    return None


_debug_enabled: Optional[bool] = None
_debug_lock = threading.Lock()


def _is_debug_enabled() -> bool:
    """Check if debug logging is enabled (cached)."""
    global _debug_enabled
    if _debug_enabled is None:
        with _debug_lock:
            if _debug_enabled is None:
                try:
                    _debug_enabled = KodiSettings.debug_enabled()
                except Exception:
                    _debug_enabled = False
    return _debug_enabled


def log(category: str, message: str, level: int = xbmc.LOGDEBUG) -> None:
    """Log message with category prefix.

    Args:
        category: Category name (Artwork, Database, API, Service, Cache, General,
                  Texture, Download, Ratings, Blur, Plugin, SkinUtils, JSON)
        message: Message to log
        level: Log level (LOGDEBUG, LOGINFO, LOGWARNING, LOGERROR)
    """
    if level >= xbmc.LOGINFO or _is_debug_enabled():
        xbmc.log(f"script.skin.info.service: [{category}] {message}", level)
