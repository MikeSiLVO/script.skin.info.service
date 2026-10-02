# Skin Info Service

Window properties and plugin paths for Kodi skins.

---

## Getting Started

| Document                              | Description                 |
|---------------------------------------|-----------------------------|
| [Getting Started](getting-started.md) | Setup and basic integration |

## Service Properties

| Document                               | Description                          |
|----------------------------------------|--------------------------------------|
| [Library Properties](service/library.md) | Focused item metadata and artwork  |
| [Online Properties](service/online.md) | External API data (TMDb, etc.)       |
| [Stinger Notifications](service/stinger.md) | Mid/post-credits scene detection |

## Info Dialogs

| Document                                  | Description                                       |
|-------------------------------------------|---------------------------------------------------|
| [Actor Info Dialog](dialogs/actor-info.md) | TMDB person info with filmography and images     |
| [Video Info Dialog](dialogs/video-info.md) | TMDB movie/TV info with cast, recommendations    |
| [Image Viewer Dialog](dialogs/image-viewer.md) | Full-screen image gallery for any plugin URL |

## Dialog Skinning

Each add-on dialog ships with a default layout. When Estuary is the active skin, the actor info, video info, image viewer and artwork selection dialogs use layouts built from Estuary's own styling instead. A skin replaces any dialog by including an XML file with the same name, and that file always takes priority over the add-on's layouts.

| Dialog              | XML file                                          |
|---------------------|---------------------------------------------------|
| Actor Info          | `script-skin-info-service-DialogActorInfo.xml`    |
| Video Info          | `script-skin-info-service-DialogVideoInfo.xml`    |
| Image Viewer        | `script-skin-info-service-DialogImageViewer.xml`  |
| Artwork Selection   | `script.skin.info.service-ArtworkSelection.xml`   |
| Multi-Art Selection | `script.skin.info.service-MultiArtSelection.xml`  |
| Color Picker        | `script.skin.info.service-ColorPicker.xml`        |

## Plugin Paths

| Document                           | Description                          |
|------------------------------------|--------------------------------------|
| [Library Widgets](plugin/widgets-library.md) | Next Up, Recent, Similar, Recommended, Music |
| [Discovery Widgets](plugin/widgets-discovery.md) | Trending, Popular, Upcoming from TMDB/Trakt |
| [Navigation](plugin/navigation.md) | Letter jump for alphabetical lists   |
| [Cast](plugin/cast.md)             | Cast lists for items and player      |
| [DBID Queries](plugin/dbid.md)     | Fetch full metadata by database or TMDB ID |
| [Online Data](plugin/online.md)    | Ratings and metadata from APIs       |
| [Path Statistics](plugin/stats.md) | Counts and totals for library paths  |
| [Person Info](plugin/person.md)    | Actor/director biography, filmography|

## Tools

The Tools menu opens with `RunScript(script.skin.info.service,action=tools)`. While it is open,
`Window(Home).Property(SkinInfo.ToolsMenuActive)` is `true`.

| Document                                  | Description                       |
|-------------------------------------------|-----------------------------------|
| [Artwork Review](tools/artwork-review.md) | Browse and manage library artwork |
| [Blur](tools/blur.md)                     | Generate blurred images           |
| [Color Picker](tools/color-picker.md)     | RGBA color picker dialog          |
| [Download Artwork](tools/download-artwork.md) | Download artwork and actor images to filesystem |
| [Fix Library IDs](tools/fix-library-ids.md) | Resolve missing IMDb/TMDB/TVDB uniqueids |
| [GIF Scanner](tools/gif-scanner.md)       | Find animated artwork in library  |
| [Metadata Editor](tools/metadata-editor.md) | Edit library item metadata      |
| [Ratings Update](tools/ratings-update.md) | Refresh IMDb/TMDB/Trakt ratings in bulk |
| [Slideshow](tools/slideshow.md)           | Rotating fanart backgrounds       |
| [Sync TV Show Metadata](tools/sync-tvshows.md) | Bulk-fetch online metadata for all TV shows |
| [Texture Cache](tools/texture-cache.md)   | Pre-cache, download, and clean artwork |
| [IMDb Top 250 Update](tools/top250-update.md) | Set Top 250 rank on library items |

## Reference

| Document                            | Description                           |
|-------------------------------------|---------------------------------------|
| [Skin Utilities](skin-utilities.md) | RunScript actions for skin operations |
| [Kodi Settings](kodi-settings.md)   | Expose Kodi settings to skins         |
