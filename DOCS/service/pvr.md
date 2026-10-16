# Live TV Properties

Artwork and details for the focused live TV programme, from TMDb.

[← Back to Index](../index.md)

---

## Enable

Needs the Online service, see [Getting Started](../getting-started.md#enabling-the-service).

```xml
<control type="radiobutton" id="100">
    <label>Live TV Artwork</label>
    <onclick>Skin.ToggleSetting(SkinInfo.PVR)</onclick>
    <selected>Skin.HasSetting(SkinInfo.PVR)</selected>
</control>
```

---

## Covered Items

- TV guide entries and PVR search results
- TV channels, for the programme on now
- TV recordings
- TV timers with a guide entry
- The PVR info dialogs for any of the above

Radio, news and sports programmes get no properties. A programme also gets none when TMDb has no
clear match for its title, such as two shows with the same name and no year to tell them apart.

---

## Properties

All under `SkinInfo.PVR.`, for the matched movie or TV show.

| Property | Description |
|----------|-------------|
| `MediaType` | `movie` or `tvshow` |
| [TMDb Properties](online.md#tmdb-properties) | Every property in those tables except `PlotOutline`, including `Poster`, `Fanart` and `Clearlogo` |
| `Rating.tmdb`, `Rating.tmdb.Votes`, `Rating.tmdb.Percent` | TMDb rating, see [Ratings](online.md#ratings) |
| `Rating`, `Votes` | Same as `Rating.tmdb` and `Rating.tmdb.Votes` |
| `Awards.*` | Award counts, see [Award Counts](online.md#award-counts) |

The properties clear when focus leaves live TV. A programme seen before shows at once, a new one a
moment after focus settles.

```xml
<control type="image">
    <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.PVR.Poster))</visible>
    <texture>$INFO[Window(Home).Property(SkinInfo.PVR.Poster)]</texture>
</control>
```

---

## Playback

While a TV channel or TV recording plays, the same properties are set under
`SkinInfo.Player.PVR.` for the programme playing. They change when the channel moves on to the next
programme, and clear when playback stops.

```xml
<texture>$INFO[Window(Home).Property(SkinInfo.Player.PVR.Fanart)]</texture>
```

---

## Fix a Match

**Fix match** in the context menu of a covered item lists the movies and TV shows found for its
title. Picking one sets it for that programme, and **None** stops it getting any properties. A
fixed match is kept, and the programme is not looked up again.

A skin can offer the same list from a button, such as one in the PVR info dialog:

```xml
<onclick>RunScript(script.skin.info.service,action=pvr_match)</onclick>
```

---

[↑ Top](#live-tv-properties) · [Index](../index.md)
