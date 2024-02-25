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
from time import time
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from . import User, Guild
from ._utils import SnowflakeField, Model
from ..utils import b64encode, b64decode


def gen_secret_key() -> str:
    return b64encode(urandom(32))


def gen_token_secret() -> str:
    return b64encode(urandom(48))


class Authorization(Model):
    id: int = SnowflakeField(pk=True)
    user: User = fields.ForeignKeyField("models.User")
    application: models.Application = fields.ForeignKeyField("models.Application")
    guild: Optional[Guild] = fields.ForeignKeyField("models.Guild", null=True, default=None)
    scope: str = fields.CharField(max_length=1024)
    secret: str = fields.CharField(max_length=128, default=gen_token_secret)
    refresh_token: str = fields.CharField(max_length=128, default=gen_token_secret, null=True)
    expires_at: int = fields.BigIntField(default=lambda: int(time() + 60 * 3))
    auth_code: Optional[str] = fields.CharField(max_length=128, null=True, default=gen_secret_key)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.secret}"

    @property
    def ref_token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.refresh_token}"

    @property
    def code(self) -> str:
        return f"{b64encode(str(self.id))}.{self.auth_code}"

    @property
    def scope_set(self) -> set[str]:
        return set(self.scope.split(" "))

    @staticmethod
    def extract_token(token: str) -> Optional[tuple[int, str]]:
        token = token.split(".")
        if len(token) != 2:
            return
        auth_id, secret = token
        try:
            auth_id = int(b64decode(auth_id))
            b64decode(secret)
        except ValueError:
            return
        return auth_id, secret

    @classmethod
    async def from_token(cls, token: str) -> Optional[Authorization]:
        token = Authorization.extract_token(token)
        if token is None:
            return
        auth_id, secret = token
        return await (Authorization.get_or_none(id=auth_id, secret=secret, expires_at__gt=int(time()))
                      .select_related("user"))
