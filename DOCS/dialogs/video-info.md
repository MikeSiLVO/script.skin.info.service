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
| `dbtype` | Conditional | `movie` or `tvshow`. Required when only `dbid` is provided; recommended otherwise. `tv` is also accepted and normalized to `tvshow`. |
| `dbid` | Conditional | Library ID. Provide this OR `tmdb_id`/`imdb_id`. |
| `tmdb_id` | Conditional | TMDB ID. |
| `imdb_id` | Conditional | IMDb ID. Resolved to a TMDB ID internally. |

At least one of `dbid`, `tmdb_id`, or `imdb_id` is required.

## Window Properties

Set on the **dialog's own window** while it's open. Read via `$INFO[Window.Property(X)]` from
within the dialog XML.

> These are **bare** names — no `SkinInfo.Online.` prefix. The service's library-browsing
> properties ([Online Properties](../service/online.md)) carry the same data but are prefixed;
> on this dialog use the plain name (`Title`, not `SkinInfo.Online.Title`).

Every property is only set when the value is non-empty, so gate on
`!String.IsEmpty(Window.Property(X))`. Availability depends on which providers returned data and
on the media type.

### Identity

| Property | Description |
|----------|-------------|
| `MediaType` | `movie` or `tvshow` |
| `DBID` | Library ID, when launched from a library item |
| `tmdb_id` | TMDB ID |
| `imdb_id` | IMDb ID |

### Core (movie + TV show)

| Property | Description |
|----------|-------------|
| `Title` | Title |
| `OriginalTitle` | Original-language title |
| `Plot` | Plot/overview |
| `Tagline` | Tagline |
| `Status` | Release/production status |
| `Year` | Release/first-air year |
| `Premiered` | Release/first-air date (`YYYY-MM-DD`) |
| `PremieredFormatted` | Localized formatted date |
| `Runtime` | Runtime in minutes |
| `Genre` | Genres, `" / "` separated |
| `Country` | Countries, `" / "` separated |
| `Studio` | Studios/networks, `" / "` separated |
| `Popularity` | TMDB popularity score |
| `Homepage` | Official website URL |
| `MPAA` | US certification |
| `Trailer` | YouTube trailer plugin URL |
| `TrailerYouTubeID` | YouTube video ID |
| `Tag` | TMDB keywords, `" / "` separated |

### Movie-specific

| Property | Description |
|----------|-------------|
| `Budget` | Production budget (comma-formatted) |
| `Revenue` | Box-office revenue (comma-formatted) |
| `Set` | Collection name |
| `SetID` | Collection TMDB ID |

### TV show-specific

| Property | Description |
|----------|-------------|
| `Type` | Show type (Scripted, Documentary, ...) |
| `Seasons` | Total season count |
| `Episodes` | Total episode count |
| `Creator` | Creator(s), `" / "` separated |
| `LastAired` / `LastAiredFormatted` | Last air date (raw / formatted) |
| `LastEpisodeTitle` | Last aired episode title |
| `LastEpisode` / `LastEpisodeSeason` | Last aired episode / season number |
| `LastEpisodeAired` | Last episode air date (formatted) |
| `NextEpisodeTitle` | Next upcoming episode title |
| `NextEpisode` / `NextEpisodeSeason` | Next episode / season number |
| `NextEpisodeAired` | Next episode air date (formatted) |

### Credits

| Property | Description |
|----------|-------------|
| `Cast` | Top 10 cast names, `" / "` separated |
| `Cast.1.Name` … `Cast.5.Name` | Individual cast names (top 5) |
| `Cast.1.Role` … `Cast.5.Role` | Character names |
| `Cast.1.Thumb` … `Cast.5.Thumb` | Profile image URLs |
| `Director` | Director(s), `" / "` separated |
| `Writer` | Writer(s), `" / "` separated |

### Images

| Property | Description |
|----------|-------------|
| `Poster` | Poster image URL |
| `Fanart` | Backdrop image URL |
| `Clearlogo` | Clear logo URL (English preferred) |
| `BlurredPoster` | Blurred copy of `Poster`, generated on open |
| `BlurredFanart` | Blurred copy of `Fanart`, generated on open |

The two blurred images are produced in the background, so they appear a moment after the dialog
opens. Blur radius follows the skin string `SkinInfo.BlurRadius` (default 40).

### IDs

| Property | Description |
|----------|-------------|
| `IMDBNumber` | IMDb ID |
| `TMDBID` | TMDB ID |
| `TVDBID` | TVDB ID (TV shows) |

### Ratings

Each source provides three properties: `Rating.{source}`, `Rating.{source}.Votes`,
`Rating.{source}.Percent` (0-100).

| Source key | Provider |
|------------|----------|
| `Rating.tmdb` | TMDB |
| `Rating.imdb` | MDBList, OMDb backfill |
| `Rating.trakt` | Trakt |
| `Rating.metacritic` | MDBList, OMDb backfill |
| `Rating.metacriticuser` | MDBList |
| `Rating.letterboxd` | MDBList |
| `Rating.rogerebert` | MDBList |
| `Rating.myanimelist` | MDBList |
| `Rating.tomatoes` | MDBList, OMDb backfill |
| `Rating.popcorn` | MDBList, OMDb backfill |

Which sources appear depends on what the providers return for the title. Property names are
case-insensitive.

### Rotten Tomatoes status

| Property | Values |
|----------|--------|
| `Tomatometer` | `Certified`, `Fresh`, `Rotten` |
| `Popcornmeter` | `Hot`, `Fresh`, `Spilled` |

### Awards (OMDb)

| Property | Description |
|----------|-------------|
| `Awards` | Full awards text |
| `Awards.Oscar.Wins` / `Awards.Oscar.Nominations` | Oscars |
| `Awards.Emmy.Wins` / `Awards.Emmy.Nominations` | Emmys |
| `Awards.Other.Wins` / `Awards.Other.Nominations` | Other wins/nominations |

### Common Sense Media (MDBList)

| Property | Description |
|----------|-------------|
| `CommonSense.Age` | Recommended minimum age |
| `CommonSense.Violence` / `.Nudity` / `.Language` / `.Drinking` | Severity 1 (minimal) - 5 (severe) |
| `CommonSense.Selection` | `true` if a Common Sense Selection |
| `CommonSense.Summary` | Localized summary |
| `CommonSense.Reasons` | Localized content reasons |

### Other provider data

| Property | Provider | Description |
|----------|----------|-------------|
| `Trakt.Subgenres` | Trakt | Curated subgenres, `" / "` separated |
| `MDBList.Trailer` | MDBList | Trailer URL |
| `MDBList.Certification` | MDBList | Content certification |

### Dialog stacking

Clicking cast/recommendations opens another dialog on top. To animate covered windows, use:

| Property | Where | Meaning |
|----------|-------|---------|
| `istop` | dialog window | Set only on the topmost dialog; empty on a dialog that's covered |
| `SkinInfo.DialogTopId` | Home window | Non-empty while any dialog is open (use on the underlying window) |

```xml
<!-- Slide a covered dialog out of the way -->
<animation effect="slide" end="-730,0" time="500" tween="quadratic"
           condition="String.IsEmpty(Window.Property(istop))">Conditional</animation>
```

### Container Paths

Plugin URLs the dialog populates. Bind them to any container `<content>` in your XML.

| Property | Source |
|----------|--------|
| `container.cast.path` | TMDB cast |
| `container.recommendations.path` | TMDB "you might also like" |
| `container.similar.path` | Library items with overlapping genres |
| `container.crew.path` | Full crew, sorted by job importance |
| `container.library.path` | The item's full local library record as a single ListItem (only when `dbid` is known) — read via `Container(<id>).ListItem.*` for all local art, stream details, watched state |
