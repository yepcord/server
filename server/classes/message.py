# All 'Message' classes (Message, etc.)
from dataclasses import dataclass
from datetime import datetime
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
from ..utils import NoneType
from ..utils import mkError, sf_ts, ping_regex


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
    attachments: Optional[list] = field(db_name="j_attachments", default=None)
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

    @property
    async def json(self) -> dict:
        data = self.toJSON(for_db=False, with_private=False)
        data["id"] = str(data["id"])
        data["channel_id"] = str(data["channel_id"])
        if data.get("guild_id"): data["guild_id"] = str(data["guild_id"])
        data["author"] = await (await getCore().getUserData(UserId(self.author))).json
        data["mention_everyone"] = ("@everyone" in self.content or "@here" in self.content) if self.content else None
        data["tts"] = False
        timestamp = datetime.utcfromtimestamp(int(sf_ts(self.id) / 1000))
        data["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        if self.edit_timestamp:
            edit_timestamp = datetime.utcfromtimestamp(int(sf_ts(self.edit_timestamp) / 1000))
            data["edit_timestamp"] = edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        data["mentions"] = []
        data["mention_roles"] = []
        data["attachments"] = []
        if self.content:
            for ping in ping_regex.findall(self.content):
                if ping.startswith("!"):
                    ping = ping[1:]
                if ping.startswith("&"):
                    data["mention_roles"].append(ping[1:])
                if member := await getCore().getUserByChannelId(self.channel_id, int(ping)):
                    mdata = await member.data
                    data["mentions"].append(await mdata.json)
        if self.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
            if user := self.extra_data.get("user"):
                user = await getCore().getUserData(UserId(user))
                data["mentions"].append(await user.json)
        for att in self.attachments:
            att = await getCore().getAttachment(att)
            data["attachments"].append({
                "filename": att.filename,
                "id": str(att.id),
                "size": att.size,
                "url": f"https://{Config('CDN_HOST')}/attachments/{self.channel_id}/{att.id}/{att.filename}"
            })
            if att.get("content_type"):
                data["attachments"][-1]["content_type"] = att.get("content_type")
            if att.get("metadata"):
                data["attachments"][-1].update(att.metadata)
        if self.message_reference:
            data["message_reference"] = {"message_id": str(self.message_reference), "channel_id": str(self.channel_id)}
        if self.nonce is not None:
            data["nonce"] = self.nonce
        if not Ctx.get("search", False):
            if reactions := await getCore().getMessageReactions(self.id, Ctx.get("user_id", 0)):
                data["reactions"] = reactions
        return data

    DEFAULTS = {"content": None, "edit_timestamp": None, "attachments": [], "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": None,
                "thread": None, "components": [], "sticker_items": [], "extra_data": {}, "guild_id": None} # TODO: remove or replace with mode convenient solution

    def __post_init__(self) -> None:
        if self.attachments is None: self.attachments = []
        if self.embeds is None: self.embeds = []
        if self.components is None: self.components = []
        if self.sticker_items is None: self.sticker_items = []
        if self.extra_data is None: self.extra_data = {}
        super().__post_init__()

    def fill_defaults(self): # TODO: remove or replace with mode convenient solution
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self

    async def check(self):
        self._checkEmbeds()
        await self._checkAttachments()

    def _checkEmbedImage(self, image, idx): # TODO: move to different class
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

    def _formatEmbedError(self, code, path=None, replace=None): # TODO: move to different class
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
            if desc := embed.get("description"):
                embed["description"] = str(desc)
                if len(str(desc)) > 2048:
                    raise EmbedErr(self._formatEmbedError(27, f"{idx}.description", {"length": "2048"}))
            if url := embed.get("url"):
                url = str(url)
                embed["url"] = url
                if (scheme := url.split(":")[0]) not in ["http", "https"]:
                    raise EmbedErr(self._formatEmbedError(24, f"{idx}.url", {"scheme": scheme}))
            if ts := embed.get("timestamp"):
                ts = str(ts)
                embed["timestamp"] = ts
                try:
                    ts = mktime(dparse(ts).timetuple())
                except ValueError:
                    raise EmbedErr(self._formatEmbedError(25, f"{idx}.timestamp", {"value": ts}))
            try:
                if color := embed.get("color"):
                    color = int(color)
                    if color > 0xffffff or color < 0:
                        raise EmbedErr(self._formatEmbedError(26, f"{idx}.color"))
            except ValueError:
                del self.embeds[idx]["color"]
            if footer := embed.get("footer"):
                if not footer.get("text"):
                    del self.embeds[idx]["footer"]
                else:
                    if len(footer.get("text")) > 2048:
                        raise EmbedErr(self._formatEmbedError(27, f"{idx}.footer.text", {"length": "2048"}))
                    if (url := footer.get("icon_url")) and (scheme := url.split(":")[0]) not in ["http", "https"]:
                        raise EmbedErr(self._formatEmbedError(24, f"{idx}.footer.icon_url", {"scheme": scheme}))
                    if footer.get("proxy_icon_url"):  # Not supported
                        del footer["proxy_icon_url"]
            if image := embed.get("image"):
                if not image.get("url"):
                    del self.embeds[idx]["image"]
                else:
                    self._checkEmbedImage(image, idx)
            if thumbnail := embed.get("thumbnail"):
                if not thumbnail.get("url"):
                    del self.embeds[idx]["thumbnail"]
                else:
                    self._checkEmbedImage(thumbnail, idx)
            if video := embed.get("video"):
                if not video.get("url"):
                    del self.embeds[idx]["video"]
                else:
                    self._checkEmbedImage(video, idx)
            if embed.get("provider"):
                del self.embeds[idx]["provider"]
            if author := embed.get("author"):
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
            if fields := embed.get("fields"):
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
    filename: str = field()
    size: int = field()
    metadata: dict = field()
    uuid: Optional[str] = field(default=None, nullable=True)
    content_type: Optional[str] = field(default=None, nullable=True)
    uploaded: bool = False

    def __post_init__(self) -> None:
        if not self.uuid: self.uuid = str(uuid4())

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
    has: Optional[str] = field(default=None, validation=And(lambda s: s in ("link", "video", "file", "embed", "image", "sound", "sticker")))
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

