# Navigation

Container navigation tools for alphabetical jumping.

[← Back to Index](../index.md)

---

## Table of Contents

- [Letter Jump](#letter-jump)

---

## Letter Jump

Returns an A-Z letter list for alphabetical container navigation. Clicking a letter jumps to items starting with that letter using Kodi's native SMS jump actions.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=letter_jump&amp;target=50&amp;reload=$INFO[Container(50).SortOrder]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `target` | Yes | 50 | Container ID to jump in |
| `reload` | No | - | Cache buster - use `$INFO[Container(ID).SortOrder]` to auto-update when sort changes |

### Visibility

Show the letter bar when the target container is sorted alphabetically:

```xml
<visible>Container(50).SortMethod(1) | Container(50).SortMethod(7) | Container(50).SortMethod(10)</visible>
```

**Common sort methods:**

- `1` - Sort by Label (A-Z)
- `4` - Sort by File name
- `7` - Sort by Title
- `10` - Sort by Artist
- `11` - Sort by Album

### Examples

**Basic usage:**

```xml
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=50&amp;reload=$INFO[Container(50).SortOrder]</content>
    <visible>Container(50).SortMethod(1)</visible>
</control>
```

**With variable for multiple views:**

```xml
<variable name="CurrentViewID">
    <value condition="Control.IsVisible(50)">50</value>
    <value condition="Control.IsVisible(51)">51</value>
    <value condition="Control.IsVisible(52)">52</value>
</variable>

<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=$VAR[CurrentViewID]&amp;reload=$INFO[Container($VAR[CurrentViewID]).SortOrder]</content>
    <visible>Container($VAR[CurrentViewID]).SortMethod(1) | Container($VAR[CurrentViewID]).SortMethod(7)</visible>
</control>
```

**Music library:**

```xml
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=500&amp;reload=$INFO[Container(500).SortOrder]</content>
    <visible>Container(500).SortMethod(10) | Container(500).SortMethod(11)</visible>
</control>
```

### Behavior

**Ascending sort (A-Z):**

- Returns: A B C D E F G H I J K L M N O P Q R S T U V W X Y Z #

**Descending sort (Z-A):**

- Returns: Z Y X W V U T S R Q P O N M L K J I H G F E D C B A #

The `#` symbol jumps to items starting with numbers.

### How It Works

Uses Kodi's native SMS jump actions (`jumpsms2` through `jumpsms9`):

- `2` = ABC
- `3` = DEF
- `4` = GHI
- `5` = JKL
- `6` = MNO
- `7` = PQRS
- `8` = TUV
- `9` = WXYZ

Clicking a letter executes the corresponding SMS action repeatedly while checking `ListItem.SortLetter` until it matches the target letter.

The `#` symbol uses `firstpage` or `lastpage` actions depending on sort order.

---

[↑ Top](#navigation) · [Index](../index.md)
