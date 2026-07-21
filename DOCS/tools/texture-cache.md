# Texture Cache Manager

Clean and optimize Kodi's image cache.

[← Back to Index](../index.md)

---

## What is the Texture Cache?

Kodi stores cached images in `Textures13.db` and the `Thumbnails` folder.
When artwork URLs change or library items are deleted, old cached images
may remain and waste disk space.

## Usage

Access via Tools menu:

```xml
RunScript(script.skin.info.service,action=tools)
```

Then select **Texture Cache Manager** from the menu.

---

## Available Operations

### 1. Pre-Cache Library Artwork

Cache all library artwork URLs that aren't already in the texture cache.
Nothing is written to your media folders.

### 2. Pre-Cache + Download

Caches the artwork as above, and also saves a copy next to your media so it
survives a texture cache rebuild.

This entry only appears when **Add 'Download' option to missing artwork and
pre-cache** is enabled in Artwork settings.

Choose a scope (all types, or one type at a time). What gets saved where:

| Scope | Saved to |
|-------|----------|
| Movies, Episodes, Music videos | Next to the media file |
| TV Shows | Show folder |
| Seasons | Show folder, as `season01-poster.jpg` and so on |
| Movie sets | Movie Set Information Folder |
| Artists | Artist Information Folder |
| Albums | Album folder (where the album's music files are) |

Artwork an item inherits from its parent (a season showing its show's poster, an
episode showing its season's) is cached, but not written as a file. The parent
already owns that image, and its own scope saves it.

Existing files are handled per the **When File Already Exists** setting in
Artwork settings.

### 3. Clean Orphaned Textures

Remove cached textures for artwork no longer in your library.

Operation:

- Only removes artwork URLs (`image://` and `http`)
- Active library artwork is not removed
- Kodi automatically re-caches when needed

---

## Troubleshooting

### Pre-cache reports many failures

- Check network connectivity to image sources
- Check Kodi log for details
- Some URLs may be invalid or broken

### Nothing downloaded for an album

The album folder comes from the location of the album's songs. An album whose
songs are not on an accessible file path is cached only.

### A run takes a long time

Both operations walk the whole library. Artwork already cached, and files
already on disk, are skipped quickly, so a second run is much faster than the
first. The operation can be cancelled at any point and resumed later.

### Cleanup finds no orphaned textures

- Library is already clean
- No action needed

### Old thumbnails still showing after cleanup

- Reload skin (Ctrl+R) or restart Kodi
- Navigate to the item to trigger re-cache

### Textures not re-caching after removal

- Navigate to the item in library to trigger re-cache
- Check network connectivity
- Verify artwork URL is still valid

---

## Debug Logging

Enable detailed logging:

Settings → Advanced → Debug → Enable Debug Output

Check Kodi log for operation details.

---

[↑ Top](#texture-cache-manager) · [Index](../index.md)
