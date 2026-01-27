"""Texture cache statistics calculation and formatting."""
from __future__ import annotations

import os
import xbmc
import xbmcgui
import xbmcvfs
from datetime import datetime
from typing import Optional, Dict, Any

from lib.kodi.client import log, ADDON
from lib.texture.utilities import is_library_artwork_url


def calculate_texture_statistics(
    textures: list[Dict[str, Any]],
    progress: xbmcgui.DialogProgress
) -> Optional[Dict[str, Any]]:
    """
    Calculate comprehensive texture cache statistics.

    Args:
        textures: List of texture records from get_cached_textures()
        progress: Progress dialog for user feedback

    Returns:
        Dict with statistics or None if cancelled/failed
    """
    try:
        if not textures:
            return None

        total_textures = len(textures)
        total_sizes = 0
        age_buckets = {'0-7': 0, '8-30': 0, '31-90': 0, '91-180': 0, '180+': 0, 'unknown': 0}
        usage_buckets = {'0': 0, '1-5': 0, '6-20': 0, '21-50': 0, '50+': 0}
        type_breakdown = {'library': 0, 'video_thumb': 0, 'music': 0, 'other': 0}

        now = datetime.now()
        thumbnails_path = xbmcvfs.translatePath("special://thumbnails")
        disk_usage = 0

        progress.update(30, ADDON.getLocalizedString(32332).format(total_textures))

        for i, texture in enumerate(textures):
            if progress.iscanceled():
                return None

            if i % 100 == 0:
                progress.update(30 + int((i / total_textures) * 50))

            sizes = texture.get('sizes', [])
            total_sizes += len(sizes)

            url = texture.get('url', '')

            if is_library_artwork_url(url):
                type_breakdown['library'] += 1
            elif 'video@' in url:
                type_breakdown['video_thumb'] += 1
            elif 'music@' in url or 'musicdb://' in url:
                type_breakdown['music'] += 1
            else:
                type_breakdown['other'] += 1

            for size in sizes:
                lastusetime = size.get('lastusetime')
                raw_usecount = size.get('usecount', 0)
                raw_width = size.get('width', 0)

                # Workaround for Kodi bug: width/usecount fields swapped
                # https://github.com/xbmc/xbmc/pull/27584
                if raw_width < 256 and raw_usecount >= 256:
                    usecount = raw_width
                else:
                    usecount = raw_usecount

                if lastusetime:
                    try:
                        last_used = datetime.strptime(lastusetime, '%Y-%m-%d %H:%M:%S')
                        days_ago = (now - last_used).days

                        if days_ago <= 7:
                            age_buckets['0-7'] += 1
                        elif days_ago <= 30:
                            age_buckets['8-30'] += 1
                        elif days_ago <= 90:
                            age_buckets['31-90'] += 1
                        elif days_ago <= 180:
                            age_buckets['91-180'] += 1
                        else:
                            age_buckets['180+'] += 1
                    except Exception:
                        age_buckets['unknown'] += 1
                else:
                    age_buckets['unknown'] += 1

                if usecount == 0:
                    usage_buckets['0'] += 1
                elif usecount <= 5:
                    usage_buckets['1-5'] += 1
                elif usecount <= 20:
                    usage_buckets['6-20'] += 1
                elif usecount <= 50:
                    usage_buckets['21-50'] += 1
                else:
                    usage_buckets['50+'] += 1

        progress.update(80, ADDON.getLocalizedString(32425))

        try:
            for root, dirs, files in os.walk(thumbnails_path):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        disk_usage += os.path.getsize(filepath)
                    except Exception:
                        pass
        except Exception as e:
            log("Texture",f"SkinInfo TextureCache: Disk usage calculation failed: {str(e)}", xbmc.LOGWARNING)

        progress.update(100, ADDON.getLocalizedString(32426))

        return {
            'total_textures': total_textures,
            'total_sizes': total_sizes,
            'disk_usage': disk_usage,
            'age_buckets': age_buckets,
            'usage_buckets': usage_buckets,
            'type_breakdown': type_breakdown
        }

    except Exception as e:
        log("Texture",f"Statistics calculation failed: {str(e)}", xbmc.LOGERROR)
        return None


def format_statistics_report(stats: Dict[str, Any]) -> str:
    """
    Format statistics into readable report.

    Args:
        stats: Statistics dict from calculate_texture_statistics()

    Returns:
        Formatted report string
    """
    total_textures = stats['total_textures']
    total_sizes = stats['total_sizes']
    disk_usage = stats['disk_usage']
    age_buckets = stats['age_buckets']
    usage_buckets = stats['usage_buckets']
    type_breakdown = stats['type_breakdown']

    disk_gb = disk_usage / (1024 ** 3)
    disk_mb = disk_usage / (1024 ** 2)

    lines = [
        "=" * 50,
        "   TEXTURE CACHE STATISTICS",
        "=" * 50,
        "",
        "OVERVIEW",
        "-" * 50,
        f"Total Textures:      {total_textures:,}",
        f"Total Cached Sizes:  {total_sizes:,}",
    ]

    if disk_usage > 0:
        if disk_gb >= 0.1:
            lines.append(f"Disk Usage:          {disk_gb:.2f} GB ({disk_usage:,} bytes)")
        else:
            lines.append(f"Disk Usage:          {disk_mb:.2f} MB ({disk_usage:,} bytes)")
    else:
        lines.append("Disk Usage:          Unable to calculate")

    lines.extend([
        "",
        "AGE DISTRIBUTION (by cached size)",
        "-" * 50
    ])

    age_labels = {
        '0-7': 'Last 7 days',
        '8-30': '8-30 days',
        '31-90': '31-90 days',
        '91-180': '91-180 days',
        '180+': 'Over 180 days',
        'unknown': 'Unknown'
    }

    for key in ['0-7', '8-30', '31-90', '91-180', '180+', 'unknown']:
        count = age_buckets.get(key, 0)
        pct = (count / total_sizes * 100) if total_sizes > 0 else 0
        lines.append(f"{age_labels[key]:18s}  {count:6,} sizes ({pct:5.1f}%)")

    lines.extend([
        "",
        "USAGE DISTRIBUTION (by cached size)",
        "-" * 50
    ])

    usage_labels = {
        '0': 'Never used',
        '1-5': '1-5 times',
        '6-20': '6-20 times',
        '21-50': '21-50 times',
        '50+': 'Over 50 times'
    }

    for key in ['0', '1-5', '6-20', '21-50', '50+']:
        count = usage_buckets.get(key, 0)
        pct = (count / total_sizes * 100) if total_sizes > 0 else 0
        lines.append(f"{usage_labels[key]:18s}  {count:6,} sizes ({pct:5.1f}%)")

    lines.extend([
        "",
        "MEDIA TYPE BREAKDOWN (by texture)",
        "-" * 50
    ])

    type_labels = {
        'library': 'Library Artwork',
        'video_thumb': 'Video Thumbnails',
        'music': 'Music Artwork',
        'other': 'Other/System'
    }

    for key in ['library', 'video_thumb', 'music', 'other']:
        count = type_breakdown.get(key, 0)
        pct = (count / total_textures * 100) if total_textures > 0 else 0
        lines.append(f"{type_labels[key]:18s}  {count:6,} textures ({pct:5.1f}%)")

    lines.extend([
        "",
        "=" * 50
    ])

    return "\n".join(lines)
