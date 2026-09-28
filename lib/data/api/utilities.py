"""API helpers that import no client, database or HTTP layer."""
from __future__ import annotations

from typing import Optional, Final


TMDB_IMAGE_BASE: Final = "https://image.tmdb.org/t/p"


def decode_key(blob: str) -> str:
    """Decode a built-in provider key."""
    from base64 import b64decode
    return b64decode(blob).decode("ascii")


def tmdb_image_url(path: Optional[str], size: str = "original") -> str:
    """Build a TMDB CDN URL for an image path at one size; empty when there is no path."""
    if not path:
        return ""
    return f"{TMDB_IMAGE_BASE}/{size}{path}"


def is_valid_tmdb_id(tmdb_id: Optional[str]) -> bool:
    """Check if a TMDB ID looks valid (numeric only, reasonable length)."""
    if not tmdb_id:
        return False
    return str(tmdb_id).isdigit() and len(str(tmdb_id)) <= 10
