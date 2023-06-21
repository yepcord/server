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
from typing import Optional, ForwardRef

import ormar
from ormar import ReferentialAction

from . import DefaultMeta, User, Channel, Guild, Emoji
from ..snowflake import Snowflake


class Message(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, related_name="channel")
    author: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    content: Optional[str] = ormar.String(max_length=2000, nullable=True, default=None)
    edit_timestamp: Optional[datetime] = ormar.DateTime(nullable=True, default=None)
    embeds: list = ormar.JSON(default=[])
    pinned: bool = ormar.Boolean(default=False)
    webhook_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    webhook_author: dict = ormar.JSON(default={})
    application: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    type: int = ormar.Integer(default=0)
    flags: int = ormar.Integer(default=0)
    message_reference: dict = ormar.JSON({})
    thread: Optional[Channel] = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, nullable=True,
                                                 default=None, related_name="thread")
    components: list = ormar.JSON(default=[])
    sticker_items: list = ormar.JSON(default=[])
    stickers: list = ormar.JSON(default=[])
    extra_data: list = ormar.JSON(default={})
    guild: Optional[Guild] = ormar.ForeignKey(Guild, ondelete=ReferentialAction.SET_NULL, nullable=True,
                                                 default=None)


class Attachment(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL)
    message: Message = ormar.ForeignKey(Message, ondelete=ReferentialAction.CASCADE)
    filename: str = ormar.String(max_length=128)
    size: str = ormar.Integer()
    content_type: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    metadata: dict = ormar.JSON(default={})


class Reactions(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    message: Message = ormar.ForeignKey(Message, ondelete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    emoji: Optional[Emoji] = ormar.ForeignKey(Emoji, ondelete=ReferentialAction.SET_NULL, nullable=True, default=None)
    emoji_name: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
