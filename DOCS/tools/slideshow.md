# Slideshow

Rotating fanart backgrounds from your library.

[← Back to Index](../index.md)

---

## Overview

The slideshow feature provides rotating fanart backgrounds for your skin. It exposes window properties with random items from your library for background slideshows, screensavers, or ambient displays.

## Key Features

- No performance impact unless explicitly enabled
- Uses database cache for property updates
- Automatically updates when library is scanned or cleaned
- Configurable refresh interval from 1 second to 1 hour
- Supports movies, TV shows, music, and music videos
- Can rotate through a specific playlist or node instead of the whole library

## Enabling Slideshow

### In Skin Settings

```xml
<!-- Toggle to enable/disable slideshow -->
<control type="radiobutton">
    <label>Enable Background Slideshow</label>
    <onclick>Skin.ToggleSetting(SkinInfo.EnableSlideshow)</onclick>
    <selected>Skin.HasSetting(SkinInfo.EnableSlideshow)</selected>
</control>

<!-- Set refresh interval (5-3600 seconds, default 10) -->
<control type="edit">
    <label>Slideshow Refresh (seconds)</label>
    <default>10</default>
    <onclick>Skin.SetString(SkinInfo.SlideshowRefreshInterval)</onclick>
    <value>$INFO[Skin.String(SkinInfo.SlideshowRefreshInterval)]</value>
</control>
```

### Via Onclick

```xml
<!-- Enable slideshow with RunScript -->
<onclick>Skin.SetBool(SkinInfo.EnableSlideshow)</onclick>
<onclick>Skin.SetString(SkinInfo.SlideshowRefreshInterval,15)</onclick>
```

## Available Properties

All slideshow properties use the `SkinInfo.Slideshow.*` and are accessible as window properties.

### Movie Properties

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Plot)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Year)]
```

### TV Show Properties

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.Plot)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.Year)]
```

### Video Properties (Movies + TV Shows)

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Video.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Video.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Video.Plot)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Video.Year)]
```

### Music Properties

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Music.Artist)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Music.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Music.Description)]
```

### Music Video Properties

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.MusicVideo.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.MusicVideo.Artist)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.MusicVideo.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.MusicVideo.Plot)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.MusicVideo.Year)]
```

A music video's fanart is its own, not the artist's, so this group reaches artwork the Music
group cannot: a music video by an artist with no music library entry still has a background.
The same artist can appear in both groups with different images.

### Global Properties (Mixed Media)

Global properties rotate through all media types (movies, TV, music, music videos):

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.Description)]
```

## Playlist Backgrounds

The properties above rotate through the whole library. To rotate through one specific list instead
(a playlist, a library node, any directory path), register it by name and read the properties back
under that name.

### Registering

Set `SkinInfo.Slideshow.Playlist.Paths` to a `name=path` manifest, separated by `|`:

```xml
<onload>SetProperty(SkinInfo.Slideshow.Playlist.Paths,unwatched=special://profile/playlists/video/Unwatched.xsp|rock=musicdb://artists/12/,Home)</onload>
```

Names are yours to choose and become part of the property name. Change the manifest at any time and
the slideshow follows it; clearing the property stops the rotation and drops the properties.

### Reading

Each registered name publishes the same set:

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Playlist.unwatched.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Playlist.unwatched.Title)]
```

| Suffix        | Description                                        |
|---------------|----------------------------------------------------|
| `Title`       | Item title                                         |
| `FanArt`      | Fanart, falling back to the show or artist art     |
| `Plot`        | Plot                                               |
| `Year`        | Year                                               |
| `Artist`      | Artist, for music and music video items            |
| `Description` | Artist biography, for songs and albums             |

### What can be registered

Anything Kodi can list: smart playlists, `videodb://` and `musicdb://` nodes, folders. Items
without fanart are skipped, so a list with no artwork publishes nothing.

Movies, TV shows, episodes, music videos, movie sets, songs, albums and artists are all eligible.
Episodes take show fanart, and songs and albums take artist fanart, so an episode or album list is
still usable as a background.

### Example

```xml
<control type="multiimage">
    <imagepath background="true">$INFO[Window(Home).Property(SkinInfo.Slideshow.Playlist.unwatched.FanArt)]</imagepath>
    <aspectratio>scale</aspectratio>
    <fadetime>1000</fadetime>
</control>
<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Slideshow.Playlist.unwatched.Title)]</label>
</control>
```

## Usage Examples

### Simple Background Fanart

```xml
<control type="multiimage">
    <visible>Skin.HasSetting(SkinInfo.EnableSlideshow)</visible>
    <imagepath>$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.FanArt)]</imagepath>
    <aspectratio>scale</aspectratio>
    <fadetime>1000</fadetime>
</control>
```

### Movie-Only Slideshow

```xml
<control type="image">
    <texture>$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.FanArt)]</texture>
    <aspectratio>scale</aspectratio>
</control>

<control type="label">
    <label>$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Title)]</label>
</control>

<control type="textbox">
    <label>$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Plot)]</label>
</control>
```

### Multi-Panel Slideshow

```xml
<!-- Movie panel -->
<control type="group">
    <control type="image">
        <texture>$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.FanArt)]</texture>
    </control>
    <control type="label">
        <label>$INFO[Window(Home).Property(SkinInfo.Slideshow.Movie.Title)]</label>
    </control>
</control>

<!-- TV panel -->
<control type="group">
    <control type="image">
        <texture>$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.FanArt)]</texture>
    </control>
    <control type="label">
        <label>$INFO[Window(Home).Property(SkinInfo.Slideshow.TV.Title)]</label>
    </control>
</control>
```

### Conditional Visibility

```xml
<!-- Only show slideshow in specific windows -->
<control type="image">
    <visible>Skin.HasSetting(SkinInfo.EnableSlideshow) + Window.IsVisible(Home)</visible>
    <texture>$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.FanArt)]</texture>
</control>

<!-- Hide slideshow during playback -->
<control type="image">
    <visible>Skin.HasSetting(SkinInfo.EnableSlideshow) + !Player.HasMedia</visible>
    <texture>$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.FanArt)]</texture>
</control>
```

## Settings Reference

### SkinInfo.EnableSlideshow

**Type:** Boolean (Skin.HasSetting)
**Default:** False (disabled)
**Description:** Master toggle for slideshow functionality

### SkinInfo.SlideshowRefreshInterval

**Type:** Integer (Skin.String)
**Range:** 5-3600 seconds
**Default:** 10 seconds
**Description:** How often slideshow properties update

### Troubleshooting

**Slideshow not updating:**

- Verify `Skin.HasSetting(SkinInfo.EnableSlideshow)` is true
- Check Kodi log for "Slideshow:" messages
- Ensure library has items with fanart

**Properties are empty:**

- Pool may be empty - check Kodi log for "Slideshow: Pool populated with X items"
- Trigger library scan to populate pool
- Verify fanart exists in library (check ListItem.Art(fanart) on media)

**Performance issues:**

- Increase refresh interval (try 30-60 seconds)
- Verify slideshow is disabled when not needed
- Check for database errors in Kodi log

---

[↑ Top](#slideshow) · [Index](../index.md)
