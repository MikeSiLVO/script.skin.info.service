"""Widget handlers that resolve Kodi favourites back to library items."""
from __future__ import annotations

import re

import xbmcplugin

from lib.kodi.client import request, extract_result

_WINDOW_TVSHOW = re.compile(r'videodb://tvshows/titles/(\d+)')

_MEDIA_TYPES = ('movie', 'episode', 'musicvideo')

_FILTER_CHUNK = 100

_LIBRARY_CALLS = {
    'movie': ('VideoLibrary.GetMovies', 'movies'),
    'episode': ('VideoLibrary.GetEpisodes', 'episodes'),
    'musicvideo': ('VideoLibrary.GetMusicVideos', 'musicvideos'),
}

_CONTENT = {'movie': 'movies', 'tvshow': 'tvshows', 'episode': 'episodes',
            'musicvideo': 'musicvideos'}


def _favourite_entries() -> list:
    """Every favourite, with the fields needed to point it at a library item."""
    result = request('Favourites.GetFavourites',
                     {'properties': ['windowparameter', 'path', 'thumbnail']})
    return extract_result(result, 'favourites', [])


def _basename(path: str) -> str:
    """Filename of a favourite's path, which is what the library can be filtered on."""
    return path.replace('\\', '/').rstrip('/').split('/')[-1]


def _items_by_file(media_type: str, paths: list, properties: list) -> dict:
    """Library items for the given file paths, keyed by path; only exact path matches count,
    since a filename can repeat across folders."""
    method, result_key = _LIBRARY_CALLS[media_type]
    wanted = set(paths)
    names = sorted({_basename(path) for path in paths if path})

    found = {}
    for start in range(0, len(names), _FILTER_CHUNK):
        chunk = names[start:start + _FILTER_CHUNK]
        result = request(method, {
            'properties': properties,
            'filter': {'or': [{'field': 'filename', 'operator': 'is', 'value': name}
                              for name in chunk]}
        })
        for item in extract_result(result, result_key, []):
            if item.get('file') in wanted:
                found[item['file']] = item
    return found


def _tvshows_by_id(tvshowids: set, properties: list) -> dict:
    """Library shows for the given DBIDs, keyed by DBID."""
    if not tvshowids:
        return {}
    result = request('VideoLibrary.GetTVShows', {'properties': properties})
    return {show['tvshowid']: show for show in extract_result(result, 'tvshows', [])
            if show['tvshowid'] in tvshowids}


def handle_favourites(handle: int, params: dict) -> None:
    """Plugin entry: favourites resolved to library items; `dbtype` narrows to one media type."""
    from lib.plugin.widgets.music import _create_musicvideo_listitem, _MUSICVIDEO_PROPERTIES
    from lib.plugin.widgets.video import (_create_movie_listitem, _create_tvshow_listitem,
                                          _episode_item_from_show, _EPISODE_PROPERTIES,
                                          _FULL_SHOW_PROPERTIES, _MOVIE_PROPERTIES)

    dbtype = params.get('dbtype', [''])[0].lower()
    limit = int(params.get('limit', ['0'])[0])

    favourites = _favourite_entries()
    wanted_shows, wanted_paths = set(), []
    for favourite in favourites:
        match = _WINDOW_TVSHOW.search(favourite.get('windowparameter') or '')
        if match:
            wanted_shows.add(int(match.group(1)))
        elif favourite.get('path'):
            wanted_paths.append(favourite['path'])

    show_properties = [name for name in _FULL_SHOW_PROPERTIES if name != 'cast']
    shows = ({} if dbtype and dbtype != 'tvshow'
             else _tvshows_by_id(wanted_shows, show_properties))

    media: dict = {}
    properties = {'movie': _MOVIE_PROPERTIES,
                  'episode': _EPISODE_PROPERTIES + ['tvshowid'],
                  'musicvideo': _MUSICVIDEO_PROPERTIES}
    for media_type in _MEDIA_TYPES:
        if dbtype and dbtype != media_type:
            continue
        if wanted_paths:
            media[media_type] = _items_by_file(media_type, wanted_paths, properties[media_type])

    added = 0
    for favourite in favourites:
        if limit and added >= limit:
            break

        match = _WINDOW_TVSHOW.search(favourite.get('windowparameter') or '')
        if match:
            show = shows.get(int(match.group(1)))
            if not show:
                continue
            listitem = _create_tvshow_listitem(show)
            xbmcplugin.addDirectoryItem(
                handle, f"videodb://tvshows/titles/{show['tvshowid']}/", listitem, True)
            added += 1
            continue

        path = favourite.get('path')
        if not path:
            continue
        for media_type in _MEDIA_TYPES:
            item = media.get(media_type, {}).get(path)
            if not item:
                continue
            if media_type == 'episode':
                listitem = _episode_item_from_show({}, item)
            elif media_type == 'musicvideo':
                listitem = _create_musicvideo_listitem(item)
            else:
                listitem = _create_movie_listitem(item)
            xbmcplugin.addDirectoryItem(handle, path, listitem, False)
            added += 1
            break

    xbmcplugin.setContent(handle, _CONTENT.get(dbtype, 'videos'))
    xbmcplugin.endOfDirectory(handle)
