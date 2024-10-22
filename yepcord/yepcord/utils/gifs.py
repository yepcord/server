"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2024 RuslanUC

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

from time import time

from httpx import AsyncClient

from .singleton import Singleton


class SlotsToDict:
    __slots__ = ()

    def json(self) -> dict:
        return {
            slot: getattr(self, slot)
            for slot in self.__slots__
        }


class GifCategory(SlotsToDict):
    __slots__ = ("name", "src",)

    def __init__(self, name: str, src: str):
        self.name = name
        self.src = src


class Gif(SlotsToDict):
    __slots__ = ("id", "title", "preview", "gif_src", "height", "width", "src", "url",)

    def __init__(self, id_: str, title: str, preview: str, gif_src: str, height: int, width: int, src: str, url: str):
        self.id = id_
        self.title = title
        self.preview = preview
        self.gif_src = gif_src
        self.height = height
        self.width = width
        self.src = src
        self.url = url


class GifSearchResult(SlotsToDict):
    __slots__ = ("query", "gifs", "time",)

    def __init__(self, query: str, gifs: list[Gif], time_: int):
        self.query = query
        self.gifs = gifs
        self.time = time_


class GifSuggestion(SlotsToDict):
    __slots__ = ("query", "tags", "time",)

    def __init__(self, query: str, tags: list[str], time_: int):
        self.query = query
        self.tags = tags
        self.time = time_


# noinspection PyTestUnpassedFixture
class Gifs(Singleton):
    __slots__ = ("_key", "_categories", "_last_searches", "_last_suggestions", "_last_update", "_keep_searches",)

    def __init__(self, key: str = None, keep_searches: int = 100):
        self._key = key
        self._categories = []
        self._last_searches = []
        self._last_suggestions = []
        self._last_update = 0
        self._keep_searches = keep_searches

    async def get_categories(self) -> list[GifCategory]:
        if time() - self._last_update > 60:
            await self._update_categories()
        return self._categories

    async def _update_categories(self) -> None:
        if self._key is None:  # pragma: no cover
            self._categories = []
            return
        categories = []
        async with AsyncClient() as client:
            resp = await client.get(f"https://tenor.googleapis.com/v2/categories?key={self._key}")
            for category in resp.json()["tags"]:
                categories.append(GifCategory(category["name"][1:], category["image"]))
        self._categories = categories
        self._last_update = time()

    async def search(self, q: str = None, **kwargs) -> GifSearchResult:
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
        async with AsyncClient() as client:
            resp = await client.get(f"https://tenor.googleapis.com/v2/search", params=_params)
            for gif in resp.json()["results"]:
                gifs.append(Gif(
                    id_=gif["id"],
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

    async def suggest(self, q: str = None, limit: int = 5, **kwargs) -> list[str]:
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
        async with AsyncClient() as client:
            resp = await client.get(f"https://tenor.googleapis.com/v2/search_suggestions", params=_params)
            suggestions = resp.json()["results"]

        self._last_suggestions.append(GifSuggestion(q, suggestions, int(time())))

        while len(self._last_suggestions) > self._keep_searches:  # pragma: no cover
            self._last_suggestions.pop(0)

        return suggestions[:limit]
