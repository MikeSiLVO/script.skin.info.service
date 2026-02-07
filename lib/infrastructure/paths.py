"""Build Kodi-compliant artwork file paths following naming conventions."""
from __future__ import annotations

import xbmcgui
import xbmcvfs
from typing import Optional, Tuple

from lib.kodi.client import request


def vfs_get_separator(path: str) -> str:
    """Detect separator used in path (backslash for Windows/SMB, forward slash otherwise)."""
    return '\\' if '\\' in path else '/'


def vfs_rstrip_sep(path: str) -> str:
    """Strip trailing separators from path."""
    return path.rstrip('/\\')


def vfs_ensure_dir_slash(path: str) -> str:
    """Ensure path has trailing separator. Required for xbmcvfs.exists() directory checks."""
    if not path:
        return path
    path = vfs_rstrip_sep(path)
    sep = vfs_get_separator(path)
    return path + sep


def vfs_split(path: str) -> Tuple[str, str]:
    """
    Split path into (directory, filename) like os.path.split but VFS-aware.

    Handles both / and \\ separators correctly.
    Strips trailing separators before splitting.

    Examples:
        '/TV/Show/' -> ('/TV', 'Show')
        '/TV/Show' -> ('/TV', 'Show')
        '/TV/Show/file.mkv' -> ('/TV/Show', 'file.mkv')
        'smb://server/share/folder' -> ('smb://server/share', 'folder')
    """
    path = vfs_rstrip_sep(path)
    if not path:
        return ('', '')

    last_sep = -1
    for i in range(len(path) - 1, -1, -1):
        if path[i] in '/\\':
            last_sep = i
            break

    if last_sep == -1:
        return ('', path)

    return (path[:last_sep], path[last_sep + 1:])


def vfs_dirname(path: str) -> str:
    """Get parent directory of path, VFS-aware."""
    return vfs_split(path)[0]


def vfs_basename(path: str) -> str:
    """Get filename/last component of path, VFS-aware."""
    return vfs_split(path)[1]


def vfs_splitext(path: str) -> Tuple[str, str]:
    """
    Split path into (base, extension) like os.path.splitext but VFS-aware.

    Only considers extension in the filename part, not in directories.

    Examples:
        '/path/file.mkv' -> ('/path/file', '.mkv')
        '/path.with.dots/file' -> ('/path.with.dots/file', '')
        '/path/file' -> ('/path/file', '')
    """
    dir_part, filename = vfs_split(path)

    if not filename:
        return (path, '')

    dot_pos = filename.rfind('.')
    if dot_pos <= 0:  # No dot, or dot at start (hidden file)
        return (path, '')

    ext = filename[dot_pos:]
    base = filename[:dot_pos]

    if dir_part:
        sep = vfs_get_separator(path)
        return (dir_part + sep + base, ext)
    return (base, ext)


def vfs_join(base: str, *parts: str) -> str:
    """Join path components using the separator from the base path."""
    if not base:
        return '/'.join(parts)

    sep = vfs_get_separator(base)
    result = vfs_rstrip_sep(base)

    for part in parts:
        if part:
            result = result + sep + part

    return result


def build_actors_folder_path(media_type: str, file_path: str, show_path: Optional[str] = None) -> Optional[str]:
    """
    Build .actors folder path for a media item.

    Follows Kodi conventions from VideoInfoScanner.cpp and VideoDatabase.cpp:
    - Movie: parent directory of movie file
    - TV Show: show root directory
    - Episode: show root directory (shared with TV show)

    Args:
        media_type: 'movie', 'tvshow', or 'episode'
        file_path: Path to movie file or TV show folder
        show_path: TV show root path (required for episodes)

    Returns:
        Full path to .actors folder, or None if cannot determine
    """
    if media_type == "movie":
        if not file_path:
            return None
        parent = vfs_dirname(file_path)
        return vfs_join(parent, ".actors")
    elif media_type in ("tvshow", "episode"):
        base_path = show_path if show_path else file_path
        if not base_path:
            return None
        base_path = base_path.rstrip("/\\")
        return vfs_join(base_path, ".actors")

    return None


class PathBuilder:
    """
    Build filesystem paths following Kodi naming conventions.

    References:
    - https://kodi.wiki/view/Movie_artwork
    - https://kodi.wiki/view/TV_show_artwork
    - xbmc/music/MusicDatabase.cpp (GetArtistFolderName, GetAlbumFolder)
    """

    _music_thumb_filename: Optional[str] = None

    @staticmethod
    def _get_kodi_folder_setting(setting: str) -> str:
        response = request("Settings.GetSettingValue", {"setting": setting})
        if response and "value" in response.get("result", {}):
            return response["result"]["value"]
        return ""

    @staticmethod
    def _configure_kodi_folder_setting(
        setting: str,
        heading: str,
        message: str,
        browse_heading: str
    ) -> Optional[str]:
        dialog = xbmcgui.Dialog()

        if not dialog.yesno(heading, message):
            return None

        folder = dialog.browse(0, browse_heading, "files", "", False, False, "")
        if not folder or not isinstance(folder, str):
            return None

        response = request("Settings.SetSettingValue", {
            "setting": setting,
            "value": folder
        })

        if response and response.get("result") is True:
            dialog.notification(
                heading,
                "Folder configured successfully",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return folder

        dialog.ok(
            "Error",
            "Failed to save setting.[CR][CR]Please configure manually in Kodi settings."
        )
        return None

    @staticmethod
    def _resolve_named_item_folder(setting: str, heading: str, message: str, browse_heading: str) -> Optional[str]:
        folder = PathBuilder._get_kodi_folder_setting(setting)
        if not folder:
            folder = PathBuilder._configure_kodi_folder_setting(
                setting, heading, message, browse_heading
            )
        return folder

    @staticmethod
    def _get_music_thumb_filename() -> str:
        if PathBuilder._music_thumb_filename is not None:
            return PathBuilder._music_thumb_filename
        # Kodi discovers thumb art by matching filenames from this setting,
        # so we must save using a name from the user's configured list.
        value = PathBuilder._get_kodi_folder_setting("musiclibrary.musicthumbs")
        result = "folder"
        if value:
            first = value[0].strip() if isinstance(value, list) else value.split(",")[0].strip()
            dot = first.rfind(".")
            if dot > 0:
                result = first[:dot]
        PathBuilder._music_thumb_filename = result
        return result

    @staticmethod
    def _make_legal_filename(name: str, fallback: str = "Unknown", parent_dir: str = "") -> str:
        if not name:
            return fallback
        # makeLegalFilename wraps CUtil::MakeLegalPath which skips
        # sanitization for bare names (no HD/SMB/NFS prefix detected).
        full_path = vfs_join(parent_dir, name) if parent_dir else name
        sanitized = xbmcvfs.makeLegalFilename(full_path)
        sanitized = vfs_basename(sanitized)
        return sanitized if sanitized else fallback

    @staticmethod
    def _make_music_folder_name(name: str, fallback: str = "Unknown", parent_dir: str = "") -> str:
        sanitized = PathBuilder._make_legal_filename(name, fallback, parent_dir)
        sanitized = sanitized.replace(' _ ', '_')
        return sanitized

    @staticmethod
    def _count_library_artists(artist_name: str) -> int:
        response = request("AudioLibrary.GetArtists", {
            "filter": {"field": "artist", "operator": "is", "value": artist_name}
        })
        if response and "artists" in response.get("result", {}):
            return len(response["result"]["artists"])
        return 1

    @staticmethod
    def _find_movie_root(path: str) -> str:
        """
        Find movie root directory, handling BDMV/VIDEO_TS structures.

        For Blu-ray: /Movies/Avatar/BDMV/STREAM/00001.m2ts -> /Movies/Avatar
        For DVD: /Movies/Avatar/VIDEO_TS/VTS_01_1.VOB -> /Movies/Avatar
        Otherwise returns parent directory of the file.
        """
        dir_path = vfs_dirname(path)

        check_path = dir_path
        for _ in range(3):
            dirname = vfs_basename(check_path)
            if dirname in ('BDMV', 'VIDEO_TS', 'STREAM', 'BACKUP'):
                check_path = vfs_dirname(check_path)
            else:
                break

        parent_name = vfs_basename(vfs_dirname(path))
        grandparent_name = vfs_basename(vfs_dirname(vfs_dirname(path)))

        if parent_name in ('BDMV', 'VIDEO_TS'):
            return vfs_dirname(vfs_dirname(path))
        elif grandparent_name in ('BDMV', 'VIDEO_TS'):
            return vfs_dirname(vfs_dirname(vfs_dirname(path)))
        elif parent_name == 'STREAM' and grandparent_name == 'BDMV':
            return vfs_dirname(vfs_dirname(vfs_dirname(path)))

        return dir_path

    @staticmethod
    def build_path(
        media_type: str,
        media_file: str,
        artwork_type: str,
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        use_basename: bool = True,
        mbid: Optional[str] = None
    ) -> Optional[str]:
        """
        Build complete path for artwork file.

        Returns base path WITHOUT extension (extension added by downloader based on content-type).

        Args:
            media_type: 'movie', 'tvshow', 'season', 'episode', 'musicvideo', 'set', 'artist', 'album'
            media_file: Full path to media file/directory, or title/name for 'set'/'artist'
            artwork_type: Artwork type ('poster', 'fanart', 'clearlogo', etc.)
            season_number: Season number (for season/episode artwork)
            episode_number: Episode number (for episode artwork)
            use_basename: Whether to use basename mode (Movie-poster vs poster in folder)
            mbid: MusicBrainz ID (for artist duplicate name disambiguation)

        Returns:
            Base path string (without extension) or None if cannot build
        """
        if not media_file:
            return None

        base_path, ext = vfs_splitext(media_file)
        dir_path, filename = vfs_split(base_path)

        if not ext:
            dir_path = vfs_rstrip_sep(media_file)
            filename = ''

        if media_type == 'movie':
            if use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                if ext:
                    movie_root = PathBuilder._find_movie_root(media_file)
                else:
                    movie_root = dir_path
                return vfs_join(movie_root, artwork_type)

        elif media_type == 'tvshow':
            return vfs_join(dir_path, artwork_type)

        elif media_type == 'season':
            if season_number is None:
                return None
            if season_number > 0:
                season_str = f"season{season_number:02d}"
            else:
                season_str = "season-specials"
            return vfs_join(dir_path, season_str + '-' + artwork_type)

        elif media_type == 'episode':
            if use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                return vfs_join(dir_path, 'episode-' + artwork_type)

        elif media_type == 'musicvideo':
            if use_basename and filename:
                return base_path + '-' + artwork_type
            else:
                return vfs_join(dir_path, artwork_type)

        elif media_type == 'set':
            movie_sets_folder = PathBuilder._resolve_named_item_folder(
                "videolibrary.moviesetsfolder",
                "Movie Set Information Folder Not Configured",
                "MSIF (Movie Set Information Folder) is not configured in Kodi settings.[CR][CR]"
                "This folder stores artwork for movie sets (like 'The Matrix Collection').[CR][CR]"
                "Would you like to select a folder now?",
                "Select Movie Sets Folder"
            )
            if not movie_sets_folder:
                return None

            sanitized_title = PathBuilder._make_legal_filename(media_file, "Unnamed Set", movie_sets_folder)

            if artwork_type.startswith('set.'):
                clean_art_type = artwork_type[4:]
            else:
                clean_art_type = artwork_type

            return vfs_join(movie_sets_folder, sanitized_title, clean_art_type)

        elif media_type == 'artist':
            artist_folder = PathBuilder._resolve_named_item_folder(
                "musiclibrary.artistsfolder",
                "Artist Information Folder Not Configured",
                "Artist Information Folder is not configured in Kodi settings.[CR][CR]"
                "This folder stores artwork and metadata for music artists.[CR][CR]"
                "Would you like to select a folder now?",
                "Select Artist Information Folder"
            )
            if not artist_folder:
                return None

            folder_name = PathBuilder._make_music_folder_name(media_file, "Unknown Artist", artist_folder)

            if mbid and PathBuilder._count_library_artists(media_file) > 1:
                folder_name += '_' + mbid[:4]

            art_name = PathBuilder._get_music_thumb_filename() if artwork_type == 'thumb' else artwork_type
            return vfs_join(artist_folder, folder_name, art_name)

        elif media_type == 'album':
            art_name = PathBuilder._get_music_thumb_filename() if artwork_type == 'thumb' else artwork_type
            return vfs_join(vfs_rstrip_sep(media_file), art_name)

        return None
