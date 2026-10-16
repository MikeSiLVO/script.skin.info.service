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
- [TMDB Recommendations](#tmdb-recommendations)
- [TMDB Discover](#tmdb-discover)
- [TMDB Posters](#tmdb-posters)

**Trakt**
- [Trakt Trending](#trakt-trending)
- [Trakt Popular](#trakt-popular)
- [Trakt Anticipated](#trakt-anticipated)
- [Trakt Most Watched](#trakt-most-watched)
- [Trakt Most Collected](#trakt-most-collected)
- [Trakt Box Office](#trakt-box-office)
- [Trakt Recommendations](#trakt-recommendations) (OAuth)
- [Trakt Most Played](#trakt-most-played)
- [Trakt Watchlist](#trakt-watchlist) (OAuth)
- [Trakt History](#trakt-history) (OAuth)
- [Trakt In Progress](#trakt-in-progress) (OAuth)
- [Trakt Lists](#trakt-lists)
- [Trakt List Items](#trakt-list-items)

**Reference**
- [Common Parameters](#common-parameters)
- [Library Filter](#library-filter)
- [Browse Menus](#browse-menus)
- [Plugin Category](#plugin-category)
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

## TMDB Recommendations

"You might also like" items derived from a specific movie or TV show. Unlike the global discovery widgets, this requires a seed item.

### Usage

```xml
<!-- Seeded by a library item -->
<content>plugin://script.skin.info.service/?action=tmdb_recommendations&amp;dbtype=movie&amp;dbid=$INFO[ListItem.DBID]</content>

<!-- Seeded by a TMDB-only item -->
<content>plugin://script.skin.info.service/?action=tmdb_recommendations&amp;dbtype=movie&amp;tmdb_id=$INFO[ListItem.Property(tmdb_id)]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | Yes | - | `movie` or `tvshow` |
| `tmdb_id` | Conditional | - | TMDB ID of the seed item. Provide this OR `dbid`. |
| `dbid` | Conditional | - | Library ID of the seed item. |
| `limit` | No | 25 | Maximum items |
| `source` | No | `online` | `online` returns all; `library` filters to items in your library |

### Notes

- Each item gets `IsInLibrary=true` set when it matches an item in the Kodi library.
- Item properties match the other TMDB widgets, see [Item Properties](#item-properties).

**Widget Type:** Movie or TV Show

---

## TMDB Discover

Titles that share a trait with a seed item, or the whole TMDB catalogue in one order.

### Usage

```xml
<!-- More from the focused movie's studio -->
<content>plugin://script.skin.info.service/?action=tmdb_discover&amp;dbtype=movie&amp;dbid=$INFO[ListItem.DBID]&amp;by=studio</content>

<!-- Same, for a TMDB-only item -->
<content>plugin://script.skin.info.service/?action=tmdb_discover&amp;dbtype=movie&amp;tmdb_id=$INFO[ListItem.Property(tmdb_id)]&amp;by=studio</content>

<!-- Most voted movies of all time -->
<content>plugin://script.skin.info.service/?action=tmdb_discover&amp;dbtype=movie&amp;sort=votes</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | No | `movie` | `movie` or `tvshow` |
| `tmdb_id` | Conditional | - | TMDB ID of the seed item. Provide this OR `dbid` when `by` is set. |
| `dbid` | Conditional | - | Library ID of the seed item. |
| `by` | No | - | What the titles share with the seed, see below. Without it, the list is the whole catalogue in `sort` order. |
| `sort` | No | `popularity` | `popularity`, `votes` (most voted) or `revenue` (movies only) |
| `limit` | No | `20` | Maximum items |
| `page` | No | `1` | Pagination |
| `source` | No | `online` | `online` returns all; `library` filters to items in your library |

| `by` | Lists | Types |
|------|-------|-------|
| `studio` | Titles from the seed's first production company | Movie, TV show |
| `network` | Shows from the seed's first network | TV show |
| `genre` | Titles in the seed's first genre | Movie, TV show |
| `year` | Titles from the seed's release or first-air year | Movie, TV show |
| `cast` | Movies with any of the seed's first three cast members | Movie |
| `director` | Movies the seed's director directed, most popular first | Movie |
| `collection` | The other parts of the seed's collection, in release order | Movie |

### Notes

- The seed item itself is left out.
- A seed with nothing for its `by`, such as a movie in no collection, gives an empty list.
- Each item gets `IsInLibrary=true` set when it matches an item in the Kodi library.
- Item properties match the other TMDB widgets, see [Item Properties](#item-properties).

**Widget Type:** Movie or TV Show

---

## TMDB Posters

A movie's or TV show's posters from TMDB. Posters in the online metadata language come first, then
English, then text-free ones; posters in other languages are not listed.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=tmdb_posters&amp;dbtype=movie&amp;dbid=$INFO[ListItem.DBID]</content>
```

Clicking a poster can open it full screen in the [Image Viewer](../dialogs/image-viewer.md):

```xml
<onclick>RunScript(script.skin.info.service,action=dialog_image_viewer,images_path=$INFO[ListItem.Property(images_path)],selected_index=$INFO[ListItem.CurrentItem])</onclick>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | Yes | - | `movie` or `tvshow` |
| `tmdb_id` | Conditional | - | TMDB ID of the item. Provide this OR `dbid`. |
| `dbid` | Conditional | - | Library ID of the item. |

### Poster Properties

| Property | Description |
|----------|-------------|
| `ListItem.Label` | Poster language, or `Text-free / Untagged` |
| `ListItem.Label2` | Dimensions, e.g. `2000x3000` |
| `ListItem.Art(thumb)`, `ListItem.Art(poster)` | The poster |
| `ListItem.Property(language)` | Language name, empty when text-free |
| `ListItem.Property(language_short)` | Language code, e.g. `en` |
| `ListItem.Property(width)`, `ListItem.Property(height)` | Size in pixels |
| `ListItem.Property(dimensions)` | Same as `Label2` |
| `ListItem.Property(aspectratio)` | Width divided by height |
| `ListItem.Property(rating)`, `ListItem.Property(votes)` | TMDB user rating and vote count |
| `ListItem.Property(images_path)` | This list's own path, for the image viewer |

**Widget Type:** Images

---

## Trakt Trending

Items being watched right now, ranked by concurrent viewers.

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

Most popular items on Trakt, based on overall user engagement.

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

Most anticipated upcoming releases, ranked by Trakt watchlist count.

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

Most watched items over a time period, ranked by unique viewers.

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

Most collected items over a time period, ranked by Trakt collection count.

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

Current top box office movies ranked by revenue.

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

Personalized recommendations based on the user's Trakt watch history and ratings.

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

## Trakt Most Played

Items played the most over a time period, counting every play including rewatches.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_played&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |
| `period` | No | `weekly` | `daily`, `weekly`, `monthly`, or `all` |

**Widget Type:** Movie or TV Show

---

## Trakt Watchlist

The user's Trakt watchlist, in the order set on Trakt.

**Requires Trakt OAuth.** Returns empty list if no Trakt account is linked.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_watchlist&amp;type=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

**Widget Type:** Movie or TV Show

---

## Trakt History

What the user watched most recently. A show is listed once, however many of its episodes were
watched.

**Requires Trakt OAuth.** Returns empty list if no Trakt account is linked.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_history&amp;type=tv</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `type` | No | `movie` | `movie` or `tv` |

**Widget Type:** Movie or TV Show

---

## Trakt In Progress

Shows the user has started with aired episodes left to watch, the most recently watched first.
Shows hidden from progress on Trakt are left out.

**Requires Trakt OAuth.** Returns empty list if no Trakt account is linked.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_inprogress</content>
```

**Widget Type:** TV Show

---

## Trakt Lists

Trakt lists as folders, each opening into its movies and shows (see [Trakt List Items](#trakt-list-items)).

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_lists&amp;kind=mine</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `kind` | No | `popular` | `mine` (your lists), `liked` (lists you liked), `popular` or `trending` |
| `limit` | No | `20` | Maximum lists |
| `page` | No | `1` | Pagination |

`mine` and `liked` require Trakt OAuth and return an empty list if no Trakt account is linked.

### List Properties

| Property | Description |
|----------|-------------|
| `ListItem.Label` | List name |
| `ListItem.Label2` | Number of items on the list |
| `ListItem.Plot` | List description |
| `ListItem.Art(poster)`, `ListItem.Art(thumb)` | The list's poster, when Trakt has one |
| `ListItem.Property(user)` | Name of the list's owner |
| `ListItem.Property(item_count)` | Same as `Label2` |
| `ListItem.Property(likes)` | Number of likes |

**Widget Type:** Folders

---

## Trakt List Items

The movies and shows on one Trakt list, in the list's rank order. Seasons, episodes and people on
the list are left out.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=trakt_list_items&amp;user=justin&amp;list=2142753</content>
```

The folders from [Trakt Lists](#trakt-lists) open this path with `user` and `list` filled in.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `user` | Yes | - | The list owner's Trakt username, or `me` for your own lists |
| `list` | Yes | - | The list's Trakt ID or slug |
| `type` | No | - | `movie` or `tv` for one type only; both when left out |
| `limit` | No | `20` | Maximum items |
| `page` | No | `1` | Pagination |
| `source` | No | `online` | `online` returns all; `library` filters to items in your library |

`user=me` requires Trakt OAuth and returns an empty list if no Trakt account is linked. Item
properties match the other Trakt widgets, see [Item Properties](#item-properties).

**Widget Type:** Movie, TV Show, or both

---

## Library Filter

Any discovery widget can be filtered to library-only items by adding `source=library`.

When an item matches a library entry:
- DBID is set on the video tag (enables library context menu)
- Movie items are playable (file URL set)
- TV show items link to their library folder
- `IsInLibrary` property is set to `true`

When `source=online` (default), all results are returned. Library matches still carry DBID and file path.

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

## Plugin Category

Every discovery widget sets `Container.PluginCategory` to its translated name ("TMDB Trending",
"Trakt Popular"); TMDB Recommendations sets "Recommendations". It is read the
same way as for [library widgets](widgets-library.md#localized-labels).

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
| `poster` | TMDB or Trakt, matching the widget |
| `fanart` | TMDB or Trakt, matching the widget |

---

[↑ Top](#discovery-widgets) · [Index](../index.md)
