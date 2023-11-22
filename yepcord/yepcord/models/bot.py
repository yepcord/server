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

from os import urandom
from typing import Optional

from tortoise import fields

from . import User
from ._utils import SnowflakeField, Model
from ..utils import b64encode
import yepcord.yepcord.models as models


def gen_token_secret() -> str:
    return b64encode(urandom(48))


class Bot(Model):
    id: int = SnowflakeField(pk=True)
    application: models.Application = fields.ForeignKeyField("models.Application", null=False, unique=True)
    user: User = fields.ForeignKeyField("models.User", null=True, default=None, related_name="bot_user")
    bot_public: bool = fields.BooleanField(default=True)
    bot_require_code_grant: bool = fields.BooleanField(default=True)
    token_secret: str = fields.CharField(max_length=128, default=gen_token_secret)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.token_secret}"

    @classmethod
    async def from_token(cls, token: str) -> Optional[Bot]:
        token = models.Authorization.extract_token(token)
        if token is None:
            return
        bot_id, secret = token
        return await Bot.get_or_none(id=bot_id, token_secret=secret).select_related("user")
