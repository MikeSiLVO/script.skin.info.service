# IMDb Top 250 Update

Set the IMDb Top 250 rank on matching library items from Trakt's official curated list.

[← Back to Index](../index.md)

## Tools Menu

Access via **Tools > IMDb Top 250 Update**.

## RunScript

```xml
RunScript(script.skin.info.service,action=update_top250)
```

Takes no parameters. Runs the update straight away and closes when it finishes, rather than
returning to the Tools menu.

## Auto-Update

Under **Settings > Ratings > IMDb Top 250**, set **Auto-update** to run it unattended:

| Option | When it runs |
|--------|--------------|
| Off | Never; the Tools entry and RunScript still work |
| After library scan | Once each library scan finishes |
| Every day | Once a day, timed to land after Trakt refreshes the list |
| Both | Either trigger |

Automatic runs show a background progress bar instead of a dialog, ask for no confirmation, and
finish with a notification giving the same counts as the manual summary. The notification waits
until video playback stops, so it never appears over a film.

Trakt rebuilds the list each morning, and the daily check aims for an hour after that, learning the
time from the list itself rather than counting 24 hours from whenever Kodi last started. If the box
was off when a check was due, it runs shortly after the next start. When the list comes back
unchanged from the previous run, the library is left untouched and no notification appears.

## What It Does

Fetches the current IMDb Top 250 list from Trakt and walks the library to update each movie's `top250` field. Items that are no longer on the list have their `top250` value cleared. Existing correct rankings are left alone.

A progress dialog reports counts as it runs and a summary shows results at the end (set, cleared, failed, unchanged).

## Library Property

Matching items expose the rank via the `Top250` field on the ListItem (e.g. `$INFO[ListItem.Top250]`), and via the focused-item property `SkinInfo.Top250`.

## Notes

- Matches use both `imdb` and `tmdb` uniqueids, so library items with either ID will pick up their rank.
- Run periodically; the Trakt list is curated and updates as IMDb's rankings shift.
- Items without either uniqueid won't match. Run **Fix Library IDs** first if rankings aren't appearing.

---

[↑ Top](#imdb-top-250-update) · [Index](../index.md)
