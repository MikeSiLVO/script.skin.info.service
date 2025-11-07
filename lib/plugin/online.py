"""Fetch online API data for plugin path.

This module provides API fetchers for external data sources (OMDb, MDBList, Trakt).
Used by lib.service.online.fetch_all_online_data.
"""
from __future__ import annotations

from typing import Dict, Optional

import xbmc

from lib.kodi.client import log
from lib.kodi.formatters import format_rating_props, build_common_sense_summary, RATING_SOURCE_NORMALIZE


def _fetch_omdb_data(imdb_id: str, abort_flag=None) -> Dict[str, str]:
    """Fetch OMDb awards data."""
    from lib.data.api.omdb import ApiOmdb

    props: Dict[str, str] = {}

    if not imdb_id:
        return props

    if abort_flag and abort_flag.is_requested():
        return props

    try:
        omdb = ApiOmdb()
        awards_data = omdb.get_awards(imdb_id, abort_flag=abort_flag)
        if awards_data:
            props["Awards.Oscar.Wins"] = str(awards_data.get("oscar_wins", 0))
            props["Awards.Oscar.Nominations"] = str(awards_data.get("oscar_nominations", 0))
            props["Awards.Emmy.Wins"] = str(awards_data.get("emmy_wins", 0))
            props["Awards.Emmy.Nominations"] = str(awards_data.get("emmy_nominations", 0))
            props["Awards.Other.Wins"] = str(awards_data.get("other_wins", 0))
            props["Awards.Other.Nominations"] = str(awards_data.get("other_nominations", 0))
            props["Awards"] = awards_data.get("awards_text", "")
    except Exception as e:
        log("Plugin", f"OMDb fetch error: {e}", xbmc.LOGWARNING)

    return props


def _fetch_mdblist_data(
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

        service_ratings = mdblist.get_service_ratings(mdblist_media_type, ids, abort_flag=abort_flag)
        if abort_flag and abort_flag.is_requested():
            return props
        if service_ratings:
            for source, rating_data in service_ratings.items():
                if isinstance(rating_data, dict) and "rating" in rating_data and "votes" in rating_data:
                    normalized_source = RATING_SOURCE_NORMALIZE.get(source, source)
                    props.update(format_rating_props(normalized_source, rating_data["rating"], int(rating_data["votes"])))

        rt_status = mdblist.get_rt_status(mdblist_media_type, ids, abort_flag=abort_flag)
        if rt_status:
            # Set Tomatometer: Certified > Fresh > Rotten
            if rt_status.get("certified"):
                props["Tomatometer"] = "Certified"
            elif rt_status.get("fresh"):
                props["Tomatometer"] = "Fresh"
            elif rt_status.get("rotten"):
                props["Tomatometer"] = "Rotten"

            # Set Popcornmeter: Hot > Fresh > Spilled
            if rt_status.get("hot"):
                props["Popcornmeter"] = "Hot"
            elif rt_status.get("popcorn"):
                props["Popcornmeter"] = "Fresh"
            elif rt_status.get("stale"):
                props["Popcornmeter"] = "Spilled"

    except Exception as e:
        log("Plugin", f"MDBList fetch error: {e}", xbmc.LOGWARNING)

    return props


def _fetch_trakt_data(
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
            props.update(format_rating_props("trakt", trakt_data["rating"], int(trakt_data["votes"])))

        if not is_episode:
            trakt_id = imdb_id or tmdb_id
            subgenres = trakt.get_subgenres(trakt_id, media_type, abort_flag=abort_flag)
            if subgenres:
                props["Trakt.Subgenres"] = " / ".join(subgenres)
    except Exception as e:
        log("Plugin", f"Trakt fetch error: {e}", xbmc.LOGWARNING)

    return props
