<div align="center">

# 🎬 Skin Info Service

**Enhanced media properties for Kodi skins**

![Kodi Version](https://img.shields.io/badge/Kodi-Omega%2B-blue?logo=kodi)
![Python](https://img.shields.io/badge/Python-3.0%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-GPL--3.0-green)
![Version](https://img.shields.io/badge/Version-2.0.0-orange)

</div>

---

## 📖 Overview

**Skin Info Service** is a Kodi service addon that provides detailed properties for skins to display enhanced media information.

### ✨ Features

#### For Skin Developers

- 🎯 **Automatic Detection** - Properties populate when items are focused
- 📦 **Batch Operations** - Optimized property setting for maximum speed
- 🎨 **Comprehensive Properties** - Rich metadata, ratings, artwork, and aggregates
- 🔧 **Easy Integration** - Simple RunScript call to activate
- 📺 **Media Support** - Movies, Sets, TV Shows, Seasons, Episodes, Music Videos, Artists, Albums
- 🎨 **Blur Generator** - Auto-blur images
- 🔌 **DBID Query** - Query item details via DBID for containers

#### For End Users (v2.0+)

- 🎬 **Animated Poster Scanner** - Auto-detect and add GIF posters
- 🖼️ **Artwork Reviewer** - Download missing or replace existing artwork
- ⭐ **Ratings Updater** - Fetch ratings from multiple sources (API Keys required)
- 🗂️ **Texture Cache Manager** - Clean and optimize cache
- 📱 **Context Menu** - Access Artwork Reviewer and Ratings Updater from any library item

---

## 📑 Table of Contents

- [Installation & Setup](#-installation--setup)
- [Properties Reference](#-properties-reference)
  - [🎬 Movies](#-movies)
  - [📦 Movie Sets](#-movie-sets)
  - [📺 TV Shows](#-tv-shows)
  - [📅 Seasons](#-seasons)
  - [📽️ Episodes](#️-episodes)
  - [🎵 Music Videos](#-music-videos)
  - [🎤 Artists](#-artists)
  - [💿 Albums](#-albums)
- [Usage Examples](#-usage-examples)
- [User Tools](#-user-tools)
  - [Animated Poster Scanner](DOCS/GIF_SCANNER.md)
  - [Artwork Reviewer](DOCS/ARTWORK_REVIEW.md)
  - [Ratings Updater](#-ratings-updater)
  - [Texture Cache Manager](DOCS/TEXTURE_CACHE.md)
- [Skinner Integration](#-skinner-integration)
  - [Blur Generator](#-blur-generator)
  - [Plugin Paths](DOCS/PLUGIN_USAGE.md)
  - [Advanced Features](#-advanced-features)

---

## 🔧 Installation & Setup

### Requirements

- Kodi Omega (v21) or higher

### Activation (For Skin Developers)

Add this to your skin's Home.xml or startup window:

```xml
<onload>RunScript(script.skin.info.service)</onload>
```

The service will run in the background and automatically monitor focused items.

**Optional - Allow users to enable/disable:**

```xml
<onload condition="Skin.HasSetting(SkinInfo.Service)">RunScript(script.skin.info.service)</onload>
```

This starts the service only when the user enables it via your skin's settings.

---

## 📚 Properties Reference

All properties are available via `Window(Home).Property(...)`. Properties automatically populate when items are focused.

---

### 🎬 Movies

**Prefix:** `SkinInfo.Movie.*`

#### Basic Information

| Property        | Description                  |
| --------------- | ---------------------------- |
| `Title`         | Movie title                  |
| `OriginalTitle` | Original title               |
| `Year`          | Release year                 |
| `Plot`          | Full plot description        |
| `PlotOutline`   | Short plot summary           |
| `Tagline`       | Movie tagline                |
| `Rating`        | Default rating value         |
| `Votes`         | Number of votes              |
| `UserRating`    | User's rating (0-10)         |
| `MPAA`          | Content rating (e.g., PG-13) |
| `Runtime`       | Runtime in minutes           |
| `Premiered`     | Premiere date                |

#### Movie Set

| Property | Description           |
| -------- | --------------------- |
| `Set`    | Movie set name        |
| `SetID`  | Movie set database ID |

#### Library Data

| Property        | Description            |
| --------------- | ---------------------- |
| `Playcount`     | Number of times played |
| `LastPlayed`    | Last played date       |
| `DateAdded`     | Date added to library  |
| `Tag`           | Tags, comma-separated  |
| `IMDBNumber`    | IMDB ID                |
| `Top250`        | IMDB Top 250 ranking   |
| `UniqueID.IMDB` | IMDB unique ID         |
| `UniqueID.TMDB` | TMDB unique ID         |
| `Trailer`       | Trailer URL            |

#### Credits

| Property        | Description                         |
| --------------- | ----------------------------------- |
| `Director`      | Director(s), comma-separated        |
| `Writer`        | Writer(s), comma-separated          |
| `Cast`          | Cast members, comma-separated names |
| `Genre`         | Genre(s), comma-separated           |
| `Studio`        | Studio(s), comma-separated          |
| `StudioPrimary` | First studio only                   |
| `Country`       | Country(ies), comma-separated       |

#### Technical Details

| Property        | Description                               |
| --------------- | ----------------------------------------- |
| `Path`          | File path                                 |
| `Codec`         | Video codec                               |
| `Resolution`    | Video resolution (480, 720, 1080, 4k, 8k) |
| `Aspect`        | Aspect ratio (1.33, 1.78, 2.35, etc.)     |
| `AudioCodec`    | Audio codec                               |
| `AudioChannels` | Audio channel count                       |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(discart)`   | Disc art    |

#### Ratings

Replace `{source}` with rating source (e.g., `imdb`, `themoviedb`, `tomatometerallcritics`):

| Property                      | Description                                           |
| ----------------------------- | ----------------------------------------------------- |
| `Rating.{source}`             | Scaled rating (0-10)                                  |
| `Rating.{source}.Votes`       | Vote count                                            |
| `Rating.{source}.Percent`     | Percentage (0-100)                                    |
| `Rating.{source}.Tomatometer` | "Fresh" (≥60%) or "Rotten" (<60%) for Rotten Tomatoes |

---

### 📦 Movie Sets

**Prefix:** `SkinInfo.Set.*`

#### Set Information

| Property | Description             |
| -------- | ----------------------- |
| `Title`  | Set title               |
| `Plot`   | Set plot description    |
| `Count`  | Number of movies in set |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(discart)`   | Disc art    |

#### Aggregate Properties

| Property          | Description                                  |
| ----------------- | -------------------------------------------- |
| `Titles`          | Formatted list of all movie titles           |
| `Plots`           | Combined plots of all movies                 |
| `ExtendedPlots`   | Titles + plots combined                      |
| `Runtime`         | Total runtime in minutes                     |
| `Runtime.Hours`   | Hours component                              |
| `Runtime.Minutes` | Minutes component                            |
| `Years`           | Years list (separated by " / ")              |
| `Writers`         | All writers (de-duped, separated by " / ")   |
| `Directors`       | All directors (de-duped, separated by " / ") |
| `Genres`          | All genres (de-duped, separated by " / ")    |
| `Countries`       | All countries (de-duped, separated by " / ") |
| `Studios`         | All studios (de-duped, separated by " / ")   |

#### Indexed Aggregates

Use `%d` as placeholder for index (1-based):

| Property       | Description                                      |
| -------------- | ------------------------------------------------ |
| `Writers.%d`   | Individual writer                                |
| `Directors.%d` | Individual director                              |
| `Genres.%d`    | Individual genre                                 |
| `Countries.%d` | Individual country                               |
| `Studios.%d`   | Primary studio per movie (de-duped, movie order) |

#### Per-Movie Properties

Use `%d` as placeholder for index (1-based):

**Basic:**

| Property               | Description        |
| ---------------------- | ------------------ |
| `Movie.%d.DBID`        | Database ID        |
| `Movie.%d.Title`       | Movie title        |
| `Movie.%d.Path`        | File path          |
| `Movie.%d.Year`        | Release year       |
| `Movie.%d.Duration`    | Runtime in minutes |
| `Movie.%d.Plot`        | Full plot          |
| `Movie.%d.PlotOutline` | Short summary      |

**Credits:**

| Property                 | Description                   |
| ------------------------ | ----------------------------- |
| `Movie.%d.Genre`         | Genre(s), comma-separated     |
| `Movie.%d.Director`      | Director(s), comma-separated  |
| `Movie.%d.Writer`        | Writer(s), comma-separated    |
| `Movie.%d.Studio`        | Studio(s), comma-separated    |
| `Movie.%d.StudioPrimary` | First studio only             |
| `Movie.%d.Country`       | Country(ies), comma-separated |

**Technical:**

| Property                   | Description                               |
| -------------------------- | ----------------------------------------- |
| `Movie.%d.VideoResolution` | Video resolution (480, 720, 1080, 4k, 8k) |
| `Movie.%d.MPAA`            | Content rating                            |

**Artwork:**

| Property                  | Description |
| ------------------------- | ----------- |
| `Movie.%d.Art(poster)`    | Poster      |
| `Movie.%d.Art(fanart)`    | Fanart      |
| `Movie.%d.Art(clearlogo)` | Clear logo  |
| `Movie.%d.Art(keyart)`    | Key art     |
| `Movie.%d.Art(landscape)` | Landscape   |
| `Movie.%d.Art(banner)`    | Banner      |
| `Movie.%d.Art(clearart)`  | Clear art   |
| `Movie.%d.Art(discart)`   | Disc art    |

---

### 📺 TV Shows

**Prefix:** `SkinInfo.TVShow.*`

#### Basic Information

| Property        | Description                          |
| --------------- | ------------------------------------ |
| `Title`         | TV show title                        |
| `OriginalTitle` | Original title                       |
| `SortTitle`     | Sort title                           |
| `Year`          | Year started                         |
| `Plot`          | Full plot description                |
| `Premiered`     | Premiere date                        |
| `Rating`        | Default rating value                 |
| `Votes`         | Number of votes                      |
| `UserRating`    | User's rating (0-10)                 |
| `MPAA`          | Content rating                       |
| `Status`        | Status (e.g., "Continuing", "Ended") |

#### Show Details

| Property          | Description                |
| ----------------- | -------------------------- |
| `Episode`         | Total episode count        |
| `Season`          | Total season count         |
| `WatchedEpisodes` | Number of watched episodes |
| `Runtime`         | Episode runtime in minutes |
| `EpisodeGuide`    | Episode guide URL          |
| `Trailer`         | Trailer URL                |

#### Library Data

| Property        | Description            |
| --------------- | ---------------------- |
| `Playcount`     | Number of times played |
| `LastPlayed`    | Last played date       |
| `DateAdded`     | Date added to library  |
| `Path`          | File path              |
| `IMDBNumber`    | IMDB ID                |
| `UniqueID.IMDB` | IMDB unique ID         |
| `UniqueID.TMDB` | TMDB unique ID         |
| `UniqueID.TVDB` | TVDB unique ID         |

#### Credits

| Property        | Description                         |
| --------------- | ----------------------------------- |
| `Cast`          | Cast members, comma-separated names |
| `Genre`         | Genre(s), comma-separated           |
| `Studio`        | Studio(s), comma-separated          |
| `StudioPrimary` | First studio only                   |
| `Tag`           | Tags, comma-separated               |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(thumb)`     | Thumbnail   |

#### Ratings

Replace `{source}` with rating source (e.g., `imdb`, `themoviedb`, `tomatometerallcritics`):

| Property                      | Description                                           |
| ----------------------------- | ----------------------------------------------------- |
| `Rating.{source}`             | Scaled rating (0-10)                                  |
| `Rating.{source}.Votes`       | Vote count                                            |
| `Rating.{source}.Percent`     | Percentage (0-100)                                    |
| `Rating.{source}.Tomatometer` | "Fresh" (≥60%) or "Rotten" (<60%) for Rotten Tomatoes |

---

### 📅 Seasons

**Prefix:** `SkinInfo.Season.*`

#### Basic Information

| Property          | Description                        |
| ----------------- | ---------------------------------- |
| `Title`           | Season title                       |
| `Season`          | Season number                      |
| `ShowTitle`       | Parent TV show title               |
| `Episode`         | Total number of episodes in season |
| `WatchedEpisodes` | Number of watched episodes         |
| `Playcount`       | Play count                         |
| `UserRating`      | User's rating (0-10)               |
| `TVShowID`        | Parent TV show database ID         |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(thumb)`     | Thumbnail   |

---

### 📽️ Episodes

**Prefix:** `SkinInfo.Episode.*`

#### Basic Information

| Property        | Description          |
| --------------- | -------------------- |
| `Title`         | Episode title        |
| `OriginalTitle` | Original title       |
| `Plot`          | Episode plot         |
| `Season`        | Season number        |
| `Episode`       | Episode number       |
| `TVShow`        | Parent TV show title |
| `Rating`        | Episode rating       |
| `Votes`         | Number of votes      |
| `UserRating`    | User's rating (0-10) |

#### Episode Details

| Property         | Description                |
| ---------------- | -------------------------- |
| `FirstAired`     | Original air date          |
| `Runtime`        | Runtime in minutes         |
| `ProductionCode` | Production code            |
| `TVShowID`       | Parent TV show database ID |
| `SeasonID`       | Season database ID         |

#### Library Data

| Property        | Description           |
| --------------- | --------------------- |
| `Playcount`     | Play count            |
| `LastPlayed`    | Last played date      |
| `DateAdded`     | Date added to library |
| `Path`          | File path             |
| `UniqueID.IMDB` | IMDB unique ID        |
| `UniqueID.TMDB` | TMDB unique ID        |
| `UniqueID.TVDB` | TVDB unique ID        |

#### Credits

| Property   | Description                         |
| ---------- | ----------------------------------- |
| `Cast`     | Cast members, comma-separated names |
| `Director` | Director(s), comma-separated        |
| `Writer`   | Writer(s), comma-separated          |
| `Genre`    | Genre(s), comma-separated           |
| `Studio`   | Studio(s), comma-separated          |

#### Technical Details

| Property        | Description                               |
| --------------- | ----------------------------------------- |
| `Codec`         | Video codec                               |
| `Resolution`    | Video resolution (480, 720, 1080, 4k, 8k) |
| `Aspect`        | Aspect ratio                              |
| `AudioCodec`    | Audio codec                               |
| `AudioChannels` | Audio channel count                       |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(thumb)`     | Thumbnail   |

#### Ratings

Replace `{source}` with rating source (e.g., `imdb`, `themoviedb`, `tomatometerallcritics`):

| Property                  | Description          |
| ------------------------- | -------------------- |
| `Rating.{source}`         | Scaled rating (0-10) |
| `Rating.{source}.Votes`   | Vote count           |
| `Rating.{source}.Percent` | Percentage (0-100)   |

---

### 🎵 Music Videos

**Prefix:** `SkinInfo.MusicVideo.*`

#### Basic Information

| Property        | Description                |
| --------------- | -------------------------- |
| `Title`         | Music video title          |
| `Artist`        | Artist(s), comma-separated |
| `ArtistPrimary` | First artist only          |
| `Album`         | Album name                 |
| `Year`          | Release year               |
| `Plot`          | Description                |
| `Runtime`       | Runtime (mm:ss format)     |
| `Premiered`     | Release date               |
| `Track`         | Track number               |

#### Library Data

| Property        | Description           |
| --------------- | --------------------- |
| `Playcount`     | Play count            |
| `LastPlayed`    | Last played date      |
| `DateAdded`     | Date added to library |
| `Path`          | File path             |
| `Rating`        | Rating                |
| `UserRating`    | User's rating (0-10)  |
| `UniqueID.IMDB` | IMDB unique ID        |
| `UniqueID.TMDB` | TMDB unique ID        |

#### Credits

| Property   | Description                  |
| ---------- | ---------------------------- |
| `Genre`    | Genre(s), comma-separated    |
| `Director` | Director(s), comma-separated |
| `Studio`   | Studio(s), comma-separated   |
| `Tag`      | Tags, comma-separated        |

#### Technical Details

| Property        | Description                               |
| --------------- | ----------------------------------------- |
| `Codec`         | Video codec                               |
| `Resolution`    | Video resolution (480, 720, 1080, 4k, 8k) |
| `Aspect`        | Aspect ratio                              |
| `AudioCodec`    | Audio codec                               |
| `AudioChannels` | Audio channel count                       |

#### Artwork

| Property         | Description |
| ---------------- | ----------- |
| `Art(poster)`    | Poster      |
| `Art(fanart)`    | Fanart      |
| `Art(clearlogo)` | Clear logo  |
| `Art(keyart)`    | Key art     |
| `Art(landscape)` | Landscape   |
| `Art(banner)`    | Banner      |
| `Art(clearart)`  | Clear art   |
| `Art(thumb)`     | Thumbnail   |

---

### 🎤 Artists

**Prefix:** `SkinInfo.Artist.*`

#### Basic Information

| Property      | Description               |
| ------------- | ------------------------- |
| `Artist`      | Artist name               |
| `Description` | Artist biography          |
| `Genre`       | Genre(s), comma-separated |
| `DateAdded`   | Date added to library     |

#### Artist Details

| Property         | Description                    |
| ---------------- | ------------------------------ |
| `Style`          | Style(s), comma-separated      |
| `Mood`           | Mood(s), comma-separated       |
| `Instrument`     | Instrument(s), comma-separated |
| `YearsActive`    | Years active, comma-separated  |
| `Born`           | Birth date                     |
| `Formed`         | Formation date (for bands)     |
| `Died`           | Death date                     |
| `Disbanded`      | Disbanded date (for bands)     |
| `Type`           | Artist type (person/group)     |
| `Gender`         | Gender                         |
| `SortName`       | Sort name                      |
| `Disambiguation` | Disambiguation string          |
| `MusicBrainzID`  | MusicBrainz ID(s)              |
| `Roles`          | Roles, comma-separated         |
| `SongGenres`     | Song genres, comma-separated   |

#### Artwork

| Property      | Description |
| ------------- | ----------- |
| `Art(thumb)`  | Thumbnail   |
| `Art(fanart)` | Fanart      |

#### Album Aggregates

| Property           | Description                   |
| ------------------ | ----------------------------- |
| `Albums.Newest`    | Most recent album year        |
| `Albums.Oldest`    | Oldest album year             |
| `Albums.Count`     | Total album count             |
| `Albums.Playcount` | Total playcount across albums |

#### Per-Album Properties

Use `%d` as placeholder for index (1-based):

| Property                | Description       |
| ----------------------- | ----------------- |
| `Album.%d.Title`        | Album title       |
| `Album.%d.Year`         | Release year      |
| `Album.%d.Artist`       | Artist name       |
| `Album.%d.Genre`        | Genre             |
| `Album.%d.DBID`         | Database ID       |
| `Album.%d.Label`        | Record label      |
| `Album.%d.Playcount`    | Play count        |
| `Album.%d.Rating`       | Album rating      |
| `Album.%d.Art(thumb)`   | Thumbnail artwork |
| `Album.%d.Art(discart)` | Disc artwork      |

---

### 💿 Albums

**Prefix:** `SkinInfo.Album.*`

#### Basic Information

| Property        | Description                  |
| --------------- | ---------------------------- |
| `Title`         | Album title                  |
| `Year`          | Release year                 |
| `Artist`        | Artist(s), comma-separated   |
| `DisplayArtist` | Display artist name          |
| `SortArtist`    | Sort artist name             |
| `Genre`         | Genre(s), comma-separated    |
| `SongGenres`    | Song genres, comma-separated |
| `Label`         | Record label                 |
| `Description`   | Album description            |

#### Album Details

| Property         | Description                    |
| ---------------- | ------------------------------ |
| `Playcount`      | Play count                     |
| `Rating`         | Album rating                   |
| `UserRating`     | User rating                    |
| `Votes`          | Number of votes                |
| `MusicBrainzID`  | MusicBrainz Album ID           |
| `ReleaseGroupID` | MusicBrainz Release Group ID   |
| `LastPlayed`     | Last played timestamp          |
| `DateAdded`      | Date added to library          |
| `Compilation`    | Whether album is a compilation |
| `ReleaseType`    | Release type                   |
| `TotalDiscs`     | Total number of discs          |
| `ReleaseDate`    | Release date                   |
| `OriginalDate`   | Original release date          |
| `AlbumDuration`  | Total duration in seconds      |

#### Artwork

| Property       | Description |
| -------------- | ----------- |
| `Art(thumb)`   | Thumbnail   |
| `Art(fanart)`  | Fanart      |
| `Art(discart)` | Disc art    |

#### Song Aggregates

| Property          | Description            |
| ----------------- | ---------------------- |
| `Songs.Tracklist` | Formatted tracklist    |
| `Songs.Discs`     | Number of discs        |
| `Songs.Duration`  | Total duration (mm:ss) |
| `Songs.Count`     | Total song count       |

#### Per-Song Properties

Use `%d` as placeholder for index (1-based):

| Property                | Description      |
| ----------------------- | ---------------- |
| `Song.%d.Title`         | Song title       |
| `Song.%d.Duration`      | Duration (mm:ss) |
| `Song.%d.Track`         | Track number     |
| `Song.%d.FileExtension` | File extension   |

---

## 💡 Usage Examples

### Display Movie Information

```xml
<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Movie.Title)]</label>
</control>
<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Movie.Year)] • $INFO[Window(Home).Property(SkinInfo.Movie.Runtime)] min</label>
</control>
<control type="image">
    <texture>$INFO[Window(Home).Property(SkinInfo.Movie.Art(poster))]</texture>
</control>
```

### Show Episode Information

```xml
<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Episode.TVShow)]</label>
</control>
<control type="label">
    <label>S$INFO[Window(Home).Property(SkinInfo.Episode.Season)]E$INFO[Window(Home).Property(SkinInfo.Episode.Episode)] - $INFO[Window(Home).Property(SkinInfo.Episode.Title)]</label>
</control>
<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Episode.Resolution)]</label>
</control>
```

### Display Set Runtime

```xml
<control type="label">
    <label>Total Runtime: $INFO[Window(Home).Property(SkinInfo.Set.Runtime.Hours)]h $INFO[Window(Home).Property(SkinInfo.Set.Runtime.Minutes)]m</label>
</control>
```

### Show IMDB Rating

```xml
<control type="label">
    <label>IMDB: $INFO[Window(Home).Property(SkinInfo.Movie.Rating.imdb)]★</label>
</control>
```

### Loop Through Set Movies

```xml
<control type="list" id="50">
    <content>
        <!-- Use Container(50).ListItem(0).Property(SkinInfo.Set.Movie.1.Title) -->
        <!-- Use Container(50).ListItem(1).Property(SkinInfo.Set.Movie.2.Title) -->
        <!-- etc. -->
    </content>
</control>
```

---

## 🔬 Advanced Features

### Ratings System

The addon supports multiple rating sources from Kodi's unified ratings system:

**Common Sources:**

- `imdb` - Internet Movie Database
- `themoviedb` - The Movie Database
- `tomatometerallcritics` - Rotten Tomatoes (All Critics)
- `tomatometeravgcritics` - Rotten Tomatoes (Top Critics)

**Scaling:**

- All ratings normalized to 0-10 scale
- Percentage calculated (0-100)
- Tomatometer shows "Fresh" (≥60%) or "Rotten" (<60%)

### Aggregate Properties

Movie sets automatically aggregate data across all movies:

**Smart De-duplication:**

- Writers, directors maintain movie order
- Genres, countries, studios alphabetically sorted
- Primary studios preserve movie order (de-duped)

**Formatted Strings:**

- Titles/plots use Kodi formatting ([B], [I], [CR])
- Separated by " / " for lists

### Property Clearing

Properties automatically clear when:

- Switching media types (movie → tvshow)
- Losing focus (DBID becomes empty)
- Indexed properties shrink (set with 5 movies → 3 movies)

## 🔧 User Tools

Version 2.0 introduces comprehensive library management tools via the unified Tools menu.

**Access Tools Menu:**

```xml
RunScript(script.skin.info.service,tools)
```

---

### Animated Poster Scanner

Scan library for animated GIF posters and add as "animatedposter" art type.

**Access:**

- Tools menu → Animated Art Scanner

**Display in skins:**

```xml
<texture fallback="$INFO[ListItem.Art(poster)]">$INFO[ListItem.Art(animatedposter)]</texture>
```

📖 **[Full Documentation](DOCS/GIF_SCANNER.md)**

---

### Artwork Reviewer

Review and manage artwork - download missing or replace existing artwork.

**Access:**

- Context menu: Right-click → Review Artwork
- Tools menu → Artwork Reviewer
- RunScript: `RunScript(script.skin.info.service,review_artwork,dbid,dbtype)`

📖 **[Full Documentation](DOCS/ARTWORK_REVIEW.md)**

---

### Ratings Updater

Fetch and update ratings from multiple sources.

**Sources:** IMDb, TMDB, OMDb (Rotten Tomatoes), Trakt, MDbList

**API Keys:**

- **TMDB** -  Required (free)
- **OMDb** - Optional (free + paid tiers)
- **MDbList** - Optional (free + paid tiers)
- **Trakt** - Optional (free)

**Access:**

- Context menu: Right-click → Update Ratings
- Tools menu → Ratings Updater
- RunScript: `RunScript(script.skin.info.service,update_ratings,dbid,dbtype)`

**Configuration:** Settings → Ratings

---

### Texture Cache Manager

Clean and optimize Kodi's texture cache.

**Access:**

- Tools menu → Texture Cache Manager

📖 **[Full Documentation](DOCS/TEXTURE_CACHE.md)**

---

### Download Artwork to Filesystem

Bulk download artwork to local filesystem.

**Access:**

- Tools menu → Download Artwork to Filesystem

---

### Context Menu

Right-click access to tools on library items (Movies, TV Shows, Seasons, Episodes).

**Enable/Disable:** Settings → Advanced → Context Menu

---

## 🎨 Skinner Integration

### Blur Generator

Auto-create blurred images.

**Requirements:**

- Background service must be running: `RunScript(script.skin.info.service)`

**Access blurred fanart:**

```xml
<texture>$INFO[Window(Home).Property(SkinInfo.BlurredFanart)]</texture>
```

---

### Plugin Interface

DBID queries.

📖 **[Full Documentation](DOCS/PLUGIN_USAGE.md)**

**Format:**

```
plugin://script.skin.info.service/?dbid=X&type=Y
```

---

### Common Issues

**Properties not populating:**

1. Check service is running via `RunScript(script.skin.info.service)`
2. Verify DBID is available (`ListItem.DBID`)
3. Check DBType matches expected type

**Service not starting:**

- Must be activated via `RunScript(script.skin.info.service)` 
- Check Kodi log for startup messages

---

## 📄 License

GPL-3.0-only

---

<div align="center">

**Made for the Kodi skinning community**

[Report Issues](https://github.com/MikeSiLVO/script.skin.info.service/issues) • [Contribute](https://github.com/MikeSiLVO/script.skin.info.service)

</div>
