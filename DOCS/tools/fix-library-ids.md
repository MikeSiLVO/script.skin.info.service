# Fix Library IDs

Resolve missing or invalid IMDb, TMDB and TVDB uniqueids on library items so ratings updates, the Top 250 sync, and online lookups can match those items.

[← Back to Index](../index.md)

## Tools Menu

Access via **Tools > Fix Library IDs**.

## What It Does

Scans the library for items where the `uniqueid` field is missing, malformed, or doesn't cross-reference correctly between providers. For each problem item, the tool resolves the missing ID by cross-referencing the existing IDs (for example, recovering a missing `imdb` from a known `tmdb`, or a missing `tmdb` from a known `tvdb`) and writes the recovered IDs back to the library.

## Notes

- Runs with a progress dialog and a summary report at the end.
- Safe to re-run; items that already have valid IDs are skipped.

---

[↑ Top](#fix-library-ids) · [Index](../index.md)
