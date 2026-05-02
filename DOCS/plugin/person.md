# Person Info

TMDB person information including biography, filmography, images, and crew.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [RunScript Usage](#runscript-usage)
- [Properties Set](#properties-set)
- [Matching Strategy](#matching-strategy)
- [Details Container](#details-container)
- [Images Container](#images-container)
- [Filmography Container](#filmography-container)
- [Crew Container](#crew-container)
- [Crew Lists](#crew-lists)

---

## Overview

Four plugin containers provide person data:

- Details - Biography and metadata
- Images - Profile images
- Filmography - Acting credits
- Crew - Director/writer/producer credits

Uses smart matching to find the correct person even when library scraped
with different providers.

---

## RunScript Usage

### person_info

Fetches person data and sets properties.

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  name=$INFO[ListItem.Label],
  role=$INFO[ListItem.Property(Role)],
  dbid=DBID,
  dbtype=DBTYPE)</onclick>
```

**Parameters:**

| Parameter     | Required | Description                                |
|---------------|----------|--------------------------------------------|
| `action`      | Yes      | `person_info`                              |
| `name`        | Yes*     | Actor/actress name                         |
| `role`        | No       | Character role (improves matching)         |
| `dbid`        | Yes      | Kodi database ID                           |
| `dbtype`      | Yes      | movie, tvshow, episode, season, set        |
| `sourceid`    | *        | Source DBID (required for set/season)      |
| `crew`        | No       | Crew type: director, writer, creator       |
| `separator`   | No       | Name separator (default: " / ")            |
| `auto_search` | No       | Show search on failure (default: true)     |
| `open_window` | No       | Window ID to open after search             |

**Movie set usage:**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  name=$INFO[ListItem.Label],
  role=$INFO[ListItem.Label2],
  dbtype=set,
  dbid=$INFO[ListItem.DBID],
  sourceid=$INFO[ListItem.Property(source_id)])</onclick>
```

**Season usage:**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  name=$INFO[ListItem.Label],
  role=$INFO[ListItem.Label2],
  dbtype=season,
  dbid=$INFO[ListItem.DBID],
  sourceid=$INFO[ListItem.Property(source_id)])</onclick>
```

**Crew lookup (director):**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  crew=director,
  dbid=$INFO[ListItem.DBID],
  dbtype=movie)</onclick>
```

**Crew lookup (writer):**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  crew=writer,
  dbid=$INFO[ListItem.DBID],
  dbtype=movie)</onclick>
```

**TV creator:**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_info,
  crew=creator,
  dbid=$INFO[ListItem.DBID],
  dbtype=tvshow)</onclick>
```

### person_search

Shows TMDB person search dialog.

**With context:**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_search,
  name=Actor Name,
  role=Role,
  dbtype=movie,
  dbid=123,
  open_window=1109)</onclick>
```

**Standalone:**

```xml
<onclick>RunScript(script.skin.info.service,
  action=person_search,
  query=Actor Name)</onclick>
```

---

## Properties Set

Window properties on Home window:

**On success:**

| Property                         | Value                                                                                              |
|----------------------------------|----------------------------------------------------------------------------------------------------|
| `SkinInfo.person_id`             | `<TMDB person ID>`                                                                                 |
| `SkinInfo.Person.Details`        | `plugin://script.skin.info.service/?action=person_info&info_type=details&person_id=N`              |
| `SkinInfo.Person.Images`         | `plugin://script.skin.info.service/?action=person_info&info_type=images&person_id=N`               |
| `SkinInfo.Person.Filmography`    | `plugin://script.skin.info.service/?action=person_info&info_type=filmography&person_id=N`          |
| `SkinInfo.Person.Crew`           | `plugin://script.skin.info.service/?action=person_info&info_type=crew&person_id=N`                 |
| `SkinInfo.Person.LibraryMovies`  | `plugin://script.skin.info.service/?action=person_library&info_type=movies&person_name=<encoded>`  |
| `SkinInfo.Person.LibraryTVShows` | `plugin://script.skin.info.service/?action=person_library&info_type=tvshows&person_name=<encoded>` |
| `SkinInfo.Person.BlurredImage`   | `<blurred profile image path>`                                                                     |

Skinners typically reference these via `$INFO[Window(Home).Property(SkinInfo.Person.Crew)]`
in `<content>` tags, but the raw paths above can also be hand-built when you need to add
filter params (e.g. `&sort=date_desc&job=Director` on the Crew URL — see Plugin Endpoints below).

**On failure (auto_search=false):**

| Property                      | Value                                |
|-------------------------------|--------------------------------------|
| `SkinInfo.Person.SearchQuery` | `<RunScript command for manual search>` |

---

## Matching Strategy

5-stage matching for scraper language mismatches:

1. **Exact Match** - Exact name + exact role
2. **Fuzzy Role** - Exact name + role substring
3. **Name Only** - Match by name alone
4. **Fuzzy Name** - Handle "First Last" vs "Last, First"
5. **Dialog Search** - TMDB search with image selection

**Name normalization:**

- Apostrophe variants (straight vs curly)
- Unicode normalization for accents
- Initial handling ("J. Smith" matches "J Smith")

---

## Details Container

Single ListItem with biography and metadata.

```xml
<content target="videos">
  $INFO[Window(Home).Property(SkinInfo.Person.Details)]
</content>
```

### Details Properties

| Property             | Description                 |
|----------------------|-----------------------------|
| `Name`               | Person name                 |
| `Biography`          | Biography text              |
| `Birthday`           | Birth date (YYYY-MM-DD)     |
| `BirthdayFormatted`  | Formatted birth date        |
| `Birthplace`         | Place of birth              |
| `Age`                | Current age (or at death)   |
| `Deathday`           | Death date                  |
| `DeathdayFormatted`  | Formatted death date        |
| `KnownFor`           | Department                  |
| `TopMovies`          | Top 5 movies                |
| `TopTVShows`         | Top 5 TV shows              |
| `person_id`          | TMDB person ID              |
| `imdb_id`            | IMDB ID                     |
| `Gender`             | Gender (1=Female, 2=Male)   |
| `Instagram`          | Instagram handle            |
| `Twitter`            | Twitter handle              |
| `Facebook`           | Facebook profile            |
| `TikTok`             | TikTok handle               |
| `YouTube`            | YouTube channel ID          |

### Details Artwork

`thumb`, `fanart` - Profile image

---

## Images Container

Multiple ListItems for profile images.

```xml
<content target="images">
  $INFO[Window(Home).Property(SkinInfo.Person.Images)]
</content>
```

### Images Properties

| Property      | Description   |
|---------------|---------------|
| `Width`       | Image width   |
| `Height`      | Image height  |
| `Rating`      | TMDB rating   |
| `Votes`       | Vote count    |
| `AspectRatio` | Aspect ratio  |

### Images Artwork

`thumb` - Profile image URL

---

## Filmography Container

Acting credits with filtering options.

```xml
<content target="videos">
  $INFO[Window(Home).Property(SkinInfo.Person.Filmography)]
</content>
```

**With filters:**

```xml
<content target="videos">plugin://script.skin.info.service/
  ?action=person_info
  &amp;info_type=filmography
  &amp;person_id=$INFO[Window(Home).Property(SkinInfo.person_id)]
  &amp;dbtype=movie
  &amp;min_votes=100
  &amp;exclude_unreleased=true
  &amp;sort=popularity
  &amp;limit=20</content>
```

### Filmography Filter Parameters

| Parameter           | Values                           | Description       |
|---------------------|----------------------------------|-------------------|
| `dbtype`            | movie, tvshow, both              | Filter by type    |
| `min_votes`         | 0-9999                           | Minimum votes     |
| `exclude_unreleased`| true, false                      | Exclude unreleased|
| `sort`              | popularity, date_desc, date_asc, | Sort order        |
|                     | rating, title                    |                   |
| `limit`             | 1-999                            | Maximum items     |

**Note:** Also accepts `both` for mixed results.

### Filmography Properties

| Property      | Description                                                |
|---------------|------------------------------------------------------------|
| `Title`       | Title                                                      |
| `Role`        | Character name (also set as `ListItem.Label2`)             |
| `MediaType`   | "movie" or "tv"                                            |
| `Year`        | Release year                                               |
| `Rating`      | TMDB rating                                                |
| `Votes`       | Vote count                                                 |
| `Overview`    | Plot summary                                               |
| `ReleaseDate` | Release date                                               |
| `Popularity`  | Popularity score                                           |

### Filmography Artwork

`thumb` - Poster, `fanart` - Backdrop

---

## Crew Container

Crew credits with same filtering options as filmography. By default, items where the
person held multiple roles (e.g. directed AND wrote the same movie) appear once with
all roles aggregated into the `Job` property as a comma-separated string.

```xml
<content target="videos">
  $INFO[Window(Home).Property(SkinInfo.Person.Crew)]
</content>
```

**With filters:**

```xml
<content target="videos">plugin://script.skin.info.service/
  ?action=person_info
  &amp;info_type=crew
  &amp;person_id=$INFO[Window(Home).Property(SkinInfo.person_id)]
  &amp;dbtype=movie
  &amp;sort=date_desc
  &amp;limit=50</content>
```

### Crew Filter Parameters

All filmography parameters apply (`dbtype`, `sort`, `min_votes`, `exclude_unreleased`,
`limit`) plus:

| Parameter | Values                                          | Description                                                |
|-----------|-------------------------------------------------|------------------------------------------------------------|
| `job`     | `Director`, `Writer`, `Producer`, `Creator`, ... | Show only items where the person held this exact job (case-insensitive). When set, dedupe is skipped because each item has at most one entry per job. |

Example — only items Ivan Reitman directed:
```
&amp;info_type=crew&amp;person_id=8858&amp;job=Director
```

### Crew Properties

Same as filmography plus:

| Property     | Description                                                              |
|--------------|--------------------------------------------------------------------------|
| `Job`        | Job title (or comma-separated list when an item has multiple roles)      |
| `Department` | Department of the first credit (`Directing`, `Writing`, `Production`...) |

---

## Crew Lists

Plugin paths for directors, writers, or creators.

### Crew List Usage

```xml
<!-- Directors -->
<content>plugin://script.skin.info.service/
  ?action=directors
  &amp;dbtype=movie
  &amp;dbid=$INFO[ListItem.DBID]</content>

<!-- Writers -->
<content>plugin://script.skin.info.service/
  ?action=writers
  &amp;dbtype=movie
  &amp;dbid=$INFO[ListItem.DBID]</content>

<!-- TV Creators -->
<content>plugin://script.skin.info.service/
  ?action=creators
  &amp;dbtype=tvshow
  &amp;dbid=$INFO[ListItem.DBID]</content>
```

### Crew List Parameters

| Parameter | Values                       | Description  |
|-----------|------------------------------|--------------|
| `action`  | directors, writers, creators | Action type  |
| `dbtype`  | movie, tvshow                | Media type   |
| `dbid`    | integer                      | Database ID  |

### Crew List Properties

| Property   | Description    |
|------------|----------------|
| `Label`    | Person name    |
| `Label2`   | Job title      |
| `person_id` | TMDB person ID |
| `Job`      | Job title      |

### Crew List Artwork

`thumb`, `icon` - Profile image

### Crew List Notes

- `creators` only works with `dbtype=tvshow`
- Writers include: Writer, Screenplay, Story jobs
- Duplicates filtered (same person appears once)

---

## Library Containers (LibraryMovies / LibraryTVShows)

The `?action=person_library&info_type=movies` and `&info_type=tvshows`
plugin paths return Kodi library items where the person appears in cast.
Each ListItem additionally has:

| Property      | Description                                          |
|---------------|------------------------------------------------------|
| `Role`        | Character name from the item's cast (also `Label2`)  |

The role is resolved from the `cast` field of the matching library item.
When the actor's role isn't available (no role string in cast metadata),
the property is omitted and `Label2` stays empty.

---

## Example Implementation

```xml
<control type="group">
    <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.person_id))</visible>

    <!-- Biography -->
    <control type="textbox">
        <label>$INFO[Container(PersonDetails).ListItem.Property(Biography)]</label>
    </control>

    <!-- Profile Images -->
    <control type="fixedlist" id="PersonImages">
        <content target="images">
          $INFO[Window(Home).Property(SkinInfo.Person.Images)]
        </content>
        <itemlayout>
            <control type="image">
                <texture>$INFO[ListItem.Art(thumb)]</texture>
            </control>
        </itemlayout>
    </control>

    <!-- Filmography -->
    <control type="list" id="PersonFilmography">
        <content target="videos">
          plugin://script.skin.info.service/
            ?action=person_info
            &amp;info_type=filmography
            &amp;person_id=$INFO[Window(Home).Property(SkinInfo.person_id)]
            &amp;sort=popularity
            &amp;limit=50
        </content>
        <itemlayout>
            <control type="label">
                <label>$INFO[ListItem.Title] ($INFO[ListItem.Year])
                  - $INFO[ListItem.Property(Role)]</label>
            </control>
        </itemlayout>
    </control>
</control>
```

---

## Caching

Person data cached for 30 days. Actor matches not cached.

---

[↑ Top](#person-info) · [Index](../index.md)
