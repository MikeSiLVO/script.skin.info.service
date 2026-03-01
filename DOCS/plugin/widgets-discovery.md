# Discovery Widgets

Online content from TMDB and Trakt APIs. See also: [Library Widgets](widgets-library.md) for Kodi library content.

[← Back to Index](../index.md)

---

## Table of Contents

**TMDB**
- [TMDB Trending](#tmdb-trending)
- [TMDB Popular](#tmdb-popular)
- [TMDB Top Rated](#tmdb-top-rated)
- [TMDB Now Playing](#tmdb-now-playing)
- [TMDB Upcoming](#tmdb-upcoming)
- [TMDB Airing Today](#tmdb-airing-today)
- [TMDB On The Air](#tmdb-on-the-air)

**Trakt**
- [Trakt Trending](#trakt-trending)
- [Trakt Popular](#trakt-popular)
- [Trakt Anticipated](#trakt-anticipated)
- [Trakt Most Watched](#trakt-most-watched)
- [Trakt Most Collected](#trakt-most-collected)
- [Trakt Box Office](#trakt-box-office)
- [Trakt Recommendations](#trakt-recommendations) (OAuth)

**Reference**
- [Common Parameters](#common-parameters)
- [Library Filter](#library-filter)
- [Browse Menus](#browse-menus)
- [Item Properties](#item-properties)

---

## Common Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` (ignored for single-type widgets) |
| `source` | No | `online` | `online` (all results) or `library` (library items only) |
| `limit` | No | `20` | Maximum items |
| `page` | No | `1` | Pagination |

---

## TMDB Trending

Items trending today or this week, ranked by views, votes, and interactions.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_trending&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |
| `window` | No | `week` | `day` or `week` |

### Examples

```xml
<!-- Trending movies this week -->
<content>plugin://script.skin.info.service/?action=tmdb_trending&amp;type=movie</content>

<!-- Trending TV shows today -->
<content>plugin://script.skin.info.service/?action=tmdb_trending&amp;type=tv&amp;window=day</content>
```

**Widget Type:** Movie or TV Show

---

## TMDB Popular

Most popular items on TMDB, based on daily page views and user engagement.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_popular&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=tmdb_popular&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=tmdb_popular&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## TMDB Top Rated

Highest rated items on TMDB by user votes.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_top_rated&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=tmdb_top_rated&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=tmdb_top_rated&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## TMDB Now Playing

Movies currently in theaters.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_now_playing</content>
```

### Notes

- Movie only. `type` parameter is ignored.

**Widget Type:** Movie

---

## TMDB Upcoming

Movies with upcoming release dates.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_upcoming</content>
```

### Notes

- Movie only. `type` parameter is ignored.

**Widget Type:** Movie

---

## TMDB Airing Today

TV show episodes airing today.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_airing_today</content>
```

### Notes

- TV only. `type` parameter is ignored.

**Widget Type:** TV Show

---

## TMDB On The Air

TV shows with episodes airing within the next 7 days.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_on_the_air</content>
```

### Notes

- TV only. `type` parameter is ignored.

**Widget Type:** TV Show

---

## Trakt Trending

Items being watched right now, ranked by concurrent viewers. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_trending&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=trakt_trending&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=trakt_trending&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## Trakt Popular

Most popular items on Trakt, based on overall user engagement. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_popular&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=trakt_popular&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=trakt_popular&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## Trakt Anticipated

Most anticipated upcoming releases, ranked by Trakt watchlist count. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_anticipated&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=trakt_anticipated&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=trakt_anticipated&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## Trakt Most Watched

Most watched items over a time period, ranked by unique viewers. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_watched&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |
| `period` | No | `weekly` | `daily`, `weekly`, `monthly`, or `all` |

### Examples

```xml
<!-- Most watched movies this week -->
<content>plugin://script.skin.info.service/?action=trakt_watched&amp;type=movie</content>

<!-- Most watched TV shows this month -->
<content>plugin://script.skin.info.service/?action=trakt_watched&amp;type=tv&amp;period=monthly</content>

<!-- Most watched movies of all time -->
<content>plugin://script.skin.info.service/?action=trakt_watched&amp;type=movie&amp;period=all</content>
```

**Widget Type:** Movie or TV Show

---

## Trakt Most Collected

Most collected items over a time period, ranked by Trakt collection count. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_collected&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |
| `period` | No | `weekly` | `daily`, `weekly`, `monthly`, or `all` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=trakt_collected&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=trakt_collected&amp;type=tv&amp;period=monthly</content>
```

**Widget Type:** Movie or TV Show

---

## Trakt Box Office

Current top box office movies ranked by revenue. Artwork fetched from TMDB.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_boxoffice</content>
```

### Notes

- Movie only. `type` parameter is ignored.
- `page` parameter not supported.

**Widget Type:** Movie

---

## Trakt Recommendations

Personalized recommendations based on the user's Trakt watch history and ratings. Artwork fetched from TMDB.

**Requires Trakt OAuth.** Returns empty list if no Trakt account is linked.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_recommendations&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

### Examples

```xml
<content>plugin://script.skin.info.service/?action=trakt_recommendations&amp;type=movie</content>
<content>plugin://script.skin.info.service/?action=trakt_recommendations&amp;type=tv</content>
```

**Widget Type:** Movie or TV Show

---

## Library Filter

Any discovery widget can be filtered to library-only items by adding `source=library`.

When an item matches a library entry:
- DBID is set on the video tag (enables library context menu)
- Movie items are playable (file URL set)
- TV show items link to their library folder
- `IsInLibrary` property is set to `true`

When `source=online` (default), all results are returned. Library matches are still enriched with DBID and file paths.

```xml
<!-- TMDB popular movies, only those in library -->
<content>plugin://script.skin.info.service/?action=tmdb_popular&amp;type=movie&amp;source=library</content>

<!-- Trakt trending TV shows, only in library -->
<content>plugin://script.skin.info.service/?action=trakt_trending&amp;type=tv&amp;source=library</content>
```

---

## Browse Menus

Folder-based menus for skin file manager integration:

```xml
<!-- Top-level menu (Movies / TV Shows) -->
<content>plugin://script.skin.info.service/?action=discover_menu</content>

<!-- All movie discovery widgets -->
<content>plugin://script.skin.info.service/?action=discover_movies_menu</content>

<!-- All TV show discovery widgets -->
<content>plugin://script.skin.info.service/?action=discover_tvshows_menu</content>
```

Also accessible from Widgets > Discover in the plugin root menu.

---

## Item Properties

All discovery ListItems include:

| Property | Description |
|----------|-------------|
| `tmdb_id` | TMDB ID |
| `IsInLibrary` | `true` if item exists in Kodi library |

### Video Tag

| Field | TMDB | Trakt |
|-------|------|-------|
| Title | Yes | Yes |
| OriginalTitle | Yes | Yes |
| Year | Yes | Yes |
| Plot | Yes | Yes |
| Rating | Yes | Yes |
| Votes | Yes | Yes |
| Genres | Yes | Yes |
| Premiered | Yes | Yes |
| MPAA | No | Yes |
| TagLine | No | Yes |
| Duration | No | Yes |
| IMDBNumber | No | Yes |
| MediaType | Yes | Yes |
| DbId | When in library | When in library |

### Art

| Art Type | Source |
|----------|--------|
| `poster` | TMDB |
| `fanart` | TMDB |

Trakt items get artwork via a TMDB lookup using the item's TMDB ID. Previously fetched items are served from cache.

---

[↑ Top](#discovery-widgets) · [Index](../index.md)
