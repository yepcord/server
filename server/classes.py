from datetime import datetime
from zlib import compressobj, Z_FULL_FLUSH
from .utils import b64encode, b64decode, snowflake_timestamp, ping_regex, result_to_json

class _Null:
    pass

Null = _Null()

class DBModel:
    FIELDS = ()
    ID_FIELD = None
    NOT_DB_FIELDS = ()
    DEFAULTS = {}

    def _checkNulls(self):
        for f in self.FIELDS:
            if getattr(self, f) == Null:
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

    @classmethod
    def from_result(cls, desc, result):
        return cls(**result_to_json(desc, result))

    def setCore(self, core):
        self._core = core
        return self

    def set(self, **kwargs):
        for k,v in kwargs.items():
            if k not in list(self.FIELDS) + list(self.NOT_DB_FIELDS):
                continue
            setattr(self, k, v)
        return self

    def fill_defaults(self):
        for k,v in self.DEFAULTS.items():
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

class _User:
    def __init__(self):
        self.id = None

    def __eq__(self, other):
        return isinstance(other, _User) and self.id == other.id

class Session(_User, DBModel):
    FIELDS = ("uid", "sid", "sig")

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

class User(_User, DBModel):
    FIELDS = ("email", "password", "key")
    ID_FIELD = "id"

    def __init__(self, id, email=Null, password=Null, key=Null):
        self.id = id
        self.email = email
        self.password = password
        self.key = key
        self._core = None
        self._uSettings = None
        self._uData = None

        self._checkNulls()

    @property
    def settings(self):
        return self._settings()

    @property
    def data(self):
        return self._userdata()

    @property
    def userdata(self):
        return self._userdata()

    async def _settings(self):
        if not self._uSettings:
            self._uSettings = await self._core.getUserSettings(self)
        return self._uSettings

    async def _userdata(self):
        if not self._uData:
            self._uData = await self._core.getUserData(self)
        return self._uData

class UserSettings(DBModel):
    FIELDS = ("inline_attachment_media", "show_current_game", "view_nsfw_guilds", "enable_tts_command",
                  "render_reactions", "gif_auto_play", "stream_notifications_enabled", "animate_emoji", "afk_timeout",
                  "view_nsfw_commands", "detect_platform_accounts", "explicit_content_filter", "status", "custom_status",
                  "default_guilds_restricted", "theme", "allow_accessibility_detection", "locale",
                  "native_phone_integration_enabled", "timezone_offset", "friend_discovery_flags", "contact_sync_enabled",
                  "disable_games_tab", "developer_mode", "render_embeds", "animate_stickers", "message_display_compact",
                  "convert_emoticons", "passwordless", "mfa", "activity_restricted_guild_ids", "friend_source_flags",
                  "guild_positions", "guild_folders", "restricted_guilds", "personalization", "usage_statistics")
    ID_FIELD = "uid"

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
                 personalization=Null, usage_statistics=Null):
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

        self._checkNulls()

    def to_json(self, with_id=False, with_values=False):
        j = super().to_json(with_id=with_id, with_values=with_values)
        if not with_values:
            return j
        if "mfa" in j:
            j["mfa"] = self.mfa_key
        return j

class UserData(DBModel):
    FIELDS = ("birth", "username", "discriminator", "phone", "premium", "accent_color", "avatar", "avatar_decoration",
              "banner", "banner_color", "bio", "flags", "public_flags")
    ID_FIELD = "uid"

    def __init__(self, uid, birth=Null, username=Null, discriminator=Null, phone=Null, accent_color=Null, premium=Null,
                 avatar=Null, avatar_decoration=Null, banner=Null, banner_color=Null, bio=Null, flags=Null, public_flags=Null):
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

class UserId(_User):
    def __init__(self, uid):
        self.id = uid

class _Channel:
    def __eq__(self, other):
        return isinstance(other, _Channel) and self.id == other.id

class Channel(_Channel, DBModel):
    FIELDS = ("guild_id", "position", "permission_overwrites", "name", "topic", "nsfw", "bitrate", "user_limit",
              "rate_limit", "recipients", "icon", "owner_id", "application_id", "parent_id", "rtc_region",
              "video_quality_mode", "thread_metadata", "default_auto_archive", "flags")
    ID_FIELD = "id"
    NOT_DB_FIELDS = ("last_message_id",)

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

    async def messages(self, limit=50, before=None, after=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await self._core.getChannelMessages(self, limit, before, after)

class _Message:
    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id

class Message(_Message, DBModel):
    FIELDS = ("channel_id", "author", "content", "edit_timestamp", "attachments", "embeds", "reactions", "pinned",
              "webhook_id", "application_id", "type", "flags", "message_reference", "thread", "components", "sticker_items")
    ID_FIELD = "id"
    NOT_DB_FIELDS = ("nonce",)
    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "reactions": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": []}

    def __init__(self, id, channel_id, author, content=Null, edit_timestamp=Null, attachments=Null, embeds=Null,
                 reactions=Null, pinned=Null, webhook_id=Null, application_id=Null, type=Null, flags=Null,
                 message_reference=Null, thread=Null, components=Null, sticker_items=Null, **kwargs):
        self.id = id
        self.content = content
        self.channel_id = channel_id
        self.author = author
        self.edit_timestamp = edit_timestamp
        self.attachments = attachments
        self.embeds = embeds
        self.reactions = reactions
        self.pinned = pinned
        self.webhook_id = webhook_id
        self.application_id = application_id
        self.type = type
        self.flags = flags
        self.message_reference = message_reference
        self.thread = thread
        self.components = components
        self.sticker_items = sticker_items
        self._core = None

        self.set(**kwargs)

        self._checkNulls()

    @property
    def json(self):
        return self._json()

    async def _json(self):
        author = await self._core.getUserData(UserId(self.author))
        timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.id) / 1000))
        timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        edit_timestamp = None
        if self.edit_timestamp:
            edit_timestamp = datetime.utcfromtimestamp(int(snowflake_timestamp(self.edit_timestamp) / 1000))
            edit_timestamp = edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        mentions = []
        role_mentions = []
        for m in ping_regex.findall(self.content):
            if m.startswith("!"):
                m = m[1:]
            if m.startswith("&"):
                role_mentions.append(m[1:])
            if (mem := await self._core.getUserByChannel(self.channel_id, int(m))):
                mentions.append({
                    "id": m,
                    "username": mem.username,
                    "avatar": mem.avatar,
                    "avatar_decoration": mem.avatar_decoration,
                    "discriminator": str(mem.discriminator).rjust(4, "0"),
                    "public_flags": mem.public_flags
                })
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
            "attachments": self.attachments, # TODO: parse attachments
            "embeds": self.embeds, # TODO: parse embeds
            "mentions": mentions,
            "mention_roles": role_mentions,
            "pinned": self.pinned,
            "mention_everyone": "@everyone" in self.content or "@here" in self.content,
            "tts": False,
            "timestamp": timestamp,
            "edited_timestamp": edit_timestamp,
            "flags": self.flags,
            "components": self.components, # TODO: parse components
        }
        if (nonce := getattr(self, "nonce", None)):
            j["nonce"] = nonce
        return j

class ZlibCompressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data)+self.cObj.flush(Z_FULL_FLUSH)

class Relationship(DBModel):
    FIELDS = ("u1", "u2", "type")

    def __init__(self, u1=Null, u2=Null, type=Null):
        self.u1 = u1
        self.u2 = u2
        self.type = type

        self._checkNulls()