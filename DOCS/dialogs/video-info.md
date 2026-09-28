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
| `dbtype` | Conditional | `movie` or `tvshow`. Required when only `dbid` is provided. `tv` is also accepted and normalized to `tvshow`. |
| `dbid` | Conditional | Library ID. Provide this OR `tmdb_id`/`imdb_id`. |
| `tmdb_id` | Conditional | TMDB ID. |
| `imdb_id` | Conditional | IMDb ID. |

At least one of `dbid`, `tmdb_id`, or `imdb_id` is required.

## Window Properties

Set on the **dialog's own window** while it's open. Read via `$INFO[Window.Property(X)]` from
within the dialog XML.

> These are **bare** names, with no `SkinInfo.Online.` prefix. The service's library-browsing
> properties ([Online Properties](../service/online.md)) carry the same data but are prefixed;
> on this dialog use the plain name (`Title`, not `SkinInfo.Online.Title`).

Every property is only set when the value is non-empty. Availability depends on which providers returned data and
on the media type.

### Identity

| Property | Description |
|----------|-------------|
| `MediaType` | `movie` or `tvshow` |
| `DBID` | Library ID, when launched from a library item |
| `tmdb_id` | TMDB ID |
| `imdb_id` | IMDb ID |

### Online data

The dialog carries the same properties as [Online Properties](../service/online.md), read as
`Window.Property(<name>)`:

| Group | Properties |
|-------|------------|
| TMDb | [TMDb Properties](../service/online.md#tmdb-properties) |
| Ratings | [Ratings](../service/online.md#ratings) |
| Rotten Tomatoes status | [Rotten Tomatoes Status](../service/online.md#rotten-tomatoes-status) |
| Awards | [Awards](../service/online.md#awards) |
| Common Sense Media | [Common Sense Media](../service/online.md#common-sense-media) |
| Trakt | [Trakt](../service/online.md#trakt) |
| MDBList | [MDBList](../service/online.md#mdblist) |

`Episode.Rating.*` is not set on the dialog.

### Blurred images

| Property | Description |
|----------|-------------|
| `BlurredPoster` | Blurred copy of `Poster`, generated on open |
| `BlurredFanart` | Blurred copy of `Fanart`, generated on open |

The two blurred images are produced in the background, so they appear a moment after the dialog
opens. Blur radius follows [`SkinInfo.BlurRadius`](../tools/blur.md#blur-radius).

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
| `container.library.path` | The item's full local library record as a single ListItem (only when `dbid` is known), read via `Container(<id>).ListItem.*` for all local art, stream details, watched state |
