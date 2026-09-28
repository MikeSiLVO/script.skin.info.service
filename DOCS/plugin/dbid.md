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
- [Music Video Nodes](#music-video-nodes)
- [TMDB Details](#tmdb-details)

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

### Differences from Library Properties

Each media type below carries the properties of its section in
[Library Properties](../service/library.md), without the `SkinInfo.<Type>.` prefix, read as
`ListItem.Property(<name>)`. These differ:

| Library Properties | Plugin ListItem |
|--------------------|-----------------|
| `Art(<type>)` | `ListItem.Art(<type>)` |
| `Rating.{source}`, `Rating.{source}.Votes` | `ListItem.Rating(<source>)` and `ListItem.Votes(<source>)`, under Kodi's source names (`imdb`, `themoviedb`, `tomatometerallcritics`, `tomatometerallaudience`, ...) |
| `Rating.{source}.Percent`, `Rating.{source}.Stars` | Same property names |
| `SkinInfo.ListItem.*` | Not set |
| Not set | `DBID`, the item's database ID |

Video items also fill Kodi's own labels, such as `ListItem.Title`, `ListItem.Year` and
`ListItem.Plot`.

---

## Movies

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=movie</content>
```

The ListItem carries the same properties as [Movies](../service/library.md#movies), without the `SkinInfo.Movie.` prefix.

Not set here: `SkinInfo.Movie.Extras.*`.

---

## TV Shows

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=tvshow</content>
```

The ListItem carries the same properties as [TV Shows](../service/library.md#tv-shows), without the `SkinInfo.TVShow.` prefix.

---

## Seasons

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=season</content>
```

The ListItem carries the same properties as [Seasons](../service/library.md#seasons), without the `SkinInfo.Season.` prefix.

---

## Episodes

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=episode</content>
```

The ListItem carries the same properties as [Episodes](../service/library.md#episodes), without the `SkinInfo.Episode.` prefix.

---

## Movie Sets

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=set</content>
```

The ListItem carries the same properties as [Movie Sets](../service/library.md#movie-sets), without the `SkinInfo.Set.` prefix.

Per-movie artwork is a property named `Movie.%d.Art.<type>`, in place of `Movie.%d.Art(<type>)`.

---

## Artists

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=artist</content>
```

The ListItem carries the same properties as [Artists](../service/library.md#artists), without the `SkinInfo.Artist.` prefix.

Per-album artwork is a property named `Album.%d.Art.thumb` and `Album.%d.Art.discart`, in place of
`Album.%d.Art(thumb)` and `Album.%d.Art(discart)`.

---

## Albums

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=album</content>
```

The ListItem carries the same properties as [Albums](../service/library.md#albums), without the `SkinInfo.Album.` prefix.

---

## Music Videos

```xml
<content>plugin://script.skin.info.service/
  ?dbid=$INFO[ListItem.DBID]
  &amp;dbtype=musicvideo</content>
```

The ListItem carries the same properties as [Music Videos](../service/library.md#music-videos), without the `SkinInfo.MusicVideo.` prefix.

---

## Music Video Nodes

For music video artist and album navigation nodes (which have `DBType=actor` and `DBType=album` instead of `musicvideo`), use the name-based path:

```xml
<value condition="!String.IsEmpty(ListItem.Property(musicvideomediatype))">
  plugin://script.skin.info.service/?action=getdetails
  &amp;dbtype=musicvideo_$INFO[ListItem.Property(musicvideomediatype)]
  &amp;artist=$INFO[ListItem.Label]
  &amp;album=$INFO[ListItem.Album]
</value>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `action`  | Yes      | Must be `getdetails` |
| `dbtype`  | Yes      | `musicvideo_artist` or `musicvideo_album` |
| `artist`  | *        | Artist name (required for `musicvideo_artist`) |
| `album`   | *        | Album name (required for `musicvideo_album`) |

### Node Properties

| Property           | Condition                             |
|--------------------|---------------------------------------|
| `Artist.Fanart`    | Artist found in music library         |
| `Artist.Thumb`     | Artist found in music library         |
| `Artist.Clearlogo` | Artist found in music library         |
| `Artist.Banner`    | Artist found in music library         |
| `Album.Thumb`      | `musicvideo_album` only, matched by title |

---

## TMDB Details

Everything above keys off a library DBID. For something that is not in the library, ask by TMDB ID
instead and get the same single-item listing back.

```xml
<content>plugin://script.skin.info.service/?action=tmdb_details&amp;type=movie&amp;tmdb_id=$INFO[ListItem.Property(tmdb_id)]</content>
```

### Parameters

| Parameter | Required | Values                  | Description                    |
|-----------|----------|-------------------------|--------------------------------|
| `type`    | No       | `movie`, `tv`, `person` | Defaults to `movie`            |
| `tmdb_id` | Yes      | Number                  | The item's TMDB ID             |

This is the path [TMDB Search](../skin-utilities.md#tmdb-search) hands back after the user picks a
result, so binding a container to that property and building the URL yourself reach the same
listing.

Discovery widgets set `tmdb_id` on every item, so this pairs directly with them:

```xml
<content>plugin://script.skin.info.service/?action=tmdb_details&amp;type=tv&amp;tmdb_id=$INFO[Container(9000).ListItem.Property(tmdb_id)]</content>
```

### What comes back

One item, with the info tag filled in as far as TMDB has data:

| Filled                | Notes                                          |
|-----------------------|------------------------------------------------|
| Title, original title |                                                |
| Plot, tagline         |                                                |
| Year, premiered       | First air date for `tv`                        |
| Duration              | `movie` only                                   |
| Rating, votes         |                                                |
| Genres, studios, countries |                                           |
| Certification         | US rating                                      |
| Cast                  | First 20, with character and thumb             |
| Directors, writers    |                                                |
| IMDb number           |                                                |
| Trailer               | YouTube add-on path, when a trailer exists     |
| Tags                  | TMDB keywords                                  |
| Poster, fanart, clearlogo | Clearlogo in the online metadata language, else English, else one with no language set |

`tmdb_id` is also set as an item property.

With `type=person` the item is the person instead, carrying the same properties as
[Person Info](person.md).

---

[↑ Top](#dbid-queries) · [Index](../index.md)
