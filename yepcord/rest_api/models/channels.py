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

from __future__ import annotations

from time import mktime
from typing import Optional

from dateutil.parser import parse as dparse
from pydantic import BaseModel, Field, field_validator

from ..utils import makeEmbedError
from ...yepcord.models import Channel, Message
from ...yepcord.enums import ChannelType
from ...yepcord.errors import EmbedErr, InvalidDataErr, Errors
from ...yepcord.utils import validImage, getImage


# noinspection PyMethodParameters
class ChannelUpdate(BaseModel):
    icon: Optional[str] = ""  # Only for GROUP_DM channel
    owner_id: Optional[int] = None  # Only for GROUP_DM channel
    name: Optional[str] = None  # For any channel (except DM)
    # For guild channels:
    type: Optional[int] = None
    position: Optional[int] = None
    topic: Optional[str] = None
    nsfw: Optional[bool] = None
    rate_limit: Optional[int] = Field(default=None, alias="rate_limit_per_user")
    bitrate: Optional[int] = None
    user_limit: Optional[int] = None
    #permission_overwrites: List[PermissionOverwriteModel] = []
    parent_id: Optional[int] = None
    #rtc_region: Optional[str] = None
    video_quality_mode: Optional[int] = None
    default_auto_archive: Optional[int] = Field(default=None, alias="default_auto_archive_duration")
    flags: Optional[int] = None
    # Only for threads:
    auto_archive_duration: Optional[int] = None
    locked: Optional[bool] = None
    invitable: Optional[bool] = None

    class Config:
        populate_by_name = True

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value[:100]
        return value

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value is not None:
            if not (img := getImage(value)) or not validImage(img):
                value = None
        return value

    @field_validator("topic")
    def validate_topic(cls, value: Optional[str]):
        if value is not None:
            value = value[:1024]
        return value

    @field_validator("rate_limit")
    def validate_rate_limit(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 21600: value = 21600
        return value

    @field_validator("bitrate")
    def validate_bitrate(cls, value: Optional[int]):
        if value is not None:
            if value < 8000: value = 8000
        return value

    @field_validator("user_limit")
    def validate_user_limit(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 99: value = 99
        return value

    @field_validator("video_quality_mode")
    def validate_video_quality_mode(cls, value: Optional[int]):
        if value is not None:
            if value not in (0, 1): value = None
        return value

    @field_validator("default_auto_archive", "auto_archive_duration")
    def validate_auto_archive(cls, value: Optional[int]):
        ALLOWED_DURATIONS = (60, 1440, 4320, 10080)
        if value is not None:
            if value not in ALLOWED_DURATIONS:
                value = min(ALLOWED_DURATIONS, key=lambda x: abs(x - value))  # Take closest
        return value

    def to_json(self, channel_type: int) -> dict:
        if channel_type == ChannelType.GROUP_DM:
            return self.model_dump(include={"name", "icon", "owner_id"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_CATEGORY:
            return self.model_dump(include={"name", "position"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_TEXT:
            return self.model_dump(
                # TODO: add `type` when GUILD_NEWS channels will be added
                include={"name", "position", "topic", "nsfw", "rate_limit", "parent_id", "default_auto_archive"},
                exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_VOICE:
            return self.model_dump(include={"name", "position", "nsfw", "bitrate", "user_limit", "parent_id",
                                            "video_quality_mode"}, exclude_defaults=True)


class PermissionOverwriteModel(BaseModel):
    id: int
    type: int
    allow: int
    deny: int

    def model_dump(self, *args, **kwargs) -> dict:
        kwargs["include"] = {"type", "allow", "deny"}
        return super().model_dump(*args, **kwargs)


# noinspection PyMethodParameters
class EmbedFooter(BaseModel):
    text: Optional[str] = None
    icon_url: Optional[str] = None

    @field_validator("text")
    def validate_text(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 2048:
                raise EmbedErr(makeEmbedError(27, f"footer.text", {"length": "2048"}))
        return value

    @field_validator("icon_url")
    def validate_icon_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"footer.icon_url", {"scheme": scheme}))
        return value

    def model_dump(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().model_dump(*args, **kwargs)


# noinspection PyMethodParameters
class EmbedImage(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    @field_validator("url")
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    def model_dump(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().model_dump(*args, **kwargs)


# noinspection PyMethodParameters
class EmbedAuthor(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    icon_url: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 256:
                raise EmbedErr(makeEmbedError(27, f"author.name", {"length": "256"}))
        return value

    @field_validator("url", "icon_url")
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    def model_dump(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().model_dump(*args, **kwargs)


# noinspection PyMethodParameters
class EmbedField(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if not value:
            raise EmbedErr(makeEmbedError(23, f"fields.name"))
        if len(value) > 256:
            raise EmbedErr(makeEmbedError(27, f"fields.name", {"length": "256"}))
        return value

    @field_validator("value")
    def validate_value(cls, value: Optional[str]):
        if not value:
            raise EmbedErr(makeEmbedError(23, f"fields.value"))
        if len(value) > 1024:
            raise EmbedErr(makeEmbedError(27, f"fields.value", {"length": "1024"}))
        return value


# noinspection PyMethodParameters
class EmbedModel(BaseModel):
    title: str
    type: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    color: Optional[int] = None
    footer: Optional[EmbedFooter] = None
    image: Optional[EmbedImage] = None
    thumbnail: Optional[EmbedImage] = None
    video: Optional[EmbedImage] = None
    author: Optional[EmbedAuthor] = None
    fields: list[EmbedField] = Field(default_factory=list)

    @field_validator("title")
    def validate_title(cls, value: str):
        if not value: raise EmbedErr(makeEmbedError(23))
        if len(value) > 256:
            raise EmbedErr(makeEmbedError(27, f"title", {"length": "256"}))
        return value

    @field_validator("type")
    def validate_type(cls, value: Optional[str]):
        return "rich"

    @field_validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 4096:
                raise EmbedErr(makeEmbedError(27, f"description", {"length": "4096"}))
        return value

    @field_validator("url")
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    @field_validator("timestamp")
    def validate_timestamp(cls, value: Optional[str]):
        if value is not None:
            try:
                mktime(dparse(value).timetuple())
            except ValueError:
                raise EmbedErr(makeEmbedError(25, f"timestamp", {"value": value}))
        return value

    @field_validator("color")
    def validate_color(cls, value: Optional[int]):
        if value is not None:
            if value > 0xffffff or value < 0:
                raise EmbedErr(makeEmbedError(26, f"color"))
        return value

    @field_validator("footer")
    def validate_footer(cls, value: Optional[EmbedFooter]):
        if value is not None:
            if not value.text:
                value = None
        return value

    @field_validator("image", "thumbnail", "video")
    def validate_image(cls, value: Optional[EmbedImage]):
        if value is not None:
            if not value.url:
                value = None
        return value

    @field_validator("author")
    def validate_author(cls, value: Optional[EmbedAuthor]):
        if value is not None:
            if not value.name:
                value = None
        return value

    @field_validator("fields")
    def validate_fields(cls, value: list[EmbedField]):
        if len(value) > 25:
            value = value[:25]
        return value

    def model_dump(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().model_dump(*args, **kwargs)


class MessageReferenceModel(BaseModel):
    message_id: Optional[int] = None
    channel_id: Optional[int] = None
    guild_id: Optional[int] = None
    fail_if_not_exists: Optional[int] = None

    def model_dump(self, *args, **kwargs):
        kwargs["include"] = {"message_id", "channel_id", "guild_id"}
        return super().model_dump(*args, **kwargs)


# noinspection PyMethodParameters
class MessageCreate(BaseModel):
    content: Optional[str] = None
    nonce: Optional[str] = None
    embeds: list[EmbedModel] = Field(default_factory=list)
    sticker_ids: list[int] = Field(default_factory=list)
    message_reference: Optional[MessageReferenceModel] = None
    flags: Optional[int] = None

    @field_validator("content")
    def validate_content(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if len(value) > 2000:
                raise InvalidDataErr(400, Errors.make(50035, {"content": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 1 and 2000 in length."
                }}))
        return value

    @field_validator("embeds")
    def validate_embeds(cls, value: list[EmbedModel]):
        if len(value) > 10:
            raise InvalidDataErr(400, Errors.make(50035, {"embeds": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 1 and 10 in length."
            }}))
        return value

    @field_validator("sticker_ids")
    def validate_sticker_ids(cls, value: list[int]):
        if len(value) > 3:
            raise InvalidDataErr(400, Errors.make(50035, {"sticker_ids": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 1 and 3 in length."
            }}))
        return value

    def validate_reply(self, channel: Channel, reply_to_message: Message):
        if reply_to_message is None:
            if self.message_reference.fail_if_not_exists:
                raise InvalidDataErr(400, Errors.make(50035, {"message_reference": {
                    "_errors": [{"code": "REPLIES_UNKNOWN_MESSAGE", "message": "Unknown message"}]}}))
            else:
                self.message_reference = None
        else:
            if not self.message_reference.channel_id:
                self.message_reference.channel_id = channel.id
            if not self.message_reference.guild_id:
                self.message_reference.guild_id = channel.guild.id
            if self.message_reference.channel_id != channel.id:
                raise InvalidDataErr(400, Errors.make(50035, {"message_reference": {
                    "_errors": [{"code": "REPLIES_CANNOT_REFERENCE_OTHER_CHANNEL",
                                 "message": "Cannot reply to a message in a different channel"}]}}))
            if self.message_reference.guild_id != channel.guild.id:
                raise InvalidDataErr(400, Errors.make(50035, {"message_reference": {
                    "_errors": [{"code": "REPLIES_UNKNOWN_MESSAGE",
                                 "message": "Unknown message"}]}}))

    def to_json(self) -> dict:
        data = self.model_dump(exclude_defaults=True, exclude={"flags", "sticker_ids"})
        if "message_reference" in data:
            data["message_reference"]["message_id"] = str(data["message_reference"]["message_id"])
            data["message_reference"]["channel_id"] = str(data["message_reference"]["channel_id"])
            if data["message_reference"].get("guild_id"):
                data["message_reference"]["guild_id"] = str(data["message_reference"]["guild_id"])
        return data


# noinspection PyMethodParameters
class MessageUpdate(BaseModel):
    content: Optional[str] = None
    embeds: list[EmbedModel] = Field(default_factory=list)

    @field_validator("content")
    def validate_content(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 2000:
                raise InvalidDataErr(400, Errors.make(50035, {"content": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 1 and 2000 in length."
                }}))
        return value

    def to_json(self) -> dict:
        return self.model_dump(exclude_defaults=True)


class InviteCreate(BaseModel):
    max_age: Optional[int] = 86400
    max_uses: Optional[int] = 0


# noinspection PyMethodParameters
class WebhookCreate(BaseModel):
    name: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {"name": {
                "code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        return value


class SearchQuery(BaseModel):
    author_id: Optional[int] = None
    mentions: Optional[int] = None
    has: Optional[str] = None
    min_id: Optional[int] = None
    max_id: Optional[int] = None
    pinned: Optional[str] = None
    offset: Optional[int] = None
    content: Optional[str] = None


# noinspection PyMethodParameters
class GetMessagesQuery(BaseModel):
    limit: int = 50
    before: int = 0
    after: int = 0

    @field_validator("limit")
    def validate_limit(cls, value: int):
        if value < 0:
            value = 50
        elif value > 100:
            value = 100
        return value


# noinspection PyMethodParameters
class GetReactionsQuery(BaseModel):
    limit: int = 3

    @field_validator("limit")
    def validate_limit(cls, value: int):
        if value < 0:
            value = 3
        elif value > 10:
            value = 10
        return value


class MessageAck(BaseModel):
    manual: bool = False
    mention_count: int = 0


class CreateThread(BaseModel):
    auto_archive_duration: int
    name: str

    @field_validator("auto_archive_duration")
    def validate_auto_archive_duration(cls, value: int) -> int:
        ALLOWED_DURATIONS = (60, 1440, 4320, 10080)
        if value not in ALLOWED_DURATIONS:
            value = min(ALLOWED_DURATIONS, key=lambda x: abs(x - value))  # Take closest
        return value


class CommandsSearchQS(BaseModel):
    type: int = 1
    limit: int = 10
    query: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z]+$")
    include_applications: bool = False
    cursor: Optional[str] = None

    @field_validator("type")
    def validate_type(cls, value: int) -> int:
        if value not in {1, 2, 3}:
            raise InvalidDataErr(400, Errors.make(50035, {"type": {
                "code": "ENUM_TYPE_COERCE", "message": f"Value \"{value}\" is not a valid enum value."
            }}))
        return value

    @field_validator("limit")
    def validate_limit(cls, value: int) -> int:
        if value > 10:
            value = 10
        return value
