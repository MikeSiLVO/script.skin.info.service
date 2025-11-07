"""Kodi settings manipulation utilities for skin integration."""
from __future__ import annotations

import xbmc
import xbmcgui
from lib.kodi.client import request


def get_setting(setting: str, prefix: str = 'SkinInfo', window: str = 'home') -> None:
    """
    Get Kodi setting value and set as window property.

    Args:
        setting: Setting name (e.g., 'lookandfeel.skin')
        prefix: Property prefix (default 'SkinInfo')
        window: Target window (default 'home')

    Properties Set:
        {prefix}.Setting.{setting} - Setting value
    """
    result = request('Settings.GetSettingValue', {'setting': setting})

    if result and 'result' in result and 'value' in result['result']:
        value = result['result']['value']
        prop_name = f'{prefix}.Setting.{setting}'
        xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')
    else:
        prop_name = f'{prefix}.Setting.{setting}'
        xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')


def set_setting(setting: str, value: str | int | bool) -> None:
    """
    Set Kodi setting value with user confirmation.

    Args:
        setting: Setting name (e.g., 'lookandfeel.skin')
        value: New value (string, integer, or boolean)
    """
    confirmed = xbmcgui.Dialog().yesno(
        'Change Setting',
        f'Change setting "{setting}" to "{value}"?'
    )

    if confirmed:
        request('Settings.SetSettingValue', {
            'setting': setting,
            'value': value
        })


def toggle_setting(setting: str) -> None:
    """
    Toggle boolean Kodi setting with user confirmation.

    Args:
        setting: Setting name (must be a boolean setting)
    """
    result = request('Settings.GetSettingValue', {'setting': setting})

    if result and 'result' in result and 'value' in result['result']:
        current_value = result['result']['value']

        if isinstance(current_value, bool):
            new_value = not current_value
            new_state = 'enabled' if new_value else 'disabled'

            confirmed = xbmcgui.Dialog().yesno(
                'Toggle Setting',
                f'Change setting "{setting}" to {new_state}?'
            )

            if confirmed:
                request('Settings.SetSettingValue', {
                    'setting': setting,
                    'value': new_value
                })


def reset_setting(setting: str) -> None:
    """
    Reset Kodi setting to default value with user confirmation.

    Args:
        setting: Setting name
    """
    confirmed = xbmcgui.Dialog().yesno(
        'Reset Setting',
        f'Reset setting "{setting}" to default value?'
    )

    if confirmed:
        request('Settings.ResetSettingValue', {'setting': setting})
