# Cast Lists

Cast containers for movies, TV shows, seasons, movie sets, and episodes.

[← Back to Index](../index.md)

---

## Table of Contents

- [Get Cast](#get-cast)
- [Get Cast Player](#get-cast-player)

---

## Get Cast

Returns deduplicated cast list for movies, TV shows, seasons, movie sets, or episodes.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `dbid` | Conditional | Library ID of the item. Required when `online=false`. Omit for non-library (add-on) items. |
| `tmdb_id` | Conditional | TMDB ID. With `online=true`, used directly and takes precedence over `dbid`/`imdb_id`. |
| `imdb_id` | Conditional | IMDb ID (`tt…`). With `online=true`, resolved to a TMDB ID when `tmdb_id` is absent. |
| `dbtype` | Yes | Media type: `movie`, `tvshow`, `season`, `set`, `episode` |
| `season` | Conditional | Season number. Needed for `episode`/`season` in `online` mode when there is no `dbid`. |
| `episode` | Conditional | Episode number. Needed for `episode` in `online` mode when there is no `dbid`. |
| `online` | No | Use fresh TMDB data instead of the Kodi database (`true` to enable). Required when identifying by `tmdb_id`/`imdb_id` instead of `dbid`. |

For `online=true`, provide at least one of `tmdb_id`, `imdb_id`, or `dbid`. For an online `episode` (or `season`) without a `dbid`, the show's `tmdb_id`/`imdb_id` plus `season`/`episode` are required.

### Supported Types

**Individual Items:**

- `movie` - Cast for a single movie
- `tvshow` - Cast for a TV show
- `episode` - Cast for a single episode

**Aggregate Items:**

- `set` - Deduplicated cast from all movies in a set
- `season` - Deduplicated cast from all episodes in a season

### Item Properties

| Property | Description |
|----------|-------------|
| `ListItem.Label` | Actor name |
| `ListItem.Label2` | Character name/role |
| `ListItem.Art(icon)` | Actor thumbnail URL |
| `ListItem.Art(thumb)` | Actor thumbnail URL |
| `ListItem.Property(source_id)` | Source item database ID |
| `ListItem.Property(person_id)` | TMDB person ID (only with `online=true`) |

### Examples

**Movie cast:**

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=movie</content>
```

**TV show cast:**

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=tvshow</content>
```

**Movie set cast (aggregated):**

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=set</content>
```

**Season cast (aggregated):**

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=season</content>
```

**Episode cast (online mode):**

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=episode&amp;online=true</content>
```

**Non-library items (add-on items with no library ID):**

Items from video add-ons have no `dbid` but carry TMDB/IMDb ids. Route them to online mode when `ListItem.DBID` is empty, passing the ids from the item:

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;online=true&amp;dbtype=$INFO[ListItem.DBType]&amp;tmdb_id=$INFO[ListItem.UniqueID(tmdb)]&amp;imdb_id=$INFO[ListItem.IMDBNumber]</content>
```

For episodes, also pass the season and episode numbers (the ids are the show's):

```xml
<content>plugin://script.skin.info.service/?action=get_cast&amp;online=true&amp;dbtype=episode&amp;tmdb_id=$INFO[ListItem.UniqueID(tmdb)]&amp;imdb_id=$INFO[ListItem.IMDBNumber]&amp;season=$INFO[ListItem.Season]&amp;episode=$INFO[ListItem.Episode]</content>
```

Pass both `tmdb_id` and `imdb_id` when available; `tmdb_id` is used directly and `imdb_id` is the fallback. A skin can pick library vs online with a `String.IsEmpty(ListItem.DBID)` condition.

### Online Mode

When `online=true` is used, cast is fetched directly from TMDB:

**Episodes:**

- Default: Combined season cast + episode guests (matches Kodi scraper)
- Online: Episode cast + episode guests (accurate TMDB data)

**Seasons:**

- Default: Cast from Kodi database
- Online: Aggregate credits + all unique guest stars

Online mode also sets `person_id` property for direct person_info integration.

### Aggregate Behavior

For `set` and `season` types:

1. Retrieves all items in collection
2. Aggregates cast from all items
3. Deduplicates by actor name (preserves first appearance order)
4. Tracks source item ID (movieid/episodeid) for each actor
5. Returns up to 2000 unique cast members

---

## Get Cast Player

Returns cast for the currently playing library item.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=get_cast_player</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `aggregate` | No | `false` | For episodes: `true` to get entire show cast |

### Supported Content Types

- `movie` - Cast for playing movie
- `episode` - Cast for playing episode (or entire show with `aggregate=true`)

### Examples

**Current episode cast:**

```xml
<control type="list">
    <visible>Player.HasVideo</visible>
    <content>plugin://script.skin.info.service/?action=get_cast_player</content>
</control>
```

**Entire show cast:**

```xml
<control type="list">
    <visible>Player.HasVideo + VideoPlayer.Content(episodes)</visible>
    <content>plugin://script.skin.info.service/?action=get_cast_player&amp;aggregate=true</content>
</control>
```

**Movie cast (fullscreen OSD):**

```xml
<control type="panel">
    <visible>Player.HasVideo + VideoPlayer.Content(movies)</visible>
    <content>plugin://script.skin.info.service/?action=get_cast_player</content>
</control>
```

### Notes

- Only works when video is playing
- Returns empty if no video playing or video is not from library
- For episodes, `aggregate=true` aggregates cast from all episodes in the show
- Not cached - updates when playback changes

---

[↑ Top](#cast-lists) · [Index](../index.md)
