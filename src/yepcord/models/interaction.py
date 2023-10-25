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
from os import urandom
from typing import Optional

from tortoise import fields

import src.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..ctx import getCore
from ..enums import InteractionType, ChannelType, InteractionStatus
from ..utils import b64encode


def gen_interaction_token() -> str:
    return b64encode(urandom(32))


class Interaction(Model):
    id: int = SnowflakeField(pk=True)
    application: models.Application = fields.ForeignKeyField("models.Application")
    user: models.User = fields.ForeignKeyField("models.User")
    type: int = fields.IntField(choices=InteractionType.values_set())
    data: Optional[dict] = fields.JSONField(default=None)
    token: str = fields.CharField(max_length=128, default=gen_interaction_token)
    guild: Optional[models.Guild] = fields.ForeignKeyField("models.Guild", on_delete=fields.SET_NULL,
                                                           null=True, default=None)
    channel: Optional[models.Channel] = fields.ForeignKeyField("models.Channel", on_delete=fields.SET_NULL,
                                                               null=True, default=None)
    message_id: Optional[int] = fields.BigIntField(null=True, default=None)
    locale: Optional[str] = fields.CharField(max_length=8, null=True, default=None)
    guild_locale: Optional[str] = fields.CharField(max_length=8, null=True, default=None)
    nonce: Optional[int] = fields.BigIntField(null=True, default=None)
    session_id: str = fields.CharField(max_length=64)
    status: int = fields.IntField(choices=InteractionStatus.values_set(), default=InteractionStatus.PENDING)
    command: Optional[models.ApplicationCommand] = fields.ForeignKeyField("models.ApplicationCommand", null=True,
                                                                          on_delete=fields.SET_NULL, default=None)

    async def ds_json(self, with_user=False, with_token=False, resolved: dict = None) -> dict:
        data = {
            "id": str(self.id),
            "application_id": str(self.application.id),
            "type": self.type,
            "version": 1,
        }

        if self.data is not None:
            data["data"] = self.data
            if resolved is not None:
                data["data"] |= {"resolved": resolved}

        if self.guild is not None:
            data["guild_id"] = self.guild.id
            member = await getCore().getGuildMember(self.guild, self.user.id)
            data["member"] = await member.ds_json()

            if (bot_member := await getCore().getGuildMember(self.guild, self.application.id)) is not None:
                data["app_permissions"] = str(await bot_member.permissions)

        if self.channel is not None:
            data["channel_id"] = self.channel.id
            data["channel"] = await self.channel.ds_json()

        if self.message_id is not None and (message := await getCore().getMessage(self.channel, self.message_id)):
            data["message"] = await message.ds_json()

        if self.locale is not None:
            data["locale"] = self.locale

        if self.guild_locale is not None:
            data["guild_locale"] = self.guild_locale

        if with_user or self.channel.type == ChannelType.DM:
            userdata = await self.user.userdata
            data["user"] = userdata.ds_json

        if with_token:
            data["token"] = self.token

        return data
