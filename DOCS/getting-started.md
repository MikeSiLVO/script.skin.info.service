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

## Enabling the Service

Library and Online monitors are skin-opt-in; IMDb and Stinger run if they are enabled in the settings.

To enable both monitors, opt in from your skin:

```xml
<onload>Skin.SetBool(SkinInfo.Service)</onload>
```

### Enabling Library and Online separately

`SkinInfo.Service` enables both monitors together. To run only one, use the
per-monitor bools instead:

```xml
<!-- Library properties only, no online API calls -->
<onload>Skin.SetBool(SkinInfo.Service.Library)</onload>

<!-- Online API properties only -->
<onload>Skin.SetBool(SkinInfo.Service.Online)</onload>
```

A skin that does not read any `SkinInfo.Online.*` / `SkinInfo.MusicVideo.Online.*`
properties should set `SkinInfo.Service.Library` so the online monitor (and its API
calls) never start. Setting `SkinInfo.Service` is equivalent to setting both bools.

### Skin-Dependent vs Independent Services

| Service | Controlled By |
|---------|---------------|
| Library properties | `Skin.HasSetting(SkinInfo.Service)` or `Skin.HasSetting(SkinInfo.Service.Library)` |
| Online API properties | `Skin.HasSetting(SkinInfo.Service)` or `Skin.HasSetting(SkinInfo.Service.Online)` |
| Stinger notifications | "Enable stinger detection" addon setting |
| IMDb auto-update | "IMDb Ratings > Auto-update" addon setting |

Library and online properties require a skin that reads `SkinInfo.*` properties. Stinger notifications and IMDb auto-update run, if enabled, regardless of skin.

## Service Properties

| Property | Description |
|----------|-------------|
| `SkinInfo.Service.Running` | Set to `true` while either the Library or Online service is running, cleared when both stop |
| `SkinInfo.Service.Library.Running` | Set to `true` while the Library service is running |
| `SkinInfo.Service.Online.Running` | Set to `true` while the Online service is running |

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
