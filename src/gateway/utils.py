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
from enum import Enum, auto
from typing import Optional

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
