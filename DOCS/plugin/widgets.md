# Widgets

Smart widget content for home screens and info dialogs.

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
<content>plugin://script.skin.info.service/?action=similar&amp;dbid=$INFO[ListItem.DBID]&amp;dbtype=$INFO[ListItem.DBType]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbid` | Yes | - | Database ID |
| `dbtype` | No | movie | Source type (movie/tvshow/episode) |
| `limit` | No | 25 | Maximum items |

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

Personalized recommendations based on watch history.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | No | movie | Content type (movie/tvshow/both) |
| `limit` | No | 25 | Maximum items |
| `strict_rating` | No | false | Only match MPAA ratings from history |
| `min_rating` | No | 6.0 | Minimum rating threshold |

**Note:** Also accepts `both` for mixed results.

### Examples

```xml
<!-- Movies -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie</content>

<!-- TV shows -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=tvshow</content>

<!-- Mixed -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=both</content>

<!-- Family mode -->
<content>plugin://script.skin.info.service/?action=recommended&amp;dbtype=movie&amp;strict_rating=true&amp;min_rating=7.0</content>
```

### Scoring

Analyzes last 20 watched items:

- **Genre overlap**: +10 points per matching genre
- **MPAA match**: +5 points if in history
- **Year range**: +3 points if within watched range
- **Favorite actor**: +2 points (appearing 2+ times)
- **Favorite director**: +3 points (appearing 2+ times)

**Widget Type:**

- **dbtype=movie**: Movie widget
- **dbtype=tvshow**: TV Show widget
- **dbtype=both**: Mixed widget

### Notes

- Requires watch history
- Only returns unwatched items
- Genre overlap required

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
| `halloween` | Halloween movies |
| `valentines` | Valentine's Day movies |
| `thanksgiving` | Thanksgiving movies |
| `newyear` | New Year's movies |
| `easter` | Easter movies |
| `independence` | Independence Day movies |
| `starwars` | Star Wars franchise |
| `startrek` | Star Trek franchise |
| `horror` | Horror movies |

### Sort Methods

`random`, `title`, `year`, `rating`, `dateadded`

### Examples

```xml
<!-- Christmas random -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=christmas</content>

<!-- Halloween by rating -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=halloween&amp;sort=rating</content>

<!-- Horror marathon -->
<content>plugin://script.skin.info.service/?action=seasonal&amp;season=horror&amp;limit=100</content>
```

### Notes

- Requires TMDB tags (enable in scraper settings)
- Returns empty if tag scraping disabled
- Uses OR logic (matches ANY season tag)

**Widget Type:** Movie

---

[↑ Top](#widgets) · [Index](../index.md)
