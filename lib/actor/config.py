"""Actor image download configuration and constants."""
import sys

ILLEGAL_CHARS_ALL = "/\\?"
ILLEGAL_CHARS_WINDOWS = ':*"<>|'
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".tbn")
DEFAULT_EXTENSION = ".jpg"


def sanitize_actor_filename(name: str, extension: str = DEFAULT_EXTENSION) -> str:
    """
    Convert actor name to Kodi-compatible filename.

    Matches Kodi's GetSafeFile() behavior from VideoDatabase.cpp.
    """
    filename = name.replace(" ", "_")

    for char in ILLEGAL_CHARS_ALL:
        filename = filename.replace(char, "_")

    if sys.platform == "win32":
        for char in ILLEGAL_CHARS_WINDOWS:
            filename = filename.replace(char, "_")
        filename = filename.rstrip(". ")

    return filename + extension


def upgrade_tmdb_image_url(url: str) -> str:
    """
    Upgrade TMDB image URL to original quality.

    Replaces w185/w300/w500 with original for full resolution.
    """
    if not url or "image.tmdb.org" not in url:
        return url

    for size in ("w45", "w92", "w154", "w185", "w300", "w342", "w500", "w780", "h632"):
        if f"/t/p/{size}/" in url:
            return url.replace(f"/t/p/{size}/", "/t/p/original/")

    return url
