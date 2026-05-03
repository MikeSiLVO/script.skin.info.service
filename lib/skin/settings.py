"""Kodi settings manipulation utilities for skin integration."""
from __future__ import annotations

import xbmc
import xbmcgui
from lib.kodi.client import request


def _confirm_and_request(heading: str, message: str, method: str, params: dict) -> None:
    """Show a Yes/No confirmation; on Yes, fire the JSON-RPC `method` with `params`."""
    if xbmcgui.Dialog().yesno(heading, message):
        request(method, params)


def get_setting(setting: str, prefix: str = 'SkinInfo', window: str = 'home') -> None:
    """Read a Kodi `setting` value and write it to `{prefix}.Setting.{setting}` window property."""
    result = request('Settings.GetSettingValue', {'setting': setting})
    prop_name = f'{prefix}.Setting.{setting}'

    if result and 'result' in result and 'value' in result['result']:
        value = result['result']['value']
        xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')
    else:
        xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')


def set_setting(setting: str, value: str | int | bool) -> None:
    """Set a Kodi setting after a Yes/No confirmation dialog."""
    _confirm_and_request(
        'Change Setting',
        f'Change setting "{setting}" to "{value}"?',
        'Settings.SetSettingValue',
        {'setting': setting, 'value': value},
    )


def toggle_setting(setting: str) -> None:
    """Toggle a boolean Kodi setting after a Yes/No confirmation dialog."""
    result = request('Settings.GetSettingValue', {'setting': setting})
    if not (result and 'result' in result and 'value' in result['result']):
        return

    current_value = result['result']['value']
    if not isinstance(current_value, bool):
        return

    new_value = not current_value
    new_state = 'enabled' if new_value else 'disabled'
    _confirm_and_request(
        'Toggle Setting',
        f'Change setting "{setting}" to {new_state}?',
        'Settings.SetSettingValue',
        {'setting': setting, 'value': new_value},
    )


def reset_setting(setting: str) -> None:
    """Reset a Kodi setting to its default after a Yes/No confirmation dialog."""
    _confirm_and_request(
        'Reset Setting',
        f'Reset setting "{setting}" to default value?',
        'Settings.ResetSettingValue',
        {'setting': setting},
    )
