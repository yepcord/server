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

import ormar
from ormar import ReferentialAction

from . import DefaultMeta, SnowflakeAIQuerySet, Application, Guild, Channel, User, ApplicationCommand
from ..ctx import getCore
from ..enums import InteractionType, ChannelType, InteractionStatus
from ..utils import b64encode


def gen_interaction_token() -> str:
    return b64encode(urandom(32))


class Interaction(ormar.Model):
    class Meta(DefaultMeta):
        queryset_class = SnowflakeAIQuerySet

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    application: Application = ormar.ForeignKey(Application, on_delete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, on_delete=ReferentialAction.CASCADE)
    type: int = ormar.Integer(choices=InteractionType.values_set())
    data: Optional[dict] = ormar.JSON(default=None)
    token: str = ormar.String(max_length=128, default=gen_interaction_token)
    guild: Optional[Guild] = ormar.ForeignKey(Guild, on_delete=ReferentialAction.SET_NULL, nullable=True, default=None)
    channel: Optional[Channel] = ormar.ForeignKey(Channel, on_delete=ReferentialAction.SET_NULL, nullable=True,
                                                  default=None)
    message_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    locale: Optional[str] = ormar.String(max_length=8, nullable=True, default=None)
    guild_locale: Optional[str] = ormar.String(max_length=8, nullable=True, default=None)
    nonce: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    session_id: str = ormar.String(max_length=64)
    status: int = ormar.Integer(choices=InteractionStatus.values_set(), default=InteractionStatus.PENDING)
    command: Optional[ApplicationCommand] = ormar.ForeignKey(ApplicationCommand, on_delete=ReferentialAction.SET_NULL,
                                                             nullable=True, default=None)

    async def ds_json(self, with_user=False, with_token=False) -> dict:
        data = {
            "id": str(self.id),
            "application_id": str(self.application.id),
            "type": self.type,
            "version": 1,
        }

        if self.data is not None:
            data["data"] = self.data

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
