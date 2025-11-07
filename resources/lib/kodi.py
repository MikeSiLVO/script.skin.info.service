"""Kodi JSON-RPC interface with caching and rate limiting."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple, List, Callable
from time import monotonic
import threading
import urllib.parse

import xbmc

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
}

KODI_SET_DETAILS_METHODS = {
    'movie': ('VideoLibrary.SetMovieDetails', 'movieid'),
    'tvshow': ('VideoLibrary.SetTVShowDetails', 'tvshowid'),
    'season': ('VideoLibrary.SetSeasonDetails', 'seasonid'),
    'episode': ('VideoLibrary.SetEpisodeDetails', 'episodeid'),
    'musicvideo': ('VideoLibrary.SetMusicVideoDetails', 'musicvideoid'),
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
    if not resp:
        if default is not None:
            return default
        return [] if result_key.endswith("s") and result_key != "details" else {}

    result = resp.get("result")
    if not result:
        if default is not None:
            return default
        return [] if result_key.endswith("s") and result_key != "details" else {}

    value = result.get(result_key)
    if value is None:
        if default is not None:
            return default
        return [] if result_key.endswith("s") and result_key != "details" else {}

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
    ttl = 30 if ttl_seconds is None else max(1, int(ttl_seconds))

    if cache_key:
        cached = get_cache_only(cache_key)
        if cached is not None:
            request._last_key = cache_key  # type: ignore[attr-defined]
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
        xbmc.log(f"SkinInfo: Network error calling {method}: {str(e)}", xbmc.LOGWARNING)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None
    except Exception as e:
        xbmc.log(f"SkinInfo: Unexpected error calling {method}: {str(e)}", xbmc.LOGERROR)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        xbmc.log(f"SkinInfo: JSON decode error for {method}: {str(e)}", xbmc.LOGERROR)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None
    except Exception as e:
        xbmc.log(f"SkinInfo: Error processing response for {method}: {str(e)}", xbmc.LOGERROR)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None

    if not isinstance(data, dict):
        xbmc.log(f"SkinInfo: Invalid response type for {method}: {type(data)}", xbmc.LOGWARNING)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None

    if "error" in data:
        error = data.get("error", {})
        xbmc.log(f"SkinInfo: JSON-RPC error for {method}: {error}", xbmc.LOGWARNING)
        request._last_key = cache_key  # type: ignore[attr-defined]
        return None

    if cache_key:
        with _CACHE_LOCK:
            try:
                # Memory optimization: Cache only the result portion, not the JSON-RPC envelope
                # The envelope ("jsonrpc", "id") is not used after response validation
                result_only = data.get("result")
                if result_only is not None:
                    _L1[cache_key] = (monotonic() + float(ttl), {"result": result_only})
                else:
                    _L1[cache_key] = (monotonic() + float(ttl), data)
            except Exception:
                pass

    request._last_key = cache_key  # type: ignore[attr-defined]
    return data


request._last_key = None  # type: ignore[attr-defined]


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

    ttl = 30 if ttl_seconds is None else max(1, int(ttl_seconds))
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
        xbmc.log(f"SkinInfo: Network error in batch request: {str(e)}", xbmc.LOGWARNING)
        # Fall back to individual requests
        return [request(c.get("method", ""), c.get("params"), c.get("cache_key"), ttl_seconds=ttl) for c in calls]
    except Exception as e:
        xbmc.log(f"SkinInfo: Unexpected error in batch request: {str(e)}", xbmc.LOGERROR)
        return [request(c.get("method", ""), c.get("params"), c.get("cache_key"), ttl_seconds=ttl) for c in calls]

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        xbmc.log(f"SkinInfo: JSON decode error in batch response: {str(e)}", xbmc.LOGERROR)
        return [request(c.get("method", ""), c.get("params"), c.get("cache_key"), ttl_seconds=ttl) for c in calls]

    if not isinstance(data, list):
        xbmc.log(f"SkinInfo: Invalid batch response type: {type(data)}", xbmc.LOGWARNING)
        # Fall back to individual requests
        return [request(c.get("method", ""), c.get("params"), c.get("cache_key"), ttl_seconds=ttl) for c in calls]

    by_id = {}
    for item in data:
        if isinstance(item, dict) and "id" in item:
            if "error" not in item:
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
            if key:
                try:
                    # Memory optimization: Cache only the result portion
                    result_only = resp.get("result")
                    if result_only is not None:
                        _L1[key] = (now + float(ttl), {"result": result_only})
                    else:
                        _L1[key] = (now + float(ttl), resp)
                except Exception:
                    pass  # Cache errors are non-critical

    return results


def get_texture_dimensions(url: str) -> Tuple[int, int]:
    """
    Get dimensions for an artwork URL from Kodi's texture cache.

    Works around Kodi bug where width and usecount fields are swapped.

    Args:
        url: Full artwork URL

    Returns:
        Tuple of (width, height), or (0, 0) if not found in cache
    """
    if not url:
        return (0, 0)

    try:
        response = request('Textures.GetTextures', {
            'properties': ['sizes'],
            'filter': {'field': 'url', 'operator': 'is', 'value': url}
        })

        if not response:
            return (0, 0)

        textures = extract_result(response, 'textures', [])
        if not textures:
            return (0, 0)

        sizes = textures[0].get('sizes', [])
        if not sizes:
            return (0, 0)

        first_size = sizes[0]
        raw_width = int(first_size.get('width', 0) or 0)
        raw_usecount = int(first_size.get('usecount', 0) or 0)
        height = int(first_size.get('height', 0) or 0)

        if raw_width < 256 and raw_usecount >= 256:
            width = raw_usecount
        else:
            width = raw_width

        return (width, height)

    except Exception as e:
        xbmc.log(f"SkinInfo: Error getting texture dimensions for {url}: {str(e)}", xbmc.LOGERROR)
        return (0, 0)


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
        if not url or not url.startswith('image://'):
            decoded[art_type] = url
            continue

        inner = url[8:-1] if url.endswith('/') else url[8:]

        if '@' in inner:
            inner = inner.split('@')[0]

        decoded[art_type] = urllib.parse.unquote(inner)

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


# API Key Validation

API_KEY_CONFIG = {
    "tmdb_api_key": {
        "name": "TMDB",
        "get_url": "https://www.themoviedb.org/settings/api",
        "setting_path": "tmdb_api_key",
        "fallback_addons": ["metadata.tvshows.themoviedb.python", "metadata.themoviedb.org"]
    },
    "fanarttv_api_key": {
        "name": "Fanart.tv",
        "get_url": "https://fanart.tv/get-an-api-key/",
        "setting_path": "fanarttv_api_key",
        "fallback_addons": ["script.artwork.downloader"]
    },
    "mdblist_api_key": {
        "name": "MDBList",
        "get_url": "https://mdblist.com/",
        "setting_path": "mdblist_api_key",
        "fallback_addons": []
    },
    "omdb_api_key": {
        "name": "OMDb",
        "get_url": "https://www.omdbapi.com/apikey.aspx",
        "setting_path": "omdb_api_key",
        "fallback_addons": []
    },
    "trakt_access_token": {
        "name": "Trakt",
        "get_url": None,
        "setting_path": "trakt_access_token",
        "fallback_addons": [],
        "token_file": "trakt_tokens.json"
    }
}


def _get_api_key(key_id: str) -> Optional[str]:
    """
    Get API key from settings with fallback support.

    Args:
        key_id: Key identifier from API_KEY_CONFIG

    Returns:
        API key or None if not found
    """
    import xbmcaddon

    config = API_KEY_CONFIG.get(key_id)
    if not config:
        return None

    addon = xbmcaddon.Addon()
    key = addon.getSetting(config["setting_path"])
    if key:
        return key

    if key_id == "tmdb_api_key":
        for fallback_id in config["fallback_addons"]:
            try:
                fallback_addon = xbmcaddon.Addon(fallback_id)
                key = fallback_addon.getSetting("api_key") or fallback_addon.getSetting("tmdb_api_key")
                if key:
                    return key
            except Exception:
                continue

    elif key_id == "fanarttv_api_key":
        for fallback_id in config["fallback_addons"]:
            try:
                fallback_addon = xbmcaddon.Addon(fallback_id)
                key = fallback_addon.getSetting("api_key") or fallback_addon.getSetting("fanarttv_api_key")
                if key:
                    return key
            except Exception:
                continue

    elif key_id == "trakt_access_token":
        token_file = config.get("token_file")
        if token_file:
            import xbmcvfs
            token_path = xbmcvfs.translatePath(f"special://profile/addon_data/script.skin.info.service/{token_file}")
            if xbmcvfs.exists(token_path):
                try:
                    with open(token_path, 'r') as f:
                        import json
                        tokens = json.load(f)
                        return tokens.get("access_token")
                except Exception:
                    pass

    return None


def validate_module_api_keys(
    module_name: str,
    required_keys: Optional[List[str]] = None,
    optional_keys: Optional[List[str]] = None,
    require_at_least_one: bool = False
) -> bool:
    """
    Universal API key validation system for modules.

    Args:
        module_name: Display name for the module (e.g., "Artwork reviewer", "Ratings updater")
        required_keys: List of required API key IDs from API_KEY_CONFIG
        optional_keys: List of optional API key IDs from API_KEY_CONFIG
        require_at_least_one: If True, requires at least one required + one optional key

    Returns:
        True if validation passes, False otherwise

    Examples:
        validate_module_api_keys(
            "Artwork reviewer",
            required_keys=["tmdb_api_key"],
            optional_keys=["fanarttv_api_key"]
        )

        validate_module_api_keys(
            "Ratings updater",
            required_keys=["tmdb_api_key"],
            optional_keys=["mdblist_api_key", "omdb_api_key", "trakt_access_token"],
            require_at_least_one=True
        )
    """
    import xbmcgui

    required_keys = required_keys or []
    optional_keys = optional_keys or []

    missing_required = []
    for key_id in required_keys:
        if not _get_api_key(key_id):
            missing_required.append(key_id)

    if missing_required:
        missing_names = [API_KEY_CONFIG[k]["name"] for k in missing_required if k in API_KEY_CONFIG]
        message = f"{module_name} requires the following API keys:\n\n" + "\n".join(f"- {name}" for name in missing_names)
        message += "\n\nPlease configure these in addon settings."
        xbmcgui.Dialog().ok(f"{module_name} - Missing API Keys", message)
        return False

    if require_at_least_one:
        has_optional = any(_get_api_key(k) for k in optional_keys)
        if not has_optional:
            optional_names = [API_KEY_CONFIG[k]["name"] for k in optional_keys if k in API_KEY_CONFIG]
            message = f"{module_name} requires at least one of the following optional API keys:\n\n"
            message += "\n".join(f"- {name}" for name in optional_names)
            message += "\n\nPlease configure at least one in addon settings."
            xbmcgui.Dialog().ok(f"{module_name} - No Optional API Keys", message)
            return False

    return True


# Debug logging
_debug_enabled: Optional[bool] = None
_debug_lock = threading.Lock()


def _is_debug_enabled() -> bool:
    """Check if debug logging is enabled (cached)."""
    global _debug_enabled
    if _debug_enabled is None:
        with _debug_lock:
            if _debug_enabled is None:
                try:
                    import xbmcaddon
                    _debug_enabled = xbmcaddon.Addon().getSettingBool('enable_debug')
                except Exception:
                    _debug_enabled = False
    return _debug_enabled


def log_artwork(message: str) -> None:
    """Log artwork-related debug message (scanner, fetcher, processor, texture ops)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [Artwork]: {message}", xbmc.LOGDEBUG)


def log_database(message: str) -> None:
    """Log database-related debug message (queue, sessions, baselines)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [Database]: {message}", xbmc.LOGDEBUG)


def log_api(message: str) -> None:
    """Log API client debug message (TMDB, fanart.tv, rate limiting)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [API]: {message}", xbmc.LOGDEBUG)


def log_service(message: str) -> None:
    """Log service operations debug message (property updates, container checks)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [Service]: {message}", xbmc.LOGDEBUG)


def log_cache(message: str) -> None:
    """Log cache operations debug message (JSON-RPC cache, hits/misses, cleanup)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [Cache]: {message}", xbmc.LOGDEBUG)


def log_general(message: str) -> None:
    """Log general debug message (utilities, misc operations)."""
    if _is_debug_enabled():
        xbmc.log(f"SkinInfo [General]: {message}", xbmc.LOGDEBUG)
