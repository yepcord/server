# All 'Guild' classes (Guild, etc.)
from dataclasses import dataclass
from datetime import datetime
from ..utils import NoneType
from typing import Optional

from schema import Or, And

from server.classes.user import UserId
from server.ctx import getCore, Ctx
from server.enums import ChannelType
from server.model import model, Model, field
from server.utils import snowflake_timestamp, b64encode, byte_length, sf_ts


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
    owner_id: int
    name: str
    icon: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    description: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    splash: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    discovery_splash: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    features: Optional[list] = field(db_name="j_features", default=None)
    emojis: Optional[list] = field(db_name="j_emojis", default=None) # TODO: Deprecated, use `emoji.guild_id`
    stickers: Optional[list] = field(db_name="j_stickers", default=None)
    banner: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    region: Optional[str] = None
    afk_channel_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    afk_timeout: Optional[int] = None
    system_channel_id: Optional[int] = None
    verification_level: Optional[int] = None
    roles: Optional[list] = field(db_name="j_roles", default=None)
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

    DEFAULTS = {"icon": None, "description": None, "splash": None, "discovery_splash": None, "features": [],
                "emojis": [], "stickers": [], "banner": None, "region": "deprecated", "afk_channel_id": None,
                "afk_timeout": 300, "verification_level": 0, "default_message_notifications": 0, "mfa_level": 0,
                "explicit_content_filter": 0, "max_members": 100, "vanity_url_code": None, "system_channel_flags": 0,
                "preferred_locale": "en-US", "premium_progress_bar_enabled": False, "nsfw": False, "nsfw_level": 0} # TODO: remove or replace with mode convenient solution

    def fill_defaults(self):  # TODO: remove or replace with mode convenient solution
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    @property
    async def json(self) -> dict:
        roles = [await role.json for role in [await getCore().getRole(role) for role in self.roles]]
        members = []
        channels = []
        if Ctx.get("with_members"):
            members = [await member.json for member in await getCore().getGuildMembers(self)]
        if Ctx.get("with_channels"):
            channels = [await channel.json for channel in await getCore().getGuildChannels(self)]
        emojis = []
        for emoji in await getCore().getEmojis(self.id):
            emojis.append(await emoji.json)
        return {
            "id": str(self.id),
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "splash": self.splash,
            "discovery_splash": self.discovery_splash,
            "features": self.features,
            **({} if not Ctx.get("user_id") else {
                "joined_at": datetime.utcfromtimestamp(int(snowflake_timestamp(
                    (await getCore().getGuildMember(self, Ctx.get("user_id"))).joined_at
                ) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
            }),
            "emojis": emojis,
            "stickers": self.stickers,
            "banner": self.banner,
            "owner_id": str(self.owner_id),
            "application_id": None, # TODO
            "region": self.region,
            "afk_channel_id": self.afk_channel_id,
            "afk_timeout": self.afk_timeout,
            "system_channel_id": str(self.system_channel_id),
            "widget_enabled": False, # TODO
            "widget_channel_id": None, # TODO
            "verification_level": self.verification_level,
            "roles": roles,
            "default_message_notifications": self.default_message_notifications,
            "mfa_level": self.mfa_level,
            "explicit_content_filter": self.explicit_content_filter,
            #"max_presences": None, # TODO
            "max_members": self.max_members,
            "max_stage_video_channel_users": 0, # TODO
            "max_video_channel_users": 0, # TODO
            "vanity_url_code": self.vanity_url_code,
            "premium_tier": 3, # TODO
            "premium_subscription_count": 30, # TODO
            "system_channel_flags": self.system_channel_flags,
            "preferred_locale": self.preferred_locale,
            "rules_channel_id": None, # TODO
            "public_updates_channel_id": None, # TODO
            "hub_type": None, # TODO
            "premium_progress_bar_enabled": bool(self.premium_progress_bar_enabled),
            "nsfw": bool(self.nsfw),
            "nsfw_level": self.nsfw_level,
            "threads": [], # TODO
            "guild_scheduled_events": [], # TODO
            "stage_instances": [], # TODO
            "application_command_counts": {}, # TODO
            "large": False, # TODO
            "lazy": True, # TODO
            "member_count": await getCore().getGuildMemberCount(self),
            **({} if not Ctx.get("with_members") else {"members": members}),
            **({} if not Ctx.get("with_channels") else {"channels": channels}),
        }

@model
@dataclass
class Role(Model):
    id: int = field(id_field=True)
    guild_id: int
    name: str
    permissions: Optional[int] = None
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
    name: str
    user_id: int
    guild_id: int
    roles: Optional[list] = field(db_name="j_roles")
    require_colons: Optional[bool] = False
    managed: Optional[bool] = False
    animated: Optional[bool] = False
    available: Optional[bool] = False

    DEFAULTS = {"roles": [], "require_colons": True, "managed": False, "animated": False, "available": True} # TODO: remove or replace with mode convenient solution

    def fill_defaults(self):  # TODO: remove or replace with mode convenient solution
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    @property
    async def json(self) -> dict:
        user = {}
        if Ctx.get("with_user"):
            user = await getCore().getUserData(UserId(self.user_id))
            user = {
                "user": {
                    "id": str(self.user_id),
                    "username": user.username,
                    "avatar": user.avatar,
                    "avatar_decoration": user.avatar_decoration,
                    "discriminator": user.s_discriminator,
                    "public_flags": user.public_flags
                }
            }
        return {
            "name": self.name,
            "roles": self.roles,
            "id": str(self.id),
            "require_colons": bool(self.require_colons),
            "managed": bool(self.managed),
            "animated": bool(self.animated),
            "available": bool(self.available),
            **user
        }

@model
@dataclass
class Invite(Model):
    id: int = field(id_field=True)
    channel_id: int
    inviter: int
    created_at: int
    max_age: int
    guild_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    type: Optional[int] = field(default=1, validation=And(lambda i: i == 1))

    @property
    async def json(self) -> dict:
        data = await getCore().getUserData(UserId(self.inviter))
        created = datetime.utcfromtimestamp(int(sf_ts(self.id) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        expires = datetime.utcfromtimestamp(int(sf_ts(self.id) / 1000)+self.max_age).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        channel = await getCore().getChannel(self.channel_id)
        j = {
            "code": b64encode(self.id.to_bytes(byte_length(self.id), 'big')),
            "inviter": {
                "id": str(data.uid),
                "username": data.username,
                "avatar": data.avatar,
                "avatar_decoration": data.avatar_decoration,
                "discriminator": data.s_discriminator,
                "public_flags": data.public_flags
            },
            "created_at": created,
            "expires_at": expires,
            "type": 1,
            "channel": {
                "id": str(channel.id),
                "type": channel.type,
                **({"name": channel.name, "icon": channel.icon} if channel.type == ChannelType.GROUP_DM else {})
            },
            "max_age": self.max_age,
        }
        # TODO: add guild field
        return j

    async def getJson(self, with_counts=False, without=None):
        if not without:
            without = []
        j = await self.json
        if with_counts:
            u = await getCore().getRelatedUsersToChannel(self.channel_id)
            j["approximate_member_count"] = len(u)
            j["channel"]["recipients"] = [{"username": (await getCore().getUserData(UserId(i))).username} for i in u]
        for wo in without:
            del j[wo]
        return j