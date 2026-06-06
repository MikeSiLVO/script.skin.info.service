# IMDb Top 250 Update

Set the IMDb Top 250 rank on matching library items from Trakt's official curated list.

[← Back to Index](../index.md)

## Tools Menu

Access via **Tools > IMDb Top 250 Update**.

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
