"""Ratings merger - combines ratings from multiple sources using vote count priority."""
from __future__ import annotations

import xbmc
from typing import Dict, List, Optional, Any
from lib.kodi.client import log


def merge_ratings(
    sources_ratings: List[Dict[str, Any]],
    source_priority: Optional[Dict[str, int]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Merge ratings from multiple sources, keeping highest vote count for duplicates.

    Direct source APIs (TMDB, Trakt) are preferred. MDBList is preferred over OMDB
    for aggregated data (RT, Metacritic) since OMDB's RT fields are deprecated.

    Args:
        sources_ratings: List of ratings dicts from different sources, e.g.:
            [
                {"themoviedb": {"rating": 8.3, "votes": 12500}, "_source": "tmdb"},
                {"imdb": {"rating": 8.5, "votes": 750000}, "themoviedb": {"rating": 8.3, "votes": 12000}, "_source": "mdblist"},
                {"imdb": {"rating": 8.5, "votes": 850000}, "_source": "omdb"}
            ]
        source_priority: Optional dict mapping source names to priority (higher = more trusted)

    Returns:
        Merged ratings dict with highest vote counts per source:
        {
            "themoviedb": {"rating": 8.3, "votes": 12500},
            "imdb": {"rating": 8.5, "votes": 850000}
        }
    """
    if source_priority is None:
        source_priority = {
            "imdb_dataset": 110,
            "tmdb": 100,
            "trakt": 100,
            "mdblist": 90,
            "omdb": 50,
        }

    merged: Dict[str, Dict[str, float]] = {}
    source_origins: Dict[str, str] = {}

    for source_data in sources_ratings:
        if not source_data:
            continue

        data_source = source_data.get("_source", "unknown")
        data_priority = source_priority.get(data_source, 0)

        for source_name, rating_data in source_data.items():
            if source_name == "_source":
                continue

            if not isinstance(rating_data, dict):
                continue

            rating = rating_data.get("rating")
            votes = rating_data.get("votes")

            if rating is None or votes is None:
                continue

            existing = merged.get(source_name)
            if existing is None:
                merged[source_name] = {"rating": rating, "votes": votes}
                source_origins[source_name] = data_source
            else:
                existing_source = source_origins.get(source_name, "unknown")
                existing_priority = source_priority.get(existing_source, 0)
                existing_votes = existing.get("votes", 0)

                should_replace = False
                if data_priority > existing_priority:
                    should_replace = True
                elif data_priority == existing_priority and votes > existing_votes:
                    should_replace = True

                if should_replace:
                    merged[source_name] = {"rating": rating, "votes": votes}
                    source_origins[source_name] = data_source

    return merged


def prepare_kodi_ratings(
    merged_ratings: Dict[str, Dict[str, float]],
    default_source: str = "imdb"
) -> Dict[str, Dict[str, bool | int | float]]:
    """
    Convert merged ratings to Kodi JSON-RPC format.

    Validates that all ratings are on 0-10 scale as required by Kodi.
    Kodi normalizes NFO ratings using: (rating / max) * 10.0
    All ratings in database and JSON-RPC must be 0-10 scale.

    Args:
        merged_ratings: Merged ratings from merge_ratings()
        default_source: Which source to mark as default (usually "imdb")

    Returns:
        Dictionary formatted for VideoLibrary.Set*Details ratings parameter:
        {
            "imdb": {"rating": 8.5, "votes": 850000, "default": True},
            "themoviedb": {"rating": 8.3, "votes": 12500, "default": False}
        }

    Note:
        From Kodi source (VideoInfoTag.cpp):
        - Database stores ratings as 0-10 floats (no max column)
        - NFO import: r.rating = r.rating / max * 10.0f
        - NFO export: Always writes max="10"
        - JSON-RPC Video.Rating: no max field, expects 0-10 scale
    """
    kodi_ratings = {}

    for source_name, rating_data in merged_ratings.items():
        rating = rating_data["rating"]
        votes = rating_data["votes"]

        if not (0.0 <= rating <= 10.0):
            log("Ratings", f"CRITICAL - Rating out of valid range for '{source_name}': {rating:.2f} "
                f"(Kodi requires 0-10 scale). This indicates a normalization bug in rating source. "
                f"Clamping to valid range to prevent database corruption.", xbmc.LOGERROR)
            rating = max(0.0, min(10.0, rating))

        kodi_ratings[source_name] = {
            "rating": rating,
            "votes": int(votes),
            "default": source_name == default_source
        }

    if default_source in kodi_ratings:
        kodi_ratings[default_source]["default"] = True
    elif kodi_ratings:
        first_source = next(iter(kodi_ratings))
        kodi_ratings[first_source]["default"] = True

    return kodi_ratings
