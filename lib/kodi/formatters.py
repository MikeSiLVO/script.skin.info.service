"""
Formatters for converting API responses to Kodi-style property dicts.

Maps API field names to Kodi InfoLabel equivalents where applicable.
"""
from typing import Dict, Tuple

import xbmcaddon

from lib.kodi.utils import format_date

RT_SOURCE_TOMATOES = "tomatoes"
RT_SOURCE_POPCORN = "popcorn"

RATING_SOURCE_NORMALIZE = {
    "tomatometerallcritics": RT_SOURCE_TOMATOES,
    "tomatometerallaudience": RT_SOURCE_POPCORN,
    "tomatoes": RT_SOURCE_TOMATOES,
    "popcorn": RT_SOURCE_POPCORN,
    "themoviedb": "tmdb",
}

# Sources that use Tomatometer (critics)
TOMATOMETER_SOURCES = frozenset((RT_SOURCE_TOMATOES,))

# Sources that use Popcornmeter (audience)
POPCORN_SOURCES = frozenset((RT_SOURCE_POPCORN,))


def format_number(value) -> str:
    """Format number with thousand separators."""
    if not value:
        return ""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def format_rating_props(source: str, rating: float, votes: int) -> Dict[str, str]:
    """Format rating data into property dict for a given source."""
    scaled = round(rating, 1)
    pct = max(0, min(100, int(round(scaled * 10))))
    return {
        f"Rating.{source}": str(scaled),
        f"Rating.{source}.Votes": format_number(votes),
        f"Rating.{source}.Percent": str(pct)
    }


def format_movie_props(data: dict) -> Dict[str, str]:
    """Format movie-specific properties from TMDB data."""
    props: Dict[str, str] = {}

    props["Title"] = data.get("title") or ""
    props["OriginalTitle"] = data.get("original_title") or ""
    props["Plot"] = data.get("overview") or ""
    props["Tagline"] = data.get("tagline") or ""
    props["Status"] = data.get("status") or ""
    props["Runtime"] = str(data.get("runtime") or "")
    props["Popularity"] = str(data.get("popularity") or "")
    props["Homepage"] = data.get("homepage") or ""

    release_date = data.get("release_date") or ""
    if release_date:
        props["Premiered"] = release_date
        props["PremieredFormatted"] = format_date(release_date)
        try:
            props["Year"] = release_date[:4]
        except (IndexError, TypeError):
            pass

    genres = data.get("genres") or []
    if genres:
        props["Genre"] = " / ".join(g.get("name", "") for g in genres if g.get("name"))

    countries = data.get("production_countries") or []
    if countries:
        props["Country"] = " / ".join(c.get("name", "") for c in countries if c.get("name"))

    studios = data.get("production_companies") or []
    if studios:
        props["Studio"] = " / ".join(s.get("name", "") for s in studios if s.get("name"))

    budget = data.get("budget") or 0
    revenue = data.get("revenue") or 0
    props["Budget"] = f"{budget:,}" if budget else ""
    props["Revenue"] = f"{revenue:,}" if revenue else ""

    collection = data.get("belongs_to_collection")
    if collection:
        props["Set"] = collection.get("name") or ""
        props["SetID"] = str(collection.get("id") or "")

    add_certification_props(props, data)
    add_trailer_props(props, data)
    add_keywords_props(props, data)

    return props


def format_tvshow_props(data: dict) -> Dict[str, str]:
    """Format TV show-specific properties from TMDB data."""
    props: Dict[str, str] = {}

    props["Title"] = data.get("name") or ""
    props["OriginalTitle"] = data.get("original_name") or ""
    props["Plot"] = data.get("overview") or ""
    props["Tagline"] = data.get("tagline") or ""
    props["Status"] = data.get("status") or ""
    props["Popularity"] = str(data.get("popularity") or "")
    props["Homepage"] = data.get("homepage") or ""
    props["Type"] = data.get("type") or ""

    first_air = data.get("first_air_date") or ""
    if first_air:
        props["Premiered"] = first_air
        props["PremieredFormatted"] = format_date(first_air)
        try:
            props["Year"] = first_air[:4]
        except (IndexError, TypeError):
            pass

    last_air = data.get("last_air_date") or ""
    if last_air:
        props["LastAired"] = last_air
        props["LastAiredFormatted"] = format_date(last_air)

    genres = data.get("genres") or []
    if genres:
        props["Genre"] = " / ".join(g.get("name", "") for g in genres if g.get("name"))

    countries = data.get("origin_country") or []
    if countries:
        props["Country"] = " / ".join(countries)

    networks = data.get("networks") or []
    if networks:
        props["Studio"] = " / ".join(n.get("name", "") for n in networks if n.get("name"))

    props["Seasons"] = str(data.get("number_of_seasons") or "")
    props["Episodes"] = str(data.get("number_of_episodes") or "")

    runtimes = data.get("episode_run_time") or []
    if runtimes:
        props["Runtime"] = str(runtimes[0])

    created_by = data.get("created_by") or []
    if created_by:
        props["Creator"] = " / ".join(c.get("name", "") for c in created_by if c.get("name"))

    last_ep = data.get("last_episode_to_air")
    if last_ep:
        props["LastEpisodeTitle"] = last_ep.get("name") or ""
        props["LastEpisode"] = str(last_ep.get("episode_number") or "")
        props["LastEpisodeSeason"] = str(last_ep.get("season_number") or "")
        air_date = last_ep.get("air_date") or ""
        if air_date:
            props["LastEpisodeAired"] = format_date(air_date)

    next_ep = data.get("next_episode_to_air")
    if next_ep:
        props["NextEpisodeTitle"] = next_ep.get("name") or ""
        props["NextEpisode"] = str(next_ep.get("episode_number") or "")
        props["NextEpisodeSeason"] = str(next_ep.get("season_number") or "")
        air_date = next_ep.get("air_date") or ""
        if air_date:
            props["NextEpisodeAired"] = format_date(air_date)

    add_content_rating_props(props, data)
    add_trailer_props(props, data)
    add_keywords_props(props, data)

    return props


def format_credits_props(data: dict) -> Dict[str, str]:
    """Format cast and crew properties from TMDB credits data."""
    props: Dict[str, str] = {}

    credits = data.get("credits") or {}
    cast = credits.get("cast") or []
    crew = credits.get("crew") or []

    if cast:
        cast_names = [c.get("name") for c in cast[:10] if c.get("name")]
        props["Cast"] = " / ".join(cast_names)

        for i, actor in enumerate(cast[:5]):
            prefix = f"Cast.{i+1}"
            props[f"{prefix}.Name"] = actor.get("name") or ""
            props[f"{prefix}.Role"] = actor.get("character") or ""
            thumb = actor.get("profile_path")
            if thumb:
                props[f"{prefix}.Thumb"] = f"https://image.tmdb.org/t/p/w185{thumb}"

    directors = [c.get("name") for c in crew if c.get("job") == "Director" and c.get("name")]
    if directors:
        props["Director"] = " / ".join(directors)

    writers = [c.get("name") for c in crew if c.get("job") in ("Writer", "Screenplay", "Story") and c.get("name")]
    if writers:
        props["Writer"] = " / ".join(writers)

    return props


def format_images_props(data: dict) -> Dict[str, str]:
    """Format image URL properties from TMDB data."""
    props: Dict[str, str] = {}

    props["Poster"] = ""
    props["Fanart"] = ""
    props["Clearlogo"] = ""

    poster = data.get("poster_path")
    if poster:
        props["Poster"] = f"https://image.tmdb.org/t/p/w500{poster}"

    backdrop = data.get("backdrop_path")
    if backdrop:
        props["Fanart"] = f"https://image.tmdb.org/t/p/original{backdrop}"

    images = data.get("images") or {}
    logos = images.get("logos") or []
    for logo in logos:
        if logo.get("iso_639_1") in ("en", None):
            file_path = logo.get("file_path")
            if file_path:
                props["Clearlogo"] = f"https://image.tmdb.org/t/p/original{file_path}"
                break

    return props


def format_extra_props(data: dict) -> Dict[str, str]:
    """Format external IDs and other extra properties from TMDB data."""
    props: Dict[str, str] = {}

    external_ids = data.get("external_ids") or {}
    props["IMDBNumber"] = external_ids.get("imdb_id") or ""
    props["TVDBID"] = str(external_ids.get("tvdb_id") or "")
    props["TMDBID"] = str(data.get("id") or "")

    return props


def add_certification_props(props: Dict[str, str], data: dict) -> None:
    """Add MPAA certification from release_dates (movies)."""
    release_dates = data.get("release_dates") or {}
    results = release_dates.get("results") or []

    for country_data in results:
        if country_data.get("iso_3166_1") == "US":
            releases = country_data.get("release_dates") or []
            for release in releases:
                cert = release.get("certification")
                if cert:
                    props["MPAA"] = cert
                    return


def add_content_rating_props(props: Dict[str, str], data: dict) -> None:
    """Add MPAA certification from content_ratings (TV shows)."""
    content_ratings = data.get("content_ratings") or {}
    results = content_ratings.get("results") or []

    for rating in results:
        if rating.get("iso_3166_1") == "US":
            cert = rating.get("rating")
            if cert:
                props["MPAA"] = cert
                return


def add_trailer_props(props: Dict[str, str], data: dict) -> None:
    """Add trailer URL from TMDB videos data."""
    videos = data.get("videos") or {}
    results = videos.get("results") or []

    for video in results:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            key = video.get("key")
            if key:
                props["Trailer"] = f"plugin://plugin.video.youtube/play/?video_id={key}"
                props["TrailerYouTubeID"] = key
                return


def add_keywords_props(props: Dict[str, str], data: dict) -> None:
    """Add keywords/tags from TMDB data."""
    keywords = data.get("keywords") or {}
    keyword_list = keywords.get("keywords") or keywords.get("results") or []

    if keyword_list:
        tag_names = [kw.get("name") for kw in keyword_list if kw.get("name")]
        props["Tag"] = " / ".join(tag_names)


# Common Sense Media severity and category mappings
_CS_SEVERITY = {5: 32200, 4: 32201, 3: 32202, 2: 32203, 1: 32204}
_CS_CATEGORIES = [
    ("violence", 32210),
    ("nudity", 32211),
    ("language", 32212),
    ("drinking", 32213)
]


def build_common_sense_summary(cs_data: dict) -> Tuple[str, str]:
    """
    Build localized Common Sense summary and reasons strings from MDBList data.

    Groups categories by severity level for natural language output.

    Returns:
        Tuple of (summary, reasons) strings
        summary: "Rated 17+ for extreme violence and nudity; moderate language"
        reasons: "extreme violence and nudity; moderate language"
    """
    from typing import Dict, List
    ADDON = xbmcaddon.Addon()

    age = cs_data.get("age", 0)

    # Group categories by severity level
    by_level: Dict[int, List[str]] = {}
    for cat_key, string_id in _CS_CATEGORIES:
        score = cs_data.get(cat_key, 0)
        if score and score >= 1:
            if score not in by_level:
                by_level[score] = []
            by_level[score].append(ADDON.getLocalizedString(string_id))

    if not by_level:
        return "", ""

    and_str = ADDON.getLocalizedString(32221)
    parts = []
    for level in [5, 4, 3, 2, 1]:
        if level not in by_level:
            continue

        level_name = ADDON.getLocalizedString(_CS_SEVERITY[level])
        cats = by_level[level]

        if len(cats) == 1:
            parts.append(f"{level_name} {cats[0]}")
        elif len(cats) == 2:
            parts.append(f"{level_name} {cats[0]}{and_str}{cats[1]}")
        else:
            parts.append(f"{level_name} {', '.join(cats[:-1])}{and_str}{cats[-1]}")

    reasons = "; ".join(parts)
    summary_format = ADDON.getLocalizedString(32220)
    summary = summary_format.format(age, reasons)

    return summary, reasons
