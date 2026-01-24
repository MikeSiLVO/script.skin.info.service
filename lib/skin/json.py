"""JSON-RPC preset executor utilities for skin integration."""
import json
import os
import xbmc
import xbmcvfs
from lib.kodi.client import log, request as json_rpc_request, ADDON


_PRESETS_CACHE = None
_ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
_PRESETS_FILE = os.path.join(_ADDON_PATH, 'lib', 'skin', 'json_presets.json')


def load_presets():
    """
    Load JSON-RPC presets from json_presets.json.

    Caches presets in memory for performance.

    Returns:
        Dictionary of preset definitions or empty dict if load fails
    """
    global _PRESETS_CACHE

    if _PRESETS_CACHE is not None:
        return _PRESETS_CACHE

    try:
        with open(_PRESETS_FILE, 'r', encoding='utf-8') as f:
            _PRESETS_CACHE = json.load(f)
            return _PRESETS_CACHE
    except (OSError, json.JSONDecodeError) as e:
        log("JSON", f"Failed to load JSON presets: {e}", xbmc.LOGERROR)
        _PRESETS_CACHE = {}
        return {}


def load_preset(preset_name):
    """
    Load a single preset by name.

    Args:
        preset_name: Name of preset to load

    Returns:
        Preset dictionary or None if not found
    """
    presets = load_presets()
    return presets.get(preset_name)


def default_property_setter(result, window_prop):
    """
    Process JSON-RPC result and set window properties.

    Sets properties as: SkinInfo.{window_prop}.{key} = value

    Args:
        result: JSON-RPC result dictionary
        window_prop: Property prefix (e.g., "Player", "System")
    """
    if not result or not window_prop:
        return

    window = 'home'

    for key, value in result.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                prop_name = f'SkinInfo.{window_prop}.{key}.{sub_key}'
                xbmc.executebuiltin(f'SetProperty({prop_name},{sub_value},{window})')
        else:
            prop_name = f'SkinInfo.{window_prop}.{key}'
            xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')


def execute_json_preset(preset_name):
    """
    Execute a single JSON-RPC preset and set window properties.

    Args:
        preset_name: Name of preset to execute
    """
    preset = load_preset(preset_name)
    if not preset:
        log("JSON", f"Unknown JSON preset: {preset_name}", xbmc.LOGWARNING)
        return

    method = preset.get('method')
    params = preset.get('params', {})
    window_prop = preset.get('window_prop')

    if not method:
        log("JSON", f"Preset '{preset_name}' missing method", xbmc.LOGERROR)
        return

    response = json_rpc_request(method, params)
    if not response:
        log("JSON", f"JSON-RPC request failed for preset '{preset_name}'", xbmc.LOGERROR)
        return

    result = response.get('result')

    if result and window_prop:
        default_property_setter(result, window_prop)


def execute_json_presets(presets):
    """
    Execute multiple JSON-RPC presets.

    Args:
        presets: Pipe-separated list of preset names (e.g., "player_info|system_info")
    """
    if not presets:
        return

    preset_list = [name.strip() for name in presets.split('|') if name.strip()]

    for preset_name in preset_list:
        execute_json_preset(preset_name)
