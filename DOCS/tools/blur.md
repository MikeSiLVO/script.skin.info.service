# Blur Generator

Automatically create blurred images.

[← Back to Index](../index.md)

---

## Service Loop Blur

### Main Library Blur

**Enable and Configure:**

```xml
<!-- Add to skin settings XML -->
<control type="radiobutton" id="100">
    <label>Enable Blur</label>
    <onclick>Skin.ToggleSetting(SkinInfo.Blur)</onclick>
    <selected>Skin.HasSetting(SkinInfo.Blur)</selected>
</control>

<!-- Option 1: Raw InfoLabel (NO $INFO[] wrapper) -->
<onload>SetProperty(SkinInfo.BlurSource,Container.ListItem.Art(fanart),home)</onload>

<!-- Option 2: VAR name for dynamic resolution -->
<onload>SetProperty(SkinInfo.BlurSourceVar,MyFanartVar,home)</onload>
```

**Using a VAR:**

When using `BlurSourceVar`, set the VAR **name** (not `$VAR[]`). The service wraps and resolves it on each poll:

```xml
<!-- In your skin's Includes.xml -->
<variable name="MyFanartVar">
    <value condition="!String.IsEmpty(ListItem.Art(fanart))">$INFO[ListItem.Art(fanart)]</value>
    <value condition="!String.IsEmpty(ListItem.Art(thumb))">$INFO[ListItem.Art(thumb)]</value>
    <value>$INFO[ListItem.Icon]</value>
</variable>

<!-- Set the VAR name -->
<onload>SetProperty(SkinInfo.BlurSourceVar,MyFanartVar,home)</onload>
```

**Fallback Sources:**

Use pipe-separated values to try multiple sources in order. The first non-empty result is used:

```xml
<!-- InfoLabel fallbacks -->
<onload>SetProperty(SkinInfo.BlurSource,ListItem.Art(fanart)|ListItem.Art(thumb)|ListItem.Icon,home)</onload>

<!-- VAR name fallbacks -->
<onload>SetProperty(SkinInfo.BlurSourceVar,FanartVar|ThumbVar|IconVar,home)</onload>
```

**Access Blurred Images:**

```xml
<texture>$INFO[Window(Home).Property(SkinInfo.BlurredImage)]</texture>
<texture>$INFO[Window(Home).Property(SkinInfo.BlurredImage.Original)]</texture>
```

---

### Player Blur (Audio)

```xml
<!-- Add to skin settings XML -->
<control type="radiobutton" id="101">
    <label>Enable Player Blur</label>
    <onclick>Skin.ToggleSetting(SkinInfo.Player.Blur)</onclick>
    <selected>Skin.HasSetting(SkinInfo.Player.Blur)</selected>
</control>

<!-- Option 1: Raw InfoLabel -->
<onload>SetProperty(SkinInfo.Player.BlurSource,Player.Art(thumb),home)</onload>

<!-- Option 2: VAR name -->
<onload>SetProperty(SkinInfo.Player.BlurSourceVar,PlayerArtVar,home)</onload>
```

**Access:**

```xml
<texture>$INFO[Window(Home).Property(SkinInfo.Player.BlurredImage)]</texture>
```

---

### Custom Prefix

Use multiple blur instances simultaneously:

```xml
<onload>SetProperty(SkinInfo.BlurPrefix,Dialog,home)</onload>
<onload>SetProperty(SkinInfo.BlurSource,ListItem.Art(poster),home)</onload>

<texture>$INFO[Window(Home).Property(SkinInfo.Dialog.BlurredImage)]</texture>
```

---

## On-Demand Blur (RunScript)

### Syntax

```text
RunScript(script.skin.info.service,action=blur,source="<infolabel>",prefix=<name>,radius=<value>,window_id=<window>)
```

### Parameters

| Parameter   | Required | Description                     | Default                                  | Quotes Required |
| ----------- | -------- | ------------------------------- | ---------------------------------------- | --------------- |
| `source`    | **Yes**  | Image path or infolabel to blur | -                                        | **Yes**         |
| `prefix`    | No       | Property name prefix            | `Custom`                                 | No              |
| `radius`    | No       | Blur radius (recommended 30-50) | `Skin.String(SkinInfo.BlurRadius)` or 40 | No              |
| `window_id` | No       | Window name or ID               | `home`                                   | No              |

### Examples

**Basic:**

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(poster)")</onclick>
<texture>$INFO[Window(Home).Property(SkinInfo.Custom.BlurredImage)]</texture>
```

**Dialog with Custom Prefix:**

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(fanart)",prefix=movieinfo,window_id=movieinformation)</onclick>
<texture>$INFO[Window(movieinformation).Property(SkinInfo.movieinfo.BlurredImage)]</texture>
```

**Custom Radius:**

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(poster)",radius=25)</onclick>
```

**No Prefix (Same as Service Loop):**

```xml
<onclick>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(fanart)",prefix=)</onclick>
<texture>$INFO[Window(Home).Property(SkinInfo.BlurredImage)]</texture>
```

---

### Window Names

| Window Name        | ID    | Description       |
| ------------------ | ----- | ----------------- |
| `home`             | 10000 | Home window       |
| `movieinformation` | 12003 | Movie info dialog |
| `musicinformation` | 12001 | Music info dialog |
| `skinsettings`     | 10035 | Skin settings     |
| `videos`           | 10025 | Video library     |
| `music`            | 10502 | Music library     |

Numeric IDs also work: `window_id=12003`

---

## Important

### Property Options

| Property | Value | Description |
|----------|-------|-------------|
| `SkinInfo.BlurSource` | Raw InfoLabel(s) | Supports pipe-separated fallbacks |
| `SkinInfo.BlurSourceVar` | VAR name(s) | Supports pipe-separated fallbacks |
| `SkinInfo.Player.BlurSource` | Raw InfoLabel(s) | Supports pipe-separated fallbacks |
| `SkinInfo.Player.BlurSourceVar` | VAR name(s) | Supports pipe-separated fallbacks |

### ⚠️ Do NOT use `$INFO[]` or `$VAR[]` wrappers

✅ **Correct:**

```xml
<onload>SetProperty(SkinInfo.BlurSource,Player.Art(thumb),home)</onload>
<onload>SetProperty(SkinInfo.BlurSourceVar,MyArtVar,home)</onload>
```

❌ **Wrong:**

```xml
<onload>SetProperty(SkinInfo.BlurSource,$INFO[Player.Art(thumb)],home)</onload>
<onload>SetProperty(SkinInfo.BlurSourceVar,$VAR[MyArtVar],home)</onload>
```

---

## Clearing Properties

```xml
<onunload>ClearProperty(SkinInfo.movieinfo.BlurredImage,movieinformation)</onunload>
<onunload>ClearProperty(SkinInfo.movieinfo.BlurredImage.Original,movieinformation)</onunload>
```

---

## Complete Example

```xml
<window type="dialog" id="1101">
    <onload>RunScript(script.skin.info.service,action=blur,source="ListItem.Art(fanart)",prefix=movieinfo,window_id=movieinformation)</onload>
    <onunload>ClearProperty(SkinInfo.movieinfo.BlurredImage,movieinformation)</onunload>
    <onunload>ClearProperty(SkinInfo.movieinfo.BlurredImage.Original,movieinformation)</onunload>

    <controls>
        <control type="image">
            <texture fallback="$INFO[ListItem.Art(fanart)]">$INFO[Window(movieinformation).Property(SkinInfo.movieinfo.BlurredImage)]</texture>
        </control>
    </controls>
</window>
```

---

## Troubleshooting

**Blur not working:**

- Install `script.module.pil`
- Check Kodi log for errors
- **For RunScript:** Always quote the `source` parameter (see examples above)

**Source image not found:**

- Kodi splits RunScript arguments on spaces
- Always use quotes around `source` parameter: `source="ListItem.Art(poster)"`
- Without quotes, paths with spaces will be split incorrectly

**Properties not updating:**

- Don't use `$INFO[]` in `SetProperty()`
- For player blur: Requires `Player.HasAudio`

**Black screen on dialog open:**

```xml
<texture fallback="$INFO[ListItem.Art(fanart)]">$INFO[Window(movieinformation).Property(SkinInfo.movieinfo.BlurredImage)]</texture>
```

---

[↑ Top](#blur-generator) · [Index](../index.md)
