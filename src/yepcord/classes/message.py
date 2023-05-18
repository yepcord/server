"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# All 'Message' classes (Message, etc.)
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from pymysql.converters import escape_string
from schema import Or, And

from .channel import ChannelId
from .user import UserId
from ..config import Config
from ..ctx import getCore, Ctx
from ..enums import MessageType
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
    type: Optional[int] = field(validation=Or(int, NoneType), default=0)
    flags: Optional[int] = field(validation=Or(int, NoneType), default=0)
    message_reference: Optional[dict] = field(db_name="j_message_reference", default=None)
    thread: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    components: Optional[list] = field(db_name="j_components", default=None)
    sticker_items: Optional[list] = field(db_name="j_sticker_items", default=None)
    stickers: Optional[list] = field(db_name="j_stickers", default=None)
    extra_data: Optional[dict] = field(db_name="j_extra_data", default=None, private=True)
    guild_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    nonce: Optional[str] = field(default=None, excluded=True)
    tts: Optional[str] = field(default=None, excluded=True)
    sticker_ids: Optional[list] = field(db_name="j_sticker_ids", default=None, excluded=True)
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
            data["message_reference"] = self.message_reference
            if self.type == MessageType.REPLY:
                referenced_message = await getCore().getMessage(ChannelId(self.channel_id), int(self.message_reference["message_id"]))
                referenced_message.message_reference = {}
                data["referenced_message"] = await referenced_message.json if referenced_message else None
        if self.nonce is not None:
            data["nonce"] = self.nonce
        if not Ctx.get("search", False):
            if reactions := await getCore().getMessageReactions(self.id, Ctx.get("user_id", 0)):
                data["reactions"] = reactions
        return data

    DEFAULTS = {"content": None, "edit_timestamp": None, "embeds": [], "pinned": False,
                "webhook_id": None, "application_id": None, "type": 0, "flags": 0, "message_reference": {},
                "thread": None, "components": [], "sticker_items": [], "sticker_ids": [], "extra_data": {},
                "guild_id": None}

    def __post_init__(self) -> None:
        if self.embeds is None: self.embeds = []
        if self.components is None: self.components = []
        if self.sticker_items is None: self.sticker_items = []
        if self.extra_data is None: self.extra_data = {}
        super().__post_init__()

    def fill_defaults(self):
        for k, v in self.DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        return self


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
        # "sticker": "" # TODO: check message for sticker
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
