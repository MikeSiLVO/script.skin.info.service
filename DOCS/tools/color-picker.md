# Color Picker

RGBA slider-based color picker for skin color settings.

[← Back to Index](../index.md)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Usage](#usage)
- [Examples](#examples)
- [Dialog Behavior](#dialog-behavior)
- [Dialog Skinning](#dialog-skinning)
- [Advanced Usage](#advanced-usage)
  - [Custom Back Button Behavior](#custom-back-button-behavior)
- [Use Cases](#use-cases)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)

## Overview

The Color Picker provides a visual interface for selecting and managing colors using a color palette or individual Red, Green, Blue, and Alpha sliders. The dialog is customizable via XML and automatically saves colors to skin settings.

## Features

- **Color Palette** - Visual grid of predefined colors loaded from colors.xml
- **RGBA Sliders** - Individual control over Red, Green, Blue, and Alpha channels
- **Live Preview** - See color changes in real-time as you adjust sliders or select from palette
- **Auto-Save** - Automatically saves to skin settings on OK
- **Reset to Default** - Restore original/default color with one click
- **Custom Back Button Behavior** - Optional onback parameter for advanced navigation control
- **Fully Skinnable** - Customize the entire dialog appearance via XML
- **Estuary Default** - Includes clean default dialog matching Estuary style

---

## Usage

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeLabelColor,default=FF6DB9E5)</onclick>
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `setting` | Yes | Skin setting name to save color to (e.g., `ThemeLabelColor`) |
| `default` | Yes | Default hex color if setting is empty (AARRGGBB format, e.g., `FF6DB9E5`) |
| `colors` | No | Path to custom colors.xml file (defaults to `special://xbmc/system/colors.xml`) |
| `onback` | No | Custom back button behavior - condition-only, action-only, or condition::action (see Advanced Usage) |

### Color Format

Colors must be in **AARRGGBB** format (8 hex characters):

- **AA** - Alpha channel (00 = transparent, FF = opaque)
- **RR** - Red channel (00-FF)
- **GG** - Green channel (00-FF)
- **BB** - Blue channel (00-FF)

**Examples:**

- `FFFF0000` - Opaque red
- `FF00FF00` - Opaque green
- `FF0000FF` - Opaque blue
- `80FFFFFF` - 50% transparent white
- `00000000` - Fully transparent

---

## Examples

### Basic Usage

```xml
<control type="button">
    <label>Theme Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeLabelColor,default=FF6DB9E5)</onclick>
</control>
```

### Multiple Color Settings

```xml
<!-- Primary Theme Color -->
<control type="button">
    <label>Primary Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=PrimaryColor,default=FFFF6DB9)</onclick>
</control>

<!-- Secondary Theme Color -->
<control type="button">
    <label>Secondary Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=SecondaryColor,default=FF6D9BE5)</onclick>
</control>

<!-- Background Color with Transparency -->
<control type="button">
    <label>Background Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=BackgroundColor,default=80000000)</onclick>
</control>
```

### Using Custom Color Palette

```xml
<control type="button">
    <label>Theme Color (Custom Palette)</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeLabelColor,default=FF6DB9E5,colors=special://skin/extras/colors.xml)</onclick>
</control>
```

### Using Saved Colors

After saving via Color Picker, use the color in your skin:

```xml
<variable name="ThemeLabelColor">
    <value condition="!String.IsEmpty(Skin.String(ThemeLabelColor))">$INFO[Skin.String(ThemeLabelColor)]</value>
    <value>FF6DB9E5</value><!-- Fallback default -->
</variable>

<!-- Use in controls -->
<control type="label">
    <textcolor>$VAR[ThemeLabelColor]</textcolor>
</control>

<control type="image">
    <colordiffuse>$VAR[ThemeLabelColor]</colordiffuse>
</control>
```

---

## Dialog Behavior

### Opening Dialog

1. Dialog opens with current color from `Skin.String(setting)`
2. If setting is empty, uses `default` parameter
3. Color palette panel (if present) displays predefined colors from colors.xml
4. Sliders are automatically positioned to reflect current color values

### Adjusting Colors

1. **Palette Selection:** Click colors in panel 300 to select from predefined colors
2. **Slider Adjustment:** Move sliders 100-103 to adjust individual RGBA components
3. Each slider represents 0-100% of that channel (0-255 integer value)
4. Color updates in real-time as sliders move or palette colors are selected

### Saving Changes

**OK Button:**

- Saves merged RGBA hex color to `Skin.String(setting)`
- Closes dialog
- Skin immediately uses new color value

**Cancel Button:**

- Discards all changes
- Closes dialog
- Original color remains unchanged

**Reset Button:**

- Restores sliders to `default` parameter value
- Does NOT save automatically
- Must click OK to save the reset color

**Back Button:**

- Default behavior: Closes dialog and discards changes
- Custom behavior: Use `onback` parameter to execute conditions/actions instead (see Advanced Usage)

---

## Dialog Skinning

### Custom Dialog XML

To customize the Color Picker dialog for your skin, create:

`script.skin.info.service-ColorPicker.xml`

Kodi will automatically use your skin's version if it exists, otherwise falls back to the addon's default.

### Required Control IDs

The following control IDs are required and must exist:

| ID  | Type   | Purpose |
|-----|--------|---------|
| 100 | slider | Red slider (0-100%) |
| 101 | slider | Green slider (0-100%) |
| 102 | slider | Blue slider (0-100%) |
| 103 | slider | Alpha slider (0-100%) |
| 200 | button | OK button (saves and closes) |
| 201 | button | Cancel button (discards and closes) |
| 202 | button | Reset to Default button (restores default color) |
| 203 | button | Enter Hex Code button (manual hex input) - optional |
| 300 | panel  | Color palette panel (displays color grid) - optional |

### Slider Requirements

- **Type:** `slider` or `sliderex`
- **Range:** 0-100 (percentage, automatically converted to 0-255)
- Script uses `getPercent()` to read slider values
- Script uses `setPercent()` to set slider positions

### Panel Requirements

- **Type:** `panel`
- **ID:** 300
- **Must include:** `allowhiddenfocus="true"` attribute
- **ListItem Property:** Each item must have `ListItem.Property(color)` set to AARRGGBB hex value
- Panel is populated by script with colors from colors.xml

### Window Properties

The dialog sets the following window properties on `Window(Home)`:

| Property | Description |
|----------|-------------|
| `SkinInfo.ColorPicker.Preview` | Current color being previewed (AARRGGBB hex) |

### ListItem Properties

Each color palette item has the following property:

| Property | Description |
|----------|-------------|
| `color` | AARRGGBB hex color value (e.g., `FFFF0000` for red) |

### Example Custom Dialog

```xml
<?xml version="1.0" encoding="UTF-8"?>
<window type="dialog">
    <defaultcontrol always="true">300</defaultcontrol>
    <controls>
        <!-- Background -->
        <control type="image">
            <texture>dialogs/dialog-bg.png</texture>
        </control>

        <!-- Color Palette Panel -->
        <control type="panel" id="300">
            <visible allowhiddenfocus="true">String.IsEmpty(Window(Home).Property(SkinInfo.ColorPicker.CustomMode))</visible>
            <ondown>200</ondown>
            <itemlayout width="100" height="100">
                <control type="image">
                    <texture colordiffuse="$INFO[ListItem.Property(color)]">white.png</texture>
                </control>
            </itemlayout>
            <focusedlayout width="100" height="100">
                <control type="image">
                    <texture colordiffuse="$INFO[ListItem.Property(color)]">white.png</texture>
                </control>
            </focusedlayout>
        </control>

        <!-- Sliders Group -->
        <control type="group">
            <visible>!String.IsEmpty(Window(Home).Property(SkinInfo.ColorPicker.CustomMode))</visible>

            <!-- Red Slider -->
            <control type="sliderex" id="100">
                <label>Red</label>
                <textcolor>FFFF0000</textcolor>
                <ondown>101</ondown>
            </control>

            <!-- Green Slider -->
            <control type="sliderex" id="101">
                <label>Green</label>
                <textcolor>FF00FF00</textcolor>
                <onup>100</onup>
                <ondown>102</ondown>
            </control>

            <!-- Blue Slider -->
            <control type="sliderex" id="102">
                <label>Blue</label>
                <textcolor>FF0000FF</textcolor>
                <onup>101</onup>
                <ondown>103</ondown>
            </control>

            <!-- Alpha Slider -->
            <control type="sliderex" id="103">
                <label>Alpha</label>
                <textcolor>FFFFFFFF</textcolor>
                <onup>102</onup>
                <ondown>200</ondown>
            </control>
        </control>

        <!-- Color Preview -->
        <control type="image">
            <texture colordiffuse="$INFO[Window(Home).Property(SkinInfo.ColorPicker.Preview)]">white.png</texture>
        </control>

        <!-- Buttons -->
        <control type="button" id="203">
            <label>Custom</label><!-- Toggle mode -->
        </control>

        <control type="button" id="202">
            <label>409</label><!-- Reset -->
        </control>

        <control type="button" id="200">
            <label>186</label><!-- OK -->
        </control>

        <control type="button" id="201">
            <label>222</label><!-- Cancel -->
        </control>
    </controls>
</window>
```

---

## Advanced Usage

### Custom Back Button Behavior

The `onback` parameter allows you to override the default back button behavior (close and discard) with custom conditions and actions.

#### Syntax

```text
onback=condition::action||condition::action
```

**Separators:**

- `::` - Separates condition from action within a block
- `||` - Separates multiple condition/action blocks
- `;` - Chains multiple actions together

**Evaluation:**

- Blocks are evaluated in order (left to right)
- First block where condition evaluates to `true` executes its action(s) and stops
- If no `::` separator, treated as condition-only (closes dialog if condition is true)
- If `::` with empty condition before it, treated as action-only (always executes, doesn't close)

#### Kodi Condition Operators

You can use standard Kodi boolean operators in conditions:

- `!` - NOT (negation)
- `+` - AND (all conditions must be true)
- `|` - OR (at least one condition must be true)

**Example:** `!Control.IsVisible(300)+String.IsEqual(Skin.String(Mode),Advanced)`

#### Examples

**Condition-only (close if condition is true):**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=Control.IsVisible(300))</onclick>
```

If panel 300 is visible, back button closes dialog. Otherwise, back button does nothing.

**Action-only (always execute, don't close):**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=::Control.SetVisible(300);SetFocus(300))</onclick>
```

Back button always shows panel 300 and focuses it, never closes dialog.

**Conditional action (execute if condition true, don't close):**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=!Control.IsVisible(300)::Control.SetVisible(300);SetFocus(300))</onclick>
```

If panel 300 is hidden, back button shows it and focuses it. If panel 300 is already visible, back button does nothing.

**Multiple blocks with fallback:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=!Control.IsVisible(300)::Control.SetVisible(300);SetFocus(300)||Control.IsVisible(300)::Control.SetHidden(300);SetFocus(100))</onclick>
```

- If panel 300 is hidden: Show panel and focus it
- Else if panel 300 is visible: Hide panel and focus slider 100

**Property-driven behavior:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=String.IsEmpty(Window(Home).Property(MyCustomMode)))</onclick>
```

Back button only closes if `MyCustomMode` property is not set.

**Complex condition with multiple actions:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=!Control.IsVisible(300)+String.IsEqual(Skin.String(ColorMode),Palette)::Control.SetVisible(300);SetFocus(300);Skin.SetString(ColorMode,Custom))</onclick>
```

If panel 300 is hidden AND ColorMode is "Palette", show panel, focus it, and change mode to "Custom".

#### Use Cases

**1. Toggle between palette and sliders:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=!Control.IsVisible(300)::Control.SetVisible(300);SetFocus(300)||Control.IsVisible(300)::Control.SetHidden(300);SetFocus(100))</onclick>
```

**2. Always show palette on back, never close:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=::Control.SetVisible(300);SetFocus(300))</onclick>
```

**3. Conditional close based on skin setting:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=String.IsEqual(Skin.String(AllowColorPickerClose),true))</onclick>
```

**4. Navigate to specific control before closing:**

```xml
<onclick>RunScript(script.skin.info.service,action=colorpicker,setting=ThemeColor,default=FF6DB9E5,onback=Control.IsVisible(300)::Control.SetHidden(300)||!Control.IsVisible(300))</onclick>
```

If palette visible, hide it (and stay open). If palette hidden, close dialog.

---

## Use Cases

### Theme Customization

Allow users to customize theme colors:

```xml
<control type="button">
    <label>Customize Theme Colors</label>
    <onclick>ActivateWindow(1100)</onclick><!-- Settings window -->
</control>

<!-- In settings window -->
<control type="button">
    <label>Primary Color</label>
    <label2>$INFO[Skin.String(PrimaryColor)]</label2>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=PrimaryColor,default=FFFF6DB9)</onclick>
</control>
```

### OSD Color Settings

Customize OSD/player colors:

```xml
<control type="button">
    <label>Progress Bar Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=OSDProgressColor,default=FF00B4FF)</onclick>
</control>

<control type="button">
    <label>OSD Background Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=OSDBackgroundColor,default=E0000000)</onclick>
</control>
```

### Highlight Colors

Customize focus/selection colors:

```xml
<control type="button">
    <label>Highlight Bar Color</label>
    <onclick>RunScript(script.skin.info.service,action=colorpicker,setting=HighlightBarColor,default=FF6DB9E5)</onclick>
</control>
```

---

## Troubleshooting

### Dialog doesn't open

**Check:**

1. Ensure `setting` parameter is provided
2. Verify `default` parameter is 8-character hex (AARRGGBB)
3. Check Kodi log for error messages

### Colors not saving

**Check:**

1. Verify `Skin.String(setting)` is being read in your skin
2. Ensure you clicked OK, not Cancel
3. Check skin setting name matches exactly (case-sensitive)

### Sliders not showing color changes

**Check:**

1. Your custom XML has correct control IDs (100-103)
2. Sliders are type `slider` or `sliderex`
3. Focus is working correctly between controls

### Palette not showing

**Check:**

1. Panel control ID is 300
2. Panel has `allowhiddenfocus="true"` attribute
3. Panel is visible in your custom XML
4. colors.xml file exists at specified path

### Reset button doesn't work

**Check:**

1. Button ID is 202
2. `default` parameter is valid AARRGGBB hex
3. You clicked OK after reset to save changes

### Back button behavior not working

**Check:**

1. Verify `onback` parameter syntax is correct (`::` and `||` separators)
2. Test conditions separately using `Skin.HasSetting()` or other infolabels
3. Check Kodi log for condition evaluation errors
4. Ensure actions are valid Kodi builtins
5. Remember: Condition-only format closes dialog when condition is true
6. Remember: Action-only format (`:action`) never closes dialog

---

## Notes

- Colors are stored as uppercase hex in skin settings (e.g., `FF6DB9E5`)
- Slider values are percentages (0-100) converted to integers (0-255)
- Dialog automatically validates color format before opening
- Panel control 300 is optional and can be omitted if you only want sliders
- Panel control 300 requires `allowhiddenfocus="true"` for proper visibility toggling
- Reset button sets sliders but doesn't auto-save (user must click OK)
- Cancel button discards all changes including resets
- Dialog uses modal window - blocks interaction with rest of Kodi until closed
- Back button default behavior: Closes dialog and discards changes
- Back button custom behavior: Use `onback` parameter to override default (see Advanced Usage)
- `onback` parameter supports Kodi conditions, actions, and boolean operators (`!`, `+`, `|`)
- Preview color property (`SkinInfo.ColorPicker.Preview`) clears after dialog closes

---

[↑ Top](#color-picker) · [Index](../index.md)
