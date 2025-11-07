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
- Supports movies, TV shows, and music

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

### Global Properties (Mixed Media)

Global properties rotate through all media types (movies, TV, music):

```xml
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.Title)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.FanArt)]
$INFO[Window(Home).Property(SkinInfo.Slideshow.Global.Description)]
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
