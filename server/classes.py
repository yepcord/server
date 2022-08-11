from datetime import datetime
from .utils import b64encode, b64decode, ChannelType, snowflake_timestamp, Null

class DBModel:
    FIELDS = ()

    def _checkNulls(self):
        args = list(self.__init__.__code__.co_varnames)
        args.remove("self")
        for arg in args:
            if getattr(self, arg) == Null:
                delattr(self, arg)

    def to_json(self):
        j = {}
        for k in self.FIELDS:
            if (v := getattr(self, k, Null)) == Null:
                continue
            j[k] = v
        return j

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

class User(_User):
    def __init__(self, uid, email=None, core=None):
        self.id = uid
        self.email = email
        self._core = core
        self._uSettings = None
        self._uData = None

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

    def to_json(self, mfa_key=False):
        j = super().to_json()
        if not mfa_key:
            return j
        if "mfa" in j:
            j["mfa"] = self.mfa_key
        return j

class UserData(DBModel):
    FIELDS = ("uid", "birth", "username", "discriminator", "phone", "premium", "accent_color", "avatar", "avatar_decoration",
              "banner", "banner_color", "bio", "flags", "public_flags")

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

class DMChannel(_Channel):
    def __init__(self, cid, recipients, core):
        self.id = cid
        self.type = ChannelType.DM
        self.recipients = recipients
        self._core = core

    @property
    def info(self):
        return self._info()

    async def messages(self, limit=50, before=None, after=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await self._core.getChannelMessages(self, limit)

    async def _info(self):
        return await self._core.getChannelInfo(self)

class _Message:
    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id

class Message(_Message):
    def __init__(self, mid, content, channel_id, author, edit=None, attachments=[], embeds=[], reactions=[], pinned=False, webhook=None, application=None, mtype=0, flags=0, reference=None, thread=None, components=[], core=None):
        self.id = mid
        self.content = content
        self.channel_id = channel_id
        self.author = author
        self.edit = edit
        self.attachments = attachments
        self.embeds = embeds
        self.reactions = reactions
        self.pinned = pinned
        self.webhook = webhook
        self.application = application
        self.type = mtype
        self.flags = flags
        self.reference = reference
        self.thread = thread
        self.components = components
        self._core = core

    @property
    def json(self):
        return self._json()

    async def _json(self):
        author = await self._core.getUserData(UserId(self.author))
        d = datetime.utcfromtimestamp(int(snowflake_timestamp(self.id) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        e = datetime.utcfromtimestamp(int(snowflake_timestamp(self.edit) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00") if self.edit else None
        return {
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
            "mentions": [], # TODO: parse mentions
            "mention_roles": [], # TODO: parse mention_roles
            "pinned": self.pinned,
            "mention_everyone": False, # TODO: parse mention_everyone
            "tts": False,
            "timestamp": d,
            "edited_timestamp": e,
            "flags": self.flags,
            "components": self.components, # TODO: parse components
        }