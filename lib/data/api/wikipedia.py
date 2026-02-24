"""Wikipedia API client for track and album summaries.

Uses Wikipedia core REST API for search (returns description field for validation)
and MediaWiki action API for plain-text extracts. No API key required.

Search: /w/rest.php/v1/search/page — HTTP error codes handled by ApiSession.
Extract: /w/api.php — always HTTP 200, errors in JSON body need manual handling.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

import xbmc

from lib.data.api.client import ApiSession
from lib.kodi.client import log
from lib.rating.source import RateLimitHit, RetryableError

_SMART_QUOTES = re.compile(r'[\u201c\u201d\u2018\u2019\u00ab\u00bb]')
_HTML_TAGS = re.compile(r'<[^>]+>')

_RETRYABLE_CODES = {'readonly', 'maxlag', 'internal_api_error'}
_NOT_FOUND_CODES = {'missingtitle', 'nosuchsection', 'invalidtitle'}

_WIKI_LANG_MAP = {
    'pt-br': 'pt',
    'zh-cn': 'zh',
    'zh-tw': 'zh',
}


def _wiki_lang(lang: str) -> str:
    return _WIKI_LANG_MAP.get(lang, lang)


class ApiWikipedia:
    """Wikipedia API client for music track and album summaries."""

    def __init__(self):
        self.session = ApiSession(
            service_name="Wikipedia",
            timeout=(5.0, 10.0),
            max_retries=2,
            backoff_factor=0.5,
            rate_limit=(10, 10.0),
        )

    def _base_url(self, lang: str) -> str:
        return f"https://{_wiki_lang(lang)}.wikipedia.org"

    def _action_request(
        self,
        params: Dict[str, Any],
        lang: str = 'en',
        abort_flag=None,
    ) -> Optional[dict]:
        """Make MediaWiki action API request with JSON-level error handling.

        Action API always returns HTTP 200 — errors are in the JSON body.
        """
        url = f"{self._base_url(lang)}/w/api.php"
        all_params: Dict[str, Any] = {"format": "json"}
        all_params.update(params)

        data = self.session.get(url, params=all_params, abort_flag=abort_flag)
        if not data:
            return None

        error = data.get('error')
        if isinstance(error, dict):
            code = error.get('code', '')
            info = error.get('info', 'Unknown error')

            if code == 'ratelimited':
                raise RateLimitHit("Wikipedia")

            if any(code.startswith(c) for c in _RETRYABLE_CODES):
                raise RetryableError("Wikipedia", f"{code}: {info}")

            if code in _NOT_FOUND_CODES:
                return None

            log("API", f"Wikipedia: {code}: {info}", xbmc.LOGWARNING)
            return None

        return data

    def _search(
        self,
        query: str,
        lang: str = 'en',
        limit: int = 5,
        abort_flag=None,
    ) -> Optional[list]:
        url = f"{self._base_url(lang)}/w/rest.php/v1/search/page"
        data = self.session.get(
            url, params={"q": query, "limit": limit}, abort_flag=abort_flag
        )
        if not data:
            return None
        pages = data.get('pages')
        if isinstance(pages, list):
            return pages
        return None

    def _get_extract(
        self,
        title: str,
        lang: str = 'en',
        abort_flag=None,
    ) -> Optional[str]:
        data = self._action_request(
            {
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
            },
            lang=lang,
            abort_flag=abort_flag,
        )
        if not data:
            return None

        query_data = data.get('query')
        if not isinstance(query_data, dict):
            return None
        pages = query_data.get('pages')
        if not isinstance(pages, dict):
            return None

        for page in pages.values():
            extract = page.get('extract')
            if extract:
                return extract.strip()
        return None

    def _validate_result(self, page: dict, item_name: str, artist: str) -> bool:
        title = page.get('title', '')
        title_clean = _SMART_QUOTES.sub('', title).lower().strip()
        item_lower = item_name.lower().strip()

        if not title_clean.startswith(item_lower):
            return False

        artist_lower = artist.lower()
        if artist_lower in title.lower():
            return True

        description = page.get('description', '')
        if artist_lower in description.lower():
            return True

        excerpt = page.get('excerpt', '')
        if excerpt:
            plain = _HTML_TAGS.sub('', excerpt).lower()
            if artist_lower in plain:
                return True

        return False

    def get_track_summary(
        self,
        artist: str,
        track: str,
        lang: str = 'en',
        abort_flag=None,
    ) -> Optional[str]:
        pages = self._search(
            f'"{track}" "{artist}" song', lang=lang, abort_flag=abort_flag
        )
        if not pages:
            return None
        for page in pages:
            if self._validate_result(page, track, artist):
                return self._get_extract(
                    page.get('title', ''), lang=lang, abort_flag=abort_flag
                )
        return None

    def get_album_summary(
        self,
        artist: str,
        album: str,
        lang: str = 'en',
        abort_flag=None,
    ) -> Optional[str]:
        pages = self._search(
            f'"{album}" "{artist}" album', lang=lang, abort_flag=abort_flag
        )
        if not pages:
            return None
        for page in pages:
            if self._validate_result(page, album, artist):
                return self._get_extract(
                    page.get('title', ''), lang=lang, abort_flag=abort_flag
                )
        return None
