# Online Properties

Window properties from external APIs, updated automatically when library items are focused or during playback.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Player Online Properties](#player-online-properties)
- [Music Video Online Properties](#music-video-online-properties)
- [Music Player Online Properties](#music-player-online-properties)
- [Enabling the Service](#enabling-the-service)
- [TMDb Properties](#tmdb-properties)
- [Ratings](#ratings)
- [Rotten Tomatoes Status](#rotten-tomatoes-status)
- [Awards](#awards)
- [Common Sense Media](#common-sense-media)
- [Trakt](#trakt)
- [MDBList](#mdblist)

---

## Overview

The online service fetches metadata from external APIs when library items are focused or during video playback:

- **TMDb** - Full metadata, images, credits, trailers
- **OMDb** - Awards data
- **MDBList** - Ratings, Common Sense Media, RT status
- **Trakt** - Ratings, subgenres

**Library browsing** - Properties set with `SkinInfo.Online.*` prefix:

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Online.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Online.Rating.imdb)]</label>
```

**Video playback** - Properties set with `SkinInfo.Player.Online.*` prefix:

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Rating.imdb)]</label>
```

Supported media types: `movie`, `tvshow`, `episode`, `musicvideo`

---

## Player Online Properties

The same properties available for library browsing are also available during video playback with the `SkinInfo.Player.Online.*` prefix.

| Context | Property Prefix |
|---------|-----------------|
| Library browsing | `SkinInfo.Online.` |
| Video playback | `SkinInfo.Player.Online.` |

Both contexts can be active simultaneously - you can browse the library while playing a video, and each will have its own set of properties.

### Example

```xml
<!-- Now playing info overlay -->
<control type="group">
    <visible>Player.HasVideo</visible>
    <control type="label">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Title)]</label>
    </control>
    <control type="label">
        <label>IMDb: $INFO[Window(Home).Property(SkinInfo.Player.Online.Rating.imdb)]</label>
    </control>
    <control type="label">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Awards)]</label>
    </control>
</control>
```

---

## Music Video Online Properties

**Prefix:** `SkinInfo.MusicVideo.Online.*`

Properties fetched from AudioDB, Last.fm, Wikipedia, and Fanart.tv when music video items or music video artist nodes are focused.

### Artist

| Property           | Description                                |
|--------------------|--------------------------------------------|
| `Artist.Bio`       | Artist biography (AudioDB / Last.fm)       |
| `Artist.FanArt`    | Current fanart URL (rotates automatically) |
| `Artist.FanArt.Count` | Total fanart images available           |
| `Artist.Thumb`     | Artist thumbnail (Fanart.tv / AudioDB)     |
| `Artist.Clearlogo` | Artist clearlogo (Fanart.tv / AudioDB)     |
| `Artist.Banner`    | Artist banner (Fanart.tv / AudioDB)        |

### Track

| Property           | Description                           |
|--------------------|---------------------------------------|
| `Track.Wiki`       | Track description (Last.fm / Wikipedia / AudioDB) |
| `Track.Tags`       | Top tags (" / " separated, up to 10) |
| `Track.Listeners`  | Last.fm listener count                |
| `Track.Playcount`  | Last.fm global play count             |

### Album

| Property           | Description                           |
|--------------------|---------------------------------------|
| `Album.Wiki`       | Album description (Last.fm / Wikipedia / AudioDB) |
| `Album.Tags`       | Top tags (" / " separated, up to 10) |
| `Album.Label`      | Record label                          |

### Example

```xml
<control type="group">
    <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.MusicVideo.Online.Artist.Bio))</visible>

    <!-- Artist fanart background -->
    <control type="image">
        <texture>$INFO[Window(Home).Property(SkinInfo.MusicVideo.Online.Artist.FanArt)]</texture>
    </control>

    <!-- Artist bio -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.MusicVideo.Online.Artist.Bio)]</label>
    </control>

    <!-- Track wiki -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.MusicVideo.Online.Track.Wiki)]</label>
    </control>
</control>
```

---

## Music Player Online Properties

Properties fetched from AudioDB, Last.fm, Wikipedia, and Fanart.tv during playback. Works with library items, local files, and radio addon streams.

Audio and music video playback use separate prefixes:

| Context | Prefix |
|---------|--------|
| Audio playback | `SkinInfo.Player.Online.Music.` |
| Music video playback | `SkinInfo.Player.Online.MusicVideo.` |

### Artist

| Property           | Description                                |
|--------------------|--------------------------------------------|
| `Artist.Name`      | Artist name                                |
| `Artist.Bio`       | Artist biography (AudioDB / Last.fm)       |
| `Artist.FanArt`    | Current fanart URL (rotates automatically) |
| `Artist.FanArt.Count` | Total fanart images available           |
| `Artist.Thumb`     | Artist thumbnail (Fanart.tv / AudioDB)     |
| `Artist.Clearlogo` | Artist clearlogo (Fanart.tv / AudioDB)     |
| `Artist.Banner`    | Artist banner (Fanart.tv / AudioDB)        |

### Track

Populated when a track title is available.

| Property           | Description                           |
|--------------------|---------------------------------------|
| `Track.Wiki`       | Track description (Last.fm / Wikipedia / AudioDB) |
| `Track.Tags`       | Top tags (" / " separated, up to 10) |
| `Track.Listeners`  | Last.fm listener count                |
| `Track.Playcount`  | Last.fm global play count             |

### Album

Populated when an album name is available.

| Property           | Description                           |
|--------------------|---------------------------------------|
| `Album.Wiki`       | Album description (Last.fm / Wikipedia / AudioDB) |
| `Album.Tags`       | Top tags (" / " separated, up to 10) |
| `Album.Label`      | Record label                          |

Fanart rotation interval is controlled by the skin string `SkinInfo.SlideshowRefreshInterval` (seconds, default 10, range 5-3600).

Fanart.tv is the primary source. TheAudioDB fanart is used only if Fanart.tv returns no results.

### Example — Audio Playback

```xml
<control type="group">
    <visible>Player.HasAudio</visible>

    <!-- Rotating artist fanart background -->
    <control type="image">
        <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.Player.Online.Music.Artist.FanArt))</visible>
        <texture>$INFO[Window(Home).Property(SkinInfo.Player.Online.Music.Artist.FanArt)]</texture>
    </control>

    <!-- Artist bio -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Music.Artist.Bio)]</label>
    </control>

    <!-- Track info -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Online.Music.Track.Wiki)]</label>
    </control>
</control>
```

### Example — Music Video Playback

```xml
<control type="group">
    <visible>Player.HasVideo + VideoPlayer.Content(musicvideos)</visible>

    <!-- Artist clearlogo -->
    <control type="image">
        <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.Player.Online.MusicVideo.Artist.Clearlogo))</visible>
        <texture>$INFO[Window(Home).Property(SkinInfo.Player.Online.MusicVideo.Artist.Clearlogo)]</texture>
    </control>

    <!-- Track wiki -->
    <control type="textbox">
        <label>$INFO[Window(Home).Property(SkinInfo.Player.Online.MusicVideo.Track.Wiki)]</label>
    </control>
</control>
```

### Slideshow Interval

Set the rotation interval via a skin string:

```xml
<control type="button">
    <label>Slideshow Interval</label>
    <onclick>Skin.SetNumeric(SkinInfo.SlideshowRefreshInterval)</onclick>
</control>
```

---

## Enabling the Service

The online service runs automatically when the main service is started. API keys are required for some data sources.

**API Key Settings:**

| API | Required | Setting Location |
|-----|----------|------------------|
| TMDb | No | Settings → Advanced (custom key optional) |
| OMDb | No | Settings → API Keys |
| MDBList | No | Settings → API Keys |
| Trakt | No | Settings → API Keys |

TMDb uses a built-in API key by default. You can optionally provide your own key in Advanced settings.

---

## TMDb Properties

### Basic Information

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

### Movie-Specific

| Property | Description |
|----------|-------------|
| `Budget` | Production budget (formatted with commas) |
| `Revenue` | Box office revenue (formatted with commas) |
| `Set` | Collection name |
| `SetID` | Collection TMDb ID |

### TV Show-Specific

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

### Credits

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

### Images

| Property | Description |
|----------|-------------|
| `Poster` | Poster image URL |
| `Fanart` | Backdrop image URL |
| `Clearlogo` | Clear logo URL (English preferred) |

### IDs

| Property | Description |
|----------|-------------|
| `IMDBNumber` | IMDB ID |
| `TMDBID` | TMDb ID |
| `TVDBID` | TVDB ID (TV shows only) |

### Other

| Property | Description |
|----------|-------------|
| `MPAA` | US certification (PG-13, R, TV-MA, etc.) |
| `Trailer` | YouTube trailer plugin URL |
| `TrailerYouTubeID` | YouTube video ID |
| `Tag` | Keywords separated by " / " |

---

## Ratings

Ratings from multiple sources. Each source provides three properties.

| Property Pattern | Description |
|------------------|-------------|
| `Rating.{source}` | Rating value (0-10 scale) |
| `Rating.{source}.Votes` | Vote count |
| `Rating.{source}.Percent` | Rating as percentage (0-100) |

### Available Sources

| Source | Property Prefix | Provider |
|--------|-----------------|----------|
| TMDb | `Rating.tmdb` | TMDb |
| IMDb | `Rating.imdb` | MDBList |
| Trakt | `Rating.trakt` | Trakt |
| Metacritic | `Rating.metacritic` | MDBList |
| Metacritic User | `Rating.metacriticuser` | MDBList |
| Letterboxd | `Rating.letterboxd` | MDBList |
| RT Critics | `Rating.Tomatoes` | MDBList |
| RT Audience | `Rating.Popcorn` | MDBList |
| Roger Ebert | `Rating.rogerebert` | MDBList |
| MyAnimeList | `Rating.myanimelist` | MDBList |

### Example

```xml
<label>TMDb: $INFO[Window(Home).Property(SkinInfo.Online.Rating.tmdb)]</label>
<label>IMDb: $INFO[Window(Home).Property(SkinInfo.Online.Rating.imdb)]</label>
<label>RT Critics: $INFO[Window(Home).Property(SkinInfo.Online.Rating.Tomatoes.Percent)]%</label>
```

---

## Rotten Tomatoes Status

| Property | Values | Description |
|----------|--------|-------------|
| `Tomatometer` | "Certified", "Fresh", "Rotten" | Critics status |
| `Popcornmeter` | "Hot", "Fresh", "Spilled" | Audience status |

### Example

```xml
<control type="image">
    <visible>String.IsEqual(Window(Home).Property(SkinInfo.Online.Tomatometer),Certified)</visible>
    <texture>certified-fresh.png</texture>
</control>
<control type="image">
    <visible>String.IsEqual(Window(Home).Property(SkinInfo.Online.Tomatometer),Fresh)</visible>
    <texture>fresh.png</texture>
</control>
<control type="image">
    <visible>String.IsEqual(Window(Home).Property(SkinInfo.Online.Tomatometer),Rotten)</visible>
    <texture>rotten.png</texture>
</control>
```

---

## Awards

Awards data from OMDb. Requires OMDb API key.

| Property | Description |
|----------|-------------|
| `Awards` | Full awards text |
| `Awards.Oscar.Wins` | Number of Oscars won |
| `Awards.Oscar.Nominations` | Number of Oscar nominations |
| `Awards.Emmy.Wins` | Number of Emmys won |
| `Awards.Emmy.Nominations` | Number of Emmy nominations |
| `Awards.Other.Wins` | Other award wins |
| `Awards.Other.Nominations` | Other award nominations |

### Example

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Online.Awards)]</label>
<label>Oscars: $INFO[Window(Home).Property(SkinInfo.Online.Awards.Oscar.Wins)] wins, $INFO[Window(Home).Property(SkinInfo.Online.Awards.Oscar.Nominations)] nominations</label>
```

---

## Common Sense Media

Parental guidance data from MDBList. Requires MDBList API key.

| Property | Description |
|----------|-------------|
| `CommonSense.Age` | Recommended minimum age |
| `CommonSense.Violence` | Violence severity (1-5) |
| `CommonSense.Nudity` | Nudity severity (1-5) |
| `CommonSense.Language` | Language severity (1-5) |
| `CommonSense.Drinking` | Substance use severity (1-5) |
| `CommonSense.Selection` | "true" if Common Sense Selection |
| `CommonSense.Summary` | Localized summary |
| `CommonSense.Reasons` | Localized content reasons |

Severity levels: 1 = Minimal, 5 = Severe

### Example

```xml
<label>Ages $INFO[Window(Home).Property(SkinInfo.Online.CommonSense.Age)]+</label>
<label>$INFO[Window(Home).Property(SkinInfo.Online.CommonSense.Summary)]</label>
```

---

## Trakt

Data from Trakt API.

| Property | Description |
|----------|-------------|
| `Trakt.Subgenres` | Curated subgenres separated by " / " |

Rating properties are included in the [Ratings](#ratings) section.

### Example

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Online.Trakt.Subgenres)]</label>
```

---

## MDBList

Additional data from MDBList.

| Property | Description |
|----------|-------------|
| `MDBList.Trailer` | Trailer URL |
| `MDBList.Certification` | Content certification |

---

[↑ Top](#online-properties) · [Index](../index.md)
