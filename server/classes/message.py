# All 'Message' classes (Message, etc.)
from dataclasses import dataclass
from time import mktime
from typing import Optional
from uuid import UUID, uuid4

from dateutil.parser import parse as dparse
from pymysql.converters import escape_string
from schema import Or, And

from .user import UserId
from ..config import Config
from ..ctx import getCore, Ctx
from ..enums import MessageType
from ..errors import EmbedErr, InvalidDataErr
from ..model import Model, field, model
from ..snowflake import Snowflake
from ..utils import NoneType
from ..utils import ping_regex


class _Message:
    id = None

    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id


@model
@dataclass
class Message(_Message, Model):
    id: int = field(id_field=True)
    channel_id: int = field()
    author: int = field()
    content: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    edit_timestamp: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    embeds: Optional[list] = field(db_name="j_embeds", default=None)
    pinned: Optional[bool] = False
    webhook_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    application_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    type: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    flags: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    message_reference: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    thread: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    components: Optional[list] = field(db_name="j_components", default=None)
    sticker_items: Optional[list] = field(db_name="j_sticker_items", default=None)
    extra_data: Optional[dict] = field(db_name="j_extra_data", default=None, private=True)
    guild_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    nonce: Optional[str] = field(default=None, excluded=True)
    tts: Optional[str] = field(default=None, excluded=True)
    sticker_ids: Optional[str] = field(default=None, excluded=True)
    webhook_author: Optional[dict] = field(db_name="j_webhook_author", default=None, private=True)

    @property
    async def json(self) -> dict:
        data = self.toJSON(for_db=False, with_private=False)
        data["id"] = str(data["id"])
        data["channel_id"] = str(data["channel_id"])
        if data.get("guild_id"): data["guild_id"] = str(data["guild_id"])
        if self.author != 0:
            data["author"] = await (await getCore().getUserData(UserId(self.author))).json
        else:
            data["author"] = self.webhook_author
        data["mention_everyone"] = ("@everyone" in self.content or "@here" in self.content) if self.content else None
        data["tts"] = False
        data["timestamp"] = Snowflake.toDatetime(self.id).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        if self.edit_timestamp:
            data["edit_timestamp"] = Snowflake.toDatetime(self.edit_timestamp).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        data["mentions"] = []
        data["mention_roles"] = []
        data["attachments"] = []
        if self.content:
            for ping in ping_regex.findall(self.content):
                if ping.startswith("!"):
                    ping = ping[1:]
                if ping.startswith("&"):
                    data["mention_roles"].append(ping[1:])
                    continue
                if member := await getCore().getUserByChannelId(self.channel_id, int(ping)):
                    mdata = await member.data
                    data["mentions"].append(await mdata.json)
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if user := self.extra_data.get("user"):
                user = await getCore().getUserData(UserId(user))
                data["mentions"].append(await user.json)
        data["attachments"] = [await attachment.json for attachment in await getCore().getAttachments(self)]
        if self.message_reference:
            data["message_reference"] = {"message_id": str(self.message_reference), "channel_id": str(self.channel_id)}
        if self.nonce is not None:
            data["nonce"] = self.nonce
        if not Ctx.get("search", False):
            if reactions := await getCore().getMessageReactions(self.id, Ctx.get("user_id", 0)):
                data["reactions"] = reactions
        return data

    DEFAULTS = {"content": None, "edit_timestamp": None, "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": [], "extra_data": {},
                "guild_id": None}  # TODO: remove or replace with mode convenient solution

    def __post_init__(self) -> None:
        if self.embeds is None: self.embeds = []
        if self.components is None: self.components = []
        if self.sticker_items is None: self.sticker_items = []
        if self.extra_data is None: self.extra_data = {}
        super().__post_init__()

    def fill_defaults(self):  # TODO: remove or replace with mode convenient solution
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    async def check(self):
        self.embeds = Embeds(self.embeds).json
        if self.embeds is None:
            self.embeds = []


@model
@dataclass
class ReadState(Model):
    uid: int
    channel_id: int
    count: int
    last_read_id: int


@model
@dataclass
class Attachment(Model):
    id: int = field(id_field=True)
    channel_id: int = field()
    message_id: int = field()
    filename: str = field()
    size: int = field()
    metadata: dict = field()
    uuid: Optional[str] = field(default=None, nullable=True)
    content_type: Optional[str] = field(default=None, nullable=True)
    uploaded: bool = False

    def __post_init__(self) -> None:
        if not self.uuid: self.uuid = str(uuid4())

    @property
    async def json(self) -> dict:
        data = {
            "filename": self.filename,
            "id": str(self.id),
            "size": self.size,
            "url": f"https://{Config('CDN_HOST')}/attachments/{self.channel_id}/{self.id}/{self.filename}"
        }
        if self.content_type:
            data["content_type"] = self.content_type
        if self.metadata:
            data.update(self.metadata)
        return data


@model
@dataclass
class Reaction(Model):
    message_id: int
    user_id: int
    emoji_id: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    emoji_name: Optional[str] = field(default=None, nullable=True)


@model
@dataclass
class SearchFilter(Model):
    author_id: Optional[int] = None
    sort_by: Optional[str] = field(default=None, validation=And(lambda s: s in ("id",)))
    sort_order: Optional[str] = field(default=None, validation=And(lambda s: s in ("asc", "desc")))
    mentions: Optional[int] = None
    has: Optional[str] = field(default=None, validation=And(
        lambda s: s in ("link", "video", "file", "embed", "image", "sound", "sticker")))
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    pinned: Optional[str] = field(default=None, validation=And(lambda s: s in ("true", "false")))
    offset: Optional[int] = None
    content: Optional[str] = None

    _HAS = {
        "link": "`content` REGEXP '(http|https):\\\\/\\\\/[a-zA-Z0-9-_]{1,63}\\\\.[a-zA-Z]{1,63}'",
        "image": "true in (select content_type LIKE '%image/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "video": "true in (select content_type LIKE '%video/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        "file": "JSON_LENGTH(`j_attachments`) > 0",
        "embed": "JSON_LENGTH(`j_embeds`) > 0",
        "sound": "true in (select content_type LIKE '%audio/%' from attachments where JSON_CONTAINS(messages.j_attachments, attachments.id, '$'))",
        # "sticker": "" # TODO
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


class Embeds:
    def __init__(self, data: list):
        self.data = data
        self._total_text_length = 0

    @staticmethod
    def makeError(code, path=None, replaces=None):
        if replaces is None: replaces = {}
        base_error = {"code": 50035, "errors": {"embeds": {}}, "message": "Invalid Form Body"}

        def insertError(error):
            errors = base_error["errors"]["embeds"]
            if path is None:
                errors["_errors"] = error
                return
            for el in path.split("."):
                errors[el] = {}
                errors = errors[el]
            errors["_errors"] = error

        if code == 23:
            insertError([{"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}])
            return base_error
        elif code == 24:
            m = "Scheme \"%SCHEME%\" is not supported. Scheme must be one of ('http', 'https')."
            for k, v in replaces.items():
                m = m.replace(f"%{k.upper()}%", v)
            insertError([{"code": "URL_TYPE_INVALID_SCHEME", "message": m}])
            return base_error
        elif code == 25:
            m = "Could not parse %VALUE%. Should be ISO8601."
            for k, v in replaces.items():
                m = m.replace(f"%{k.upper()}%", v)
            insertError([{"code": "DATE_TIME_TYPE_PARSE", "message": m}])
            return base_error
        elif code == 26:
            insertError([{"code": "NUMBER_TYPE_MAX", "message": "int value should be <= 16777215 and >= 0."}])
            return base_error
        elif code == 27:
            m = "Must be %LENGTH% or fewer in length."
            for k, v in replaces.items():
                m = m.replace(f"%{k.upper()}%", v)
            insertError([{"code": "BASE_TYPE_MAX_LENGTH", "message": m}])
            return base_error
        elif code == 28:
            insertError([{"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or fewer in length."}])
            return base_error

    def delOptionalFields(self, index: int) -> None:
        """
        Removes non-required fields in embed with given index if field is empty
        :param index:
        :return:
        """
        fields = ["description", "url", "timestamp", "color", "footer", "image", "thumbnail", "video", "provider",
                  "author"]
        data = self.data[index]
        for field in fields:
            if (v := data.get(field)) and not bool(v):
                del data[field]

    def validateTitle(self, idx: int, embed: dict) -> None:
        self._total_text_length += (title_len := len(embed.get("title")))
        if title_len > 256:
            raise EmbedErr(self.makeError(27, f"{idx}.title", {"length": "256"}))

    def validateDescription(self, idx: int, embed: dict) -> None:
        if desc := embed.get("description"):
            embed["description"] = str(desc)
            self._total_text_length += (description_len := len(desc))
            if description_len > 4096:
                raise EmbedErr(self.makeError(27, f"{idx}.description", {"length": "2048"}))

    def validateUrl(self, idx: int, embed: dict) -> None:
        if url := embed.get("url"):
            url = str(url)
            embed["url"] = url
            if (scheme := url.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(self.makeError(24, f"{idx}.url", {"scheme": scheme}))

    def validateTimestamp(self, idx: int, embed: dict) -> None:
        if ts := embed.get("timestamp"):
            ts = str(ts)
            embed["timestamp"] = ts
            try:
                ts = mktime(dparse(ts).timetuple())
            except ValueError:
                raise EmbedErr(self.makeError(25, f"{idx}.timestamp", {"value": ts}))

    def validateColor(self, idx: int, embed: dict) -> None:
        try:
            if color := embed.get("color"):
                color = int(color)
                if color > 0xffffff or color < 0:
                    raise EmbedErr(self.makeError(26, f"{idx}.color"))
        except ValueError:
            del embed["color"]

    def validateFooter(self, idx: int, embed: dict) -> None:
        if footer := embed.get("footer"):
            if not footer.get("text"):
                del embed["footer"]
            else:
                self._total_text_length += (footer_len := len(footer.get("text")))
                if footer_len > 2048:
                    raise EmbedErr(self.makeError(27, f"{idx}.footer.text", {"length": "2048"}))
                if (url := footer.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedErr(self.makeError(24, f"{idx}.footer.icon_url", {"scheme": scheme}))
                if footer.get("proxy_icon_url"): del footer["proxy_icon_url"]  # Not supported

    def validateImageField(self, image: dict, idx: int):
        if (url := image.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
            raise EmbedErr(self.makeError(24, f"{idx}.image.url", {"embed_index": idx, "scheme": scheme}))
        if image.get("proxy_url"): del image["proxy_url"]  # Not supported
        if width := image.get("width"):
            try:
                image["width"] = int(width)
            except ValueError:
                del image["width"]
        if height := image.get("height"):
            try:
                image["height"] = int(height)
            except ValueError:
                del image["height"]

    def validateImage(self, idx: int, embed: dict) -> None:
        if image := embed.get("image"):
            if not image.get("url"):
                del embed["image"]
            else:
                self.validateImageField(image, idx)

    def validateThumbnail(self, idx: int, embed: dict) -> None:
        if thumbnail := embed.get("thumbnail"):
            if not thumbnail.get("url"):
                del embed["thumbnail"]
            else:
                self.validateImageField(thumbnail, idx)

    def validateVideo(self, idx: int, embed: dict) -> None:
        if video := embed.get("video"):
            if not video.get("url"):
                del embed["video"]
            else:
                self.validateImageField(video, idx)

    def validateProvider(self, idx: int, embed: dict) -> None:
        if embed.get("provider"): del embed["provider"]  # Not supported

    def validateAuthor(self, idx: int, embed: dict) -> None:
        if author := embed.get("author"):
            if not (name := author.get("name")):
                del embed["author"]
            else:
                if len(name) > 256:
                    raise EmbedErr(self.makeError(27, f"{idx}.author.name", {"length": "256"}))
                if (url := author.get("url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedErr(self.makeError(24, f"{idx}.author.url", {"scheme": scheme}))
                if (url := author.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedErr(self.makeError(24, f"{idx}.author.icon_url", {"scheme": scheme}))
                if author.get("proxy_icon_url"): del author["proxy_icon_url"]  # Not supported

    def validateFields(self, idx: int, embed: dict) -> None:
        if fields := embed.get("fields"):
            embed["fields"] = fields = fields[:25]
            for fidx, field in enumerate(fields):
                if not (name := field.get("name")):
                    raise EmbedErr(self.makeError(23, f"{idx}.fields.{fidx}.name"))
                self._total_text_length += (name_len := len(name))
                if name_len > 256:
                    raise EmbedErr(self.makeError(27, f"{idx}.fields.{fidx}.name", {"length": "256"}))

                if not (value := field.get("value")):
                    raise EmbedErr(self.makeError(23, f"{idx}.fields.{fidx}.value"))
                self._total_text_length += (value_len := len(value))
                if value_len > 1024:
                    raise EmbedErr(self.makeError(27, f"{idx}.fields.{fidx}.value", {"length": "1024"}))
                if not field.get("inline"): field["inline"] = False

    @property
    def json(self) -> Optional[list]:
        if not self.data:
            return
        if len(self.data) > 10:
            raise EmbedErr(self.makeError(28))
        if not isinstance(self.data, list):
            return
        for idx, embed in enumerate(self.data):
            if not isinstance(embed, dict):
                return
            if not embed.get("title"):
                raise EmbedErr(self.makeError(23, f"{idx}"))
            embed["type"] = "rich"  # Single supported embed type now
            embed["title"] = str(embed["title"])
            self.delOptionalFields(idx)
            self.validateTitle(idx, embed)
            self.validateDescription(idx, embed)
            self.validateUrl(idx, embed)
            self.validateTimestamp(idx, embed)
            self.validateColor(idx, embed)
            self.validateFooter(idx, embed)
            self.validateImage(idx, embed)
            self.validateVideo(idx, embed)
            self.validateProvider(idx, embed)
            self.validateAuthor(idx, embed)
            self.validateFields(idx, embed)
            if self._total_text_length > 6000:
                raise EmbedErr(self.makeError(27, replaces={"length": "6000"}))

        return self.data
