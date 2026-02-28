# Stinger Notifications

Mid-credits and post-credits scene detection with notification during movie playback.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Settings](#settings)
- [Detection Sources](#detection-sources)
- [Window Properties](#window-properties)
- [Notification Customization](#notification-customization)
- [Custom Skin Notification](#custom-skin-notification)

---

## Overview

Detects movies with post-credits scenes (stingers) and notifies near the end of playback. Runs as an independent service controlled by the `stinger_enabled` addon setting — works on any skin without requiring the main skin service.

Supports three stinger types:

| Type | Description |
|------|-------------|
| `during` | Scene embedded within the credits |
| `after` | Scene after credits finish |
| `both` | Scenes during and after credits |

---

## Settings

Enable in addon settings under **Stinger Detection**:

| Setting | Default | Description |
|---------|---------|-------------|
| Enable notifications | Off | Master toggle |
| Minutes before end | 8 | When to show notification (for files without chapters) |
| Notification duration | 4 sec | How long notification displays |

**Timing detection:**
- Uses chapter info if available (triggers on last chapter)
- Falls back to time-based (X minutes before end)

---

## Detection Sources

Stinger data is checked in order:

1. **TMDB keywords** - `duringcreditsstinger`, `aftercreditsstinger`
2. **Kodi library tags** - Same keywords imported from scrapers
3. **Trakt** - `during_credits`, `after_credits` fields (requires Trakt authorization)

All sources are checked shortly after movie playback begins.

---

## Window Properties

Properties set on fullscreen video window (12901) during movie playback:

| Property | Values | Description |
|----------|--------|-------------|
| `SkinInfo.Stinger.Type` | `during`, `after`, `both`, `none` | Stinger type detected |
| `SkinInfo.Stinger.HasDuring` | `true` or empty | Has during-credits scene |
| `SkinInfo.Stinger.HasAfter` | `true` or empty | Has after-credits scene |
| `SkinInfo.Stinger.Source` | `tmdb`, `trakt`, `kodi_tags` | Detection source |
| `SkinInfo.Stinger.ShowNotify` | `true` or empty | Set when notification should display |

### Example Usage

```xml
<!-- Show stinger indicator during playback -->
<control type="image">
    <visible>!String.IsEmpty(Window(fullscreenvideo).Property(SkinInfo.Stinger.Type))</visible>
    <texture>stinger-icon.png</texture>
</control>

<!-- Different icons per type -->
<control type="image">
    <visible>String.IsEqual(Window(fullscreenvideo).Property(SkinInfo.Stinger.Type),both)</visible>
    <texture>stinger-both.png</texture>
</control>
```

---

## Notification Customization

Skinners can customize the default Kodi notification via `Skin.String`:

| Skin.String | Purpose |
|-------------|---------|
| `SkinInfo.Stinger.NotificationIcon` | Custom icon path |
| `SkinInfo.Stinger.Heading` | Custom heading text |
| `SkinInfo.Stinger.MessageDuring` | Message for during-credits |
| `SkinInfo.Stinger.MessageAfter` | Message for after-credits |
| `SkinInfo.Stinger.MessageBoth` | Message for both types |

### Example

```xml
<!-- In skin startup or settings -->
<onclick>Skin.SetString(SkinInfo.Stinger.Heading,Stick Around!)</onclick>
<onclick>Skin.SetString(SkinInfo.Stinger.MessageDuring,There's more in the credits)</onclick>
<onclick>Skin.SetString(SkinInfo.Stinger.MessageAfter,Stay til the very end)</onclick>
<onclick>Skin.SetString(SkinInfo.Stinger.MessageBoth,Bonus scenes during and after credits)</onclick>
```

---

## Custom Skin Notification

Skins can handle notification display entirely, bypassing Kodi's built-in notification.

### Opt-In

Set this skin bool to disable the Kodi notification:

```xml
<onclick>Skin.SetBool(SkinInfo.Stinger.CustomNotification)</onclick>
```

When opted in, the addon only sets window properties. The skin handles display using `SkinInfo.Stinger.ShowNotify`.

### Example Implementation

```xml
<!-- In VideoFullScreen.xml or similar -->
<control type="group">
    <visible>String.IsEqual(Window(fullscreenvideo).Property(SkinInfo.Stinger.ShowNotify),true)</visible>
    <animation effect="fade" start="0" end="100" time="300">Visible</animation>
    <animation effect="fade" start="100" end="0" time="300" delay="5000">Visible</animation>

    <!-- Background -->
    <control type="image">
        <width>400</width>
        <height>120</height>
        <texture border="12">notification-bg.png</texture>
    </control>

    <!-- Icon -->
    <control type="image">
        <left>15</left>
        <top>15</top>
        <width>90</width>
        <height>90</height>
        <texture>$ADDON[script.skin.info.service]/resources/icons/stinger.png</texture>
    </control>

    <!-- Text -->
    <control type="label">
        <left>120</left>
        <top>20</top>
        <label>Post-Credits Scene</label>
        <font>font_heading</font>
    </control>
    <control type="label">
        <left>120</left>
        <top>55</top>
        <label>$INFO[Window(fullscreenvideo).Property(SkinInfo.Stinger.Type)]</label>
    </control>
</control>
```

### Benefits of Custom Display

- Full control over appearance and animation
- Match skin's visual style
- Custom positioning
- Extended information display
- Interactive elements if desired

---

[↑ Top](#stinger-notifications) · [Index](../index.md)
