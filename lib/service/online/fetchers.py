"""Online data fetchers: TMDB details plus OMDb, MDBList and Trakt ratings, as properties."""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

import xbmc

from lib.kodi.client import log
from lib.kodi.formatters import (
    format_rating_props,
    build_common_sense_summary,
    RATING_SOURCE_NORMALIZE,
)
from lib.kodi.utilities import MULTI_VALUE_SEP

if TYPE_CHECKING:
    from lib.service.online.main import ServiceAbortFlag


# MDBList only
_AWARD_PROPS = {
    "oscar-winner": "Awards.Oscar.Won",
    "oscar-nominated": "Awards.Oscar.Nominated",
    "best-picture-winner": "Awards.BestPicture.Won",
    "best-picture-nominated": "Awards.BestPicture.Nominated",
    "oscar-best-director-winner": "Awards.BestDirector.Won",
    "oscar-best-director-nominee": "Awards.BestDirector.Nominated",
    "golden-globe-winner": "Awards.GoldenGlobe.Won",
    "golden-globe-nominated": "Awards.GoldenGlobe.Nominated",
    "razzie-winner": "Awards.Razzie.Won",
    "razzie-nominee": "Awards.Razzie.Nominated",
    "emmy-award-winner": "Awards.Emmy.Won",
    "emmy-award-nominated": "Awards.Emmy.Nominated",
    "festival-cannes-winner": "Awards.Festival.Cannes",
    "festival-venice-winner": "Awards.Festival.Venice",
    "festival-sundance-winner": "Awards.Festival.Sundance",
    "festival-toronto-winner": "Awards.Festival.Toronto",
    "national-film-preservation-board-winner": "Awards.FilmRegistry",
    "national-film-registry": "Awards.FilmRegistry",
}

_STATUS_PROPS = {
    "tomatoes": "Tomatometer",
    "popcorn": "Popcornmeter",
    "metacritic": "Metacritic",
    "rogerebert": "RogerEbert",
}


def fetch_omdb_data(media_type: str, imdb_id: str, abort_flag=None) -> Dict[str, str]:
    """Fetch OMDb awards plus ratings (imdb/metacritic/rotten tomatoes) from the same response."""
    from lib.data.api.omdb import ApiOmdb

    props: Dict[str, str] = {}

    if not imdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    try:
        omdb = ApiOmdb()
        awards = omdb.get_awards(media_type, imdb_id, abort_flag=abort_flag)
        if awards:
            props["Awards"] = awards

        ratings = omdb.fetch_ratings(media_type, {"imdb": imdb_id}, abort_flag=abort_flag)
        if ratings:
            for source, info in ratings.items():
                if isinstance(info, dict) and "rating" in info and "votes" in info:
                    props.update(format_rating_props(source, info["rating"], int(info["votes"])))
    except Exception as e:
        log("Service", f"OMDb fetch error: {e}", xbmc.LOGWARNING)

    return props


def fetch_mdblist_data(
    media_type: str,
    imdb_id: str,
    tmdb_id: str,
    is_episode: bool,
    abort_flag=None
) -> Dict[str, str]:
    """Fetch MDBList data (extra info, common sense, ratings)."""
    from lib.data.api.mdblist import ApiMdblist

    props: Dict[str, str] = {}

    if not imdb_id and not tmdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    mdblist_media_type = "tvshow" if is_episode else media_type

    try:
        mdblist = ApiMdblist()
        ids = {"imdb": imdb_id, "tmdb": tmdb_id}

        extra_data = mdblist.get_extra_data(mdblist_media_type, ids, abort_flag=abort_flag)
        if abort_flag and abort_flag.is_requested():
            return props
        if extra_data:
            if "trailer" in extra_data:
                props["MDBList.Trailer"] = extra_data["trailer"]
            if "certification" in extra_data:
                props["MDBList.Certification"] = extra_data["certification"]

        cs_data = mdblist.get_common_sense_data(mdblist_media_type, ids, abort_flag=abort_flag)
        if abort_flag and abort_flag.is_requested():
            return props
        if cs_data:
            props["CommonSense.Age"] = str(cs_data["age"])
            props["CommonSense.Violence"] = str(cs_data["violence"])
            props["CommonSense.Nudity"] = str(cs_data["nudity"])
            props["CommonSense.Language"] = str(cs_data["language"])
            props["CommonSense.Drinking"] = str(cs_data["drinking"])
            props["CommonSense.Selection"] = "true" if cs_data["selection"] else "false"

            summary, reasons = build_common_sense_summary(cs_data)
            if summary:
                props["CommonSense.Summary"] = summary
                props["CommonSense.Reasons"] = reasons

        service_ratings = mdblist.get_service_ratings(
            mdblist_media_type, ids, abort_flag=abort_flag
        )
        if abort_flag and abort_flag.is_requested():
            return props
        if service_ratings:
            for source, rating_data in service_ratings.items():
                if (
                    isinstance(rating_data, dict)
                    and "rating" in rating_data and "votes" in rating_data
                ):
                    normalized_source = RATING_SOURCE_NORMALIZE.get(source, source)
                    props.update(format_rating_props(
                        normalized_source, rating_data["rating"], int(rating_data["votes"])
                    ))

        status = mdblist.get_rating_status(mdblist_media_type, ids, abort_flag=abort_flag)
        for source, state in (status or {}).items():
            prop = _STATUS_PROPS.get(source)
            if prop:
                props[prop] = state

        for tag in mdblist.get_award_tags(mdblist_media_type, ids, abort_flag=abort_flag):
            prop = _AWARD_PROPS.get(tag)
            if prop:
                props[prop] = "true"

        score = mdblist.get_score(mdblist_media_type, ids, abort_flag=abort_flag)
        if score is not None:
            props.update(format_rating_props("mdblistscore", score, 0))

    except Exception as e:
        log("Service", f"MDBList fetch error: {e}", xbmc.LOGWARNING)

    return props


def fetch_trakt_data(
    media_type: str,
    imdb_id: str,
    tmdb_id: str,
    is_episode: bool,
    season: Optional[int],
    episode: Optional[int],
    abort_flag=None
) -> Dict[str, str]:
    """Fetch Trakt ratings and subgenres."""
    from lib.data.api.trakt import ApiTrakt

    props: Dict[str, str] = {}

    if not imdb_id and not tmdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    try:
        trakt = ApiTrakt()
        trakt_ids: Dict[str, str] = {"imdb": imdb_id or "", "tmdb": tmdb_id or ""}
        if is_episode and season is not None and episode is not None:
            trakt_ids["season"] = str(season)
            trakt_ids["episode"] = str(episode)

        trakt_ratings = trakt.fetch_ratings(media_type, trakt_ids, abort_flag=abort_flag)
        if abort_flag and abort_flag.is_requested():
            return props
        if trakt_ratings and "trakt" in trakt_ratings:
            trakt_data = trakt_ratings["trakt"]
            props.update(format_rating_props(
                "trakt", trakt_data["rating"], int(trakt_data["votes"])
            ))

        if not is_episode:
            trakt_id = imdb_id or tmdb_id
            subgenres = trakt.get_subgenres(trakt_id, media_type, abort_flag=abort_flag)
            if subgenres:
                props["Trakt.Subgenres"] = MULTI_VALUE_SEP.join(subgenres)
    except Exception as e:
        log("Service", f"Trakt fetch error: {e}", xbmc.LOGWARNING)

    return props


def fetch_all_online_data(media_type: str, imdb_id: str, tmdb_id: str,
                          abort_flag: Optional['ServiceAbortFlag'] = None,
                          is_library_item: bool = True) -> Dict[str, str]:
    """Fetch TMDB details + ratings (OMDb/MDBList/Trakt) and return as flat property dict.

    `is_library_item=False` shortens TTL to 24h and skips season fetches.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from lib.data.api.tmdb import resolve_tmdb_id

    props: Dict[str, str] = {}
    is_episode = media_type == "episode"

    if abort_flag and abort_flag.is_requested():
        return props

    resolved_tmdb_id = resolve_tmdb_id(
        tmdb_id,
        imdb_id,
        "tvshow" if is_episode else media_type
    )

    if not imdb_id and not resolved_tmdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        if resolved_tmdb_id and not is_episode:
            futures[executor.submit(
                _fetch_tmdb_full_data,
                media_type,
                resolved_tmdb_id,
                abort_flag,
                is_library_item
            )] = "tmdb"

        if imdb_id and not is_episode:
            futures[executor.submit(
                fetch_omdb_data,
                media_type,
                imdb_id,
                abort_flag
            )] = "omdb"

        if (imdb_id or resolved_tmdb_id) and not is_episode:
            futures[executor.submit(
                fetch_mdblist_data,
                media_type,
                imdb_id,
                resolved_tmdb_id or "",
                is_episode,
                abort_flag
            )] = "mdblist"

        if imdb_id or resolved_tmdb_id:
            futures[executor.submit(
                fetch_trakt_data,
                media_type,
                imdb_id,
                resolved_tmdb_id or "",
                is_episode,
                None,
                None,
                abort_flag
            )] = "trakt"

        results: Dict[str, Dict[str, str]] = {}
        for future in as_completed(futures):
            if abort_flag and abort_flag.is_requested():
                executor.shutdown(wait=False)
                return props

            source = futures[future]
            try:
                result = future.result()
                if result:
                    results[source] = result
            except Exception as e:
                log("Service", f"Online fetch error ({source}): {e}", xbmc.LOGWARNING)

    # Merge in priority order: MDBList (richer aggregator) wins shared rating keys, OMDb
    # only backfills.
    for source in ("tmdb", "omdb", "mdblist", "trakt"):
        if source in results:
            props.update(results[source])

    return props


def fetch_tmdb_online_data(
    media_type: str,
    imdb_id: str,
    tmdb_id: str,
    abort_flag: Optional['ServiceAbortFlag'] = None,
    is_library_item: bool = True
) -> Dict[str, str]:
    """Fetch only TMDB data and return as property dictionary."""
    from lib.data.api.tmdb import resolve_tmdb_id

    is_episode = media_type == "episode"

    if abort_flag and abort_flag.is_requested():
        return {}

    resolved_tmdb_id = resolve_tmdb_id(
        tmdb_id, imdb_id, "tvshow" if is_episode else media_type
    )
    if not resolved_tmdb_id or is_episode:
        return {}

    return _fetch_tmdb_full_data(
        media_type, resolved_tmdb_id, abort_flag, is_library_item=is_library_item
    ) or {}


def _fetch_tmdb_full_data(media_type: str, tmdb_id: str,
                          abort_flag: Optional['ServiceAbortFlag'] = None,
                          is_library_item: bool = True) -> Dict[str, str]:
    """Fetch TMDB metadata and format as a property dict via `lib.kodi.formatters`."""
    from lib.data.api.tmdb import ApiTmdb
    from lib.kodi.formatters import (
        format_rating_props,
        format_movie_props,
        format_tvshow_props,
        format_credits_props,
        format_images_props,
        format_extra_props,
    )

    props: Dict[str, str] = {}

    if abort_flag and abort_flag.is_requested():
        return props

    try:
        api = ApiTmdb()
        data = api.get_complete_data(
            media_type, int(tmdb_id), abort_flag=abort_flag, is_library_item=is_library_item
        )

        if abort_flag and abort_flag.is_requested():
            return props

        if not data:
            return props

        if media_type == "movie":
            props.update(format_movie_props(data))
        else:
            props.update(format_tvshow_props(data))

        vote_avg = data.get("vote_average")
        vote_cnt = data.get("vote_count")
        if vote_avg is not None and vote_cnt is not None:
            props.update(format_rating_props("tmdb", float(vote_avg), int(vote_cnt)))

        props.update(format_credits_props(data))
        props.update(format_images_props(data))
        props.update(format_extra_props(data))

    except Exception as e:
        log("Service", f"TMDb full fetch error: {e}", xbmc.LOGWARNING)

    return props


def get_playing_artist_mbids() -> List[str]:
    """Return MusicBrainz artist IDs for the currently playing audio (or `[]`)."""
    try:
        player = xbmc.Player()
        if not player.isPlayingAudio():
            return []
        tag = player.getMusicInfoTag()
        mbids = tag.getMusicBrainzArtistID()
        if isinstance(mbids, list):
            return [m for m in mbids if m]
        return []
    except Exception:
        return []
