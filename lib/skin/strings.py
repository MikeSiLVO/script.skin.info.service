"""String manipulation utilities for skin integration."""
import xbmc

from lib.kodi.utilities import set_window_prop, clear_window_prop


def split_string(string, separator='|', prefix='', window='home'):
    """Split `string` and write `SkinInfo.Split[.{prefix}].{Count, 1, 2, ...}` window properties."""
    prop_base = f'SkinInfo.Split.{prefix}' if prefix else 'SkinInfo.Split'
    previous = xbmc.getInfoLabel(f'Window({window}).Property({prop_base}.Count)')
    parts = string.split(separator) if string else []

    set_window_prop(f'{prop_base}.Count', len(parts), window)
    for idx, part in enumerate(parts, start=1):
        set_window_prop(f'{prop_base}.{idx}', part.strip(), window)
    for idx in range(len(parts) + 1, int(previous) + 1 if previous.isdigit() else 0):
        clear_window_prop(f'{prop_base}.{idx}', window)


def urlencode(string, prefix='', window='home'):
    """URL-encode `string` and write to `SkinInfo.Encoded[.{prefix}]`."""
    prop_name = f'SkinInfo.Encoded.{prefix}' if prefix else 'SkinInfo.Encoded'

    if not string:
        clear_window_prop(prop_name, window)
        return

    from urllib.parse import quote
    encoded = quote(string)
    set_window_prop(prop_name, encoded, window)


def urldecode(string, prefix='', window='home'):
    """URL-decode `string` and write to `SkinInfo.Decoded[.{prefix}]`."""
    prop_name = f'SkinInfo.Decoded.{prefix}' if prefix else 'SkinInfo.Decoded'

    if not string:
        clear_window_prop(prop_name, window)
        return

    from urllib.parse import unquote
    decoded = unquote(string)
    set_window_prop(prop_name, decoded, window)
