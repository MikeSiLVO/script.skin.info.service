# Download Artwork

Download library artwork and actor images to the filesystem.

[← Back to Index](../index.md)

## Context Menu

Right-click a movie, TV show, episode, or season and select **Download Artwork** to download all artwork for that item to local files.

**What gets downloaded:**
- All artwork stored in Kodi's library (poster, fanart, banner, etc.)
- Actor images to the `.actors` folder (movies and TV shows)

**TV Shows:** Downloads artwork for the show, all seasons, and all episodes.

**Actor Images:** Downloaded to a `.actors` folder next to the media file:
- Movies: `.actors` folder in the movie's directory
- TV Shows: `.actors` folder in the show's root directory

Actor filenames follow Kodi's convention (e.g., `Tom_Hanks.jpg`).

## Tools Menu

Access via **Tools > Download Artwork** for bulk operations.

### Download Artwork

Download all library artwork to filesystem files.

| Scope | Description |
|-------|-------------|
| All | All media types |
| Movies | Movies only |
| TV Shows | TV shows with seasons and episodes |
| Music | Music videos |

### View Reports

View results from the last download operation.

## Settings

| Setting | Description |
|---------|-------------|
| When File Already Exists | Skip or overwrite existing files |
| Use Movie Filename Prefix | `Movie-poster.jpg` vs `poster.jpg` |
| Use Music Video Filename Prefix | `Video-poster.jpg` vs `poster.jpg` |
| Include TV Episode Guest Stars | Download guest stars from all episodes (disabled by default) |
| Include Episode Thumbnails | Download episode thumbnails during bulk operations (disabled by default) |

## Notes

- Actor images use the thumbnail URL from Kodi's library (typically from TMDB)
- TMDB image URLs are automatically upgraded to original quality
- Actor images are skipped if no thumbnail URL exists in the library
- Duplicate actor names across items share the same image file

---

[↑ Top](#download-artwork) · [Index](../index.md)
