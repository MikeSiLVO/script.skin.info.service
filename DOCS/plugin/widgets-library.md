# Library Widgets

Widget content sourced from the Kodi library. See also: [Discovery Widgets](widgets-discovery.md) for online content.

[← Back to Index](../index.md)

---

## Table of Contents

- [Next Up](#next-up)
- [Recent Episodes Grouped](#recent-episodes-grouped)
- [By Actor](#by-actor)
- [By Director](#by-director)
- [Similar Items](#similar-items)
- [Recommended For You](#recommended-for-you)
- [Seasonal](#seasonal)
- [Similar Artists](#similar-artists)
- [Artist Albums](#artist-albums)
- [Artist Music Videos](#artist-music-videos)
- [Genre Artists](#genre-artists)

---

## Next Up

Returns the next unwatched episode for each in-progress TV show.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=next_up</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `limit` | No | 25 | Maximum shows to process |

### Examples

```xml
<!-- Basic -->
<content>plugin://script.skin.info.service/?action=next_up</content>

<!-- Custom limit -->
<content>plugin://script.skin.info.service/?action=next_up&amp;limit=10</content>

<!-- With auto-refresh -->
<content>plugin://script.skin.info.service/?action=next_up&amp;refresh=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>
```

### Behavior

1. Queries in-progress TV shows (sorted by last played)
2. For each show, finds the last played episode
3. Returns the next unwatched episode in same season
4. If season complete, returns first unwatched overall

### Item Properties

- **Label**: Formatted as `2x05. Episode Title`
- **MediaType**: `episode`
- **Video Info**: title, season, episode, showtitle, plot, rating, runtime, firstaired
- **Artwork**: TV show artwork + episode thumb
- **Resume Point**: If partially watched

**Widget Type:** Episode

---

## Recent Episodes Grouped

Recently added episodes with intelligent grouping.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=recent_episodes_grouped</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `limit` | No | 25 | Maximum shows to process |
| `include_watched` | No | false | Include shows with all episodes watched |

### Examples

```xml
<!-- Unwatched only -->
<content>plugin://script.skin.info.service/?action=recent_episodes_grouped&amp;limit=25</content>

<!-- Include watched -->
<content>plugin://script.skin.info.service/?action=recent_episodes_grouped&amp;include_watched=true</content>
```

### Behavior

1. Queries recently added TV shows
2. For each show:
   - **1 unwatched episode**: Returns episode item with show artwork
   - **Multiple unwatched**: Returns show folder
   - **include_watched=true**: Checks if multiple added same day

Returns **mixed** episode and TV show items.

**Widget Type:** Mixed

---

## By Actor

Items featuring a random actor from the source item's cast.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=by_actor&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbid` | Yes | - | Database ID of source item |
| `dbtype` | No | movie | Source type (movie/tvshow/episode) |
| `limit` | No | 25 | Maximum items |
| `cast_limit` | No | 4 | Pick from top N cast (0=all) |
| `mix` | No | true | Mixed movie/show results |
| `lock` | No | false | Lock to same actor across widgets |

### Examples

```xml
<!-- Mixed results -->
<content>plugin://script.skin.info.service/?action=by_actor&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>

<!-- Movies only -->
<content>plugin://script.skin.info.service/?action=by_actor&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]&amp;mix=false</content>

<!-- Lock same actor across two widgets -->
<content>plugin://script.skin.info.service/?action=by_actor&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=movie&amp;mix=false&amp;lock=true</content>
<content>plugin://script.skin.info.service/?action=by_actor&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=tvshow&amp;mix=false&amp;lock=true</content>
```

### Actor Locking

With `lock=true`:

- First call picks and stores random actor
- Subsequent calls reuse stored actor
- Resets when navigating to different item

**Widget Type:**

- **mix=true**: Mixed widget
- **mix=false**: Movie or TV Show widget

### Per-Item Properties

Each result ListItem has the standard movie/tvshow infotag fields plus:

| Property | Description                                                |
|----------|------------------------------------------------------------|
| `Actor`  | Name of the picked actor (same value on every result)      |
| `Role`   | Character the actor plays in this item                     |

Use `$INFO[ListItem.Property(Role)]` to display the character. Note that
`ListItem.Label2` is not reliable for results from this widget — Kodi
overrides it from the VideoInfoTag for video items. The `Role` property
is the canonical way to get the character name.

---

## By Director

Items by a random director from the source item.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=by_director&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbid` | Yes | - | Database ID |
| `dbtype` | No | movie | Source type (movie/episode) |
| `limit` | No | 25 | Maximum items |
| `director_limit` | No | 3 | Pick from top N directors (0=all) |
| `mix` | No | true | Mixed movie/episode results |

### Examples

```xml
<!-- Mixed results -->
<content>plugin://script.skin.info.service/?action=by_director&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>

<!-- Movies only -->
<content>plugin://script.skin.info.service/?action=by_director&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]&amp;mix=false</content>
```

**Widget Type:**

- **mix=true**: Mixed widget (movie + episode)
- **mix=false**: Movie or Episode widget

---

## Similar Items

Items similar to source based on genre matching with year/MPAA scoring.

### Usage

```xml
<!-- Library item as seed -->
<content>plugin://script.skin.info.service/?action=similar&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>

<!-- TMDB-only item as seed (no library entry) -->
<content>plugin://script.skin.info.service/?action=similar&amp;tmdb_id=$INFO[ListItem.Property(tmdb_id)]&amp;dbtype=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbid` | Conditional | - | Library ID. Provide this OR `tmdb_id`. Library seed gives the richest scoring (year + MPAA proximity). |
| `tmdb_id` | Conditional | - | TMDB ID. Used when no library entry exists. Genres pulled from TMDB; MPAA proximity scoring skipped. |
| `dbtype` | No | movie | Source type (`movie`, `tvshow`, `episode`) |
| `limit` | No | 25 | Maximum items |

Results are always **library items** — `tmdb_id` only changes how the seed's genres are obtained.

### Scoring

- **Genre overlap**: +10 points per matching genre
- **Year proximity**: +3 (≤5 years), +2 (≤10 years), +1 (≤20 years)
- **MPAA match**: +2 points

### Example

Source: "The Dark Knight" (Action, Crime, Drama | 2008 | PG-13)

- "Heat" (Action, Crime, Drama | 1995 | R) = 31 points
- "Inception" (Action, Sci-Fi | 2010 | PG-13) = 15 points

**Widget Type:**

- **Source movie/set**: Movie widget
- **Source tvshow/episode**: TV Show widget

---

## Recommended For You

Personalized recommendations from your watch history.

By default this is single-seed: it picks titles most like your single most recent watch, matching on genre, MPAA tone, shared director, shared cast, and release era. Every item is tagged with that seed, so the widget can show a "Recommended based on <title>" header. Add `multi=true` for a blend across several recent watches instead, weighted toward the most recent.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | No | movie | Content type (movie/tvshow/both) |
| `limit` | No | 25 | Maximum items |
| `multi` | No | false | Blend across recent history instead of a single seed |
| `strict_rating` | No | false | Only match the seed's MPAA tone |
| `min_rating` | No | 6.0 | Minimum rating threshold |
| `recency` | No | 0.75 | Multi only: 0-1, how strongly recent watches dominate |
| `history_size` | No | 10 | Multi only: number of recent watches blended |

### Item properties

| Property | Description |
|----------|-------------|
| `ListItem.Property(BasedOn)` | Seed title a pick came from (single: the one seed; multi: that pick's own seed watch) |
| `ListItem.Property(BasedOnLabel)` | Ready-made header label: "Recommended based on <title>" (single) or "Recommended based on recent watches" (multi) |

### Examples

```xml
<!-- Single-seed (default): more like your last watch -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie</content>

<!-- Blend across recent history -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie&amp;multi=true</content>

<!-- TV shows -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=tvshow</content>

<!-- Mixed -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=both</content>

<!-- Family mode -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie&amp;strict_rating=true&amp;min_rating=7.0</content>
```

### Notes

- Requires watch history; only returns unwatched items.
- Single-seed fills to `limit` with same-tone titles when there are few genuine matches, so the widget isn't sparse.
- `dbtype=both` mixes movies and TV shows in one widget.

---

## Seasonal

Seasonal movie collections filtered by TMDB tags.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=christmas</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `season` | Yes | - | Season identifier |
| `limit` | No | 50 | Maximum items |
| `sort` | No | random | Sort method |

### Available Seasons

| Season ID | Description |
|-----------|-------------|
| `christmas` | Christmas movies |
| `halloween` | Halloween movies, mixed with horror for variety |
| `valentines` | Valentine's Day / romance movies |
| `thanksgiving` | Thanksgiving movies |
| `newyear` | New Year's movies |
| `easter` | Easter movies |
| `independence` | Independence Day movies |
| `starwars` | Star Wars franchise |
| `startrek` | Star Trek franchise |

### Sort Methods

`random`, `title`, `year`, `rating`, `dateadded`

### Examples

```xml
<!-- Christmas random -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=christmas</content>

<!-- Halloween by rating -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=halloween&amp;sort=rating</content>

<!-- Star Wars marathon, chronological -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=starwars&amp;sort=year</content>
```

### Notes

- Holiday seasons (christmas, halloween, thanksgiving, newyear, easter, independence) need TMDB keyword tags imported in your scraper; without them they return empty
- `starwars`, `startrek` and `valentines` do not use tags, so they work regardless of scraper tag settings
- `halloween` mixes holiday titles with horror for variety

**Widget Type:** Movie

---

## Similar Artists

Library artists similar to a given artist, matched via Last.fm data.

### Usage

```xml
<content sortby="none">plugin://script.skin.info.service/?action=similar_artists&amp;artist=$INFO[ListItem.Artist]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `artist` | No* | - | Artist name |
| `dbid` | No* | - | Database ID of source item |
| `dbtype` | No* | - | Source type (musicvideo/artist/album/song) |
| `limit` | No | 25 | Maximum items |

*Either `artist` or `dbid`+`dbtype` required.

### Examples

```xml
<!-- From artist name -->
<content sortby="none">plugin://script.skin.info.service/?action=similar_artists&amp;artist=$INFO[ListItem.Artist]&amp;limit=10</content>

<!-- From musicvideo -->
<content sortby="none">plugin://script.skin.info.service/?action=similar_artists&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=musicvideo</content>
```

### Behavior

1. Resolves artist name from params
2. Reads similar artists from Last.fm cached data (fetches if not cached)
3. Matches similar names against AudioLibrary artists (case-insensitive)
4. Returns matching artists with library artwork

**Widget Type:** Artist

---

## Artist Albums

Albums by a given artist from AudioLibrary.

### Usage

```xml
<content sortby="none">plugin://script.skin.info.service/?action=artist_albums&amp;artist=$INFO[ListItem.Artist]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `artist` | No* | - | Artist name |
| `dbid` | No* | - | Database ID of source item |
| `dbtype` | No* | - | Source type (musicvideo/artist/album/song) |
| `limit` | No | 25 | Maximum items |
| `sort` | No | year | Sort method |

*Either `artist` or `dbid`+`dbtype` required.

### Examples

```xml
<!-- From artist name -->
<content sortby="none">plugin://script.skin.info.service/?action=artist_albums&amp;artist=$INFO[ListItem.Artist]</content>

<!-- From musicvideo, sorted by title -->
<content sortby="none">plugin://script.skin.info.service/?action=artist_albums&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=musicvideo&amp;sort=title</content>
```

### Behavior

1. Resolves artist name from params
2. Looks up `artistid` in AudioLibrary
3. Queries albums filtered by `artistid`
4. Returns album ListItems with cover art

**Widget Type:** Album

---

## Artist Music Videos

Music videos by a given artist from VideoLibrary.

### Usage

```xml
<content sortby="none">plugin://script.skin.info.service/?action=artist_musicvideos&amp;artist=$INFO[ListItem.Artist]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `artist` | No* | - | Artist name |
| `dbid` | No* | - | Database ID of source item |
| `dbtype` | No* | - | Source type (musicvideo/artist/album/song) |
| `limit` | No | 25 | Maximum items |

*Either `artist` or `dbid`+`dbtype` required.

When `dbid`+`dbtype=musicvideo` is provided, that musicvideo is excluded from results.

### Examples

```xml
<!-- Other musicvideos by this artist (exclude current) -->
<content sortby="none">plugin://script.skin.info.service/?action=artist_musicvideos&amp;artist=$INFO[ListItem.Artist]&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=musicvideo&amp;limit=10</content>

<!-- All musicvideos by artist name -->
<content sortby="none">plugin://script.skin.info.service/?action=artist_musicvideos&amp;artist=$INFO[ListItem.Artist]</content>
```

### Behavior

1. Resolves artist name from params
2. Queries VideoLibrary filtered by artist name (sorted by year descending)
3. Excludes source musicvideo if `dbid`+`dbtype=musicvideo` provided
4. Returns playable musicvideo ListItems

**Widget Type:** Music Video

---

## Genre Artists

Artists in the same genre as a given artist from AudioLibrary.

### Usage

```xml
<content sortby="none">plugin://script.skin.info.service/?action=genre_artists&amp;artist=$INFO[ListItem.Artist]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `artist` | No* | - | Artist name (to resolve genre) |
| `dbid` | No* | - | Database ID of source item |
| `dbtype` | No* | - | Source type (musicvideo/artist/album/song) |
| `genre` | No | - | Explicit genre (skips artist lookup) |
| `limit` | No | 25 | Maximum items |

*Either `artist`, `dbid`+`dbtype`, or `genre` required.

### Examples

```xml
<!-- From artist name -->
<content sortby="none">plugin://script.skin.info.service/?action=genre_artists&amp;artist=$INFO[ListItem.Artist]&amp;limit=10</content>

<!-- Explicit genre -->
<content sortby="none">plugin://script.skin.info.service/?action=genre_artists&amp;genre=Rock&amp;limit=10</content>
```

### Behavior

1. If no explicit genre: resolves artist name, looks up their genre from AudioLibrary
2. Queries AudioLibrary artists filtered by genre (random sort)
3. Excludes source artist
4. Returns artist ListItems with library artwork

**Widget Type:** Artist

---

[↑ Top](#library-widgets) · [Index](../index.md)
