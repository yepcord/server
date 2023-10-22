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

from time import time
from typing import Optional

from tortoise.models import Model
from tortoise import fields

import src.yepcord.models as models


def time_plus_150s():
    return int(time()) + 150


class RemoteAuthSession(Model):
    id: int = fields.BigIntField(pk=True)
    fingerprint: str = fields.CharField(max_length=64, unique=True)
    user: Optional[models.User] = fields.ForeignKeyField("models.User", null=True, default=None)
    expires_at: int = fields.IntField(default=time_plus_150s)
