"""Widget handlers for plugin content."""
from __future__ import annotations

import math
import random
import re
from typing import Optional

import xbmc
import xbmcgui
import xbmcplugin
from lib.kodi.client import request, batch_request, get_item_details, extract_result, ADDON

_FAVOURITE_TVSHOW = re.compile(r'videodb://tvshows/titles/(\d+)')

_EPISODE_PROPERTIES = ['title', 'season', 'episode', 'showtitle', 'plot', 'art', 'file',
                       'resume', 'runtime', 'firstaired', 'rating', 'userrating',
                       'playcount', 'lastplayed']

_SHOW_PROPERTIES = ['title', 'mpaa', 'studio', 'episode', 'watchedepisodes']

_FULL_SHOW_PROPERTIES = ['art', 'episode', 'watchedepisodes', 'title', 'plot', 'rating',
                         'userrating', 'year', 'premiered', 'playcount', 'votes', 'genre',
                         'studio', 'mpaa', 'cast', 'tag', 'dateadded', 'lastplayed',
                         'imdbnumber', 'originaltitle', 'season']

_MOVIE_PROPERTIES = ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                     'plot', 'tagline', 'runtime', 'genre', 'director', 'studio', 'mpaa',
                     'trailer', 'votes', 'tag', 'dateadded', 'lastplayed', 'resume']

_RECENT_WINDOW = {'field': 'dateadded', 'operator': 'inthelast', 'value': '365 days'}

_TAG_STOPLIST = frozenset({
    'duringcreditsstinger', 'aftercreditsstinger', 'woman director', 'sequel', 'remake',
    'based on novel or book', 'based on true story', 'based on comic',
    'based on young adult novel', 'live action remake',
    'amused', 'hilarious', 'suspenseful', 'absurd', 'awestruck', 'tense', 'fascinate',
    'emotional', 'sentimental', 'uplifting', 'entertaining', 'excited', 'admiring',
})

_TAG_WEIGHT = 8.0
_TAG_FULL_MATCH = 0.08
_SAME_SET_PENALTY = 12.0
_MAX_VOTE_LOG = math.log1p(1000000)

_SIMILAR_MOVIE_SCORING = ['genre', 'year', 'mpaa', 'tag', 'director', 'writer', 'studio',
                          'setid', 'rating', 'votes', 'playcount']

_SIMILAR_SHOW_SCORING = ['genre', 'year', 'mpaa', 'tag', 'studio', 'rating', 'votes',
                         'watchedepisodes']


def _set_episode_artwork_from_show(listitem: xbmcgui.ListItem, show_art: dict,
                                   episode_art: dict) -> None:
    """Set episode ListItem art using show artwork + episode thumb."""
    listitem.setArt({
        'poster': show_art.get('poster', ''),
        'fanart': show_art.get('fanart', ''),
        'clearlogo': show_art.get('clearlogo', '') or show_art.get('logo', ''),
        'banner': show_art.get('banner', ''),
        'landscape': show_art.get('landscape', ''),
        'clearart': show_art.get('clearart', ''),
        'thumb': episode_art.get('thumb', ''),
        'icon': 'DefaultTVShows.png'
    })


def _earliest_unwatched(tvshowid: int, season: Optional[int] = None) -> list:
    """Lowest-numbered unwatched episode of a show, restricted to one season when given."""
    params = {
        'tvshowid': tvshowid,
        'filter': {'field': 'playcount', 'operator': 'is', 'value': '0'},
        'properties': _EPISODE_PROPERTIES,
        'sort': {'method': 'episode', 'order': 'ascending'},
        'limits': {'start': 0, 'end': 1}
    }
    if season is not None:
        params['season'] = season
    return extract_result(request('VideoLibrary.GetEpisodes', params), 'episodes', [])


def _next_unwatched_episode(tvshowid: int) -> Optional[dict]:
    """Episode to watch next: earliest unwatched in the season last played, else earliest
    unwatched anywhere, so an untouched show starts at its first episode."""
    last_result = request('VideoLibrary.GetEpisodes', {
        'tvshowid': tvshowid,
        'filter': {
            'or': [
                {'field': 'inprogress', 'operator': 'true', 'value': ''},
                {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'}
            ]
        },
        'properties': ['season'],
        'sort': {'method': 'lastplayed', 'order': 'descending'},
        'limits': {'start': 0, 'end': 1}
    })
    last_played = extract_result(last_result, 'episodes', [])

    if last_played:
        episodes = _earliest_unwatched(tvshowid, last_played[0]['season'])
        if episodes:
            return episodes[0]

    episodes = _earliest_unwatched(tvshowid)
    return episodes[0] if episodes else None


def _show_art_from_episode(episode_art: dict) -> dict:
    """Parent show art, which Kodi mirrors onto every episode under `tvshow.*`."""
    return {key[7:]: value for key, value in episode_art.items() if key.startswith('tvshow.')}


def _episode_item_from_show(show: dict, episode: dict) -> xbmcgui.ListItem:
    """Episode ListItem carrying the parent show's art, certificate and studio."""
    listitem = _create_episode_listitem(episode)
    episode_art = episode.get('art', {})
    _set_episode_artwork_from_show(listitem, _show_art_from_episode(episode_art), episode_art)
    video_tag = listitem.getVideoInfoTag()
    if show.get('mpaa'):
        video_tag.setMpaa(show['mpaa'])
    if show.get('studio'):
        video_tag.setStudios(show['studio'])
    return listitem


def handle_next_up(handle: int, params: dict) -> None:
    """Plugin entry: next unwatched episode per in-progress show (`limit`, default 25)."""
    limit = int(params.get('limit', ['25'])[0])

    result = request('VideoLibrary.GetTVShows', {
        'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''},
        'properties': _SHOW_PROPERTIES,
        'sort': {'method': 'lastplayed', 'order': 'descending'},
        'limits': {'start': 0, 'end': limit}
    })
    shows = extract_result(result, 'tvshows', [])

    for show in shows:
        if show.get('episode', 0) <= show.get('watchedepisodes', 0):
            continue

        episode = _next_unwatched_episode(show['tvshowid'])
        if not episode:
            continue

        listitem = _episode_item_from_show(show, episode)
        xbmcplugin.addDirectoryItem(handle, episode['file'], listitem, False)

    xbmcplugin.setContent(handle, 'episodes')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _favourite_tvshow_ids() -> list:
    """TV show DBIDs pulled from the favourites list, in the order they were favourited."""
    result = request('Favourites.GetFavourites',
                     {'type': 'window', 'properties': ['windowparameter']})

    ids = []
    seen = set()
    for favourite in extract_result(result, 'favourites', []):
        match = _FAVOURITE_TVSHOW.search(favourite.get('windowparameter') or '')
        if not match:
            continue
        tvshowid = int(match.group(1))
        if tvshowid not in seen:
            seen.add(tvshowid)
            ids.append(tvshowid)
    return ids


def handle_next_up_favourites(handle: int, params: dict) -> None:
    """Plugin entry: next unwatched episode for each favourited TV show (`limit`, default 25)."""
    limit = int(params.get('limit', ['25'])[0])

    favourite_ids = _favourite_tvshow_ids()
    shows = {}
    for tvshowid in favourite_ids:
        details = get_item_details('tvshow', tvshowid, _SHOW_PROPERTIES)
        if details:
            details['tvshowid'] = tvshowid
            shows[tvshowid] = details

    added = 0
    for tvshowid in favourite_ids:
        if added >= limit:
            break

        show = shows.get(tvshowid)
        if not show or show.get('episode', 0) <= show.get('watchedepisodes', 0):
            continue

        episode = _next_unwatched_episode(tvshowid)
        if not episode:
            continue

        listitem = _episode_item_from_show(show, episode)
        xbmcplugin.addDirectoryItem(handle, episode['file'], listitem, False)
        added += 1

    xbmcplugin.setContent(handle, 'episodes')
    # favourites change without a library event, so a cached listing would go stale
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _recently_added(method: str, result_key: str, properties: list, limit: int) -> list:
    """Newest items by date added, from a recent window first and the whole library only when
    that window cannot fill the widget."""
    params = {
        'properties': properties,
        'sort': {'method': 'dateadded', 'order': 'descending'},
        'limits': {'start': 0, 'end': limit},
        'filter': _RECENT_WINDOW
    }
    items = extract_result(request(method, params), result_key, [])
    if len(items) >= limit:
        return items

    del params['filter']
    return extract_result(request(method, params), result_key, [])


def _recent_movie_rows(limit: int) -> list:
    """Recently added movies as `(dateadded, url, listitem, isfolder)` rows."""
    movies = _recently_added('VideoLibrary.GetMovies', 'movies', _MOVIE_PROPERTIES, limit)
    return [(movie.get('dateadded', ''), movie['file'],
             _dated(_create_movie_listitem(movie), movie.get('dateadded', '')), False)
            for movie in movies]


def _dated(listitem: xbmcgui.ListItem, added: str) -> xbmcgui.ListItem:
    """Stamp the added date a date-ordered widget sorts on, so skins can show it."""
    if added:
        listitem.getVideoInfoTag().setDateAdded(added)
    return listitem


def _collapsed_show_row(episodes: list, show_cache: dict) -> tuple:
    """One row for a show's recent episodes, collapsing a same-day batch add into a show
    folder."""
    newest = episodes[0]
    added = newest.get('dateadded', '')

    same_day = (len(episodes) > 1
                and added[:10] == episodes[1].get('dateadded', '')[:10]
                and added[:10])
    if same_day:
        tvshowid = newest['tvshowid']
        if tvshowid not in show_cache:
            detail = request('VideoLibrary.GetTVShowDetails',
                             {'tvshowid': tvshowid, 'properties': _FULL_SHOW_PROPERTIES})
            show_cache[tvshowid] = extract_result(detail, 'tvshowdetails', {})
        show = show_cache[tvshowid]
        if show:
            listitem = _dated(_create_tvshow_listitem(show), added)
            if show.get('season'):
                listitem.setProperty('TotalSeasons', str(show['season']))
            return (added, f"videodb://tvshows/titles/{tvshowid}/", listitem, True)

    return (added, newest['file'], _dated(_episode_item_from_show({}, newest), added), False)


def _recent_episode_rows(limit: int, group: bool) -> list:
    """Recently added episodes as `(dateadded, url, listitem, isfolder)` rows, one row per show
    when grouping."""
    episodes = _recently_added('VideoLibrary.GetEpisodes', 'episodes',
                               _EPISODE_PROPERTIES + ['dateadded', 'tvshowid'], limit)

    if not group:
        return [(episode.get('dateadded', ''), episode['file'],
                 _dated(_episode_item_from_show({}, episode), episode.get('dateadded', '')), False)
                for episode in episodes]

    by_show: dict = {}
    for episode in episodes:
        by_show.setdefault(episode.get('tvshowid'), []).append(episode)

    show_cache: dict = {}
    return [_collapsed_show_row(show_episodes, show_cache)
            for show_episodes in by_show.values()]


def handle_recent_videos(handle: int, params: dict) -> None:
    """Plugin entry: recently added movies and episodes interleaved by date; `group=false` lists
    every episode instead of one row per show."""
    limit = int(params.get('limit', ['25'])[0])
    group = params.get('group', ['true'])[0].lower() != 'false'

    rows = _recent_movie_rows(limit) + _recent_episode_rows(limit, group)
    rows.sort(key=lambda row: row[0], reverse=True)

    for _, url, listitem, isfolder in rows[:limit]:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle)


def _create_episode_listitem(episode: dict) -> xbmcgui.ListItem:
    """Create an episode ListItem labeled `2x05. Title` (or `S05. Title` for specials)."""
    season = episode.get('season', 0)
    ep_num = episode.get('episode', 0)
    title = episode.get('title', '')

    if ep_num < 10:
        ep_label = f"0{ep_num}. {title}"
    else:
        ep_label = f"{ep_num}. {title}"

    if season == 0:
        label = f"S{ep_label}"
    else:
        label = f"{season}x{ep_label}"

    listitem = xbmcgui.ListItem(label, offscreen=True)

    video_tag = listitem.getVideoInfoTag()
    video_tag.setTitle(title)

    episodeid = episode.get('episodeid')
    if episodeid:
        video_tag.setDbId(episodeid)
    video_tag.setEpisode(ep_num)
    video_tag.setSeason(season)
    video_tag.setTvShowTitle(episode.get('showtitle', ''))
    video_tag.setPlot(episode.get('plot', ''))
    video_tag.setFirstAired(episode.get('firstaired', ''))

    rating = episode.get('rating', 0.0)
    video_tag.setRating(float(rating) if rating else 0.0)

    userrating = episode.get('userrating', 0)
    video_tag.setUserRating(int(userrating) if userrating else 0)

    playcount = episode.get('playcount', 0)
    video_tag.setPlaycount(int(playcount) if playcount else 0)

    video_tag.setLastPlayed(episode.get('lastplayed', ''))

    runtime = episode.get('runtime', 0)
    video_tag.setDuration(int(runtime) if runtime else 0)

    video_tag.setMediaType('episode')

    resume = episode.get('resume', {})
    if isinstance(resume, dict):
        resume_position = resume.get('position', 0)
        resume_total = resume.get('total', 0)
        if resume_position > 0 and resume_total > 0:
            video_tag.setResumePoint(resume_position, resume_total)

    return listitem


def handle_recent_episodes_grouped(handle: int, params: dict) -> None:
    """Plugin entry: recently-added episodes, grouped so new series collapse into one folder;
    `include_watched=true` disables the in-progress filter."""
    limit = int(params.get('limit', ['25'])[0])
    include_watched = params.get('include_watched', ['false'])[0].lower() == 'true'

    tvshow_filter = None if include_watched else {
        'field': 'playcount',
        'operator': 'lessthan',
        'value': '1'
    }

    result = request('VideoLibrary.GetTVShows', {
        'filter': tvshow_filter,
        'properties': _FULL_SHOW_PROPERTIES,
        'sort': {'method': 'dateadded', 'order': 'descending'},
        'limits': {'start': 0, 'end': limit}
    })
    shows = extract_result(result, 'tvshows', [])

    items = []
    for show in shows:
        unwatched_count = show.get('episode', 0) - show.get('watchedepisodes', 0)

        if unwatched_count == 1:
            ep_result = request('VideoLibrary.GetEpisodes', {
                'tvshowid': show['tvshowid'],
                'filter': {'field': 'playcount', 'operator': 'is', 'value': '0'},
                'properties': _EPISODE_PROPERTIES,
                'sort': {'method': 'dateadded', 'order': 'descending'},
                'limits': {'start': 0, 'end': 1}
            })
            episodes = extract_result(ep_result, 'episodes', [])

            if episodes:
                episode = episodes[0]
                listitem = _create_episode_listitem(episode)
                _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
                if show.get('season'):
                    listitem.setProperty('TotalSeasons', str(show['season']))
                items.append((episode['file'], listitem, False))

        elif include_watched:
            recent_result = request('VideoLibrary.GetEpisodes', {
                'tvshowid': show['tvshowid'],
                'properties': ['dateadded', 'title', 'season', 'episode', 'showtitle',
                              'plot', 'art', 'file', 'resume', 'runtime', 'firstaired',
                              'rating', 'userrating', 'playcount', 'lastplayed'],
                'sort': {'method': 'dateadded', 'order': 'descending'},
                'limits': {'start': 0, 'end': 2}
            })
            recent_eps = extract_result(recent_result, 'episodes', [])

            if len(recent_eps) >= 2:
                date1 = recent_eps[0].get('dateadded', '').split('T')[0]
                date2 = recent_eps[1].get('dateadded', '').split('T')[0]

                if date1 == date2:
                    listitem = _create_tvshow_listitem(show)
                    if show.get('season'):
                        listitem.setProperty('TotalSeasons', str(show['season']))
                    show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
                    items.append((show_url, listitem, True))
                else:
                    episode = recent_eps[0]
                    listitem = _create_episode_listitem(episode)
                    _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
                    if show.get('season'):
                        listitem.setProperty('TotalSeasons', str(show['season']))
                    items.append((episode['file'], listitem, False))
            elif recent_eps:
                episode = recent_eps[0]
                listitem = _create_episode_listitem(episode)
                _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
                if show.get('season'):
                    listitem.setProperty('TotalSeasons', str(show['season']))
                items.append((episode['file'], listitem, False))
        else:
            listitem = _create_tvshow_listitem(show)
            if show.get('season'):
                listitem.setProperty('TotalSeasons', str(show['season']))
            show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
            items.append((show_url, listitem, True))

    for url, listitem, isfolder in items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.setContent(handle, 'tvshows')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _create_tvshow_listitem(show: dict) -> xbmcgui.ListItem:
    """Create a TV show ListItem from a JSON-RPC show dict."""
    title = show.get('title', '')
    listitem = xbmcgui.ListItem(title, offscreen=True)

    video_tag = listitem.getVideoInfoTag()
    video_tag.setTitle(title)
    video_tag.setMediaType('tvshow')

    tvshowid = show.get('tvshowid')
    if tvshowid:
        video_tag.setDbId(tvshowid)

    plot = show.get('plot', '')
    if plot:
        video_tag.setPlot(plot)

    rating = show.get('rating', 0.0)
    if rating:
        video_tag.setRating(float(rating))

    userrating = show.get('userrating', 0)
    if userrating:
        video_tag.setUserRating(int(userrating))

    votes = show.get('votes', 0)
    if votes:
        votes_int = int(votes) if isinstance(votes, (int, str)) and str(votes).isdigit() else 0
        video_tag.setVotes(votes_int)

    year = show.get('year', 0)
    if year:
        video_tag.setYear(int(year))

    premiered = show.get('premiered', '')
    if premiered:
        video_tag.setPremiered(premiered)

    playcount = show.get('playcount', 0)
    if playcount:
        video_tag.setPlaycount(int(playcount))

    lastplayed = show.get('lastplayed', '')
    if lastplayed:
        video_tag.setLastPlayed(lastplayed)

    genres = show.get('genre', [])
    if genres:
        video_tag.setGenres(genres if isinstance(genres, list) else [genres])

    studios = show.get('studio', [])
    if studios:
        video_tag.setStudios(studios if isinstance(studios, list) else [studios])

    mpaa = show.get('mpaa', '')
    if mpaa:
        video_tag.setMpaa(mpaa)

    cast_list = show.get('cast', [])
    if cast_list:
        video_tag.setCast([
            xbmc.Actor(
                member.get('name', ''),
                member.get('role', ''),
                member.get('order', 0),
                member.get('thumbnail', '')
            )
            for member in cast_list
        ])

    tags = show.get('tag', [])
    if tags:
        video_tag.setTags(tags if isinstance(tags, list) else [tags])

    originaltitle = show.get('originaltitle', '')
    if originaltitle:
        video_tag.setOriginalTitle(originaltitle)

    imdbnumber = show.get('imdbnumber', '')
    if imdbnumber:
        video_tag.setIMDBNumber(imdbnumber)

    episode_count = show.get('episode', 0)
    watched_episodes = show.get('watchedepisodes', 0)
    unwatched_episodes = episode_count - watched_episodes
    # integer math, not round(), to match Kodi's own WatchedEpisodePercent
    watched_percent = (watched_episodes * 100) // episode_count if episode_count > 0 else 0
    listitem.setProperty('TotalEpisodes', str(episode_count))
    listitem.setProperty('WatchedEpisodes', str(watched_episodes))
    listitem.setProperty('UnWatchedEpisodes', str(unwatched_episodes))
    listitem.setProperty('WatchedEpisodePercent', str(watched_percent))

    listitem.setArt(show.get('art', {}))

    return listitem


def _find_actor_role(cast: list, actor_name: str) -> str:
    """Return the actor's role/character from a JSON-RPC cast list, or '' if not found."""
    for member in cast:
        if member.get('name') == actor_name:
            return member.get('role', '') or ''
    return ''


def handle_by_actor(handle: int, params: dict) -> None:
    """Plugin entry: library items featuring a random actor from the source item; `mix` picks
    movies+shows or matches `dbtype`, `lock` keeps the actor stable across refreshes."""
    dbid_param = params.get('dbid', [''])[0]
    if not dbid_param:
        xbmcplugin.endOfDirectory(handle)
        return

    dbid = int(dbid_param)
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])
    cast_limit = int(params.get('cast_limit', ['4'])[0])
    mix = params.get('mix', ['true'])[0].lower() == 'true'
    lock = params.get('lock', ['false'])[0].lower() == 'true'

    from lib.kodi.client import log

    window = xbmcgui.Window(10000)
    lock_property_actor = 'SkinInfoService.ByActor.Lock'
    lock_property_dbid = 'SkinInfoService.ByActor.Lock.DbId'

    if lock:
        locked_dbid = window.getProperty(lock_property_dbid)
        locked_actor = window.getProperty(lock_property_actor)

        if locked_dbid == str(dbid) and locked_actor:
            actor = locked_actor
            log('Plugin', f"by_actor: Using locked actor '{actor}' for dbid={dbid}", xbmc.LOGINFO)
        else:
            item = get_item_details(dbtype, dbid, ['cast', 'title'])
            if not item or not item.get('cast'):
                xbmcplugin.endOfDirectory(handle)
                return

            if cast_limit > 0:
                top_cast = item['cast'][:cast_limit]
            else:
                top_cast = item['cast']

            actor = random.choice(top_cast)['name']
            window.setProperty(lock_property_actor, actor)
            window.setProperty(lock_property_dbid, str(dbid))
            log('Plugin', f"by_actor: Picked and locked actor '{actor}' for dbid={dbid}",
                xbmc.LOGINFO)
    else:
        window.clearProperty(lock_property_actor)
        window.clearProperty(lock_property_dbid)
        item = get_item_details(dbtype, dbid, ['cast', 'title'])

        if not item or not item.get('cast'):
            xbmcplugin.endOfDirectory(handle)
            return

        if cast_limit > 0:
            top_cast = item['cast'][:cast_limit]
        else:
            top_cast = item['cast']

        actor = random.choice(top_cast)['name']

    all_items = []

    if mix or dbtype in ('movie', 'set'):
        movie_result = request('VideoLibrary.GetMovies', {
            'filter': {'actor': actor},
            'properties': _MOVIE_PROPERTIES + ['cast'],
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        movies = extract_result(movie_result, 'movies', [])

        for movie in movies:
            if movie.get('movieid') != dbid or dbtype != 'movie':
                listitem = _create_movie_listitem(movie)
                role = _find_actor_role(movie.get('cast', []), actor)
                if role:
                    listitem.setProperty('Role', role)
                all_items.append((movie['file'], listitem, False))

    if mix or dbtype in ('tvshow', 'season', 'episode'):
        show_result = request('VideoLibrary.GetTVShows', {
            'filter': {'actor': actor},
            'properties': _FULL_SHOW_PROPERTIES,
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        shows = extract_result(show_result, 'tvshows', [])

        for show in shows:
            if show.get('tvshowid') != dbid or dbtype != 'tvshow':
                listitem = _create_tvshow_listitem(show)
                role = _find_actor_role(show.get('cast', []), actor)
                if role:
                    listitem.setProperty('Role', role)
                show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
                all_items.append((show_url, listitem, True))

    random.shuffle(all_items)

    for url, listitem, isfolder in all_items:
        listitem.setProperty('Actor', actor)
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    if mix:
        xbmcplugin.setContent(handle, 'videos')
    elif dbtype in ('movie', 'set'):
        xbmcplugin.setContent(handle, 'movies')
    else:
        xbmcplugin.setContent(handle, 'tvshows')
    xbmcplugin.endOfDirectory(handle)


def _create_movie_listitem(movie: dict) -> xbmcgui.ListItem:
    """Create a movie ListItem from a JSON-RPC movie dict."""
    title = movie.get('title', '')
    listitem = xbmcgui.ListItem(title, offscreen=True)

    video_tag = listitem.getVideoInfoTag()
    video_tag.setTitle(title)
    video_tag.setMediaType('movie')

    movieid = movie.get('movieid')
    if movieid:
        video_tag.setDbId(movieid)

    plot = movie.get('plot', '')
    if plot:
        video_tag.setPlot(plot)

    rating = movie.get('rating', 0.0)
    if rating:
        video_tag.setRating(float(rating))

    userrating = movie.get('userrating', 0)
    if userrating:
        video_tag.setUserRating(int(userrating))

    votes = movie.get('votes', 0)
    if votes:
        votes_int = int(votes) if isinstance(votes, (int, str)) and str(votes).isdigit() else 0
        video_tag.setVotes(votes_int)

    year = movie.get('year', 0)
    if year:
        video_tag.setYear(int(year))

    playcount = movie.get('playcount', 0)
    if playcount:
        video_tag.setPlaycount(int(playcount))

    lastplayed = movie.get('lastplayed', '')
    if lastplayed:
        video_tag.setLastPlayed(lastplayed)

    runtime = movie.get('runtime', 0)
    if runtime:
        video_tag.setDuration(int(runtime))

    genres = movie.get('genre', [])
    if genres:
        video_tag.setGenres(genres if isinstance(genres, list) else [genres])

    directors = movie.get('director', [])
    if directors:
        video_tag.setDirectors(directors if isinstance(directors, list) else [directors])

    studios = movie.get('studio', [])
    if studios:
        video_tag.setStudios(studios if isinstance(studios, list) else [studios])

    mpaa = movie.get('mpaa', '')
    if mpaa:
        video_tag.setMpaa(mpaa)

    tagline = movie.get('tagline', '')
    if tagline:
        video_tag.setTagLine(tagline)

    trailer = movie.get('trailer', '')
    if trailer:
        video_tag.setTrailer(trailer)

    tags = movie.get('tag', [])
    if tags:
        video_tag.setTags(tags if isinstance(tags, list) else [tags])

    resume = movie.get('resume', {})
    if isinstance(resume, dict):
        resume_position = resume.get('position', 0)
        resume_total = resume.get('total', 0)
        if resume_position > 0 and resume_total > 0:
            video_tag.setResumePoint(resume_position, resume_total)

    listitem.setArt(movie.get('art', {}))

    return listitem


def handle_by_director(handle: int, params: dict) -> None:
    """Plugin entry: library items by a random director from the source item; `mix` returns
    mixed movies+episodes or matches `dbtype`."""
    dbid_param = params.get('dbid', [''])[0]
    if not dbid_param:
        xbmcplugin.endOfDirectory(handle)
        return

    dbid = int(dbid_param)
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])
    director_limit = int(params.get('director_limit', ['3'])[0])
    mix = params.get('mix', ['true'])[0].lower() == 'true'

    if dbtype in ('tvshow', 'set'):  # neither has a director field
        xbmcplugin.endOfDirectory(handle)
        return

    item = get_item_details(dbtype, dbid, ['director', 'title'])

    if not item or not item.get('director'):
        xbmcplugin.endOfDirectory(handle)
        return

    directors = item['director']
    if not isinstance(directors, list):
        directors = [directors]

    if director_limit > 0:
        top_directors = directors[:director_limit]
    else:
        top_directors = directors

    director = random.choice(top_directors)

    all_items = []

    if mix or dbtype in ('movie', 'set'):
        movie_result = request('VideoLibrary.GetMovies', {
            'filter': {'field': 'director', 'operator': 'is', 'value': director},
            'properties': _MOVIE_PROPERTIES,
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        movies = extract_result(movie_result, 'movies', [])

        for movie in movies:
            if movie.get('movieid') != dbid or dbtype != 'movie':
                listitem = _create_movie_listitem(movie)
                all_items.append((movie['file'], listitem, False))

    if mix or dbtype == 'episode':
        episode_result = request('VideoLibrary.GetEpisodes', {
            'filter': {'field': 'director', 'operator': 'is', 'value': director},
            'properties': _EPISODE_PROPERTIES,
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        episodes = extract_result(episode_result, 'episodes', [])

        for episode in episodes:
            if episode.get('episodeid') != dbid or dbtype != 'episode':
                episode_art = episode.get('art', {})
                listitem = _create_episode_listitem(episode)
                _set_episode_artwork_from_show(listitem, _show_art_from_episode(episode_art),
                                               episode_art)
                all_items.append((episode['file'], listitem, False))

    random.shuffle(all_items)

    for url, listitem, isfolder in all_items:
        listitem.setProperty('Director', director)
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    if mix:
        xbmcplugin.setContent(handle, 'videos')
    elif dbtype in ('movie', 'set'):
        xbmcplugin.setContent(handle, 'movies')
    else:
        xbmcplugin.setContent(handle, 'episodes')
    xbmcplugin.endOfDirectory(handle)


def _int_param(params: dict, name: str, default: int) -> int:
    """Read an integer plugin argument, falling back to the default on anything unparseable."""
    try:
        return int(params.get(name, [str(default)])[0])
    except (ValueError, TypeError):
        return default


def _vote_count(item: dict) -> float:
    """Vote count as a number; Kodi returns it as a grouped string."""
    raw = item.get('votes')
    if isinstance(raw, (int, float)):
        return float(raw)
    digits = re.sub(r'[^0-9]', '', str(raw or ''))
    return float(digits) if digits else 0.0


def _as_set(value) -> set:
    """Coerce a Kodi field that may be a list, a bare string or absent into a set."""
    if isinstance(value, list):
        return {v for v in value if v}
    return {value} if value else set()


def _similar_tag_weights(rows: list) -> dict:
    """Inverse document frequency per tag over the candidate pool, so common tags count least."""
    counts: dict = {}
    for row in rows:
        for tag in _as_set(row.get('tag')) - _TAG_STOPLIST:
            counts[tag] = counts.get(tag, 0) + 1

    total = max(len(rows), 1)
    return {tag: math.log(total / seen) for tag, seen in counts.items()}


def _tag_norm(tags: set, weights: dict) -> float:
    """Euclidean norm of a tag set under the IDF weights, for cosine similarity."""
    return math.sqrt(sum(weights.get(t, 0.0) ** 2 for t in tags)) or 1.0


def _similar_tier_score(seed: dict, cand: dict, weights: dict) -> float:
    """Rank a candidate against the seed within its genre tier; never large enough to cross one."""
    shared = seed['tags'] & cand['tags']
    if shared:
        cosine = sum(weights.get(t, 0.0) for t in shared) / (seed['norm'] * cand['norm'])
        score = _TAG_WEIGHT * min(1.0, cosine / _TAG_FULL_MATCH)
    else:
        score = 0.0

    if seed['directors'] & cand['directors']:
        score += 1.5
    if seed['writers'] & cand['writers']:
        score += 0.9
    if seed['studios'] & cand['studios']:
        score += 0.4

    if seed['year'] and cand.get('year'):
        gap = abs(seed['year'] - cand['year'])
        score += 1.5 if gap <= 5 else 1.0 if gap <= 10 else 0.5 if gap <= 20 else 0.0

    if seed['certificate'][1] and seed['certificate'] == cand['certificate']:
        score += 0.6

    # Kodi surfaces sets of its own
    if seed['setid'] and seed['setid'] == cand.get('setid'):
        score -= _SAME_SET_PENALTY

    score += 1.5 * min(1.0, math.log1p(_vote_count(cand)) / _MAX_VOTE_LOG)
    return score + 0.15 * (cand.get('rating') or 0.0)


def _similar_pool(target_dbtype: str, genres: list, path: str) -> list:
    """Every candidate the seed could match, from an XSP path when given, else by shared genre."""
    properties = (_SIMILAR_MOVIE_SCORING if target_dbtype == 'movie'
                  else _SIMILAR_SHOW_SCORING)

    if path:
        result = request('Files.GetDirectory',
                         {'directory': path, 'media': 'video', 'properties': properties})
        rows = extract_result(result, 'files', [])
        id_field = 'movieid' if target_dbtype == 'movie' else 'tvshowid'
        for row in rows:
            row[id_field] = row.get('id', 0)
        return rows

    genre_filter = {'field': 'genre', 'operator': 'is', 'value': genres}
    if target_dbtype == 'movie':
        result = request('VideoLibrary.GetMovies',
                         {'filter': genre_filter, 'properties': properties})
        return extract_result(result, 'movies', [])

    result = request('VideoLibrary.GetTVShows',
                     {'filter': genre_filter, 'properties': properties})
    return extract_result(result, 'tvshows', [])


def _watch_state_wanted(row: dict, target_dbtype: str, wanted: str) -> bool:
    """True when a candidate's watch state matches the requested `watched` filter."""
    if wanted not in ('watched', 'unwatched'):
        return True

    # a show's playcount only turns 1 once every episode is watched
    seen = (row.get('playcount') or 0) if target_dbtype == 'movie' else (
        row.get('watchedepisodes') or 0)
    return bool(seen) if wanted == 'watched' else not seen


def _similar_seed(dbtype: str, dbid: int, tmdb_id_param: str) -> dict:
    """Resolve the seed's scoring fields from the library, falling back to TMDB genres."""
    seed = {'genres': [], 'year': 0, 'mpaa': '', 'tags': set(), 'directors': set(),
            'writers': set(), 'studios': set(), 'setid': 0}

    if dbid and dbtype != 'set':
        properties = (_SIMILAR_MOVIE_SCORING if dbtype == 'movie'
                      else _SIMILAR_SHOW_SCORING)
        item = get_item_details(dbtype, dbid, properties)
        if item:
            seed['genres'] = list(_as_set(item.get('genre')))
            _fill_seed_fields(seed, item)

    if not seed['genres'] and tmdb_id_param and dbtype in ('movie', 'tvshow'):
        try:
            tmdb_id = int(tmdb_id_param)
        except (ValueError, TypeError):
            tmdb_id = 0
        if tmdb_id:
            from lib.data.api.tmdb import ApiTmdb
            data = ApiTmdb().get_complete_data(dbtype, tmdb_id)
            if data:
                seed['genres'] = [g.get('name', '') for g in (data.get('genres') or [])
                                  if g.get('name')]
                released = data.get('release_date') or data.get('first_air_date') or ''
                if len(released) >= 4 and released[:4].isdigit():
                    seed['year'] = int(released[:4])

    return seed


def _fill_seed_fields(seed: dict, item: dict) -> None:
    """Copy the scoring fields shared by movies and shows off a resolved seed item."""
    seed['year'] = item.get('year', 0)
    seed['mpaa'] = item.get('mpaa', '')
    seed['tags'] = _as_set(item.get('tag')) - _TAG_STOPLIST
    seed['directors'] = _as_set(item.get('director'))
    seed['writers'] = _as_set(item.get('writer'))
    seed['studios'] = _as_set(item.get('studio'))
    seed['setid'] = item.get('setid', 0)


def handle_similar(handle: int, params: dict) -> None:
    """Plugin entry: movies or shows similar to the source, ranked by shared genre count first
    and then by tag, crew, era, certificate and popularity; `watched` filters by watch state
    and `path` scores inside an XSP pool instead of the whole library."""
    dbid_param = params.get('dbid', [''])[0]
    tmdb_id_param = params.get('tmdb_id', [''])[0]
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = _int_param(params, 'limit', 25)
    wanted = params.get('watched', ['both'])[0].lower()
    path = params.get('path', [''])[0]

    if dbtype not in ('movie', 'set', 'tvshow') or (not dbid_param and not tmdb_id_param):
        xbmcplugin.endOfDirectory(handle)
        return

    try:
        dbid = int(dbid_param) if dbid_param else 0
    except (ValueError, TypeError):
        dbid = 0

    from lib.kodi.utilities import normalize_certificate

    seed = _similar_seed(dbtype, dbid, tmdb_id_param)
    if not seed['genres']:
        xbmcplugin.endOfDirectory(handle)
        return

    target_dbtype = 'movie' if dbtype in ('movie', 'set') else 'tvshow'
    id_field = 'movieid' if target_dbtype == 'movie' else 'tvshowid'

    candidates = _similar_pool(target_dbtype, seed['genres'], path)
    weights = _similar_tag_weights(candidates)
    seed['norm'] = _tag_norm(seed['tags'], weights)
    seed['certificate'] = normalize_certificate(seed['mpaa'])
    seed_genres = set(seed['genres'])

    ranked = []
    for cand in candidates:
        if cand.get(id_field) == dbid:
            continue
        if not _watch_state_wanted(cand, target_dbtype, wanted):
            continue

        overlap = len(seed_genres & _as_set(cand.get('genre')))
        if not overlap:
            continue

        cand['tags'] = _as_set(cand.get('tag')) - _TAG_STOPLIST
        cand['directors'] = _as_set(cand.get('director'))
        cand['writers'] = _as_set(cand.get('writer'))
        cand['studios'] = _as_set(cand.get('studio'))
        cand['certificate'] = normalize_certificate(cand.get('mpaa'))
        cand['norm'] = _tag_norm(cand['tags'], weights)
        ranked.append((overlap, _similar_tier_score(seed, cand, weights), cand[id_field]))

    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    item_ids = [row[2] for row in ranked[:limit]]
    if not item_ids:
        xbmcplugin.endOfDirectory(handle)
        return

    if target_dbtype == 'movie':
        method, result_key = 'VideoLibrary.GetMovieDetails', 'moviedetails'
        detail_properties = _MOVIE_PROPERTIES
    else:
        method, result_key = 'VideoLibrary.GetTVShowDetails', 'tvshowdetails'
        detail_properties = _FULL_SHOW_PROPERTIES

    details = batch_request([
        {'method': method, 'params': {id_field: item_id, 'properties': detail_properties}}
        for item_id in item_ids
    ])

    for item_id, detail in zip(item_ids, details):
        full = extract_result(detail, result_key, {})
        if not full:
            continue
        full[id_field] = item_id
        if target_dbtype == 'movie':
            xbmcplugin.addDirectoryItem(handle, full.get('file', ''),
                                        _create_movie_listitem(full), False)
        else:
            xbmcplugin.addDirectoryItem(handle, f"videodb://tvshows/titles/{item_id}/",
                                        _create_tvshow_listitem(full), True)

    xbmcplugin.setContent(handle, 'movies' if target_dbtype == 'movie' else 'tvshows')
    xbmcplugin.endOfDirectory(handle, succeeded=True)
def _fetch_unwatched(dbtype: str, genre_filter: dict) -> list:
    """Unwatched movies and shows for a genre, each tagged with its media type."""
    candidates = []
    if dbtype in ('movie', 'both'):
        result = request('VideoLibrary.GetMovies', {
            'filter': {'and': [{'field': 'playcount', 'operator': 'is', 'value': '0'},
                               genre_filter]},
            'properties': ['genre', 'year', 'mpaa', 'rating', 'director'],
        })
        for movie in extract_result(result, 'movies', []):
            movie['_mtype'] = 'movie'
            candidates.append(movie)
    if dbtype in ('tvshow', 'both'):
        result = request('VideoLibrary.GetTVShows', {
            'filter': {'and': [{'field': 'numwatched', 'operator': 'is', 'value': '0'},
                               genre_filter]},
            'properties': ['genre', 'year', 'mpaa', 'rating'],
        })
        for show in extract_result(result, 'tvshows', []):
            show['_mtype'] = 'tvshow'
            candidates.append(show)
    return candidates


def _top_rated_unwatched(dbtype: str, count: int, mpaa: str = '') -> list:
    """Top-rated unwatched titles for padding a sparse single-seed widget, certificate-matched
    to the seed so padding stays related to it."""
    def _filter(field: str) -> dict:
        unwatched = {'field': field, 'operator': 'is', 'value': '0'}
        if mpaa:
            return {'and': [unwatched,
                            {'field': 'mpaarating', 'operator': 'is', 'value': mpaa}]}
        return unwatched

    extra = []
    if dbtype in ('movie', 'both'):
        result = request('VideoLibrary.GetMovies', {
            'filter': _filter('playcount'),
            'properties': ['rating'], 'sort': {'method': 'rating', 'order': 'descending'},
            'limits': {'start': 0, 'end': count},
        })
        for movie in extract_result(result, 'movies', []):
            movie['_mtype'] = 'movie'
            extra.append(movie)
    if dbtype in ('tvshow', 'both'):
        result = request('VideoLibrary.GetTVShows', {
            'filter': _filter('numwatched'),
            'properties': ['rating'], 'sort': {'method': 'rating', 'order': 'descending'},
            'limits': {'start': 0, 'end': count},
        })
        for show in extract_result(result, 'tvshows', []):
            show['_mtype'] = 'tvshow'
            extra.append(show)
    return extra


def _render_recommended(handle: int, scored_items: list, based_on_label: str, dbtype: str) -> None:
    """Turn the chosen picks into directory items, tagged with their seed title and the
    "based on" header label."""

    all_items = []
    for item_data, based_on_raw in scored_items:
        if item_data['_mtype'] == 'movie':
            item_id = item_data['movieid']
            detail = request('VideoLibrary.GetMovieDetails',
                             {'movieid': item_id, 'properties': _MOVIE_PROPERTIES + ['cast']})
            full = extract_result(detail, 'moviedetails', {})
            if not full:
                continue
            full['movieid'] = item_id
            listitem = _create_movie_listitem(full)
            listitem.setProperty('BasedOn', based_on_raw)
            if based_on_label:
                listitem.setProperty('BasedOnLabel', based_on_label)
            all_items.append((full.get('file', ''), listitem, False))
        else:
            item_id = item_data['tvshowid']
            detail = request('VideoLibrary.GetTVShowDetails',
                             {'tvshowid': item_id, 'properties': _FULL_SHOW_PROPERTIES})
            full = extract_result(detail, 'tvshowdetails', {})
            if not full:
                continue
            full['tvshowid'] = item_id
            listitem = _create_tvshow_listitem(full)
            listitem.setProperty('BasedOn', based_on_raw)
            if based_on_label:
                listitem.setProperty('BasedOnLabel', based_on_label)
            if full.get('season'):
                listitem.setProperty('TotalSeasons', str(full['season']))
            all_items.append((f"videodb://tvshows/titles/{item_id}/", listitem, True))

    for url, listitem, isfolder in all_items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    if dbtype == 'movie':
        xbmcplugin.setContent(handle, 'movies')
    elif dbtype == 'tvshow':
        xbmcplugin.setContent(handle, 'tvshows')
    else:
        xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _recommend_single(handle: int, history: list, dbtype: str, limit: int,
                      min_rating: float, strict_rating: bool) -> None:
    """Recommend unwatched titles most like the single most recent watch (genre, tone,
    director, era); pads with top-rated unwatched so it isn't sparse, with a
    truthful "Based on <that movie>" header."""
    seed = None
    seed_set: frozenset = frozenset()
    for entry in history:  # first recent watch that actually has genres
        eg = entry.get('genre', [])
        if not isinstance(eg, list):
            eg = [eg] if eg else []
        if eg:
            seed, seed_set = entry, frozenset(eg)
            break
    if seed is None:
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    seed_title = seed.get('title', '')

    seed_mpaa = seed.get('mpaa', '')
    seed_year = seed.get('year', 0)
    sd = seed.get('director', [])
    seed_directors = set(sd if isinstance(sd, list) else [sd] if sd else [])

    genre_filters = [{'field': 'genre', 'operator': 'contains', 'value': g} for g in seed_set]
    genre_filter = {'or': genre_filters} if len(genre_filters) > 1 else genre_filters[0]

    scored = []
    for c in _fetch_unwatched(dbtype, genre_filter):
        cg = c.get('genre', [])
        if not isinstance(cg, list):
            cg = [cg] if cg else []
        cset = frozenset(cg)
        if not cset or c.get('rating', 0.0) < min_rating:
            continue
        cmpaa = c.get('mpaa', '')
        if strict_rating and cmpaa != seed_mpaa:
            continue
        inter = len(cset & seed_set)
        if not inter:
            continue
        # score vs the one seed only (genre, tone, director, era), not a history blend
        score = inter / len(cset | seed_set)
        if cmpaa and cmpaa == seed_mpaa:
            score += 0.25
        cd = c.get('director', [])
        if not isinstance(cd, list):
            cd = [cd] if cd else []
        if seed_directors.intersection(cd):
            score += 0.30
        cyear = c.get('year', 0)
        if cyear and seed_year:
            yd = abs(cyear - seed_year)
            if yd <= 5:
                score += 0.15
            elif yd <= 15:
                score += 0.06
        score *= random.uniform(0.95, 1.05)  # light jitter so it rotates between refreshes
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    picks = [c for _, c in scored[:limit]]

    if len(picks) < limit:  # niche seed: pad so the widget isn't sparse
        have = {(c['_mtype'], c.get('movieid') or c.get('tvshowid')) for c in picks}

        def _pad_from(pool: list) -> None:
            for extra in pool:
                if len(picks) >= limit:
                    return
                eid = (extra['_mtype'], extra.get('movieid') or extra.get('tvshowid'))
                if eid not in have:
                    have.add(eid)
                    picks.append(extra)

        if seed_mpaa:  # same-tone first so padding stays related to the seed
            _pad_from(_top_rated_unwatched(dbtype, limit * 2, seed_mpaa))
        if len(picks) < limit:
            _pad_from(_top_rated_unwatched(dbtype, limit * 2))

    scored_items = [(c, seed_title) for c in picks]
    label = ADDON.getLocalizedString(32651).format(seed_title) if seed_title else ''
    _render_recommended(handle, scored_items, label, dbtype)


def handle_recommended(handle: int, params: dict) -> None:
    """Plugin entry: recommendations from recent watch history; default is single-seed (most
    like the last watch), `multi=true` blends across `history_size` watches with
    recency-weighted per-watch fill, `strict_rating`/`min_rating` filter tone/quality."""
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])
    strict_rating = params.get('strict_rating', ['false'])[0].lower() == 'true'
    min_rating = float(params.get('min_rating', ['6.0'])[0])
    history_size = int(params.get('history_size', ['10'])[0])
    recency_decay = min(1.0, max(0.0, float(params.get('recency', ['0.75'])[0])))
    multi = params.get('multi', ['false'])[0].lower() == 'true'

    history = []

    if dbtype in ('movie', 'both'):
        movie_history = request('VideoLibrary.GetMovies', {
            'filter': {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'},
            'properties': ['title', 'genre', 'year', 'mpaa', 'rating', 'director',
                           'lastplayed'],
            'sort': {'method': 'lastplayed', 'order': 'descending'},
            'limits': {'start': 0, 'end': history_size}
        })
        movies = extract_result(movie_history, 'movies', [])
        history.extend(movies)

    if dbtype in ('tvshow', 'both'):
        # tvshow playcount only turns 1 once every episode is watched, numwatched is per episode
        show_history = request('VideoLibrary.GetTVShows', {
            'filter': {'field': 'numwatched', 'operator': 'greaterthan', 'value': '0'},
            'properties': ['title', 'genre', 'year', 'mpaa', 'rating', 'lastplayed'],
            'sort': {'method': 'lastplayed', 'order': 'descending'},
            'limits': {'start': 0, 'end': history_size}
        })
        shows = extract_result(show_history, 'tvshows', [])
        history.extend(shows)

    if not history:
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    history.sort(key=lambda x: x.get('lastplayed', ''), reverse=True)
    history = history[:history_size]

    if not multi:
        _recommend_single(handle, history, dbtype, limit, min_rating, strict_rating)
        return

    watched_sets = []  # title seeds the BasedOn label
    all_watched_genres = set()
    mpaa_counts = {}
    years = []
    directors = {}

    for idx, item in enumerate(history):
        weight = recency_decay ** idx  # exponential recency: last few watches dominate

        item_genres = item.get('genre', [])
        if not isinstance(item_genres, list):
            item_genres = [item_genres] if item_genres else []
        gset = frozenset(item_genres)
        if gset:
            watched_sets.append((gset, weight, item.get('title', '')))
            all_watched_genres |= gset

        mpaa = item.get('mpaa', '')
        if mpaa:
            mpaa_counts[mpaa] = mpaa_counts.get(mpaa, 0) + weight

        year = item.get('year', 0)
        if year:
            years.append(year)

        item_directors = item.get('director', [])
        if not isinstance(item_directors, list):
            item_directors = [item_directors] if item_directors else []
        for director in item_directors:
            if director:
                directors[director] = directors.get(director, 0) + weight

    if not watched_sets:
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    total_weight = sum(w for _, w, _ in watched_sets)
    preferred_mpaa = set(mpaa_counts.keys())
    median_year = sorted(years)[len(years) // 2] if years else 0
    favorite_directors = {d for d, w in directors.items() if w >= 1.5}

    genre_filters = [{'field': 'genre', 'operator': 'contains', 'value': g}
                     for g in all_watched_genres]
    genre_filter = {'or': genre_filters} if len(genre_filters) > 1 else genre_filters[0]

    candidates = []

    if dbtype in ('movie', 'both'):
        movie_filter = {
            'and': [
                {'field': 'playcount', 'operator': 'is', 'value': '0'},
                genre_filter
            ]
        }
        result = request('VideoLibrary.GetMovies', {
            'filter': movie_filter,
            'properties': ['genre', 'year', 'mpaa', 'rating', 'director'],
        })
        for movie in extract_result(result, 'movies', []):
            movie['_mtype'] = 'movie'
            candidates.append(movie)

    if dbtype in ('tvshow', 'both'):
        tvshow_filter = {
            'and': [
                {'field': 'numwatched', 'operator': 'is', 'value': '0'},
                genre_filter
            ]
        }
        result = request('VideoLibrary.GetTVShows', {
            'filter': tvshow_filter,
            'properties': ['genre', 'year', 'mpaa', 'rating'],
        })
        for show in extract_result(result, 'tvshows', []):
            show['_mtype'] = 'tvshow'
            candidates.append(show)

    # quality multiplier (tone/year/director) ranks picks within each watch's own slots
    pool = []
    for candidate in candidates:
        cand_genres = candidate.get('genre', [])
        if not isinstance(cand_genres, list):
            cand_genres = [cand_genres] if cand_genres else []
        cand_set = frozenset(cand_genres)
        if not cand_set or candidate.get('rating', 0.0) < min_rating:
            continue
        cand_mpaa = candidate.get('mpaa', '')
        if strict_rating and cand_mpaa not in preferred_mpaa:
            continue

        quality = 1.0
        if cand_mpaa in preferred_mpaa:
            quality += 0.15
        cand_year = candidate.get('year', 0)
        if cand_year and median_year:
            year_distance = abs(cand_year - median_year)
            if year_distance <= 5:
                quality += 0.15
            elif year_distance <= 15:
                quality += 0.06
        cand_directors = candidate.get('director', [])
        if not isinstance(cand_directors, list):
            cand_directors = [cand_directors] if cand_directors else []
        if any(d in favorite_directors for d in cand_directors):
            quality += 0.12

        candidate['_set'] = cand_set
        candidate['_quality'] = quality
        pool.append(candidate)

    # each watch gets slots proportional to its recency weight, so the mix mirrors recent
    # watches instead of one pervasive genre taking every slot
    scored_items = []
    used_ids = set()

    for wset, wweight, wtitle in watched_sets:
        slots = max(1, round(limit * wweight / total_weight))
        ranked = sorted(
            pool,
            key=lambda c, ws=wset: ((len(c['_set'] & ws) / len(c['_set'] | ws)) * c['_quality']
                                    * random.uniform(0.9, 1.1)) if (c['_set'] & ws) else 0.0,
            reverse=True,
        )
        taken = 0
        for c in ranked:
            if not (c['_set'] & wset):
                break  # ranked desc; once overlap hits zero the rest are zero too
            cid = (c['_mtype'], c.get('movieid') or c.get('tvshowid'))
            if cid in used_ids:
                continue
            used_ids.add(cid)
            scored_items.append((c, wtitle))
            taken += 1
            if taken >= slots or len(scored_items) >= limit:
                break
        if len(scored_items) >= limit:
            break

    scored_items = scored_items[:limit]

    # blend spans many watches, so the header stays generic rather than naming one movie
    _render_recommended(handle, scored_items, ADDON.getLocalizedString(32652), dbtype)


# Holiday seasons: library movies whose TMDB keyword tags match (exact, OR'd).
SEASONAL_TAGS = {
    'christmas': [
        'christmas', 'christmas eve', 'christmas party', 'christmas tree',
        'christmas music', 'christmas spirit', 'christmas horror', 'christmas romance',
        'christmas present', 'christmas dinner', 'santa claus', "santa's elves",
        'north pole', 'reindeer', 'snowman', 'scrooge',
    ],
    'halloween': [
        'halloween', 'trick or treat', 'trick or treating', 'pumpkin',
        'jack-o-lantern', 'haunted house', 'werewolf', 'vampire',
    ],
    'thanksgiving': ['thanksgiving', 'turkey', 'harvest'],
    'newyear': ["new year's eve", "new year's day", 'new year', "new year's party"],
    'easter': ['easter', 'easter bunny', 'easter egg', 'bunny', 'spring holiday'],
    'independence': ['independence day', 'fourth of july', '4th of july',
                     'patriotic', 'american flag'],
}

# Genre seasons: the occasion is the holiday, the genre is just how its content is found.
SEASONAL_GENRES = {
    'valentines': 'Romance',
}

# Franchise seasons: matched like _franchise_movies below. Star Trek needs no TMDB
# collection since every Trek film's title already contains "Star Trek".
SEASONAL_FRANCHISES = {
    'starwars': {'title': 'Star Wars', 'collections': [10]},
    'startrek': {'title': 'Star Trek', 'collections': []},
}

_SEASONAL_MOVIE_PROPERTIES = _MOVIE_PROPERTIES + ['sorttitle', 'originaltitle']

# widget sort method -> (movie field, reverse, is_text)
_SORT_KEYS = {
    'year': ('year', False, False), 'title': ('title', False, True),
    'label': ('title', False, True), 'sorttitle': ('sorttitle', False, True),
    'originaltitle': ('originaltitle', False, True), 'rating': ('rating', True, False),
    'userrating': ('userrating', True, False), 'votes': ('votes', True, False),
    'dateadded': ('dateadded', True, True), 'lastplayed': ('lastplayed', True, True),
    'playcount': ('playcount', True, False),
}


def _seasonal_filter(season: str) -> Optional[dict]:
    """Build the VideoLibrary.GetMovies filter for a holiday/genre seasonal key, or None."""
    if season in SEASONAL_GENRES:
        return {'field': 'genre', 'operator': 'is', 'value': SEASONAL_GENRES[season]}
    if season in SEASONAL_TAGS:
        return {'or': [{'field': 'tag', 'operator': 'is', 'value': t}
                       for t in SEASONAL_TAGS[season]]}
    return None


def _sort_movies(movies: list, method: str) -> None:
    """Sort combined franchise results in place to match the requested widget sort."""
    if method == 'random':
        random.shuffle(movies)
        return
    spec = _SORT_KEYS.get(method)
    if spec:
        field, reverse, text = spec
        movies.sort(key=lambda m: m.get(field) or ('' if text else 0), reverse=reverse)


def _library_movies_by_tmdb(tmdb_ids: set) -> list:
    """Full movie dicts for library movies matching the given TMDB ids."""
    from lib.data.database.rollcall import get_dbids_by_tmdb

    out = []
    for movieid in get_dbids_by_tmdb('movie', tmdb_ids).values():
        detail = request('VideoLibrary.GetMovieDetails',
                         {'movieid': movieid, 'properties': _SEASONAL_MOVIE_PROPERTIES})
        movie = extract_result(detail, 'moviedetails', {})
        if movie:
            out.append(movie)
    return out


def _franchise_movies(franchise: dict, limit: int, sort_method: str) -> list:
    """Library movies for a franchise: title/set match plus TMDB collection ∩ uniqueid, so
    cached collection lookups recover odd-titled saga entries even without Kodi movie sets."""
    name = franchise['title']
    result = request('VideoLibrary.GetMovies', {
        'filter': {'or': [
            {'field': 'set', 'operator': 'contains', 'value': name},
            {'field': 'title', 'operator': 'contains', 'value': name},
        ]},
        'properties': _SEASONAL_MOVIE_PROPERTIES + ['uniqueid'],
    })
    movies = extract_result(result, 'movies', [])
    have = {str((m.get('uniqueid') or {}).get('tmdb')) for m in movies}

    wanted = set()
    if franchise['collections']:
        from lib.data.api.tmdb import ApiTmdb
        api = ApiTmdb()
        for collection_id in franchise['collections']:
            for part in api.get_collection(collection_id):
                part_id = part.get('id')
                if part_id:
                    wanted.add(str(part_id))
    missing = wanted - have
    if missing:
        movies.extend(_library_movies_by_tmdb(missing))

    _sort_movies(movies, sort_method)
    return movies[:limit]


def _query_movies(movie_filter: dict, sort_method: str, limit: int) -> list:
    """Fetch movies for a seasonal filter with the standard render properties."""
    reverse = _SORT_KEYS.get(sort_method, ('', False, False))[1]
    result = request('VideoLibrary.GetMovies', {
        'filter': movie_filter,
        'properties': _SEASONAL_MOVIE_PROPERTIES,
        'sort': {'method': sort_method, 'order': 'descending' if reverse else 'ascending'},
        'limits': {'start': 0, 'end': limit},
    })
    return extract_result(result, 'movies', [])


_HALLOWEEN_HOLIDAY_RATIO = 0.62  # remainder is general horror-genre variety


def _halloween_movies(limit: int, sort_method: str) -> list:
    """Halloween blend: ~62% holiday-tagged films, remainder horror genre for variety; horror
    excludes titles already in the holiday set (pools overlap), and either side backfills
    the other when thin."""
    holiday_filter = {'or': [{'field': 'tag', 'operator': 'is', 'value': t}
                             for t in SEASONAL_TAGS['halloween']]}
    holiday = _query_movies(holiday_filter, sort_method, limit)
    horror = _query_movies(
        {'field': 'genre', 'operator': 'is', 'value': 'Horror'}, sort_method, limit)

    # dedup horror against the whole holiday set (not just this page) so the split is exact
    holiday_all = request('VideoLibrary.GetMovies', {'filter': holiday_filter})
    holiday_ids = {m['movieid'] for m in extract_result(holiday_all, 'movies', [])}
    horror_only = [m for m in horror if m['movieid'] not in holiday_ids]

    keep_holiday = min(len(holiday), round(limit * _HALLOWEEN_HOLIDAY_RATIO))
    picked = holiday[:keep_holiday]
    picked += horror_only[:limit - len(picked)]
    if len(picked) < limit:  # horror ran out -> top up with remaining holiday
        picked += holiday[keep_holiday:keep_holiday + (limit - len(picked))]

    _sort_movies(picked, sort_method)
    return picked


def handle_seasonal(handle: int, params: dict) -> None:
    """Plugin entry: seasonal movie collections (holiday keywords, genre, or franchise set)."""
    from lib.plugin.widgets import validate_sort_method
    season = params.get('season', [''])[0].lower()
    limit = int(params.get('limit', ['50'])[0])
    sort_method = validate_sort_method(params.get('sort', ['random'])[0], 'random')

    if season in SEASONAL_FRANCHISES:
        movies = _franchise_movies(SEASONAL_FRANCHISES[season], limit, sort_method)
    elif season == 'halloween':
        movies = _halloween_movies(limit, sort_method)
    else:
        movie_filter = _seasonal_filter(season)
        if movie_filter is None:
            xbmcplugin.endOfDirectory(handle)
            return
        movies = _query_movies(movie_filter, sort_method, limit)

    all_items = []
    for movie in movies:
        listitem = _create_movie_listitem(movie)
        all_items.append((movie['file'], listitem, False))

    for url, listitem, isfolder in all_items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.setContent(handle, 'movies')
    xbmcplugin.endOfDirectory(handle)
