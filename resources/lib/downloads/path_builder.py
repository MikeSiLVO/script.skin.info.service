"""Build Kodi-compliant artwork file paths following naming conventions."""
from __future__ import annotations

import os
import json
import xbmc
import xbmcgui
from typing import Optional


class ArtworkPathBuilder:
    """
    Build filesystem paths following Kodi naming conventions.

    References:
    - https://kodi.wiki/view/Movie_artwork
    - https://kodi.wiki/view/TV_show_artwork
    """

    @staticmethod
    def _get_movie_sets_folder() -> str:
        """
        Query Kodi for the movie sets folder setting.

        Returns:
            Movie sets folder path, or empty string if not configured
        """
        request = {
            "jsonrpc": "2.0",
            "method": "Settings.GetSettingValue",
            "params": {"setting": "videolibrary.moviesetsfolder"},
            "id": 1
        }
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)
        if "result" in result and "value" in result["result"]:
            return result["result"]["value"]
        return ""

    @staticmethod
    def _configure_movie_sets_folder() -> Optional[str]:
        """
        Prompt user to select and configure movie sets folder if not set.

        Returns:
            Selected folder path, or None if user cancelled
        """
        dialog = xbmcgui.Dialog()

        configure = dialog.yesno(
            "Movie Set Information Folder Not Configured",
            "MSIF (Movie Set Information Folder) is not configured in Kodi settings.[CR][CR]"
            "This folder stores artwork for movie sets (like 'The Matrix Collection').[CR][CR]"
            "Would you like to select a folder now?"
        )

        if not configure:
            return None

        folder = dialog.browse(
            0,
            "Select Movie Sets Folder",
            "files",
            "",
            False,
            False,
            ""
        )

        if not folder or isinstance(folder, list):
            return None

        request = {
            "jsonrpc": "2.0",
            "method": "Settings.SetSettingValue",
            "params": {
                "setting": "videolibrary.moviesetsfolder",
                "value": folder
            },
            "id": 1
        }
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)

        if result.get("result") is True:
            dialog.notification(
                "Movie Sets Folder",
                "Folder configured successfully",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return folder
        else:
            dialog.ok(
                "Error",
                "Failed to save movie sets folder setting.[CR][CR]Please configure manually in Kodi settings."
            )
            return None

    @staticmethod
    def _make_legal_filename(title: str) -> str:
        """
        Sanitize set title to legal filename matching Kodi's MakeLegalFileName behavior.

        Args:
            title: Movie set title

        Returns:
            Sanitized filename safe for cross-platform use
        """
        illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        sanitized = title
        for char in illegal_chars:
            sanitized = sanitized.replace(char, '')
        sanitized = sanitized.strip('. ')
        return sanitized if sanitized else "Unnamed Set"

    @staticmethod
    def build_path(
        media_type: str,
        media_file: str,
        artwork_type: str,
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        use_basename: bool = True
    ) -> Optional[str]:
        """
        Build complete path for artwork file.

        Returns base path WITHOUT extension (extension added by downloader based on content-type).

        Examples:
            Movie basename: /Movies/Avatar.mkv -> /Movies/Avatar-poster
            Movie folder: /Movies/Avatar/ -> /Movies/Avatar/poster
            Movie BDMV: /Movies/Avatar/BDMV/STREAM/00001.m2ts -> /Movies/Avatar/poster
            Movie VIDEO_TS: /Movies/Avatar/VIDEO_TS/VTS_01_1.VOB -> /Movies/Avatar/poster
            TV Show: /TV/Show/ -> /TV/Show/poster
            Season: /TV/Show/ -> /TV/Show/season01-poster
            Episode basename: /TV/Show/S01E01.mkv -> /TV/Show/S01E01-thumb

        Args:
            media_type: 'movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set'
            media_file: Full path to media file/directory, or set title for 'set' media_type
            artwork_type: Artwork type ('poster', 'fanart', 'clearlogo', etc.)
            season_number: Season number (for season/episode artwork)
            episode_number: Episode number (for episode artwork)
            use_basename: Whether to use basename mode (Movie-poster vs poster in folder)

        Returns:
            Base path string (without extension) or None if cannot build
        """
        if not media_file:
            return None

        base_path = os.path.splitext(media_file)[0]
        dir_path, filename = os.path.split(base_path)

        sep = '\\' if '\\' in media_file else '/'

        if media_type == 'movie':
            parent_dir_name = os.path.basename(dir_path)
            if parent_dir_name in ('BDMV', 'VIDEO_TS'):
                dir_path = os.path.dirname(dir_path)
                return dir_path + sep + artwork_type
            elif use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                return dir_path + sep + artwork_type

        elif media_type == 'tvshow':
            return dir_path + sep + artwork_type

        elif media_type == 'season':
            if season_number is None:
                return None
            if season_number > 0:
                season_str = f"season{season_number:02d}"
            else:
                season_str = "season-specials"
            return dir_path + sep + season_str + '-' + artwork_type

        elif media_type == 'episode':
            if use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                return dir_path + sep + 'episode-' + artwork_type

        elif media_type == 'musicvideo':
            if use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                return dir_path + sep + artwork_type

        elif media_type == 'set':
            movie_sets_folder = ArtworkPathBuilder._get_movie_sets_folder()

            if not movie_sets_folder:
                movie_sets_folder = ArtworkPathBuilder._configure_movie_sets_folder()

            if not movie_sets_folder:
                return None

            set_title = media_file
            sanitized_title = ArtworkPathBuilder._make_legal_filename(set_title)

            if artwork_type.startswith('set.'):
                clean_art_type = artwork_type[4:]
            else:
                clean_art_type = artwork_type

            sep = '\\' if '\\' in movie_sets_folder else '/'
            return movie_sets_folder + sep + sanitized_title + sep + clean_art_type

        return None
