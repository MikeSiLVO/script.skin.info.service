# Online Data

Fetch ratings, awards, and metadata from external APIs via plugin container.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Usage](#usage)
- [Two-Container Pattern](#two-container-pattern)
- [Available Properties](#available-properties)

---

## Overview

The `action=online` plugin path fetches data from external APIs:

- **TMDb** - Full metadata, credits, images, trailers
- **OMDb** - Awards data
- **MDBList** - Ratings, Common Sense Media, RT status
- **Trakt** - Ratings, subgenres

Two modes available:

- **Library mode**: Provide `dbid` + `dbtype` to look up IDs from Kodi library
- **Direct mode**: Provide `tmdb_id` or `imdb_id` directly (for non-library content)

---

## Usage

**Library item:**

```xml
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?action=online&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=movie</content>
</control>

<label>Budget: $INFO[Container(9001).ListItem.Property(Budget)]</label>
```

**Non-library item (TMDb ID):**

```xml
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?action=online&amp;tmdb_id=550&amp;dbtype=movie</content>
</control>
```

**Non-library item (IMDB ID):**

```xml
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?action=online&amp;imdb_id=tt0137523&amp;dbtype=movie</content>
</control>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `action` | Yes | Must be `online` |
| `dbtype` | Yes | `movie`, `tvshow`, or `episode` |
| `dbid` | * | Database ID (library items) |
| `tmdb_id` | * | TMDb ID (non-library items) |
| `imdb_id` | * | IMDB ID (non-library items) |
| `reload` | No | Cache buster |

\* Provide one of: `dbid`, `tmdb_id`, or `imdb_id`

**Note:** For episodes, the parent TV show's online data is returned.

---

## Two-Container Pattern

Use two hidden containers - Kodi data loads instantly, online data appears when ready:

```xml
<!-- Container 1: Fast Kodi data -->
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&amp;dbtype=movie</content>
</control>

<!-- Container 2: Online data (blocks until complete) -->
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?action=online&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=movie</content>
</control>

<!-- Loading indicator -->
<control type="image">
    <texture>loading.gif</texture>
    <visible>Container(9001).IsUpdating</visible>
</control>

<!-- Combined display -->
<label>$INFO[Container(9000).ListItem.Property(Title)] ($INFO[Container(9000).ListItem.Property(Year)])</label>
<label>Budget: $INFO[Container(9001).ListItem.Property(Budget)]</label>
```

---

## Available Properties

Properties via `Container(ID).ListItem.Property(...)`

### TMDb - Basic Information

| Property | Description | Media Types |
|----------|-------------|-------------|
| `Title` | Title | Movie, TVShow |
| `OriginalTitle` | Original title | Movie, TVShow |
| `Plot` | Overview/description | Movie, TVShow |
| `Tagline` | Tagline | Movie, TVShow |
| `Status` | Release status | Movie, TVShow |
| `Runtime` | Runtime in minutes | Movie, TVShow |
| `Popularity` | TMDb popularity score | Movie, TVShow |
| `Homepage` | Official website URL | Movie, TVShow |
| `Year` | Release year | Movie, TVShow |
| `Premiered` | Release/first air date | Movie, TVShow |
| `PremieredFormatted` | Formatted date | Movie, TVShow |
| `Genre` | Genres separated by " / " | Movie, TVShow |
| `Country` | Countries separated by " / " | Movie, TVShow |
| `Studio` | Studios/networks separated by " / " | Movie, TVShow |

### TMDb - Movie-Specific

| Property | Description |
|----------|-------------|
| `Budget` | Production budget (formatted with commas) |
| `Revenue` | Box office revenue (formatted with commas) |
| `Set` | Collection name |
| `SetID` | Collection TMDb ID |

### TMDb - TV Show-Specific

| Property | Description |
|----------|-------------|
| `Type` | Show type (Scripted, Documentary, etc.) |
| `Seasons` | Total season count |
| `Episodes` | Total episode count |
| `Creator` | Creator(s) separated by " / " |
| `LastAired` | Last air date |
| `LastAiredFormatted` | Formatted last air date |
| `LastEpisodeTitle` | Last aired episode title |
| `LastEpisode` | Last aired episode number |
| `LastEpisodeSeason` | Last aired episode season |
| `LastEpisodeAired` | Last episode air date (formatted) |
| `NextEpisodeTitle` | Next episode title |
| `NextEpisode` | Next episode number |
| `NextEpisodeSeason` | Next episode season |
| `NextEpisodeAired` | Next episode air date (formatted) |

### TMDb - Credits

| Property | Description |
|----------|-------------|
| `Cast` | Top 10 cast names separated by " / " |
| `Director` | Director(s) separated by " / " |
| `Writer` | Writer(s) separated by " / " |
| `Cast.1.Name` | First cast member name |
| `Cast.1.Role` | First cast member role |
| `Cast.1.Thumb` | First cast member thumbnail URL |
| `Cast.2.Name` | Second cast member name |
| `Cast.2.Role` | Second cast member role |
| `Cast.2.Thumb` | Second cast member thumbnail URL |
| ... | Up to Cast.5 |

### TMDb - Images

| Property | Description |
|----------|-------------|
| `Poster` | Poster image URL |
| `Fanart` | Backdrop image URL |
| `Clearlogo` | Clear logo URL (English preferred) |

### TMDb - IDs

| Property | Description |
|----------|-------------|
| `IMDBNumber` | IMDB ID |
| `TMDBID` | TMDb ID |
| `TVDBID` | TVDB ID (TV shows only) |

### TMDb - Other

| Property | Description |
|----------|-------------|
| `MPAA` | US certification (PG-13, R, TV-MA, etc.) |
| `Trailer` | YouTube trailer plugin URL |
| `TrailerYouTubeID` | YouTube video ID |
| `Tag` | Keywords separated by " / " |

### OMDb Awards

| Property | Description |
|----------|-------------|
| `Awards` | Full awards text |
| `Awards.Oscar.Wins` | Oscar wins |
| `Awards.Oscar.Nominations` | Oscar nominations |
| `Awards.Emmy.Wins` | Emmy wins |
| `Awards.Emmy.Nominations` | Emmy nominations |
| `Awards.Other.Wins` | Other wins |
| `Awards.Other.Nominations` | Other nominations |

### MDBList Properties

| Property | Description |
|----------|-------------|
| `MDBList.Trailer` | Trailer URL |
| `MDBList.Certification` | Content certification |

### Rotten Tomatoes Status

| Property | Values | Description |
|----------|--------|-------------|
| `Tomatometer` | "Certified", "Fresh", "Rotten" | Critics status |
| `Popcornmeter` | "Hot", "Fresh", "Spilled" | Audience status |

### Common Sense Media

| Property | Description |
|----------|-------------|
| `CommonSense.Age` | Recommended minimum age |
| `CommonSense.Violence` | Violence severity (1-5) |
| `CommonSense.Nudity` | Nudity severity (1-5) |
| `CommonSense.Language` | Language severity (1-5) |
| `CommonSense.Drinking` | Substance use severity (1-5) |
| `CommonSense.Selection` | Common Sense Selection winner |
| `CommonSense.Summary` | Localized summary |
| `CommonSense.Reasons` | Content reasons |

### Trakt Properties

| Property | Description |
|----------|-------------|
| `Trakt.Subgenres` | Curated subgenres |

### Rating Properties

Each source provides three properties:

| Property | Description |
|----------|-------------|
| `Rating.{source}` | Rating (0-10) |
| `Rating.{source}.Votes` | Vote count |
| `Rating.{source}.Percent` | Percentage (0-100) |

**Available Sources:**

- `tmdb` - TMDb
- `trakt` - Trakt
- `imdb` - IMDb (via MDBList)
- `metacritic` - Metacritic
- `metacriticuser` - Metacritic User
- `letterboxd` - Letterboxd
- `Tomatoes` - RT Critics
- `Popcorn` - RT Audience
- `rogerebert` - Roger Ebert
- `myanimelist` - MyAnimeList

### Example

```xml
<label>IMDb: $INFO[Container(9001).ListItem.Property(Rating.imdb)]</label>
<label>RT: $INFO[Container(9001).ListItem.Property(Rating.Tomatoes.Percent)]%</label>
```

---

## Notes

- **Blocking call** - The online action blocks until all API calls complete
- **Cached responses** - Data cached 24-72 hours depending on content age
- **Episode support** - Episodes return parent TV show's online data

---

[↑ Top](#online-data) · [Index](../index.md)
