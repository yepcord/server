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


class Sticker(Model):
    id: int = SnowflakeField(pk=True)
    name: str = fields.CharField(max_length=64)
    user: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    type: int = fields.IntField()
    format: int = fields.IntField()
    description: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    tags: Optional[str] = fields.CharField(max_length=64, null=True, default=None)

    async def ds_json(self, with_user: bool=True) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "type": self.type,
            "format_type": self.format,
            "guild_id": str(self.guild.id),
            "available": True,
            "asset": ""
        }
        if with_user and self.user is not None:
            userdata = await self.user.data
            data["user"] = userdata.ds_json
        return data
