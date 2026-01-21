# Path Statistics

Path wrapping and statistics for library paths.

[← Back to Index](../index.md)

---

## Table of Contents

- [Path Wrapper](#path-wrapper)
- [Path Statistics](#path-statistics)

---

## Path Wrapper

Wraps XSP-filtered library paths in a plugin URL to enable dynamic refresh support.

### Use Cases

**Use for:**

- XSP inline filters with InfoLabels
- Smart playlists (.xsp files)
- Dynamically filtered library views

**Do not use for:**

- Full library browsing (`videodb://movies/titles/`)
- Static directory browsing
- Paths that don't need refresh support

### Usage

```xml
<content>plugin://script.skin.info.service/?action=wrap&amp;path={encoded_path}&amp;refresh={counter}</content>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `path` | Yes | The library path to wrap (can use InfoLabels) |
| `refresh` | No | Counter/value that triggers reload when changed |

### Examples

**XSP inline filter with InfoLabels:**

```xml
<onclick>SetProperty(genre_filter,Action,home)</onclick>

<content>plugin://script.skin.info.service/?action=wrap&amp;path=videodb://movies/titles/?xsp={"rules":{"and":[{"field":"genre","operator":"contains","value":["$INFO[Window(Home).Property(genre_filter)]"]}]},"type":"movies"}&amp;refresh=$INFO[Window(Home).Property(SkinInfo.FilterRefresh)]</content>

<onclick>SetProperty(genre_filter,Comedy,home)</onclick>
<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=FilterRefresh)</onclick>
```

**Smart playlist file:**

```xml
<content>plugin://script.skin.info.service/?action=wrap&amp;path=special://profile/playlists/video/unwatched.xsp&amp;refresh=$INFO[Window(Home).Property(SkinInfo.PlaylistRefresh)]</content>

<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=PlaylistRefresh)</onclick>
```

### How It Works

1. Plugin receives the wrapped path
2. Uses `Files.GetDirectory` JSON-RPC to fetch contents
3. Returns items as plugin content
4. When `refresh` parameter changes, Kodi detects URL change and reloads

### Notes

- Works with `videodb://`, `musicdb://`, and `special://` paths
- XSP filters can include InfoLabels that resolve at runtime
- Use `refresh_counter` utility to increment refresh values

---

## Path Statistics

Calculates statistics for video library paths, including counts, watch status, and episode data.

### Use Cases

- Widget headers showing counts (e.g., "Unwatched Movies (42)")
- Progress indicators for playlists
- Collection statistics (TV show episode counts)
- Filter result previews

### Usage

```xml
<onclick>RunPlugin(plugin://script.skin.info.service/?action=path_stats&amp;path=$INFO[Window(Home).Property(widget.path)])</onclick>

<label>Total: $INFO[Window(Home).Property(SkinInfo.PathStats.Count)]</label>
<label>Watched: $INFO[Window(Home).Property(SkinInfo.PathStats.Watched)]</label>
<label>Unwatched: $INFO[Window(Home).Property(SkinInfo.PathStats.Unwatched)]</label>
```

### Available Properties

All properties via `Window(Home).Property(SkinInfo.PathStats.*)`

**Common Properties:**

| Property | Description |
|----------|-------------|
| `Count` | Total number of items |
| `Watched` | Items with playcount > 0 |
| `Unwatched` | Items never watched |
| `InProgress` | Items with resume position > 0 |

**TV Show Properties:**

| Property | Description |
|----------|-------------|
| `TVShowCount` | Number of TV shows |
| `Episodes` | Total episodes across all shows |
| `WatchedEpisodes` | Watched episodes |
| `UnWatchedEpisodes` | Unwatched episodes |

### Supported Paths

- `videodb://movies/*` - Movie library paths
- `videodb://tvshows/*` - TV show library paths
- `special://profile/playlists/video/*` - Smart playlists
- `plugin://*` - Plugin paths
- Any path supported by `Files.GetDirectory`

### Examples

**Widget header with count:**

```xml
<onclick>SetProperty(widget.path,videodb://movies/titles/?xsp={"type":"movies","rules":{"and":[{"field":"genre","operator":"is","value":"Action"}]}},home)</onclick>
<onclick>RunPlugin(plugin://script.skin.info.service/?action=path_stats&amp;path=$INFO[Window(Home).Property(widget.path)])</onclick>

<label>Action Movies ($INFO[Window(Home).Property(SkinInfo.PathStats.Count)])</label>
```

**TV show progress bar:**

```xml
<onclick>RunPlugin(plugin://script.skin.info.service/?action=path_stats&amp;path=videodb://tvshows/titles/)</onclick>

<control type="progress">
    <info>$NUMBER[$INFO[Window(Home).Property(SkinInfo.PathStats.WatchedEpisodes)]]</info>
</control>

<label>$INFO[Window(Home).Property(SkinInfo.PathStats.WatchedEpisodes)] / $INFO[Window(Home).Property(SkinInfo.PathStats.Episodes)] Episodes</label>
```

**Conditional visibility:**

```xml
<control type="image" id="new_badge">
    <texture>badges/new.png</texture>
    <visible>Integer.IsGreater(Window(Home).Property(SkinInfo.PathStats.Unwatched),0)</visible>
</control>

<control type="group" id="widget_container">
    <visible>Integer.IsGreater(Window(Home).Property(SkinInfo.PathStats.Count),0)</visible>
</control>
```

### Auto-Refresh

The service monitors library updates and recalculates statistics when:

- Items are added/removed
- Playback status changes
- Resume points are updated

**Global refresh property:**

- `Window(Home).Property(SkinInfo.Library.Refreshed)` - Auto-increments on library updates

```xml
<!-- Include reload parameter in the URL to trigger refresh when property changes -->
<content>plugin://script.skin.info.service/?action=wrap&amp;path=$INFO[Window(Home).Property(widget.path)]&amp;reload=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>
```

### Categorization Logic

**Movies and Episodes:**

- **Watched**: playcount > 0
- **In Progress**: playcount == 0 AND resume.position > 0
- **Unwatched**: playcount == 0 AND resume.position == 0

**TV Shows:**

- **Watched**: watchedepisodes >= total episodes
- **In Progress**: 0 < watchedepisodes < total episodes
- **Unwatched**: watchedepisodes == 0

---

[↑ Top](#path-statistics) · [Index](../index.md)
