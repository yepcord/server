from copy import deepcopy
from datetime import datetime, timedelta
from email.message import EmailMessage
from time import mktime
from typing import Any, List, Tuple, Dict, Optional as tOptional
from uuid import uuid4, UUID
from zlib import compressobj, Z_FULL_FLUSH

from dateutil.parser import parse as dparse
from aiomysql import escape_string
from schema import Schema, Use, Optional, And, Or, Regex

from .config import Config
from .ctx import Ctx, getCore, getGateway
from .enums import ChannelType, MessageType, UserFlags as UserFlagsE, RelationshipType
from .errors import EmbedErr, InvalidDataErr
from .proto import PreloadedUserSettings, Version, UserContentSettings, VoiceAndVideoSettings, AfkTimeout, \
    StreamNotificationsEnabled, TextAndImagesSettings, UseRichChatInput, UseThreadSidebar, Theme, RenderSpoilers, \
    InlineAttachmentMedia, RenderEmbeds, RenderReactions, ExplicitContentFilter, ViewNsfwGuilds, ConvertEmoticons, \
    AnimateStickers, ExpressionSuggestionsEnabled, InlineEmbedMedia, PrivacySettings, FriendSourceFlags, StatusSettings, \
    ShowCurrentGame, Status, LocalizationSettings, Locale, TimezoneOffset, AppearanceSettings, MessageDisplayCompact, \
    ViewImageDescriptions
from .utils import b64encode, b64decode, snowflake_timestamp, ping_regex, result_to_json, mkError, proto_get, \
    byte_length, sf_ts
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

    def to_typed_json(self, **json_args):
        schema = self.SCHEMA
        json = self.to_json(**json_args)
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

class Session(_User, DBModel):
    FIELDS = ("uid", "sid", "sig")
    SCHEMA = Schema({"uid": int, "sid": int, "sig": str})

    def __init__(self, uid, sid, sig):
        self.id = uid
        self.uid = uid
        self.sid = sid
        self.sig = sig
        self.token = f"{b64encode(str(uid).encode('utf8'))}.{b64encode(int.to_bytes(sid, 6, 'big'))}.{sig}"

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

class UserSettings(DBModel):
    FIELDS = ("inline_attachment_media", "show_current_game", "view_nsfw_guilds", "enable_tts_command",
              "render_reactions", "gif_auto_play", "stream_notifications_enabled", "animate_emoji", "afk_timeout",
              "view_nsfw_commands", "detect_platform_accounts", "explicit_content_filter", "status", "custom_status",
              "default_guilds_restricted", "theme", "allow_accessibility_detection", "locale",
              "native_phone_integration_enabled", "timezone_offset", "friend_discovery_flags", "contact_sync_enabled",
              "disable_games_tab", "developer_mode", "render_embeds", "animate_stickers", "message_display_compact",
              "convert_emoticons", "passwordless", "mfa", "activity_restricted_guild_ids", "friend_source_flags",
              "guild_positions", "guild_folders", "restricted_guilds", "personalization", "usage_statistics",
              "render_spoilers", "inline_embed_media", "use_thread_sidebar", "use_rich_chat_input",
              "expression_suggestions_enabled", "dismissed_contents",)
    EXCLUDED_FIELDS = ("dismissed_contents",)
    ID_FIELD = "uid"
    DB_FIELDS = {"custom_status": "j_custom_status", "activity_restricted_guild_ids": "j_activity_restricted_guild_ids",
                 "friend_source_flags": "j_friend_source_flags", "guild_positions": "j_guild_positions",
                 "guild_folders": "j_guild_folders", "restricted_guilds": "j_restricted_guilds"}
    SCHEMA = Schema({
        "uid": Use(int),
        Optional("inline_attachment_media"): Use(bool),
        Optional("show_current_game"): Use(bool),
        Optional("view_nsfw_guilds"): Use(bool),
        Optional("enable_tts_command"): Use(bool),
        Optional("render_reactions"): Use(bool),
        Optional("gif_auto_play"): Use(bool),
        Optional("stream_notifications_enabled"): Use(bool),
        Optional("animate_emoji"): Use(bool),
        Optional("afk_timeout"): Use(int),
        Optional("view_nsfw_commands"): Use(bool),
        Optional("detect_platform_accounts"): Use(bool),
        Optional("explicit_content_filter"): Use(int),
        Optional("status"): And(Use(str), Use(str.lower), lambda s: s in ("online", "invisible", "dnd", "idle")),
        Optional("custom_status"): Or(And(Use(dict), lambda d: "text" in d), NoneType),  # TODO
        Optional("default_guilds_restricted"): Use(bool),
        Optional("theme"): And(Use(str), Use(str.lower), lambda s: s in ("light", "dark")),
        Optional("allow_accessibility_detection"): Use(bool),
        Optional("locale"): And(Use(str), lambda s: 2 <= len(s) <= 6),
        Optional("native_phone_integration_enabled"): Use(bool),
        Optional("timezone_offset"): And(Use(int), lambda i: -600 <= i <= 840),
        Optional("friend_discovery_flags"): Use(int),
        Optional("contact_sync_enabled"): Use(bool),
        Optional("disable_games_tab"): Use(bool),
        Optional("developer_mode"): Use(bool),
        Optional("render_embeds"): Use(bool),
        Optional("animate_stickers"): Use(bool),
        Optional("message_display_compact"): Use(bool),
        Optional("convert_emoticons"): Use(bool),
        Optional("passwordless"): Use(bool),
        Optional("mfa"): Or(And(Use(str), lambda s: 16 <= len(s) <= 32 and len(s) % 4 == 0), NoneType),
        Optional("activity_restricted_guild_ids"): [Use(int)],
        Optional("friend_source_flags"): {"all": Use(bool),Optional("mutual_friends"): Use(bool),
                                          Optional("mutual_guilds"): Use(bool)},
        Optional("guild_positions"): [Use(int)],
        Optional("guild_folders"): [Use(int)],
        Optional("restricted_guilds"): [Use(int)],
        Optional("personalization"): Use(bool),
        Optional("usage_statistics"): Use(bool),
        Optional("render_spoilers"): And(Use(str), Use(str.upper), lambda s: s in ("ON_CLICK", "IF_MODERATOR", "ALWAYS")),
        Optional("inline_embed_media"): Use(bool),
        Optional("use_thread_sidebar"): Use(bool),
        Optional("use_rich_chat_input"): Use(bool),
        Optional("expression_suggestions_enabled"): Use(bool),
        Optional("view_image_descriptions"): Use(bool),
        Optional("dismissed_contents"): And(Use(str), lambda s: len(s) % 2 == 0)
    })

    def __init__(self,
                 uid, inline_attachment_media=Null, show_current_game=Null, view_nsfw_guilds=Null,
                 enable_tts_command=Null, render_reactions=Null, gif_auto_play=Null, stream_notifications_enabled=Null,
                 animate_emoji=Null, afk_timeout=Null, view_nsfw_commands=Null, detect_platform_accounts=Null,
                 explicit_content_filter=Null, status=Null, custom_status=Null, default_guilds_restricted=Null,
                 theme=Null, allow_accessibility_detection=Null, locale=Null, native_phone_integration_enabled=Null,
                 timezone_offset=Null, friend_discovery_flags=Null, contact_sync_enabled=Null, disable_games_tab=Null,
                 developer_mode=Null, render_embeds=Null, animate_stickers=Null, message_display_compact=Null,
                 convert_emoticons=Null, passwordless=Null, mfa=Null, activity_restricted_guild_ids=Null,
                 friend_source_flags=Null, guild_positions=Null, guild_folders=Null, restricted_guilds=Null,
                 personalization=Null, usage_statistics=Null, render_spoilers=Null, inline_embed_media=Null,
                 use_thread_sidebar=Null, use_rich_chat_input=Null, expression_suggestions_enabled=Null,
                 view_image_descriptions=Null, dismissed_contents=Null, **kwargs):
        self.uid = uid
        self.inline_attachment_media = inline_attachment_media
        self.show_current_game = show_current_game
        self.view_nsfw_guilds = view_nsfw_guilds
        self.enable_tts_command = enable_tts_command
        self.render_reactions = render_reactions
        self.gif_auto_play = gif_auto_play
        self.stream_notifications_enabled = stream_notifications_enabled
        self.animate_emoji = animate_emoji
        self.afk_timeout = afk_timeout
        self.view_nsfw_commands = view_nsfw_commands
        self.detect_platform_accounts = detect_platform_accounts
        self.explicit_content_filter = explicit_content_filter
        self.status = status
        if isinstance(custom_status, dict):
            if not custom_status:
                custom_status = None
        self.custom_status = custom_status
        self.default_guilds_restricted = default_guilds_restricted
        self.theme = theme
        self.allow_accessibility_detection = allow_accessibility_detection
        self.locale = locale
        self.native_phone_integration_enabled = native_phone_integration_enabled
        self.timezone_offset = timezone_offset
        self.friend_discovery_flags = friend_discovery_flags
        self.contact_sync_enabled = contact_sync_enabled
        self.disable_games_tab = disable_games_tab
        self.developer_mode = developer_mode
        self.render_embeds = render_embeds
        self.animate_stickers = animate_stickers
        self.message_display_compact = message_display_compact
        self.convert_emoticons = convert_emoticons
        self.passwordless = passwordless
        self.mfa_key = mfa
        self.mfa = bool(mfa) if mfa != Null else Null
        self.activity_restricted_guild_ids = activity_restricted_guild_ids
        self.friend_source_flags = friend_source_flags
        self.guild_positions = guild_positions
        self.guild_folders = guild_folders
        self.restricted_guilds = restricted_guilds
        self.personalization = personalization
        self.usage_statistics = usage_statistics
        self.render_spoilers = render_spoilers
        self.inline_embed_media = inline_embed_media
        self.use_thread_sidebar = use_thread_sidebar
        self.use_rich_chat_input = use_rich_chat_input
        self.expression_suggestions_enabled = expression_suggestions_enabled
        self.view_image_descriptions = view_image_descriptions
        self.dismissed_contents = dismissed_contents

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    def to_json(self, with_id=False, with_values=False, with_excluded=True):
        j = super().to_json(with_id=with_id, with_values=with_values, with_excluded=with_excluded)
        if not with_values:
            return j
        if "mfa" in j:
            j["mfa"] = self.mfa_key
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
                animate_stickers=AnimateStickers(value=self.get("animate_stickers", True)),
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
        if (d := self.get("friend_source_flags")):
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
            inline_attachment_media=proto_get(proto, "text_and_images.inline_attachment_media.value", Null),
            show_current_game=proto_get(proto, "status.show_current_game.value", Null),
            view_nsfw_guilds=proto_get(proto, "text_and_images.view_nsfw_guilds.value", Null),
            enable_tts_command=proto_get(proto, "text_and_images.enable_tts_command.value", Null),
            render_reactions=proto_get(proto, "text_and_images.render_reactions.value", Null),
            gif_auto_play=proto_get(proto, "text_and_images.gif_auto_play.value", Null),
            stream_notifications_enabled=proto_get(proto, "voice_and_video.stream_notifications_enabled.value", Null),
            animate_emoji=proto_get(proto, "text_and_images.animate_emoji.value", Null),
            afk_timeout=proto_get(proto, "voice_and_video.afk_timeout.value", Null),
            view_nsfw_commands=proto_get(proto, "text_and_images.view_nsfw_commands.value", Null),
            detect_platform_accounts=proto_get(proto, "privacy.detect_platform_accounts.value", Null),
            explicit_content_filter=proto_get(proto, "text_and_images.explicit_content_filter.value", Null),
            status=proto_get(proto, "status.status.status", Null),
            default_guilds_restricted=proto_get(proto, "privacy.default_guilds_restricted", Null),
            theme="dark" if proto_get(proto, "appearance.theme", 1) == 1 else "light",
            allow_accessibility_detection=proto_get(proto, "privacy.allow_accessibility_detection", Null),
            locale=proto_get(proto, "localization.locale.locale_code", Null),
            native_phone_integration_enabled=proto_get(proto, "voice_and_video.native_phone_integration_enabled.value", Null),
            timezone_offset=proto_get(proto, "localization.timezone_offset.offset", Null),
            friend_discovery_flags=proto_get(proto, "privacy.friend_discovery_flags.value", Null),
            contact_sync_enabled=proto_get(proto, "privacy.contact_sync_enabled.value", Null),
            disable_games_tab=proto_get(proto, "game_library.disable_games_tab.value", Null),
            developer_mode=proto_get(proto, "appearance.developer_mode", Null),
            render_embeds=proto_get(proto, "text_and_images.render_embeds.value", Null),
            animate_stickers=proto_get(proto, "text_and_images.animate_stickers.value", Null),
            message_display_compact=proto_get(proto, "text_and_images.message_display_compact.value", Null),
            convert_emoticons=proto_get(proto, "text_and_images.convert_emoticons.value", Null),
            passwordless=proto_get(proto, "privacy.passwordless.value", Null),
            activity_restricted_guild_ids=proto_get(proto, "privacy.activity_restricted_guild_ids", Null),
            restricted_guilds=proto_get(proto, "privacy.restricted_guild_ids", Null),
            render_spoilers=proto_get(proto, "text_and_images.render_spoilers.value", Null),
            inline_embed_media=proto_get(proto, "text_and_images.inline_embed_media.value", Null),
            use_thread_sidebar=proto_get(proto, "text_and_images.use_thread_sidebar.value", Null),
            use_rich_chat_input=proto_get(proto, "text_and_images.use_rich_chat_input.value", Null),
            expression_suggestions_enabled=proto_get(proto, "text_and_images.expression_suggestions_enabled.value", Null),
            view_image_descriptions=proto_get(proto, "text_and_images.view_image_descriptions.value", Null),
        )
        if proto_get(proto, "status.custom_status", Null) is not Null:
            cs = {}
            custom_status = proto_get(proto, "status.custom_status", Null)
            cs["text"] = proto_get(custom_status, "text", None)
            cs["emoji_id"] = proto_get(custom_status, "emoji_id", None)
            cs["emoji_name"] = proto_get(custom_status, "emoji_name", None)
            cs["expires_at_ms"] = proto_get(custom_status, "expires_at_ms", None)
            self.set(custom_status=cs)
        if (p := proto_get(proto, "privacy.friend_source_flags.value", Null)) is not Null:
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
        if (p := proto_get(proto, "user_content.dismissed_contents", Null)) is not Null:
            self.set(dismissed_contents=p[:64].hex())
        return self

class UserData(DBModel):
    FIELDS = ("birth", "username", "discriminator", "phone", "premium", "accent_color", "avatar", "avatar_decoration",
              "banner", "banner_color", "bio", "flags", "public_flags")
    ID_FIELD = "uid"
    SCHEMA = Schema({
        "uid": Use(int),
        Optional("birth"): str,
        Optional("username"): str,
        Optional("discriminator"): int,
        Optional("phone"): Or(str, NoneType),
        Optional("premium"): Or(Use(bool), NoneType),
        Optional("accent_color"): Or(int, NoneType),
        Optional("avatar"): Or(str, NoneType),
        Optional("avatar_decoration"): Or(str, NoneType),
        Optional("banner"): Or(str, NoneType),
        Optional("banner_color"): Or(int, NoneType),
        Optional("bio"): Use(str),
        Optional("flags"): Use(int),
        Optional("public_flags"): Use(int)
    })

    def __init__(self, uid, birth=Null, username=Null, discriminator=Null, phone=Null, accent_color=Null, premium=Null,
                 avatar=Null, avatar_decoration=Null, banner=Null, banner_color=Null, bio=Null, flags=Null,
                 public_flags=Null, **kwargs):
        self.uid = uid
        self.birth = birth
        self.username = username
        self.discriminator = discriminator
        self.phone = phone
        self.premium = premium
        self.accent_color = accent_color
        self.avatar = avatar
        self.avatar_decoration = avatar_decoration
        self.banner = banner
        self.banner_color = banner_color
        self.bio = bio
        self.flags = flags
        self.public_flags = public_flags

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    @property
    def s_discriminator(self) -> str:
        return str(self.discriminator).rjust(4, "0")

    @property
    def nsfw_allowed(self) -> bool:
        db = datetime.strptime(self.birth, "%Y-%m-%d")
        dn = datetime.utcnow()
        return dn-db > timedelta(days=18*365+4)

class User(_User, DBModel):
    FIELDS = ("email", "password", "key", "verified")
    ID_FIELD = "id"
    SCHEMA = Schema({
        "id": Use(int),
        Optional("email"): And(Use(str), Use(str.lower),
                               lambda s: Regex(r'^[a-z0-9_\.]{1,64}@[a-zA-Z-_\.]{2,250}?\.[a-zA-Z]{2,6}$').validate(s)),
        Optional("password"): Use(str),
        Optional("key"): Use(str),
        Optional("verified"): Use(bool)
    })

    def __init__(self, id, email=Null, password=Null, key=Null, verified=Null):
        self.id = id
        self.email = email
        self.password = password
        self.key = key
        self.verified = verified
        self._uSettings = None
        self._uData = None
        self._uFrecencySettings = None

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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

class Channel(_Channel, DBModel):
    FIELDS = ("type", "guild_id", "position", "permission_overwrites", "name", "topic", "nsfw", "bitrate", "user_limit",
              "rate_limit", "recipients", "icon", "owner_id", "application_id", "parent_id", "rtc_region",
              "video_quality_mode", "thread_metadata", "default_auto_archive", "flags")
    ID_FIELD = "id"
    ALLOWED_FIELDS = ("last_message_id",)
    DB_FIELDS = {"permission_overwrites": "j_permission_overwrites", "recipients": "j_recipients",
                 "thread_metadata": "j_thread_metadata"}
    SCHEMA = Schema({
        "id": Use(int),
        "type": Use(int),
        Optional("guild_id"): Or(int, NoneType),
        Optional("position"): Or(int, NoneType),
        Optional("permission_overwrites"): Or(dict, list, NoneType),
        Optional("name"): Or(Use(str), NoneType),
        Optional("topic"): Or(Use(str), NoneType),
        Optional("nsfw"): Or(bool, NoneType),
        Optional("bitrate"): Or(int, NoneType),
        Optional("user_limit"): Or(int, NoneType),
        Optional("rate_limit"): Or(int, NoneType),
        Optional("recipients"): Or([int], NoneType),
        Optional("icon"): Or(str, NoneType),
        Optional("owner_id"): Or(int, NoneType),
        Optional("application_id"): Or(int, NoneType),
        Optional("parent_id"): Or(int, NoneType),
        Optional("rtc_region"): Or(str, NoneType),
        Optional("video_quality_mode"): Or(int, NoneType),
        Optional("thread_metadata"): Or(dict, NoneType),
        Optional("default_auto_archive"): Or(int, NoneType),
        Optional("flags"): Or(int, NoneType),
    })

    def __init__(self, id, type, guild_id=Null, position=Null, permission_overwrites=Null, name=Null, topic=Null,
                 nsfw=Null, bitrate=Null, user_limit=Null, rate_limit=Null, recipients=Null, icon=Null, owner_id=Null,
                 application_id=Null, parent_id=Null, rtc_region=Null, video_quality_mode=Null, thread_metadata=Null,
                 default_auto_archive=Null, flags=Null, last_message_id=None):
        self.id = id
        self.type = type
        self.guild_id = guild_id
        self.position = position
        self.permission_overwrites = permission_overwrites
        self.name = name
        self.topic = topic
        self.nsfw = nsfw
        self.bitrate = bitrate
        self.user_limit = user_limit
        self.rate_limit = rate_limit
        self.recipients = recipients
        self.icon = icon
        self.owner_id = owner_id
        self.application_id = application_id
        self.parent_id = parent_id
        self.rtc_region = rtc_region
        self.video_quality_mode = video_quality_mode
        self.thread_metadata = thread_metadata
        self.default_auto_archive = default_auto_archive
        self.flags = flags
        self.last_message_id = last_message_id

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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

class Message(_Message, DBModel):
    FIELDS = ("channel_id", "author", "content", "edit_timestamp", "attachments", "embeds", "pinned",
              "webhook_id", "application_id", "type", "flags", "message_reference", "thread", "components",
              "sticker_items", "extra_data", "guild_id")
    ID_FIELD = "id"
    ALLOWED_FIELDS = ("nonce",)
    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": [], "extra_data": {}, "guild_id": None}
    SCHEMA = Schema({
        "id": Use(int),
        "channel_id": Use(int),
        "author": Use(int),
        Optional("content"): Or(str, NoneType),
        Optional("edit_timestamp"): Or(int, NoneType),
        Optional("attachments"): list, # TODO
        Optional("embeds"): list,
        Optional("pinned"): Use(bool),
        Optional("webhook_id"): Or(int, NoneType),
        Optional("application_id"): Or(int, NoneType),
        Optional("type"): Or(int, NoneType),
        Optional("flags"): Use(int),
        Optional("message_reference"): Or(int, NoneType),
        Optional("thread"): Or(int, NoneType),
        Optional("components"): list,
        Optional("sticker_items"): list,
        Optional("extra_data"): dict,
        Optional("guild_id"): Or(int, NoneType),
    })
    DB_FIELDS = {"attachments": "j_attachments", "embeds": "j_embeds", "components": "j_components",
                 "sticker_items": "j_sticker_items", "extra_data": "j_extra_data"}

    def __init__(self, id, channel_id, author, content=Null, edit_timestamp=Null, attachments=Null, embeds=Null,
                 pinned=Null, webhook_id=Null, application_id=Null, type=Null, flags=Null, message_reference=Null,
                 thread=Null, components=Null, sticker_items=Null, extra_data=Null, guild_id=Null, **kwargs):
        self.id = id
        self.content = content
        self.channel_id = channel_id
        self.author = author
        self.edit_timestamp = edit_timestamp
        self.attachments = attachments
        self.embeds = embeds
        self.pinned = pinned
        self.webhook_id = webhook_id
        self.application_id = application_id
        self.type = type
        self.flags = flags
        self.message_reference = message_reference
        self.thread = thread
        self.components = components
        self.sticker_items = sticker_items
        self.extra_data = extra_data
        self.guild_id = guild_id

        self.set(**kwargs)

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    async def check(self):
        self._checkEmbeds()
        await self._checkAttachments()

    def _checkEmbedImage(self, image, idx):
        if (url := image.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
            raise EmbedErr(self._formatEmbedError(24, {"embed_index": idx, "scheme": scheme}))
        if image.get("proxy_url"):  # Not supported
            del image["proxy_url"]
        if (w := image.get("width")):
            try:
                w = int(w)
                image["width"] = w
            except:
                del image["width"]
        if (w := image.get("height")):
            try:
                w = int(w)
                image["height"] = w
            except:
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
        author = await getCore().getUserData(UserId(self.author))
        timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.id) / 1000))
        timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        edit_timestamp = None
        if self.edit_timestamp:
            edit_timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.edit_timestamp) / 1000))
            edit_timestamp = edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        mentions = []
        role_mentions = []
        attachments = []
        if self.content:
            for m in ping_regex.findall(self.content):
                if m.startswith("!"):
                    m = m[1:]
                if m.startswith("&"):
                    role_mentions.append(m[1:])
                if (mem := await getCore().getUserByChannelId(self.channel_id, int(m))):
                    mdata = await mem.data
                    mentions.append({
                        "id": m,
                        "username": mdata.username,
                        "avatar": mdata.avatar,
                        "avatar_decoration": mdata.avatar_decoration,
                        "discriminator": mdata.s_discriminator,
                        "public_flags": mdata.public_flags
                    })
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if u := self.extra_data.get("user"):
                u = await getCore().getUserData(UserId(u))
                mentions.append({
                    "username": u.username,
                    "public_flags": u.public_flags,
                    "id": str(u.uid),
                    "discriminator": u.s_discriminator,
                    "avatar_decoration": u.avatar_decoration,
                    "avatar": u.avatar
                })
        for att in self.attachments:
            att = await getCore().getAttachment(att)
            attachments.append({
                "filename": att.filename,
                "id": str(att.id),
                "size": att.size,
                "url": f"https://{Config('CDN_HOST')}/attachments/{self.channel_id}/{att.id}/{att.filename}"
            })
            if att.get("content_type"):
                attachments[-1]["content_type"] = att.get("content_type")
            if att.get("metadata"):
                attachments[-1].update(att.metadata)
        message_reference = None
        if self.message_reference:
            message_reference = {"message_id": str(self.message_reference), "channel_id": str(self.channel_id)}
        j = {
            "id": str(self.id),
            "type": self.type,
            "content": self.content,
            "channel_id": str(self.channel_id),
            "author": {
                "id": str(self.author),
                "username": author.username,
                "avatar": author.avatar,
                "avatar_decoration": author.avatar_decoration,
                "discriminator": author.s_discriminator,
                "public_flags": author.public_flags
            },
            "attachments": attachments,
            "embeds": self.embeds,
            "mentions": mentions,
            "mention_roles": role_mentions,
            "pinned": self.pinned,
            "mention_everyone": ("@everyone" in self.content or "@here" in self.content) if self.content else None,
            "tts": False,
            "timestamp": timestamp,
            "edited_timestamp": edit_timestamp,
            "flags": self.flags,
            "components": self.components,  # TODO: parse components
            **({} if not self.guild_id else {"guild_id": str(self.guild_id)})
        }
        if nonce := getattr(self, "nonce", None):
            j["nonce"] = nonce
        if message_reference:
            j["message_reference"] = message_reference
        if not Ctx.get("search", False):
            if reactions := await getCore().getMessageReactions(self.id, Ctx.get("user_id", 0)):
                j["reactions"] = reactions
        if Ctx.get("with_member") and self.guild_id:
            member = await getCore().getGuildMember(GuildId(self.guild_id), self.author)
            j["member"] = {
                "roles": member.roles,
                "premium_since": member.s_premium_since,
                "pending": False,
                "nick": member.nick,
                "mute": member.mute,
                "joined_at": datetime.utcfromtimestamp(int(snowflake_timestamp(member.joined_at) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
                "flags": member.flags,
                "deaf": member.deaf,
                "communication_disabled_until": member.communication_disabled_until,
                "avatar": member.avatar
            }
        return j

class ZlibCompressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data) + self.cObj.flush(Z_FULL_FLUSH)

class Relationship(DBModel):
    FIELDS = ("u1", "u2", "type")
    SCHEMA = Schema({
        "u1": Use(int),
        "u2": Use(int),
        "type": Use(int)
    })

    def __init__(self, u1=Null, u2=Null, type=Null):
        self.u1 = u1
        self.u2 = u2
        self.type = type

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    def discord_type(self, current_uid: int) -> int:
        t: int = self.type
        if t == RelationshipType.PENDING:
            if self.u1 == current_uid:
                return 4
            else:
                return 3
        return t

class ReadState(DBModel):
    FIELDS = ("channel_id", "last_read_id", "count",)
    ID_FIELD = "uid"
    SCHEMA = Schema({
        "uid": Use(int),
        "channel_id": Use(int),
        "count": Use(int),
        "last_read_id": Use(int)
    })

    def __init__(self, uid, channel_id, last_read_id, count=Null):
        self.uid = uid
        self.channel_id = channel_id
        self.count = count
        self.last_read_id = last_read_id

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

class UserNote(DBModel):
    FIELDS = ("uid", "target_uid", "note",)
    SCHEMA = Schema({
        "uid": Use(int),
        "target_uid": Use(int),
        "note": Or(Use(str), NoneType)
    })

    def __init__(self, uid, target_uid, note):
        self.uid = uid
        self.target_uid = target_uid
        self.note = note

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    def to_response(self):
        return {
            "note": self.note,
            "user_id": str(self.uid),
            "note_user_id": str(self.target_uid)
        }

class UserConnection(DBModel):  # TODO: make schema
    FIELDS = ("type", "state", "username", "service_uid", "friend_sync", "integrations", "visible",
              "verified", "revoked", "show_activity", "two_way_link",)
    ID_FIELD = "uid"
    DB_FIELDS = {"integrations": "j_integrations"}

    def __init__(self, uid, type, state=Null, username=Null, service_uid=Null, friend_sync=Null, integrations=Null,
                 visible=Null, verified=Null, revoked=Null, show_activity=Null, two_way_link=Null):
        self.uid = uid
        self.type = type
        self.state = state
        self.username = username
        self.service_uid = service_uid
        self.friend_sync = friend_sync
        self.integrations = integrations
        self.visible = visible
        self.verified = verified
        self.revoked = revoked
        self.show_activity = show_activity
        self.two_way_link = two_way_link

        self._checkNulls()

class Attachment(DBModel):  # TODO: make schema
    FIELDS = ("channel_id", "filename", "size", "uuid", "content_type", "uploaded", "metadata",)
    ID_FIELD = "id"
    DB_FIELDS = {"metadata": "j_metadata"}

    def __init__(self, id, channel_id, filename, size, uuid=Null, content_type=Null, uploaded=Null, metadata=Null):
        self.id = id
        self.channel_id = channel_id
        self.filename = filename
        self.size = size
        self.uuid = uuid if uuid != Null else str(uuid4())
        self.content_type = content_type
        self.uploaded = uploaded
        self.metadata = metadata

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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

class Reaction(DBModel):
    FIELDS = ("message_id", "user_id", "emoji_id", "emoji_name")
    SCHEMA = Schema({
        "message_id": Use(int),
        "user_id": Use(int),
        "emoji_id": Or(int, NoneType),
        "emoji_name": Or(str, NoneType)
    })

    def __init__(self, message_id, user_id, emoji_id=Null, emoji_name=Null):
        self.message_id = message_id
        self.user_id = user_id
        self.emoji_id = emoji_id
        self.emoji_name = emoji_name

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

class SearchFilter(DBModel): # Not database model, using DBModel for convenience
    FIELDS = ("author_id", "sort_by", "sort_order", "mentions", "has", "min_id", "max_id", "pinned", "offset", "content")
    SCHEMA = Schema({
        Optional("author_id"): Use(int),
        Optional("sort_by"): And(lambda s: s in ("id",)),
        Optional("sort_order"): And(lambda s: s in ("asc", "desc")),
        Optional("mentions"): Use(int),
        Optional("has"): And(lambda s: s in ("link", "video", "file", "embed", "image", "sound", "sticker")),
        Optional("min_id"): Use(int),
        Optional("max_id"): Use(int),
        Optional("pinned"): And(lambda s: s in ("true", "false")),
        Optional("offset"): Use(int),
        Optional("content"): str,
    })
    _HAS = {
        "link": "`content` REGEXP '(http|https):\\\\/\\\\/[a-zA-Z0-9-_]{1,63}\\\\.[a-zA-Z]{1,63}'",
        "image": "true in (select content_type LIKE '%image/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "video": "true in (select content_type LIKE '%video/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "file": "JSON_LENGTH(`j_attachments`) > 0",
        "embed": "JSON_LENGTH(`j_embeds`) > 0",
        "sound": "true in (select content_type LIKE '%audio/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        #"sticker": "" # TODO
    }

    def __init__(self, author_id=Null, sort_by=Null, sort_order=Null, mentions=Null, has=Null, min_id=Null, max_id=Null,
                 pinned=Null, offset=Null, content=Null):
        self.author_id = author_id
        if sort_by == "relevance":
            sort_by = "timestamp"
            sort_order = "desc"
        if sort_by == "timestamp":
            sort_by = "id"
            sort_order = "desc"
        self.sort_by = sort_by or "id"
        self.sort_order = sort_order or "desc"
        self.mentions = mentions
        self.has = has
        self.min_id = min_id
        self.max_id = max_id
        self.pinned = pinned
        self.offset = offset
        self.content = content

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    def to_sql(self) -> str: # TODO: add has parameter
        data = self.to_typed_json()
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
            where.append(f"`content`={escape_string(data['content'])}")
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

class Invite(DBModel):
    FIELDS = ("channel_id", "inviter", "created_at", "max_age", "type", "guild_id")
    ID_FIELD = "id"
    SCHEMA = Schema({
        "id": Use(int),
        "channel_id": Use(int),
        "inviter": Use(int),
        "created_at": Use(int),
        "max_age": Use(int),
        Optional("guild_id"): Or(int, NoneType),
        "type": And(lambda i: i == 1) # TODO
    })

    def __init__(self, id, channel_id, inviter, created_at, max_age, guild_id=Null, type=1):
        self.id = id
        self.channel_id = channel_id
        self.inviter = inviter
        self.created_at = created_at
        self.max_age = max_age
        self.guild_id = guild_id
        self.type = type

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

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
        if channel.guild_id and (guild := await getCore().getGuild(channel.guild_id)):
            j["type"] = 0
            j["guild"] = {
                "banner": guild.banner,
                "description": guild.description,
                "features": guild.features,
                "icon": guild.icon,
                "id": str(guild.id),
                "name": guild.name,
                "nsfw": guild.nsfw,
                "nsfw_level": guild.nsfw_level,
                "premium_subscription_count": 30,
                "splash": guild.splash,
                "vanity_url_code": guild.vanity_url_code,
                "verification_level": guild.verification_level,
            }
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
        data = await self.data
        return {
            "avatar": self.avatar,
            "communication_disabled_until": self.communication_disabled_until,
            "flags": self.flags,
            "joined_at": datetime.utcfromtimestamp(self.joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "nick": self.nick,
            "is_pending": False,  # TODO
            "pending": False,
            "premium_since": self.s_premium_since,
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
    def s_premium_since(self) -> str:
        return datetime.utcfromtimestamp(int(snowflake_timestamp(self.user_id) / 1000)).strftime("%Y-%m-%dT%H:%M:%SZ")

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

class GuildMemberStatus:
    def __init__(self, member: GuildMember):
        self.member = member

    @property
    async def json(self) -> dict:
        j = await self.member.json
        status = getGateway().statuses.get(self.member.user_id) or getGateway().getOfflineStatus(self.member.user_id)
        j["presence"] = {
            "user": {"id": str(self.member.user_id)},
            "status": status["status"],
            "client_status": {} if status["status"] == "offline" else {"desktop": status["status"]},
            "activities": status.get("activities", [])
        }
        return j

    @property
    def group(self) -> str:
        status = getGateway().statuses.get(self.member.user_id)
        if not status:
            return "offline"
        return status["status"] # TODO: add roles check

class GuildMembers:
    def __init__(self, guild_id: int):
        self.guild_id: int = guild_id
        self.ids: List[int] = []
        self.members: Dict[str, List[GuildMemberStatus]] = {}
        self.subscribers: List[str] = []

    def getIndex(self, uid: int) -> tOptional[int]:
        for _, v in self.members.values():
            try:
                return v.index(key=lambda e: e.user_id == uid)
            except ValueError:
                continue

    def addMember(self, member: GuildMember) -> tOptional[int]:
        if member.user_id in self.ids:
            return self.getIndex(member.user_id)
        mem = GuildMemberStatus(member)
        if mem.group not in self.members:
            self.members[mem.group] = []
        self.members[mem.group].append(mem)
        self.ids.append(member.user_id)

        return self.getIndex(member.user_id)

    # FROM https://github.com/fosscord/fosscord-server/blob/c2ced3f5ca02732501d29cfdf791ef8a79a0b7af/src/gateway/opcodes/LazyRequest.ts#L22
    #
    #.createQueryBuilder("member")
    #.where("member.guild_id = :guild_id", {guild_id})
    #.leftJoinAndSelect("member.roles", "role")
    #.leftJoinAndSelect("member.user", "user")
    #.leftJoinAndSelect("user.sessions", "session")
    #.innerJoinAndSelect("user.settings", "settings")
    #.addSelect("CASE WHEN session.status = 'offline' THEN 0 ELSE 1 END", "_status")
    #.orderBy("role.position", "DESC")
    #.addOrderBy("_status", "DESC")
    #.addOrderBy("user.username", "ASC")
    #.offset(Number(range[0]) | | 0)
    #.limit(Number(range[1]) | | 100)

    async def load(self, s, e) -> None:
        if len(self.members) < e+1:
            s = len(self.members)
            if s > 0:
                s -= 1
            for member in await getCore().getGuildMembersRange(self.guild_id, s, e):
                self.addMember(member)

    async def sync(self, rng: Tuple[int, int]) -> Tuple[dict, dict, int, int]:
        # -> groups, members, total, online
        j = {}
        for member in self.members[rng[0]:rng[1]]:
            if member.group not in j:
                j[member.group] = []
            j[member.group].append(await member.json)
        for k in j.keys():
            j[k].sort(key=lambda i: i["nick"] or i["user"]["username"])
        groups = {} # TODO
        return j