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
- [Saving to NFO Files](#saving-to-nfo-files)
  - [NFO Settings](#nfo-settings)
  - [Limitations](#limitations)

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

Settings → Advanced → Context Menu Items

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

## Saving to NFO Files

Edits are saved to Kodi's library straight away. They can optionally also be written to the item's local NFO file, so your changes survive a library refresh or rescrape that would otherwise overwrite them from the scraper.

This is **not** a replacement for Kodi's own library export. It writes only the fields the editor manages, in the same format Kodi uses, and leaves the rest of the file as it is.

### NFO Settings

In addon settings under **Advanced → NFO Files**:

| Setting | Description |
|---------|-------------|
| Write metadata changes to NFO files | Master switch. When on, saving an edit also writes it to the item's NFO. When off, nothing is written to NFO files. |
| Create an NFO file when none exists | When on, writes a new NFO if the item has none. When off, only existing NFO files are updated. |
| Include watched state in NFO files | When on, writes playcount and last-played date. When off, watched state is left out. |

A manual **Export to NFO** action is also available as a context menu item (enable it under **Advanced → Context Menu Items**). It writes the current item's NFO on demand, creating the file if needed, regardless of the settings above.

### Limitations

| Limitation | Detail |
|------------|--------|
| Single item only | Writes only the item you edit, or the one you run **Export to NFO** on. There is no bulk or library-wide write. |
| Not a full export | Persists editor changes only. For a complete backup, use Kodi's own library export. |
| Seasons are not written | Season edits are saved to the library but not to an NFO. Only movies, TV shows, episodes and music videos get NFO files. |
| Artwork is not written | Posters, fanart and other item artwork are left to Kodi, which rebuilds them on rescrape. Existing artwork entries in the file are preserved. |
| Some fields are skipped | A few fields Kodi does not expose to add-ons are left out (for example, TV show status) and kept as-is if already present. |

---

[↑ Top](#metadata-editor) · [Index](../index.md)
