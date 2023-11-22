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

from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class Emoji(Model):
    id: int = SnowflakeField(pk=True)
    name: str = fields.CharField(max_length=64)
    user: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    require_colons: bool = fields.BooleanField(default=True)
    managed: bool = fields.BooleanField(default=False)
    animated: bool = fields.BooleanField(default=False)
    available: bool = fields.BooleanField(default=True)

    async def ds_json(self, with_user: bool=False) -> dict:
        data = {
            "name": self.name,
            "roles": [],
            "id": str(self.id),
            "require_colons": bool(self.require_colons),
            "managed": bool(self.managed),
            "animated": bool(self.animated),
            "available": bool(self.available)
        }
        if with_user and self.user is not None:
            userdata = await self.user.data
            data["user"] = userdata.ds_json
        return data
