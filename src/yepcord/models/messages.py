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

import ormar
from ormar import ReferentialAction
from pydantic import Field

from . import DefaultMeta, User, Channel, Guild, Emoji, GuildMember, ThreadMember, UserData
from ..config import Config
from ..ctx import getCore
from ..enums import MessageType
from ..snowflake import Snowflake
from ..utils import ping_regex


class Message(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, related_name="channel")
    author: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    content: Optional[str] = ormar.String(max_length=2000, nullable=True, default=None, collation="utf8mb4_general_ci")
    edit_timestamp: Optional[datetime] = ormar.DateTime(nullable=True, default=None)
    embeds: list = ormar.JSON(default=[])
    pinned: bool = ormar.Boolean(default=False)
    webhook_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    webhook_author: dict = ormar.JSON(default={})
    application: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    type: int = ormar.Integer(default=0)
    flags: int = ormar.Integer(default=0)
    message_reference: dict = ormar.JSON(default={})
    thread: Optional[Channel] = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, nullable=True,
                                                 default=None, related_name="thread")
    components: list = ormar.JSON(default=[])
    sticker_items: list = ormar.JSON(default=[])
    stickers: list = ormar.JSON(default=[])
    extra_data: dict = ormar.JSON(default={})
    guild: Optional[Guild] = ormar.ForeignKey(Guild, ondelete=ReferentialAction.SET_NULL, nullable=True, default=None)

    nonce: Optional[str] = Field()

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    async def ds_json(self, user_id: int=None, search: bool=False) -> dict:
        edit_timestamp = self.edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00") if self.edit_timestamp else None
        data = {
            "id": str(self.id),
            "channel_id": str(self.channel.id),
            "author": (await self.author.data).ds_json if self.author else self.webhook_author,
            "content": self.content,
            "timestamp": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "edit_timestamp": edit_timestamp,
            "embeds": self.embeds,
            "pinned": self.pinned,
            "webhook_id": self.webhook_id,
            "application_id": self.application,
            "type": self.type,
            "flags": self.flags,
            "thread": await self.thread.ds_json(user_id) if self.thread is not None else None,
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
        data["attachments"] = []
        if self.content:
            for ping in ping_regex.findall(self.content):
                if ping.startswith("!"):
                    ping = ping[1:]
                if ping.startswith("&"):
                    data["mention_roles"].append(ping[1:])
                    continue
                if not (member := await getCore().getUserByChannelId(self.channel.id, int(ping))):
                    continue
                if isinstance(member, GuildMember):
                    member = member.user
                elif isinstance(member, ThreadMember):
                    member = member.user
                mdata = await member.data
                data["mentions"].append(mdata.ds_json)
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if (user_id := self.extra_data.get("user")) and (udata := await UserData.objects.get_or_none(id=user_id)):
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
        return data


class Attachment(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL)
    message: Message = ormar.ForeignKey(Message, ondelete=ReferentialAction.CASCADE)
    filename: str = ormar.String(max_length=128, collation="utf8mb4_general_ci")
    size: str = ormar.Integer()
    content_type: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    metadata: dict = ormar.JSON(default={})

    def ds_json(self) -> dict:
        data = {
            "filename": self.filename,
            "id": str(self.id),
            "size": self.size,
            "url": f"https://{Config.CDN_HOST}/attachments/{self.channel.id}/{self.id}/{self.filename}"
        }
        if self.content_type:
            data["content_type"] = self.content_type
        if self.metadata:
            data.update(self.metadata)
        return data


class Reactions(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    message: Message = ormar.ForeignKey(Message, ondelete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    emoji: Optional[Emoji] = ormar.ForeignKey(Emoji, ondelete=ReferentialAction.SET_NULL, nullable=True, default=None)
    emoji_name: Optional[str] = ormar.String(max_length=128, nullable=True, default=None,
                                             collation="utf8mb4_general_ci")
