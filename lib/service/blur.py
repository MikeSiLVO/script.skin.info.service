"""Image blur processing module for creating blurred background artwork."""

import hashlib
import os
from typing import Optional

import xbmc
import xbmcvfs

from lib.kodi.client import log, decode_image_url, encode_image_url


PIL_AVAILABLE = None


def _check_pil():
    global PIL_AVAILABLE

    if PIL_AVAILABLE is not None:
        return PIL_AVAILABLE

    try:
        from PIL import Image, ImageFilter  # noqa: F401
        PIL_AVAILABLE = True
        return True
    except ImportError:
        PIL_AVAILABLE = False
        log("Blur", "PIL (Pillow) not available - blur feature will not work", xbmc.LOGWARNING)
        return False


def _get_resize_filter():
    """Compatibility for old and new Pillow versions."""
    try:
        from PIL.Image import Resampling
        return Resampling.NEAREST
    except (ImportError, AttributeError):
        from PIL import Image
        return Image.NEAREST  # type: ignore[attr-defined]


def _get_cache_dir():
    cache_dir = os.path.join(
        xbmcvfs.translatePath("special://profile/addon_data/script.skin.info.service"),
        "blur_cache"
    )

    if not xbmcvfs.exists(cache_dir):
        success = xbmcvfs.mkdirs(cache_dir)
        if not success:
            log("Blur", f"Failed to create blur cache directory: {cache_dir}", xbmc.LOGERROR)
            return None

    return cache_dir


def _url_to_cached_path(url: str) -> Optional[str]:
    """
    Uses xbmc.getCacheThumbName() which handles path normalization
    (e.g., backslash to forward slash on Windows) to match Kodi's behavior exactly.
    """
    if not url:
        return None

    url = decode_image_url(url)

    cache_name = xbmc.getCacheThumbName(url)
    hex_name = cache_name[:-4] if cache_name.endswith('.tbn') else cache_name

    for ext in ['.jpg', '.png']:
        cache_path = xbmcvfs.translatePath(f"special://profile/Thumbnails/{hex_name[0]}/{hex_name}{ext}")
        if xbmcvfs.exists(cache_path):
            return cache_path

    return None


def _generate_cache_key(source_path: str, blur_radius: int) -> str:
    cache_key = f"{source_path}_{blur_radius}"
    hash_value = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    return f"{hash_value}.jpg"


def blur_image(source_path: str, blur_radius: int = 40) -> Optional[str]:
    """
    Create a blurred version of the source image.

    Args:
        source_path: Path to source image or URL (image:// or http(s)://)
        blur_radius: Gaussian blur radius (default 40, recommended 30-50)

    Returns:
        Path to blurred image in cache, or None on failure
    """
    if not source_path:
        return None

    # Resource addon icons can't be resolved via texture cache
    if source_path.startswith('resource://'):
        return None

    cache_dir = _get_cache_dir()
    if cache_dir:
        cache_filename = _generate_cache_key(source_path, blur_radius)
        cache_path = os.path.join(cache_dir, cache_filename)
        if xbmcvfs.exists(cache_path):
            return cache_path

    if not _check_pil():
        return None

    original_path = source_path

    img_bytes = None
    if source_path.startswith(('http://', 'https://', 'image://')):
        local_path = _url_to_cached_path(source_path)

        if not local_path:
            try:
                with xbmcvfs.File(encode_image_url(source_path), 'rb') as f:
                    img_bytes = f.readBytes()

                if not img_bytes:
                    log("Blur", f"Failed to download artwork: {source_path}", xbmc.LOGWARNING)
                    return None

            except Exception as e:
                log("Blur", f"Failed to download artwork: {source_path}: {e}", xbmc.LOGWARNING)
                return None
        else:
            source_path = local_path
    else:
        source_path = xbmcvfs.translatePath(source_path)

    if img_bytes is None and not xbmcvfs.exists(source_path):
        log("Blur", f"Source image does not exist: {source_path}", xbmc.LOGWARNING)
        return None

    if not cache_dir:
        return None

    cache_filename = _generate_cache_key(original_path, blur_radius)
    cache_path = os.path.join(cache_dir, cache_filename)

    try:
        from PIL import Image, ImageFilter
        import io

        if img_bytes is None:
            with xbmcvfs.File(source_path, 'rb') as f:
                img_data = f.readBytes()
        else:
            img_data = img_bytes

        with Image.open(io.BytesIO(img_data)) as img:
            if img.format == 'JPEG':
                img.draft('RGB', (480, 480))

            # JPEG doesn't support transparency
            if img.mode in ("RGBA", "LA", "PA", "P"):
                img = img.convert("RGB")

            img = img.resize((480, 480), _get_resize_filter())

            img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            img.save(xbmcvfs.translatePath(cache_path), "JPEG", quality=70, optimize=False, subsampling=2)

        return cache_path

    except Exception as e:
        log("Blur", f"Failed to blur image {source_path}: {e}", xbmc.LOGERROR)
        return None


