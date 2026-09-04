"""Online service helpers: cache key, TTL derivation, ID resolution."""
from __future__ import annotations

from typing import Optional, Tuple

import xbmc

from lib.data.database.cache import CacheKey, invalidate_online_properties


def get_online_ttl(media_type: str, tmdb_id: str) -> int:
    """Derive smart TTL from cached TMDB metadata for online properties cache."""
    from lib.data.database.cache import get_title_ttl_hours

    return get_title_ttl_hours(media_type, tmdb_id) or 72


def invalidate_online_cache(media_type: str, imdb_id: str = '', tmdb_id: str = '') -> None:
    """Invalidate the online properties cache for a specific library item."""
    invalidate_online_properties(media_type, imdb_id=imdb_id, tmdb_id=tmdb_id)


def invalidate_online_cache_for_dbid(media_type: str, dbid: str) -> None:
    """Resolve uniqueids for a library item and drop its cached online data."""
    from lib.kodi.client import get_item_uniqueids
    imdb_id, tmdb_id = get_item_uniqueids(media_type, dbid)
    if imdb_id or tmdb_id:
        invalidate_online_properties(media_type, imdb_id=imdb_id, tmdb_id=tmdb_id)


def make_cache_key(media_type: str, imdb_id: str, tmdb_id: str,
                   scope: str = '') -> Optional[CacheKey]:
    """Build a stable cache key. TMDB preferred (earlier-resolved, consistent), IMDb fallback."""
    item_id = tmdb_id or imdb_id
    return CacheKey(media_type, item_id, scope) if item_id else None


def resolve_ids_from(dbtype: str, dbid: str, info_prefix: str) -> Tuple[str, str]:
    """Resolve `(imdb_id, tmdb_id)`: InfoLabel -> ID map -> JSON-RPC fallback."""
    imdb_id = xbmc.getInfoLabel(f"{info_prefix}.UniqueID(imdb)") or ""
    tmdb_id = xbmc.getInfoLabel(f"{info_prefix}.UniqueID(tmdb)") or ""

    if not imdb_id:
        imdbnumber = xbmc.getInfoLabel(f"{info_prefix}.IMDBNumber") or ""
        if imdbnumber.startswith("tt"):
            imdb_id = imdbnumber

    if not imdb_id and tmdb_id:
        from lib.data.database.mapping import get_imdb_id
        cache_type = "tvshow" if dbtype == "episode" else dbtype
        imdb_id = get_imdb_id(tmdb_id, cache_type) or ""

    if not imdb_id and not tmdb_id:
        from lib.kodi.client import get_item_uniqueids
        imdb_id, tmdb_id = get_item_uniqueids(dbtype, dbid)

    return imdb_id, tmdb_id


def resolve_season_ids(seasonid: str) -> Tuple[str, str]:
    """Resolve IMDb/TMDb IDs for a season via its parent tvshow."""
    from lib.kodi.client import get_item_details, get_item_uniqueids
    details = get_item_details('season', int(seasonid), ["tvshowid"])
    if not details or not isinstance(details, dict):
        return "", ""
    tvshowid = details.get("tvshowid")
    if not tvshowid or tvshowid == -1:
        return "", ""
    return get_item_uniqueids("tvshow", str(tvshowid))
