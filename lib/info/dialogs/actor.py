from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Dict, Optional

import xbmc
import xbmcgui

from lib.info.dialogs.base import InfoDialogBase, ADDON_PATH
from lib.kodi.client import log

XML_FILE = 'script-skin-info-service-DialogActorInfo.xml'


class DialogActorInfo(InfoDialogBase):

    def __init__(self, *args, **kwargs):
        self._person_data: Dict = kwargs.pop('person_data', {})
        self._person_id: int = kwargs.pop('person_id', 0)
        self._person_name: str = kwargs.pop('person_name', '')
        super().__init__(*args, **kwargs)

    def onInit(self) -> None:
        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        self._set_person_properties()
        self._bind_containers()

    def _set_person_properties(self) -> None:
        data = self._person_data
        props: Dict[str, str] = {}

        props['Name'] = data.get('name', 'Unknown')
        props['person_id'] = str(self._person_id)

        if data.get('biography'):
            props['Biography'] = data['biography']

        birthday = data.get('birthday')
        deathday = data.get('deathday')

        if birthday:
            props['Birthday'] = birthday
            try:
                birth_date = datetime.strptime(birthday, '%Y-%m-%d')
                end_date = datetime.strptime(deathday, '%Y-%m-%d') if deathday else datetime.now()
                age = end_date.year - birth_date.year
                if (end_date.month, end_date.day) < (birth_date.month, birth_date.day):
                    age -= 1
                props['Age'] = str(age)
                date_format = xbmc.getRegion('dateshort')
                props['BirthdayFormatted'] = birth_date.strftime(date_format)
            except (ValueError, TypeError):
                pass

        if deathday:
            props['Deathday'] = deathday
            try:
                death_date = datetime.strptime(deathday, '%Y-%m-%d')
                date_format = xbmc.getRegion('dateshort')
                props['DeathdayFormatted'] = death_date.strftime(date_format)
            except (ValueError, TypeError):
                pass

        if data.get('place_of_birth'):
            props['Birthplace'] = data['place_of_birth']

        if data.get('known_for_department'):
            props['KnownFor'] = data['known_for_department']

        if data.get('imdb_id'):
            props['imdb_id'] = data['imdb_id']

        gender = data.get('gender')
        if gender:
            gender_text = {1: 'Female', 2: 'Male'}.get(gender)
            if gender_text:
                props['Gender'] = gender_text

        external_ids = data.get('external_ids', {})
        for key in ['instagram_id', 'twitter_id', 'facebook_id', 'tiktok_id', 'youtube_id']:
            value = external_ids.get(key)
            if value:
                props[key.replace('_id', '').title()] = value

        profile_path = data.get('profile_path')
        if profile_path:
            props['ProfileImage'] = f"https://image.tmdb.org/t/p/original{profile_path}"

        combined_credits = data.get('combined_credits', {})
        cast = combined_credits.get('cast', [])
        if cast:
            movies = sorted(
                [c for c in cast if c.get('media_type') == 'movie'],
                key=lambda x: x.get('popularity', 0), reverse=True
            )
            tv_shows = sorted(
                [c for c in cast if c.get('media_type') == 'tv'],
                key=lambda x: x.get('popularity', 0), reverse=True
            )

            seen: set = set()
            unique_movies = []
            for m in movies:
                mid = m.get('id')
                if mid and mid not in seen:
                    seen.add(mid)
                    unique_movies.append(m)

            seen.clear()
            unique_tv = []
            for t in tv_shows:
                tid = t.get('id')
                if tid and tid not in seen:
                    seen.add(tid)
                    unique_tv.append(t)

            top_movies = ' / '.join(m.get('title', '') for m in unique_movies[:5] if m.get('title'))
            top_tv = ' / '.join(t.get('name', '') for t in unique_tv[:5] if t.get('name'))
            if top_movies:
                props['TopMovies'] = top_movies
            if top_tv:
                props['TopTVShows'] = top_tv

        self._set_window_properties(props)

        if profile_path:
            image_url = f"https://image.tmdb.org/t/p/original{profile_path}"
            self.setProperty('ProfileImage', image_url)

    def _bind_containers(self) -> None:
        base_url = 'plugin://script.skin.info.service/'
        pid = str(self._person_id)
        encoded_name = urllib.parse.quote(self._person_name)

        containers = {
            'library_movies': f"{base_url}?action=person_library&info_type=movies&person_name={encoded_name}",
            'library_tvshows': f"{base_url}?action=person_library&info_type=tvshows&person_name={encoded_name}",
            'movies': f"{base_url}?action=person_info&info_type=filmography&person_id={pid}&dbtype=movie",
            'tvshows': f"{base_url}?action=person_info&info_type=filmography&person_id={pid}&dbtype=tvshow",
            'all_credits': f"{base_url}?action=person_info&info_type=filmography&person_id={pid}",
            'crew': f"{base_url}?action=person_info&info_type=crew&person_id={pid}",
            'images': f"{base_url}?action=person_info&info_type=images&person_id={pid}",
        }

        for name, path in containers.items():
            self.setProperty(f"container.{name}.path", path)

    def onAction(self, action: xbmcgui.Action) -> None:
        if self.is_close_action(action):
            self.close()


def open_actor_info(
    person_id: int,
    person_name: str,
    person_data: Optional[Dict] = None,
    set_home_props: bool = False,
) -> None:
    if not person_data:
        from lib.data.api.person import get_person_data
        person_data = get_person_data(person_id)
        if not person_data:
            log("General", f"DialogActorInfo: No data for person_id={person_id}", xbmc.LOGWARNING)
            return

    dialog = DialogActorInfo(
        XML_FILE,
        ADDON_PATH,
        'default',
        '1080i',
        person_data=person_data,
        person_id=person_id,
        person_name=person_name,
        set_home_props=set_home_props,
    )
    dialog.doModal()
    del dialog
