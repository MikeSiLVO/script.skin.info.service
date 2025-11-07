# DBID Queries

Query media details for any library item using its database ID.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [Movies](#movies)
- [TV Shows](#tv-shows)
- [Seasons](#seasons)
- [Episodes](#episodes)
- [Movie Sets](#movie-sets)
- [Artists](#artists)
- [Albums](#albums)
- [Music Videos](#music-videos)

---

## Overview

The plugin returns a single ListItem with all properties set, accessible
through a hidden container.

---

## Basic Usage

```xml
<control type="group">
    <!-- Hidden container (positioned off-screen) -->
    <control type="list" id="9999">
        <left>-100</left>
        <top>-100</top>
        <width>100</width>
        <height>100</height>
        <itemlayout height="100" width="100" />
        <focusedlayout height="100" width="100" />
        <content>plugin://script.skin.info.service/
          ?dbid=$INFO[ListItem.DBID]
          &amp;dbtype=movie</content>
    </control>

    <!-- Display data -->
    <control type="label">
        <label>$INFO[Container(9999).ListItem.Property(Title)]</label>
    </control>
</control>
```

### Parameters

| Parameter | Required | Description                                           |
|-----------|----------|-------------------------------------------------------|
| `dbid`    | Yes      | Database ID of the item                               |
| `dbtype`  | Yes      | `movie`, `tvshow`, `season`, `episode`, `musicvideo`, |
|           |          | `artist`, `album`, `set`                              |

---

## Movies

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=movie</content>
```

### Movie Properties

| Property         | Description         |
|------------------|---------------------|
| `Title`          | Movie title         |
| `Year`           | Release year        |
| `Plot`           | Full plot           |
| `PlotOutline`    | Short summary       |
| `Rating`         | Default rating      |
| `Votes`          | Vote count          |
| `Genre`          | Genres              |
| `Director`       | Directors           |
| `Writer`         | Writers             |
| `Studio`         | Studios             |
| `StudioPrimary`  | First studio        |
| `Country`        | Countries           |
| `Runtime`        | Minutes             |
| `MPAA`           | Content rating      |
| `Tagline`        | Tagline             |
| `OriginalTitle`  | Original title      |
| `Premiered`      | Premiere date       |
| `Trailer`        | Trailer URL         |
| `Set`            | Set name            |
| `SetID`          | Set database ID     |
| `LastPlayed`     | Last played date    |
| `Playcount`      | Play count          |
| `Cast`           | Cast list           |
| `IMDBNumber`     | IMDB ID             |
| `Top250`         | Top 250 rank        |
| `DateAdded`      | Date added          |
| `Tag`            | Tags                |
| `UserRating`     | User rating         |
| `UniqueID.IMDB`  | IMDB unique ID      |
| `UniqueID.TMDB`  | TMDB unique ID      |
| `Path`           | File path           |
| `Codec`          | Video codec         |
| `Resolution`     | Resolution          |
| `Aspect`         | Aspect ratio        |
| `AudioCodec`     | Audio codec         |
| `AudioChannels`  | Audio channels      |
| `PercentPlayed`  | Progress percentage |
| `IsResumable`    | Has resume data     |
| `FileName`       | File name           |
| `FileExtension`  | Extension           |

### Movie Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(discart)`

### Movie Ratings

Standard InfoLabels (via Kodi's native rating API):

- `ListItem.Rating`
- `ListItem.Rating(imdb)`
- `ListItem.Rating(themoviedb)`
- `ListItem.Rating(tomatometerallcritics)`
- `ListItem.Rating(tomatometerallaudience)`

Properties (percent values only):

- `Rating.imdb.Percent`
- `Rating.tmdb.Percent`
- `Rating.Tomatoes.Percent`
- `Rating.Popcorn.Percent`

---

## TV Shows

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=tvshow</content>
```

### TV Show Properties

| Property          | Description       |
|-------------------|-------------------|
| `Title`           | Show title        |
| `Plot`            | Plot              |
| `Year`            | Start year        |
| `Premiered`       | Premiere date     |
| `Rating`          | Rating            |
| `Votes`           | Votes             |
| `Genre`           | Genres            |
| `Studio`          | Studios           |
| `StudioPrimary`   | First studio      |
| `MPAA`            | Content rating    |
| `Status`          | Status            |
| `Season`          | Season count      |
| `Episode`         | Episode count     |
| `WatchedEpisodes` | Watched count     |
| `WatchedEpisodePercent` | Watched percentage |
| `Path`            | Path              |
| `Cast`            | Cast              |
| `EpisodeGuide`    | Episode guide URL |
| `Trailer`         | Trailer URL       |
| `IMDBNumber`      | IMDB ID           |
| `OriginalTitle`   | Original title    |
| `SortTitle`       | Sort title        |
| `LastPlayed`      | Last played       |
| `Playcount`       | Play count        |
| `DateAdded`       | Date added        |
| `Tag`             | Tags              |
| `UserRating`      | User rating       |
| `UniqueID.IMDB`   | IMDB ID           |
| `UniqueID.TMDB`   | TMDB ID           |
| `UniqueID.TVDB`   | TVDB ID           |
| `Runtime`         | Episode runtime   |

### TV Show Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(thumb)`

---

## Seasons

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=season</content>
```

### Season Properties

| Property          | Description       |
|-------------------|-------------------|
| `Title`           | Season title      |
| `Season`          | Season number     |
| `ShowTitle`       | Parent show title |
| `Episode`         | Episode count     |
| `WatchedEpisodes` | Watched count     |
| `Playcount`       | Play count        |
| `UserRating`      | User rating       |
| `TVShowID`        | Parent show DBID  |

### Season Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(thumb)`

---

## Episodes

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=episode</content>
```

### Episode Properties

| Property         | Description     |
|------------------|-----------------|
| `Title`          | Episode title   |
| `Plot`           | Plot            |
| `Season`         | Season number   |
| `Episode`        | Episode number  |
| `TVShow`         | Show title      |
| `Rating`         | Rating          |
| `Votes`          | Votes           |
| `FirstAired`     | Air date        |
| `Runtime`        | Runtime         |
| `Director`       | Directors       |
| `Writer`         | Writers         |
| `Cast`           | Cast            |
| `ProductionCode` | Production code |
| `OriginalTitle`  | Original title  |
| `TVShowID`       | Show DBID       |
| `SeasonID`       | Season DBID     |
| `LastPlayed`     | Last played     |
| `Playcount`      | Play count      |
| `DateAdded`      | Date added      |
| `UserRating`     | User rating     |
| `Genre`          | Genres          |
| `Studio`         | Studios         |
| `UniqueID.IMDB`  | IMDB ID         |
| `UniqueID.TMDB`  | TMDB ID         |
| `UniqueID.TVDB`  | TVDB ID         |
| `Path`           | Path            |
| `Codec`          | Video codec     |
| `Resolution`     | Resolution      |
| `Aspect`         | Aspect ratio    |
| `AudioCodec`     | Audio codec     |
| `AudioChannels`  | Audio channels  |
| `PercentPlayed`  | Progress        |
| `IsResumable`    | Has resume      |
| `FileName`       | File name       |
| `FileExtension`  | Extension       |

### Episode Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(thumb)`

---

## Movie Sets

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=set</content>
```

### Set Properties

| Property | Description |
|----------|-------------|
| `Title`  | Set title   |
| `Plot`   | Set plot    |
| `Count`  | Movie count |

### Set Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(discart)`

### Set Aggregate Properties

| Property         | Description    |
|------------------|----------------|
| `Titles`         | All titles     |
| `Plots`          | Combined plots |
| `ExtendedPlots`  | Titles + plots |
| `Runtime`        | Total runtime  |
| `Runtime.Hours`  | Hours          |
| `Runtime.Minutes`| Minutes        |
| `Years`          | Years list     |
| `Writers`        | All writers    |
| `Directors`      | All directors  |
| `Genres`         | All genres     |
| `Countries`      | All countries  |
| `Studios`        | All studios    |

### Per-Movie Properties

Use `%d` as index (1-based):

- `Movie.%d.DBID`
- `Movie.%d.Title`
- `Movie.%d.Path`
- `Movie.%d.Year`
- `Movie.%d.Duration`
- `Movie.%d.Plot`
- `Movie.%d.Genre`
- `Movie.%d.Director`
- `Movie.%d.Writer`
- `Movie.%d.Studio`
- `Movie.%d.Country`
- `Movie.%d.VideoResolution`
- `Movie.%d.MPAA`
- `Movie.%d.Art(poster)`

---

## Artists

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=artist</content>
```

### Artist Properties

| Property        | Description    |
|-----------------|----------------|
| `Artist`        | Artist name    |
| `Description`   | Biography      |
| `Genre`         | Genres         |
| `Style`         | Styles         |
| `Mood`          | Moods          |
| `Instrument`    | Instruments    |
| `YearsActive`   | Years active   |
| `Born`          | Birth date     |
| `Formed`        | Formation date |
| `Died`          | Death date     |
| `Disbanded`     | Disbanded date |
| `Type`          | Artist type    |
| `Gender`        | Gender         |
| `SortName`      | Sort name      |
| `Disambiguation`| Disambiguation |
| `MusicBrainzID` | MusicBrainz ID |
| `Roles`         | Roles          |
| `SongGenres`    | Song genres    |
| `DateAdded`     | Date added     |

### Artist Album Aggregates

- `Albums.Newest`
- `Albums.Oldest`
- `Albums.Count`
- `Albums.Playcount`

### Per-Album Properties

- `Album.%d.Title`
- `Album.%d.Year`
- `Album.%d.Artist`
- `Album.%d.Genre`
- `Album.%d.DBID`
- `Album.%d.Label`
- `Album.%d.Playcount`
- `Album.%d.Rating`
- `Album.%d.Art(thumb)`
- `Album.%d.Art(discart)`

---

## Albums

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=album</content>
```

### Album Properties

| Property         | Description     |
|------------------|-----------------|
| `Title`          | Album title     |
| `Year`           | Release year    |
| `Artist`         | Artists         |
| `DisplayArtist`  | Display artist  |
| `SortArtist`     | Sort artist     |
| `Genre`          | Genres          |
| `SongGenres`     | Song genres     |
| `Label`          | Record label    |
| `Description`    | Description     |
| `Playcount`      | Play count      |
| `Rating`         | Rating          |
| `UserRating`     | User rating     |
| `Votes`          | Votes           |
| `MusicBrainzID`  | MusicBrainz ID  |
| `ReleaseGroupID` | Release group ID|
| `LastPlayed`     | Last played     |
| `DateAdded`      | Date added      |
| `Compilation`    | Is compilation  |
| `ReleaseType`    | Release type    |
| `TotalDiscs`     | Disc count      |
| `ReleaseDate`    | Release date    |
| `OriginalDate`   | Original date   |
| `AlbumDuration`  | Total seconds   |

### Album Song Aggregates

- `Songs.Tracklist`
- `Songs.Discs`
- `Songs.Duration`
- `Songs.Count`

### Per-Song Properties

- `Song.%d.Title`
- `Song.%d.Duration`
- `Song.%d.Track`
- `Song.%d.FileExtension`

---

## Music Videos

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=musicvideo</content>
```

### Music Video Properties

| Property        | Description  |
|-----------------|--------------|
| `Title`         | Title        |
| `Artist`        | Artists      |
| `ArtistPrimary` | First artist |
| `Album`         | Album        |
| `Year`          | Year         |
| `Plot`          | Description  |
| `Runtime`       | Runtime      |
| `Premiered`     | Release date |
| `Track`         | Track number |
| `Playcount`     | Play count   |
| `LastPlayed`    | Last played  |
| `DateAdded`     | Date added   |
| `Path`          | Path         |
| `Rating`        | Rating       |
| `UserRating`    | User rating  |
| `Genre`         | Genres       |
| `Director`      | Directors    |
| `Studio`        | Studios      |
| `Tag`           | Tags         |
| `Codec`         | Video codec  |
| `Resolution`    | Resolution   |
| `Aspect`        | Aspect ratio |
| `AudioCodec`    | Audio codec  |
| `AudioChannels` | Audio channels|

### Music Video Artwork

- `ListItem.Art(poster)`
- `ListItem.Art(fanart)`
- `ListItem.Art(clearlogo)`
- `ListItem.Art(keyart)`
- `ListItem.Art(landscape)`
- `ListItem.Art(banner)`
- `ListItem.Art(clearart)`
- `ListItem.Art(thumb)`

---

[↑ Top](#dbid-queries) · [Index](../index.md)
