# Actor Info Dialog

A full-screen actor info dialog with profile image, biography, top credits, and panels for filmography, crew credits, library matches, and images.

[← Back to Index](../index.md)

---

## Launch

```xml
<!-- From a cast list item -->
<onclick>RunScript(script.skin.info.service,action=dialog_actor_info,
  person_id=$INFO[Container.ListItem.Property(person_id)],
  name=$ESCINFO[Container.ListItem.Label])</onclick>

<!-- From a name in plain text (resolves via the parent video's TMDB cast) -->
<onclick>RunScript(script.skin.info.service,action=dialog_actor_info,
  name=$ESCINFO[Container.ListItem.Label],
  dbid=$INFO[ListItem.DBID],
  dbtype=$INFO[ListItem.DBType])</onclick>

<!-- For a crew role (director/writer/creator) of a video -->
<onclick>RunScript(script.skin.info.service,action=dialog_actor_info,
  crew=director,
  dbid=$INFO[ListItem.DBID],
  dbtype=$INFO[ListItem.DBType])</onclick>
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `person_id` | Conditional | TMDB person ID. Opens directly. |
| `name` | Conditional | Person name. Used to look up `person_id` from the parent video's TMDB cast or crew. Required if `person_id` is absent. |
| `dbid` | Conditional | Library ID of the parent video. Required when `name` is the only identifier. |
| `dbtype` | Conditional | `movie`, `tvshow`, `episode`, `season`, or `set`. Pairs with `dbid`. |
| `role` | No | Character name. Helps disambiguate when multiple cast members share the same name. |
| `crew` | No | `director`, `writer`, or `creator`. When provided (with `dbid`+`dbtype`), shows a picker of all matching crew members or opens the dialog directly if there's only one. |
| `sourceid` | Conditional | When `dbtype` is `set` or `season`, this is the source movie or episode ID used to resolve the person. |
| `separator` | No | Default ` / `. Separator for multi-name `name` values (e.g., `"John Doe / Jane Smith"`). |
| `auto_search` | No | Default `true`. If `false`, the dialog will not run a TMDB name search when the person isn't found in the parent video's cast. |
| `online` | No | Default `false`. Forces the cast lookup to fetch fresh data from TMDB rather than relying on Kodi's library cast. |

## Window Properties

Set on the dialog window while it's open. Read via `$INFO[Window.Property(X)]`.

### Person Data

| Property | Description |
|----------|-------------|
| `Name` | Person name |
| `person_id` | TMDB person ID |
| `imdb_id` | IMDb ID |
| `Biography` | Bio text |
| `Birthday`, `BirthdayFormatted` | Birth date |
| `Deathday`, `DeathdayFormatted` | Death date |
| `Age` | Calculated age |
| `Birthplace` | Place of birth |
| `KnownFor` | Department (e.g., "Acting") |
| `Gender` | Gender text |
| `TopMovies`, `TopTVShows` | Top credit titles |
| `ProfileImage` | Profile image URL |

### Container Paths

Plugin URLs the dialog populates. Bind them to any container `<content>` in your XML.

| Property | Source |
|----------|--------|
| `container.library_movies.path` | Library movies featuring this person |
| `container.library_tvshows.path` | Library TV shows featuring this person |
| `container.movies.path` | TMDB filmography — movies only |
| `container.tvshows.path` | TMDB filmography — TV only |
| `container.all_credits.path` | Full TMDB filmography |
| `container.crew.path` | TMDB crew credits |
| `container.images.path` | Profile images from TMDB |
