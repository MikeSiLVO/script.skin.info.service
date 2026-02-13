# 🎬 Skin Info Service

Window properties, plugin paths, and utilities for Kodi skins.

If you find this useful, [buy me a coffee](https://ko-fi.com/mikesilvo) ☕

![Kodi Version](https://img.shields.io/badge/Kodi-Omega%2B-blue?logo=kodi)
![Python](https://img.shields.io/badge/Python-3.0%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-GPL--3.0-green)

---

## 📖 Overview

Skin Info Service provides:

- **Service Properties** - Window properties updated on focus changes
- **Online Properties** - Ratings and metadata from external APIs
- **Plugin Paths** - Widgets, cast lists, DBID queries, person info
- **Tools** - Blur generator, color picker, artwork reviewer, slideshow

---

## 🚀 Quick Start

Start the service in your skin's Home.xml or startup window:

```xml
<onload>RunScript(script.skin.info.service)</onload>
```

Access properties via `Window(Home).Property(...)`:

```xml
<label>$INFO[Window(Home).Property(SkinInfo.Movie.Title)]</label>
<texture>$INFO[Window(Home).Property(SkinInfo.Movie.Art(poster))]</texture>
```

See [Getting Started](DOCS/getting-started.md) for setup details.

---

## 📚 Documentation

### 🔧 Service Properties

| Document                                       | Description                         |
|------------------------------------------------|-------------------------------------|
| [Library Properties](DOCS/service/library.md)  | Focused item metadata and artwork   |
| [Online Properties](DOCS/service/online.md)    | TMDb, Trakt, MDBList, OMDb data     |

### 🔌 Plugin Paths

| Document                                    | Description                            |
|---------------------------------------------|----------------------------------------|
| [Widgets](DOCS/plugin/widgets.md)           | Next Up, Similar, Recommended, etc.    |
| [Navigation](DOCS/plugin/navigation.md)     | Letter jump for containers             |
| [Cast](DOCS/plugin/cast.md)                 | Cast lists for movies, shows, sets     |
| [DBID Queries](DOCS/plugin/dbid.md)         | Fetch full metadata by database ID     |
| [Online Data](DOCS/plugin/online.md)        | Ratings via plugin container           |
| [Path Statistics](DOCS/plugin/stats.md)     | Counts and totals for library paths    |
| [Person Info](DOCS/plugin/person.md)        | Actor/director biography, filmography  |

### 🛠️ Tools

| Document                                        | Description                        |
|-------------------------------------------------|------------------------------------|
| [Artwork Review](DOCS/tools/artwork-review.md)  | Browse and manage library artwork  |
| [Blur](DOCS/tools/blur.md)                      | Generate blurred background images |
| [Color Picker](DOCS/tools/color-picker.md)      | RGBA color picker dialog           |
| [GIF Scanner](DOCS/tools/gif-scanner.md)        | Find animated artwork in library   |
| [Metadata Editor](DOCS/tools/metadata-editor.md)| Edit library item metadata         |
| [Slideshow](DOCS/tools/slideshow.md)            | Rotating fanart backgrounds        |
| [Texture Cache](DOCS/tools/texture-cache.md)    | Texture database utilities         |

### 📋 Reference

| Document                                    | Description                           |
|---------------------------------------------|---------------------------------------|
| [Skin Utilities](DOCS/skin-utilities.md)    | RunScript actions for skin operations |
| [Kodi Settings](DOCS/kodi-settings.md)      | Expose Kodi settings to skins         |

---

## 🧰 Tools Menu

Access user tools via:

```xml
<onclick>RunScript(script.skin.info.service,action=tools)</onclick>
```

Available tools:

- Artwork Reviewer
- Ratings Updater
- Animated Art Scanner
- Texture Cache Manager
- Download Artwork to Filesystem

---

## 📄 License

GPL-3.0-only

---

[📖 Documentation](DOCS/index.md) ·
[🐛 Report Issues](https://github.com/MikeSiLVO/script.skin.info.service/issues)
