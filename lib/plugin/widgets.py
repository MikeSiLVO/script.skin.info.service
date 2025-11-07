"""Widget handlers for plugin content."""
from __future__ import annotations

import random
import xbmc
import xbmcgui
import xbmcplugin
from lib.kodi.client import request, get_item_details


def _set_episode_artwork_from_show(listitem: xbmcgui.ListItem, show_art: dict, episode_art: dict) -> None:
    """
    Set episode ListItem artwork using show artwork with episode thumb.

    Combines TV show artwork (poster, fanart, clearlogo, etc.) with episode thumbnail.

    Args:
        listitem: Episode ListItem to set artwork on
        show_art: TV show art dict from JSON-RPC
        episode_art: Episode art dict from JSON-RPC
    """
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


def handle_next_up(handle: int, params: dict) -> None:
    """
    Get next episode to watch for each in-progress TV show.

    Returns episode ListItems with TV show artwork (poster, fanart, clearlogo).
    Uses native season parameter for optimal database queries.

    Args:
        handle: Plugin handle
        params: URL parameters dict with optional 'limit'
    """
    limit = int(params.get('limit', ['25'])[0])

    result = request('VideoLibrary.GetTVShows', {
        'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''},
        'properties': ['art', 'title'],
        'sort': {'method': 'lastplayed', 'order': 'descending'},
        'limits': {'start': 0, 'end': limit}
    })
    shows = result.get('result', {}).get('tvshows', []) if result else []

    items = []
    for show in shows:
        last_result = request('VideoLibrary.GetEpisodes', {
            'tvshowid': show['tvshowid'],
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
        last_played = last_result.get('result', {}).get('episodes', []) if last_result else []

        if not last_played:
            continue

        season = last_played[0]['season']

        next_result = request('VideoLibrary.GetEpisodes', {
            'tvshowid': show['tvshowid'],
            'season': season,
            'filter': {'field': 'playcount', 'operator': 'is', 'value': '0'},
            'properties': ['title', 'season', 'episode', 'showtitle', 'plot',
                          'art', 'file', 'resume', 'runtime', 'firstaired',
                          'rating', 'userrating', 'playcount', 'lastplayed'],
            'sort': {'method': 'episode', 'order': 'ascending'},
            'limits': {'start': 0, 'end': 1}
        })
        next_ep = next_result.get('result', {}).get('episodes', []) if next_result else []

        if not next_ep:
            fallback_result = request('VideoLibrary.GetEpisodes', {
                'tvshowid': show['tvshowid'],
                'filter': {'field': 'playcount', 'operator': 'is', 'value': '0'},
                'properties': ['title', 'season', 'episode', 'showtitle', 'plot',
                              'art', 'file', 'resume', 'runtime', 'firstaired',
                              'rating', 'userrating', 'playcount', 'lastplayed'],
                'sort': {'method': 'episode', 'order': 'ascending'},
                'limits': {'start': 0, 'end': 1}
            })
            next_ep = fallback_result.get('result', {}).get('episodes', []) if fallback_result else []

        if next_ep:
            episode = next_ep[0]
            listitem = _create_episode_listitem(episode)
            _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
            items.append((episode['file'], listitem, False))

    for url, listitem, isfolder in items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)


def _create_episode_listitem(episode: dict) -> xbmcgui.ListItem:
    """
    Create episode ListItem with proper formatting and metadata.

    Label format: "2x05. Episode Title" or "S05. Special Title"

    Args:
        episode: Episode data dict from JSON-RPC

    Returns:
        Configured ListItem with episode metadata
    """
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
    """
    Get recently added episodes with intelligent grouping.

    Returns mixed episode/show ListItems:
    - Single unwatched episode: Returns episode with show artwork
    - Multiple unwatched episodes: Returns show folder
    - Multiple episodes added same day: Returns show folder

    Args:
        handle: Plugin handle
        params: URL parameters dict with optional 'limit' and 'include_watched'
    """
    limit = int(params.get('limit', ['25'])[0])
    include_watched = params.get('include_watched', ['false'])[0].lower() == 'true'

    tvshow_filter = None if include_watched else {
        'field': 'playcount',
        'operator': 'lessthan',
        'value': '1'
    }

    result = request('VideoLibrary.GetTVShows', {
        'filter': tvshow_filter,
        'properties': ['art', 'episode', 'watchedepisodes', 'title', 'plot', 'rating',
                      'userrating', 'year', 'premiered', 'playcount', 'votes', 'genre',
                      'studio', 'mpaa', 'cast', 'tag', 'dateadded', 'lastplayed',
                      'imdbnumber', 'originaltitle'],
        'sort': {'method': 'dateadded', 'order': 'descending'},
        'limits': {'start': 0, 'end': limit}
    })
    shows = result.get('result', {}).get('tvshows', []) if result else []

    items = []
    for show in shows:
        unwatched_count = show.get('episode', 0) - show.get('watchedepisodes', 0)

        if unwatched_count == 1:
            ep_result = request('VideoLibrary.GetEpisodes', {
                'tvshowid': show['tvshowid'],
                'filter': {'field': 'playcount', 'operator': 'is', 'value': '0'},
                'properties': ['title', 'season', 'episode', 'showtitle', 'plot',
                              'art', 'file', 'resume', 'runtime', 'firstaired',
                              'rating', 'userrating', 'playcount', 'lastplayed'],
                'sort': {'method': 'dateadded', 'order': 'descending'},
                'limits': {'start': 0, 'end': 1}
            })
            episodes = ep_result.get('result', {}).get('episodes', []) if ep_result else []

            if episodes:
                episode = episodes[0]
                listitem = _create_episode_listitem(episode)
                _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
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
            recent_eps = recent_result.get('result', {}).get('episodes', []) if recent_result else []

            if len(recent_eps) >= 2:
                date1 = recent_eps[0].get('dateadded', '').split('T')[0]
                date2 = recent_eps[1].get('dateadded', '').split('T')[0]

                if date1 == date2:
                    listitem = _create_tvshow_listitem(show)
                    show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
                    items.append((show_url, listitem, True))
                else:
                    episode = recent_eps[0]
                    listitem = _create_episode_listitem(episode)
                    _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
                    items.append((episode['file'], listitem, False))
            elif recent_eps:
                episode = recent_eps[0]
                listitem = _create_episode_listitem(episode)
                _set_episode_artwork_from_show(listitem, show['art'], episode['art'])
                items.append((episode['file'], listitem, False))
        else:
            listitem = _create_tvshow_listitem(show)
            show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
            items.append((show_url, listitem, True))

    for url, listitem, isfolder in items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)


def _create_tvshow_listitem(show: dict) -> xbmcgui.ListItem:
    """
    Create TV show ListItem with proper metadata.

    Args:
        show: TV show data dict from JSON-RPC

    Returns:
        Configured ListItem with TV show metadata
    """
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
    listitem.setProperty('TotalEpisodes', str(episode_count))
    listitem.setProperty('WatchedEpisodes', str(watched_episodes))
    listitem.setProperty('UnWatchedEpisodes', str(unwatched_episodes))

    listitem.setArt(show.get('art', {}))

    return listitem


def handle_by_actor(handle: int, params: dict) -> None:
    """
    Get movies and TV shows featuring an actor from the specified item.

    Context-aware: Extracts random actor from source item's cast and returns
    results featuring that actor. Can return mixed types or match source type.

    Args:
        handle: Plugin handle
        params: URL parameters dict with 'dbid', optional 'dbtype', 'limit', 'cast_limit', 'mix', 'lock'
    """
    dbid_param = params.get('dbid', [''])[0]
    if not dbid_param:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
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
                xbmcplugin.endOfDirectory(handle, succeeded=False)
                return

            if cast_limit > 0:
                top_cast = item['cast'][:cast_limit]
            else:
                top_cast = item['cast']

            actor = random.choice(top_cast)['name']
            window.setProperty(lock_property_actor, actor)
            window.setProperty(lock_property_dbid, str(dbid))
            log('Plugin', f"by_actor: Picked and locked actor '{actor}' for dbid={dbid}", xbmc.LOGINFO)
    else:
        window.clearProperty(lock_property_actor)
        window.clearProperty(lock_property_dbid)
        item = get_item_details(dbtype, dbid, ['cast', 'title'])

        if not item or not item.get('cast'):
            xbmcplugin.endOfDirectory(handle, succeeded=False)
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
            'properties': ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                          'plot', 'runtime', 'genre', 'director', 'studio', 'mpaa', 'trailer',
                          'votes', 'tag', 'dateadded', 'lastplayed', 'resume'],
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        movies = movie_result.get('result', {}).get('movies', []) if movie_result else []

        for movie in movies:
            if movie.get('movieid') != dbid or dbtype != 'movie':
                listitem = _create_movie_listitem(movie)
                all_items.append((movie['file'], listitem, False))

    if mix or dbtype in ('tvshow', 'season', 'episode'):
        show_result = request('VideoLibrary.GetTVShows', {
            'filter': {'actor': actor},
            'properties': ['art', 'episode', 'watchedepisodes', 'title', 'plot', 'rating',
                          'userrating', 'year', 'premiered', 'playcount', 'votes', 'genre',
                          'studio', 'mpaa', 'cast', 'tag', 'dateadded', 'lastplayed',
                          'imdbnumber', 'originaltitle'],
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        shows = show_result.get('result', {}).get('tvshows', []) if show_result else []

        for show in shows:
            if show.get('tvshowid') != dbid or dbtype != 'tvshow':
                listitem = _create_tvshow_listitem(show)
                show_url = f"videodb://tvshows/titles/{show['tvshowid']}/"
                all_items.append((show_url, listitem, True))

    random.shuffle(all_items)

    for url, listitem, isfolder in all_items:
        listitem.setProperty('Actor', actor)
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)


def _create_movie_listitem(movie: dict) -> xbmcgui.ListItem:
    """
    Create movie ListItem with proper metadata.

    Args:
        movie: Movie data dict from JSON-RPC

    Returns:
        Configured ListItem with movie metadata
    """
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
    """
    Get movies and episodes by a director from the specified item.

    Context-aware: Extracts random director from source item and returns
    results by that director. Can return mixed types or match source type.

    Args:
        handle: Plugin handle
        params: URL parameters dict with 'dbid', optional 'dbtype', 'limit', 'director_limit', 'mix'
    """
    dbid_param = params.get('dbid', [''])[0]
    if not dbid_param:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    dbid = int(dbid_param)
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])
    director_limit = int(params.get('director_limit', ['3'])[0])
    mix = params.get('mix', ['true'])[0].lower() == 'true'

    item = get_item_details(dbtype, dbid, ['director', 'title'])

    if not item or not item.get('director'):
        xbmcplugin.endOfDirectory(handle, succeeded=False)
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
            'properties': ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                          'plot', 'runtime', 'genre', 'director', 'studio', 'mpaa', 'trailer',
                          'votes', 'tag', 'dateadded', 'lastplayed', 'resume'],
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        movies = movie_result.get('result', {}).get('movies', []) if movie_result else []

        for movie in movies:
            if movie.get('movieid') != dbid or dbtype != 'movie':
                listitem = _create_movie_listitem(movie)
                all_items.append((movie['file'], listitem, False))

    if mix or dbtype == 'episode':
        episode_result = request('VideoLibrary.GetEpisodes', {
            'filter': {'field': 'director', 'operator': 'is', 'value': director},
            'properties': ['title', 'season', 'episode', 'showtitle', 'plot', 'art', 'file',
                          'resume', 'runtime', 'firstaired', 'rating', 'userrating', 'playcount',
                          'lastplayed', 'tvshowid'],
            'sort': {'method': 'random'},
            'limits': {'start': 0, 'end': limit if not mix else limit // 2}
        })
        episodes = episode_result.get('result', {}).get('episodes', []) if episode_result else []

        for episode in episodes:
            if episode.get('episodeid') != dbid or dbtype != 'episode':
                listitem = _create_episode_listitem(episode)

                tvshowid = episode.get('tvshowid')
                if tvshowid:
                    show_result = request('VideoLibrary.GetTVShowDetails', {
                        'tvshowid': tvshowid,
                        'properties': ['art']
                    })
                    show = show_result.get('result', {}).get('tvshowdetails', {}) if show_result else {}

                    if show:
                        _set_episode_artwork_from_show(listitem, show['art'], episode['art'])

                all_items.append((episode['file'], listitem, False))

    random.shuffle(all_items)

    for url, listitem, isfolder in all_items:
        listitem.setProperty('Director', director)
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)


def handle_similar(handle: int, params: dict) -> None:
    """
    Get similar items based on genre matching with light scoring.

    Scores items by genre overlap, year proximity, and MPAA compatibility.

    Args:
        handle: Plugin handle
        params: URL parameters dict with 'dbid', optional 'dbtype', 'limit'
    """
    dbid_param = params.get('dbid', [''])[0]
    if not dbid_param:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    dbid = int(dbid_param)
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])

    properties = ['genre', 'year', 'mpaa']
    if dbtype == 'episode':
        properties.extend(['tvshowid'])

    item = get_item_details(dbtype, dbid, properties)

    if not item:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    genres = item.get('genre', [])
    if not isinstance(genres, list):
        genres = [genres] if genres else []

    if not genres:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    source_year = item.get('year', 0)
    source_mpaa = item.get('mpaa', '')

    target_dbtype = 'movie' if dbtype in ('movie', 'set') else 'tvshow'

    # Server-side filter: only fetch items sharing at least one genre
    genre_filters = [{'field': 'genre', 'operator': 'contains', 'value': g} for g in genres]
    genre_filter = {'or': genre_filters} if len(genre_filters) > 1 else genre_filters[0]

    candidates = []

    if target_dbtype == 'movie':
        result = request('VideoLibrary.GetMovies', {
            'filter': genre_filter,
            'properties': ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                          'plot', 'runtime', 'genre', 'director', 'studio', 'mpaa', 'trailer',
                          'votes', 'tag', 'dateadded', 'lastplayed', 'resume'],
        })
        candidates = result.get('result', {}).get('movies', []) if result else []
        id_field = 'movieid'
    else:
        result = request('VideoLibrary.GetTVShows', {
            'filter': genre_filter,
            'properties': ['art', 'episode', 'watchedepisodes', 'title', 'plot', 'rating',
                          'userrating', 'year', 'premiered', 'playcount', 'votes', 'genre',
                          'studio', 'mpaa', 'cast', 'tag', 'dateadded', 'lastplayed',
                          'imdbnumber', 'originaltitle'],
        })
        candidates = result.get('result', {}).get('tvshows', []) if result else []
        id_field = 'tvshowid'

    scored_items = []
    for candidate in candidates:
        if candidate.get(id_field) == dbid:
            continue

        cand_genres = candidate.get('genre', [])
        if not isinstance(cand_genres, list):
            cand_genres = [cand_genres] if cand_genres else []

        if not cand_genres:
            continue

        genre_overlap = len(set(genres) & set(cand_genres))
        if genre_overlap == 0:
            continue

        score = genre_overlap * 10

        cand_year = candidate.get('year', 0)
        if source_year and cand_year:
            year_diff = abs(source_year - cand_year)
            if year_diff <= 5:
                score += 3
            elif year_diff <= 10:
                score += 2
            elif year_diff <= 20:
                score += 1

        cand_mpaa = candidate.get('mpaa', '')
        if source_mpaa and cand_mpaa and source_mpaa == cand_mpaa:
            score += 2

        scored_items.append((score, candidate))

    scored_items.sort(key=lambda x: (x[0], random.random()), reverse=True)
    scored_items = scored_items[:limit]

    all_items = []
    for score, item_data in scored_items:
        if target_dbtype == 'movie':
            listitem = _create_movie_listitem(item_data)
            all_items.append((item_data['file'], listitem, False))
        else:
            listitem = _create_tvshow_listitem(item_data)
            show_url = f"videodb://tvshows/titles/{item_data['tvshowid']}/"
            all_items.append((show_url, listitem, True))

    for url, listitem, isfolder in all_items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)

def handle_recommended(handle: int, params: dict) -> None:
    """
    Get personalized recommendations based on watch history.

    Analyzes recent watch history to identify genre preferences, MPAA context,
    and year patterns, then scores unwatched items accordingly.

    Args:
        handle: Plugin handle
        params: URL parameters dict with optional 'dbtype', 'limit', 'strict_rating', 'min_rating'
    """
    dbtype = params.get('dbtype', ['movie'])[0]
    limit = int(params.get('limit', ['25'])[0])
    strict_rating = params.get('strict_rating', ['false'])[0].lower() == 'true'
    min_rating = float(params.get('min_rating', ['6.0'])[0])

    history = []

    if dbtype in ('movie', 'both'):
        movie_history = request('VideoLibrary.GetMovies', {
            'filter': {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'},
            'properties': ['genre', 'year', 'mpaa', 'rating', 'cast', 'director', 'lastplayed'],
            'sort': {'method': 'lastplayed', 'order': 'descending'},
            'limits': {'start': 0, 'end': 20}
        })
        movies = movie_history.get('result', {}).get('movies', []) if movie_history else []
        history.extend(movies)

    if dbtype in ('tvshow', 'both'):
        show_history = request('VideoLibrary.GetTVShows', {
            'filter': {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'},
            'properties': ['genre', 'year', 'mpaa', 'rating', 'cast', 'lastplayed'],
            'sort': {'method': 'lastplayed', 'order': 'descending'},
            'limits': {'start': 0, 'end': 20}
        })
        shows = show_history.get('result', {}).get('tvshows', []) if show_history else []
        history.extend(shows)

    if not history:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    genre_counts = {}
    mpaa_counts = {}
    years = []
    actors = {}
    directors = {}

    for item in history:
        item_genres = item.get('genre', [])
        if not isinstance(item_genres, list):
            item_genres = [item_genres] if item_genres else []
        for genre in item_genres:
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

        mpaa = item.get('mpaa', '')
        if mpaa:
            mpaa_counts[mpaa] = mpaa_counts.get(mpaa, 0) + 1

        year = item.get('year', 0)
        if year:
            years.append(year)

        cast = item.get('cast', [])
        for member in cast[:3]:
            name = member.get('name', '')
            if name:
                actors[name] = actors.get(name, 0) + 1

        item_directors = item.get('director', [])
        if not isinstance(item_directors, list):
            item_directors = [item_directors] if item_directors else []
        for director in item_directors:
            if director:
                directors[director] = directors.get(director, 0) + 1

    if not genre_counts:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    preferred_genres = set(genre_counts.keys())
    preferred_mpaa = set(mpaa_counts.keys())
    year_min = min(years) if years else 1900
    year_max = max(years) if years else 2100
    favorite_actors = {actor for actor, count in actors.items() if count >= 2}
    favorite_directors = {director for director, count in directors.items() if count >= 2}

    # Server-side filter: only fetch unwatched items matching preferred genres
    genre_filters = [{'field': 'genre', 'operator': 'contains', 'value': g} for g in preferred_genres]
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
            'properties': ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                          'plot', 'runtime', 'genre', 'director', 'studio', 'mpaa', 'trailer',
                          'votes', 'tag', 'dateadded', 'lastplayed', 'resume', 'cast'],
        })
        candidates.extend(result.get('result', {}).get('movies', []) if result else [])

    if dbtype in ('tvshow', 'both'):
        tvshow_filter = {
            'and': [
                {'field': 'playcount', 'operator': 'lessthan', 'value': '1'},
                genre_filter
            ]
        }
        result = request('VideoLibrary.GetTVShows', {
            'filter': tvshow_filter,
            'properties': ['art', 'episode', 'watchedepisodes', 'title', 'plot', 'rating',
                          'userrating', 'year', 'premiered', 'playcount', 'votes', 'genre',
                          'studio', 'mpaa', 'cast', 'tag', 'dateadded', 'lastplayed',
                          'imdbnumber', 'originaltitle'],
        })
        candidates.extend(result.get('result', {}).get('tvshows', []) if result else [])

    scored_items = []
    for candidate in candidates:
        cand_genres = candidate.get('genre', [])
        if not isinstance(cand_genres, list):
            cand_genres = [cand_genres] if cand_genres else []

        cand_rating = candidate.get('rating', 0.0)
        if cand_rating < min_rating:
            continue

        genre_overlap = len(set(cand_genres) & preferred_genres)
        if genre_overlap == 0:
            continue

        score = genre_overlap * 10

        cand_mpaa = candidate.get('mpaa', '')
        if strict_rating:
            if cand_mpaa not in preferred_mpaa:
                continue
        elif cand_mpaa in preferred_mpaa:
            score += 5

        cand_year = candidate.get('year', 0)
        if cand_year and year_min <= cand_year <= year_max:
            score += 3

        cand_cast = candidate.get('cast', [])
        for member in cand_cast[:5]:
            if member.get('name', '') in favorite_actors:
                score += 2
                break

        cand_directors = candidate.get('director', [])
        if not isinstance(cand_directors, list):
            cand_directors = [cand_directors] if cand_directors else []
        if any(d in favorite_directors for d in cand_directors):
            score += 3

        scored_items.append((score, candidate))

    scored_items.sort(key=lambda x: (x[0], random.random()), reverse=True)
    scored_items = scored_items[:limit]

    all_items = []
    for score, item_data in scored_items:
        if 'file' in item_data:
            listitem = _create_movie_listitem(item_data)
            all_items.append((item_data['file'], listitem, False))
        else:
            listitem = _create_tvshow_listitem(item_data)
            show_url = f"videodb://tvshows/titles/{item_data['tvshowid']}/"
            all_items.append((show_url, listitem, True))

    for url, listitem, isfolder in all_items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)


SEASONAL_TAGS = {
    'christmas': [
        'christmas', 'xmas', 'santa claus', 'santa', 'north pole',
        'elf', 'elves', 'reindeer', 'grinch', 'scrooge',
        'christmas tree', 'snowman', 'advent', 'nativity',
        'christmas party', 'xmas eve', 'mall santa', 'christmas spirit',
        'saving christmas'
    ],
    'halloween': [
        'halloween', 'trick or treat', 'trick or treating',
        'pumpkin', 'jack-o-lantern', 'witch', 'werewolf',
        'zombie', 'monster', 'vampire', 'holiday horror',
        'horror anthology'
    ],
    'valentines': [
        "valentine's day", 'soulmate', 'soulmates', 'love story'
    ],
    'thanksgiving': [
        'thanksgiving', 'turkey', 'pilgrim', 'harvest festival'
    ],
    'starwars': [
        'star wars', 'jedi', 'sith', 'lightsaber', 'death star',
        'rebel alliance', 'galactic empire', 'the force', 'x-wing'
    ],
    'startrek': [
        'star trek', 'starship', 'starfleet', 'uss enterprise',
        'vulcan', 'klingon', 'warp speed', 'space opera'
    ],
    'newyear': [
        "new year's eve", "new year's day", 'new year',
        'celebration', 'countdown', 'midnight'
    ],
    'easter': [
        'easter', 'easter bunny', 'easter egg', 'resurrection',
        'spring holiday'
    ],
    'independence': [
        'independence day', '4th of july', 'fourth of july',
        'patriotic', 'american flag', 'fireworks'
    ],
    'horror': [
        'horror', 'slasher', 'monster', 'haunted', 'demon',
        'possessed', 'serial killer', 'zombie', 'vampire'
    ]
}


def handle_seasonal(handle: int, params: dict) -> None:
    """
    Get seasonal movies filtered by TMDB keywords (tags).

    Uses Kodi's native tag field populated by TMDB scrapers.

    Args:
        handle: Plugin handle
        params: URL parameters dict with 'season', optional 'limit', 'sort'
    """
    season = params.get('season', [''])[0].lower()
    limit = int(params.get('limit', ['50'])[0])
    sort_method = params.get('sort', ['random'])[0]

    if season not in SEASONAL_TAGS:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    tags = SEASONAL_TAGS[season]

    tag_filters = [{'field': 'tag', 'operator': 'is', 'value': tag} for tag in tags]

    result = request('VideoLibrary.GetMovies', {
        'filter': {'or': tag_filters},
        'properties': ['title', 'art', 'file', 'year', 'rating', 'userrating', 'playcount',
                      'plot', 'runtime', 'genre', 'director', 'studio', 'mpaa', 'trailer',
                      'votes', 'tag', 'dateadded', 'lastplayed', 'resume'],
        'sort': {'method': sort_method},
        'limits': {'start': 0, 'end': limit}
    })
    movies = result.get('result', {}).get('movies', []) if result else []

    all_items = []
    for movie in movies:
        listitem = _create_movie_listitem(movie)
        all_items.append((movie['file'], listitem, False))

    for url, listitem, isfolder in all_items:
        xbmcplugin.addDirectoryItem(handle, url, listitem, isfolder)

    xbmcplugin.endOfDirectory(handle)
