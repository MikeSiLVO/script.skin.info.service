# Video Info Dialog

A full-screen video info dialog with poster, ratings, plot, and panels for cast, recommendations, similar items, and crew.

[← Back to Index](../index.md)

---

## Launch

```xml
<!-- From a library item -->
<onclick>RunScript(script.skin.info.service,action=dialog_video_info,
  dbid=$INFO[ListItem.DBID],
  dbtype=$INFO[ListItem.DBType])</onclick>

<!-- From a TMDB-only item (e.g., a discovery widget) -->
<onclick>RunScript(script.skin.info.service,action=dialog_video_info,
  tmdb_id=$INFO[ListItem.Property(tmdb_id)],
  dbtype=$INFO[ListItem.Property(MediaType)])</onclick>
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `dbtype` | Conditional | `movie`, `tvshow`, or `episode`. Required when only `dbid` is provided; recommended otherwise. `tv` is also accepted and normalized to `tvshow`. |
| `dbid` | Conditional | Library ID. Provide this OR `tmdb_id`/`imdb_id`. Episodes resolve to their parent TV show. |
| `tmdb_id` | Conditional | TMDB ID. |
| `imdb_id` | Conditional | IMDb ID. Resolved to a TMDB ID internally. |
| `set_home_props` | No | Default `false`. If `true`, mirrors the dialog's Window properties to the Home window. |

At least one of `dbid`, `tmdb_id`, or `imdb_id` is required.

## Window Properties

Set on the dialog window while it's open. Read via `$INFO[Window.Property(X)]`.

### Video Data

| Property | Description |
|----------|-------------|
| `Title` | Title |
| `Year` | Release year |
| `MediaType` | `movie` or `tvshow` |
| `DBID` | Library ID (if launched from a library item) |
| `tmdb_id`, `imdb_id` | External IDs |
| `Genre` | Comma-joined genres |
| `Runtime` | Runtime string |
| `MPAA` | Content rating |
| `Tagline` | Tagline |
| `Plot` | Plot/overview |
| `Director`, `Writer` | Top crew names |
| `Studio` | Studio |
| `Rating.tmdb`, `Rating.imdb`, `Rating.trakt` | External ratings |
| `Poster`, `Fanart` | Image URLs |

The full set of online properties depends on which providers have data — see [Online Properties](../service/online.md) for the broader list.

### Container Paths

Plugin URLs the dialog populates. Bind them to any container `<content>` in your XML.

| Property | Source |
|----------|--------|
| `container.cast.path` | TMDB cast |
| `container.recommendations.path` | TMDB "you might also like" |
| `container.similar.path` | Library items with overlapping genres |
| `container.crew.path` | Full crew, sorted by job importance |
