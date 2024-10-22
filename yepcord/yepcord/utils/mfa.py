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

from __future__ import annotations

import re
from base64 import b32decode
from hmac import new
from json import loads
from struct import pack, unpack
from time import time
from typing import Union, Optional

from .jwt import JWT
from ..config import Config
from ..utils import b64decode, assert_


class MFA:
    _re = re.compile(r'^[A-Z0-9]{16}$')

    def __init__(self, key: str, uid: int):
        self.key = str(key).upper()
        self.uid = self.id = uid

    def get_code(self, timestamp: Union[int, float] = None) -> str:
        if timestamp is None:
            timestamp = time()
        key = b32decode(self.key.upper() + '=' * ((8 - len(self.key)) % 8))
        counter = pack('>Q', int(timestamp / 30))
        mac = new(key, counter, "sha1").digest()
        offset = mac[-1] & 0x0f
        binary = unpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
        return str(binary)[-6:].zfill(6)

    def get_codes(self) -> tuple[str, str]:
        return self.get_code(time() - 5), self.get_code(time() + 1)

    @property
    def valid(self) -> bool:
        return bool(self._re.match(self.key))

    @staticmethod
    async def get_from_ticket(ticket: str) -> Optional[MFA]:
        from ..models import User

        try:
            user_id, session_id, sig = ticket.split(".")
            user_id = loads(b64decode(user_id).decode("utf8"))[0]
            session_id = int.from_bytes(b64decode(session_id), "big")
            sig = b64decode(sig).decode("utf8")

            assert_(user := await User.y.get(user_id))
            assert_(payload := JWT.decode(sig, b64decode(Config.KEY)))
            assert_(payload["u"] == user.id)
            assert_(payload["s"] == session_id)
        except (ValueError, IndexError):
            return

        return MFA(await user.get_mfa_key(), user_id)

    @staticmethod
    async def nonce_to_code(nonce: str) -> Optional[str]:
        key = b64decode(Config.KEY)

        if not (payload := JWT.decode(nonce, key)):
            return
        token = JWT.encode({"code": payload["c"]}, key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()
