"""Ratings merger - combines ratings from multiple sources using vote count priority."""
from __future__ import annotations

import xbmc
from typing import Dict, List, Optional, Any
from lib.kodi.client import log

# only breaks a tie on vote count; a rating's owner already wins via _RATING_ORIGIN
DEFAULT_SOURCE_PRIORITY: Dict[str, int] = {
    "imdb_dataset": 110,
    "tmdb": 100,
    "trakt": 100,
    "mdblist": 90,
    "omdb": 50,
}

# Kodi scrapers are inconsistent: movies use "themoviedb", TV uses "tmdb". Mirror both
# so skins find the rating regardless of which key they check.
_KEY_ALIASES: Dict[str, str] = {
    "themoviedb": "tmdb",
    "tmdb": "themoviedb",
}


# the provider a rating belongs to; a downstream copy cannot lead it
_RATING_ORIGIN: Dict[str, str] = {
    "imdb": "imdb_dataset",
    "trakt": "trakt",
    "tmdb": "tmdb",
    "themoviedb": "tmdb",
}


def merge_ratings(sources_ratings: List[Dict[str, Any]],
                  source_priority: Optional[Dict[str, int]] = None
                  ) -> Dict[str, Dict[str, float]]:
    """Best entry per rating key: the owning provider, else the highest vote count."""
    if source_priority is None:
        source_priority = DEFAULT_SOURCE_PRIORITY

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

                origin = _RATING_ORIGIN.get(source_name)
                incoming_is_origin = origin is not None and origin == data_source
                existing_is_origin = origin is not None and origin == existing_source

                should_replace = False
                if incoming_is_origin != existing_is_origin:
                    should_replace = incoming_is_origin
                elif votes > existing_votes:
                    should_replace = True
                elif votes == existing_votes and data_priority > existing_priority:
                    should_replace = True

                if should_replace:
                    merged[source_name] = {"rating": rating, "votes": votes}
                    source_origins[source_name] = data_source

    return merged


def prepare_kodi_ratings(merged_ratings: Dict[str, Dict[str, float]],
                         default_source: str = "imdb"
                         ) -> Dict[str, Dict[str, bool | int | float]]:
    """Convert merged ratings into Kodi's `Set*Details.ratings` shape.

    All ratings must be 0-10; out-of-range values are logged ERROR and clamped to
    prevent DB corruption. Also mirrors `themoviedb <-> tmdb` since movies and TV
    use different scraper keys and skins may check either.
    """
    kodi_ratings = {}

    for source_name, rating_data in merged_ratings.items():
        rating = rating_data["rating"]
        votes = rating_data["votes"]

        if not (0.0 <= rating <= 10.0):
            log(
                "Ratings",
                f"CRITICAL - Rating out of valid range for '{source_name}': {rating:.2f} "
                f"(Kodi requires 0-10 scale). This indicates a normalization bug in rating source. "
                f"Clamping to valid range to prevent database corruption.",
                xbmc.LOGERROR,
            )
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

    for src, alias in _KEY_ALIASES.items():
        if src in kodi_ratings and alias not in kodi_ratings:
            kodi_ratings[alias] = {
                "rating": kodi_ratings[src]["rating"],
                "votes": kodi_ratings[src]["votes"],
                "default": False,
            }

    return kodi_ratings
