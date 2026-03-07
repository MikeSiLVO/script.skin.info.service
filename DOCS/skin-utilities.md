# Skin Utilities

Utility functions accessible via `RunScript()` for skin integration.

[← Back to Index](index.md)

---

## RunScript Syntax

```xml
RunScript(script.skin.info.service,action=blur,source=...)
RunScript(script.skin.info.service,dialog=select,heading=...)
```

All actions use `action=name` or `dialog=type` syntax.

---

## Table of Contents

- [Dialog Utilities](#dialog-utilities)
  - [dialog=yesno](#dialogyesno)
  - [dialog=yesnocustom](#dialogyesnocustom)
  - [dialog=ok](#dialogok)
  - [dialog=select](#dialogselect)
  - [dialog=multiselect](#dialogmultiselect)
  - [dialog=contextmenu](#dialogcontextmenu)
  - [dialog=input](#dialoginput)
  - [dialog=numeric](#dialognumeric)
  - [dialog=textviewer](#dialogtextviewer)
  - [dialog=notification](#dialognotification)
  - [dialog=browse](#dialogbrowse)
  - [dialog=colorpicker](#dialogcolorpicker)
  - [dialog=progress](#dialogprogress)
- [Container Utilities](#container-utilities)
  - [Move Container Position](#move-container-position)
  - [Aggregate Container Labels](#aggregate-container-labels)
- [Playback Utilities](#playback-utilities)
  - [Play All Items](#play-all-items)
  - [Play Random Item](#play-random-item)
- [Settings Utilities](#settings-utilities)
  - [Get Kodi Setting](#get-kodi-setting)
  - [Set Kodi Setting](#set-kodi-setting)
  - [Toggle Kodi Setting](#toggle-kodi-setting)
  - [Reset Kodi Setting](#reset-kodi-setting)
- [String Utilities](#string-utilities)
  - [Split String](#split-string)
  - [URL Encode String](#url-encode-string)
  - [URL Decode String](#url-decode-string)
- [Math Utilities](#math-utilities)
  - [Math Expression Evaluation](#math-expression-evaluation)
- [Property Utilities](#property-utilities)
  - [Copy Container Item](#copy-container-item)
  - [Refresh Counter](#refresh-counter)
- [File Utilities](#file-utilities)
  - [Check File Exists](#check-file-exists)
- [JSON-RPC Utilities](#json-rpc-utilities)
  - [JSON-RPC Presets](#json-rpc-presets)

---

## Dialog Utilities

Complete set of Kodi dialog wrappers that execute builtins based on user choices. All dialogs work with no parameters for quick skin testing.

### Test Defaults

All dialogs can be called with minimal parameters for testing:

```xml
<onclick>RunScript(script.skin.info.service,dialog=select)</onclick>
<onclick>RunScript(script.skin.info.service,dialog=yesno)</onclick>
```

Default values are used for missing parameters to allow quick testing of dialog styling.

---

### dialog=yesno

Show Yes/No confirmation dialog with custom actions for each button.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=yesno,heading=Delete?,message=Are you sure?,yesaction=RunPlugin(delete),noaction=Notification(Cancelled))</onclick>
```

**Parameters:**

| Parameter       | Required | Default        | Description                                      |
| --------------- | -------- | -------------- | ------------------------------------------------ |
| `heading`       | No       | "Test Dialog"  | Dialog heading                                   |
| `message`       | No       | "Test message" | Dialog message                                   |
| `yesaction`     | No       | -              | Pipe-separated builtins for Yes button           |
| `noaction`      | No       | -              | Pipe-separated builtins for No button            |
| `cancel_action` | No       | -              | Pipe-separated builtins for cancel/ESC/autoclose |
| `yeslabel`      | No       | "Yes"          | Custom Yes button text                           |
| `nolabel`       | No       | "No"           | Custom No button text                            |
| `autoclose`     | No       | 0              | Milliseconds to auto-close                       |

**Builtin Chaining:**

```xml
yesaction=Action1|Action2|Action3
```

---

### dialog=yesnocustom

Show three-button dialog (Yes/No/Custom).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=yesnocustom,heading=Save?,message=What to do?,yesaction=Save,noaction=DontSave,customaction=Cancel,customlabel=Cancel)</onclick>
```

**Parameters:**

Same as yesno, plus:

| Parameter      | Required | Default  | Description                               |
| -------------- | -------- | -------- | ----------------------------------------- |
| `customaction` | No       | -        | Pipe-separated builtins for Custom button |
| `customlabel`  | No       | "Custom" | Custom button text                        |

---

### dialog=ok

Show simple OK acknowledgment dialog.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=ok,heading=Success,message=Item deleted,okaction=Notification(Done))</onclick>
```

**Parameters:**

| Parameter  | Required | Default        | Description                             |
| ---------- | -------- | -------------- | --------------------------------------- |
| `heading`  | No       | "Test Dialog"  | Dialog heading                          |
| `message`  | No       | "Test message" | Dialog message                          |
| `okaction` | No       | -              | Pipe-separated builtins when OK pressed |

---

### dialog=select

Show select dialog with single selection.

**Usage:**

```xml
<!-- Simple string list -->
<onclick>RunScript(script.skin.info.service,dialog=select,heading=Quality,items=SD|HD|4K,executebuiltin=Skin.SetString(Quality,{value}))</onclick>

<!-- Per-index actions -->
<onclick>RunScript(script.skin.info.service,dialog=select,heading=Navigate,items=Movies|TV|Music,executebuiltin_0=ActivateWindow(Videos),executebuiltin_1=ActivateWindow(TVShows),executebuiltin_2=ActivateWindow(Music))</onclick>

<!-- Property mode with icons -->
<onclick>SetProperty(Dialog.1.Label,Movies)</onclick>
<onclick>SetProperty(Dialog.1.Icon,special://skin/icons/movies.png)</onclick>
<onclick>SetProperty(Dialog.2.Label,TV Shows)</onclick>
<onclick>SetProperty(Dialog.2.Icon,special://skin/icons/tv.png)</onclick>
<onclick>RunScript(script.skin.info.service,dialog=select,items=properties,heading=Navigate)</onclick>
```

**Parameters:**

| Parameter                                    | Required | Default                   | Description                                |
| -------------------------------------------- | -------- | ------------------------- | ------------------------------------------ |
| `heading`                                    | No       | "Test Dialog"             | Dialog heading                             |
| `items`                                      | No       | "Option 1\|...\|Option 5" | Pipe-separated items OR "properties"       |
| `separator`                                  | No       | \|                        | Item separator                             |
| `executebuiltin`                             | No       | -                         | Template with {index}/{value} placeholders |
| `executebuiltin_0`, `executebuiltin_1`, etc. | No       | -                         | Per-index actions (override template)      |
| `cancel_action`                              | No       | -                         | Pipe-separated builtins if cancelled       |
| `preselect`                                  | No       | -1                        | Index or value to preselect                |
| `usedetails`                                 | No       | false                     | Use detailed list view                     |
| `autoclose`                                  | No       | 0                         | Milliseconds to auto-close                 |
| `window`                                     | No       | "home"                    | Window for property mode                   |

**Property Mode:**

If `items=properties`, reads window properties:

- `Dialog.1.Label` - Item label (required)
- `Dialog.1.Icon` - Item icon (optional)
- `Dialog.1.Label2` - Secondary label (optional)
- `Dialog.1.Builtin` - Action for this item (overrides executebuiltin)

Properties are auto-cleared after dialog closes.

**Template Placeholders:**

- `{index}` or `{x}` - Selected index (0-based)
- `{value}` or `{v}` - Selected value text

---

### dialog=multiselect

Show multiselect dialog (multiple selections).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=multiselect,heading=Features,items=Feature A|Feature B|Feature C,executebuiltin=Skin.SetString(Feature_{index},{value}))</onclick>
```

**Parameters:**

Same as select. The `executebuiltin` template is executed for **each** selected item.

---

### dialog=contextmenu

Show context menu popup (strings only, no property mode).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=contextmenu,items=Play|Info|Queue,executebuiltin_0=PlayMedia,executebuiltin_1=Info,executebuiltin_2=Queue)</onclick>
```

**Parameters:**

| Parameter                | Required | Default                   | Description                          |
| ------------------------ | -------- | ------------------------- | ------------------------------------ |
| `items`                  | No       | "Option 1\|...\|Option 3" | Pipe-separated items (strings only)  |
| `separator`              | No       | \|                        | Item separator                       |
| `executebuiltin`         | No       | -                         | Template with {index}/{value}        |
| `executebuiltin_0`, etc. | No       | -                         | Per-index actions                    |
| `cancel_action`          | No       | -                         | Pipe-separated builtins if cancelled |

---

### dialog=input

Show text/keyboard input dialog.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=input,heading=Search,type=alphanum,doneaction=RunPlugin(search?q={value}))</onclick>
```

**Parameters:**

| Parameter       | Required | Default       | Description                                                     |
| --------------- | -------- | ------------- | --------------------------------------------------------------- |
| `heading`       | No       | "Test Dialog" | Dialog heading                                                  |
| `type`          | No       | "alphanum"    | Input type (alphanum, numeric, date, time, ipaddress, password) |
| `default`       | No       | -             | Default value                                                   |
| `hidden`        | No       | false         | Hide input (for alphanum type)                                  |
| `doneaction`    | No       | -             | Template with {value} placeholder                               |
| `cancel_action` | No       | -             | Pipe-separated builtins if cancelled                            |
| `autoclose`     | No       | 0             | Milliseconds to auto-close                                      |

---

### dialog=numeric

Show numeric input dialog.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=numeric,heading=Enter,type=0,doneaction=Skin.SetString(Number,{value}))</onclick>
```

**Parameters:**

| Parameter       | Required | Default       | Description                                             |
| --------------- | -------- | ------------- | ------------------------------------------------------- |
| `heading`       | No       | "Test Dialog" | Dialog heading                                          |
| `type`          | No       | 0             | Type: 0=number, 1=date, 2=time, 3=ipaddress, 4=password |
| `default`       | No       | -             | Default value                                           |
| `hidden`        | No       | false         | Hide input (type 0 only)                                |
| `doneaction`    | No       | -             | Template with {value} placeholder                       |
| `cancel_action` | No       | -             | Pipe-separated builtins if cancelled                    |

---

### dialog=textviewer

Show text viewer dialog (read-only scrollable text).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=textviewer,heading=License,text=$INFO[Window.Property(LicenseText)],usemono=true)</onclick>
```

**Parameters:**

| Parameter | Required | Default        | Description                   |
| --------- | -------- | -------------- | ----------------------------- |
| `heading` | No       | "Test Dialog"  | Dialog heading                |
| `text`    | No       | "Test text..." | Text content (supports $INFO) |
| `usemono` | No       | false          | Use monospace font            |

---

### dialog=notification

Show toast notification (non-blocking).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=notification,heading=Success,message=Item deleted,icon=info,time=5000)</onclick>
```

**Parameters:**

| Parameter | Required | Default        | Description                                     |
| --------- | -------- | -------------- | ----------------------------------------------- |
| `heading` | No       | "Test"         | Notification heading                            |
| `message` | No       | "Notification" | Notification message                            |
| `icon`    | No       | "info"         | Icon: "info", "warning", "error", or image path |
| `time`    | No       | 5000           | Display time in milliseconds                    |
| `sound`   | No       | true           | Play sound                                      |

---

### dialog=browse

Show file/folder browser dialog.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=browse,type=image,heading=Choose,shares=pictures,mask=.jpg|.png,doneaction=Skin.SetImage(BG,{value}))</onclick>
```

**Parameters:**

| Parameter       | Required | Default       | Description                                                                     |
| --------------- | -------- | ------------- | ------------------------------------------------------------------------------- |
| `heading`       | No       | "Choose File" | Dialog heading                                                                  |
| `type`          | No       | "file"        | Type: "directory", "file", "image", "writable"                                  |
| `shares`        | No       | ""            | Shares: "programs", "video", "music", "pictures", "files", "games", "local", "" |
| `mask`          | No       | -             | Pipe-separated extensions: ".jpg\|.png"                                         |
| `default`       | No       | -             | Default path                                                                    |
| `multiple`      | No       | false         | Allow multiple selection                                                        |
| `doneaction`    | No       | -             | Template with {value} (called per file if multiple)                             |
| `cancel_action` | No       | -             | Pipe-separated builtins if cancelled                                            |

---

### dialog=colorpicker

Show color picker dialog.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,dialog=colorpicker,heading=Choose,default=FFFF0000,doneaction=Skin.SetString(Color,{value}))</onclick>
```

**Parameters:**

| Parameter       | Required | Default        | Description                          |
| --------------- | -------- | -------------- | ------------------------------------ |
| `heading`       | No       | "Choose Color" | Dialog heading                       |
| `default`       | No       | -              | Default hex color (AARRGGBB)         |
| `doneaction`    | No       | -              | Template with {value} placeholder    |
| `cancel_action` | No       | -              | Pipe-separated builtins if cancelled |

---

### dialog=progress

Show progress dialog that polls window property for progress value.

**Usage:**

```xml
<!-- Long operation sets Window.Property(MyTask.Progress) from 0-100 -->
<onclick>RunScript(script.skin.info.service,dialog=progress,heading=Processing,progress_info=Window.Property(MyTask.Progress))</onclick>
```

**Parameters:**

| Parameter       | Required | Default          | Description                                       |
| --------------- | -------- | ---------------- | ------------------------------------------------- |
| `heading`       | No       | "Progress"       | Dialog heading                                    |
| `message`       | No       | "Please wait..." | Static message                                    |
| `message_info`  | No       | -                | InfoLabel for dynamic message updates             |
| `progress_info` | Yes      | -                | InfoLabel containing progress value (0-max_value) |
| `max_value`     | No       | 100              | Completion target                                 |
| `timeout`       | No       | 200              | Polling cycles before auto-close                  |
| `polling`       | No       | 0.1              | Seconds between polls                             |
| `background`    | No       | false            | Use background progress bar                       |

**Behavior:**

- Polls `progress_info` InfoLabel every `polling` seconds
- Calculates percentage: `progress_info / max_value * 100`
- Closes when progress reaches `max_value` or `timeout` cycles elapsed
- User can cancel foreground dialog (not background)

---

## Container Utilities

### Move Container Position

**RunScript:** `action=container_move`

Move containers to specific positions and execute builtins sequentially.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011)</onclick>
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012|90013)</onclick>
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=50,main_position=$INFO[Window.Property(actor_id)],main_action=Action(select),next_focus=90050)</onclick>
```

**Parameters:**

| Parameter                      | Type   | Description                                                                                                                                                                                                                                   |
| ------------------------------ | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main_focus` (positional 0)    | string | Container ID or pipe-separated list (e.g., `90011\|90012\|90013`)                                                                                                                                                                             |
| `main_position` (positional 1) | string | Target position (1-indexed, same as `Container.CurrentItem`)<br>If None or empty, resets to position 1<br>Supports pipe-separated values for different positions per container<br>Can use InfoLabels (e.g., `$INFO[Window.Property(target)]`) |
| `main_action`                  | string | Builtin(s) to execute after moving each main container<br>Supports pipe-separated values for different actions per container                                                                                                                  |
| `next_focus`                   | string | Container ID(s) to focus after main containers complete<br>Supports conditional focus: `condition::focus_id\|\|condition::focus_id\|\|focus_id`<br>Supports pipe-separated list for unconditional focus                                        |
| `next_position`                | string | Target position for next containers (1-indexed)<br>If None, just focuses without moving<br>Supports pipe-separated values for different positions per container<br>Only works with unconditional `next_focus`                                 |
| `next_action`                  | string | Builtin(s) to execute after focusing/moving each next container<br>Supports pipe-separated values for different actions per container<br>Only works with unconditional `next_focus`                                                           |

**Pipe-Separated Behavior:**

| Type       | Behavior                                                                                                                                                                                               |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Containers | Always pipe-separated (e.g., `90011\|90012\|90013`)                                                                                                                                                    |
| Positions  | If contains `\|`, each position applies to corresponding container by index<br>If no `\|`, same position applies to all containers                                                                     |
| Actions    | If contains `\|`, each action applies to corresponding container by index<br>If no `\|`, same action applies to all containers<br>If fewer actions than containers, remaining containers get no action |

**Execution Order:**

All operations execute sequentially:

1. **Main containers loop:**

   - Move to target position (skipped if already there)
   - Execute main_action[i] (if provided)

2. **Next containers loop:**

   - Focus container
   - Move to target position (if next_position provided)
   - Execute next_action[i] (if provided)

**Examples:**

**Reset single container:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011)</onclick>
```

Result: Container 90011 moves to position 1

---

**Reset multiple containers:**

```xml
<onload>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012|90013)</onload>
```

Result: All three containers move to position 1

---

**Reset with action on each container:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012,main_action=Action(select))</onclick>
```

Result:

1. Container 90011 moves to position 1 → Action(select)
2. Container 90012 moves to position 1 → Action(select)

---

**Different actions per container:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012,main_action=Action(select)|Action(info))</onclick>
```

Result:

1. Container 90011 moves to position 1 → Action(select)
2. Container 90012 moves to position 1 → Action(info)

---

**Move to specific position from window property:**

```xml
<onunload>RunScript(script.skin.info.service,action=container_move,main_focus=50,main_position=$INFO[Window.Property(my_prop)],main_action=Action(select),next_focus=90050)</onunload>
```

Result:

1. Container 50 moves to position specified in `Window.Property(my_prop)` → Action(select)
2. Container 90050 focused (no move)

---

**Move containers to different positions:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012,main_position=5|10)</onclick>
```

Result:

1. Container 90011 moves to position 5
2. Container 90012 moves to position 10

---

**Move main containers, then focus and move next containers:**

```xml
<onclick>RunScript(script.skin.info.service,container_move,main_focus=90011,main_position=5,next_focus=50|60,next_position=10|20,next_action=Action(select))</onclick>
```

Result:

1. Container 90011 moves to position 5
2. Container 50 moves to position 10 → Action(select)
3. Container 60 moves to position 20 → Action(select)

---

**Move to last item using InfoLabel:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011,main_position=$INFO[Container(90011).NumItems])</onclick>
```

Result: Container 90011 moves to last item

---

**Reset multiple with focus change:**

```xml
<onload>RunScript(script.skin.info.service,action=container_move,main_focus=90011|90012|90013,next_focus=90003)</onload>
```

Result:

1. Containers 90011, 90012, 90013 all move to position 1
2. Container 90003 focused

---

**Conditional Focus:**

Focus different containers based on conditions:

```xml
<!-- Inline conditional focus (parameter) -->
<onclick>RunScript(script.skin.info.service,action=container_move,main_focus=90011,next_focus=String.IsEqual(ListItem.Property(item.type),person)::9876||Window.IsActive(Home)::808||90003)</onclick>
```

Format: `condition::focus_id||condition::focus_id||focus_id`

- Blocks separated by `||` are evaluated in order
- `::` separates condition from focus ID
- No `::` means unconditional (always focus)
- First matching condition focuses its control and stops
- `next_position` and `next_action` are ignored in conditional mode

---

**Multi-line Conditional Focus (Properties):**

For complex conditions, use `SkinInfo.CM_Focus.N` properties on home window:

```xml
<onload>SetProperty(SkinInfo.CM_Focus.1,String.IsEqual(ListItem.Property(item.type),person)::9876,home)</onload>
<onload>SetProperty(SkinInfo.CM_Focus.2,Window.IsActive(Home) + String.IsEqual(ListItem.DBTYPE,tvshow)::808,home)</onload>
<onload>SetProperty(SkinInfo.CM_Focus.3,90003,home)</onload>
<onload>RunScript(script.skin.info.service,action=container_move,main_focus=90017|90016|90015)</onload>
```

- Properties auto-clear after use
- Checked only if `next_focus` parameter not provided
- Must be set on `home` window
- Format same as parameter: `condition::focus_id` or just `focus_id`
- If both parameter and properties are set, parameter takes precedence (warning logged)

---

**Notes:**

- All containers process sequentially (not simultaneously)
- Each builtin waits for completion before next executes
- Position indices are 1-based (matching `Container.CurrentItem`)
- Empty position values default to position 1 (reset)
- InfoLabels (e.g., `$INFO[...]`) are automatically resolved
- If targeting position > 1 on a container that's still loading, the position may not be set correctly (items not yet available)

---

### Aggregate Container Labels

**RunScript:** `action=container_labels`

Aggregate unique values from all container items.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=container_labels,container=50,infolabel=Genre)</onclick>
<onclick>RunScript(script.skin.info.service,action=container_labels,container=$INFO[System.CurrentControlId],infolabel=Genre)</onclick>
<onclick>RunScript(script.skin.info.service,action=container_labels,container=50,infolabel=Studio,separator= | ,prefix=AllStudios)</onclick>
```

**Parameters:**

| Parameter                  | Type   | Description                          |
| -------------------------- | ------ | ------------------------------------ |
| `container` (positional 0) | string | Container ID (can use InfoLabel)     |
| `infolabel` (positional 1) | string | InfoLabel to aggregate               |
| `separator`                | string | Join separator (default ` / `)       |
| `prefix`                   | string | Property prefix (default `SkinInfo`) |
| `window`                   | string | Target window (default `home`)       |

**Properties Set:**

- `{prefix}.{infolabel}s` - Aggregated unique values

**Examples:**

```xml
<!-- Get all unique genres from current container -->
<onclick>RunScript(script.skin.info.service,action=container_labels,container=$INFO[System.CurrentControlId],infolabel=Genre)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Genres)]</label> <!-- Action / Comedy / Drama -->
```

---

## Playback Utilities

### Play All Items

**RunScript:** `action=playall`

Play all items from a directory path in order. Auto-detects media type (music vs video).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[ListItem.FolderPath])</onclick>
<onclick>RunScript(script.skin.info.service,action=playall,path=videodb://movies/titles/)</onclick>
<onclick>RunScript(script.skin.info.service,action=playall,path=musicdb://artists/123/)</onclick>
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[Container.FolderPath])</onclick>
```

**Parameters:**

| Parameter             | Type   | Description                                 |
| --------------------- | ------ | ------------------------------------------- |
| `path` (positional 0) | string | Directory path to play (can use InfoLabels) |

**Supported Paths:**

- `videodb://` - Virtual video library paths (movies, TV shows, music videos)
- `musicdb://` - Virtual music library paths (artists, albums, songs)
- `library://video/` - Video library node paths
- `library://music/` - Music library node paths
- `special://` - Special protocol paths (playlists, addons)
- `plugin://` - Plugin directory paths
- File system paths

**Media Type Detection:**

Automatically detects media type from path:

- `musicdb://` or `library://music/` → Uses music playlist (playlistid 0)
- All other paths → Uses video playlist (playlistid 1)

**Behavior:**

1. Detects media type from path prefix
2. Validates directory contains playable items
3. Clears appropriate playlist (music or video)
4. Adds all items from directory recursively
5. Starts playback in order (not shuffled)

**Examples:**

**Video:**

```xml
<!-- Play all movies from ListItem folder -->
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[ListItem.FolderPath])</onclick>

<!-- Play all movies in library -->
<onclick>RunScript(script.skin.info.service,action=playall,path=videodb://movies/titles/)</onclick>

<!-- Play all episodes from TV show -->
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[ListItem.FolderPath])</onclick>

<!-- Play all items from current container -->
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[Container.FolderPath])</onclick>

<!-- Play video smart playlist -->
<onclick>RunScript(script.skin.info.service,action=playall,path=special://profile/playlists/video/ActionMovies.xsp)</onclick>
```

**Music:**

```xml
<!-- Play all songs from artist -->
<onclick>RunScript(script.skin.info.service,action=playall,path=musicdb://artists/123/)</onclick>

<!-- Play all songs from album -->
<onclick>RunScript(script.skin.info.service,action=playall,path=musicdb://albums/456/)</onclick>

<!-- Play all songs from genre -->
<onclick>RunScript(script.skin.info.service,action=playall,path=musicdb://genres/1/)</onclick>

<!-- Play music smart playlist -->
<onclick>RunScript(script.skin.info.service,action=playall,path=special://profile/playlists/music/TopRated.xsp)</onclick>

<!-- Play all music from current folder -->
<onclick>RunScript(script.skin.info.service,action=playall,path=$INFO[Container.FolderPath])</onclick>
```

**Error Handling:**

- Shows notification if path is empty
- Shows notification if directory contains no items
- Uses JSON-RPC for all operations (Kodi handles directory expansion)

---

### Play Random Item

**RunScript:** `action=playrandom`

Play all items from a directory path in random order. Auto-detects media type (music vs video).

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=playrandom,path=$INFO[ListItem.FolderPath])</onclick>
<onclick>RunScript(script.skin.info.service,action=playrandom,path=videodb://movies/genres/28/)</onclick>
<onclick>RunScript(script.skin.info.service,action=playrandom,path=musicdb://artists/123/)</onclick>
<onclick>RunScript(script.skin.info.service,action=playrandom,path=$INFO[Container.FolderPath])</onclick>
```

**Parameters:**

| Parameter             | Type   | Description                                 |
| --------------------- | ------ | ------------------------------------------- |
| `path` (positional 0) | string | Directory path to play (can use InfoLabels) |

**Supported Paths:**

Same as `playall` - any directory path supported by Kodi (video or music).

**Media Type Detection:**

Automatically detects media type from path:

- `musicdb://` or `library://music/` → Uses music playlist (playlistid 0)
- All other paths → Uses video playlist (playlistid 1)

**Behavior:**

1. Detects media type from path prefix
2. Validates directory contains playable items
3. Clears appropriate playlist (music or video)
4. Adds all items from directory recursively
5. Starts playback shuffled

**Examples:**

**Video:**

```xml
<!-- Play random movie from action genre -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=videodb://movies/genres/28/)</onclick>

<!-- Party mode - random episodes from TV show -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=$INFO[ListItem.FolderPath])</onclick>

<!-- Random movies from current folder -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=$INFO[Container.FolderPath])</onclick>

<!-- Random from video smart playlist -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=special://profile/playlists/video/Unwatched.xsp)</onclick>
```

**Music:**

```xml
<!-- Random songs from artist -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=musicdb://artists/123/)</onclick>

<!-- Random songs from album -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=musicdb://albums/456/)</onclick>

<!-- Party shuffle - random songs from genre -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=musicdb://genres/1/)</onclick>

<!-- Random from music smart playlist -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=special://profile/playlists/music/PartyMix.xsp)</onclick>

<!-- Random from current music folder -->
<onclick>RunScript(script.skin.info.service,action=playrandom,path=$INFO[Container.FolderPath])</onclick>
```

**Error Handling:**

- Shows notification if path is empty
- Shows notification if directory contains no items
- Uses JSON-RPC for all operations (Kodi handles directory expansion)

**Notes:**

- Both `playall` and `playrandom` use JSON-RPC Playlist methods
- Auto-detects media type from path (music vs video)
- Kodi handles directory expansion automatically (recursive=true)
- Works with any path type that Kodi can enumerate
- InfoLabels starting with `$` are automatically resolved
- Playlist operations clear existing playlist before adding new items
- Smart playlists (.xsp) supported for both video and music

---

## Settings Utilities

Utilities for manipulating Kodi settings via JSON-RPC. See [kodi-settings.md](kodi-settings.md) for a complete list of available settings.

### Get Kodi Setting

**RunScript:** `action=get_setting`

Get a Kodi setting value and set as window property.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=lookandfeel.skin)</onclick>
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=videoplayer.adjustrefreshrate,prefix=RefreshRate)</onclick>
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=musicplayer.crossfade,prefix=Music,window=home)</onclick>
```

**Parameters:**

| Parameter                | Type   | Description                             |
| ------------------------ | ------ | --------------------------------------- |
| `setting` (positional 0) | string | Setting name (e.g., `lookandfeel.skin`) |
| `prefix`                 | string | Property prefix (default `SkinInfo`)    |
| `window`                 | string | Target window (default `home`)          |

**Properties Set:**

- `{prefix}.Setting.{setting}` - Setting value

**Examples:**

```xml
<!-- Get current skin name (no prefix) -->
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=lookandfeel.skin)</onclick>
<label>Current skin: $INFO[Window(Home).Property(SkinInfo.Setting.lookandfeel.skin)]</label>

<!-- Get video player refresh rate setting with prefix -->
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=videoplayer.adjustrefreshrate,prefix=Video)</onclick>
<label>Refresh rate: $INFO[Window(Home).Property(Video.Setting.videoplayer.adjustrefreshrate)]</label>

<!-- Get multiple settings with different prefixes -->
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=musicplayer.crossfade,prefix=Music)</onclick>
<onclick>RunScript(script.skin.info.service,action=get_setting,setting=videoplayer.seekdelay,prefix=Video)</onclick>
<label>Crossfade: $INFO[Window(Home).Property(Music.Setting.musicplayer.crossfade)]</label>
<label>Seek delay: $INFO[Window(Home).Property(Video.Setting.videoplayer.seekdelay)]</label>
```

---

### Set Kodi Setting

**RunScript:** `action=set_setting`

Set a Kodi setting value with user confirmation.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=screensaver.mode,value=screensaver.xbmc.builtin.dim)</onclick>
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=musicplayer.crossfade,value=5)</onclick>
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=filelists.showhidden,value=true)</onclick>
```

**Parameters:**

| Parameter                | Type            | Description                                       |
| ------------------------ | --------------- | ------------------------------------------------- |
| `setting` (positional 0) | string          | Setting name (e.g., `musicplayer.crossfade`)      |
| `value` (positional 1)   | string/int/bool | New value (automatically converted based on type) |

**Type Conversion:**

| Input Value    | Converted To | Example                                |
| -------------- | ------------ | -------------------------------------- |
| `"true"`       | `True`       | `value=true` → boolean `True`          |
| `"false"`      | `False`      | `value=false` → boolean `False`        |
| Numeric string | `int`        | `value=5` → integer `5`                |
| Other strings  | `str`        | `value=addon.id` → string `"addon.id"` |

**Examples:**

```xml
<!-- Enable hidden files (boolean) -->
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=filelists.showhidden,value=true)</onclick>

<!-- Set crossfade duration (integer) -->
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=musicplayer.crossfade,value=8)</onclick>

<!-- Change screensaver addon (string) -->
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=screensaver.mode,value=screensaver.xbmc.builtin.black)</onclick>

<!-- Set audio language (string) -->
<onclick>RunScript(script.skin.info.service,action=set_setting,setting=locale.audiolanguage,value=en)</onclick>
```

**Notes:**

- User must confirm the change via yes/no dialog
- Values are validated against the setting type by Kodi's JSON-RPC
- Passing wrong type (e.g., string to integer setting) returns error
- See [kodi-settings.md](kodi-settings.md) for setting types

---

### Toggle Kodi Setting

**RunScript:** `action=toggle_setting`

Toggle a boolean Kodi setting with user confirmation.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=filelists.showhidden)</onclick>
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=musicplayer.crossfadealbumtracks)</onclick>
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=videoplayer.usedisplayasclock)</onclick>
```

**Parameters:**

| Parameter                | Type   | Description                                   |
| ------------------------ | ------ | --------------------------------------------- |
| `setting` (positional 0) | string | Setting name (must be a boolean type setting) |

**Examples:**

```xml
<!-- Toggle show hidden files -->
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=filelists.showhidden)</onclick>

<!-- Toggle crossfade album tracks -->
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=musicplayer.crossfadealbumtracks)</onclick>

<!-- Toggle RSS feeds -->
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=lookandfeel.enablerssfeeds)</onclick>

<!-- Toggle video library background update -->
<onclick>RunScript(script.skin.info.service,action=toggle_setting,setting=videolibrary.backgroundupdate)</onclick>
```

**Notes:**

- User must confirm the change via yes/no dialog
- Only works with boolean type settings
- Non-boolean settings fail silently
- See [kodi-settings.md](kodi-settings.md) for boolean settings

---

### Reset Kodi Setting

**RunScript:** `action=reset_setting`

Reset a Kodi setting to its default value with user confirmation.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=musicplayer.crossfade)</onclick>
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=videoplayer.seekdelay)</onclick>
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=lookandfeel.skin)</onclick>
```

**Parameters:**

| Parameter                | Type   | Description                      |
| ------------------------ | ------ | -------------------------------- |
| `setting` (positional 0) | string | Setting name to reset to default |

**Examples:**

```xml
<!-- Reset crossfade to default -->
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=musicplayer.crossfade)</onclick>

<!-- Reset seek delay to default -->
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=videoplayer.seekdelay)</onclick>

<!-- Reset skin zoom to default -->
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=lookandfeel.skinzoom)</onclick>

<!-- Reset multiple settings -->
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=musicplayer.crossfade)</onclick>
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=musicplayer.replaygaintype)</onclick>
<onclick>RunScript(script.skin.info.service,action=reset_setting,setting=musicplayer.visualisation)</onclick>
```

**Notes:**

- User must confirm the reset via yes/no dialog
- Works with all setting types (boolean, integer, string, list, addon, path)
- Default value is defined by Kodi's settings schema
- See [kodi-settings.md](kodi-settings.md) for available settings

---

## String Utilities

### Split String

**RunScript:** `action=split_string`

Split a string into parts and set window properties.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=split_string,string=Red|Green|Blue)</onclick>
<onclick>RunScript(script.skin.info.service,action=split_string,string=$INFO[ListItem.Genre],prefix=Genres)</onclick>
<onclick>RunScript(script.skin.info.service,action=split_string,string=$INFO[Window.Property(MyString)],separator=|,prefix=MyData)</onclick>
```

**Parameters:**

| Parameter                  | Type   | Description                              |
| -------------------------- | ------ | ---------------------------------------- |
| `string` (positional 0)    | string | String to split (can use InfoLabels)     |
| `separator` (positional 1) | string | Delimiter (default `\|`)                 |
| `prefix`                   | string | Property suffix for namespace separation |
| `window`                   | string | Target window (default `home`)           |

**Properties Set:**

- Without prefix: `SkinInfo.Split.Count`, `SkinInfo.Split.1`, `SkinInfo.Split.2`, etc.
- With prefix: `SkinInfo.Split.{prefix}.Count`, `SkinInfo.Split.{prefix}.1`, etc.

**Examples:**

```xml
<!-- Without prefix -->
<onclick>RunScript(script.skin.info.service,action=split_string,string=Action|Comedy|Drama)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Split.1)]</label> <!-- Action -->
<label>$INFO[Window(Home).Property(SkinInfo.Split.Count)]</label> <!-- 3 -->

<!-- With prefix for multiple split operations -->
<onclick>RunScript(script.skin.info.service,action=split_string,string=$INFO[ListItem.Genre],prefix=Genres)</onclick>
<onclick>RunScript(script.skin.info.service,action=split_string,string=$INFO[ListItem.Studio],prefix=Studios)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Split.Genres.1)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Split.Studios.1)]</label>
```

---

### URL Encode String

**RunScript:** `action=urlencode`

URL-encode a string.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=urlencode,string=hello world)</onclick>
<onclick>RunScript(script.skin.info.service,action=urlencode,string=$INFO[ListItem.Label])</onclick>
<onclick>RunScript(script.skin.info.service,action=urlencode,string=$INFO[ListItem.Title],prefix=MovieTitle)</onclick>
```

**Parameters:**

| Parameter               | Type   | Description                              |
| ----------------------- | ------ | ---------------------------------------- |
| `string` (positional 0) | string | String to encode (can use InfoLabels)    |
| `prefix`                | string | Property suffix for namespace separation |
| `window`                | string | Target window (default `home`)           |

**Properties Set:**

- Without prefix: `SkinInfo.Encoded`
- With prefix: `SkinInfo.Encoded.{prefix}`

**Examples:**

```xml
<!-- Without prefix -->
<onclick>RunScript(script.skin.info.service,action=urlencode,string=$INFO[ListItem.Title])</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Encoded)]</label> <!-- hello%20world -->

<!-- With prefix for multiple encoded values -->
<onclick>RunScript(script.skin.info.service,action=urlencode,string=$INFO[ListItem.Title],prefix=Title)</onclick>
<onclick>RunScript(script.skin.info.service,action=urlencode,string=$INFO[ListItem.Plot],prefix=Plot)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Encoded.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Encoded.Plot)]</label>
```

---

### URL Decode String

**RunScript:** `action=urldecode`

URL-decode a string.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=urldecode,string=hello%20world)</onclick>
<onclick>RunScript(script.skin.info.service,action=urldecode,string=$INFO[Window.Property(EncodedData)])</onclick>
<onclick>RunScript(script.skin.info.service,action=urldecode,string=$INFO[Container.ListItem.Property(encoded_param)],prefix=Param)</onclick>
```

**Parameters:**

| Parameter               | Type   | Description                              |
| ----------------------- | ------ | ---------------------------------------- |
| `string` (positional 0) | string | String to decode (can use InfoLabels)    |
| `prefix`                | string | Property suffix for namespace separation |
| `window`                | string | Target window (default `home`)           |

**Properties Set:**

- Without prefix: `SkinInfo.Decoded`
- With prefix: `SkinInfo.Decoded.{prefix}`

**Examples:**

```xml
<!-- Decode URL parameter from plugin -->
<onclick>RunScript(script.skin.info.service,action=urldecode,string=$INFO[Container.ListItem.Property(url_param)])</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Decoded)]</label>

<!-- With prefix for multiple values -->
<onclick>RunScript(script.skin.info.service,action=urldecode,string=$INFO[Window.Property(EncodedQuery)],prefix=Search)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Decoded.Search)]</label>
```

---

## Math Utilities

### Math Expression Evaluation

**RunScript:** `action=math`

Evaluate mathematical expressions safely.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=math,expression=10 + 5)</onclick>
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] * 2)</onclick>
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] / 10,prefix=Pages)</onclick>
```

**Parameters:**

| Parameter                   | Type   | Description                                                              |
| --------------------------- | ------ | ------------------------------------------------------------------------ |
| `expression` (positional 0) | string | Math expression to evaluate (can use InfoLabels that resolve to numbers) |
| `prefix`                    | string | Property suffix for namespace separation                                 |
| `window`                    | string | Target window (default `home`)                                           |

**Properties Set:**

- Without prefix: `SkinInfo.Math.Result`
- With prefix: `SkinInfo.Math.{prefix}.Result`

**Supported Operators:**

| Operator | Description    |
| -------- | -------------- |
| `+`      | Addition       |
| `-`      | Subtraction    |
| `*`      | Multiplication |
| `/`      | Division       |
| `//`     | Floor Division |
| `%`      | Modulo         |
| `**`     | Power          |
| `()`     | Parentheses    |

**InfoLabel Resolution:**

- Automatically resolves `$INFO[...]` and `$VAR[...]` in expressions
- InfoLabels must resolve to numeric values (integers or decimals)
- Valid: `$INFO[Container.NumItems]`, `$INFO[Player.Progress]`, `$INFO[System.CpuUsage]`
- Invalid: `$INFO[ListItem.Title]` (text), `$INFO[ListItem.Genre]` (text)

**Examples:**

**Basic Operations:**

```xml
<!-- Addition and multiplication (follows order of operations: 5 * 2 = 10, then 10 + 10 = 20) -->
<onclick>RunScript(script.skin.info.service,action=math,expression=10 + 5 * 2)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Math.Result)]</label> <!-- 20 -->

<!-- Division: Divide container item count by 10 -->
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] / 10)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Math.Result)]</label>

<!-- Subtraction: Remaining items (100 - current count) -->
<onclick>RunScript(script.skin.info.service,action=math,expression=100 - $INFO[Container.NumItems])</onclick>
```

**Complex Expressions:**

```xml
<!-- Parentheses control order: (items - 1) calculated first, then multiply by 100, then add 50 -->
<onclick>RunScript(script.skin.info.service,action=math,expression=($INFO[Container.NumItems] - 1) * 100 + 50)</onclick>

<!-- Calculate elapsed time in minutes: (progress% / 100) * total duration / 60 -->
<onclick>RunScript(script.skin.info.service,action=math,expression=(($INFO[Player.Progress] / 100) * $INFO[Player.Duration]) / 60,prefix=Elapsed)</onclick>
<label>Elapsed: $INFO[Window(Home).Property(SkinInfo.Math.Elapsed.Result)] minutes</label>
```

**Advanced Operators:**

```xml
<!-- Power: 2 to the power of 8 = 256 -->
<onclick>RunScript(script.skin.info.service,action=math,expression=2 ** 8)</onclick>
<label>Result: $INFO[Window(Home).Property(SkinInfo.Math.Result)]</label> <!-- 256 -->

<!-- Modulo: Get remainder when dividing items by 10 -->
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] % 10)</onclick>

<!-- Floor division: Divide and round down (calculate total pages with 20 items per page) -->
<onclick>RunScript(script.skin.info.service,action=math,expression=($INFO[Container.NumItems] + 19) // 20,prefix=Pages)</onclick>
<label>Pages: $INFO[Window(Home).Property(SkinInfo.Math.Pages.Result)]</label>
```

**Multiple Calculations with Prefixes:**

```xml
<!-- Calculate multiple values simultaneously using different prefixes -->
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] * 2,prefix=Double)</onclick>
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] / 2,prefix=Half)</onclick>
<onclick>RunScript(script.skin.info.service,action=math,expression=$INFO[Container.NumItems] ** 2,prefix=Squared)</onclick>

<label>Double: $INFO[Window(Home).Property(SkinInfo.Math.Double.Result)]</label>
<label>Half: $INFO[Window(Home).Property(SkinInfo.Math.Half.Result)]</label>
<label>Squared: $INFO[Window(Home).Property(SkinInfo.Math.Squared.Result)]</label>
```

---

## Property Utilities

### Copy Container Item

**RunScript:** `action=copy_item`

Copy container item properties to window properties.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=copy_item,container=50,infolabels=Title|Year)</onclick>
<onclick>RunScript(script.skin.info.service,action=copy_item,container=$INFO[System.CurrentControlId],infolabels=Title|Plot)</onclick>
<onclick>RunScript(script.skin.info.service,action=copy_item,container=$INFO[System.CurrentControlId],artwork=poster|fanart,prefix=MyItem)</onclick>
```

**Parameters:**

| Parameter                  | Type   | Description                              |
| -------------------------- | ------ | ---------------------------------------- |
| `container` (positional 0) | string | Container ID (can use InfoLabels)        |
| `infolabels`               | string | Pipe-separated InfoLabels to copy        |
| `artwork`                  | string | Pipe-separated art types to copy         |
| `prefix`                   | string | Property suffix for namespace separation |
| `window`                   | string | Target window (default `home`)           |

**Properties Set:**

- Without prefix: `SkinInfo.Selected.{InfoLabel}`, `SkinInfo.Selected.Art({type})`
- With prefix: `SkinInfo.Selected.{prefix}.{InfoLabel}`, `SkinInfo.Selected.{prefix}.Art({type})`

**Examples:**

```xml
<!-- Copy from current focused container (no prefix) -->
<onclick>RunScript(script.skin.info.service,action=copy_item,container=$INFO[System.CurrentControlId],infolabels=Title|Year|Rating,artwork=poster)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Selected.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Selected.Year)]</label>
<texture>$INFO[Window(Home).Property(SkinInfo.Selected.Art(poster))]</texture>

<!-- With prefix for multiple container selections -->
<onclick>RunScript(script.skin.info.service,action=copy_item,container=50,infolabels=Title|Year,prefix=Widget1)</onclick>
<onclick>RunScript(script.skin.info.service,action=copy_item,container=51,infolabels=Title|Year,prefix=Widget2)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.Selected.Widget1.Title)]</label>
<label>$INFO[Window(Home).Property(SkinInfo.Selected.Widget2.Title)]</label>
```

---

### Refresh Counter

**RunScript:** `action=refresh_counter`

Increment a counter for widget refresh triggers.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=MyWidget)</onclick>
<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=$INFO[Container.FolderName])</onclick>
<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=Widget,prefix=Counter)</onclick>
```

**Parameters:**

| Parameter            | Type   | Description                           |
| -------------------- | ------ | ------------------------------------- |
| `uid` (positional 0) | string | Unique identifier (can use InfoLabel) |
| `prefix`             | string | Property prefix (default `SkinInfo`)  |

**Properties Set:**

- `{prefix}.{uid}` - Incremented counter value

**Examples:**

```xml
<!-- Button to refresh widget with static UID -->
<onclick>RunScript(script.skin.info.service,action=refresh_counter,uid=MyWidget)</onclick>

<!-- Widget URL with refresh parameter -->
<content>plugin://plugin.video.example/?action=list&amp;refresh=$INFO[Window(Home).Property(SkinInfo.MyWidget)]</content>
```

Each click increments the counter, changing the URL and triggering a widget reload.

---

## File Utilities

### Check File Exists

**RunScript:** `action=file_exists`

Check if files exist and return first match.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=special://skin/extras/file.txt)</onclick>
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=$INFO[Skin.String(CustomIconPath)]|special://skin/extras/default.png)</onclick>
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=$INFO[Skin.String(CustomBG)]|special://skin/extras/default.jpg,prefix=Background)</onclick>
```

**Parameters:**

| Parameter              | Type   | Description                                    |
| ---------------------- | ------ | ---------------------------------------------- |
| `paths` (positional 0) | string | Pipe-separated file paths (can use InfoLabels) |
| `separator`            | string | Path delimiter (default `\|`)                  |
| `prefix`               | string | Property suffix for namespace separation       |
| `window`               | string | Target window (default `home`)                 |

**Properties Set:**

- Without prefix: `SkinInfo.File.Exists`, `SkinInfo.File.Path`
- With prefix: `SkinInfo.File.{prefix}.Exists`, `SkinInfo.File.{prefix}.Path`

**Examples:**

```xml
<!-- Check custom skin setting path first, fallback to default (no prefix) -->
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=$INFO[Skin.String(UserIcon)]|special://skin/extras/default.png)</onclick>
<visible>String.IsEqual(Window(Home).Property(SkinInfo.File.Exists),true)</visible>
<texture>$INFO[Window(Home).Property(SkinInfo.File.Path)]</texture>

<!-- With prefix for multiple file checks -->
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=$INFO[Skin.String(CustomIcon)]|special://skin/icons/default.png,prefix=Icon)</onclick>
<onclick>RunScript(script.skin.info.service,action=file_exists,paths=$INFO[Skin.String(CustomBG)]|special://skin/backgrounds/default.jpg,prefix=BG)</onclick>
<texture>$INFO[Window(Home).Property(SkinInfo.File.Icon.Path)]</texture>
<texture>$INFO[Window(Home).Property(SkinInfo.File.BG.Path)]</texture>
```

---

## JSON-RPC Utilities

### JSON-RPC Presets

**RunScript:** `action=json`

Execute JSON-RPC preset(s) and set window properties.

**Usage:**

```xml
<onclick>RunScript(script.skin.info.service,action=json,presets=player_info)</onclick>
<onclick>RunScript(script.skin.info.service,action=json,presets=system_info|app_info)</onclick>
```

**Parameters:**

| Parameter                | Type   | Description                 |
| ------------------------ | ------ | --------------------------- |
| `presets` (positional 0) | string | Pipe-separated preset names |

**Available Presets:**

#### player_info

Gets active player properties.

**Properties Set:**

- `SkinInfo.Player.time.hours`
- `SkinInfo.Player.time.minutes`
- `SkinInfo.Player.time.seconds`
- `SkinInfo.Player.totaltime.*`
- `SkinInfo.Player.speed`
- `SkinInfo.Player.percentage`

---

#### system_info

Gets system capabilities.

**Properties Set:**

- `SkinInfo.System.canhibernate`
- `SkinInfo.System.cansuspend`
- `SkinInfo.System.canreboot`
- `SkinInfo.System.canshutdown`

---

#### app_info

Gets application information.

**Properties Set:**

- `SkinInfo.App.volume`
- `SkinInfo.App.muted`
- `SkinInfo.App.name`
- `SkinInfo.App.version.major`
- `SkinInfo.App.version.minor`
- `SkinInfo.App.version.revision`

**Examples:**

```xml
<onclick>RunScript(script.skin.info.service,action=json,presets=app_info)</onclick>
<label>$INFO[Window(Home).Property(SkinInfo.App.name)]</label> <!-- Kodi -->
<label>Volume: $INFO[Window(Home).Property(SkinInfo.App.volume)]</label>
```

---

## Automatic Refresh Properties

The service provides automatic refresh properties for widget auto-reload.

### Library Refresh

`Window(Home).Property(SkinInfo.Library.Refreshed)` - Auto-increments when video library updates

**Triggers:**

- `VideoLibrary.OnUpdate` - Item added/removed, playcount changed, resume point updated
- `VideoLibrary.OnScanFinished` - Library scan completed

**Usage:**

```xml
<!-- Auto-refresh on library changes -->
<content>plugin://script.skin.info.service/?action=next_up&amp;refresh=$INFO[Window(Home).Property(SkinInfo.Library.Refreshed)]</content>
```

### Scheduled Refresh

Auto-increment properties on fixed time intervals for periodic widget refresh.

**Available Intervals:**

| Property                 | Interval   | Use Case                                |
| ------------------------ | ---------- | --------------------------------------- |
| `SkinInfo.Refresh.5min`  | 5 minutes  | Very frequent updates (news, live data) |
| `SkinInfo.Refresh.10min` | 10 minutes | Quick refresh cycles                    |
| `SkinInfo.Refresh.15min` | 15 minutes | Quarter hour updates                    |
| `SkinInfo.Refresh.20min` | 20 minutes | Short content rotation                  |
| `SkinInfo.Refresh.30min` | 30 minutes | Half hour updates                       |
| `SkinInfo.Refresh.45min` | 45 minutes | Three-quarter hour updates              |
| `SkinInfo.Refresh.60min` | 60 minutes | Hourly updates                          |

**Usage:**

```xml
<!-- Random widget - new selection every 15 minutes -->
<content>plugin://script.skin.info.service/?action=wrap&amp;path=special://profile/playlists/video/RandomActionMovies.xsp&amp;reload=$INFO[Window(Home).Property(SkinInfo.Refresh.15min)]</content>
```

**Notes:**

- Timers start when service starts
- Properties increment based on elapsed time, not absolute time
- All scheduled refresh properties are independent

---

## Notes

- All utilities support both positional and named arguments
- InfoLabels starting with `$` are automatically resolved
- Empty input clears properties (where applicable)

---

[↑ Top](#skin-utilities) · [Index](index.md)
