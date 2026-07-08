# Navigation

Container navigation tools for alphabetical jumping.

[← Back to Index](../index.md)

---

## Table of Contents

- [Letter Jump](#letter-jump)

---

## Letter Jump

Returns an A-Z (plus `#`) letter list for jumping around an alphabetical list. Clicking a letter jumps to the items that start with it, using Kodi's built-in SMS jump actions. It can also flag the letters that have no items, so skins can style or hide them, or drop those letters with `showall=false`.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=letter_jump&amp;target=50&amp;reload=$INFO[Container(50).NumItems]$INFO[Container(50).SortMethod]$INFO[Container(50).SortOrder]$INFO[Container(50).FolderPath]</content>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `target` | Yes | 50 | Container ID to jump in |
| `available` | No | false | `true` flags letters with no matching item (`IsNotAvailable`); those letters can't be jumped to. Off by default so a plain bar costs nothing |
| `showall` | No | true | `false` drops letters with no items (compact bar); turns `available` on |
| `reload` | No | - | A value that forces the bar to rebuild when the target's content or sort changes. See below |

### The reload value

The letter bar is a separate container from the one it navigates, so Kodi does not rebuild it when you browse the target to a different folder. Give `reload` a value that changes whenever the target's content or sort changes, so the bar (and `IsNotAvailable`) keeps up:

```
reload=$INFO[Container(50).NumItems]$INFO[Container(50).SortMethod]$INFO[Container(50).SortOrder]$INFO[Container(50).FolderPath]
```

- `NumItems` catches filtering
- `SortMethod` catches a change of sort field (which letter each item falls under)
- `SortOrder` catches ascending/descending (the bar reverses)
- `FolderPath` catches folder navigation

Keep `reload` as the last parameter. A folder path can contain special characters, and placing it last keeps `action` and `target` working.

`SortOrder` alone (the old advice) only reacts to the ascending/descending flip, so the bar goes stale the moment you change folders. Use the full value above, especially with `available`.

### Visibility

Show the letter bar only when the target is sorted alphabetically. Compare the current sort method to its localized label, which is stable across Kodi versions:

```xml
<visible>String.IsEqual(Container.SortMethod,$LOCALIZE[551]) | String.IsEqual(Container.SortMethod,$LOCALIZE[556]) | String.IsEqual(Container.SortMethod,$LOCALIZE[557]) | String.IsEqual(Container.SortMethod,$LOCALIZE[558]) | String.IsEqual(Container.SortMethod,$LOCALIZE[561])</visible>
```

- `551` Name, `556` Title, `557` Artist, `558` Album, `561` File

`SortMethod` belongs to the window, so `Container.SortMethod` with no ID reflects the active view's sort. Under a non-alphabetical sort the sort letters are meaningless and everything falls under `#`.

The numeric `Container(50).SortMethod(N)` also works, but `N` is an internal sort-method number and those shift between Kodi versions (e.g. Album is 12, not 11), so the label comparison above is safer.

### Highlighting the current letter

Do this skin-side, not through the plugin. It needs no reload and updates instantly as you scroll the target list. Compare each bar letter to the target's focused sort letter:

```xml
<control type="label">
    <label>$INFO[ListItem.Label]</label>
    <visible>String.IsEqual(ListItem.Label,Container(50).ListItem.SortLetter)</visible>
    <textcolor>...</textcolor>
</control>
```

Write it bare, with no `$INFO[...]` around the second part. Only the second part is looked up against `Container(50)`, so the order matters (`ListItem.Label` first).

If instead the bar itself has focus (the user is arrowing through it directly), style the control's `<focusedlayout>` - the two are independent.

The `#` cell cannot be matched this way, because a numeric item's sort letter is the digit, not `#`. If you need it highlighted, overlay a window-level control on the `#` cell's fixed position with `<visible>Integer.IsGreater(Container(50).ListItem.SortLetter,0)</visible>`; that condition works only outside the bar's item layout.

### Examples

**Basic usage:**

```xml
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=50&amp;reload=$INFO[Container(50).NumItems]$INFO[Container(50).SortMethod]$INFO[Container(50).SortOrder]$INFO[Container(50).FolderPath]</content>
    <visible>Container(50).SortMethod(1)</visible>
</control>
```

**Flagging empty letters:**

```xml
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=50&amp;available=true&amp;reload=$INFO[Container(50).NumItems]$INFO[Container(50).SortMethod]$INFO[Container(50).SortOrder]$INFO[Container(50).FolderPath]</content>
    <visible>Container(50).SortMethod(1)</visible>
</control>
```

**With a variable for multiple views:**

```xml
<variable name="CurrentViewID">
    <value condition="Control.IsVisible(50)">50</value>
    <value condition="Control.IsVisible(51)">51</value>
    <value condition="Control.IsVisible(52)">52</value>
</variable>

<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=$VAR[CurrentViewID]&amp;reload=$INFO[Container($VAR[CurrentViewID]).NumItems]$INFO[Container($VAR[CurrentViewID]).SortMethod]$INFO[Container($VAR[CurrentViewID]).SortOrder]$INFO[Container($VAR[CurrentViewID]).FolderPath]</content>
    <visible>Container($VAR[CurrentViewID]).SortMethod(1) | Container($VAR[CurrentViewID]).SortMethod(7)</visible>
</control>
```

**Music library:**

```xml
<control type="list" id="9000">
    <content>plugin://script.skin.info.service/?action=letter_jump&amp;target=500&amp;reload=$INFO[Container(500).NumItems]$INFO[Container(500).SortMethod]$INFO[Container(500).SortOrder]$INFO[Container(500).FolderPath]</content>
    <visible>String.IsEqual(Container.SortMethod,$LOCALIZE[557]) | String.IsEqual(Container.SortMethod,$LOCALIZE[558])</visible>
</control>
```

### Behavior

**Ascending sort (A-Z):**

- Returns: A B C D E F G H I J K L M N O P Q R S T U V W X Y Z #

**Descending sort (Z-A):**

- Returns: Z Y X W V U T S R Q P O N M L K J I H G F E D C B A #

The `#` cell jumps to items starting with a number or symbol.

Accented letters fold to their base letter (`École` → E), matching where the item sorts and where the jump lands. Non-Latin scripts (Cyrillic, CJK) have no cell of their own and fall under `#`.

### Item Properties

| Property | Description |
|----------|-------------|
| `IsNotAvailable` | Set on letters with no matching item. These letters can't be jumped to, so clicking one does nothing. Only present when `available=true` (or `showall=false`) |

The property just marks which letters have no matching item. The skin decides what to do with it.

Or drop the empty letters entirely with `showall=false` so the bar only shows letters that have items.

On very large containers (roughly 10,000+ items) the check is skipped and every letter shows as available, so `IsNotAvailable` won't appear there.

To hide the bar when few letters are worth jumping to, use `showall=false` and base the bar's visibility on its own item count (the bar then holds only the available letters):

```xml
<visible>Integer.IsGreater(Container(9000).NumItems,2)</visible>
```

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

Clicking a letter executes the corresponding SMS action repeatedly until the container's sort letter matches the target.

The `#` symbol uses `firstpage` or `lastpage` depending on sort order.

---

[↑ Top](#navigation) · [Index](../index.md)
