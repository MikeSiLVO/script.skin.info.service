"""File system utilities for skin integration."""
import xbmc
import xbmcvfs


def check_file_exists(paths, separator='|', prefix='', window='home'):
    """
    Check if files exist and set window properties with results.

    Checks multiple paths in order, sets properties for first found file.

    Sets properties as:
    - SkinInfo.File.Exists, SkinInfo.File.Path (no prefix)
    - SkinInfo.File.{prefix}.Exists, SkinInfo.File.{prefix}.Path (with prefix)

    Args:
        paths: Pipe-separated list of file paths to check
        separator: Delimiter for paths list (default '|')
        prefix: Optional property suffix (default '', creates SkinInfo.File.*)
        window: Target window name or ID (default 'home')
    """
    prop_base = f'SkinInfo.File.{prefix}' if prefix else 'SkinInfo.File'

    if not paths:
        xbmc.executebuiltin(f'SetProperty({prop_base}.Exists,false,{window})')
        xbmc.executebuiltin(f'ClearProperty({prop_base}.Path,{window})')
        return

    path_list = [path.strip() for path in paths.split(separator) if path.strip()]

    for path in path_list:
        if xbmcvfs.exists(path):
            xbmc.executebuiltin(f'SetProperty({prop_base}.Exists,true,{window})')
            xbmc.executebuiltin(f'SetProperty({prop_base}.Path,{path},{window})')
            return

    xbmc.executebuiltin(f'SetProperty({prop_base}.Exists,false,{window})')
    xbmc.executebuiltin(f'ClearProperty({prop_base}.Path,{window})')
