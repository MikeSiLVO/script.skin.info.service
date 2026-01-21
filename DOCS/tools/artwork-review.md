# Artwork Review

Scan library for missing artwork and fetch from TMDB and fanart.tv.

[← Back to Index](../index.md)

---

## Table of Contents

- [Requirements](#requirements)
  - [API Keys](#api-keys)
  - [Getting API Keys](#getting-api-keys)
- [Usage](#usage)
  - [Bulk Review (Tools Menu)](#bulk-review-tools-menu)
  - [Single Item Review (Context Menu)](#single-item-review-context-menu)
- [Review Process](#review-process)
  - [Visual Dialog](#visual-dialog)
  - [User Actions](#user-actions)
  - [Multi-Art Dialog](#multi-art-dialog)
  - [Auto Fetch Prompt](#auto-fetch-prompt)
- [Processing Modes](#processing-modes)
- [Session Reports](#session-reports)
- [Configuration](#configuration)
- [Dialog Skinning](#dialog-skinning)
  - [Artwork Selection Dialog](#artwork-selection-dialog)
  - [Multi-Art Dialog Skinning](#multi-art-dialog-skinning)
  - [Testing Your Dialog XML](#testing-your-dialog-xml)
- [Resume Capability](#resume-capability)
- [Troubleshooting](#troubleshooting)
- [Advanced Tips](#advanced-tips)

## Requirements

### API Keys

You must provide your own API keys - the addon does not include built-in keys.

#### Why Both APIs?

**TMDB provides:**

- poster
- fanart (backdrops)
- clearlogo

**fanart.tv provides:**

- poster
- fanart (backgrounds)
- clearlogo
- clearart
- banner
- discart (disc art)
- landscape
- characterart (TV shows only)

TMDB is required for basic artwork. fanart.tv provides additional artwork types including clearart, banners, disc art, and landscape images.

#### Getting API Keys

**TMDB API Key** - Free & Optional

A built-in TMDB key is included. To use your own key:

1. Sign up at [themoviedb.org](https://www.themoviedb.org/)
2. Go to Settings → API → Request API Key
3. Select "Developer" as the type of use
4. Fill out the required information
5. Copy your API key
6. Add to addon settings: Settings → Advanced → Enable "Use Custom TMDB Key" → Enter Key

**fanart.tv API Key** - Free & Optional

1. Sign up at [fanart.tv](https://fanart.tv/)
2. Get your personal API key from [fanart.tv/get-an-api-key](https://fanart.tv/get-an-api-key/)
3. Copy your personal API key
4. Add to addon settings: Settings → API Keys → fanart.tv API Key

## Usage

### Bulk Review (Tools Menu)

Launch the artwork tools workflow from your skin:

```text
RunScript(script.skin.info.service,action=tools)
```

#### Scope Selection

Choose which media types to review:

- **Movies** - Review movie artwork only
- **TV Shows** - Review TV show artwork only
- **Music** - Review music artwork only
- **All** - Review all media types

#### Action Menu

After choosing a scope, select an action:

- **Continue Review** - Resume a paused review session (shown when pending items exist)
- **Manual Review** - Start or resume a manual review session with visual artwork selection
- **Auto-Apply Missing Artwork** - Scan and automatically fill language-compliant empty slots
- **View Last Report** - View statistics from your last review session (when available)

When starting **Manual Review**, choose what to scan for:

- **Missing + upgrades** - Find missing artwork AND better quality replacements (default)
- **Missing artwork only** - Only find missing artwork slots

---

### Single Item Review (Context Menu)

Review artwork for a specific library item using RunScript:

```xml
RunScript(script.skin.info.service,action=review_artwork,dbid=$INFO[ListItem.DBID],dbtype=$INFO[ListItem.DBType])
```

**Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `dbid` | Yes | Database ID of the item |
| `dbtype` | Yes | Database type: `movie`, `tvshow`, `season`, `episode`, `musicvideo`, `set` |

**Example - Context Menu:**

```xml
<control type="button" id="1">
    <label>Review Artwork</label>
    <onclick>RunScript(script.skin.info.service,action=review_artwork,dbid=$INFO[ListItem.DBID],dbtype=$INFO[ListItem.DBType])</onclick>
</control>
```

This launches the artwork review dialog for the focused item, showing all available artwork from TMDB and fanart.tv.

---

## Review Process

### Visual Dialog

For each art type, a visual dialog shows:

- Thumbnail previews of all available options
- Resolution (width × height)
- Language (if applicable)
- Clear labels and metadata

### User Actions

- **Select**: Click the image or Select button to apply that artwork
- **Skip**: Skip this art type and leave it unchanged
- **Cancel**: Exit the review process (progress is saved)

### Multi-Art Dialog

For fanart and other multi-image types, a special dialog allows:

- View current extra art slots (fanart1, fanart2, etc.)
- Select multiple new images from available options
- Remove existing images
- Reorder by selection sequence
- Apply changes in one batch

### Auto Fetch Prompt

After manual review completes or is paused, if any missing artwork remains, you'll see a prompt:

- **Fetch** - Runs auto processor in "missing-only" mode, filling empty slots with language-compliant artwork
- **Skip** - Leaves queue untouched for later manual review

## Processing Modes

### Auto-Process

- Always applies the highest quality/resolution artwork
- No user interaction required
- Runs in background
- Triggered via **Auto-Apply Missing Artwork** action

### Manual Review

- Shows visual dialog for each art type
- User selects preferred artwork
- Can skip individual art types
- Can cancel to exit (progress saved)
- Triggered via **Manual Review** action

## Session Reports

Manual-review session details:

- Manual selections (title, art type, source, URL)
- Manual skips and auto-skipped entries (with reasons)
- Stale detections (queue entries invalidated mid-review)
- Auto-fetch runs: counts, applied URLs, skipped titles, remaining queue size

Reports are accessible from:

- **View Last Report** option in the action menu
- Resume dialog when picking a scope

## Configuration

Configure the Artwork Reviewer in addon settings under "Artwork Tools":

### Art Types to Check

Settings > Artwork Tools > Art Types to Check

Default: `poster,fanart,clearlogo,clearart,discart,banner,landscape,keyart`

Comma-separated list of art types to scan for. Common types:

- `poster` - Movie/show posters
- `fanart` - Background artwork
- `clearlogo` - Transparent logo
- `clearart` - Transparent artwork
- `discart` - Disc artwork
- `banner` - Wide banner artwork
- `landscape` - Landscape/thumb
- `keyart` - Key art/poster variant
- `characterart` - Character artwork

Not all art types are available for all items - availability depends on scraper sources.

## Dialog Skinning

### Artwork Selection Dialog

The default dialog is styled to match Kodi's Estuary skin and uses standard Estuary textures and patterns.

**For Skinners:**
To customize the artwork selection dialog for your skin, create:
`script.skin.info.service-ArtworkSelection.xml`

Kodi will automatically use your skin's version if it exists, otherwise falls back to the addon's default.

**Required control IDs:**

- **100**: Panel/List for artwork options (click to select)
- **201**: Skip button
- **202**: Cancel button
- **203**: Multi-Art button (visibility controlled by show_multiart property)
- **204**: Change Language button (visibility controlled by show_change_language property)
- **205**: Sort button (visibility controlled by show_sort_button property)
- **206**: Source filter button (visibility controlled by show_source_button property)

**Window Properties:**

- **Window.Property(arttype)**: Artwork type being selected (poster, fanart, clearlogo, etc.)
- **Window.Property(heading)**: Media item title
- **Window.Property(count)**: Formatted count (e.g., "15 available" or "24 of 58 available (English)")
- **Window.Property(count_total)**: Total number of artwork options (numeric string)
- **Window.Property(count_filtered)**: Number of filtered artwork options (numeric string)
- **Window.Property(mediatype)**: Media type (movie, tvshow, episode, musicvideo, artist, album)
- **Window.Property(year)**: Release year (e.g., "1999")
- **Window.Property(hascurrentart)**: "true" or "false"
- **Window.Property(currentarturl)**: URL of existing artwork (empty if none exists)
- **Window.Property(language)**: Display name for current language filter (e.g., "English")
- **Window.Property(language_short)**: Language code (e.g., "en")
- **Window.Property(show_multiart)**: "true" or "false"
- **Window.Property(show_change_language)**: "true" or "false"
- **Window.Property(show_sort_button)**: "true" or "false"
- **Window.Property(show_source_button)**: "true" or "false"

**Example conditional usage in XML:**

```xml
<!-- Show different layout for fanart vs poster -->
<visible>String.IsEqual(Window.Property(arttype),fanart)</visible>
<visible>String.IsEqual(Window.Property(arttype),poster)</visible>

<!-- Show message if only 1 option available -->
<visible>String.IsEqual(Window.Property(count_total),1)</visible>

<!-- Different layouts for movies vs TV shows -->
<visible>String.IsEqual(Window.Property(mediatype),movie)</visible>
<visible>String.IsEqual(Window.Property(mediatype),tvshow)</visible>

<!-- Show title with year context -->
<label>$INFO[Window.Property(heading)] ($INFO[Window.Property(year)])</label>

<!-- Show "Replace Existing" indicator when artwork exists -->
<visible>String.IsEqual(Window.Property(hascurrentart),true)</visible>

<!-- Side-by-side before/after comparison -->
<control type="image">
    <texture>$INFO[Window.Property(currentarturl)]</texture>
    <label>Current Artwork</label>
    <visible>String.IsEqual(Window.Property(hascurrentart),true)</visible>
</control>
```

### Multi-Art Dialog Skinning

To customize the multi-art selection dialog for your skin, create:
`script.skin.info.service-MultiArtSelection.xml`

This dialog uses a "working set" approach for managing extra art slots (fanart1+, poster1+, etc.):

**Required control IDs:**

- **100**: Current/Working art panel (shows working set, click to remove)
- **200**: Available art panel (shows options NOT in working set, click to add)
- **300**: Apply button (applies working set and closes)
- **301**: Cancel button
- **302**: Clear All button (resets to original state)

**How it works:**

- List 100 shows all items in the working set, labeled fanart1, fanart2, etc. based on position
- List 200 shows available art that is NOT already in the working set
- Clicking an item in list 200 appends it to the working set (list 100)
- Clicking an item in list 100 removes it from the working set
- Apply saves the working set as fanart1, fanart2, fanart3, etc. in order

**ListItem Properties (List 100 - Working Set):**

- `ListItem.Label`: Slot name (fanart1, fanart2, poster1, poster2, etc.)
- `ListItem.Art(thumb)`: Image URL
- `ListItem.Property(url)`: Full URL
- `ListItem.Property(index)`: Position in working set (0-based)

**ListItem Properties (List 200 - Available):**

- `ListItem.Label`: "Option 1 - 1920x1080 - [en]", etc. (includes available metadata)
- `ListItem.Art(thumb)`: Preview URL
- `ListItem.Property(url)`: Full URL
- `ListItem.Property(width)`: Resolution width
- `ListItem.Property(height)`: Resolution height
- `ListItem.Property(rating)`: User rating (if available)
- `ListItem.Property(language)`: Language code (if available)
- `ListItem.Property(likes)`: Number of likes (if available)
- `ListItem.Property(season)`: Season number (if available)

**Window Properties:**

- **Window.Property(multiart_dialog_active)**: "true" when dialog is open, cleared when closed
- **Window.Property(heading)**: Media item title
- **Window.Property(arttype)**: Art type label (e.g., "Multi-Art Fanart")
- **Window.Property(mediatype)**: Media type (movie, tvshow, etc.)
- **Window.Property(count)**: Formatted count (e.g., "3 images selected")
- **Window.Property(count_total)**: Total available images (numeric string)
- **Window.Property(count_selected)**: Number of selected images (numeric string)
- **Window.Property(show_sort_button)**: "true" or "false"
- **Window.Property(show_source_button)**: "true" or "false"

### Testing Your Dialog XML

Use the test functions to preview your dialogs with dummy data (survives ReloadSkin):

**Artwork Selection Dialog:**

```xml
RunScript(script.skin.info.service,action=arttest)
RunScript(script.skin.info.service,action=arttest,art_type=fanart)
RunScript(script.skin.info.service,action=arttest,art_type=clearlogo)
RunScript(script.skin.info.service,action=arttest,art_type=banner)
```

**Multi-Art Selection Dialog:**

```xml
RunScript(script.skin.info.service,action=multiarttest)
RunScript(script.skin.info.service,action=multiarttest,art_type=poster)
RunScript(script.skin.info.service,action=multiarttest,art_type=characterart)
```

Available test types: `poster`, `fanart`, `clearlogo`, `clearart`, `banner`, `landscape`, `keyart`, `characterart`, `discart`

**Artwork Selection Dialog Test Data:**

- 20-30 dummy artwork options with realistic aspect ratios per art type
- Different resolutions, ratings, likes, languages, and season numbers

**Multi-Art Dialog Test Data:**

- 2 existing extra art items (fanart1, fanart2)
- 20 available art options with realistic dimensions
- All items use type-specific test images from resources/media/artwork_test/

Workflow: Edit XML → `ReloadSkin()` → Re-run test command → See changes

## Resume Capability

The Artwork Reviewer fully supports resume from any point:

**Scenario:**

1. Start scanning 4,000 movies
2. Process 500 items
3. Close Kodi or cancel processing
4. Run Artwork Reviewer again later
5. Dialog: "Continue Review (3,500 pending)"
6. Choose to continue from item 501

**Queue Persistence:**

- Queue stored in SQLite database
- Survives Kodi restarts
- Can resume days/weeks/months later

## Troubleshooting

### No Artwork Found

**Problem**: Artwork Reviewer says "No missing artwork found" but you know some is missing.

**Solutions**:

1. Check "Art Types to Check" setting - make sure it includes the types you want
2. Verify the artwork actually exists on scraper sources (TMDB, fanart.tv)
3. Check that your scrapers are configured correctly in Kodi

### API Keys Not Working

**Problem**: Getting errors about API keys or no artwork being found.

**Solutions**:

1. Verify your TMDB API key is entered correctly in Settings → API Keys
2. Verify your fanart.tv API key is entered correctly (if using fanart.tv)
3. Check Kodi log for API error messages

## Advanced Tips

### Custom Art Types

Add custom/rare art types to "Art Types to Check":

```text
poster,fanart,clearlogo,clearart,banner,landscape,keyart,discart,characterart,animatedposter
```

### Clear Queue and Start Fresh

If you want to abandon current queue:

1. Run Artwork Reviewer
2. Choose **Manual Review**
3. When prompted, choose to start a new scan
4. Old queue is cleared and new scan begins

---

[↑ Top](#artwork-review) · [Index](../index.md)
