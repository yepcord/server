# All 'Guild' classes (Guild, etc.)
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from schema import Or, And, Use

from server.classes.user import UserId
from server.ctx import getCore, Ctx
from server.enums import ChannelType
from server.model import model, Model, field
from server.utils import b64encode, int_length, sf_ts
from ..discord_converters.guild import discord_Guild, discord_Role, discord_Emoji, discord_Invite
from ..utils import NoneType


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
    afk_channel_id: Optional[int] = field(default=None, nullable=True, validation=Or(Use(int), NoneType))
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

    json = property(discord_Guild)

    DEFAULTS = {"icon": None, "description": None, "splash": None, "discovery_splash": None, "features": [],
                "emojis": [], "stickers": [], "banner": None, "region": "deprecated", "afk_channel_id": None,
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

    json = property(discord_Role)

@model
@dataclass
class Emoji(Model):
    id: int = field(id_field=True)
    name: str
    user_id: int
    guild_id: int
    roles: Optional[list] = field(default=None, db_name="j_roles")
    require_colons: Optional[bool] = False
    managed: Optional[bool] = False
    animated: Optional[bool] = False
    available: Optional[bool] = False

    DEFAULTS = {"roles": [], "require_colons": True, "managed": False, "animated": False, "available": True} # TODO: remove or replace with more convenient solution

    def fill_defaults(self):  # TODO: remove or replace with more convenient solution
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    json = property(discord_Emoji)

@model
@dataclass
class Invite(Model):
    id: int = field(id_field=True)
    channel_id: int
    inviter: int
    created_at: int
    max_age: int
    max_uses: Optional[int] = 0
    guild_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    type: Optional[int] = field(default=1, validation=And(lambda i: i in (0, 1)))

    json = property(discord_Invite)
