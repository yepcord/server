from datetime import datetime
from time import mktime
from zlib import compressobj, Z_FULL_FLUSH
from .errors import EmbedException
from .utils import b64encode, b64decode, snowflake_timestamp, ping_regex, result_to_json
from dateutil.parser import parse as dparse


class _Null:
    pass


Null = _Null()


class DBModel:
    FIELDS = ()
    ID_FIELD = None
    ALLOWED_FIELDS = ()
    DEFAULTS = {}
    TYPES = {}
    DB_FIELDS = {}

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

    def _typed(self, value, T):
        if isinstance(T, type):
            return T(value)
        elif isinstance(T, dict):
            value = dict(value)
            v = {}
            for key in [k for k in value.keys() if k in T.keys()]:
                v[key] = self._typed(value[key], T.get(key))
            return v
        elif isinstance(T, tuple):
            if "nullable" in T and not value:
                return None
            return self._typed(value, T[0])
        return value

    def to_typed_json(self, **json_args):
        json = self.to_json(**json_args)
        for key in json.keys():
            json[key] = self._typed(json[key], self.TYPES.get(key))
        return json

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
        for k,v in kwargs.items():
            if k not in list(self.FIELDS) + list(self.ALLOWED_FIELDS):
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
    TYPES = {"uid": int, "sid": int, "sig": str}

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
    DB_FIELDS = {"custom_status": "j_custom_status", "activity_restricted_guild_ids": "j_activity_restricted_guild_ids",
                 "friend_source_flags": "j_friend_source_flags", "guild_positions": "j_guild_positions",
                 "guild_folders": "j_guild_folders", "restricted_guilds": "j_restricted_guilds"}
    TYPES = {"custom_status": (dict, "nullable",), "friend_source_flags": {"all": bool, "mutual_friends": bool, "mutual_guilds": bool}}

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
                 personalization=Null, usage_statistics=Null, **kwargs):
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
        self.custom_status = custom_status if custom_status else None
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
    TYPES = {"phone": (str, "nullable",), "premium": (bool, "nullable",), "accent_color": (int, "nullable",),
             "avatar": (str, "nullable",), "avatar_decoration": (str, "nullable",), "banner": (str, "nullable",),
             "banner_color": (int, "nullable",)}

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
    id = None
    def __eq__(self, other):
        return isinstance(other, _Channel) and self.id == other.id


class ChannelId(_Channel):
    def __init__(self, cid):
        self.id = cid


class Channel(_Channel, DBModel):
    FIELDS = ("guild_id", "position", "permission_overwrites", "name", "topic", "nsfw", "bitrate", "user_limit",
              "rate_limit", "recipients", "icon", "owner_id", "application_id", "parent_id", "rtc_region",
              "video_quality_mode", "thread_metadata", "default_auto_archive", "flags")
    ID_FIELD = "id"
    ALLOWED_FIELDS = ("last_message_id",)
    DB_FIELDS = {"permission_overwrites": "j_permission_overwrites", "recipients": "j_recipients",
                 "thread_metadata": "j_thread_metadata"}
    TYPES = {"guild_id": (int, "nullable",), "position": (int, "nullable",), "j_permission_overwrites": (list, "nullable",),
             "name": (str, "nullable",), "topic": (str, "nullable",), "nsfw": (bool, "nullable",),
             "bitrate": (int, "nullable",), "user_limit": (int, "nullable",), "rate_limit": (int, "nullable",),
             "j_recipients": (list, "nullable",), "icon": (str, "nullable",), "owner_id": (int, "nullable",),
             "application_id": (int, "nullable",), "parent_id": (int, "nullable",), "rtc_region": (str, "nullable",),
             "video_quality_mode": (int, "nullable",), "j_thread_metadata": (dict, "nullable",),
             "default_auto_archive": (int, "nullable",), "flags": (int, "nullable",)}

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
    id = None
    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id


class Message(_Message, DBModel):
    FIELDS = ("channel_id", "author", "content", "edit_timestamp", "attachments", "embeds", "reactions", "pinned",
              "webhook_id", "application_id", "type", "flags", "message_reference", "thread", "components", "sticker_items")
    ID_FIELD = "id"
    ALLOWED_FIELDS = ("nonce",)
    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "reactions": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": []}
    TYPES = {"content": (str, "nullable",), "edit_timestamp": (int, "nullable",), "attachments": list, "embeds": list,
             "reactions": list, "pinned": bool,"webhook_id": (int, "nullable",), "application_id": (int, "nullable",),
             "type": int, "flags": int, "message_reference": (int, "nullable",),"thread": (int, "nullable",),
             "components": list, "sticker_items": list}
    DB_FIELDS = {"attachments": "j_attachments", "embeds": "j_embeds", "reactions": "j_reactions", "components": "j_components",
                 "sticker_items": "j_sticker_items"}

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
        self._checkEmbeds()

    def _checkEmbedImage(self, image, idx):
        if (url := image.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
            raise EmbedException(24, {"embed_index": idx, "scheme": scheme})
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

    def _formatEmbedError(self, code, path=None, replace={}):
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
            for k,v in replace.items():
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
            raise EmbedException(28)
        if type(self.embeds) != list:
            delattr(self, "embeds")
            return
        for idx, embed in enumerate(self.embeds):
            if type(embed) != dict:
                delattr(self, "embeds")
                return
            if not embed.get("title"):
                raise EmbedException(self._formatEmbedError(23, f"{idx}"))
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
                raise EmbedException(self._formatEmbedError(27, f"{idx}.title", {"length": "256"}))
            if (desc := embed.get("description")):
                embed["description"] = str(desc)
                if len(str(desc)) > 2048:
                    raise EmbedException(self._formatEmbedError(27, f"{idx}.description", {"length": "2048"}))
            if (url := embed.get("url")):
                url = str(url)
                embed["url"] = url
                if (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedException(self._formatEmbedError(24, f"{idx}.url", {"scheme": scheme}))
            if (ts := embed.get("timestamp")):
                ts = str(ts)
                embed["timestamp"] = ts
                try:
                    ts = mktime(dparse(ts).timetuple())
                except ValueError:
                    raise EmbedException(self._formatEmbedError(25, f"{idx}.timestamp", {"value": ts}))
            try:
                if (color := embed.get("color")):
                    color = int(color)
                    if color > 0xffffff or color < 0:
                        raise EmbedException(self._formatEmbedError(26, f"{idx}.color"))
            except ValueError:
                del self.embeds[idx]["color"]
            if (footer := embed.get("footer")):
                if not footer.get("text"):
                    del self.embeds[idx]["footer"]
                else:
                    if len(footer.get("text")) > 2048:
                        raise EmbedException(self._formatEmbedError(27, f"{idx}.footer.text", {"length": "2048"}))
                    if (url := footer.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedException(self._formatEmbedError(24, f"{idx}.footer.icon_url", {"scheme": scheme}))
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
                        raise EmbedException(self._formatEmbedError(27, f"{idx}.author.name", {"length": "256"}))
                    if (url := author.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedException(self._formatEmbedError(24, f"{idx}.author.url", {"scheme": scheme}))
                    if (url := author.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedException(self._formatEmbedError(24, f"{idx}.author.icon_url", {"scheme": scheme}))
                    if author.get("proxy_icon_url"):  # Not supported
                        del author["proxy_icon_url"]
            if (fields := embed.get("fields")):
                embed["fields"] = fields = fields[:25]
                for fidx, field in enumerate(fields):
                    if not (name := field.get("name")):
                        raise EmbedException(self._formatEmbedError(23, f"{idx}.fields.{fidx}.name"))
                    if len(name) > 256:
                        raise EmbedException(self._formatEmbedError(27, f"{idx}.fields.{fidx}.name", {"length": "256"}))
                    if not (value := field.get("value")):
                        raise EmbedException(self._formatEmbedError(23, f"{idx}.fields.{fidx}.value"))
                    if len(value) > 1024:
                        raise EmbedException(self._formatEmbedError(27, f"{idx}.fields.{fidx}.value", {"length": "1024"}))
                    if not field.get("inline"):
                        field["inline"] = False


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


class ReadState(DBModel):
    FIELDS = ("channel_id", "last_read_id", "count",)
    ID_FIELD = "uid"

    def __init__(self, uid, channel_id, last_read_id, count=Null):
        self.uid = uid
        self.channel_id = channel_id
        self.count = count
        self.last_read_id = last_read_id
        self._core = None

        self._checkNulls()


class UserNote(DBModel):
    FIELDS = ("uid", "target_uid", "note",)

    def __init__(self, uid, target_uid, note):
        self.uid = uid
        self.target_uid = target_uid
        self.note = note

        self._checkNulls()

    def to_response(self):
        return {
            "note": self.note,
            "user_id": str(self.uid),
            "note_user_id": str(self.target_uid)
        }


class UserConnection(DBModel):
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
