from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from time import mktime
from typing import Any, Optional as tOptional
from uuid import uuid4, UUID
from zlib import compressobj, Z_FULL_FLUSH

from dateutil.parser import parse as dparse
from aiomysql import escape_string
from schema import Schema, Use, Optional, And, Or, Regex

from .config import Config
from .ctx import Ctx, getCore
from .enums import ChannelType, MessageType, UserFlags as UserFlagsE, RelationshipType
from .errors import EmbedErr, InvalidDataErr
from .model import model, field, Model
from .proto import PreloadedUserSettings, Version, UserContentSettings, VoiceAndVideoSettings, AfkTimeout, \
    StreamNotificationsEnabled, TextAndImagesSettings, UseRichChatInput, UseThreadSidebar, Theme, RenderSpoilers, \
    InlineAttachmentMedia, RenderEmbeds, RenderReactions, ExplicitContentFilter, ViewNsfwGuilds, ConvertEmoticons, \
    AnimateStickers, ExpressionSuggestionsEnabled, InlineEmbedMedia, PrivacySettings, FriendSourceFlags, StatusSettings, \
    ShowCurrentGame, Status, LocalizationSettings, Locale, TimezoneOffset, AppearanceSettings, MessageDisplayCompact, \
    ViewImageDescriptions
from .utils import b64encode, b64decode, snowflake_timestamp, ping_regex, result_to_json, mkError, proto_get, \
    byte_length, sf_ts, json_to_sql
from aiosmtplib import send as smtp_send, SMTPConnectError

NoneType = type(None)

class _Null:
    value = None
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(_Null, cls).__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    def __int__(self):
        return 0

    def __repr__(self):
        return "<Null>"

    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration

Null = _Null()
Null.value = Null

class DBModel:
    FIELDS = ()
    ID_FIELD = None
    ALLOWED_FIELDS = ()
    EXCLUDED_FIELDS = ()
    DEFAULTS = {}
    SCHEMA: Schema = Schema(dict)
    DB_FIELDS = {}

    def _checkNulls(self):
        for f in self.FIELDS:
            if getattr(self, f, None) == Null:
                delattr(self, f)

    def to_json(self, with_id=False, with_values=False, with_excluded=True):
        j = {}
        f = list(self.FIELDS)
        if with_id and self.ID_FIELD:
            f.append(self.ID_FIELD)
        if self.EXCLUDED_FIELDS and not with_excluded:
            for ef in self.EXCLUDED_FIELDS:
                if ef in f:
                    f.remove(ef)
        for k in f:
            if (v := getattr(self, k, Null)) == Null:
                continue
            j[k] = v
        return j

    def to_typed_json(self, func=None, **json_args):
        if func is None:
            func = self.to_json
        schema = self.SCHEMA
        json = func(**json_args)
        if self.ID_FIELD and self.ID_FIELD not in json:
            schema = schema.schema.copy()
            del schema[self.ID_FIELD]
            schema = Schema(schema)
        return schema.validate(json)

    def to_sql_json(self, json_func, **json_args):
        json = json_func(**json_args)
        for key in list(json.keys()):
            if (newkey := self.DB_FIELDS.get(key, key)) != key:
                json[newkey] = json[key]
                del json[key]
        return json

    @classmethod
    def from_result(cls, desc, result):
        return cls(**result_to_json(desc, result))

    def set(self, **kwargs):
        for k, v in kwargs.items():
            if k not in list(self.FIELDS) + list(self.ALLOWED_FIELDS):
                continue
            setattr(self, k, v)
        self._checkNulls()
        return self

    def fill_defaults(self):
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    def get_diff(self, other) -> dict:
        this = self.to_json()
        other = other.to_json()
        diff = {}
        for k, v in this.items():
            if (l := other.get(k, v)) != this[k]:
                diff[k] = l
            if k in other:
                del other[k]
        diff.update(other)
        return diff

    def copy(self):
        o = self.__class__.__new__(self.__class__)
        for k, v in self.__dict__.items():
            if isinstance(v, (dict, list)):
                v = deepcopy(v)
            setattr(o, k, v)
        return o

    def get(self, item, default=None):
        if not hasattr(self, item):
            return default
        return getattr(self, item)

class _User:
    def __init__(self):
        self.id = None

    def __eq__(self, other):
        return isinstance(other, _User) and self.id == other.id

    def get(self, item, default=None):
        if not hasattr(self, item):
            return default
        return getattr(self, item)

@model
@dataclass
class Session(_User):
    uid: int
    sid: int
    sig: str

    @property
    def id(self):
        return self.uid

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.uid).encode('utf8'))}.{b64encode(int.to_bytes(self.sid, 6, 'big'))}.{self.sig}"

    @classmethod
    def from_token(cls, token: str):
        token = token.split(".")
        if len(token) != 3:
            return
        uid, sid, sig = token
        try:
            uid = int(b64decode(uid))
            sid = int.from_bytes(b64decode(sid), "big")
            b64decode(sig)
        except:
            return
        return cls(uid, sid, sig)

@model
@dataclass
class UserSettings(Model):
    uid: int = field(id_field=True)
    mfa: tOptional[bool] = field(nullable=True)
    inline_attachment_media: tOptional[bool] = None
    show_current_game: tOptional[bool] = None
    view_nsfw_guilds: tOptional[bool] = None
    enable_tts_command: tOptional[bool] = None
    render_reactions: tOptional[bool] = None
    gif_auto_play: tOptional[bool] = None
    stream_notifications_enabled: tOptional[bool] = None
    animate_emoji: tOptional[bool] = None
    afk_timeout: tOptional[int] = None
    view_nsfw_commands: tOptional[bool] = None
    detect_platform_accounts: tOptional[bool] = None
    explicit_content_filter: tOptional[int] = None
    default_guilds_restricted: tOptional[bool] = None
    allow_accessibility_detection: tOptional[bool] = None
    native_phone_integration_enabled: tOptional[bool] = None
    friend_discovery_flags: tOptional[int] = None
    contact_sync_enabled: tOptional[bool] = None
    disable_games_tab: tOptional[bool] = None
    developer_mode: tOptional[bool] = None
    render_embeds: tOptional[bool] = None
    animate_stickers: tOptional[int] = None
    message_display_compact: tOptional[bool] = None
    convert_emoticons: tOptional[bool] = None
    passwordless: tOptional[bool] = None
    personalization: tOptional[bool] = None
    usage_statistics: tOptional[bool] = None
    inline_embed_media: tOptional[bool] = None
    use_thread_sidebar: tOptional[bool] = None
    use_rich_chat_input: tOptional[bool] = None
    expression_suggestions_enabled: tOptional[bool] = None
    view_image_descriptions: tOptional[bool] = None
    status: tOptional[str] = field(validation=And(Use(str), Use(str.lower), lambda s: s in ("online", "invisible", "dnd", "idle")), default=None)
    custom_status: tOptional[dict] = field(validation=Or(And(Use(dict), lambda d: "text" in d), NoneType), db_name="j_custom_status", nullable=True, default=None)
    theme: tOptional[str] = field(validation=And(Use(str), Use(str.lower), lambda s: s in ("light", "dark")), default=None)
    locale: tOptional[str] = field(validation=And(Use(str), lambda s: 2 <= len(s) <= 6), default=None)
    timezone_offset: tOptional[int] = field(validation=And(Use(int), lambda i: -600 <= i <= 840), default=None)
    activity_restricted_guild_ids: tOptional[list] = field(validation=[Use(int)], db_name="j_activity_restricted_guild_ids", default=None)
    friend_source_flags: tOptional[dict] = field(validation={"all": Use(bool), Optional("mutual_friends"): Use(bool),
                                          Optional("mutual_guilds"): Use(bool)}, db_name="j_friend_source_flags", default=None)
    guild_positions: tOptional[list] = field(validation=[Use(int)], db_name="j_guild_positions", default=None)
    guild_folders: tOptional[list] = field(validation=[Use(int)], db_name="j_guild_folders", default=None)
    restricted_guilds: tOptional[list] = field(validation=[Use(int)], db_name="j_restricted_guilds", default=None)
    render_spoilers: tOptional[str] = field(validation=And(Use(str), Use(str.upper), lambda s: s in ("ON_CLICK", "IF_MODERATOR", "ALWAYS")), default=None)
    dismissed_contents: tOptional[str] = field(validation=And(Use(str), lambda s: len(s) % 2 == 0), excluded=True, default=None)

    def toJSON(self, **kwargs) -> dict:
        j = super().toJSON(**kwargs)
        if "for_db" in kwargs and "mfa" in j:
            j["mfa"] = self.mfa
        return j

    def to_proto(self) -> PreloadedUserSettings:
        proto = PreloadedUserSettings(
            versions=Version(client_version=14, data_version=1), # TODO: get data version from database
            user_content=UserContentSettings(dismissed_contents=bytes.fromhex(self.dismissed_contents)),
            voice_and_video=VoiceAndVideoSettings(
                afk_timeout=AfkTimeout(value=self.get("afk_timeout", 600)),
                stream_notifications_enabled=StreamNotificationsEnabled(
                    value=bool(self.get("stream_notifications_enabled", True))
                )
            ),
            text_and_images=TextAndImagesSettings(
                use_rich_chat_input=UseRichChatInput(value=self.get("use_rich_chat_input", True)),
                use_thread_sidebar=UseThreadSidebar(value=self.get("use_thread_sidebar", True)),
                render_spoilers=RenderSpoilers(value=self.get("render_spoilers", "ON_CLICK")),
                inline_attachment_media=InlineAttachmentMedia(value=self.get("inline_attachment_media", True)),
                inline_embed_media=InlineEmbedMedia(value=self.get("inline_embed_media", True)),
                render_embeds=RenderEmbeds(value=self.get("render_embeds", True)),
                render_reactions=RenderReactions(value=self.get("render_reactions", True)),
                explicit_content_filter=ExplicitContentFilter(value=self.get("explicit_content_filter", True)),
                view_nsfw_guilds=ViewNsfwGuilds(value=self.get("view_nsfw_guilds", False)),
                convert_emoticons=ConvertEmoticons(value=self.get("convert_emoticons", True)),
                animate_stickers=AnimateStickers(value=self.get("animate_stickers", 1)),
                expression_suggestions_enabled=ExpressionSuggestionsEnabled(value=self.get("expression_suggestions_enabled", True)),
                message_display_compact=MessageDisplayCompact(value=self.get("message_display_compact", False)),
                view_image_descriptions=ViewImageDescriptions(value=self.get("view_image_descriptions", False))
            ),
            privacy=PrivacySettings(
                friend_source_flags=FriendSourceFlags(value=14),
                default_guilds_restricted=self.get("default_guilds_restricted", False),
                allow_accessibility_detection=self.get("allow_accessibility_detection", False)
            ),
            status=StatusSettings(
                status=Status(status=self.get("status", "online")),
                show_current_game=ShowCurrentGame(value=bool(self.get("show_current_game", True)))
            ),
            localization=LocalizationSettings(
                locale=Locale(locale_code=self.get("locale", "en_US")),
                timezone_offset=TimezoneOffset(offset=self.get("timezone_offset", 0))
            ),
            appearance=AppearanceSettings(
                theme=Theme.DARK if self.get("theme", "dark") == "dark" else Theme.LIGHT,
                developer_mode=bool(self.get("developer_mode", False))
            )
        )
        if d := self.get("friend_source_flags"):
            if d["all"]:
                proto.privacy.friend_source_flags.value = 14
            elif d["mutual_friends"] and d["mutual_guilds"]:
                proto.privacy.friend_source_flags.value = 6
            elif d["mutual_guilds"]:
                proto.privacy.friend_source_flags.value = 4
            elif d["mutual_friends"]:
                proto.privacy.friend_source_flags.value = 2
            else:
                proto.privacy.friend_source_flags.value = 0
        return proto

    def from_proto(self, proto):
        self.set(
            inline_attachment_media=proto_get(proto, "text_and_images.inline_attachment_media.value"),
            show_current_game=proto_get(proto, "status.show_current_game.value"),
            view_nsfw_guilds=proto_get(proto, "text_and_images.view_nsfw_guilds.value"),
            enable_tts_command=proto_get(proto, "text_and_images.enable_tts_command.value"),
            render_reactions=proto_get(proto, "text_and_images.render_reactions.value"),
            gif_auto_play=proto_get(proto, "text_and_images.gif_auto_play.value"),
            stream_notifications_enabled=proto_get(proto, "voice_and_video.stream_notifications_enabled.value"),
            animate_emoji=proto_get(proto, "text_and_images.animate_emoji.value"),
            afk_timeout=proto_get(proto, "voice_and_video.afk_timeout.value"),
            view_nsfw_commands=proto_get(proto, "text_and_images.view_nsfw_commands.value"),
            detect_platform_accounts=proto_get(proto, "privacy.detect_platform_accounts.value"),
            explicit_content_filter=proto_get(proto, "text_and_images.explicit_content_filter.value"),
            status=proto_get(proto, "status.status.status"),
            default_guilds_restricted=proto_get(proto, "privacy.default_guilds_restricted"),
            theme="dark" if proto_get(proto, "appearance.theme", 1) == 1 else "light",
            allow_accessibility_detection=proto_get(proto, "privacy.allow_accessibility_detection"),
            locale=proto_get(proto, "localization.locale.locale_code"),
            native_phone_integration_enabled=proto_get(proto, "voice_and_video.native_phone_integration_enabled.value"),
            timezone_offset=proto_get(proto, "localization.timezone_offset.offset"),
            friend_discovery_flags=proto_get(proto, "privacy.friend_discovery_flags.value"),
            contact_sync_enabled=proto_get(proto, "privacy.contact_sync_enabled.value"),
            disable_games_tab=proto_get(proto, "game_library.disable_games_tab.value"),
            developer_mode=proto_get(proto, "appearance.developer_mode"),
            render_embeds=proto_get(proto, "text_and_images.render_embeds.value"),
            animate_stickers=proto_get(proto, "text_and_images.animate_stickers.value"),
            message_display_compact=proto_get(proto, "text_and_images.message_display_compact.value"),
            convert_emoticons=proto_get(proto, "text_and_images.convert_emoticons.value"),
            passwordless=proto_get(proto, "privacy.passwordless.value"),
            activity_restricted_guild_ids=proto_get(proto, "privacy.activity_restricted_guild_ids"),
            restricted_guilds=proto_get(proto, "privacy.restricted_guild_ids"),
            render_spoilers=proto_get(proto, "text_and_images.render_spoilers.value"),
            inline_embed_media=proto_get(proto, "text_and_images.inline_embed_media.value"),
            use_thread_sidebar=proto_get(proto, "text_and_images.use_thread_sidebar.value"),
            use_rich_chat_input=proto_get(proto, "text_and_images.use_rich_chat_input.value"),
            expression_suggestions_enabled=proto_get(proto, "text_and_images.expression_suggestions_enabled.value"),
            view_image_descriptions=proto_get(proto, "text_and_images.view_image_descriptions.value"),
        )
        if proto_get(proto, "status.custom_status") is not None:
            cs = {}
            custom_status = proto_get(proto, "status.custom_status")
            cs["text"] = proto_get(custom_status, "text", None)
            cs["emoji_id"] = proto_get(custom_status, "emoji_id", None)
            cs["emoji_name"] = proto_get(custom_status, "emoji_name", None)
            cs["expires_at_ms"] = proto_get(custom_status, "expires_at_ms", None)
            self.set(custom_status=cs)
        if (p := proto_get(proto, "privacy.friend_source_flags.value")) is not None:
            if p == 14:
                self.set(friend_source_flags={"all": True})
            elif p == 6:
                self.set(friend_source_flags={"all": False, "mutual_friends": True, "mutual_guilds": True})
            elif p == 4:
                self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": True})
            elif p == 2:
                self.set(friend_source_flags={"all": False, "mutual_friends": True, "mutual_guilds": False})
            else:
                self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": True})
        else:
            self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": False})
        if (p := proto_get(proto, "user_content.dismissed_contents")) is not None:
            self.set(dismissed_contents=p[:64].hex())
        return self

@model
@dataclass
class UserData(Model):
    uid: int = field(id_field=True, discord_type=str)
    birth: tOptional[str] = None
    username: tOptional[str] = None
    discriminator: tOptional[int] = None
    bio: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    flags: tOptional[int] = None
    public_flags: tOptional[int] = None
    phone: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    premium: tOptional[str] = field(validation=Or(Use(bool), NoneType), default=None, nullable=True)
    accent_color: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    avatar: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    avatar_decoration: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    banner: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    banner_color: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)

    @property
    def s_discriminator(self) -> str:
        return str(self.discriminator).rjust(4, "0")

    @property
    def nsfw_allowed(self) -> bool:
        db = datetime.strptime(self.birth, "%Y-%m-%d")
        dn = datetime.utcnow()
        return dn-db > timedelta(days=18*365+4)

    @property
    def author(self) -> dict:
        j = self.toJSON(discord_types=True)
        j = {
            "id": j["uid"],
            "username": j["username"],
            "avatar": j["avatar"],
            "avatar_decoration": j["avatar_decoration"],
            "discriminator": self.s_discriminator,
            "public_flags": j["public_flags"],
        }
        return j

@model
@dataclass
class User(_User, Model):
    id: int = field(id_field=True)
    email: tOptional[str] = field(validation=And(Use(str), Use(str.lower),
                               lambda s: Regex(r'^[a-z0-9_\.]{1,64}@[a-zA-Z-_\.]{2,250}?\.[a-zA-Z]{2,6}$').validate(s)), default=None)
    password: tOptional[str] = None
    key: tOptional[str] = None
    verified: tOptional[bool] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self._uSettings = None
        self._uData = None
        self._uFrecencySettings = None

    @property
    async def settings(self) -> UserSettings:
        if not self._uSettings:
            self._uSettings = await getCore().getUserSettings(self)
        return self._uSettings

    @property
    async def data(self) -> UserData:
        return await self.userdata

    @property
    async def userdata(self) -> UserData:
        if not self._uData:
            self._uData = await getCore().getUserData(self)
        return self._uData

    @property
    async def settings_proto(self) -> PreloadedUserSettings:
        settings = await self.settings
        return settings.to_proto()

    @property
    async def frecency_settings_proto(self) -> bytes:
        if not self._uFrecencySettings:
            self._uFrecencySettings = await getCore().getFrecencySettings(self)
        return b64decode(self._uFrecencySettings.encode("utf8"))

class UserId(_User):
    def __init__(self, uid):
        self.id = uid

class _Channel:
    id = None

    def __eq__(self, other):
        return isinstance(other, _Channel) and self.id == other.id

class ChannelId(_Channel):
    def __init__(self, cid):
        self.id = cid

@model
@dataclass
class Channel(_Channel, Model):
    id: int = field(id_field=True)
    type: int
    guild_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    position: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    permission_overwrites: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True, db_name="j_permission_overwrites")
    name: tOptional[str] = None
    topic: tOptional[str] = None
    nsfw: tOptional[bool] = field(validation=Or(bool, NoneType), default=None, nullable=True)
    bitrate: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    user_limit: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    rate_limit: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    recipients: tOptional[int] = field(validation=Or([int], NoneType), default=None, nullable=True, db_name="j_recipients")
    icon: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    owner_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    application_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    parent_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    rtc_region: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    video_quality_mode: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    thread_metadata: tOptional[dict] = field(validation=Or(dict, NoneType), default=None, nullable=True, db_name="j_thread_metadata")
    default_auto_archive: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    flags: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.last_message_id = None

    async def messages(self, limit=50, before=None, after=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await getCore().getChannelMessages(self, limit, before, after)

    @property
    async def json(self):
        if self.type == ChannelType.GUILD_CATEGORY:
            return {
                "type": self.type,
                "position": self.position,
                "permission_overwrites": self.permission_overwrites,
                "name": self.name,
                "id": str(self.id),
                "flags": self.flags
            }
        elif self.type == ChannelType.GUILD_TEXT:
            return {
                "type": self.type,
                "topic": self.topic,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": self.permission_overwrites,
                "parent_id": str(self.parent_id),
                "name": self.name,
                "last_message_id": self.last_message_id,
                "id": str(self.id),
                "flags": self.flags
            }
        elif self.type == ChannelType.GUILD_VOICE:
            return {
                "user_limit": self.user_limit,
                "type": self.type,
                "rtc_region": self.rtc_region,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": self.permission_overwrites,
                "parent_id": str(self.parent_id),
                "name": self.name,
                "last_message_id": self.last_message_id,
                "id": str(self.id),
                "flags": self.flags,
                "bitrate": self.bitrate
            }

class _Message:
    id = None

    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id

@model
@dataclass
class Message(_Message, Model):
    id: int = field(id_field=True, discord_type=str)
    channel_id: int = field(discord_type=str)
    author: int = field()
    content: tOptional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    edit_timestamp: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    attachments: tOptional[list] = field(db_name="j_attachments", default=None)
    embeds: tOptional[list] = field(db_name="j_embeds", default=None)
    pinned: tOptional[bool] = False
    webhook_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    application_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    type: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    flags: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    message_reference: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    thread: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    components: tOptional[list] = field(db_name="j_components", default=None)
    sticker_items: tOptional[list] = field(db_name="j_sticker_items", default=None)
    extra_data: tOptional[dict] = field(db_name="j_extra_data", default=None, private=True)
    guild_id: tOptional[int] = field(validation=Or(int, NoneType), default=None, nullable=True, discord_type=str)
    nonce: tOptional[str] = field(default=None, excluded=True)
    tts: tOptional[str] = field(default=None, excluded=True)
    sticker_ids: tOptional[str] = field(default=None, excluded=True)

    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": [], "extra_data": {}, "guild_id": None} # TODO: remove

    def __post_init__(self) -> None:
        if self.attachments is None: self.attachments = []
        if self.embeds is None: self.embeds = []
        if self.components is None: self.components = []
        if self.sticker_items is None: self.sticker_items = []
        if self.extra_data is None: self.extra_data = {}
        super().__post_init__()

    def fill_defaults(self):  # TODO: remove
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    async def check(self):
        self._checkEmbeds()
        await self._checkAttachments()

    def _checkEmbedImage(self, image, idx):
        if (url := image.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
            raise EmbedErr(self._formatEmbedError(24, {"embed_index": idx, "scheme": scheme}))
        if image.get("proxy_url"):  # Not supported
            del image["proxy_url"]
        if w := image.get("width"):
            try:
                w = int(w)
                image["width"] = w
            except ValueError:
                del image["width"]
        if w := image.get("height"):
            try:
                w = int(w)
                image["height"] = w
            except ValueError:
                del image["height"]

    def _formatEmbedError(self, code, path=None, replace=None):
        if replace is None:
            replace = {}

        def _mkTree(o, p, e):
            _tmp = o["errors"]["embeds"]
            if p is None:
                _tmp["_errors"] = e
                return
            for s in p.split("."):
                _tmp[s] = {}
                _tmp = _tmp[s]
            _tmp["_errors"] = e

        e = {"code": 50035, "errors": {"embeds": {}}, "message": "Invalid Form Body"}
        if code == 23:
            _mkTree(e, path, [{"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}])
            return e
        elif code == 24:
            m = "Scheme \"%SCHEME%\" is not supported. Scheme must be one of ('http', 'https')."
            for k, v in replace.items():
                m = m.replace(f"%{k.upper()}%", v)
            _mkTree(e, path, [{"code": "URL_TYPE_INVALID_SCHEME", "message": m}])
            return e
        elif code == 25:
            m = "Could not parse %VALUE%. Should be ISO8601."
            for k, v in replace.items():
                m = m.replace(f"%{k.upper()}%", v)
            _mkTree(e, path, [{"code": "DATE_TIME_TYPE_PARSE", "message": m}])
            return e
        elif code == 26:
            _mkTree(e, path, [{"code": "NUMBER_TYPE_MAX", "message": "int value should be <= 16777215 and >= 0."}])
            return e
        elif code == 27:
            m = "Must be %LENGTH% or fewer in length."
            for k, v in replace.items():
                m = m.replace(f"%{k.upper()}%", v)
            _mkTree(e, path, [{"code": "BASE_TYPE_MAX_LENGTH", "message": m}])
            return e
        elif code == 28:
            _mkTree(e, path, [{"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or fewer in length."}])
            return e

    def _checkEmbeds(self):  # TODO: Check for total text lenght
        def _delIfEmpty(i, a):
            if (v := self.embeds[i].get(a)) and not bool(v):
                del self.embeds[i][a]

        if not hasattr(self, "embeds"):
            return
        if len(self.embeds) > 10:
            raise EmbedErr(self._formatEmbedError(28))
        if type(self.embeds) != list:
            delattr(self, "embeds")
            return
        for idx, embed in enumerate(self.embeds):
            if type(embed) != dict:
                delattr(self, "embeds")
                return
            if not embed.get("title"):
                raise EmbedErr(self._formatEmbedError(23, f"{idx}"))
            embed["type"] = "rich"
            embed["title"] = str(embed["title"])
            _delIfEmpty(idx, "description")
            _delIfEmpty(idx, "url")
            _delIfEmpty(idx, "timestamp")
            _delIfEmpty(idx, "color")
            _delIfEmpty(idx, "footer")
            _delIfEmpty(idx, "image")
            _delIfEmpty(idx, "thumbnail")
            _delIfEmpty(idx, "video")
            _delIfEmpty(idx, "provider")
            _delIfEmpty(idx, "author")
            if len(embed.get("title")) > 256:
                raise EmbedErr(self._formatEmbedError(27, f"{idx}.title", {"length": "256"}))
            if (desc := embed.get("description")):
                embed["description"] = str(desc)
                if len(str(desc)) > 2048:
                    raise EmbedErr(self._formatEmbedError(27, f"{idx}.description", {"length": "2048"}))
            if (url := embed.get("url")):
                url = str(url)
                embed["url"] = url
                if (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedErr(self._formatEmbedError(24, f"{idx}.url", {"scheme": scheme}))
            if (ts := embed.get("timestamp")):
                ts = str(ts)
                embed["timestamp"] = ts
                try:
                    ts = mktime(dparse(ts).timetuple())
                except ValueError:
                    raise EmbedErr(self._formatEmbedError(25, f"{idx}.timestamp", {"value": ts}))
            try:
                if (color := embed.get("color")):
                    color = int(color)
                    if color > 0xffffff or color < 0:
                        raise EmbedErr(self._formatEmbedError(26, f"{idx}.color"))
            except ValueError:
                del self.embeds[idx]["color"]
            if (footer := embed.get("footer")):
                if not footer.get("text"):
                    del self.embeds[idx]["footer"]
                else:
                    if len(footer.get("text")) > 2048:
                        raise EmbedErr(self._formatEmbedError(27, f"{idx}.footer.text", {"length": "2048"}))
                    if (url := footer.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedErr(self._formatEmbedError(24, f"{idx}.footer.icon_url", {"scheme": scheme}))
                    if footer.get("proxy_icon_url"):  # Not supported
                        del footer["proxy_icon_url"]
            if (image := embed.get("image")):
                if not image.get("url"):
                    del self.embeds[idx]["image"]
                else:
                    self._checkEmbedImage(image, idx)
            if (thumbnail := embed.get("thumbnail")):
                if not thumbnail.get("url"):
                    del self.embeds[idx]["thumbnail"]
                else:
                    self._checkEmbedImage(thumbnail, idx)
            if (video := embed.get("video")):
                if not video.get("url"):
                    del self.embeds[idx]["video"]
                else:
                    self._checkEmbedImage(video, idx)
            if embed.get("provider"):
                del self.embeds[idx]["provider"]
            if (author := embed.get("author")):
                if not (aname := author.get("name")):
                    del self.embeds[idx]["author"]
                else:
                    if len(aname) > 256:
                        raise EmbedErr(self._formatEmbedError(27, f"{idx}.author.name", {"length": "256"}))
                    if (url := author.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedErr(self._formatEmbedError(24, f"{idx}.author.url", {"scheme": scheme}))
                    if (url := author.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedErr(self._formatEmbedError(24, f"{idx}.author.icon_url", {"scheme": scheme}))
                    if author.get("proxy_icon_url"):  # Not supported
                        del author["proxy_icon_url"]
            if (fields := embed.get("fields")):
                embed["fields"] = fields = fields[:25]
                for fidx, field in enumerate(fields):
                    if not (name := field.get("name")):
                        raise EmbedErr(self._formatEmbedError(23, f"{idx}.fields.{fidx}.name"))
                    if len(name) > 256:
                        raise EmbedErr(self._formatEmbedError(27, f"{idx}.fields.{fidx}.name", {"length": "256"}))
                    if not (value := field.get("value")):
                        raise EmbedErr(self._formatEmbedError(23, f"{idx}.fields.{fidx}.value"))
                    if len(value) > 1024:
                        raise EmbedErr(self._formatEmbedError(27, f"{idx}.fields.{fidx}.value", {"length": "1024"}))
                    if not field.get("inline"):
                        field["inline"] = False

    async def _checkAttachments(self):
        if not hasattr(self, "attachments"):
            return
        attachments = self.attachments.copy()
        self.attachments = []
        for idx, attachment in enumerate(attachments):
            if not attachment.get("uploaded_filename"):
                raise InvalidDataErr(400, mkError(50013, {
                    f"attachments.{idx}.uploaded_filename": {"code": "BASE_TYPE_REQUIRED",
                                                             "message": "Required field"}}))
            uuid = attachment["uploaded_filename"].split("/")[0]
            try:
                uuid = str(UUID(uuid))
            except ValueError:
                continue
            att = await getCore().getAttachmentByUUID(uuid)
            self.attachments.append(att.id)

    @property
    async def json(self):
        j = self.toJSON(for_db=False, discord_types=True, with_private=False)
        j["author"] = (await getCore().getUserData(UserId(self.author))).author
        j["mention_everyone"] = ("@everyone" in self.content or "@here" in self.content) if self.content else None
        j["tts"] = False
        timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.id) / 1000))
        j["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        if self.edit_timestamp:
            edit_timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.edit_timestamp) / 1000))
            j["edit_timestamp"] = edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        j["mentions"] = []
        j["mention_roles"] = []
        j["attachments"] = []
        if self.content:
            for m in ping_regex.findall(self.content):
                if m.startswith("!"):
                    m = m[1:]
                if m.startswith("&"):
                    j["mention_roles"].append(m[1:])
                if mem := await getCore().getUserByChannelId(self.channel_id, int(m)):
                    mdata = await mem.data
                    j["mentions"].append(mdata.author)
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if u := self.extra_data.get("user"):
                u = await getCore().getUserData(UserId(u))
                j["mentions"].append(u.author)
        for att in self.attachments:
            att = await getCore().getAttachment(att)
            j["attachments"].append({
                "filename": att.filename,
                "id": str(att.id),
                "size": att.size,
                "url": f"https://{Config('CDN_HOST')}/attachments/{self.channel_id}/{att.id}/{att.filename}"
            })
            if att.get("content_type"):
                j["attachments"][-1]["content_type"] = att.get("content_type")
            if att.get("metadata"):
                j["attachments"][-1].update(att.metadata)
        if self.message_reference:
            j["message_reference"] = {"message_id": str(self.message_reference), "channel_id": str(self.channel_id)}
        if self.nonce is not None:
            j["nonce"] = self.nonce
        if not Ctx.get("search", False):
            if reactions := await getCore().getMessageReactions(self.id, Ctx.get("user_id", 0)):
                j["reactions"] = reactions
        return j

class ZlibCompressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data) + self.cObj.flush(Z_FULL_FLUSH)

@model
@dataclass
class Relationship(Model):
    u1: int
    u2: int
    type: int

    def discord_type(self, current_uid: int) -> int:
        t: int = self.type
        if t == RelationshipType.PENDING:
            if self.u1 == current_uid:
                return 4
            else:
                return 3
        return t

@model
@dataclass
class ReadState(Model):
    uid: int
    channel_id: int
    count: int
    last_read_id: int

@model
@dataclass
class UserNote(Model):
    uid: int
    target_uid: int
    note: str = field(validation=Or(Use(str), NoneType), nullable=True)

    def to_response(self):
        return {
            "note": self.note,
            "user_id": str(self.uid),
            "note_user_id": str(self.target_uid)
        }

#class UserConnection(DBModel): # TODO: implement UserConnection
#    FIELDS = ("type", "state", "username", "service_uid", "friend_sync", "integrations", "visible",
#              "verified", "revoked", "show_activity", "two_way_link",)
#    ID_FIELD = "uid"
#    DB_FIELDS = {"integrations": "j_integrations"}
#
#    def __init__(self, uid, type, state=Null, username=Null, service_uid=Null, friend_sync=Null, integrations=Null,
#                 visible=Null, verified=Null, revoked=Null, show_activity=Null, two_way_link=Null):
#        self.uid = uid
#        self.type = type
#        self.state = state
#        self.username = username
#        self.service_uid = service_uid
#        self.friend_sync = friend_sync
#        self.integrations = integrations
#        self.visible = visible
#        self.verified = verified
#        self.revoked = revoked
#        self.show_activity = show_activity
#        self.two_way_link = two_way_link
#
#        self._checkNulls()

@model
@dataclass
class Attachment(Model):
    id: int = field(id_field=True)
    channel_id: int
    filename: str
    size: int
    metadata: dict
    uuid: tOptional[str] = field(default=None, nullable=True)
    content_type: tOptional[str] = field(default=None, nullable=True)
    uploaded: bool = False

    def __post_init__(self) -> None:
        if not self.uuid: self.uuid = str(uuid4())

class EmailMsg:
    def __init__(self, to: str, subject: str, text: str):
        self.to = to
        self.subject = subject
        self.text = text

    async def send(self):
        message = EmailMessage()
        message["From"] = "no-reply@yepcord.ml"
        message["To"] = self.to
        message["Subject"] = self.subject
        message.set_content(self.text)
        try:
            await smtp_send(message, hostname=Config('SMTP_HOST'), port=int(Config('SMTP_PORT')))
        except SMTPConnectError:
            pass # TODO: write warning to log

"""
class GuildTemplate(DBModel):
    FIELDS = ("template",)
    ID_FIELD = "id"
    DB_FIELDS = {"template": "j_template"}
    SCHEMA = Schema({
        "id": int,
        "updated_at": Or(int, NoneType),
        "template": {
           "name": str,
           "description": Or(str, NoneType),
           "usage_count": int,
           "creator_id": Use(int),
           "creator":{
              "id": Use(int),
              "username": str,
              "avatar": Or(str, NoneType),
              "avatar_decoration":Or(str, NoneType),
              "discriminator": Use(int),
              "public_flags": int
           },
           "source_guild_id": Use(int),
           "serialized_source_guild": {
              "name": str,
              "description": Or(str, NoneType),
              "region": str,
              "verification_level": int,
              "default_message_notifications": int,
              "explicit_content_filter": int,
              "preferred_locale": str,
              "afk_timeout": int,
              "roles":[{
                    "id": int,
                    "name": str,
                    "color": int,
                    "hoist": bool,
                    "mentionable": bool,
                    "permissions": Use(int),
                    "icon": Or(str, NoneType),
                    "unicode_emoji": Or(str, NoneType)
              }],
              "channels":[{
                    "id": int,
                    "type": And(Use(int), lambda i: i in ChannelType.values()),
                    "name": str,
                    "position": int,
                    "topic": Or(str, NoneType),
                    "bitrate": int,
                    "user_limit": int,
                    "nsfw": bool,
                    "rate_limit_per_user": int,
                    "parent_id": Or(int, NoneType),
                    "default_auto_archive_duration": Or(int, NoneType),
                    "permission_overwrites": [Any], # TODO
                    "available_tags": Any, # TODO
                    "template": str,
                    "default_reaction_emoji": Or(str, NoneType),
                    "default_thread_rate_limit_per_user": Or(int, NoneType),
                    "default_sort_order": Any # TODO
              }],
              "afk_channel_id": Or(int, NoneType),
              "system_channel_id": int,
              "system_channel_flags": int
           },
           "is_dirty": Any # TODO
        }
    })

    def __init__(self, id, template):
        self.code = id
        self.template = template

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)
"""

class UserFlags:
    def __init__(self, value: int):
        self.value = value
        self.parsedFlags = self.parseFlags(value)

    @staticmethod
    def parseFlags(value: int) -> list:
        flags = []
        for val in UserFlagsE.values().values():
            if (value & val) == val:
                flags.append(val)
        return flags

    def add(self, val: int):
        if val not in self.parsedFlags:
            self.value += val
            self.parsedFlags.append(val)
        return self

    def remove(self, val: int):
        if val in self.parsedFlags:
            self.value -= val
            self.parsedFlags.remove(val)
        return self

@model
@dataclass
class Reaction(Model):
    message_id: int
    user_id: int
    emoji_id: tOptional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    emoji_name: tOptional[str] = field(default=None, nullable=True)

@model
@dataclass
class SearchFilter(Model):
    author_id: tOptional[int] = None
    sort_by: tOptional[str] = field(default=None, validation=And(lambda s: s in ("id",)))
    sort_order: tOptional[str] = field(default=None, validation=And(lambda s: s in ("asc", "desc")))
    mentions: tOptional[int] = None
    has: tOptional[str] = field(default=None, validation=And(lambda s: s in ("link", "video", "file", "embed", "image", "sound", "sticker")))
    min_id: tOptional[int] = None
    max_id: tOptional[int] = None
    pinned: tOptional[str] = field(default=None, validation=And(lambda s: s in ("true", "false")))
    offset: tOptional[int] = None
    content: tOptional[str] = None

    _HAS = {
        "link": "`content` REGEXP '(http|https):\\\\/\\\\/[a-zA-Z0-9-_]{1,63}\\\\.[a-zA-Z]{1,63}'",
        "image": "true in (select content_type LIKE '%image/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "video": "true in (select content_type LIKE '%video/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "file": "JSON_LENGTH(`j_attachments`) > 0",
        "embed": "JSON_LENGTH(`j_embeds`) > 0",
        "sound": "true in (select content_type LIKE '%audio/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        #"sticker": "" # TODO
    }

    def __post_init__(self):
        if self.sort_by == "relevance":
            self.sort_by = "timestamp"
            self.sort_order = "desc"
        if self.sort_by == "timestamp":
            self.sort_by = "id"
            self.sort_order = "desc"
        self.sort_by = self.sort_by or "id"
        self.sort_order = self.sort_order or "desc"
        super().__post_init__()

    def to_sql(self) -> str:
        data = self.toJSON()
        print(data)
        where = []
        if "author_id" in data:
            where.append(f"`author`={data['author_id']}")
        if "mentions" in data:
            where.append("`content` REGEXP '<@!{0,1}\\\\d{17,}>'")
        if "pinned" in data:
            where.append(f"`pinned`={data['pinned']}")
        if "min_id" in data:
            where.append(f"`id` > {data['min_id']}")
        if "max_id" in data:
            where.append(f"`id` < {data['max_id']}")
        if "content" in data:
            where.append(f"`content`=\"{escape_string(data['content'])}\"")
        if "has" in data and data["has"] in self._HAS:
            where.append(self._HAS[data["has"]])
        if not where:
            where = ["true"]
        where = " AND ".join(where)
        if "sort_by" in data:
            where += f" ORDER BY `{data['sort_by']}`"
            if "sort_order" in data:
                where += f" {data['sort_order'].upper()}"
        if "offset" in data:
            where += f" LIMIT {data['offset']},25"
        else:
            where += f" LIMIT 25"
        return where

@model
@dataclass
class Invite(Model):
    id: int = field(id_field=True)
    channel_id: int
    inviter: int
    created_at: int
    max_age: int
    guild_id: tOptional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    type: tOptional[int] = field(default=1, validation=And(lambda i: i == 1))

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

class _Guild:
    id = None

    def __eq__(self, other):
        return isinstance(other, _Guild) and self.id == other.id

class GuildId(_Guild):
    def __init__(self, id):
        self.id = id

class Guild(_Guild, DBModel):
    FIELDS = ("owner_id", "name", "icon", "description", "splash", "discovery_splash", "features", "emojis", "stickers",
              "banner", "region", "afk_channel_id", "afk_timeout", "system_channel_id", "verification_level", "roles",
              "default_message_notifications", "mfa_level", "explicit_content_filter", "max_members", "vanity_url_code",
              "system_channel_flags", "preferred_locale", "premium_progress_bar_enabled", "nsfw", "nsfw_level",)
    DB_FIELDS = {"features": "j_features", "emojis": "j_emojis", "stickers": "j_stickers", "roles": "j_roles"}
    ID_FIELD = "id"
    DEFAULTS = {"icon": None, "description": None, "splash": None, "discovery_splash": None, "features": [],
                "emojis": [], "stickers": [], "banner": None, "region": "deprecated", "afk_channel_id": None,
                "afk_timeout": 300, "verification_level": 0, "default_message_notifications": 0, "mfa_level": 0,
                "explicit_content_filter": 0, "max_members": 100, "vanity_url_code": None, "system_channel_flags": 0,
                "preferred_locale": "en-US", "premium_progress_bar_enabled": False, "nsfw": False, "nsfw_level": 0}
    SCHEMA = Schema({
        "id": Use(int),
        "owner_id": Use(int),
        "name": str,
        Optional("icon"): Or(str, NoneType),
        Optional("description"): Or(str, NoneType),
        Optional("splash"): Or(str, NoneType),
        Optional("discovery_splash"): Or(str, NoneType),
        Optional("features"): list,
        Optional("emojis"): list,
        Optional("stickers"): list,
        Optional("banner"): Or(str, NoneType),
        Optional("region"): str,
        Optional("afk_channel_id"): Or(int, NoneType),
        Optional("afk_timeout"): int,
        Optional("system_channel_id"): int,
        Optional("verification_level"): int,
        Optional("roles"): [int],
        Optional("default_message_notifications"): int,
        Optional("mfa_level"): int,
        Optional("explicit_content_filter"): int,
        Optional("max_members"): int,
        Optional("vanity_url_code"): Or(str, NoneType),
        Optional("system_channel_flags"): int,
        Optional("preferred_locale"): str,
        Optional("premium_progress_bar_enabled"): Use(bool),
        Optional("nsfw"): Use(bool),
        Optional("nsfw_level"): int,
    })

    def __init__(self, id, owner_id, name, icon=Null, description=Null, splash=Null, discovery_splash=Null, features=Null,
                 emojis=Null, stickers=Null, banner=Null, region=Null, afk_channel_id=Null, afk_timeout=Null,
                 system_channel_id=Null, verification_level=Null, roles=Null, default_message_notifications=Null,
                 mfa_level=Null, explicit_content_filter=Null, max_members=Null, vanity_url_code=Null,
                 system_channel_flags=Null, preferred_locale=Null, premium_progress_bar_enabled=Null, nsfw=Null, nsfw_level=Null):
        self.id = id
        self.owner_id = owner_id
        self.name = name
        self.icon = icon
        self.description = description
        self.splash = splash
        self.discovery_splash = discovery_splash
        self.features = features
        self.emojis = emojis # TODO: Deprecated, use `emoji.guild_id`
        self.stickers = stickers
        self.banner = banner
        self.region = region
        self.afk_channel_id = afk_channel_id
        self.afk_timeout = afk_timeout
        self.system_channel_id = system_channel_id
        self.verification_level = verification_level
        self.roles = roles
        self.default_message_notifications = default_message_notifications
        self.mfa_level = mfa_level
        self.explicit_content_filter = explicit_content_filter
        self.max_members = max_members
        self.vanity_url_code = vanity_url_code
        self.system_channel_flags = system_channel_flags
        self.preferred_locale = preferred_locale
        self.premium_progress_bar_enabled = premium_progress_bar_enabled
        self.nsfw = nsfw
        self.nsfw_level = nsfw_level

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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

class Role(DBModel):
    FIELDS = ("guild_id", "name", "permissions", "position", "color", "hoist", "managed=, ""mentionable", "icon",
              "unicode_emoji", "flags")
    ID_FIELD = "id"
    SCHEMA = Schema({
        "id": Use(int),
        "guild_id": int,
        "name": str,
        Optional("permissions"): int,
        Optional("position"): int,
        Optional("color"): int,
        Optional("hoist"): Use(bool),
        Optional("managed"): Use(bool),
        Optional("mentionable"): Use(bool),
        Optional("icon"): Or(str, NoneType),
        Optional("unicode_emoji"): Or(str, NoneType),
        Optional("flags"): int
    })

    def __init__(self, id, guild_id, name, permissions=Null, position=Null, color=Null, hoist=Null, managed=Null,
                 mentionable=Null, icon=Null, unicode_emoji=Null, flags=Null):
        self.id = id
        self.guild_id = guild_id
        self.name = name
        self.permissions = permissions
        self.position = position
        self.color = color
        self.hoist = hoist
        self.managed = managed
        self.mentionable = mentionable
        self.icon = icon
        self.unicode_emoji = unicode_emoji
        self.flags = flags

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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

class GuildMember(_User, DBModel):
    FIELDS = ("user_id", "guild_id", "joined_at", "avatar", "communication_disabled_until", "flags", "nick", "roles",
              "mute", "deaf",)
    ALLOWED_FIELDS = ("_user")
    DB_FIELDS = {"roles": "j_roles"}
    SCHEMA = Schema({
        "user_id": Use(int),
        "guild_id": Use(int),
        "joined_at": int,
        Optional("avatar"): Or(str, NoneType),
        Optional("communication_disabled_until"): Or(int, NoneType),
        Optional("flags"): int,
        Optional("nick"): Or(str, NoneType),
        Optional("roles"): [int],
        Optional("mute"): Use(bool),
        Optional("deaf"): Use(bool)
    })

    def __init__(self, user_id, guild_id, joined_at, avatar=Null, communication_disabled_until=Null, flags=Null,
                 nick=Null, roles=Null, mute=Null, deaf=Null):
        self.user_id = user_id
        self.guild_id = guild_id
        self.joined_at = joined_at
        self.avatar = avatar
        self.communication_disabled_until = communication_disabled_until
        self.flags = flags
        self.nick = nick
        self.roles = roles
        self.mute = mute
        self.deaf = deaf

        self._user = User(user_id)

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    @property
    async def json(self) -> dict:
        data = await getCore().getUserData(UserId(self.user_id))
        return {
            "avatar": self.avatar,
            "communication_disabled_until": self.communication_disabled_until,
            "flags": self.flags,
            "joined_at": datetime.utcfromtimestamp(self.joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "nick": self.nick,
            "is_pending": False,  # TODO
            "pending": False,
            "premium_since": datetime.utcfromtimestamp(int(snowflake_timestamp(self.user_id)/1000)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "roles": self.roles,
            "user": {
                "id": str(data.uid),
                "username": data.username,
                "avatar": data.avatar,
                "avatar_decoration": data.avatar_decoration,
                "discriminator": data.s_discriminator,
                "public_flags": data.public_flags
            },
            "mute": self.mute,
            "deaf": self.deaf
        }

    @property
    async def data(self) -> UserData:
        d = await self._user.data
        if self.avatar:
            d.avatar = self.avatar
        return d

class Emoji(DBModel):
    FIELDS = ("name", "user_id", "guild_id", "roles", "require_colons", "managed", "animated", "available",)
    ID_FIELD = "id"
    DB_FIELDS = {"roles": "j_roles"}
    DEFAULTS = {"roles": [], "require_colons": True, "managed": False, "animated": False, "available": True}
    SCHEMA = Schema({
        "id": Use(int),
        "name": str,
        "user_id": Use(int),
        "guild_id": Use(int),
        Optional("roles"): list,
        Optional("require_colons"): Use(bool),
        Optional("managed"): Use(bool),
        Optional("animated"): Use(bool),
        Optional("available"): Use(bool),
    })

    def __init__(self, id, name, user_id, guild_id, roles=Null, require_colons=Null, managed=Null, animated=Null,
                 available=Null):
        self.id = id
        self.user_id = user_id
        self.guild_id = guild_id
        self.name = name
        self.roles = roles
        self.require_colons = require_colons
        self.managed = managed
        self.animated = animated
        self.available = available

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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