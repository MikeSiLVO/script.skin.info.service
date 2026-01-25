# GIF Scanner

Scan library for animated GIF poster files.

[← Back to Index](../index.md)

---

## Overview

The Gif Poster Scanner is a utility tool that scans your Kodi library for animated gif poster files and adds them to your media items as "animatedposter" art.

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

- **Incremental** - Only checks items added since the last scan (faster subsequent scans)
- **Full Scan** - Scans all items regardless of when they were added
- **Always Ask** - Prompts you to choose each time

Use Full Scan when you've:

- Added gif files to existing movies/shows
- Changed your filename patterns
- Want to verify all items

## How It Works

1. The scanner searches your Kodi video library
2. For each movie or TV show, it checks the media folder for gif files matching your patterns
3. If a gif is found and the item doesn't already have an animatedposter, it adds it
4. Progress is shown in a dialog with cancel support
5. A notification shows the results when complete

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

- The scanner skips items that already have animatedposter set
- Progress can be cancelled at any time
- Results are shown in a notification when complete

---

[↑ Top](#gif-scanner) · [Index](../index.md)
