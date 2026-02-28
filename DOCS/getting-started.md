# Getting Started

Basic setup for integrating Skin Info Service into your skin.

[← Back to Index](index.md)

---

## Table of Contents

- [Overview](#overview)
- [Starting the Service](#starting-the-service)
- [Service Properties](#service-properties)
- [Integration Types](#integration-types)
- [Plugin Paths](#plugin-paths)
- [RunScript Actions](#runscript-actions)

---

## Overview

Skin Info Service provides three integration methods:

1. **Service Properties** - Window properties updated automatically on focus changes
2. **Plugin Paths** - Container content for widgets and lists
3. **RunScript Actions** - On-demand operations triggered by buttons

---

## Starting the Service

The service must be started via RunScript. Add to any window that loads early in your skin:

```xml
<onload>RunScript(script.skin.info.service)</onload>
```

**With user toggle (recommended):**

```xml
<onload condition="Skin.HasSetting(SkinInfo.Service)">RunScript(script.skin.info.service)</onload>
```

The service sets `Skin.SetBool(SkinInfo.Service)` on start and checks it each loop iteration. If the setting is toggled off, the service stops automatically. This allows skins to provide a toggle that both prevents starting and stops a running service.

A duplicate RunScript call is ignored if the service is already running.

### Skin-Dependent vs Independent Services

The RunScript starts multiple services:

| Service | Controlled By |
|---------|---------------|
| Library properties | `Skin.HasSetting(SkinInfo.Service)` |
| Online API properties | Runs with library service |
| Stinger notifications | `stinger_enabled` addon setting |
| IMDb auto-update | `imdb_auto_update` addon setting |

Library and online properties require a skin that reads `SkinInfo.*` properties. Stinger notifications and IMDb auto-update run on any skin based on their own addon settings.

## Service Properties

| Property | Description |
|----------|-------------|
| `SkinInfo.Service.Running` | Set to `true` while the service is running, cleared on stop |

```xml
<visible>!String.IsEmpty(Window(Home).Property(SkinInfo.Service.Running))</visible>
```

---

## Integration Types

### Service Properties

Properties set on the Home window, updated automatically as focus changes.

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Movie.Title)]</label>
<texture>$INFO[Window(Home).Property(SkinInfo.Movie.Art(poster))]</texture>
```

See: [Library Properties](service/library.md), [Online Properties](service/online.md)

---

### Plugin Paths

Content sources for containers.

```xml
<content>plugin://script.skin.info.service/?action=next_up</content>
```

See: [Library Widgets](plugin/widgets-library.md), [Discovery Widgets](plugin/widgets-discovery.md),
[Navigation](plugin/navigation.md), [Cast](plugin/cast.md), [DBID Queries](plugin/dbid.md)

---

### RunScript Actions

Button-triggered operations.

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(fanart)")</onclick>
```

See: [Blur](tools/blur.md), [Color Picker](tools/color-picker.md), [Skin Utilities](skin-utilities.md)

---

[↑ Top](#getting-started) · [Index](index.md)
