# Online Data

Fetch ratings, awards, and metadata from external APIs via plugin container.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Usage](#usage)
- [RunScript Trigger](#runscript-trigger)
- [Two-Container Pattern](#two-container-pattern)
- [Available Properties](#available-properties)
- [Music Video Properties](#music-video-properties)

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
| `dbtype` | Yes | `movie`, `tvshow`, `episode`, or `musicvideo` |
| `dbid` | * | Database ID (library items) |
| `tmdb_id` | * | TMDb ID (non-library items, video only) |
| `imdb_id` | * | IMDB ID (non-library items, video only) |
| `reload` | No | Any value; a change forces a refetch |

\* Provide one of: `dbid`, `tmdb_id`, or `imdb_id`

**Note:** For episodes, the parent TV show's online data is returned. For music videos, data comes from AudioDB, Last.fm, and Fanart.tv instead of TMDb.

---

## RunScript Trigger

`action=online_fetch` runs the same online fetch as the plugin URL above, then writes a plugin URL into a Window property the skin can bind to a container. Use this when the source item is set by a button or click rather than by a static skin path.

```xml
<onclick>RunScript(script.skin.info.service,action=online_fetch,
  dbid=$INFO[ListItem.DBID],
  dbtype=$INFO[ListItem.DBType],
  property=SkinInfo.Online.Content,
  window=home)</onclick>

<control type="list" id="9001">
    <content>$INFO[Window(Home).Property(SkinInfo.Online.Content)]</content>
</control>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | Yes | - | `movie`, `tvshow`, `episode` |
| `dbid` | * | - | Library ID |
| `tmdb_id` | * | - | TMDB ID |
| `imdb_id` | * | - | IMDb ID |
| `property` | No | `SkinInfo.Online.Content` | Window property name to set |
| `window` | No | `home` | Window to set the property on (`home` for Home window) |

\* Provide one of `dbid`, `tmdb_id`, or `imdb_id`.

---

## Two-Container Pattern

Use two hidden containers - Kodi data loads instantly, online data appears when ready:

```xml
<!-- Container 1: Fast Kodi data -->
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?dbid=$INFO[ListItem.DBID]&amp;dbtype=movie</content>
</control>

<!-- Container 2: Online data -->
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

The plugin item carries the same properties as [Online Properties](../service/online.md), read as
`Container(ID).ListItem.Property(<name>)` with no `SkinInfo.Online.` prefix. Only properties with a
value are set.

| Group | Properties |
|-------|------------|
| TMDb | [TMDb Properties](../service/online.md#tmdb-properties) |
| Ratings | [Ratings](../service/online.md#ratings) |
| Rotten Tomatoes status | [Rotten Tomatoes Status](../service/online.md#rotten-tomatoes-status) |
| Awards | [Awards](../service/online.md#awards) |
| Common Sense Media | [Common Sense Media](../service/online.md#common-sense-media) |
| Trakt | [Trakt](../service/online.md#trakt) |
| MDBList | [MDBList](../service/online.md#mdblist) |

Plugin only:

| Property | Description |
|----------|-------------|
| `dbid` | Library ID, when the item was requested by `dbid` |

`Episode.Rating.*` is not set on the plugin item.

### Example

```xml
<label>IMDb: $INFO[Container(9001).ListItem.Property(Rating.imdb)]</label>
<label>RT: $INFO[Container(9001).ListItem.Property(Rating.tomatoes.Percent)]%</label>
```

---

## Music Video Properties

```xml
<control type="list" id="9002">
    <content>plugin://script.skin.info.service/?action=online&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=musicvideo</content>
</control>
```

### Artist

| Property            | Description                        |
|---------------------|------------------------------------|
| `Artist.Bio`        | Artist biography                   |
| `Artist.FanArt`     | Artist fanart URL (first image)    |
| `Artist.FanArt.Count` | Total fanart images available    |
| `Artist.Thumb`      | Artist thumbnail                   |
| `Artist.Clearlogo`  | Artist clearlogo                   |
| `Artist.Banner`     | Artist banner                      |

### Track

Populated when the music video has a title and artist.

| Property            | Description                          |
|---------------------|--------------------------------------|
| `Track.Wiki`        | Track description / wiki             |
| `Track.Tags`        | Top tags (" / " separated, up to 10) |
| `Track.Listeners`   | Last.fm listener count               |
| `Track.Playcount`   | Last.fm global play count            |

### Album

Populated when the music video has an album and artist.

| Property            | Description                          |
|---------------------|--------------------------------------|
| `Album.Wiki`        | Album description / wiki             |
| `Album.Tags`        | Top tags (" / " separated, up to 10) |
| `Album.Label`       | Record label                         |

---

[↑ Top](#online-data) · [Index](../index.md)
