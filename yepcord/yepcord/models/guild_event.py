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

from datetime import datetime
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ..ctx import getCore
from ..enums import ScheduledEventEntityType
from ._utils import SnowflakeField, Model


class GuildEvent(Model):
    id: int = SnowflakeField(pk=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    creator: models.User = fields.ForeignKeyField("models.User")
    channel: Optional[models.Channel] = fields.ForeignKeyField("models.Channel", on_delete=fields.SET_NULL,
                                                               null=True, default=None)
    name: str = fields.CharField(max_length=64)
    description: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    start: datetime = fields.DatetimeField()
    end: Optional[datetime] = fields.DatetimeField(null=True, default=None)
    privacy_level: int = fields.IntField(default=2)
    status: int = fields.IntField(default=1)
    entity_type: int = fields.IntField()
    entity_id: Optional[int] = fields.BigIntField(null=True, default=None)
    entity_metadata: dict = fields.JSONField(default={}, null=True)
    image: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    subscribers = fields.ManyToManyField("models.GuildMember")

    async def ds_json(self, with_user: bool = False, with_user_count: bool = False) -> dict:
        channel_id = str(self.channel.id) if self.channel else None
        entity_id = str(self.entity_id) if self.entity_id else None
        start_time = self.start.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        end_time = None
        if self.end:
            end_time = self.end.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        data = {
            "id": str(self.id),
            "guild_id": str(self.guild.id),
            "channel_id": str(channel_id),
            "creator_id": str(self.creator.id),
            "name": self.name,
            "description": self.description,
            "scheduled_start_time": start_time,
            "scheduled_end_time": end_time,
            "privacy_level": self.privacy_level,
            "status": self.status,
            "entity_type": self.entity_type,
            "entity_id": entity_id,
            "image": self.image
        }
        if self.entity_type == ScheduledEventEntityType.EXTERNAL:
            data["entity_metadata"] = self.entity_metadata
        if with_user:
            creator = await self.creator.data
            data["creator"] = creator.ds_json
        if with_user_count:
            data["user_count"] = await getCore().getGuildEventUserCount(self)
        return data
