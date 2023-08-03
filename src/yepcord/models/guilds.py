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
from time import time
from typing import Optional, Union

import ormar
from ormar import ReferentialAction, QuerySet
from ormar.relations.relation_proxy import RelationProxy

from . import DefaultMeta, User
from .channels import Channel, Invite, PermissionOverwrite
from ..ctx import getCore
from ..enums import ScheduledEventEntityType, ChannelType, GuildPermissions, AuditLogEntryType
from ..errors import InvalidDataErr, Errors
from ..snowflake import Snowflake
from ..utils import b64encode, int_size, NoneType


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
    afk_channel: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    system_channel: Optional[int] = ormar.BigInteger(nullable=True, default=None)
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

    async def ds_json(self, user_id: int, for_gateway: bool=False, with_members: bool=False,
                      with_channels: bool=False) -> dict:
        data = {
            "id": str(self.id),
            "version": int(time() * 1000),  # What is this?
            "stickers": [await sticker.ds_json() for sticker in await getCore().getGuildStickers(self)],
            "stage_instances": [],
            "roles": [role.ds_json() for role in await getCore().getRoles(self)],
            "properties": {
                "afk_timeout": self.afk_timeout,
                "splash": self.splash,
                "owner_id": str(self.owner.id),
                "description": self.description,
                "id": str(self.id),
                "discovery_splash": self.discovery_splash,
                "icon": self.icon,
                "incidents_data": None,  # ???
                "explicit_content_filter": self.explicit_content_filter,
                "system_channel_id": str(self.system_channel) if self.system_channel is not None else None,
                "default_message_notifications": self.default_message_notifications,
                "premium_progress_bar_enabled": bool(self.premium_progress_bar_enabled),
                "public_updates_channel_id": None,  # ???
                "max_members": self.max_members,
                "nsfw": bool(self.nsfw),
                "application_id": None,
                "max_video_channel_users": 0,
                "verification_level": self.verification_level,
                "rules_channel_id": None,
                "afk_channel_id": str(self.afk_channel) if self.afk_channel is not None else None,
                "latest_onboarding_question_id": None,  # ???
                "mfa_level": self.mfa_level,
                "nsfw_level": self.nsfw_level,
                "safety_alerts_channel_id": None,  # ???
                "premium_tier": 3,
                "vanity_url_code": self.vanity_url_code,
                "features": [
                    "ANIMATED_ICON",
                    "BANNER",
                    "INVITE_SPLASH",
                    "VANITY_URL",
                    "PREMIUM_TIER_3_OVERRIDE",
                    "ROLE_ICONS",
                    *self.features
                ],
                "max_stage_video_channel_users": 0,
                "system_channel_flags": self.system_channel_flags,
                "name": self.name,
                "hub_type": None,  # ???
                "preferred_locale": self.preferred_locale,
                "home_header": None,  # ???
                "banner": self.banner,
                "region": self.region,
                "widget_enabled": False,
                "widget_channel_id": None,
            },
            "premium_subscription_count": 30,
            "member_count": await getCore().getGuildMemberCount(self),
            "lazy": True,
            "large": False,
            "guild_scheduled_events": [await event.ds_json() for event in await getCore().getGuildEvents(self)],
            "emojis": [await emoji.ds_json(False) for emoji in await getCore().getEmojis(self.id)],
            "data_mode": "full",
            "application_command_counts": [],
        }

        if not for_gateway:
            props = data["properties"]
            del data["properties"]
            data.update(props)

        if for_gateway or user_id:
            member = await getCore().getGuildMember(self, user_id)
            data["joined_at"] = member.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
            data["threads"] = [thread.ds_json() for thread in await getCore().getGuildMemberThreads(self, user_id)]
        if for_gateway or with_channels:
            data["channels"] = [await channel.ds_json() for channel in await getCore().getGuildChannels(self)]
        if with_members:
            data["members"] = [await member.ds_json() for member in await getCore().getGuildMembers(self)]

        return data


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

    def ds_json(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "permissions": str(self.permissions),
            "position": self.position,
            "color": self.color,
            "hoist": bool(self.hoist),
            "managed": bool(self.managed),
            "mentionable": bool(self.mentionable),
            "icon": self.icon,
            "unicode_emoji": self.unicode_emoji,
            "flags": self.flags
        }


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
    roles: Optional[Union[RelationProxy, QuerySet]] = ormar.ManyToMany(Role)

    @property
    def joined_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    async def ds_json(self) -> dict:
        userdata = await self.user.userdata
        return {
            "avatar": self.avatar,
            "communication_disabled_until": self.communication_disabled_until,
            "flags": self.flags,
            "joined_at": self.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "nick": self.nick,
            "is_pending": False,  # TODO
            "pending": False,  # TODO
            "premium_since": self.user.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "roles": [str(role) for role in await getCore().getMemberRolesIds(self)],
            "user": userdata.ds_json,
            "mute": self.mute,
            "deaf": self.deaf
        }

    @property
    def perm_checker(self) -> PermissionsChecker:
        return PermissionsChecker(self)

    @property
    async def roles_w_default(self) -> list[Role]:
        return await getCore().getMemberRoles(self, True)

    @property
    async def top_role(self) -> Role:
        roles = await self.roles_w_default
        return roles[-1]

    async def checkPermission(self, *check_permissions, channel: Optional[Channel] = None) -> None:
        return await self.perm_checker.check(*check_permissions, channel=channel)

    @property
    async def permissions(self) -> int:
        permissions = 0
        for role in await self.roles_w_default:
            permissions |= role.permissions
        return permissions


class PermissionsChecker:
    def __init__(self, member: GuildMember):
        self.member = member

    async def check(self, *check_permissions, channel: Optional[Channel]=None) -> None:
        def _check(perms: int, perm: int) -> bool:
            return (perms & perm) == perm
        guild = self.member.guild
        if guild.owner == self.member.user:
            return
        permissions = await self.member.permissions
        if _check(permissions, GuildPermissions.ADMINISTRATOR):
            return
        if channel:
            overwrites = await getCore().getOverwritesForMember(channel, self.member)
            for overwrite in overwrites:
                permissions &= ~overwrite.deny
                permissions |= overwrite.allow

        for permission in check_permissions:
            if not _check(permissions, permission):
                raise InvalidDataErr(403, Errors.make(50013))

    async def canKickOrBan(self, target_member: GuildMember) -> bool:
        if self.member == target_member:
            return False
        guild = self.member.guild
        if target_member.user == guild.owner:
            return False
        if self.member.user == guild.owner:
            return True
        self_top_role = await self.member.top_role
        target_top_role = await target_member.top_role
        if self_top_role.position <= target_top_role.position:
            return False
        return True

    async def canChangeRolesPositions(self, roles_changes: dict, current_roles: Optional[list[Role]]=None) -> bool:
        guild = self.member.guild
        if self.member.user == guild.owner:
            return True
        roles_ids = {role.id: role for role in current_roles}
        top_role = await self.member.top_role
        for role_change in roles_changes:
            role_id = int(role_change["id"])
            position = role_change["position"]
            if roles_ids[role_id].position >= top_role.position or position >= top_role.position:
                return False
        return True


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

    async def ds_json(self, with_user: bool=False) -> dict:
        data = {
            "name": self.name,
            "roles": [],
            "id": str(self.id),
            "require_colons": bool(self.require_colons),
            "managed": bool(self.managed),
            "animated": bool(self.animated),
            "available": bool(self.available)
        }
        if with_user and self.user is not None:
            userdata = await self.user.data
            data["user"] = userdata.ds_json
        return data


class GuildBan(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    reason: str = ormar.String(max_length=512)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)

    async def ds_json(self) -> dict:
        userdata = await self.user.data
        data = {
            "user": userdata.ds_json,
            "reason": self.reason
        }
        return data


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

    async def ds_json(self, with_user: bool=True) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "type": self.type,
            "format_type": self.format,
            "guild_id": str(self.guild.id),
            "available": True,
            "asset": ""
        }
        if with_user and self.user is not None:
            userdata = await self.user.data
            data["user"] = userdata.ds_json
        return data


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
    updated_at: Optional[datetime] = ormar.DateTime(nullable=True, default=None)
    is_dirty: bool = ormar.Boolean(default=False)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_size(self.id), 'big'))

    async def ds_json(self) -> dict:
        creator_data = await self.creator.data if self.creator is not None else None
        updated_at = self.updated_at
        if updated_at is None:
            updated_at = self.created_at
        data = {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "usage_count": self.usage_count,
            "creator_id": str(self.creator.id) if self.creator is not None else None,
            "creator": creator_data.ds_json if creator_data is not None else None,
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "source_guild_id": str(self.guild.id),
            "serialized_source_guild": self.serialized_guild,
            "is_dirty": self.is_dirty
        }
        return data

    @staticmethod
    async def serialize_guild(guild: Guild) -> dict:
        replaced_ids: dict[Union[int, NoneType], Union[int, NoneType]] = {None: None}
        last_replaced_id = 0
        serialized_roles = []
        serialized_channels = []

        # Serialize roles
        roles = await getCore().getRoles(guild)
        roles.sort(key=lambda r: r.id)
        for role in roles:
            replaced_ids[role.id] = last_replaced_id
            role.id = last_replaced_id
            last_replaced_id += 1
            serialized_roles.append({
                "id": role.id,
                "name": role.name,
                "color": role.color,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": str(role.permissions),
                "icon": None,
                "unicode_emoji": role.unicode_emoji
            })

        # Serialize channels
        channels = await getCore().getGuildChannels(guild)
        channels.sort(key=lambda ch: (int(ch.type == ChannelType.GUILD_CATEGORY), ch.id), reverse=True)
        for channel in channels:
            serialized_permission_overwrites = []
            for overwrite in await getCore().getPermissionOverwrites(channel):
                if overwrite.type == 0:  # Overwrite for role
                    role_id = replaced_ids[overwrite.target_id]
                    if role_id is None:
                        continue
                    overwrite = overwrite.ds_json()
                    overwrite["id"] = role_id
                    serialized_permission_overwrites.append(overwrite)
            replaced_ids[channel.id] = last_replaced_id
            channel.id = last_replaced_id
            last_replaced_id += 1

            serialized_channels.append({
                "id": channel.id,
                "type": channel.type,
                "name": channel.name,
                "position": channel.position,
                "topic": channel.topic,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "nsfw": channel.nsfw,
                "rate_limit_per_user": channel.rate_limit,
                "parent_id": replaced_ids.get(channel.parent.id if channel.parent is not None else None),
                "default_auto_archive_duration": channel.default_auto_archive,
                "permission_overwrites": serialized_permission_overwrites,
                "available_tags": None,  # ???
                "template": "",  # ???
                "default_reaction_emoji": None,  # ???
                "default_thread_rate_limit_per_user": None,  # ???
                "default_sort_order": None,  # ???
                "default_forum_layout": None  # ???
            })

        # Serialize guild
        data = {
            "name": guild.name,
            "description": guild.description,
            "region": guild.region,
            "verification_level": guild.verification_level,
            "default_message_notifications": guild.default_message_notifications,
            "explicit_content_filter": guild.explicit_content_filter,
            "preferred_locale": guild.preferred_locale,
            "afk_timeout": guild.afk_timeout,
            "roles": serialized_roles,
            "channels": serialized_channels,
            "afk_channel_id": replaced_ids.get(guild.afk_channel),
            "system_channel_id": replaced_ids.get(guild.system_channel),
            "system_channel_flags": guild.system_channel_flags
        }

        return data


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
    subscribers: Optional[Union[RelationProxy, QuerySet]] = ormar.ManyToMany(GuildMember)

    async def ds_json(self, with_user: bool=False, with_user_count: bool=False) -> dict:
        channel_id = str(self.channel_id) if self.channel_id is not None else None
        entity_id = str(self.entity_id) if self.entity_id is not None else None
        start_time = self.start.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        end_time = None
        if self.end:
            end_time = self.end.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        data = {
            "id": str(self.id),
            "guild_id": str(self.guild_id),
            "channel_id": str(channel_id),
            "creator_id": str(self.creator_id),
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


class AuditLogEntryQuerySet(QuerySet):
    async def channel_create(self, user: User, channel: Channel) -> AuditLogEntry:
        changes = [
            {"new_value": channel.name, "key": "name"},
            {"new_value": channel.type, "key": "type"},
            {"new_value": [], "key": "permission_overwrites"},
            {"new_value": channel.nsfw, "key": "nsfw"},
            {"new_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"new_value": channel.flags, "key": "flags"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                 action_type=AuditLogEntryType.CHANNEL_CREATE, changes=changes)

    async def channel_update(self, user: User, channel: Channel, changes: dict) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                 action_type=AuditLogEntryType.CHANNEL_UPDATE, changes=changes)

    async def channel_delete(self, user: User, channel: Channel) -> AuditLogEntry:
        changes = [
            {"old_value": channel.name, "key": "name"},
            {"old_value": channel.type, "key": "type"},
            {"old_value": [], "key": "permission_overwrites"},
            {"old_value": channel.nsfw, "key": "nsfw"},
            {"old_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"old_value": channel.flags, "key": "flags"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                 action_type=AuditLogEntryType.CHANNEL_DELETE, changes=changes)

    async def overwrite_create(self, user: User, overwrite: PermissionOverwrite) -> AuditLogEntry:
        changes = [
            {"new_value": str(overwrite.target_id), "key": "id"},
            {"new_value": str(overwrite.type), "key": "type"},
            {"new_value": str(overwrite.allow), "key": "allow"},
            {"new_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0 and (role := await Role.objects.get_or_none(id=overwrite.target_id)) is not None:
            options["role_name"] = role.name
        return await self.create(id=Snowflake.makeId(), guild=overwrite.channel.guild, user=user, changes=changes,
                                 target_id=overwrite.id, action_type=AuditLogEntryType.CHANNEL_OVERWRITE_CREATE,
                                 options=options)

    async def overwrite_update(self, user: User, old: PermissionOverwrite, new: PermissionOverwrite) -> AuditLogEntry:
        changes = []
        if old.allow != new.allow:
            changes.append({"new_value": str(new.allow), "old_value": str(old.allow), "key": "allow"})
        if old.deny != new.deny:
            changes.append({"new_value": str(new.deny), "old_value": str(old.deny), "key": "deny"})
        options = {
            "type": str(new.type),
            "id": str(new.target_id)
        }
        if new.type == 0 and (role := await Role.objects.get_or_none(id=new.target_id)) is not None:
            options["role_name"] = role.name
        return await self.create(id=Snowflake.makeId(), guild=old.channel.guild, changes=changes, options=options,
                                 target_id=old.id, action_type=AuditLogEntryType.CHANNEL_OVERWRITE_UPDATE, user=user)

    async def overwrite_delete(self, user: User, overwrite: PermissionOverwrite) -> AuditLogEntry:
        changes = [
            {"old_value": str(overwrite.target_id), "key": "id"},
            {"old_value": str(overwrite.type), "key": "type"},
            {"old_value": str(overwrite.allow), "key": "allow"},
            {"old_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0 and (role := await Role.objects.get_or_none(id=overwrite.target_id)) is not None:
            options["role_name"] = role.name
        return await self.create(id=Snowflake.makeId(), guild=overwrite.channel.guild, user=user, changes=changes,
                                 target_id=overwrite.id, action_type=AuditLogEntryType.CHANNEL_OVERWRITE_DELETE,
                                 options=options)

    async def invite_create(self, user: User, invite: Invite) -> AuditLogEntry:
        changes = [
            {"new_value": invite.code, "key": "code"},
            {"new_value": invite.channel.id, "key": "channel_id"},
            {"new_value": invite.inviter.id, "key": "inviter_id"},
            {"new_value": invite.uses, "key": "uses"},
            {"new_value": invite.max_uses, "key": "max_uses"},
            {"new_value": invite.max_age, "key": "max_age"},
            {"new_value": False, "key": "temporary"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=invite.channel.guild, user=user, target_id=invite.id,
                                 action_type=AuditLogEntryType.INVITE_CREATE, changes=changes)

    async def invite_delete(self, user: User, invite: Invite) -> AuditLogEntry:
        changes = [
            {"old_value": invite.code, "key": "code"},
            {"old_value": invite.channel.id, "key": "channel_id"},
            {"old_value": invite.inviter.id, "key": "inviter_id"},
            {"old_value": invite.uses, "key": "uses"},
            {"old_value": invite.max_uses, "key": "max_uses"},
            {"old_value": invite.max_age, "key": "max_age"},
            {"old_value": False, "key": "temporary"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=invite.channel.guild, user=user, target_id=invite.id,
                                 action_type=AuditLogEntryType.INVITE_DELETE, changes=changes)

    async def guild_update(self, user: User, guild: Guild, changes: dict) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=guild.id,
                                 action_type=AuditLogEntryType.GUILD_UPDATE, changes=changes)

    async def emoji_create(self, user: User, emoji: Emoji) -> AuditLogEntry:
        changes = [{"new_value": emoji.name, "key": "name"}]
        return await self.create(id=Snowflake.makeId(), guild=emoji.guild, user=user, target_id=emoji.id,
                                 action_type=AuditLogEntryType.EMOJI_CREATE, changes=changes)

    async def emoji_delete(self, user: User, emoji: Emoji) -> AuditLogEntry:
        changes = [{"old_value": emoji.name, "key": "name"}]
        return await self.create(id=Snowflake.makeId(), guild=emoji.guild, user=user, target_id=emoji.id,
                                 action_type=AuditLogEntryType.EMOJI_DELETE, changes=changes)

    async def member_kick(self, user: User, member: GuildMember) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                 action_type=AuditLogEntryType.MEMBER_KICK)

    async def member_ban(self, user: User, member: GuildMember, reason: str = None) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                 action_type=AuditLogEntryType.MEMBER_BAN_ADD, reason=reason)

    async def member_unban(self, user: User, guild: Guild, target_user: User) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=target_user.id,
                                 action_type=AuditLogEntryType.MEMBER_BAN_REMOVE)

    async def member_update(self, user: User, member: GuildMember, changes: dict) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                 action_type=AuditLogEntryType.MEMBER_UPDATE, changes=changes)

    async def role_create(self, user: User, role: Role) -> AuditLogEntry:
        changes = [
            {"new_value": role.name, "key": "name"},
            {"new_value": role.permissions, "key": "permissions"},
            {"new_value": role.color, "key": "color"},
            {"new_value": role.hoist, "key": "hoist"},
            {"new_value": role.mentionable, "key": "mentionable"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                 action_type=AuditLogEntryType.ROLE_CREATE, changes=changes)

    async def role_update(self, user: User, role: Role, changes: dict) -> AuditLogEntry:
        return await self.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                 action_type=AuditLogEntryType.ROLE_UPDATE, changes=changes)

    async def role_delete(self, user: User, role: Role) -> AuditLogEntry:
        changes = [
            {"old_value": role.name, "key": "name"},
            {"old_value": role.permissions, "key": "permissions"},
            {"old_value": role.color, "key": "color"},
            {"old_value": role.hoist, "key": "hoist"},
            {"old_value": role.mentionable, "key": "mentionable"}
        ]
        return await self.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                 action_type=AuditLogEntryType.ROLE_DELETE, changes=changes)


class AuditLogEntry(ormar.Model):
    class Meta(DefaultMeta):
        queryset_class = AuditLogEntryQuerySet

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    guild: Guild = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE)
    user: Optional[User] = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL)
    target_id: int = ormar.BigInteger(nullable=True, default=None)
    action_type: int = ormar.Integer()
    reason: Optional[str] = ormar.String(max_length=512, nullable=True, default=None)
    changes: list = ormar.JSON(default=[])
    options: dict = ormar.JSON(default={})

    def ds_json(self) -> dict:
        data = {
            "user_id": str(self.user.id),
            "target_id": str(self.target_id),
            "id": str(self.id),
            "action_type": self.action_type,
            "guild_id": str(self.guild.id)
        }
        if self.changes: data["changes"] = self.changes
        if self.options: data["options"] = self.options
        if self.reason: data["reason"] = self.reason
        return data
