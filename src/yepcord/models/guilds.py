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

from . import DefaultMeta, User
from .channels import Channel
from ..snowflake import Snowflake


class Guild(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    owner: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    name: str = ormar.String(max_length=64)
    features: list = ormar.JSON(default=[])
    icon: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    description: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    splash: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    discovery_splash: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    banner: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    region: str = ormar.String(max_length=64, default="deprecated")
    #afk_channel: Optional[Channel] = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, nullable=True,
    #                                                  default=None, related_name="afk_channel")
    #system_channel: Optional[Channel] = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, nullable=True,
    #                                                     default=None, related_name="system_channel")
    afk_channel: Optional[int] = ormar.BigInteger(nullable=True, default=None) # TODO: use ForeignKey instead of BigInteger (if that's event possible)
    system_channel: Optional[int] = ormar.BigInteger(nullable=True, default=None) # TODO: use ForeignKey instead of BigInteger (if that's event possible)
    afk_timeout: int = ormar.Integer(default=300)
    verification_level: int = ormar.Integer(default=0)
    default_message_notifications: int = ormar.Integer(default=0)
    mfa_level: int = ormar.Integer(default=0)
    explicit_content_filter: int = ormar.Integer(default=0)
    system_channel_flags: int = ormar.BigInteger(default=0)
    max_members: int = ormar.Integer(default=100)
    vanity_url_code: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)
    preferred_locale: str = ormar.String(max_length=8, default="en-US")
    premium_progress_bar_enabled: bool = ormar.Boolean(default=False)
    nsfw: bool = ormar.Boolean(default=False)
    nsfw_level: int = ormar.Integer(default=0)


class Role(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    name: str = ormar.String(max_length=64)
    permissions: int = ormar.BigInteger(default=1071698660929)
    position: int = ormar.Integer(default=0)
    color: int = ormar.BigInteger(default=0)
    hoist: bool = ormar.Boolean(default=False)
    managed: bool = ormar.Boolean(default=False)
    mentionable: bool = ormar.Boolean(default=False)
    icon: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    unicode_emoji: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    flags: int = ormar.BigInteger(default=0)


class GuildMember(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    avatar: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    communication_disabled_until: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    flags: int = ormar.BigInteger(default=0)
    nick: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    mute: bool = ormar.Boolean(default=False)
    deaf: bool = ormar.Boolean(default=False)
    roles: Optional[list[Role]] = ormar.ManyToMany(Role)

    @property
    def joined_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)


class Emoji(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    name: str = ormar.String(max_length=64)
    user: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    require_colons: bool = ormar.Boolean(default=True)
    managed: bool = ormar.Boolean(default=False)
    animated: bool = ormar.Boolean(default=False)
    available: bool = ormar.Boolean(default=True)


class GuildBan(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    reason: str = ormar.String(max_length=512)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)


class Sticker(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    name: str = ormar.String(max_length=64)
    user: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    type: int = ormar.Integer()
    format: int = ormar.Integer()
    description: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    tags: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)


class GuildTemplate(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    name: str = ormar.String(max_length=64)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    description: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    usage_count: int = ormar.BigInteger(default=0)
    creator: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    serialized_guild: dict = ormar.JSON(default={})
    updated_at: Optional[datetime] = ormar.DateTime()
    is_dirty: bool = ormar.Boolean(default=False)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)


class GuildEvent(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    creator: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    channel: Optional[Channel] = ormar.ForeignKey(Channel, ondelete=ReferentialAction.SET_NULL, nullable=True, default=None)
    name: str = ormar.String(max_length=64)
    description: Optional[str] = ormar.String(max_length=128, nullable=True, default=None)
    start: datetime = ormar.DateTime()
    end: Optional[datetime] = ormar.DateTime(nullable=True, default=None)
    privacy_level: int = ormar.Integer(default=2)
    status: int = ormar.Integer(default=1)
    entity_type: int = ormar.Integer()
    entity_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    entity_metadata: dict = ormar.JSON(default={})
    image: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    subscribers: list[GuildMember] = ormar.ManyToMany(GuildMember)


class AuditLogEntry(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    user: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    target_id: int = ormar.BigInteger(nullable=True, default=None)
    action_type: int = ormar.Integer()
    reason: Optional[str] = ormar.String(max_length=512, nullable=True, default=None)
    changes: list = ormar.JSON(default=[])
    options: dict = ormar.JSON(default={})
