# All 'Guild' classes (Guild, etc.)
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from schema import Or, And, Use

from .user import UserId
from ..ctx import getCore, Ctx
from ..enums import ChannelType, AuditLogEntryType
from ..model import model, Model, field
from ..snowflake import Snowflake
from ..utils import NoneType
from ..utils import b64encode, int_length


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
    system_channel_id: Optional[int] = None
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
            "stickers": [], # TODO
            "banner": self.banner,
            "owner_id": str(self.owner_id),
            "application_id": None,  # TODO
            "region": self.region,
            "afk_channel_id": self.afk_channel_id,
            "afk_timeout": self.afk_timeout,
            "system_channel_id": str(self.system_channel_id),
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
            "threads": [],  # TODO
            "guild_scheduled_events": [],  # TODO
            "stage_instances": [],  # TODO
            "application_command_counts": {},  # TODO
            "large": False,  # TODO
            "lazy": True,  # TODO
            "member_count": await getCore().getGuildMemberCount(self),
        }
        if uid := Ctx.get("user_id"):
            joined_at = (await getCore().getGuildMember(self, uid)).joined_at
            data["joined_at"] = Snowflake.toDatetime(joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
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
                "preferred_locale": "en-US", "premium_progress_bar_enabled": False, "nsfw": False, "nsfw_level": 0} # TODO: remove or replace with more convenient solution

    def fill_defaults(self):  # TODO: remove or replace with more convenient solution
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

    DEFAULTS = {"roles": [], "require_colons": True, "managed": False, "animated": False, "available": True} # TODO: remove or replace with more convenient solution

    def fill_defaults(self):  # TODO: remove or replace with more convenient solution
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