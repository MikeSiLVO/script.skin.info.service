# Infolabel List

List items built from a numbered set of infolabels, such as a weather forecast's hours or days.

[← Back to Index](../index.md)

---

## Table of Contents

- [Infolabel List](#infolabel-list)

---

## Infolabel List

Returns one list item per index, with each field read from a numbered infolabel. The list ends at the first index whose first field is empty. A field can also be given as a 0-100 value, scaled from the lowest to the highest value in the list, for progress bars.

### Usage

```xml
<content>plugin://script.skin.info.service/?action=infolabel_list&amp;template=Window(Weather).Property(Hourly.{n}.{field})&amp;fields=Time,Temperature,Precipitation,FanartCode&amp;scale=Temperature&amp;reload=$INFO[Weather.LastUpdated]$INFO[Weather.Location]</content>
```

```xml
<control type="progress">
    <info>ListItem.Property(Temperature.Scaled)</info>
</control>
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `template` | Yes | - | Infolabel to read, with `{n}` for the index and `{field}` for the field name |
| `fields` | Yes | - | Comma-separated field names. The first is the item label |
| `from` | No | `1` | First index |
| `to` | No | `100` | Last index |
| `scale` | No | - | Comma-separated fields to add a 0-100 value for. Fields joined with `+` share one range |
| `floor` | No | `0` | Value the lowest entry scales to, 0-100 |
| `reload` | No | - | Any value; a change rebuilds the list |

### Properties

| Property | Description |
|----------|-------------|
| `ListItem.Label` | The first field |
| `ListItem.Property(<field>)` | Each field's value |
| `ListItem.Property(<field>.Scaled)` | 0-100, for each field in `scale` whose value starts with a number |

### Scaling

- The number a value starts with is used and the rest is ignored, so `63°F` reads as 63. `.` and `,` are both read as the decimal point, except before exactly three digits, where they group thousands.
- The lowest value scales to `floor` and the highest to 100. When every value is the same, each scales to halfway between.
- `scale=LowTemperature+HighTemperature` puts both fields on one range, for bars from each day's low to its high:

```xml
<content>plugin://script.skin.info.service/?action=infolabel_list&amp;template=Window(Weather).Property(Daily.{n}.{field})&amp;fields=ShortDay,LowTemperature,HighTemperature&amp;scale=LowTemperature+HighTemperature&amp;reload=$INFO[Weather.LastUpdated]$INFO[Weather.Location]</content>
```

- A progress `<info>` reads the number a value starts with, so `40%` precipitation reads as 40 unscaled.

### Notes

- Items have no action of their own.
- `$INFO[...]` and `$VAR[...]` inside `template` read as empty.
