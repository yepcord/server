from copy import deepcopy
from datetime import datetime
from email.message import EmailMessage
from time import mktime
from uuid import uuid4, UUID
from zlib import compressobj, Z_FULL_FLUSH

from dateutil.parser import parse as dparse
from schema import Schema, Use, Optional, And, Or, Regex

from .config import Config
from .enums import ChannelType, MessageType, UserFlags as UserFlagsE
from .errors import EmbedErr, InvalidDataErr
from .proto import PreloadedUserSettings, Version, UserContentSettings, VoiceAndVideoSettings, AfkTimeout, \
    StreamNotificationsEnabled, TextAndImagesSettings, UseRichChatInput, UseThreadSidebar, Theme, RenderSpoilers, \
    InlineAttachmentMedia, RenderEmbeds, RenderReactions, ExplicitContentFilter, ViewNsfwGuilds, ConvertEmoticons, \
    AnimateStickers, ExpressionSuggestionsEnabled, InlineEmbedMedia, PrivacySettings, FriendSourceFlags, StatusSettings, \
    ShowCurrentGame, Status, LocalizationSettings, Locale, TimezoneOffset, AppearanceSettings, MessageDisplayCompact, \
    ViewImageDescriptions
from .utils import b64encode, b64decode, snowflake_timestamp, ping_regex, result_to_json, mkError, proto_get
from aiosmtplib import send as smtp_send, SMTPConnectError


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
    DEFAULTS = {}
    SCHEMA: Schema = Schema(dict)
    DB_FIELDS = {}

    def _checkNulls(self):
        for f in self.FIELDS:
            if getattr(self, f, None) == Null:
                delattr(self, f)

    def to_json(self, with_id=False, with_values=False):
        j = {}
        f = list(self.FIELDS)
        if with_id and self.ID_FIELD:
            f.append(self.ID_FIELD)
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

    def setCore(self, core):
        self._core = core
        return self

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
              "expression_suggestions_enabled")
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
        Optional("custom_status"): Or(And(Use(dict), lambda d: "text" in d), type(None)),  # TODO
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
        Optional("mfa"): Or(And(Use(str), lambda s: 16 <= len(s) <= 32 and len(s) % 4 == 0), type(None)),
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
                 view_image_descriptions=Null, **kwargs):
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

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    def to_json(self, with_id=False, with_values=False):
        j = super().to_json(with_id=with_id, with_values=with_values)
        if not with_values:
            return j
        if "mfa" in j:
            j["mfa"] = self.mfa_key
        return j

    def to_proto(self) -> PreloadedUserSettings:
        proto = PreloadedUserSettings(
            versions=Version(client_version=14, data_version=62),
            user_content=UserContentSettings(dismissed_contents=b'Q\x01\t\x00\x00\x02\x00\x00\x80'),
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
            native_phone_integration_enabled=proto_get(proto, "voice_and_video.native_phone_integration_enabled.value",
                                                       Null),
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
        return self

class UserData(DBModel):
    FIELDS = ("birth", "username", "discriminator", "phone", "premium", "accent_color", "avatar", "avatar_decoration",
              "banner", "banner_color", "bio", "flags", "public_flags")
    ID_FIELD = "uid"
    SCHEMA = Schema({
        "uid": Use(int), Optional("birth"): str, Optional("username"): str, Optional("discriminator"): int,
        Optional("phone"): Or(str, type(None)), Optional("premium"): Or(Use(bool), type(None)),
        Optional("accent_color"): Or(int, type(None)), Optional("avatar"): Or(str, type(None)),
        Optional("avatar_decoration"): Or(str, type(None)), Optional("banner"): Or(str, type(None)),
        Optional("banner_color"): Or(int, type(None)), Optional("bio"): Use(str), Optional("flags"): Use(int),
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
        self._core = None
        self._uSettings = None
        self._uData = None
        self._uFrecencySettings = None

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    @property
    async def settings(self) -> UserSettings:
        if not self._uSettings:
            self._uSettings = await self._core.getUserSettings(self)
        return self._uSettings

    @property
    async def data(self) -> UserData:
        return await self.userdata

    @property
    async def userdata(self) -> UserData:
        if not self._uData:
            self._uData = await self._core.getUserData(self)
        return self._uData

    @property
    async def settings_proto(self) -> PreloadedUserSettings:
        settings = await self.settings
        return settings.to_proto()

    @property
    async def frecency_settings_proto(self) -> bytes:
        if not self._uFrecencySettings:
            self._uFrecencySettings = await self._core.getFrecencySettings(self)
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
        Optional("guild_id"): Or(int, type(None)),
        Optional("position"): Or(int, type(None)),
        Optional("permission_overwrites"): Or(dict, type(None)),
        Optional("name"): Or(Use(str), type(None)),
        Optional("topic"): Or(Use(str), type(None)),
        Optional("nsfw"): Or(bool, type(None)),
        Optional("bitrate"): Or(int, type(None)),
        Optional("user_limit"): Or(int, type(None)),
        Optional("rate_limit"): Or(int, type(None)),
        Optional("recipients"): Or([int], type(None)),
        Optional("icon"): Or(str, type(None)),
        Optional("owner_id"): Or(int, type(None)),
        Optional("application_id"): Or(int, type(None)),
        Optional("parent_id"): Or(int, type(None)),
        Optional("rtc_region"): Or(str, type(None)),
        Optional("video_quality_mode"): Or(int, type(None)),
        Optional("thread_metadata"): Or(dict, type(None)),
        Optional("default_auto_archive"): Or(int, type(None)),
        Optional("flags"): Or(int, type(None)),
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
        self._core = None

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

    async def messages(self, limit=50, before=None, after=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await self._core.getChannelMessages(self, limit, before, after)

class _Message:
    id = None

    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id

class Message(_Message, DBModel):
    FIELDS = ("channel_id", "author", "content", "edit_timestamp", "attachments", "embeds", "pinned",
              "webhook_id", "application_id", "type", "flags", "message_reference", "thread", "components",
              "sticker_items", "extra_data")
    ID_FIELD = "id"
    ALLOWED_FIELDS = ("nonce",)
    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": [], "extra_data": {}}
    SCHEMA = Schema({
        "id": Use(int),
        "channel_id": Use(int),
        "author": Use(int),
        Optional("content"): Or(str, type(None)),
        Optional("edit_timestamp"): Or(int, type(None)),
        Optional("attachments"): list, # TODO
        Optional("embeds"): list,
        Optional("pinned"): Use(bool),
        Optional("webhook_id"): Or(int, type(None)),
        Optional("application_id"): Or(int, type(None)),
        Optional("type"): Or(int, type(None)),
        Optional("flags"): Use(int),
        Optional("message_reference"): Or(int, type(None)),
        Optional("thread"): Or(int, type(None)),
        Optional("components"): list,
        Optional("sticker_items"): list,
        Optional("extra_data"): dict,
    })
    DB_FIELDS = {"attachments": "j_attachments", "embeds": "j_embeds", "components": "j_components",
                 "sticker_items": "j_sticker_items", "extra_data": "j_extra_data"}

    def __init__(self, id, channel_id, author, content=Null, edit_timestamp=Null, attachments=Null, embeds=Null,
                 pinned=Null, webhook_id=Null, application_id=Null, type=Null, flags=Null, message_reference=Null,
                 thread=Null, components=Null, sticker_items=Null, extra_data=Null, **kwargs):
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
        self._core = None

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

    def _checkEmbeds(self):  # TODO: Check for total lenght
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
            att = await self._core.getAttachmentByUUID(uuid)
            self.attachments.append(att.id)

    @property
    async def json(self):
        author = await self._core.getUserData(UserId(self.author))
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
                if (mem := await self._core.getUserByChannelId(self.channel_id, int(m))):
                    mdata = await mem.data
                    mentions.append({
                        "id": m,
                        "username": mdata.username,
                        "avatar": mdata.avatar,
                        "avatar_decoration": mdata.avatar_decoration,
                        "discriminator": str(mdata.discriminator).rjust(4, "0"),
                        "public_flags": mdata.public_flags
                    })
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if u := self.extra_data.get("user"):
                u = await self._core.getUserData(UserId(u))
                mentions.append({
                    "username": u.username,
                    "public_flags": u.public_flags,
                    "id": str(u.uid),
                    "discriminator": str(u.discriminator).rjust(4, "0"),
                    "avatar_decoration": u.avatar_decoration,
                    "avatar": u.avatar
                })
        for att in self.attachments:
            att = await self._core.getAttachment(att)
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
                "discriminator": str(author.discriminator).rjust(4, "0"),
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
        }
        if nonce := getattr(self, "nonce", None):
            j["nonce"] = nonce
        if message_reference:
            j["message_reference"] = message_reference
        if reactions := await self._core.getMessageReactions(self.id):
            j["reactions"] = []
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
        self._core = None

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)

class UserNote(DBModel):
    FIELDS = ("uid", "target_uid", "note",)
    SCHEMA = Schema({
        "uid": Use(int),
        "target_uid": Use(int),
        "note": Or(Use(str), type(None))
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
    FIELDS = ("code", "template")
    DB_FIELDS = {"template": "j_template"}
    SCHEMA = Schema({
        "code": And(Use(str), lambda s: bool(b64decode(s))),
        "type": [{
            "id": Use(int),
            "parent_id": Or(int, type(None)),
            "name": str,
            "type": And(Use(int),lambda i: i in ChannelType.values())
        }],
    })

    def __init__(self, code, template):
        self.code = code
        self.template = template

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
        "emoji_id": Or(int, type(None)),
        "emoji_name": Or(str, type(None))
    })

    def __init__(self, message_id, user_id, emoji_id=Null, emoji_name=Null):
        self.message_id = message_id
        self.user_id = user_id
        self.emoji_id = emoji_id
        self.emoji_name = emoji_name

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)