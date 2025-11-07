"""Media utilities for streamdetails and path processing."""
from __future__ import annotations

import os
import urllib.request
import xbmc
from typing import Dict, Optional

# Lookup tables for faster resolution/aspect detection
_RESOLUTION_TABLE = [
    (720, 480, "480"),
    (768, 576, "576"),
    (960, 544, "540"),
    (1280, 720, "720"),
    (1920, 1080, "1080"),
    (3840, 2160, "4k"),
    (7680, 4320, "8k"),
]

_ASPECT_TABLE = [
    (1.4859, "1.33"),
    (1.7190, "1.66"),
    (1.8147, "1.78"),
    (2.0174, "1.85"),
    (2.2738, "2.20"),
    (float('inf'), "2.35"),
]


def media_streamdetails(filename: str, streamdetails: dict) -> Dict[str, str]:
    info: Dict[str, str] = {}
    video = streamdetails.get("video") or []
    audio = streamdetails.get("audio") or []
    name = (filename or "").lower()

    if xbmc.getCondVisibility("ListItem.IsStereoscopic"):
        info["videoresolution"] = "3d"
    elif video:
        v0 = video[0]
        w = int(v0.get("width", 0) or 0)
        h = int(v0.get("height", 0) or 0)
        # Use lookup table for faster resolution detection
        for max_w, max_h, label in _RESOLUTION_TABLE:
            if w <= max_w and h <= max_h:
                info["videoresolution"] = label
                break
        else:
            info["videoresolution"] = ""
    elif ("dvd" in name and not any(x in name for x in ("hddvd", "hd-dvd"))) or name.endswith((".vob", ".ifo")):
        info["videoresolution"] = "576"
    elif any(x in name for x in ("bluray", "blu-ray", "brrip", "bdrip", "hddvd", "hd-dvd")):
        info["videoresolution"] = "1080"
    elif "4k" in name:
        info["videoresolution"] = "4k"
    else:
        info["videoresolution"] = "1080"

    if video:
        v0 = video[0]
        aspect = float(v0.get("aspect", 0) or 0)
        info["videocodec"] = v0.get("codec", "") or ""
        # Use lookup table for faster aspect ratio detection
        for max_aspect, label in _ASPECT_TABLE:
            if aspect < max_aspect:
                info["videoaspect"] = label
                break
    else:
        info["videocodec"] = ""
        info["videoaspect"] = ""

    if audio:
        a0 = audio[0]
        info["audiocodec"] = a0.get("codec", "") or ""
        ch = a0.get("channels", "")
        info["audiochannels"] = "" if ch is None else str(ch)
    else:
        info["audiocodec"] = ""
        info["audiochannels"] = ""

    return info


def media_path(path: Optional[str]) -> str:
    """ Normalize a file path and resolve rar:// or multipath:// prefixes. """
    path = str(path or "")
    try:
        base = os.path.split(path)[0].rsplit(" , ", 1)[1].replace(",,", ",")
    except Exception:
        base = os.path.split(path)[0]

    if base.startswith("rar://"):
        base = urllib.request.url2pathname(base[6:])
    elif base.startswith("multipath://"):
        parts = base[13:].split("%2f/")
        base = urllib.request.url2pathname(parts[0])
    return base
