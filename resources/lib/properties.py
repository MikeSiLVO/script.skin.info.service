"""Window property setters for movies, sets, artists, albums, and ratings.

Optimized batch property operations for high-performance UI updates.
"""
from __future__ import annotations

from typing import Any, Optional, List, Tuple, Dict, Set
import xbmcaddon

from resources.lib.utils import clear_prop, batch_set_props, format_date, extract_cast_names
from resources.lib.media import media_streamdetails, media_path

ADDON = xbmcaddon.Addon()

_STATE = {
    "set_movies": 0,
    "artist_albums": 0,
    "album_songs": 0,
    "set_studios": 0,
    "set_writers": 0,
    "set_directors": 0,
    "set_genres": 0,
    "set_countries": 0,
}

_VIDEO_ART_KEYS = (
    "poster", "fanart", "clearlogo", "keyart", "landscape",
    "banner", "clearart", "thumb",
)

_MOVIE_ART_KEYS = (
    "poster", "fanart", "clearlogo", "keyart", "landscape",
    "banner", "clearart", "discart",
)

_SET_ART_KEYS = (
    "poster", "fanart", "clearlogo", "keyart", "landscape",
    "banner", "clearart", "discart",
)

_AUDIO_ART_KEYS = ("thumb", "fanart", "discart")

# Cached for performance (avoid recreating strings in loops)
_CR = "[CR]"
_BOLD_OPEN = "[B]"
_BOLD_CLOSE = "[/B]"
_ITALIC_OPEN = "[I]"
_ITALIC_CLOSE = "[/I]"
_SEP = " / "


def _ordered_unique_push(seen: set, acc: list, items) -> None:
    """Add items to list in order, de-duplicating based on seen set."""
    if not items:
        return
    for x in (items if isinstance(items, list) else [items]):
        if x and x not in seen:
            seen.add(x)
            acc.append(x)


def _join(items: Optional[List[Any]], separator: str = " / ") -> str:
    """ Join list items with separator. """
    if not items:
        return ""
    return separator.join(str(i) for i in items if i)


def _first_or_empty(value) -> str:
    """ Return first item if list-like, or the string itself, else empty. """
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _format_number(value) -> str:
    """ Format number with comma thousands separator. """
    if not value:
        return ""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _extract_artist_names(items, key=None):
    """Extract names from artist/album metadata objects."""
    if not isinstance(items, list):
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and key:
            val = item.get(key)
            if val:
                names.append(val)
        elif isinstance(item, str):
            names.append(item)
    return names


def _set_art_props(prefix: str, art: Optional[Dict[str, Any]], keys: Tuple[str, ...], fallbacks: Optional[Dict[str, Any]] = None) -> None:
    art = art or {}
    fallbacks = fallbacks or {}

    art_props = {}
    for key in keys:
        val = art.get(key) or fallbacks.get(key) or ""
        art_props[f"{prefix}.Art({key})"] = val

    batch_set_props(art_props)


def _trim_indexed(prefix: str, prev: int, now: int) -> None:
    if now >= prev:
        return
    suffixes = (
        "DBID",
        "Title",
        "Year",
        "Duration",
        "TrackNumber",
        "FileExtension",
        "Genre",
        "Studio",
        "StudioPrimary",
        "Country",
        "Director",
        "Writer",
        "Plot",
        "PlotOutline",
        "Path",
        "VideoResolution",
        "MPAA",
        "Label",
        "Playcount",
        "Rating",
        "Artist",
        "Art(poster)",
        "Art(fanart)",
        "Art(clearlogo)",
        "Art(keyart)",
        "Art(landscape)",
        "Art(banner)",
        "Art(clearart)",
        "Art(thumb)",
        "Art(discart)",
    )
    for i in range(now + 1, prev + 1):
        for sfx in suffixes:
            clear_prop(f"{prefix}.{i}.{sfx}")


def _trim_simple_index(prefix: str, prev: int, now: int) -> None:
    if now >= prev:
        return
    for i in range(now + 1, prev + 1):
        clear_prop(f"{prefix}.{i}")


def build_movie_data(details: dict) -> dict:
    """Build movie data dictionary for ListItem properties."""
    data = {}

    path = media_path(details.get("file"))
    info = media_streamdetails(path, details.get("streamdetails", {}))

    runtime_seconds = int(details.get("runtime") or 0)
    runtime_minutes = runtime_seconds // 60
    hrs = runtime_minutes // 60
    mins = runtime_minutes % 60

    year = details.get("year")
    rating = details.get("rating")
    setid = details.get("setid")
    playcount = details.get("playcount")
    top250 = details.get("top250")
    userrating = details.get("userrating")

    data["Path"] = path or ""
    data["Title"] = details.get("title") or ""
    data["Year"] = str(year) if year else ""
    data["Rating"] = f"{rating:.1f}" if rating else ""
    data["Votes"] = _format_number(details.get("votes"))
    data["Genre"] = _join(details.get("genre"))
    data["Director"] = _join(details.get("director"))
    data["Studio"] = _join(details.get("studio"))
    data["Country"] = _join(details.get("country"))
    data["Tagline"] = details.get("tagline") or ""
    data["Plot"] = details.get("plot") or ""
    data["MPAA"] = details.get("mpaa") or ""
    data["Runtime"] = str(runtime_minutes) if runtime_minutes else ""
    data["Runtime.Hours"] = str(hrs) if hrs else ""
    data["Runtime.Minutes"] = str(mins) if mins >= 1 else ""
    data["Codec"] = info.get("videocodec") or ""
    data["Resolution"] = info.get("videoresolution") or ""
    data["Aspect"] = info.get("videoaspect") or ""
    data["AudioCodec"] = info.get("audiocodec") or ""
    data["AudioChannels"] = info.get("audiochannels") or ""

    _studios = details.get("studio")
    primary_studio = _first_or_empty(_studios)
    data["StudioPrimary"] = primary_studio or ""

    data["OriginalTitle"] = details.get("originaltitle") or ""
    data["Premiered"] = details.get("premiered") or ""
    data["Trailer"] = details.get("trailer") or ""
    data["Set"] = details.get("set") or ""
    data["SetID"] = str(setid) if setid else ""
    data["Writer"] = _join(details.get("writer"))
    data["PlotOutline"] = details.get("plotoutline") or ""
    data["LastPlayed"] = format_date(details.get("lastplayed") or "", include_time=False)
    data["Playcount"] = str(playcount) if playcount else ""
    data["IMDBNumber"] = details.get("imdbnumber") or ""
    data["Top250"] = str(top250) if top250 else ""
    data["DateAdded"] = format_date(details.get("dateadded") or "", include_time=False)
    data["Tag"] = _join(details.get("tag"))
    data["UserRating"] = str(userrating) if userrating else ""

    cast_names = extract_cast_names(details.get("cast"))
    data["Cast"] = _join(cast_names)

    uniqueid_dict = details.get("uniqueid") or {}
    data["UniqueID.IMDB"] = uniqueid_dict.get("imdb") or ""
    data["UniqueID.TMDB"] = uniqueid_dict.get("tmdb") or ""

    return data


def set_movie_properties(details: dict) -> None:
    """Set movie window properties with SkinInfo prefix."""
    data = build_movie_data(details)
    props = {f"SkinInfo.Movie.{k}": v for k, v in data.items()}
    batch_set_props(props)
    _set_art_props("SkinInfo.Movie", details.get("art"), _MOVIE_ART_KEYS)


def build_movieset_data(set_details: dict, movies: list[dict]) -> dict:
    """Build movie set data dictionary for ListItem properties."""
    data = {}

    title = set_details.get("title") or set_details.get("label") or ""
    data["Title"] = title
    data["Plot"] = set_details.get("plot") or ""

    total_runtime_min = 0
    title_list_parts = []
    plot_blocks = []
    years = []
    studios_set, genres_set, countries_set = set(), set(), set()
    seen_dirs, agg_dirs = set(), []
    seen_wrs, agg_wrs = set(), []
    prim_seen, prim_list = set(), []

    for idx, m in enumerate(movies, 1):
        label = m.get("title") or m.get("label") or ""
        year = m.get("year")
        runtime = int(m.get("runtime") or 0)
        duration_min = runtime // 60
        total_runtime_min += duration_min
        years.append(str(year) if year is not None else "")

        path = media_path(m.get("file"))
        info = media_streamdetails(path, m.get("streamdetails", {}))

        data[f"Movie.{idx}.DBID"] = str(m.get("movieid") or "")
        data[f"Movie.{idx}.Title"] = label or ""
        data[f"Movie.{idx}.Plot"] = m.get("plot") or ""
        data[f"Movie.{idx}.PlotOutline"] = m.get("plotoutline") or ""
        data[f"Movie.{idx}.Path"] = path or ""
        data[f"Movie.{idx}.Year"] = str(year) if year is not None else ""
        data[f"Movie.{idx}.Duration"] = str(duration_min) if duration_min else ""
        data[f"Movie.{idx}.VideoResolution"] = info.get("videoresolution") or ""
        data[f"Movie.{idx}.MPAA"] = m.get("mpaa") or ""
        data[f"Movie.{idx}.Genre"] = _join(m.get("genre"))
        data[f"Movie.{idx}.Director"] = _join(m.get("director"))
        data[f"Movie.{idx}.Writer"] = _join(m.get("writer"))
        data[f"Movie.{idx}.Studio"] = _join(m.get("studio"))
        data[f"Movie.{idx}.Country"] = _join(m.get("country"))

        _studios = m.get("studio")
        primary = _first_or_empty(_studios)
        data[f"Movie.{idx}.StudioPrimary"] = primary

        if year is not None:
            title_list_parts.append(f"{_ITALIC_OPEN}{label} ({year}){_ITALIC_CLOSE}{_CR}")
        else:
            title_list_parts.append(f"{_ITALIC_OPEN}{label}{_ITALIC_CLOSE}{_CR}")

        use_outline = (m.get("plotoutline") or "").strip()
        block_plot = use_outline if use_outline else (m.get("plot") or "")
        if label:
            if year is not None:
                plot_blocks.append(f"{_BOLD_OPEN}{label} ({year}){_BOLD_CLOSE}{_CR}{block_plot}{_CR}{_CR}")
            else:
                plot_blocks.append(f"{_BOLD_OPEN}{label}{_BOLD_CLOSE}{_CR}{block_plot}{_CR}{_CR}")

        _ordered_unique_push(seen_dirs, agg_dirs, m.get("director"))
        _ordered_unique_push(seen_wrs, agg_wrs, m.get("writer"))
        studios_set.update(m.get("studio") or [])
        genres_set.update(m.get("genre") or [])
        countries_set.update(m.get("country") or [])

        if primary:
            key = primary.casefold()
            if key not in prim_seen:
                prim_seen.add(key)
                prim_list.append(primary)

    total_count = len(movies)
    title_list = "".join(title_list_parts)
    plot_joined = "".join(plot_blocks)

    data["Plots"] = plot_joined or ""
    if total_count > 1:
        data["ExtendedPlots"] = (title_list + "[CR]" + plot_joined) or ""
    else:
        data["ExtendedPlots"] = plot_joined or ""
    data["Titles"] = title_list or ""

    data["Runtime"] = str(total_runtime_min) if total_runtime_min else ""

    hrs = total_runtime_min // 60
    mins = total_runtime_min % 60
    data["Runtime.Hours"] = str(hrs) if hrs else ""
    data["Runtime.Minutes"] = str(mins) if mins >= 1 else ""

    data["Writers"] = _join(agg_wrs)
    data["Directors"] = _join(agg_dirs)
    genres_sorted = sorted(genres_set, key=str.casefold) if genres_set else []
    countries_sorted = sorted(countries_set, key=str.casefold) if countries_set else []
    data["Genres"] = _join(genres_sorted)
    data["Countries"] = _join(countries_sorted)
    data["Studios"] = _join(sorted(studios_set, key=str.casefold))

    for i, studio in enumerate(prim_list, 1):
        data[f"Studios.{i}"] = studio

    for i, w in enumerate(agg_wrs, 1):
        data[f"Writers.{i}"] = w

    for i, d in enumerate(agg_dirs, 1):
        data[f"Directors.{i}"] = d

    for i, g in enumerate(genres_sorted, 1):
        data[f"Genres.{i}"] = g

    for i, c in enumerate(countries_sorted, 1):
        data[f"Countries.{i}"] = c

    data["Years"] = _join(years)
    data["Count"] = str(total_count)

    data["_metadata"] = {
        "prim_list_count": len(prim_list),
        "writers_count": len(agg_wrs),
        "directors_count": len(agg_dirs),
        "genres_count": len(genres_sorted),
        "countries_count": len(countries_sorted),
        "movies_count": total_count,
    }

    return data


def set_movieset_properties(set_details: dict, movies: list[dict]) -> None:
    """Set movie set window properties with SkinInfo.Set prefix."""
    data = build_movieset_data(set_details, movies)

    metadata = data.pop("_metadata")
    props = {f"SkinInfo.Set.{k}": v for k, v in data.items()}
    batch_set_props(props)

    set_art = set_details.get("art") or {}
    art_props = {f"SkinInfo.Set.Art({key})": set_art.get(key) or "" for key in _SET_ART_KEYS}

    for idx, m in enumerate(movies, 1):
        m_art = m.get("art") or {}
        for key in _MOVIE_ART_KEYS:
            art_props[f"SkinInfo.Set.Movie.{idx}.Art({key})"] = m_art.get(key) or (m.get("thumbnail") if key == "thumbnail" else "")

    batch_set_props(art_props)

    _trim_simple_index("SkinInfo.Set.Studios", _STATE["set_studios"], metadata["prim_list_count"])
    _STATE["set_studios"] = metadata["prim_list_count"]
    _trim_simple_index("SkinInfo.Set.Writers", _STATE["set_writers"], metadata["writers_count"])
    _STATE["set_writers"] = metadata["writers_count"]
    _trim_simple_index("SkinInfo.Set.Directors", _STATE["set_directors"], metadata["directors_count"])
    _STATE["set_directors"] = metadata["directors_count"]
    _trim_simple_index("SkinInfo.Set.Genres", _STATE["set_genres"], metadata["genres_count"])
    _STATE["set_genres"] = metadata["genres_count"]
    _trim_simple_index("SkinInfo.Set.Countries", _STATE["set_countries"], metadata["countries_count"])
    _STATE["set_countries"] = metadata["countries_count"]
    _trim_indexed("SkinInfo.Set.Movie", _STATE["set_movies"], metadata["movies_count"])
    _STATE["set_movies"] = metadata["movies_count"]


def build_artist_data(artist: dict, albums: list[dict]) -> dict:
    """Build artist data dictionary for ListItem properties."""
    data = {}

    data["Artist"] = artist.get("artist") or ""
    data["Description"] = artist.get("description") or ""
    data["Genre"] = _join(artist.get("genre"))
    data["DateAdded"] = format_date(artist.get("dateadded") or "", include_time=False)

    data["Roles"] = _join(_extract_artist_names(artist.get("roles"), "role"))
    data["SongGenres"] = _join(_extract_artist_names(artist.get("songgenres"), "title"))
    data["Style"] = _join(artist.get("style"))
    data["Mood"] = _join(artist.get("mood"))
    data["Instrument"] = _join(artist.get("instrument"))
    data["YearsActive"] = _join(artist.get("yearsactive"))
    data["Born"] = artist.get("born") or ""
    data["Formed"] = artist.get("formed") or ""
    data["Died"] = artist.get("died") or ""
    data["Disbanded"] = artist.get("disbanded") or ""
    data["Type"] = artist.get("type") or ""
    data["Gender"] = artist.get("gender") or ""
    data["SortName"] = artist.get("sortname") or ""
    data["Disambiguation"] = artist.get("disambiguation") or ""

    mbids = artist.get("musicbrainzartistid") or []
    if isinstance(mbids, list):
        data["MusicBrainzID"] = ", ".join(mbids)
    else:
        data["MusicBrainzID"] = mbids or ""

    latestyear = 0
    firstyear = 0
    playcount_total = 0

    for idx, a in enumerate(albums, 1):
        a_year = a.get("year")
        a_albumid = a.get("albumid")
        a_playcount = a.get("playcount")
        a_rating = a.get("rating")

        data[f"Album.{idx}.Title"] = a.get("title") or ""
        data[f"Album.{idx}.Year"] = str(a_year) if a_year else ""
        data[f"Album.{idx}.Artist"] = _join(a.get("artist"))
        data[f"Album.{idx}.Genre"] = _join(a.get("genre"))
        data[f"Album.{idx}.DBID"] = str(a_albumid) if a_albumid else ""
        data[f"Album.{idx}.Label"] = a.get("albumlabel") or ""
        data[f"Album.{idx}.Playcount"] = str(a_playcount) if a_playcount else ""
        data[f"Album.{idx}.Rating"] = f"{a_rating:.1f}" if a_rating else ""

        y = a.get("year") or 0
        if y:
            if y > latestyear:
                latestyear = y
            if firstyear == 0 or y < firstyear:
                firstyear = y
        playcount_total += int(a.get("playcount") or 0)

    count = len(albums)
    if firstyear > 0 and latestyear < 2030:
        data["Albums.Newest"] = str(latestyear)
        data["Albums.Oldest"] = str(firstyear)
    else:
        data["Albums.Newest"] = ""
        data["Albums.Oldest"] = ""
    data["Albums.Count"] = str(count)
    data["Albums.Playcount"] = str(playcount_total)

    data["_metadata"] = {"albums_count": count}

    return data


def set_artist_properties(artist: dict, albums: list[dict]) -> None:
    """Set artist window properties with SkinInfo.Artist prefix."""
    data = build_artist_data(artist, albums)

    metadata = data.pop("_metadata")
    props = {f"SkinInfo.Artist.{k}": v for k, v in data.items()}
    batch_set_props(props)

    artist_art = artist.get("art") or {}
    art_props = {}
    art_props["SkinInfo.Artist.Art(thumb)"] = artist_art.get("thumb") or artist.get("thumbnail") or ""
    art_props["SkinInfo.Artist.Art(fanart)"] = artist_art.get("fanart") or artist.get("fanart") or ""

    for idx, a in enumerate(albums, 1):
        a_art = a.get("art") or {}
        art_props[f"SkinInfo.Artist.Album.{idx}.Art(thumb)"] = a_art.get("thumb") or a.get("thumbnail") or ""
        art_props[f"SkinInfo.Artist.Album.{idx}.Art(discart)"] = a_art.get("discart") or ""

    batch_set_props(art_props)

    _trim_indexed("SkinInfo.Artist.Album", _STATE["artist_albums"], metadata["albums_count"])
    _STATE["artist_albums"] = metadata["albums_count"]


def build_album_data(album: dict, songs: list[dict]) -> dict:
    """Build album data dictionary for ListItem properties."""
    data = {}

    album_year = album.get("year")
    album_playcount = album.get("playcount")
    album_rating = album.get("rating")
    album_userrating = album.get("userrating")
    album_compilation = album.get("compilation")
    album_totaldiscs = album.get("totaldiscs")

    data["Title"] = album.get("title") or ""
    data["Year"] = str(album_year) if album_year else ""
    data["Artist"] = _join(album.get("artist"))
    data["Genre"] = _join(album.get("genre"))
    data["Label"] = album.get("albumlabel") or ""
    data["Playcount"] = str(album_playcount) if album_playcount else ""
    data["Rating"] = f"{album_rating:.1f}" if album_rating else ""
    data["UserRating"] = f"{album_userrating:.1f}" if album_userrating else ""
    data["MusicBrainzID"] = album.get("musicbrainzalbumid") or ""
    data["ReleaseGroupID"] = album.get("musicbrainzreleasegroupid") or ""
    data["LastPlayed"] = format_date(album.get("lastplayed") or "", include_time=False)
    data["DateAdded"] = format_date(album.get("dateadded") or "", include_time=False)
    data["Description"] = album.get("description") or ""
    data["Votes"] = _format_number(album.get("votes"))
    data["DisplayArtist"] = album.get("displayartist") or ""
    data["Compilation"] = str(album_compilation) if album_compilation is not None else ""
    data["ReleaseType"] = album.get("releasetype") or ""
    data["SortArtist"] = album.get("sortartist") or ""
    data["TotalDiscs"] = str(album_totaldiscs) if album_totaldiscs else ""
    data["ReleaseDate"] = album.get("releasedate") or ""
    data["OriginalDate"] = album.get("originaldate") or ""

    songgenres_list = album.get("songgenres") or []
    if songgenres_list:
        genre_titles = [g.get("title") for g in songgenres_list if isinstance(g, dict) and g.get("title")]
        data["SongGenres"] = _join(genre_titles)
    else:
        data["SongGenres"] = ""

    disc_max = 0
    total_seconds = 0
    tracklist_parts = []

    for idx, s in enumerate(songs, 1):
        s_duration = s.get("duration")
        s_track = s.get("track")

        data[f"Song.{idx}.Title"] = s.get("title") or ""
        data[f"Song.{idx}.Duration"] = str(s_duration) if s_duration else ""
        data[f"Song.{idx}.TrackNumber"] = str(s_track) if s_track else ""

        f = s.get("file") or ""
        ext = f.rsplit(".", 1)[-1] if "." in f else ""
        data[f"Song.{idx}.FileExtension"] = ext or ""

        d = int(s.get("disc") or 0)
        if d > disc_max:
            disc_max = d
        total_seconds += int(s_duration or 0)
        trk = s.get("track")
        title = s.get("title") or ""
        if trk is not None and title:
            tracklist_parts.append(f"{_BOLD_OPEN}{trk}{_BOLD_CLOSE}: {title}{_CR}")

    minutes = total_seconds // 60
    seconds = total_seconds % 60
    data["Songs.Discs"] = str(disc_max)
    data["Songs.Duration"] = f"{minutes:02d}:{seconds:02d}" if total_seconds else ""
    data["Songs.Tracklist"] = "".join(tracklist_parts)
    data["Songs.Count"] = str(len(songs))

    data["_metadata"] = {"songs_count": len(songs)}

    return data


def set_album_properties(album: dict, songs: list[dict]) -> None:
    """Set album window properties with SkinInfo.Album prefix."""
    data = build_album_data(album, songs)

    metadata = data.pop("_metadata")
    props = {f"SkinInfo.Album.{k}": v for k, v in data.items()}
    batch_set_props(props)

    album_art = album.get("art") or {}
    art_props = {}
    art_props["SkinInfo.Album.Art(thumb)"] = album_art.get("thumb") or album.get("thumbnail") or ""
    art_props["SkinInfo.Album.Art(fanart)"] = album_art.get("fanart") or album.get("fanart") or ""
    art_props["SkinInfo.Album.Art(discart)"] = album_art.get("discart") or ""

    batch_set_props(art_props)

    _trim_indexed("SkinInfo.Album.Song", _STATE["album_songs"], metadata["songs_count"])
    _STATE["album_songs"] = metadata["songs_count"]


_RATING_STATE: Dict[str, Set[str]] = {}

_TOMATOMETER_SOURCES = frozenset(("tomatometerallcritics", "tomatometeravgcritics"))


def _clear_rating_source(prefix: str, src: str) -> None:
    clear_prop(f"{prefix}.{src}")
    clear_prop(f"{prefix}.{src}.Votes")
    clear_prop(f"{prefix}.{src}.Percent")
    clear_prop(f"{prefix}.{src}.Tomatometer")


def set_ratings_properties(item: dict, media_type: str = "Movie") -> None:
    ratings = item.get("ratings") or {}
    prefix = f"SkinInfo.{media_type}.Rating"

    current_sources = set()

    if not ratings:
        if media_type in _RATING_STATE:
            for src in _RATING_STATE[media_type]:
                _clear_rating_source(prefix, src)
            _RATING_STATE[media_type] = set()
        clear_prop(prefix)
        return

    # Batch all rating properties together for performance
    props = {}

    for src, info in ratings.items():
        current_sources.add(src)

        val = info.get("rating")
        max_val = info.get("max") or 10
        votes = info.get("votes")

        if val is None or not max_val:
            continue

        try:
            scaled = round(float(val) / (float(max_val) / 10.0), 1)
            pct = max(0, min(100, int(round(scaled * 10))))
        except (TypeError, ValueError, ZeroDivisionError):
            continue

        props[f"{prefix}.{src}"] = str(scaled)
        props[f"{prefix}.{src}.Votes"] = _format_number(votes)
        props[f"{prefix}.{src}.Percent"] = str(pct)

        if src in _TOMATOMETER_SOURCES:
            props[f"{prefix}.{src}.Tomatometer"] = "Fresh" if pct >= 60 else "Rotten"

    # Batch set all rating properties at once
    if props:
        batch_set_props(props)

    prev_sources = _RATING_STATE.get(media_type, set())
    removed_sources = prev_sources - current_sources
    for src in removed_sources:
        _clear_rating_source(prefix, src)

    _RATING_STATE[media_type] = current_sources


def build_tvshow_data(details: dict) -> dict:
    """Build TV show data dictionary for ListItem properties."""
    data = {}

    year = details.get("year")
    rating = details.get("rating")
    runtime_seconds = int(details.get("runtime") or 0)
    runtime_minutes = runtime_seconds // 60
    episode = details.get("episode")
    season = details.get("season")
    watchedepisodes = details.get("watchedepisodes")
    playcount = details.get("playcount")

    data["Title"] = details.get("title") or ""
    data["Plot"] = details.get("plot") or ""
    data["Year"] = str(year) if year else ""
    data["Premiered"] = details.get("premiered") or ""
    data["Rating"] = f"{rating:.1f}" if rating else ""
    data["Votes"] = _format_number(details.get("votes"))
    data["Genre"] = _join(details.get("genre"))
    data["Studio"] = _join(details.get("studio"))
    data["MPAA"] = details.get("mpaa") or ""
    data["Status"] = details.get("status") or ""
    data["Runtime"] = str(runtime_minutes) if runtime_minutes else ""
    data["Episode"] = str(episode) if episode else ""
    data["Season"] = str(season) if season else ""
    data["WatchedEpisodes"] = str(watchedepisodes) if watchedepisodes else ""
    data["IMDBNumber"] = details.get("imdbnumber") or ""
    data["OriginalTitle"] = details.get("originaltitle") or ""
    data["SortTitle"] = details.get("sorttitle") or ""
    data["EpisodeGuide"] = details.get("episodeguide") or ""
    data["Tag"] = _join(details.get("tag"))
    data["Path"] = media_path(details.get("file")) or ""
    data["DateAdded"] = format_date(details.get("dateadded") or "", include_time=False)
    data["LastPlayed"] = format_date(details.get("lastplayed") or "", include_time=False)
    data["Playcount"] = str(playcount) if playcount else ""
    data["Trailer"] = details.get("trailer") or ""

    cast_names = extract_cast_names(details.get("cast"))
    data["Cast"] = _join(cast_names)

    uniqueid_dict = details.get("uniqueid") or {}
    data["UniqueID.IMDB"] = uniqueid_dict.get("imdb") or ""
    data["UniqueID.TMDB"] = uniqueid_dict.get("tmdb") or ""
    data["UniqueID.TVDB"] = uniqueid_dict.get("tvdb") or ""

    _studios = details.get("studio")
    primary_studio = _first_or_empty(_studios)
    data["StudioPrimary"] = primary_studio or ""

    return data


def set_tvshow_properties(details: dict) -> None:
    """Set TV show window properties with SkinInfo.TVShow prefix."""
    data = build_tvshow_data(details)
    props = {f"SkinInfo.TVShow.{k}": v for k, v in data.items()}
    batch_set_props(props)
    _set_art_props("SkinInfo.TVShow", details.get("art"), _VIDEO_ART_KEYS)


def build_season_data(details: dict) -> dict:
    """Build season data dictionary for ListItem properties."""
    data = {}

    season = details.get("season")
    episode = details.get("episode")
    watchedepisodes = details.get("watchedepisodes")
    playcount = details.get("playcount")
    tvshowid = details.get("tvshowid")
    userrating = details.get("userrating")

    data["Title"] = details.get("title") or ""
    data["Season"] = str(season) if season is not None else ""
    data["ShowTitle"] = details.get("showtitle") or ""
    data["Episode"] = str(episode) if episode else ""
    data["WatchedEpisodes"] = str(watchedepisodes) if watchedepisodes else ""
    data["Playcount"] = str(playcount) if playcount else ""
    data["UserRating"] = str(userrating) if userrating else ""
    data["TVShowID"] = str(tvshowid) if tvshowid and tvshowid != -1 else ""

    return data


def set_season_properties(details: dict) -> None:
    """Set season window properties with SkinInfo.Season prefix."""
    data = build_season_data(details)
    props = {f"SkinInfo.Season.{k}": v for k, v in data.items()}
    batch_set_props(props)
    _set_art_props("SkinInfo.Season", details.get("art"), _VIDEO_ART_KEYS)


def build_episode_data(details: dict) -> dict:
    """Build episode data dictionary for ListItem properties."""
    data = {}

    path = media_path(details.get("file"))
    info = media_streamdetails(path, details.get("streamdetails", {}))

    rating = details.get("rating")
    season = details.get("season")
    episode = details.get("episode")
    runtime_seconds = int(details.get("runtime") or 0)
    runtime_minutes = runtime_seconds // 60
    playcount = details.get("playcount")
    tvshowid = details.get("tvshowid")
    userrating = details.get("userrating")
    seasonid = details.get("seasonid")

    data["Title"] = details.get("title") or ""
    data["Plot"] = details.get("plot") or ""
    data["Rating"] = f"{rating:.1f}" if rating else ""
    data["Votes"] = _format_number(details.get("votes"))
    data["Season"] = str(season) if season is not None else ""
    data["Episode"] = str(episode) if episode is not None else ""
    data["TVShow"] = details.get("showtitle") or ""
    data["FirstAired"] = details.get("firstaired") or ""
    data["Runtime"] = str(runtime_minutes) if runtime_minutes else ""
    data["Director"] = _join(details.get("director"))
    data["Writer"] = _join(details.get("writer"))
    data["Path"] = path or ""
    data["ProductionCode"] = details.get("productioncode") or ""
    data["OriginalTitle"] = details.get("originaltitle") or ""
    data["Playcount"] = str(playcount) if playcount else ""

    data["Codec"] = info.get("videocodec") or ""
    data["Resolution"] = info.get("videoresolution") or ""
    data["Aspect"] = info.get("videoaspect") or ""
    data["AudioCodec"] = info.get("audiocodec") or ""
    data["AudioChannels"] = info.get("audiochannels") or ""

    data["LastPlayed"] = format_date(details.get("lastplayed") or "", include_time=False)
    data["TVShowID"] = str(tvshowid) if tvshowid else ""
    data["DateAdded"] = format_date(details.get("dateadded") or "", include_time=False)
    data["UserRating"] = str(userrating) if userrating else ""
    data["SeasonID"] = str(seasonid) if seasonid else ""
    data["Genre"] = _join(details.get("genre"))
    data["Studio"] = _join(details.get("studio"))

    cast_names = extract_cast_names(details.get("cast"))
    data["Cast"] = _join(cast_names)

    uniqueid_dict = details.get("uniqueid") or {}
    data["UniqueID.IMDB"] = uniqueid_dict.get("imdb") or ""
    data["UniqueID.TMDB"] = uniqueid_dict.get("tmdb") or ""
    data["UniqueID.TVDB"] = uniqueid_dict.get("tvdb") or ""

    return data


def set_episode_properties(details: dict) -> None:
    """Set episode window properties with SkinInfo.Episode prefix."""
    data = build_episode_data(details)
    props = {f"SkinInfo.Episode.{k}": v for k, v in data.items()}
    batch_set_props(props)
    _set_art_props("SkinInfo.Episode", details.get("art"), _VIDEO_ART_KEYS)


def build_musicvideo_data(details: dict) -> dict:
    """Build music video data dictionary for ListItem properties."""
    data = {}

    path = media_path(details.get("file"))
    info = media_streamdetails(path, details.get("streamdetails", {}))

    runtime_seconds = int(details.get("runtime") or 0)
    if runtime_seconds:
        minutes = runtime_seconds // 60
        seconds = runtime_seconds % 60
        runtime_formatted = f"{minutes}:{seconds:02d}"
    else:
        runtime_formatted = ""

    year = details.get("year")
    playcount = details.get("playcount")
    rating = details.get("rating")
    userrating = details.get("userrating")
    track = details.get("track")

    data["Title"] = details.get("title") or ""
    data["Artist"] = _join(details.get("artist"))
    data["Album"] = details.get("album") or ""
    data["Genre"] = _join(details.get("genre"))
    data["Year"] = str(year) if year else ""
    data["Plot"] = details.get("plot") or ""
    data["Runtime"] = runtime_formatted
    data["Director"] = _join(details.get("director"))
    data["Studio"] = _join(details.get("studio"))
    data["Path"] = path or ""
    data["Premiered"] = details.get("premiered") or ""
    data["Tag"] = _join(details.get("tag"))
    data["Playcount"] = str(playcount) if playcount else ""

    data["Codec"] = info.get("videocodec") or ""
    data["Resolution"] = info.get("videoresolution") or ""
    data["Aspect"] = info.get("videoaspect") or ""
    data["AudioCodec"] = info.get("audiocodec") or ""
    data["AudioChannels"] = info.get("audiochannels") or ""

    _artists = details.get("artist")
    primary_artist = _first_or_empty(_artists)
    data["ArtistPrimary"] = primary_artist or ""

    data["LastPlayed"] = format_date(details.get("lastplayed") or "", include_time=False)
    data["DateAdded"] = format_date(details.get("dateadded") or "", include_time=False)
    data["Rating"] = f"{rating:.1f}" if rating else ""
    data["UserRating"] = str(userrating) if userrating else ""
    data["Track"] = str(track) if track else ""

    uniqueid_dict = details.get("uniqueid") or {}
    data["UniqueID.IMDB"] = uniqueid_dict.get("imdb") or ""
    data["UniqueID.TMDB"] = uniqueid_dict.get("tmdb") or ""

    return data


def set_musicvideo_properties(details: dict) -> None:
    """Set music video window properties with SkinInfo.MusicVideo prefix."""
    data = build_musicvideo_data(details)
    props = {f"SkinInfo.MusicVideo.{k}": v for k, v in data.items()}
    batch_set_props(props)
    _set_art_props("SkinInfo.MusicVideo", details.get("art"), _VIDEO_ART_KEYS)
