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
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class WebhookUtils:
    @staticmethod
    async def get(webhook_id: int) -> Optional[models.Webhook]:
        return await Webhook.get_or_none(id=webhook_id).select_related("channel", "channel__guild", "user")


class Webhook(Model):
    Y = WebhookUtils

    id: int = SnowflakeField(pk=True)
    type: int = fields.IntField()
    name: str = fields.CharField(max_length=128)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    user: models.User = fields.ForeignKeyField("models.User")
    application_id: Optional[int] = fields.BigIntField(null=True, default=None)
    avatar: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    token: Optional[str] = fields.CharField(max_length=128)

    async def ds_json(self) -> dict:
        userdata = await self.user.data
        return {
            "type": self.type,
            "id": str(self.id),
            "name": self.name,
            "avatar": self.avatar,
            "channel_id": str(self.channel.id),
            "guild_id": str(self.channel.guild.id),
            "application_id": str(self.application_id) if self.application_id is not None else self.application_id,
            "token": self.token,
            "user": userdata.ds_json
        }
