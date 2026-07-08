# 🎬 Skin Info Service

Window properties, plugin paths, and utilities for Kodi skins.

If you find this useful, [buy me a coffee](https://ko-fi.com/mikesilvo) ☕

[![Code checks](https://github.com/MikeSiLVO/script.skin.info.service/actions/workflows/checks.yml/badge.svg)](https://github.com/MikeSiLVO/script.skin.info.service/actions/workflows/checks.yml)
![Kodi Version](https://img.shields.io/badge/Kodi-Omega%2B-blue?logo=kodi)
![Python](https://img.shields.io/badge/Python-3.0%2B-blue?logo=python)

---

## 📖 Overview

Skin Info Service provides:

- **Service Properties** - Window properties updated on focus changes
- **Online Properties** - Ratings and metadata from external APIs
- **Plugin Paths** - Widgets, cast lists, DBID queries, person info
- **Info Dialogs** - Full-screen Actor Info, Video Info, and Image Viewer dialogs
- **Tools** - Blur generator, color picker, artwork reviewer, slideshow, ratings update, IMDb Top 250

---

## 🚀 Quick Start

To enable the Library and Online service monitors, opt in from your skin's Home.xml or startup window:

```xml
<onload>Skin.SetBool(SkinInfo.Service)</onload>
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
| [Stinger Notifications](DOCS/service/stinger.md) | Mid/post-credits scene detection  |

### 🔌 Plugin Paths

| Document                                    | Description                            |
|---------------------------------------------|----------------------------------------|
| [Library Widgets](DOCS/plugin/widgets-library.md) | Next Up, Similar, Recommended, Music |
| [Discovery Widgets](DOCS/plugin/widgets-discovery.md) | Trending, Popular, Upcoming from TMDB/Trakt |
| [Navigation](DOCS/plugin/navigation.md)     | Letter jump for containers             |
| [Cast](DOCS/plugin/cast.md)                 | Cast lists for movies, shows, sets     |
| [DBID Queries](DOCS/plugin/dbid.md)         | Fetch full metadata by database ID     |
| [Online Data](DOCS/plugin/online.md)        | Ratings via plugin container           |
| [Path Statistics](DOCS/plugin/stats.md)     | Counts and totals for library paths    |
| [Person Info](DOCS/plugin/person.md)        | Actor/director biography, filmography  |

### 🎭 Info Dialogs

| Document                                          | Description                                       |
|---------------------------------------------------|---------------------------------------------------|
| [Actor Info](DOCS/dialogs/actor-info.md)          | TMDB person info with filmography and images     |
| [Video Info](DOCS/dialogs/video-info.md)          | TMDB movie/TV info with cast, recommendations    |
| [Image Viewer](DOCS/dialogs/image-viewer.md)      | Full-screen image gallery for any plugin URL     |

### 🛠️ Tools

| Document                                        | Description                        |
|-------------------------------------------------|------------------------------------|
| [Artwork Review](DOCS/tools/artwork-review.md)  | Browse and manage library artwork  |
| [Blur](DOCS/tools/blur.md)                      | Generate blurred background images |
| [Color Picker](DOCS/tools/color-picker.md)      | RGBA color picker dialog           |
| [Download Artwork](DOCS/tools/download-artwork.md) | Download artwork and actor images to filesystem |
| [Fix Library IDs](DOCS/tools/fix-library-ids.md) | Resolve missing IMDb/TMDB/TVDB uniqueids |
| [GIF Scanner](DOCS/tools/gif-scanner.md)        | Find animated artwork in library   |
| [Metadata Editor](DOCS/tools/metadata-editor.md)| Edit library item metadata         |
| [Ratings Update](DOCS/tools/ratings-update.md)  | Refresh IMDb/TMDB/Trakt ratings in bulk |
| [Slideshow](DOCS/tools/slideshow.md)            | Rotating fanart backgrounds        |
| [Texture Cache](DOCS/tools/texture-cache.md)    | Texture database utilities         |
| [IMDb Top 250 Update](DOCS/tools/top250-update.md) | Set Top 250 rank on library items |

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
- Fix Library IDs
- IMDb Top 250 Update

---

[📖 Documentation](DOCS/index.md) ·
[🐛 Report Issues](https://github.com/MikeSiLVO/script.skin.info.service/issues)
