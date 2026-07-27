# Ratings Update

Refresh IMDb, TMDB and Trakt ratings on library items in bulk.

[← Back to Index](../index.md)

## Tools Menu

Access via **Tools > Ratings**.

### Update by Media Type

| Option | Scope |
|--------|-------|
| Update Movies | All movies in the library |
| Update TV Shows | All TV shows in the library |
| Update Episodes | All episodes in the library |
| Update All | Movies, TV shows and episodes |

### Foreground / Background

After choosing a scope, pick how the update runs:

| Mode | Behavior |
|------|----------|
| Foreground | Runs with a progress dialog. Cancel any time. |
| Background | Runs as a background task. Notifications when complete. Only one background ratings update can run at a time. |

### View Report

After any update, the menu shows a **View Report** entry summarizing what changed (counts of updated, unchanged, and failed items).

## RunScript

### Single Item

Refresh ratings for one library item:

```xml
RunScript(script.skin.info.service,action=update_ratings,dbid=$INFO[ListItem.DBID],dbtype=$INFO[ListItem.DBType])
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `dbid` | Yes | Database ID of the item |
| `dbtype` | Yes | `movie`, `tvshow`, `episode` or `set` |

Same operation as the **Update Ratings** context menu item.

### Bulk

Run a library-wide update without going through the Tools menu:

```xml
RunScript(script.skin.info.service,action=update_library_ratings,dbtype=movie,background=true)
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `dbtype` | No | `movie` | `movie`, `tvshow` or `episode`. Anything else falls back to `movie`. |
| `background` | No | `true` | `true` runs as a background task, `false` shows a progress dialog. |

Note this takes one media type, unlike the Tools menu's **Update All**. Call it once per type for the same coverage.

## What Gets Updated

For each item, the latest ratings are fetched from the enabled providers and written to the library's `ratings` field. Sources include TMDB, IMDb and Trakt. Disable providers in addon settings to skip them.

## Notes

- Items without an external ID (no `imdb`, `tmdb` or `tvdb` uniqueid in the library) are skipped.
- Episode ratings require a TMDB ID on the parent show.
- The full update is throttled to provider rate limits; large libraries may take a while in background mode.

---

[↑ Top](#ratings-update) · [Index](../index.md)
