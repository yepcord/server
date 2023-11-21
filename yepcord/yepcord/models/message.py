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

from datetime import datetime
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ..ctx import getCore
from ..enums import MessageType
from ..models._utils import SnowflakeField, Model
from ..snowflake import Snowflake
from ..utils import ping_regex


class Message(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel", on_delete=fields.SET_NULL, null=True,
                                                     related_name="channel")
    author: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)
    content: Optional[str] = fields.TextField(max_length=2000, null=True, default=None)
    edit_timestamp: Optional[datetime] = fields.DatetimeField(null=True, default=None)
    embeds: list = fields.JSONField(default=[])
    pinned: bool = fields.BooleanField(default=False)
    webhook_id: Optional[int] = fields.BigIntField(null=True, default=None)
    webhook_author: dict = fields.JSONField(default={})
    application: Optional[int] = fields.BigIntField(null=True, default=None)
    type: int = fields.IntField(default=0)
    flags: int = fields.IntField(default=0)
    message_reference: dict = fields.JSONField(default={})
    thread: Optional[models.Channel] = fields.ForeignKeyField("models.Channel", on_delete=fields.SET_NULL,
                                                              null=True, default=None, related_name="thread")
    components: list = fields.JSONField(default=[])
    sticker_items: list = fields.JSONField(default=[])
    stickers: list = fields.JSONField(default=[])
    extra_data: dict = fields.JSONField(default={})
    guild: Optional[models.Guild] = fields.ForeignKeyField("models.Guild", on_delete=fields.SET_NULL,
                                                           null=True, default=None)
    interaction: Optional[models.Interaction] = fields.ForeignKeyField("models.Interaction", null=True, default=None)
    ephemeral: bool = fields.BooleanField(default=False)

    nonce: Optional[str] = None
    DEFAULT_RELATED = ("thread", "thread__guild", "thread__parent", "thread__owner", "channel", "author", "guild",
                       "interaction", "interaction__user", "interaction__command", "interaction__application")

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    async def ds_json(self, user_id: int = None, search: bool = False) -> dict:
        edit_timestamp = self.edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00") if self.edit_timestamp else None
        data = {
            "id": str(self.id),
            "channel_id": str(self.channel.id),
            "author": (await self.author.data).ds_json if self.author else self.webhook_author,
            "content": self.content,
            "timestamp": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "edit_timestamp": edit_timestamp,
            "edited_timestamp": edit_timestamp,
            "embeds": self.embeds,
            "pinned": self.pinned,
            "webhook_id": str(self.webhook_id) if self.webhook_id else None,
            "application_id": str(self.interaction.application.id) if self.interaction else None,
            "type": self.type,
            "flags": self.flags,
            "thread": await self.thread.ds_json(user_id) if self.thread else None,
            "components": self.components,
            "sticker_items": self.sticker_items,
            "stickers": self.stickers,
            "tts": False,
            "sticker_ids": [sticker["id"] for sticker in self.stickers],
            "attachments": [attachment.ds_json() for attachment in await getCore().getAttachments(self)],
        }
        if self.guild: data["guild_id"] = str(self.guild.id)
        data["mention_everyone"] = ("@everyone" in self.content or "@here" in self.content) if self.content else None
        data["mentions"] = []
        data["mention_roles"] = []
        if self.content:
            for ping in ping_regex.findall(self.content):
                if ping.startswith("!"):
                    ping = ping[1:]
                if ping.startswith("&"):
                    data["mention_roles"].append(ping[1:])
                    continue
                if not (member := await getCore().getUserByChannelId(self.channel.id, int(ping))):
                    continue
                if isinstance(member, (models.GuildMember, models.ThreadMember)):
                    member = member.user
                mdata = await member.data
                data["mentions"].append(mdata.ds_json)
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if (userid := self.extra_data.get("user")) and (udata := await models.UserData.get_or_none(id=userid)
                    .select_related("user")):
                data["mentions"].append(udata.ds_json)
        if self.message_reference:
            data["message_reference"] = {
                "message_id": str(self.message_reference["message_id"]),
                "channel_id": str(self.message_reference["channel_id"]),
            }
            if "guild_id" in self.message_reference:
                data["message_reference"]["guild_id"] = str(self.message_reference["guild_id"])
            if self.type in (MessageType.REPLY, MessageType.THREAD_STARTER_MESSAGE):
                ref_channel = await getCore().getChannel(int(self.message_reference["channel_id"]))
                ref_message = None
                if ref_channel:
                    ref_message = await getCore().getMessage(ref_channel, int(self.message_reference["message_id"]))
                if ref_message: ref_message.message_reference = {}
                data["referenced_message"] = await ref_message.ds_json() if ref_message else None
        if self.nonce is not None:
            data["nonce"] = self.nonce
        if not search and (reactions := await getCore().getMessageReactionsJ(self, user_id)):
            data["reactions"] = reactions

        if self.interaction:
            userdata = (await self.interaction.user.userdata).ds_json or {
                "id": "0", "username": "Deleted User", "discriminator": "0", "avatar": None}
            data["interaction"] = await self.interaction.get_command_info() | {
                "type": self.interaction.type,
                "id": str(self.interaction.id),
                "user": userdata,
            }
        return data
