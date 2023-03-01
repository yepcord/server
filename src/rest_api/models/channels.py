from __future__ import annotations

from time import mktime
from typing import Optional, List

from dateutil.parser import parse as dparse
from pydantic import BaseModel, validator, Field

from ..utils import makeEmbedError
from ...yepcord.enums import ChannelType
from ...yepcord.errors import EmbedErr, InvalidDataErr, Errors
from ...yepcord.utils import validImage, getImage


class ChannelUpdate(BaseModel):
    icon: Optional[str] = "" # Only for GROUP_DM channel
    owner_id: Optional[int] = Field(default=None, alias="owner") # Only for GROUP_DM channel
    name: Optional[str] = None # For any channel (except DM)
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
        allow_population_by_field_name = True

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value[:100]
        return value

    @validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value is not None:
            if not (img := getImage(value)) or not validImage(img):
                value = None
        return value

    @validator("topic")
    def validate_topic(cls, value: Optional[str]):
        if value is not None:
            value = value[:1024]
        return value

    @validator("rate_limit")
    def validate_rate_limit(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 21600: value = 21600
        return value

    @validator("bitrate")
    def validate_bitrate(cls, value: Optional[int]):
        if value is not None:
            if value < 8000: value = 8000
        return value

    @validator("user_limit")
    def validate_user_limit(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 99: value = 99
        return value

    @validator("video_quality_mode")
    def validate_video_quality_mode(cls, value: Optional[int]):
        if value is not None:
            if value not in (0, 1): value = None
        return value

    @validator("default_auto_archive", allow_reuse=True)
    @validator("auto_archive_duration", allow_reuse=True)
    def validate_video_quality_mode(cls, value: Optional[int]):
        ALLOWED_DURATIONS = (60, 1440, 4320, 10080)
        if value is not None:
            if value not in ALLOWED_DURATIONS:
                value = min(ALLOWED_DURATIONS, key=lambda x: abs(x - value)) # Take closest
        return value

    def to_json(self, channel_type: int) -> dict:
        if channel_type == ChannelType.GROUP_DM:
            return self.dict(include={"name", "icon", "owner_id"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_CATEGORY:
            return self.dict(include={"name", "position"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_TEXT:
            return self.dict(
                # TODO: add `type` when GUILD_NEWS channels will be added
                include={"name", "position", "topic", "nsfw", "rate_limit", "parent_id", "default_auto_archive"},
                exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_VOICE:
            return self.dict(include={"name", "position", "nsfw", "bitrate", "user_limit", "parent_id",
                                      "video_quality_mode"}, exclude_defaults=True)


class PermissionOverwriteModel(BaseModel):
    id: int
    type: int
    allow: int
    deny: int

    def dict(self, *args, **kwargs) -> dict:
        kwargs["include"] = {"type", "allow", "deny"}
        return super().dict(*args, **kwargs)


class EmbedFooter(BaseModel):
    text: Optional[str] = None
    icon_url: Optional[str] = None

    @validator("text")
    def validate_text(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 2048:
                raise EmbedErr(makeEmbedError(27, f"footer.text", {"length": "2048"}))
        return value

    @validator("icon_url")
    def validate_icon_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"footer.icon_url", {"scheme": scheme}))
        return value

    def dict(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().dict(*args, **kwargs)


class EmbedImage(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    @validator("url")
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    def dict(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().dict(*args, **kwargs)


class EmbedAuthor(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    icon_url: Optional[int] = None

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 256:
                raise EmbedErr(makeEmbedError(27, f"author.name", {"length": "256"}))
        return value

    @validator("url", allow_reuse=True)
    @validator("icon_url", allow_reuse=True)
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    def dict(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().dict(*args, **kwargs)


class EmbedField(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if not value:
            raise EmbedErr(makeEmbedError(23, f"fields.name"))
        if len(value) > 256:
            raise EmbedErr(makeEmbedError(27, f"fields.name", {"length": "256"}))

    @validator("value")
    def validate_value(cls, value: Optional[str]):
        if not value:
            raise EmbedErr(makeEmbedError(23, f"fields.value"))
        if len(value) > 1024:
            raise EmbedErr(makeEmbedError(27, f"fields.value", {"length": "1024"}))


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
    fields: List[EmbedField] = Field(default_factory=list)

    @validator("title")
    def validate_title(cls, value: str):
        if not value: raise EmbedErr(makeEmbedError(23))
        if len(value) > 256:
            raise EmbedErr(makeEmbedError(27, f"title", {"length": "256"}))
        return value

    @validator("type")
    def validate_type(cls, value: Optional[str]):
        return "rich"

    @validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 4096:
                raise EmbedErr(makeEmbedError(27, f"description", {"length": "4096"}))
        return value

    @validator("url")
    def validate_url(cls, value: Optional[str]):
        if value is not None:
            if (scheme := value.split(":")[0]) not in ["http", "https"]:
                raise EmbedErr(makeEmbedError(24, f"url", {"scheme": scheme}))
        return value

    @validator("timestamp")
    def validate_timestamp(cls, value: Optional[str]):
        if value is not None:
            try:
                mktime(dparse(value).timetuple())
            except ValueError:
                raise EmbedErr(makeEmbedError(25, f"timestamp", {"value": value}))
        return value

    @validator("color")
    def validate_color(cls, value: Optional[int]):
        if value is not None:
            if value > 0xffffff or value < 0:
                raise EmbedErr(makeEmbedError(26, f"color"))
        return value

    @validator("footer")
    def validate_footer(cls, value: Optional[EmbedFooter]):
        if value is not None:
            if not value.text:
                value = None
        return value

    @validator("image", allow_reuse=True)
    @validator("thumbnail", allow_reuse=True)
    @validator("video", allow_reuse=True)
    def validate_image(cls, value: Optional[EmbedImage]):
        if value is not None:
            if not value.url:
                value = None
        return value

    @validator("author")
    def validate_author(cls, value: Optional[EmbedAuthor]):
        if value is not None:
            if not value.name:
                value = None
        return value

    @validator("fields")
    def validate_fields(cls, value: List[EmbedField]):
        if len(value) > 25:
            value = value[:25]

    def dict(self, *args, **kwargs) -> dict:
        kwargs["exclude_defaults"] = True
        return super().dict(*args, **kwargs)


class MessageCreate(BaseModel):
    content: Optional[str] = None
    nonce: Optional[str] = None
    embeds: List[EmbedModel] = Field(default_factory=list)
    message_reference: Optional[int] = None
    flags: Optional[int] = None

    def __init__(self, **data):
        if "message_reference" in data:
            data["message_reference"] = data["message_reference"]["message_id"]
        super().__init__(**data)

    @validator("content")
    def validate_content(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 2000: value = value[:2000] # TODO: raise exception instead
        return value

    def to_json(self) -> dict:
        return self.dict(exclude_defaults=True)


class MessageUpdate(BaseModel):
    content: Optional[str] = None
    embeds: List[EmbedModel] = Field(default_factory=list)

    @validator("content")
    def validate_content(cls, value: Optional[str]):
        if value is not None:
            if len(value) > 2000: value = value[:2000]  # TODO: raise exception instead
        return value

    def to_json(self) -> dict:
        return self.dict(exclude_defaults=True)


class InviteCreate(BaseModel):
    max_age: Optional[int] = 86400
    max_uses: Optional[int] = 0


class WebhookCreate(BaseModel):
    name: Optional[str] = None

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if not value:
            raise InvalidDataErr(400,
                                 Errors.make(50035,
                                             {"name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        return value