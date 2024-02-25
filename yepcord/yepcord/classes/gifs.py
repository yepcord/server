"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from dataclasses import dataclass, asdict
from time import time
from typing import List

from aiohttp import ClientSession

from .singleton import Singleton


@dataclass
class _J:
    @property
    def json(self) -> dict:
        return asdict(self)


@dataclass
class GifCategory(_J):
    name: str
    src: str


@dataclass
class Gif(_J):
    id: str
    title: str
    preview: str
    gif_src: str
    height: int
    width: int
    src: str
    url: str


@dataclass
class GifSearchResult(_J):
    query: str
    gifs: List[Gif]
    time: int


@dataclass
class GifSuggestion(_J):
    query: str
    tags: List[str]
    time: int


class Gifs(Singleton):
    def __init__(self, key: str = None, keep_searches: int = 100):
        self._key = key
        self._categories = []
        self._last_searches = []
        self._last_suggestions = []
        self._last_update = 0
        self._keep_searches = keep_searches

    @property
    async def categories(self) -> List[GifCategory]:
        if time() - self._last_update > 60:
            await self._update_categories()
        return self._categories

    async def _update_categories(self) -> None:
        if self._key is None:  # pragma: no cover
            self._categories = []
            return
        categories = []
        async with ClientSession() as sess:
            async with sess.get(f"https://tenor.googleapis.com/v2/categories?key={self._key}") as resp:
                for category in (await resp.json())["tags"]:
                    categories.append(GifCategory(category["name"][1:], category["image"]))
        self._categories = categories
        self._last_update = time()

    async def search(self, q: str=None, **kwargs) -> GifSearchResult:
        if self._key is None or not q:  # pragma: no cover
            return GifSearchResult(q, [], 0)

        search = [s for s in self._last_searches if s.query == q]
        if search:
            search = search[0]
            if time() - search.time < 60 * 30:
                # Move to the end
                self._last_searches.remove(search)
                self._last_searches.append(search)
                return search
            self._last_searches.remove(search)  # pragma: no cover

        gifs = []
        if "key" in kwargs: del kwargs["key"]
        _params = {"key": self._key, "q": q, **kwargs}
        async with ClientSession() as sess:
            async with sess.get(f"https://tenor.googleapis.com/v2/search", params=_params) as resp:
                for gif in (await resp.json())["results"]:
                    gifs.append(Gif(
                        id=gif["id"],
                        title=gif["title"],
                        preview=gif["media_formats"]["gifpreview"]["url"],
                        gif_src=gif["media_formats"]["gif"]["url"],
                        height=gif["media_formats"]["mp4"]["dims"][0],
                        width=gif["media_formats"]["mp4"]["dims"][1],
                        src=gif["media_formats"]["mp4"]["url"],
                        url=gif["itemurl"]
                    ))

        search = GifSearchResult(q, gifs, int(time()))

        self._last_searches.append(search)

        while len(self._last_searches) > self._keep_searches:  # pragma: no cover
            self._last_searches.pop(0)

        return search

    async def suggest(self, q: str=None, limit: int = 5, **kwargs) -> List[str]:
        if self._key is None or not q:  # pragma: no cover
            return []

        suggestion = [s for s in self._last_suggestions if s.query == q]
        if suggestion:
            suggestion = suggestion[0]
            if time() - suggestion.time < 60 * 30:
                # Move to the end
                self._last_suggestions.remove(suggestion)
                self._last_suggestions.append(suggestion)
                return suggestion.tags[:limit]
            self._last_suggestions.remove(suggestion)  # pragma: no cover

        if "key" in kwargs: del kwargs["key"]
        _params = {"key": self._key, "q": q, **kwargs}
        async with ClientSession() as sess:
            async with sess.get(f"https://tenor.googleapis.com/v2/search_suggestions", params=_params) as resp:
                suggestions = (await resp.json())["results"]

        self._last_suggestions.append(GifSuggestion(q, suggestions, int(time())))

        while len(self._last_suggestions) > self._keep_searches:  # pragma: no cover
            self._last_suggestions.pop(0)

        return suggestions[:limit]
