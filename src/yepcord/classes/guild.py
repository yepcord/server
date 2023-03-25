# All 'Guild' classes (Guild, etc.)
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Dict, Union

from schema import Or, And, Use

from .user import UserId, User, GuildMember
from ..ctx import getCore, Ctx
from ..enums import ChannelType, AuditLogEntryType, ScheduledEventEntityType
from ..model import model, Model, field
from ..snowflake import Snowflake
from ..utils import NoneType
from ..utils import b64encode, int_length
if TYPE_CHECKING:
    from .channel import Channel

class _Guild:
    id: int

    def __eq__(self, other):
        return isinstance(other, _Guild) and self.id == other.id

class GuildId(_Guild):
    def __init__(self, id):
        self.id = id

@model
@dataclass
class Guild(_Guild, Model):
    id: int = field(id_field=True)
    owner_id: int = field()
    name: str = field()
    icon: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    description: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    splash: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    discovery_splash: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    features: Optional[list] = field(db_name="j_features", default=None)
    banner: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    region: Optional[str] = None
    afk_channel_id: Optional[int] = field(default=None, nullable=True, validation=Or(Use(int), NoneType))
    afk_timeout: Optional[int] = None
    system_channel_id: Optional[int] = field(default=None, nullable=True, validation=Or(Use(int), NoneType))
    verification_level: Optional[int] = None
    default_message_notifications: Optional[int] = None
    mfa_level: Optional[int] = None
    explicit_content_filter: Optional[int] = None
    max_members: Optional[int] = None
    vanity_url_code: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    system_channel_flags: Optional[int] = None
    preferred_locale: Optional[str] = None
    premium_progress_bar_enabled: Optional[bool] = None
    nsfw: Optional[bool] = None
    nsfw_level: Optional[int] = None

    @property
    async def json(self) -> dict:
        afk_channel_id = str(self.afk_channel_id) if self.afk_channel_id is not None else None
        system_channel_id = str(self.system_channel_id) if self.system_channel_id is not None else None
        data = {
            "id": str(self.id),
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "splash": self.splash,
            "discovery_splash": self.discovery_splash,
            "features": [
                "ANIMATED_ICON",
                "BANNER",
                "INVITE_SPLASH",
                "VANITY_URL",
                "PREMIUM_TIER_3_OVERRIDE",
                "ROLE_ICONS",
                *self.features
            ],
            "emojis": [
                await emoji.json for emoji in await getCore().getEmojis(self.id)  # Get json for every emoji in guild
            ],
            "stickers": [
                await sticker.json for sticker in await getCore().getGuildStickers(self)  # Get json for every sticker in guild
            ],
            "banner": self.banner,
            "owner_id": str(self.owner_id),
            "application_id": None,  # TODO
            "region": self.region,
            "afk_channel_id": afk_channel_id,
            "afk_timeout": self.afk_timeout,
            "system_channel_id": system_channel_id,
            "widget_enabled": False,  # TODO
            "widget_channel_id": None,  # TODO
            "verification_level": self.verification_level,
            "roles": [
                await role.json for role in await getCore().getRoles(self)  # Get json for every role in guild
            ],
            "default_message_notifications": self.default_message_notifications,
            "mfa_level": self.mfa_level,
            "explicit_content_filter": self.explicit_content_filter,
            # "max_presences": None, # TODO
            "max_members": self.max_members,
            "max_stage_video_channel_users": 0,  # TODO
            "max_video_channel_users": 0,  # TODO
            "vanity_url_code": self.vanity_url_code,
            "premium_tier": 3,  # TODO
            "premium_subscription_count": 30,  # TODO
            "system_channel_flags": self.system_channel_flags,
            "preferred_locale": self.preferred_locale,
            "rules_channel_id": None,  # TODO
            "public_updates_channel_id": None,  # TODO
            "hub_type": None,  # TODO
            "premium_progress_bar_enabled": bool(self.premium_progress_bar_enabled),
            "nsfw": bool(self.nsfw),
            "nsfw_level": self.nsfw_level,
            "threads": [],
            "guild_scheduled_events": [await event.json for event in await getCore().getScheduledEvents(self)],  # TODO
            "stage_instances": [],  # TODO
            "application_command_counts": {},  # TODO
            "large": False,  # TODO
            "lazy": True,
            "member_count": await getCore().getGuildMemberCount(self),
        }
        if uid := Ctx.get("user_id"):
            joined_at = (await getCore().getGuildMember(self, uid)).joined_at
            data["joined_at"] = Snowflake.toDatetime(joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
            data["threads"] = [await thread.json for thread in await getCore().getGuildMemberThreads(self, uid)]
        if Ctx.get("with_members"):
            data["members"] = [await member.json for member in await getCore().getGuildMembers(self)]
        if Ctx.get("with_channels"):
            data["channels"] = [await channel.json for channel in await getCore().getGuildChannels(self)]
        return data

    DEFAULTS = {"icon": None, "description": None, "splash": None, "discovery_splash": None, "features": [
        "ANIMATED_ICON", "BANNER", "INVITE_SPLASH", "VANITY_URL", "PREMIUM_TIER_3_OVERRIDE", "ROLE_ICONS"],
                "banner": None, "region": "deprecated", "afk_channel_id": None,
                "afk_timeout": 300, "verification_level": 0, "default_message_notifications": 0, "mfa_level": 0,
                "explicit_content_filter": 0, "max_members": 100, "vanity_url_code": None, "system_channel_flags": 0,
                "preferred_locale": "en-US", "premium_progress_bar_enabled": False, "nsfw": False, "nsfw_level": 0}

    def fill_defaults(self):
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self


@model
@dataclass
class Role(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    name: str = field()
    permissions: Optional[int] = field(default=0, validation=Or(Use(int), NoneType))
    position: Optional[int] = None
    color: Optional[int] = None
    hoist: Optional[bool] = None
    managed: Optional[bool] = None
    mentionable: Optional[bool] = None
    icon: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    unicode_emoji: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    flags: Optional[int] = None

    @property
    async def json(self) -> dict:
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


@model
@dataclass
class Emoji(Model):
    id: int = field(id_field=True)
    name: str = field()
    user_id: int = field()
    guild_id: int = field()
    roles: Optional[list] = field(default=None, db_name="j_roles")
    require_colons: Optional[bool] = False
    managed: Optional[bool] = False
    animated: Optional[bool] = False
    available: Optional[bool] = True

    DEFAULTS = {"roles": [], "require_colons": True, "managed": False, "animated": False, "available": True}

    def fill_defaults(self):
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    @property
    async def json(self) -> dict:
        data = {
            "name": self.name,
            "roles": self.roles,
            "id": str(self.id),
            "require_colons": bool(self.require_colons),
            "managed": bool(self.managed),
            "animated": bool(self.animated),
            "available": bool(self.available)
        }
        if Ctx.get("with_user"):
            user = await getCore().getUserData(UserId(self.user_id))
            data["user"] = {
                "id": str(self.user_id),
                "username": user.username,
                "avatar": user.avatar,
                "avatar_decoration": user.avatar_decoration,
                "discriminator": user.s_discriminator,
                "public_flags": user.public_flags
            }
        return data


@model
@dataclass
class Invite(Model):
    id: int = field(id_field=True)
    channel_id: int = field()
    inviter: int = field()
    created_at: int = field()
    max_age: int = field()
    max_uses: Optional[int] = 0
    uses: Optional[int] = 0
    vanity_code: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    guild_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    type: Optional[int] = field(default=1, validation=And(lambda i: i in (0, 1)))

    @property
    async def json(self) -> dict:
        userdata = await getCore().getUserData(UserId(self.inviter))
        expires_at = None
        if self.max_age > 0:
            expires_timestamp = int(Snowflake.toTimestamp(self.id) / 1000) + self.max_age
            expires_at = datetime.utcfromtimestamp(expires_timestamp).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        channel = await getCore().getChannel(self.channel_id)
        data = {
            "code": self.code,
            "inviter": await userdata.json,
            "created_at": Snowflake.toDatetime(self.id).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "expires_at": expires_at,
            "type": self.type,
            "channel": {
                "id": str(channel.id),
                "type": channel.type
            },
            "max_age": self.max_age,
        }

        if Ctx.get("with_counts"):
            related_users = await getCore().getRelatedUsersToChannel(self.channel_id)
            data["approximate_member_count"] = len(related_users)
            if channel.type == ChannelType.GROUP_DM:
                data["channel"]["recipients"] = [
                    {"username": (await getCore().getUserData(UserId(i))).username}
                    for i in related_users
                ]

        if channel.type == ChannelType.GROUP_DM:
            data["channel"].update({"name": channel.name, "icon": channel.icon})
        elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
            data["channel"]["name"] = channel.name

        if self.guild_id:
            guild = await getCore().getGuild(self.guild_id)
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

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_length(self.id), 'big'))


@model
@dataclass
class GuildBan(Model):
    user_id: int
    guild_id: int
    reason: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))

    @property
    async def json(self) -> dict:
        userdata = await getCore().getUserData(UserId(self.user_id))
        data = {
            "user": await userdata.json,
            "reason": self.reason
        }
        return data


@model
@dataclass
class AuditLogEntry(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    user_id: int = field()
    target_id: Optional[int] = None
    action_type: int = 0
    reason: Optional[str] = None
    changes: list = field(db_name="j_changes", default_factory=list)
    options: dict = field(db_name="j_options", default_factory=dict)

    @property
    async def json(self) -> dict:
        data = {
            "user_id": str(self.user_id),
            "target_id": str(self.target_id),
            "id": str(self.id),
            "action_type": self.action_type,
            "guild_id": str(self.guild_id)
        }
        if self.changes: data["changes"] = self.changes
        if self.options: data["options"] = self.options
        if self.reason: data["reason"] = self.reason
        return data

    @property
    def target_user_id(self) -> Optional[int]:
        if self.action_type in (AuditLogEntryType.MEMBER_UPDATE, AuditLogEntryType.MEMBER_BAN_ADD,
                                AuditLogEntryType.MEMBER_BAN_REMOVE, AuditLogEntryType.MEMBER_KICK,
                                AuditLogEntryType.MEMBER_ROLE_UPDATE, AuditLogEntryType.MEMBER_DISCONNECT,
                                AuditLogEntryType.MEMBER_MOVE):
            return self.target_id

    @staticmethod
    def get_changes(before: Model, after: Model) -> List[dict]:
        changes = []
        for k, v in before.getDiff(after).items():
            changes.append({"key": k, "old_value": before.get(k), "new_value": after.get(k)})
        return changes

    @classmethod
    def guild_update(cls, guild: Guild, new_guild: Guild, user: User) -> AuditLogEntry:
        return AuditLogEntry(Snowflake.makeId(), guild.id, user.id, guild.id, AuditLogEntryType.GUILD_UPDATE,
                              changes=cls.get_changes(guild, new_guild))

    @classmethod
    def emoji_create(cls, emoji: Emoji, user: User) -> AuditLogEntry:
        changes = [{"new_value": emoji.name, "key": "name"}]
        return AuditLogEntry(Snowflake.makeId(), emoji.guild_id, user.id, emoji.id, AuditLogEntryType.EMOJI_CREATE,
                             changes=changes)

    @classmethod
    def emoji_delete(cls, emoji: Emoji, user: User) -> AuditLogEntry:
        changes = [{"old_value": emoji.name, "key": "name"}]
        return AuditLogEntry(Snowflake.makeId(), emoji.guild_id, user.id, emoji.id, AuditLogEntryType.EMOJI_DELETE,
                          changes=changes)

    @classmethod
    def channel_create(cls, channel: Channel, user: User) -> AuditLogEntry:
        changes = [
            {"new_value": channel.name, "key": "name"},
            {"new_value": channel.type, "key": "type"},
            {"new_value": [], "key": "permission_overwrites"},
            {"new_value": channel.nsfw, "key": "nsfw"},
            {"new_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"new_value": channel.flags, "key": "flags"}
        ]
        return AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id,
                             AuditLogEntryType.CHANNEL_CREATE,
                             changes=changes)

    @classmethod
    def channel_update(cls, channel: Channel, new_channel: Channel, user: User) -> AuditLogEntry:
        return AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id,
                             AuditLogEntryType.CHANNEL_CREATE,
                             changes=cls.get_changes(channel, new_channel))

    @classmethod
    def channel_delete(cls, channel: Channel, user: User) -> AuditLogEntry:
        changes = [
            {"old_value": channel.name, "key": "name"},
            {"old_value": channel.type, "key": "type"},
            {"old_value": [], "key": "permission_overwrites"},
            {"old_value": channel.nsfw, "key": "nsfw"},
            {"old_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"old_value": channel.flags, "key": "flags"}
        ]
        return AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id,
                             AuditLogEntryType.CHANNEL_DELETE,
                             changes=changes)

    @classmethod
    def invite_create(cls, invite: Invite, user: User) -> AuditLogEntry:
        changes = [
            {"new_value": invite.code, "key": "code"},
            {"new_value": invite.channel_id, "key": "channel_id"},
            {"new_value": invite.inviter, "key": "inviter_id"},
            {"new_value": invite.uses, "key": "uses"},
            {"new_value": invite.max_uses, "key": "max_uses"},
            {"new_value": invite.max_age, "key": "max_age"},
            {"new_value": False, "key": "temporary"}
        ]
        return AuditLogEntry(Snowflake.makeId(), invite.guild_id, user.id, invite.id, AuditLogEntryType.INVITE_CREATE,
                              changes=changes)

    @classmethod
    def invite_delete(cls, invite: Invite, user: User) -> AuditLogEntry:
        changes = [
            {"old_value": invite.code, "key": "code"},
            {"old_value": invite.channel_id, "key": "channel_id"},
            {"old_value": invite.inviter_id, "key": "inviter_id"},
            {"old_value": invite.uses, "key": "uses"},
            {"old_value": invite.max_uses, "key": "max_uses"},
            {"old_value": invite.max_age, "key": "max_age"},
            {"old_value": invite.temporary, "key": "temporary"}
        ]
        return AuditLogEntry(Snowflake.makeId(), invite.guild_id, user.id, invite.id, AuditLogEntryType.INVITE_DELETE,
                              changes=changes)

    @classmethod
    def role_create(cls, role: Role, user: User) -> AuditLogEntry:
        changes = [
            {"new_value": role.name, "key": "name"},
            {"new_value": role.permissions, "key": "permissions"},
            {"new_value": role.color, "key": "color"},
            {"new_value": role.hoist, "key": "hoist"},
            {"new_value": role.mentionable, "key": "mentionable"}
        ]
        return AuditLogEntry(Snowflake.makeId(), role.guild_id, user.id, role.id, AuditLogEntryType.ROLE_CREATE,
                              changes=changes)

    @classmethod
    def role_update(cls, role: Role, new_role: Role, user: User) -> AuditLogEntry:
        return  AuditLogEntry(Snowflake.makeId(), role.guild_id, user.id, role.id, AuditLogEntryType.ROLE_UPDATE,
                          changes=cls.get_changes(role, new_role))

    @classmethod
    def role_delete(cls, role: Role, user: User) -> AuditLogEntry:
        changes = [
            {"old_value": role.name, "key": "name"},
            {"old_value": role.permissions, "key": "permissions"},
            {"old_value": role.color, "key": "color"},
            {"old_value": role.hoist, "key": "hoist"},
            {"old_value": role.mentionable, "key": "mentionable"}
        ]
        return AuditLogEntry(Snowflake.makeId(), role.guild_id, user.id, role.id, AuditLogEntryType.ROLE_DELETE,
                              changes=changes)

    @classmethod
    def member_update(cls, member: GuildMember, new_member: GuildMember, user: User) -> AuditLogEntry:
        return  AuditLogEntry(Snowflake.makeId(), member.guild_id, user.id, member.user_id, AuditLogEntryType.MEMBER_UPDATE,
                          changes=cls.get_changes(member, new_member))


@model
@dataclass
class GuildTemplate(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    name: str = field()
    description: Optional[str] = field()
    usage_count: int = field()
    creator_id: int = field()
    created_at: int = field()
    serialized_guild: dict = field(db_name="j_serialized_guild")
    updated_at: Optional[int] = None
    is_dirty: Optional[bool] = None

    @property
    async def json(self) -> dict:
        creator_data = await getCore().getUserData(UserId(self.creator_id))
        updated_at = self.updated_at
        if updated_at is None:
            updated_at = self.created_at
        data = {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "usage_count": self.usage_count,
            "creator_id": str(self.creator_id),
            "creator": await creator_data.json,
            "created_at": Snowflake.toDatetime(self.id).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "updated_at": datetime.utcfromtimestamp(updated_at).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "source_guild_id": str(self.guild_id),
            "serialized_source_guild": self.serialized_guild,
            "is_dirty": self.is_dirty
        }
        return data

    @staticmethod
    async def serialize_guild(guild: Guild) -> dict:
        replaced_ids: Dict[Union[int, NoneType], Union[int, NoneType]] = {None: None}
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
                if overwrite.type == 0: # Overwrite for role
                    role_id = replaced_ids[overwrite.target_id]
                    if role_id is None:
                        continue
                    overwrite = await overwrite.json
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
                "topic": channel.get("topic", None),
                "bitrate": channel.get("bitrate", 64000),
                "user_limit": channel.get("user_limit", 0),
                "nsfw": channel.get("nsfw", 0),
                "rate_limit_per_user": channel.get("rate_limit", 0),
                "parent_id": replaced_ids.get(channel.parent_id),
                "default_auto_archive_duration": channel.get("default_auto_archive", None),
                "permission_overwrites": serialized_permission_overwrites,
                "available_tags": None, # ???
                "template": "", # ???
                "default_reaction_emoji": None, # ???
                "default_thread_rate_limit_per_user": None, # ???
                "default_sort_order": None, # ???
                "default_forum_layout": None # ???
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
            "afk_channel_id": replaced_ids.get(guild.afk_channel_id),
            "system_channel_id": replaced_ids.get(guild.system_channel_id),
            "system_channel_flags": guild.system_channel_flags
        }

        return data

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_length(self.id), 'big'))


@model
@dataclass
class Webhook(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    channel_id: int = field()
    user_id: int = field()
    type: int = field()
    name: str = field()
    token: str = field()
    application_id: Optional[int] = field(default=None, nullable=True, validation=Or(Use(int), NoneType))
    avatar: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))

    @property
    async def json(self) -> dict:
        userdata = await getCore().getUserData(UserId(self.user_id))
        data = {
            "type": self.type,
            "id": str(self.id),
            "name": self.name,
            "avatar": self.avatar,
            "channel_id": str(self.channel_id),
            "guild_id": str(self.guild_id),
            "application_id": str(self.application_id) if self.application_id is not None else self.application_id,
            "token": self.token,
            "user": await userdata.json
        }

        return data


@model
@dataclass
class Sticker(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    user_id: int = field()
    name: str = field()
    tags: str = field()
    type: int = field()
    format: int = field()
    description: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))

    @property
    async def json(self) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "type": self.type,
            "format_type": self.format,
            "guild_id": str(self.guild_id),
            "available": True,
            "asset": ""
        }
        if Ctx.get("with_user", True):
            userdata = await getCore().getUserData(UserId(self.user_id))
            data["user"] = await userdata.json
        return data


@model
@dataclass
class ScheduledEvent(Model):
    id: int = field(id_field=True)
    guild_id: int = field()
    creator_id: int = field()
    name: str = field()
    start: int = field()
    privacy_level: int = field()
    status: int = field()
    entity_type: int = field()
    end: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    description: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    channel_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    entity_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    entity_metadata: Optional[dict] = field(default_factory=dict)
    image: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))

    @property
    async def json(self) -> dict:
        channel_id = str(self.channel_id) if self.channel_id is not None else None
        entity_id = str(self.entity_id) if self.entity_id is not None else None
        start_time = datetime.utcfromtimestamp(self.start).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        end_time = None
        if self.end:
            end_time = datetime.utcfromtimestamp(self.end).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
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
        if Ctx.get("with_user"):
            creator = await getCore().getUserData(UserId(self.creator_id))
            data["creator"] = await creator.json
        if Ctx.get("with_user_count"):
            data["user_count"] = await getCore().getScheduledEventUserCount(self)
        return data