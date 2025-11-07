# Getting Started

Basic setup for integrating Skin Info Service into your skin.

[← Back to Index](index.md)

---

## Table of Contents

- [Overview](#overview)
- [Starting the Service](#starting-the-service)
- [Integration Types](#integration-types)
- [Service Properties](#service-properties)
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

The service must be started via RunScript. Add to any window that loads
early in your skin:

**Home.xml:**

```xml
<onload>RunScript(script.skin.info.service)</onload>
```

**Startup.xml:**

```xml
<onload>RunScript(script.skin.info.service)</onload>
```

**With user toggle:**

```xml
<onload condition="Skin.HasSetting(SkinInfo.Service)">RunScript(script.skin.info.service)</onload>
```

The service runs in the background once started and monitors focused items automatically.

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

See: [Widgets](plugin/widgets.md), [Navigation](plugin/navigation.md),
[Cast](plugin/cast.md), [DBID Queries](plugin/dbid.md)

---

### RunScript Actions

Button-triggered operations.

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(fanart)")</onclick>
```

See: [Blur](tools/blur.md), [Color Picker](tools/color-picker.md), [Skin Utilities](skin-utilities.md)

---

[↑ Top](#getting-started) · [Index](index.md)
