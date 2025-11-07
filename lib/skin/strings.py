"""String manipulation utilities for skin integration."""
import urllib.parse
import xbmc


def split_string(string, separator='|', prefix='', window='home'):
    """
    Split a string into parts and set window properties.

    Sets properties as:
    - SkinInfo.Split.Count, SkinInfo.Split.1, etc. (no prefix)
    - SkinInfo.Split.{prefix}.Count, SkinInfo.Split.{prefix}.1, etc. (with prefix)

    Args:
        string: String to split
        separator: Delimiter to split on (default '|')
        prefix: Optional property suffix (default '', creates SkinInfo.Split.*)
        window: Target window name or ID (default 'home')
    """
    prop_base = f'SkinInfo.Split.{prefix}' if prefix else 'SkinInfo.Split'

    if not string:
        xbmc.executebuiltin(f'SetProperty({prop_base}.Count,0,{window})')
        return

    parts = string.split(separator)
    xbmc.executebuiltin(f'SetProperty({prop_base}.Count,{len(parts)},{window})')

    for idx, part in enumerate(parts, start=1):
        xbmc.executebuiltin(f'SetProperty({prop_base}.{idx},{part.strip()},{window})')


def urlencode(string, prefix='', window='home'):
    """
    URL-encode a string and set as window property.

    Sets property as:
    - SkinInfo.Encoded (no prefix)
    - SkinInfo.Encoded.{prefix} (with prefix)

    Args:
        string: String to encode
        prefix: Optional property suffix (default '', creates SkinInfo.Encoded)
        window: Target window name or ID (default 'home')
    """
    prop_name = f'SkinInfo.Encoded.{prefix}' if prefix else 'SkinInfo.Encoded'

    if not string:
        xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')
        return

    encoded = urllib.parse.quote(string)
    xbmc.executebuiltin(f'SetProperty({prop_name},{encoded},{window})')


def urldecode(string, prefix='', window='home'):
    """
    URL-decode a string and set as window property.

    Sets property as:
    - SkinInfo.Decoded (no prefix)
    - SkinInfo.Decoded.{prefix} (with prefix)

    Args:
        string: String to decode
        prefix: Optional property suffix (default '', creates SkinInfo.Decoded)
        window: Target window name or ID (default 'home')
    """
    prop_name = f'SkinInfo.Decoded.{prefix}' if prefix else 'SkinInfo.Decoded'

    if not string:
        xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')
        return

    decoded = urllib.parse.unquote(string)
    xbmc.executebuiltin(f'SetProperty({prop_name},{decoded},{window})')
