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
from enum import Enum, auto
from typing import Optional
from zlib import compressobj, Z_FULL_FLUSH

from redis.asyncio import Redis

from ..yepcord.config import Config
from ..yepcord.utils import b64decode


def require_auth(func):
    async def wrapped(self, *args, **kwargs):
        if self.user_id is None:
            return self.ws.close(4005)
        return await func(self, *args, **kwargs)

    return wrapped


class TokenType(Enum):
    USER = auto()
    BOT = auto()


def get_token_type(token: str) -> Optional[TokenType]:
    if not token:
        return

    token = token.split(".")
    if len(token) not in {2, 3}:
        return

    try:
        user_id = int(b64decode(token[0]))
        assert (user_id >> 22) > 0
    except (ValueError, AssertionError):
        return

    return TokenType.USER if len(token) == 3 else TokenType.BOT


async def init_redis_pool() -> Optional[Redis]:
    if not Config.REDIS_URL:
        return
    return Redis.from_url(
        Config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


class ZlibCompressor:
    __slots__ = ("_obj",)

    def __init__(self):
        self._obj = compressobj()

    def __call__(self, data):
        return self._obj.compress(data) + self._obj.flush(Z_FULL_FLUSH)
