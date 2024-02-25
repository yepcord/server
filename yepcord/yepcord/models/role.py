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


class Role(Model):
    id: int = SnowflakeField(pk=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    name: str = fields.CharField(max_length=64)
    permissions: int = fields.BigIntField(default=1071698660929)
    position: int = fields.IntField(default=0)
    color: int = fields.BigIntField(default=0)
    hoist: bool = fields.BooleanField(default=False)
    managed: bool = fields.BooleanField(default=False)
    mentionable: bool = fields.BooleanField(default=False)
    icon: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    unicode_emoji: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    flags: int = fields.BigIntField(default=0)
    tags: Optional[dict] = fields.JSONField(default=None, null=True)

    guildmembers: fields.ReverseRelation[models.GuildMember]

    def ds_json(self) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "permissions": str(self.permissions),
            "position": self.position,
            "color": self.color,
            "hoist": bool(self.hoist),
            "managed": bool(self.managed),
            "mentionable": bool(self.mentionable),
            "icon": self.icon,
            "unicode_emoji": self.unicode_emoji,
            "flags": self.flags
        }

        if self.tags is not None:
            data["tags"] = self.tags

        return data
