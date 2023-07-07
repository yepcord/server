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
from datetime import datetime, timedelta
from typing import Optional, ForwardRef, Union

from ormar.relations.relation_proxy import RelationProxy
from typing_extensions import TYPE_CHECKING

from ..utils import b64encode, int_length

if TYPE_CHECKING:
    from . import Message

import ormar
from ormar import ReferentialAction, QuerySet
from pydantic import Field

from . import DefaultMeta, User
from ..ctx import getCore
from ..enums import ChannelType
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
    recipients: Optional[Union[RelationProxy, QuerySet]] = ormar.ManyToMany(User, nullable=True, default=None,
                                                                            related_name="recipients_mm")
    icon: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    owner: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, nullable=True, default=None,
                                             related_name="owner")
    application_id: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    parent: Optional[ChannelRef] = ormar.ForeignKey(ChannelRef, ondelete=ReferentialAction.SET_NULL, nullable=True,
                                                    default=None)
    rtc_region: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)
    video_quality_mode: Optional[int] = ormar.Integer(nullable=True, default=None)
    default_auto_archive: Optional[int] = ormar.Integer(nullable=True, default=None)
    flags: Optional[int] = ormar.Integer(nullable=True, default=0)

    last_message_id: Optional[int] = Field()

    async def ds_json(self, user_id: int=None, with_ids: bool=True) -> dict:
        if self.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            self.last_message_id = await getCore().getLastMessageId(self)
        last_message_id = str(self.last_message_id) if self.last_message_id is not None else None
        recipients = []
        if self.type in (ChannelType.DM, ChannelType.GROUP_DM):
            exclude = {} if not user_id else {"id": user_id}
            recipients = await self.recipients.exclude(**exclude).all()
            if with_ids:
                recipients = [str(recipient.id) for recipient in recipients]
            else:
                _recipients = recipients
                recipients = []
                for recipient in _recipients:
                    userdata = await recipient.data
                    recipients.append(userdata.ds_json)

        base_data = {
            "id": str(self.id),
            "type": self.type,
        }

        if self.type == ChannelType.DM:
            return base_data | {
                "recipient_ids" if with_ids else "recipients": recipients,
                "last_message_id": last_message_id,
            }
        elif self.type == ChannelType.GROUP_DM:
            return base_data | {
                "recipient_ids" if with_ids else "recipients": recipients,
                "last_message_id": last_message_id,
                "owner_id": str(self.owner.id),
                "name": self.name,
                "icon": self.icon
            }
        elif self.type == ChannelType.GUILD_CATEGORY:
            return base_data | {
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent is not None else None,
                "name": self.name,
                "flags": self.flags,
                "guild_id": str(self.guild.id)
            }
        elif self.type == ChannelType.GUILD_TEXT:
            return base_data | {
                "topic": self.topic,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent is not None else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "guild_id": str(self.guild.id),
                "nsfw": self.nsfw
            }
        elif self.type == ChannelType.GUILD_VOICE:
            return base_data | {
                "user_limit": self.user_limit,
                "rtc_region": self.rtc_region,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent is not None else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "bitrate": self.bitrate,
                "guild_id": str(self.guild.id)
            }
        elif self.type == ChannelType.GUILD_NEWS:
            return base_data | {
                "topic": self.topic,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent is not None else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "guild_id": str(self.guild.id),
                "nsfw": self.nsfw
            }
        elif self.type == ChannelType.GUILD_PUBLIC_THREAD:
            message_count = await getCore().getChannelMessagesCount(self)
            data = base_data | {
                "guild_id": str(self.guild.id),
                "parent_id": str(self.parent_id),
                "owner_id": str(self.owner.id),
                "name": self.name,
                "last_message_id": last_message_id,
                "thread_metadata": (await getCore().getThreadMetadata(self)).ds_json(),
                "message_count": message_count,
                "member_count": await getCore().getThreadMembersCount(self),
                "rate_limit_per_user": self.rate_limit,
                "flags": self.flags,
                "total_message_sent": message_count,
                "member_ids_preview": [str(member.user.id) for member in await getCore().getThreadMembers(self, 10)]
            }
            if user_id:
                member = await getCore().getThreadMember(self, user_id)
                data["member"] = {
                    "muted": False,
                    "mute_config": None,
                    "join_timestamp": member.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
                    "flags": 1
                }

            return data

    async def messages(self, limit: int=50, before: int=0, after: int=0) -> list[Message]:
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await getCore().getChannelMessages(self, limit, before, after)

    async def other_user(self, current_user: User) -> Optional[User]:
        if self.type != ChannelType.DM:
            return
        return await self.recipients.exclude(id=current_user.id).get_or_none()


class ThreadMetadata(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    archived: bool = ormar.Boolean(default=False)
    locked: bool = ormar.Boolean(default=False)
    archive_timestamp: datetime = ormar.DateTime()
    auto_archive_duration: int = ormar.BigInteger()

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    def ds_json(self) -> dict:
        archive_timestamp = self.created_at
        archive_timestamp += timedelta(minutes=self.auto_archive_duration)
        return {
            "archived": bool(self.archived),
            "archive_timestamp": archive_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "auto_archive_duration": self.auto_archive_duration,
            "locked": bool(self.locked),
            "create_timestamp": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        }


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

    def ds_json(self) -> dict:
        return {
            "user_id": str(self.user.id),
            "muted": False,
            "mute_config": None,
            "join_timestamp": self.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "id": str(self.channel.id),
            "guild_id": str(self.guild.id),
            "flags": 1
        }


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

    def ds_json(self) -> dict:
        return {
            "type": self.type,
            "id": str(self.target_id),
            "deny": str(self.deny),
            "allow": str(self.allow)
        }


class Invite(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    type: int = ormar.Integer(default=1)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    inviter: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    max_age: int = ormar.BigInteger(default=86400)
    max_uses: int = ormar.BigInteger(default=0)
    uses: int = ormar.BigInteger(default=0)
    vanity_code: Optional[str] = ormar.String(max_length=64, nullable=True, default=None)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_length(self.id), 'big'))

    async def ds_json(self, with_counts: bool=False) -> dict:
        userdata = await self.inviter.data
        expires_at = None
        if self.max_age > 0:
            expires_timestamp = int(Snowflake.toTimestamp(self.id) / 1000) + self.max_age
            expires_at = datetime.utcfromtimestamp(expires_timestamp).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        data = {
            "code": self.code,
            "inviter": userdata.ds_json,
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "expires_at": expires_at,
            "type": self.type,
            "channel": {
                "id": str(self.channel.id),
                "type": self.channel.type
            },
            "max_age": self.max_age,
        }

        if with_counts:
            related_users = await getCore().getRelatedUsersToChannel(self.channel_id)
            data["approximate_member_count"] = len(related_users)
            if self.channel.type == ChannelType.GROUP_DM:
                data["channel"]["recipients"] = [
                    {"username": (await rel_user.data).username}
                    for rel_user in related_users
                ]

        if self.channel.type == ChannelType.GROUP_DM:
            data["channel"].update({"name": self.channel.name, "icon": self.channel.icon})
        elif self.channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
            data["channel"]["name"] = self.channel.name

        if self.channel.guild:
            guild = self.channel.guild
            print(guild)
            print(guild.features)
            data["guild"] = {
                "id": str(guild.id),
                "banner": guild.banner,
                "description": guild.description,
                "features": [
                    "ANIMATED_ICON",
                    "BANNER",
                    "INVITE_SPLASH",
                    "VANITY_URL",
                    "PREMIUM_TIER_3_OVERRIDE",
                    "ROLE_ICONS",
                    *guild.features
                ],
                "icon": guild.icon,
                "name": guild.name,
                "nsfw": guild.nsfw,
                "nsfw_level": guild.nsfw_level,
                "premium_subscription_count": 30,
                "splash": guild.splash,
                "vanity_url_code": guild.vanity_url_code,
                "verification_level": guild.verification_level
            }
            data["max_uses"] = self.max_uses
            data["uses"] = self.uses
            data["temporary"] = False
            if self.vanity_code:
                data["code"] = self.vanity_code

        return data


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


class ReadState(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    channel: Channel = ormar.ForeignKey(Channel, ondelete=ReferentialAction.CASCADE)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    last_read_id: int = ormar.BigInteger()
    count: int = ormar.Integer()

    @property
    def ds_json(self) -> dict:
        return {
            "mention_count": self.count,
            "last_pin_timestamp": ...,
            "last_message_id": str(self.last_read_id),
            "id": str(self.channel.id),
        }
