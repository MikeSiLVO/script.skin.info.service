# Sync TV Show Metadata

Fetch online metadata for every TV show in the library in one pass, instead of one show at a time while browsing.

[← Back to Index](../index.md)

## Settings

Access via addon settings under **Sync TV Show Metadata**.

## RunScript

```xml
RunScript(script.skin.info.service,action=sync_tvshows)
```

Takes no parameters. A confirmation prompt appears before anything runs.

## What It Does

Scans every TV show in the library, then fetches TMDB metadata for the ones that aren't cached yet. Shows already in the cache are skipped, so re-running it only picks up what's new.

Alongside the metadata, it records each show's status and its next and last episode to air, so that information is ready without waiting on a lookup. Next-episode dates already in the past are discarded rather than stored.

A progress dialog reports each show as it goes and can be cancelled at any point. Work completed before cancelling is kept. A summary at the end reports updated, skipped and failed counts.

## Notes

- Runs in the foreground only. There is no background mode.
- Only one long-running task can be active at a time. If another is running you are asked whether to cancel it first.
- Shows without a TMDB ID are not fetched. Run **Fix Library IDs** first if shows are being missed.
- Large libraries take a while, since the fetch is paced to the provider's rate limit.

---

[↑ Top](#sync-tv-show-metadata) · [Index](../index.md)
