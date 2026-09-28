# Path Statistics

Path wrapping and statistics for library paths.

[← Back to Index](../index.md)

---

## Table of Contents

- [Path Wrapper](#path-wrapper)
- [Path Statistics](#path-statistics)

---

## Path Wrapper

Wraps an XSP-filtered library path or smart playlist in a plugin URL, which reloads when its `refresh` value changes.

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

### Notes

- Works with `videodb://`, `musicdb://`, and `special://` paths
- XSP filters can include InfoLabels that resolve at runtime
- Use `refresh_counter` utility to increment refresh values

---

## Path Statistics

Calculates statistics for video library paths, including counts, watch status, and episode data.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=path_stats&amp;path=videodb://movies/titles/&amp;reload=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>

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
| `TVShowCount` | Number of TV shows, counting each show once for a path of episodes |
| `Episodes` | Total episodes across all shows |
| `WatchedEpisodes` | Watched episodes |
| `UnWatchedEpisodes` | Unwatched episodes |

### Supported Paths

- `videodb://movies/*` - Movie library paths
- `videodb://tvshows/*` - TV show library paths
- `special://profile/playlists/video/*` - Smart playlists
- `plugin://*` - Plugin paths
- Any path Kodi can list

### Examples

**Widget header with count:**

```xml
<content>plugin://script.skin.info.service/?action=path_stats&amp;path=videodb://movies/titles/?xsp={"type":"movies","rules":{"and":[{"field":"genre","operator":"is","value":"Action"}]}}&amp;reload=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>

<label>Action Movies ($INFO[Window(Home).Property(SkinInfo.PathStats.Count)])</label>
```

**TV show episode counts:**

```xml
<content>plugin://script.skin.info.service/?action=path_stats&amp;path=videodb://tvshows/titles/&amp;reload=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>

<label>$INFO[Window(Home).Property(SkinInfo.PathStats.WatchedEpisodes)] / $INFO[Window(Home).Property(SkinInfo.PathStats.Episodes)] Episodes</label>
```

**Conditional visibility:**

```xml
<control type="image">
    <texture>badges/new.png</texture>
    <visible>Integer.IsGreater(Window(Home).Property(SkinInfo.PathStats.Unwatched),0)</visible>
</control>

<control type="group">
    <visible>Integer.IsGreater(Window(Home).Property(SkinInfo.PathStats.Count),0)</visible>
</control>
```

### Auto-Refresh

Include `reload=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]` in the plugin URL. See [Library Refresh](../skin-utilities.md#library-refresh).

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
