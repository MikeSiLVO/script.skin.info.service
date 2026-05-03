"""Plugin handlers for cast lists (library and player)."""
from __future__ import annotations

import traceback
import xbmc
import xbmcgui
import xbmcplugin

from lib.kodi.client import log, extract_result
from lib.data.api.utilities import tmdb_image_url


_MAX_CAST_ITEMS = 2000


def _deduplicate_cast(items: list) -> list:
    """Dedupe cast across items (by `name`, first occurrence wins). Adds `_source_id` to each actor."""
    seen = set()
    unique_cast = []

    for item in items:
        cast = item.get('cast', [])
        item_id = item.get('movieid') or item.get('episodeid')

        for actor in cast:
            name = actor.get('name')
            if name and name not in seen:
                seen.add(name)
                actor_copy = actor.copy()
                if item_id:
                    actor_copy['_source_id'] = item_id
                unique_cast.append(actor_copy)

    if len(unique_cast) > _MAX_CAST_ITEMS:
        unique_cast = unique_cast[:_MAX_CAST_ITEMS]

    return unique_cast


def _create_cast_listitems(handle: int, cast_list: list) -> int:
    """Add ListItems to the plugin directory for each actor. Returns count added."""
    items_added = 0
    for actor in cast_list:
        name = actor.get('name', '')
        if not name:
            continue

        role = actor.get('role') or actor.get('character', '')
        if not role and 'roles' in actor and actor['roles']:
            role = actor['roles'][0].get('character', '')

        item = xbmcgui.ListItem(label=name, label2=role, offscreen=True)
        thumb = actor.get('thumbnail') or actor.get('profile_path') or ''

        if thumb.startswith('/'):
            thumb = tmdb_image_url(thumb, 'w185')

        if thumb:
            item.setArt({'icon': thumb, 'thumb': thumb})
        else:
            item.setArt({'icon': 'DefaultActor.png', 'thumb': 'DefaultActor.png'})

        source_id = actor.get('_source_id')
        if source_id:
            item.setProperty('source_id', str(source_id))

        person_id = actor.get('id')
        if person_id:
            item.setProperty('person_id', str(person_id))

        xbmcplugin.addDirectoryItem(handle, '', item, False)
        items_added += 1

    if items_added > 0:
        xbmcplugin.setContent(handle, 'actors')

    return items_added


def _handle_online_cast(handle: int, dbtype: str, dbid: int) -> int:
    """Fetch cast from TMDB and render as directory. Returns count added."""
    from lib.kodi.client import get_item_details
    from lib.data.api.tmdb import ApiTmdb
    from lib.data.api.person import resolve_tmdb_id

    tmdb_id = resolve_tmdb_id(dbtype, dbid)
    if not tmdb_id:
        log("Plugin", f"Online Cast: Could not resolve TMDB ID for {dbtype} {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return 0

    api = ApiTmdb()
    cast = []

    if dbtype == 'movie':
        data = api.get_movie_details_extended(tmdb_id)
        if data and 'credits' in data:
            cast = data['credits'].get('cast', [])

    elif dbtype == 'tvshow':
        data = api.get_tv_details_extended(tmdb_id)
        if data and 'credits' in data:
            cast = data['credits'].get('cast', [])

    elif dbtype == 'season':
        details = get_item_details(dbtype, dbid, ['season'])
        if not details:
            log("Plugin", f"Online Cast: Failed to get season details for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_num = details.get('season')
        if season_num is None:
            log("Plugin", f"Online Cast: No season number for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_data = api.get_season_details(tmdb_id, season_num)
        if season_data:
            main_cast = season_data.get('aggregate_credits', {}).get('cast', [])
            all_guests = {}
            for episode in season_data.get('episodes', []):
                for guest in episode.get('guest_stars', []):
                    guest_id = guest.get('id')
                    if guest_id and guest_id not in all_guests:
                        all_guests[guest_id] = guest
            cast = main_cast + list(all_guests.values())

    elif dbtype == 'episode':
        details = get_item_details(dbtype, dbid, ['season', 'episode'])
        if not details:
            log("Plugin", f"Online Cast: Failed to get episode details for {dbid}", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return 0

        season_num = details.get('season')
        episode_num = details.get('episode')

        episode_data = api.get_episode_details_extended(tmdb_id, season_num, episode_num)
        if episode_data and 'credits' in episode_data:
            episode_cast = episode_data['credits'].get('cast', [])
            episode_guests = episode_data['credits'].get('guest_stars', [])
            cast = episode_cast + episode_guests

    if not cast:
        log("Plugin", f"Online Cast: No cast found for {dbtype} {dbid}", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return 0

    log("Plugin", f"Online Cast: Found {len(cast)} cast members for {dbtype} {dbid}", xbmc.LOGDEBUG)
    return _create_cast_listitems(handle, cast)


def handle_get_cast(handle: int, params: dict) -> None:
    """Plugin entry for cast listings. `online=true` fetches from TMDB; default reads the Kodi library."""
    try:
        dbid = params.get('dbid', [''])[0]
        dbtype = params.get('dbtype', [''])[0]
        online = params.get('online', ['false'])[0].lower() == 'true'

        if not dbid or not dbtype:
            log("Plugin", "Library Cast: Missing required parameters", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        if dbtype not in ('movie', 'set', 'tvshow', 'season', 'episode'):
            log("Plugin", f'Library Cast: Invalid dbtype "{dbtype}"', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        from lib.kodi.client import get_item_details

        items_added = 0

        if online:
            log("Plugin", f"Library Cast: Using online TMDB data for {dbtype} {dbid}", xbmc.LOGDEBUG)
            items_added = _handle_online_cast(handle, dbtype, int(dbid))
        elif dbtype in ('movie', 'episode', 'tvshow'):
            if dbtype == 'movie':
                details = get_item_details('movie', int(dbid), ['cast'])
            elif dbtype == 'episode':
                details = get_item_details('episode', int(dbid), ['cast'])
            else:
                details = get_item_details('tvshow', int(dbid), ['cast'])

            if not details:
                log("Plugin", f"Library Cast: {dbtype.capitalize()} {dbid} not found", xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return

            cast = details.get('cast', [])
            if not cast:
                log("Plugin", f"Library Cast: No cast found for {dbtype} {dbid}", xbmc.LOGINFO)
                xbmcplugin.endOfDirectory(handle, succeeded=True)
                return

            log("Plugin", f"Library Cast: Processing {dbtype} {dbid} - Found {len(cast)} cast members", xbmc.LOGDEBUG)
            items_added = _create_cast_listitems(handle, cast)

        elif dbtype in ('set', 'season'):
            if dbtype == 'set':
                details = get_item_details(
                    'set',
                    int(dbid),
                    ['title'],
                    movies={
                        'properties': ['cast'],
                        'sort': {'method': 'year', 'order': 'ascending'},
                    }
                )
                items = details.get('movies', []) if details else []

            else:
                from lib.kodi.client import request

                season_details = get_item_details('season', int(dbid), ['season', 'tvshowid'])
                if not season_details:
                    log("Plugin", f"Library Cast: Season {dbid} not found", xbmc.LOGWARNING)
                    xbmcplugin.endOfDirectory(handle, succeeded=False)
                    return

                tvshow_id = season_details.get('tvshowid')
                season_num = season_details.get('season')

                result = request(
                    'VideoLibrary.GetEpisodes',
                    {
                        'tvshowid': tvshow_id,
                        'season': season_num,
                        'properties': ['cast'],
                        'sort': {'method': 'episode', 'order': 'ascending'}
                    }
                )
                items = extract_result(result, 'episodes', [])

            if not items:
                log("Plugin", f"Library Cast: No items found for {dbtype} {dbid}", xbmc.LOGINFO)
                xbmcplugin.endOfDirectory(handle, succeeded=True)
                return

            unique_cast = _deduplicate_cast(items)

            log("Plugin", f"Library Cast: Processing {dbtype} {dbid} - Found {len(items)} items, deduplicated to {len(unique_cast)} unique cast", xbmc.LOGDEBUG)

            items_added = _create_cast_listitems(handle, unique_cast)

        log("Plugin", f"Library Cast: Created {items_added} ListItems", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)

    except Exception as e:
        log("Plugin", f"Library Cast: Error - {e}", xbmc.LOGERROR)
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def handle_get_cast_player(handle: int, params: dict) -> None:
    """Plugin entry for player cast. `scope=show` on episodes returns the show's combined cast."""
    try:
        content = xbmc.getInfoLabel('VideoPlayer.Content()')
        dbid = xbmc.getInfoLabel('VideoPlayer.DBID')
        tvshow_dbid = xbmc.getInfoLabel('VideoPlayer.TvShowDBID')

        if not content or not dbid:
            log("Plugin", "Player Cast: No video playing or missing DBID", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        content_type = content.rstrip('s')

        valid_types = ('movie', 'episode', 'musicvideo')
        if content_type not in valid_types:
            log("Plugin",
                f'Player Cast: Unsupported content type "{content_type}"',
                xbmc.LOGWARNING
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

        from lib.kodi.client import get_item_details, request

        aggregate = params.get('aggregate', ['false'])[0].lower() == 'true'

        if content_type == 'episode' and aggregate and tvshow_dbid:
            result = request(
                'VideoLibrary.GetEpisodes',
                {
                    'tvshowid': int(tvshow_dbid),
                    'properties': ['cast'],
                    'sort': {'method': 'episode', 'order': 'ascending'}
                }
            )
            items = extract_result(result, 'episodes', [])
            log("Plugin", f"Player Cast: Aggregating cast from entire show (DBID: {tvshow_dbid})", xbmc.LOGDEBUG)

        else:
            details = get_item_details(content_type, int(dbid), ['cast'])
            if not details:
                log("Plugin", f"Player Cast: No details for {content_type} {dbid}", xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return

            items = [details]
            log("Plugin", f"Player Cast: Getting cast for {content_type} {dbid}", xbmc.LOGDEBUG)

        if not items:
            log("Plugin", "Player Cast: No items found", xbmc.LOGINFO)
            xbmcplugin.endOfDirectory(handle, succeeded=True)
            return

        unique_cast = _deduplicate_cast(items)
        log("Plugin", f"Player Cast: Found {len(items)} items, deduplicated to {len(unique_cast)} unique cast", xbmc.LOGDEBUG)

        items_added = _create_cast_listitems(handle, unique_cast)

        log("Plugin", f"Player Cast: Created {items_added} ListItems", xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)

    except Exception as e:
        log("Plugin", f"Player Cast: Error - {e}", xbmc.LOGERROR)
        log("Plugin", traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
