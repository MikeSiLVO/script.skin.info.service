# GIF Scanner

Scan library for animated GIF poster files.

[← Back to Index](../index.md)

---

## Overview

The Gif Poster Scanner scans your Kodi library for animated gif poster files and adds them to your media items as "animatedposter" art.

## Usage

### Accessing the Scanner

The Gif Poster Scanner is accessed via the Tools menu:

```xml
<!-- Open Tools menu, then select "Animated Art Scanner" -->
<onclick>RunScript(script.skin.info.service,action=tools)</onclick>
```

When launched, a dialog appears letting you choose:

- All (Movies + TV Shows)
- Movies Only
- TV Shows Only

## Configuration

Configure the scanner in addon settings under **Artwork > Animated Art**:

### Gif Filename Patterns

Settings > Artwork > Animated Art

Default patterns: `poster.gif, animatedposter.gif`

You can add custom patterns separated by commas.

**Pattern Matching:**

- **Exact match**: Files named exactly as the pattern (e.g., `poster.gif`)
- **Suffix match**: Files ending with the pattern (e.g., `movie.poster.gif`)
- If multiple files match, the shortest filename is used (most specific match)

### Scan Mode

Settings > Artwork > Animated Art

Default: `Incremental`

Options:

- **Incremental** - Skips gif files already applied and unchanged since the last scan
- **Full Scan** - Applies every matching gif file found
- **Always Ask** - Prompts you to choose each time

Incremental does not reapply an unchanged gif, for example after its art was removed in Kodi.

## Accessing Animated Posters

Once added, animated posters are available in your skin via:

```xml
$INFO[ListItem.Art(animatedposter)]
```

With fallback to regular poster:

```xml
<texture fallback="$INFO[ListItem.Art(poster)]">$INFO[ListItem.Art(animatedposter)]</texture>
```

## Supported Media Types

- Movies
- TV Shows

## File Location

The scanner looks for gif files in the same folder as your media files. For example:

```text
/Movies/Movie Title/
  ├── Movie.mkv
  └── poster.gif                  <- Will be found (exact match)

/Movies/Another Movie/
  ├── Movie.mkv
  └── Movie.Title.poster.gif      <- Will be found (suffix match)
```

## Notes

- Items with no matching gif keep any animatedposter they already have
- Progress can be canceled at any time
- Results are shown in a notification when complete

---

[↑ Top](#gif-scanner) · [Index](../index.md)
