# Image Color

The main color of the focused item's image, for tinting highlights or text to match the poster.

[← Back to Index](../index.md)

---

## Enable

Needs the Library service, see [Getting Started](../getting-started.md).

```xml
<control type="radiobutton" id="100">
    <label>Match Poster Colors</label>
    <onclick>Skin.ToggleSetting(SkinInfo.ImageColor)</onclick>
    <selected>Skin.HasSetting(SkinInfo.ImageColor)</selected>
</control>
```

---

## Source Image

`SkinInfo.ImageColorSource` picks the image as a raw infolabel, with pipe-separated fallbacks. The
first non-empty one is used. Unset uses `ListItem.Art(poster)`.

```xml
<onload>SetProperty(SkinInfo.ImageColorSource,ListItem.Art(fanart)|ListItem.Art(poster),home)</onload>
```

Set the infolabel without a `$INFO[]` wrapper, as with `SkinInfo.BlurSource`.

---

## Property

| Property | Description |
|----------|-------------|
| `SkinInfo.ImageColor.Main` | Main color of the image as `FFRRGGBB`. Every color comes out at the same lightness and saturation, light enough for text on a dark background. Empty when the item has no image |

The color changes a moment after focus settles on a new image, and the previous color stays until
then.

```xml
<variable name="HighlightColor">
    <value condition="!String.IsEmpty(Window(Home).Property(SkinInfo.ImageColor.Main))">$INFO[Window(Home).Property(SkinInfo.ImageColor.Main)]</value>
    <value>FF12A0C7</value>
</variable>
```

---

[↑ Top](#image-color) · [Index](../index.md)
