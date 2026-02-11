# Library Properties

Window properties set automatically by the service when library items are focused.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Unified Properties](#unified-properties)
- [Movies](#movies)
- [Movie Sets](#movie-sets)
- [TV Shows](#tv-shows)
- [Seasons](#seasons)
- [Episodes](#episodes)
- [Music Videos](#music-videos)
- [Artists](#artists)
- [Albums](#albums)
- [Music Player](#music-player)
- [Property Clearing](#property-clearing)

---

## Overview

All properties are available via `Window(Home).Property(...)`. Properties populate automatically when items with a valid `ListItem.DBID` are focused.

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Movie.Title)]</label>
<texture>$INFO[Window(Home).Property(SkinInfo.Movie.Art(poster))]</texture>
```

---

## Unified Properties

**Prefix:** `SkinInfo.ListItem.*`

Media-type-agnostic properties that work regardless of what item is focused.

### Basic Information

| Property | Description | Available For |
|----------|-------------|---------------|
| `Title` | Item title | All |
| `Plot` | Plot or description | Movie, TVShow, Episode, Set, Artist, Album, MusicVideo |
| `Year` | Release year | Movie, TVShow, Album, MusicVideo |
| `Genre` | Genre(s), comma-separated | All except Season |

### Runtime (Video)

| Property | Description | Available For |
|----------|-------------|---------------|
| `Runtime` | Total runtime in minutes | Movie, TVShow, Episode, Set, MusicVideo |
| `Runtime.Hours` | Hours component | Movie, TVShow, Episode, Set, MusicVideo |
| `Runtime.Minutes` | Minutes component | Movie, TVShow, Episode, Set, MusicVideo |

### Duration (Music)

| Property | Description | Available For |
|----------|-------------|---------------|
| `Duration` | Duration in mm:ss format | Album, MusicVideo |
| `Duration.Seconds` | Total seconds | Album, MusicVideo |

### Ratings

| Property | Description | Available For |
|----------|-------------|---------------|
| `Rating` | Primary rating (0-10) | Movie, TVShow, Episode, Album, MusicVideo |
| `Rating.Votes` | Vote count | Movie, TVShow, Episode, Album |
| `Rating.Percent` | Rating as percentage (0-100) | Movie, TVShow, Episode, Album, MusicVideo |
| `UserRating` | User's personal rating (1-10) | All except Set, Artist |
| `Rating.{source}` | Rating from specific source | Movie, TVShow, Episode |
| `Rating.{source}.Votes` | Vote count for source | Movie, TVShow, Episode |
| `Rating.{source}.Percent` | Source rating as percentage | Movie, TVShow, Episode |
| `Tomatometer` | "Fresh" or "Rotten" (based on ≥60%) | Movie, TVShow |
| `Popcornmeter` | "Fresh" or "Spilled" (based on ≥60%) | Movie, TVShow |

### Example

```xml
<label>$INFO[Window(Home).Property(SkinInfo.ListItem.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.ListItem.Year)] - $INFO[Window(Home).Property(SkinInfo.ListItem.Genre)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.ListItem.Rating)]</label>

<!-- Rotten Tomatoes Tomatometer (library data) -->
<control type="image">
    <visible>String.IsEqual(Window(Home).Property(SkinInfo.ListItem.Tomatometer),Fresh)</visible>
    <texture>fresh.png</texture>
</control>
<control type="image">
    <visible>String.IsEqual(Window(Home).Property(SkinInfo.ListItem.Tomatometer),Rotten)</visible>
    <texture>rotten.png</texture>
</control>
```

---

## Movies

**Prefix:** `SkinInfo.Movie.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Title` | Movie title |
| `OriginalTitle` | Original title |
| `Year` | Release year |
| `Plot` | Full plot description |
| `PlotOutline` | Short plot summary |
| `Tagline` | Movie tagline |
| `Rating` | Default rating value |
| `Votes` | Number of votes |
| `UserRating` | User's rating (0-10) |
| `MPAA` | Content rating (PG-13, R, etc.) |
| `Runtime` | Runtime in minutes |
| `Runtime.Hours` | Runtime hours component |
| `Runtime.Minutes` | Runtime minutes component |
| `Premiered` | Premiere date |
| `PercentPlayed` | Playback progress percentage |

### Movie Set

| Property | Description |
|----------|-------------|
| `Set` | Movie set name |
| `SetID` | Movie set database ID |

### Library Data

| Property | Description |
|----------|-------------|
| `Playcount` | Number of times played |
| `LastPlayed` | Last played date |
| `DateAdded` | Date added to library |
| `Tag` | Tags, comma-separated |
| `IMDBNumber` | IMDB ID |
| `Top250` | IMDB Top 250 ranking |
| `UniqueID.IMDB` | IMDB unique ID |
| `UniqueID.TMDB` | TMDB unique ID |
| `Trailer` | Trailer URL |

### Credits

| Property | Description |
|----------|-------------|
| `Director` | Director(s), comma-separated |
| `Writer` | Writer(s), comma-separated |
| `Cast` | Cast members, comma-separated |
| `Genre` | Genre(s), comma-separated |
| `Studio` | Studio(s), comma-separated |
| `StudioPrimary` | First studio only |
| `Country` | Country(ies), comma-separated |

### Technical

| Property | Description |
|----------|-------------|
| `Path` | File path |
| `FileName` | File name without path |
| `FileExtension` | File extension (mkv, mp4, etc.) |
| `Codec` | Video codec |
| `Resolution` | Video resolution (480, 720, 1080, 4k, 8k) |
| `Aspect` | Aspect ratio (1.33, 1.78, 2.35, etc.) |
| `AudioCodec` | Audio codec |
| `AudioChannels` | Audio channel count |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(discart)` | Disc art |

### Ratings

| Property | Description |
|----------|-------------|
| `Rating.{source}` | Scaled rating (0-10) |
| `Rating.{source}.Votes` | Vote count |
| `Rating.{source}.Percent` | Percentage (0-100) |
| `Tomatometer` | "Fresh" or "Rotten" (based on ≥60%) |
| `Popcornmeter` | "Fresh" or "Spilled" (based on ≥60%) |

---

## Movie Sets

**Prefix:** `SkinInfo.Set.*`

### Set Information

| Property | Description |
|----------|-------------|
| `Title` | Set title |
| `Plot` | Set plot description |
| `Count` | Number of movies in set |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(discart)` | Disc art |

### Aggregates

| Property | Description |
|----------|-------------|
| `Titles` | Formatted list of all movie titles |
| `Plots` | Combined plots of all movies |
| `ExtendedPlots` | Titles + plots combined |
| `Runtime` | Total runtime in minutes |
| `Runtime.Hours` | Hours component |
| `Runtime.Minutes` | Minutes component |
| `Years` | Years list (separated by " / ") |
| `Writers` | All writers (de-duped, separated by " / ") |
| `Directors` | All directors (de-duped, separated by " / ") |
| `Genres` | All genres (de-duped, separated by " / ") |
| `Countries` | All countries (de-duped, separated by " / ") |
| `Studios` | All studios (de-duped, separated by " / ") |

### Indexed Aggregates

Use `%d` as placeholder for index (1-based):

| Property | Description |
|----------|-------------|
| `Writers.%d` | Individual writer |
| `Directors.%d` | Individual director |
| `Genres.%d` | Individual genre |
| `Countries.%d` | Individual country |
| `Studios.%d` | Primary studio per movie |

### Per-Movie Properties

Use `%d` as placeholder for index (1-based):

| Property | Description |
|----------|-------------|
| `Movie.%d.DBID` | Database ID |
| `Movie.%d.Title` | Movie title |
| `Movie.%d.Path` | File path |
| `Movie.%d.Year` | Release year |
| `Movie.%d.Duration` | Runtime in minutes |
| `Movie.%d.Plot` | Full plot |
| `Movie.%d.PlotOutline` | Short summary |
| `Movie.%d.Genre` | Genre(s) |
| `Movie.%d.Director` | Director(s) |
| `Movie.%d.Writer` | Writer(s) |
| `Movie.%d.Studio` | Studio(s) |
| `Movie.%d.StudioPrimary` | First studio only |
| `Movie.%d.Country` | Country(ies) |
| `Movie.%d.VideoResolution` | Video resolution |
| `Movie.%d.MPAA` | Content rating |
| `Movie.%d.Art(poster)` | Poster |
| `Movie.%d.Art(fanart)` | Fanart |
| `Movie.%d.Art(clearlogo)` | Clear logo |
| `Movie.%d.Art(keyart)` | Key art |
| `Movie.%d.Art(landscape)` | Landscape |
| `Movie.%d.Art(banner)` | Banner |
| `Movie.%d.Art(clearart)` | Clear art |
| `Movie.%d.Art(discart)` | Disc art |

---

## TV Shows

**Prefix:** `SkinInfo.TVShow.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Title` | TV show title |
| `OriginalTitle` | Original title |
| `SortTitle` | Sort title |
| `Year` | Year started |
| `Plot` | Full plot description |
| `Premiered` | Premiere date |
| `Rating` | Default rating value |
| `Votes` | Number of votes |
| `UserRating` | User's rating (0-10) |
| `MPAA` | Content rating |
| `Status` | Status (Continuing, Ended) |

### Show Details

| Property | Description |
|----------|-------------|
| `Episode` | Total episode count |
| `Season` | Total season count |
| `WatchedEpisodes` | Number of watched episodes |
| `Runtime` | Episode runtime in minutes |
| `EpisodeGuide` | Episode guide URL |
| `Trailer` | Trailer URL |

### Library Data

| Property | Description |
|----------|-------------|
| `Playcount` | Number of times played |
| `LastPlayed` | Last played date |
| `DateAdded` | Date added to library |
| `Path` | File path |
| `IMDBNumber` | IMDB ID |
| `UniqueID.IMDB` | IMDB unique ID |
| `UniqueID.TMDB` | TMDB unique ID |
| `UniqueID.TVDB` | TVDB unique ID |

### Credits

| Property | Description |
|----------|-------------|
| `Cast` | Cast members, comma-separated |
| `Genre` | Genre(s), comma-separated |
| `Studio` | Studio(s), comma-separated |
| `StudioPrimary` | First studio only |
| `Tag` | Tags, comma-separated |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(thumb)` | Thumbnail |

---

## Seasons

**Prefix:** `SkinInfo.Season.*`

| Property | Description |
|----------|-------------|
| `Title` | Season title |
| `Season` | Season number |
| `ShowTitle` | Parent TV show title |
| `Episode` | Total episodes in season |
| `WatchedEpisodes` | Number of watched episodes |
| `Playcount` | Play count |
| `UserRating` | User's rating (0-10) |
| `TVShowID` | Parent TV show database ID |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(thumb)` | Thumbnail |

---

## Episodes

**Prefix:** `SkinInfo.Episode.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Title` | Episode title |
| `OriginalTitle` | Original title |
| `Plot` | Episode plot |
| `Season` | Season number |
| `Episode` | Episode number |
| `TVShow` | Parent TV show title |
| `Rating` | Episode rating |
| `Votes` | Number of votes |
| `UserRating` | User's rating (0-10) |

### Episode Details

| Property | Description |
|----------|-------------|
| `FirstAired` | Original air date |
| `Runtime` | Runtime in minutes |
| `ProductionCode` | Production code |
| `TVShowID` | Parent TV show database ID |
| `SeasonID` | Season database ID |

### Library Data

| Property | Description |
|----------|-------------|
| `Playcount` | Play count |
| `LastPlayed` | Last played date |
| `DateAdded` | Date added to library |
| `Path` | File path |
| `UniqueID.IMDB` | IMDB unique ID |
| `UniqueID.TMDB` | TMDB unique ID |
| `UniqueID.TVDB` | TVDB unique ID |

### Credits

| Property | Description |
|----------|-------------|
| `Cast` | Cast members, comma-separated |
| `Director` | Director(s), comma-separated |
| `Writer` | Writer(s), comma-separated |
| `Genre` | Genre(s), comma-separated |
| `Studio` | Studio(s), comma-separated |

### Technical

| Property | Description |
|----------|-------------|
| `Codec` | Video codec |
| `Resolution` | Video resolution (480, 720, 1080, 4k, 8k) |
| `Aspect` | Aspect ratio |
| `AudioCodec` | Audio codec |
| `AudioChannels` | Audio channel count |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(thumb)` | Thumbnail |

---

## Music Videos

**Prefix:** `SkinInfo.MusicVideo.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Title` | Music video title |
| `Artist` | Artist(s), comma-separated |
| `ArtistPrimary` | First artist only |
| `Album` | Album name |
| `Year` | Release year |
| `Plot` | Description |
| `Runtime` | Runtime (mm:ss format) |
| `Premiered` | Release date |
| `Track` | Track number |

### Library Data

| Property | Description |
|----------|-------------|
| `Playcount` | Play count |
| `LastPlayed` | Last played date |
| `DateAdded` | Date added to library |
| `Path` | File path |
| `Rating` | Rating |
| `UserRating` | User's rating (0-10) |
| `UniqueID.IMDB` | IMDB unique ID |
| `UniqueID.TMDB` | TMDB unique ID |

### Credits

| Property | Description |
|----------|-------------|
| `Genre` | Genre(s), comma-separated |
| `Director` | Director(s), comma-separated |
| `Studio` | Studio(s), comma-separated |
| `Tag` | Tags, comma-separated |

### Technical

| Property | Description |
|----------|-------------|
| `Codec` | Video codec |
| `Resolution` | Video resolution |
| `Aspect` | Aspect ratio |
| `AudioCodec` | Audio codec |
| `AudioChannels` | Audio channel count |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(poster)` | Poster |
| `Art(fanart)` | Fanart |
| `Art(clearlogo)` | Clear logo |
| `Art(keyart)` | Key art |
| `Art(landscape)` | Landscape |
| `Art(banner)` | Banner |
| `Art(clearart)` | Clear art |
| `Art(thumb)` | Thumbnail |

---

## Artists

**Prefix:** `SkinInfo.Artist.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Artist` | Artist name |
| `Description` | Artist biography |
| `Genre` | Genre(s), comma-separated |
| `DateAdded` | Date added to library |

### Artist Details

| Property | Description |
|----------|-------------|
| `Style` | Style(s), comma-separated |
| `Mood` | Mood(s), comma-separated |
| `Instrument` | Instrument(s), comma-separated |
| `YearsActive` | Years active, comma-separated |
| `Born` | Birth date |
| `Formed` | Formation date (for bands) |
| `Died` | Death date |
| `Disbanded` | Disbanded date (for bands) |
| `Type` | Artist type (person/group) |
| `Gender` | Gender |
| `SortName` | Sort name |
| `Disambiguation` | Disambiguation string |
| `MusicBrainzID` | MusicBrainz ID(s) |
| `Roles` | Roles, comma-separated |
| `SongGenres` | Song genres, comma-separated |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(thumb)` | Thumbnail |
| `Art(fanart)` | Fanart |

### Album Aggregates

| Property | Description |
|----------|-------------|
| `Albums.Newest` | Most recent album year |
| `Albums.Oldest` | Oldest album year |
| `Albums.Count` | Total album count |
| `Albums.Playcount` | Total playcount across albums |

### Per-Album Properties

Use `%d` as placeholder for index (1-based):

| Property | Description |
|----------|-------------|
| `Album.%d.Title` | Album title |
| `Album.%d.Year` | Release year |
| `Album.%d.Artist` | Artist name |
| `Album.%d.Genre` | Genre |
| `Album.%d.DBID` | Database ID |
| `Album.%d.Label` | Record label |
| `Album.%d.Playcount` | Play count |
| `Album.%d.Rating` | Album rating |
| `Album.%d.Art(thumb)` | Thumbnail artwork |
| `Album.%d.Art(discart)` | Disc artwork |

---

## Albums

**Prefix:** `SkinInfo.Album.*`

### Basic Information

| Property | Description |
|----------|-------------|
| `Title` | Album title |
| `Year` | Release year |
| `Artist` | Artist(s), comma-separated |
| `DisplayArtist` | Display artist name |
| `SortArtist` | Sort artist name |
| `Genre` | Genre(s), comma-separated |
| `SongGenres` | Song genres, comma-separated |
| `Label` | Record label |
| `Description` | Album description |

### Album Details

| Property | Description |
|----------|-------------|
| `Playcount` | Play count |
| `Rating` | Album rating |
| `UserRating` | User rating |
| `Votes` | Number of votes |
| `MusicBrainzID` | MusicBrainz Album ID |
| `ReleaseGroupID` | MusicBrainz Release Group ID |
| `LastPlayed` | Last played timestamp |
| `DateAdded` | Date added to library |
| `Compilation` | Whether album is a compilation |
| `ReleaseType` | Release type |
| `TotalDiscs` | Total number of discs |
| `ReleaseDate` | Release date |
| `OriginalDate` | Original release date |
| `AlbumDuration` | Total duration in seconds |

### Artwork

| Property | Description |
|----------|-------------|
| `Art(thumb)` | Thumbnail |
| `Art(fanart)` | Fanart |
| `Art(discart)` | Disc art |

### Song Aggregates

| Property | Description |
|----------|-------------|
| `Songs.Tracklist` | Formatted tracklist |
| `Songs.Discs` | Number of discs |
| `Songs.Duration` | Total duration (mm:ss) |
| `Songs.Count` | Total song count |

### Per-Song Properties

Use `%d` as placeholder for index (1-based):

| Property | Description |
|----------|-------------|
| `Song.%d.Title` | Song title |
| `Song.%d.Duration` | Duration (mm:ss) |
| `Song.%d.Track` | Track number |
| `Song.%d.FileExtension` | File extension |

---

## Music Player

**Prefix:** `SkinInfo.Player.Music.*`

Properties from the Kodi music library, set automatically during music playback when the artist changes. Only populated for library artists.

### Artist

| Property | Description |
|----------|-------------|
| `Artist` | Current artist name |
| `Bio` | Artist biography from library |
| `FanArt` | Artist fanart from library |

### Album Discography

| Property | Description |
|----------|-------------|
| `Album.Count` | Number of albums (up to 20) |
| `Album.{N}.Title` | Album title |
| `Album.{N}.Year` | Album year |
| `Album.{N}.Thumb` | Album thumbnail |

Albums are sorted by year (ascending).

### Example

```xml
<control type="group">
    <visible>Player.HasAudio</visible>

    <!-- Artist fanart from library -->
    <control type="image">
        <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.Player.Music.FanArt))</visible>
        <texture>$INFO[Window(Home).Property(SkinInfo.Player.Music.FanArt)]</texture>
    </control>

    <!-- Artist bio from library -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Music.Bio)]</label>
    </control>

    <!-- Album count -->
    <control type="label">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Music.Album.Count)] Albums</label>
    </control>
</control>
```

Properties clear automatically when playback stops or the artist changes.

---

## Property Clearing

Properties clear automatically when:

- Switching media types (movie → tvshow)
- Losing focus (DBID becomes empty)
- Indexed properties shrink (set with 5 movies → 3 movies)

---

[↑ Top](#library-properties) · [Index](../index.md)
