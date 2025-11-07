# Metadata Editor

Edit library item metadata directly from your skin.

[← Back to Index](../index.md)

---

## Table of Contents

- [Usage](#usage)
  - [RunScript](#runscript)
  - [Context Menu](#context-menu)
- [Supported Media Types](#supported-media-types)
- [Editable Fields](#editable-fields)
  - [Movies](#movies)
  - [TV Shows](#tv-shows)
  - [Episodes](#episodes)
  - [Seasons](#seasons)
  - [Music Videos](#music-videos)
- [Field Types](#field-types)

## Usage

### RunScript

```xml
RunScript(script.skin.info.service,action=edit,dbid=$INFO[ListItem.DBID],dbtype=$INFO[ListItem.DBType])
```

**Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `dbid` | No | Database ID of the item. Falls back to `ListItem.DBID` if not provided |
| `dbtype` | No | Media type. Falls back to `ListItem.DBType` if not provided |

**Example - Button:**

```xml
<control type="button">
    <label>Edit Metadata</label>
    <onclick>RunScript(script.skin.info.service,action=edit,dbid=$INFO[ListItem.DBID],dbtype=$INFO[ListItem.DBType])</onclick>
</control>
```

### Context Menu

The addon provides a context menu item for editing metadata. Enable it in addon settings:

Settings → Context Menu → Show Edit Metadata

---

## Supported Media Types

| Type | dbtype value |
|------|--------------|
| Movies | `movie` |
| TV Shows | `tvshow` |
| Episodes | `episode` |
| Seasons | `season` |
| Music Videos | `musicvideo` |

---

## Editable Fields

### Movies

| Field | Type | Description |
|-------|------|-------------|
| Title | Text | Movie title |
| Plot | Long Text | Movie synopsis |
| Tagline | Text | Movie tagline |
| Sort Title | Text | Title used for sorting |
| Original Title | Text | Title in original language |
| Year | Integer | Release year (1888-2100) |
| Premiered | Date | Release date (YYYY-MM-DD) |
| Runtime | Integer | Duration in minutes |
| MPAA Rating | Text | Content rating (PG, R, etc.) |
| Top 250 | Integer | IMDb Top 250 position (0-250) |
| Genre | List | Genre tags |
| Studio | List | Production studios |
| Director | List | Directors |
| Writer | List | Writers |
| Country | List | Production countries |
| Tags | List | Custom tags |
| User Rating | Rating | Personal rating (0-10) |
| External Ratings | Ratings | IMDb, TMDB, etc. |

### TV Shows

| Field | Type | Description |
|-------|------|-------------|
| Title | Text | Show title |
| Plot | Long Text | Show synopsis |
| Sort Title | Text | Title used for sorting |
| Original Title | Text | Title in original language |
| Premiered | Date | First air date (YYYY-MM-DD) |
| Runtime | Integer | Episode duration in minutes |
| MPAA Rating | Text | Content rating |
| Status | Select | Returning Series, Ended, Cancelled, etc. |
| Genre | List | Genre tags |
| Studio | List | Networks/studios |
| Tags | List | Custom tags |
| User Rating | Rating | Personal rating (0-10) |
| External Ratings | Ratings | IMDb, TMDB, etc. |

### Episodes

| Field | Type | Description |
|-------|------|-------------|
| Title | Text | Episode title |
| Plot | Long Text | Episode synopsis |
| Original Title | Text | Title in original language |
| First Aired | Date | Air date (YYYY-MM-DD) |
| Runtime | Integer | Duration in minutes |
| Director | List | Directors |
| Writer | List | Writers |
| User Rating | Rating | Personal rating (0-10) |
| External Ratings | Ratings | IMDb, TMDB, etc. |

### Seasons

| Field | Type | Description |
|-------|------|-------------|
| Title | Text | Season title |
| User Rating | Rating | Personal rating (0-10) |

### Music Videos

| Field | Type | Description |
|-------|------|-------------|
| Title | Text | Video title |
| Plot | Long Text | Video description |
| Year | Integer | Release year |
| Premiered | Date | Release date (YYYY-MM-DD) |
| Runtime | Integer | Duration in minutes |
| Genre | List | Genre tags |
| Studio | List | Studios/labels |
| Director | List | Directors |
| Tags | List | Custom tags |
| User Rating | Rating | Personal rating (0-10) |

---

## Field Types

| Type | Input Method |
|------|--------------|
| Text | Keyboard input |
| Long Text | Multi-line keyboard input |
| Integer | Numeric keyboard |
| Date | Date picker (YYYY-MM-DD format) |
| List | Add/remove/reorder items |
| Rating | Select 0-10 |
| Ratings | Edit individual rating sources |
| Select | Choose from predefined options |

---

[↑ Top](#metadata-editor) · [Index](../index.md)
