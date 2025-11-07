# Plugin Usage Guide - Get Details by DBID

## Overview

The plugin path feature allows you to query media details for any item in your Kodi library using its DBID.

The plugin returns a single ListItem with all properties set, which can be accessed through a hidden container.

## Basic Usage

From your skin XML, use the plugin as a content source in a hidden container (positioned off-screen):

```xml
<control type="group">
    <!-- Hidden container that fetches the data (positioned off-screen) -->
    <control type="list" id="9999">
        <left>-100</left>
        <top>-100</top>
        <width>100</width>
        <height>100</height>
        <itemlayout height="100" width="100" />
        <focusedlayout height="100" width="100" />
        <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=movie</content>
    </control>

    <!-- Display the data from the container's ListItem -->
    <control type="label">
        <label>$INFO[Container(9999).ListItem.Property(Title)]</label>
    </control>
</control>
```

## Parameters

| Parameter | Required | Description                 | Valid Values                                                                   |
| --------- | -------- | --------------------------- | ------------------------------------------------------------------------------ |
| `dbid`    | Yes      | The database ID of the item | Any valid DBID (number)                                                        |
| `type`    | Yes      | The media type              | `movie`, `tvshow`, `season`, `episode`, `musicvideo`, `artist`, `album`, `set` |

## Accessing Properties

Properties are accessed as **ListItem properties** from the container:

```xml
<!-- Query a movie by DBID in a hidden container (positioned off-screen) -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=movie</content>
</control>

<!-- Access properties from the container's ListItem -->
<label>$INFO[Container(8000).ListItem.Property(Title)]</label>
<label>$INFO[Container(8000).ListItem.Property(Year)]</label>
<label>$INFO[Container(8000).ListItem.Property(Plot)]</label>
```

## Examples by Media Type

### Movies

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=movie</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Year`
- `Plot`
- `PlotOutline`
- `Rating`
- `Votes`
- `Genre`
- `Director`
- `Writer`
- `Studio`
- `StudioPrimary`
- `Country`
- `Runtime`
- `MPAA`
- `Tagline`
- `OriginalTitle`
- `Premiered`
- `Trailer`
- `Set`
- `SetID`
- `LastPlayed`
- `Playcount`
- `Cast`
- `IMDBNumber`
- `Top250`
- `DateAdded`
- `Tag`
- `UserRating`
- `UniqueID.IMDB`
- `UniqueID.TMDB`
- `Path`
- `Codec`
- `Resolution`
- `Aspect`
- `AudioCodec`
- `AudioChannels`
- `Rating.*` (multiple rating sources)

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `discart`

### TV Shows

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=tvshow</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Plot`
- `Year`
- `Premiered`
- `Rating`
- `Votes`
- `Genre`
- `Studio`
- `StudioPrimary`
- `MPAA`
- `Status`
- `Runtime`
- `Episode`
- `Season`
- `WatchedEpisodes`
- `IMDBNumber`
- `OriginalTitle`
- `SortTitle`
- `EpisodeGuide`
- `Tag`
- `Path`
- `DateAdded`
- `LastPlayed`
- `Playcount`
- `Trailer`
- `Cast`
- `UniqueID.IMDB`
- `UniqueID.TMDB`
- `UniqueID.TVDB`
- `Rating.*` (multiple rating sources)

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `thumb`

### Seasons

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=season</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Season`
- `ShowTitle`
- `Episode` (total episodes in season)
- `WatchedEpisodes`
- `Playcount`
- `UserRating`
- `TVShowID`

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `thumb`

### Episodes

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=episode</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `TVShow`
- `Season`
- `Episode`
- `Plot`
- `Rating`
- `Votes`
- `FirstAired`
- `Runtime`
- `Director`
- `Writer`
- `Path`
- `ProductionCode`
- `OriginalTitle`
- `Playcount`
- `LastPlayed`
- `TVShowID`
- `DateAdded`
- `UserRating`
- `SeasonID`
- `Genre`
- `Studio`
- `Cast`
- `UniqueID.IMDB`
- `UniqueID.TMDB`
- `UniqueID.TVDB`
- `Codec`
- `Resolution`
- `Aspect`
- `AudioCodec`
- `AudioChannels`
- `Rating.*` (multiple rating sources)

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `thumb`

### Movie Sets

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=set</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Plot`
- `Count` (number of movies)
- `Runtime` (total runtime)
- `Genres`
- `Directors`
- `Movie.1.Title`
- `Movie.1.Year`
- `Movie.2.Title`
- And more... (indexed per movie)

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `discart`

### Artists

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=artist</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Artist`
- `Description`
- `Genre`
- `DateAdded`
- `Roles`
- `SongGenres`
- `Style`
- `Mood`
- `Instrument`
- `YearsActive`
- `Born`
- `Formed`
- `Died`
- `Disbanded`
- `Type`
- `Gender`
- `SortName`
- `Disambiguation`
- `MusicBrainzID`
- `Albums.Count`
- `Albums.Newest`
- `Albums.Oldest`
- `Albums.Playcount`
- `Album.1.Title`
- `Album.1.Year`
- `Album.1.Artist`
- `Album.1.Genre`
- `Album.1.DBID`
- `Album.1.Label`
- `Album.1.Playcount`
- `Album.1.Rating`

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `thumb`
- `fanart`

**Per-Album Artwork** (accessed via `Container(8000).ListItem.Property(...)`):

- `Album.1.Art.thumb`
- `Album.1.Art.discart`

### Albums

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=album</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Year`
- `Artist`
- `Genre`
- `Label`
- `Playcount`
- `Rating`
- `UserRating`
- `MusicBrainzID`
- `ReleaseGroupID`
- `LastPlayed`
- `DateAdded`
- `Description`
- `Votes`
- `DisplayArtist`
- `Compilation`
- `ReleaseType`
- `SortArtist`
- `SongGenres`
- `TotalDiscs`
- `ReleaseDate`
- `OriginalDate`
- `AlbumDuration`
- `Songs.Count`
- `Songs.Discs`
- `Songs.Duration`
- `Songs.Tracklist`
- `Song.1.Title`
- `Song.1.Duration`
- `Song.1.Track`
- `Song.1.FileExtension`

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `thumb`
- `fanart`
- `discart`

### Music Videos

```xml
<!-- Hidden container -->
<control type="list" id="8000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=musicvideo</content>
</control>
```

**Available Properties** (accessed via `Container(8000).ListItem.Property(...)`):

- `Title`
- `Artist`
- `ArtistPrimary`
- `Album`
- `Genre`
- `Year`
- `Plot`
- `Runtime`
- `Director`
- `Studio`
- `Path`
- `Premiered`
- `Tag`
- `Playcount`
- `LastPlayed`
- `DateAdded`
- `Rating`
- `UserRating`
- `Track`
- `UniqueID.IMDB`
- `UniqueID.TMDB`
- `Codec`
- `Resolution`
- `Aspect`
- `AudioCodec`
- `AudioChannels`

**Artwork** (accessed via `Container(8000).ListItem.Art(...)`):

- `poster`
- `fanart`
- `clearlogo`
- `keyart`
- `landscape`
- `banner`
- `clearart`
- `thumb`

## Advanced Use Cases

### 1. Display Related Movie Information

```xml
<!-- Hidden container (positioned off-screen) fetches details for a related movie -->
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?dbid=456&type=movie</content>
</control>

<!-- Display the related movie info from the container -->
<control type="label">
    <label>$INFO[Container(9001).ListItem.Property(Title)]</label>
</control>
<control type="label">
    <label>$INFO[Container(9001).ListItem.Property(Year)]</label>
</control>
```

### 2. Multiple Simultaneous Queries

```xml
<!-- Query multiple items with different container IDs (each positioned off-screen) -->
<control type="list" id="9001">
    <content>plugin://script.skin.info.service/?dbid=10&type=movie</content>
</control>

<control type="list" id="9002">
    <content>plugin://script.skin.info.service/?dbid=20&type=movie</content>
</control>

<control type="list" id="9003">
    <content>plugin://script.skin.info.service/?dbid=30&type=movie</content>
</control>

<!-- Display all three -->
<label>Movie 1: $INFO[Container(9001).ListItem.Property(Title)]</label>
<label>Movie 2: $INFO[Container(9002).ListItem.Property(Title)]</label>
<label>Movie 3: $INFO[Container(9003).ListItem.Property(Title)]</label>
```

### 3. Dynamic DBID from InfoLabels

```xml
<!-- Use current ListItem's DBID -->
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&type=$INFO[ListItem.DBType]</content>
</control>

<!-- Or from a property -->
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[Window(Home).Property(MyCustom.DBID)]&type=movie</content>
</control>
```

## Comparison with Automatic Service

| Scenario              | Access Method                             | When Updated                 |
| --------------------- | ----------------------------------------- | ---------------------------- |
| **Automatic Service** | `Window(Home).Property(SkinInfo.Movie.*)` | When item is focused         |
| **Plugin Query**      | `Container(ID).ListItem.Property(*)`      | When container content loads |

## Important Notes

1. **All properties from focus are available** - The plugin uses the same JSON-RPC queries as the automatic service, so all properties are available.

2. **Container-based approach** - Properties are set on ListItems within hidden containers. This allows multiple simultaneous queries without conflicts.

