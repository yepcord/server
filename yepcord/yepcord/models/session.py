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

from __future__ import annotations
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..utils import b64encode, int_size, b64decode


class Session(Model):
    id: int = SnowflakeField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    signature: str = fields.CharField(max_length=128)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.user.id).encode('utf8'))}." \
               f"{b64encode(int.to_bytes(self.id, int_size(self.id), 'big'))}." \
               f"{self.signature}"

    @staticmethod
    def extract_token(token: str) -> Optional[tuple[int, int, str]]:
        token = token.split(".")
        if len(token) != 3:
            return
        uid, sid, sig = token
        try:
            uid = int(b64decode(uid))
            sid = int.from_bytes(b64decode(sid), "big")
            b64decode(sig)
        except ValueError:
            return
        return uid, sid, sig

    @classmethod
    async def from_token(cls, token: str) -> Optional[Session]:
        token = Session.extract_token(token)
        if token is None:
            return
        user_id, session_id, signature = token
        return await Session.get_or_none(id=session_id, user__id=user_id, signature=signature).select_related("user")
