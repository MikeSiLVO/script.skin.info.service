# Texture Cache Manager

Clean and optimize Kodi's image cache.

## What is the Texture Cache?

Kodi stores cached images in `Textures13.db` and the `Thumbnails` folder. When artwork URLs change or library items are deleted, old cached images may remain and waste disk space.

## Usage

Access via Tools menu:

```
RunScript(script.skin.info.service,tools)
```

Then select **Texture Cache Manager** from the menu.

---

## Available Operations

### 1. Pre-Cache Library Artwork

Cache all library artwork URLs that aren't already in the texture cache.

**Benefits:**
- Faster UI browsing (images load instantly)
- Ensures all artwork is locally available
- Useful after bulk artwork updates

**When to use:**
- After bulk artwork updates
- Before going offline (travel, presentations)
- After adding new library items with artwork

### 2. Clean Orphaned Textures

Remove cached textures for artwork no longer in your library.

**Benefits:**
- Reclaim disk space from deleted library items
- Clean up after library reorganization
- Remove old/unused textures

**When to use:**
- After large library reorganization (many items deleted)
- Periodically for maintenance (monthly/quarterly)
- After removing duplicate or incorrect library items

**Safety:**
- Only removes artwork URLs (`image://` and `http`)
- Never removes active library artwork
- Kodi automatically re-caches when needed

---

## Troubleshooting

**Pre-cache reports many failures**
- Check network connectivity to image sources
- Check Kodi log for details
- Some URLs may be invalid or broken

**Cleanup finds no orphaned textures**
- Library is already clean
- No action needed

**Old thumbnails still showing after cleanup**
- Reload skin (Ctrl+R) or restart Kodi
- Navigate to the item to trigger re-cache

**Textures not re-caching after removal**
- Navigate to the item in library to trigger re-cache
- Check network connectivity
- Verify artwork URL is still valid

---

## Debug Logging

Enable detailed logging:

Settings → Advanced → Debug → Enable Debug Output

Check Kodi log for operation details.
