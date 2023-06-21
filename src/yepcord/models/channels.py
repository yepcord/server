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

from . import DefaultMeta, User
from ..snowflake import Snowflake

GuildRef = ForwardRef("Guild")
ChannelRef = ForwardRef("Channel")

class Channel(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    type: int = ormar.Integer()
    guild: Optional[GuildRef] = ormar.ForeignKey(GuildRef, ondelete=ReferentialAction.CASCADE, nullable=True,
                                                 default=None)
    position: Optional[int] = ormar.Integer(nullable=True, default=None)
    name: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    topic: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    nsfw: Optional[bool] = ormar.Boolean(nullable=True, default=None)
    bitrate: Optional[int] = ormar.Integer(nullable=True, default=None)
    user_limit: Optional[int] = ormar.Integer(nullable=True, default=None)
    rate_limit: Optional[int] = ormar.Integer(nullable=True, default=None)
    recipients: Optional[list[User]] = ormar.ManyToMany(User, nullable=True, default=None, related_name="recipients_mm")
    icon: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    owner: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, nullable=True, default=None,
                                             related_name="owner")
    application_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    parent: Optional[ChannelRef] = ormar.ForeignKey(ChannelRef, ondelete=ReferentialAction.SET_NULL, nullable=True,
                                                    default=None)
    rtc_region: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)
    video_quality_mode: Optional[int] = ormar.Integer(nullable=True, default=None)
    default_auto_archive: Optional[int] = ormar.Integer(nullable=True, default=None)
    flags: Optional[int] = ormar.Integer(nullable=True, default=None)


class ThreadMetadata(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    archived: bool = ormar.Boolean(default=False)
    locked: bool = ormar.Boolean(default=False)
    archive_timestamp: datetime = ormar.DateTime()
    auto_archive_duration: int = ormar.BigInteger()


class ThreadMember(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    guild: GuildRef = ormar.ForeignKey(GuildRef, ondelete=ReferentialAction.CASCADE)

    @property
    def joined_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)


class HiddenDmChannel(ormar.Model):
    class Meta(DefaultMeta):
        constraints = [ormar.UniqueColumns("user", "channel")]

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)


class PermissionOverwrite(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    target_id: int = ormar.BigInteger()
    type: int = ormar.Integer()
    allow: int = ormar.BigInteger()
    deny: int = ormar.BigInteger()


class Invite(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    type: int = ormar.Integer(default=1)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    inviter: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    max_age: int = ormar.BigInteger()
    max_uses: int = ormar.BigInteger(default=0)
    uses: int = ormar.BigInteger(default=0)
    vanity_code: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)


class Webhook(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    type: int = ormar.Integer()
    name: str = ormar.String(max_length=128)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    application_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    avatar: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    token: Optional[str] = ormar.String(max_length=128)


class ReadState(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    last_read_id: int = ormar.BigInteger()
    count: int = ormar.Integer()
