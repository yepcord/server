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

from datetime import datetime, timezone
from time import mktime
from typing import Optional, List

from dateutil.parser import parse as dparse
from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from .channels import PermissionOverwriteModel
from ...yepcord.classes.other import BitFlags
from ...yepcord.enums import SystemChannelFlags, ChannelType, ScheduledEventEntityType, GUILD_CHANNELS
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.utils import getImage, validImage, LOCALES


# noinspection PyMethodParameters
class GuildCreate(BaseModel):
    name: str
    #region
    icon: Optional[str] = ""
    #verification_level
    #roles
    #channels
    #afk_channel_id
    #system_channel_id

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = ""
        return value


# noinspection PyMethodParameters
class GuildUpdate(BaseModel):
    name: Optional[str] = None
    verification_level: Optional[int] = None
    default_message_notifications: Optional[int] = None
    explicit_content_filter: Optional[int] = None
    afk_channel: Optional[int] = Field(default=None, alias="afk_channel_id")
    afk_timeout: Optional[int] = None
    icon: Optional[str] = ""
    owner_id: Optional[int] = None
    splash: Optional[str] = ""
    banner: Optional[str] = ""
    system_channel: Optional[int] = Field(default=None, alias="system_channel_id")
    system_channel_flags: Optional[int] = None
    #rules_channel_id
    #public_updates_channel_id
    preferred_locale: Optional[str] = None
    description: Optional[str] = None
    premium_progress_bar_enabled: Optional[bool] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value

    @field_validator("verification_level")
    def validate_verification_level(cls, value: Optional[int]):
        if value not in range(5):
            raise InvalidDataErr(400, Errors.make(50035, {"verification_level": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (0, 1, 2, 3, 4)."
            }}))
        return value

    @field_validator("default_message_notifications")
    def validate_default_message_notifications(cls, value: Optional[int]):
        if value not in (0, 1):
            raise InvalidDataErr(400, Errors.make(50035, {"default_message_notifications": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (0, 1)."
            }}))
        return value

    @field_validator("explicit_content_filter")
    def validate_explicit_content_filter(cls, value: Optional[int]):
        if value not in (0, 1):
            raise InvalidDataErr(400, Errors.make(50035, {"explicit_content_filter": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (0, 1, 2)."
            }}))
        return value

    @field_validator("afk_timeout")
    def validate_afk_timeout(cls, value: Optional[int]):
        ALLOWED_TIMEOUTS = (60, 300, 900, 1800, 3600)
        if value is not None:
            if value not in ALLOWED_TIMEOUTS:
                value = min(ALLOWED_TIMEOUTS, key=lambda x: abs(x - value))  # Take closest
        return value

    @field_validator("icon", "splash", "banner")
    def validate_icon_splash_banner(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = ""
        return value

    @field_validator("system_channel_flags")
    def validate_system_channel_flags(cls, value: Optional[int]):
        if value is not None:
            value = BitFlags(value, SystemChannelFlags).value
        return value

    @field_validator("preferred_locale")
    def validate_preferred_locale(cls, value: Optional[str]):
        if value is not None and value not in LOCALES:
            value = None
        return value

    @field_validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


# noinspection PyMethodParameters
class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {
                "name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if len(value) > 100 or len(value) < 2:
            raise InvalidDataErr(400, Errors.make(50035, {"name": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 100 in length."
            }}))
        return value

    @field_validator("description")
    def validate_description(cls, value: str):
        if len(value) > 120:
            raise InvalidDataErr(400, Errors.make(50035, {"description": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 1 and 120 in length."
            }}))
        return value


# noinspection PyMethodParameters
class TemplateUpdate(TemplateCreate):
    name: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
            elif len(value) > 100:
                raise InvalidDataErr(400, Errors.make(50035, {"name": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 100 in length."
                }}))
        return value


# noinspection PyMethodParameters
class EmojiCreate(BaseModel):
    name: str
    image: str

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {
                "name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if len(value) > 32:
            value = value[:32]
        return value

    @field_validator("image")
    def validate_image(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value


# noinspection PyMethodParameters
class EmojiUpdate(BaseModel):
    name: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
            elif len(value) > 32:
                value = value[:32]
        return value


class ChannelsPositionsChange(BaseModel):
    id: int
    position: Optional[int] = 0
    parent_id: Optional[int] = 0


class ChannelsPositionsChangeList(BaseModel):
    changes: List[ChannelsPositionsChange]


# noinspection PyMethodParameters
class ChannelCreate(BaseModel):
    name: str
    type: Optional[int] = None
    position: Optional[int] = None
    topic: Optional[str] = None
    nsfw: Optional[bool] = None
    rate_limit: Optional[int] = Field(default=None, alias="rate_limit_per_user")
    bitrate: Optional[int] = None
    user_limit: Optional[int] = None
    permission_overwrites: List[PermissionOverwriteModel] = Field(default_factory=list)
    parent_id: Optional[int] = None
    #rtc_region: Optional[str] = None
    video_quality_mode: Optional[int] = None
    default_auto_archive: Optional[int] = Field(default=None, alias="default_auto_archive_duration")
    flags: Optional[int] = None

    class Config:
        populate_by_name = True

    @field_validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value[:100]
        return value

    @field_validator("type")
    def validate_type(cls, value: Optional[str]):
        if value not in GUILD_CHANNELS:
            value = ChannelType.GUILD_TEXT
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

    @field_validator("default_auto_archive")
    def validate_auto_archive(cls, value: Optional[int]):
        ALLOWED_DURATIONS = (60, 1440, 4320, 10080)
        if value is not None:
            if value not in ALLOWED_DURATIONS:
                value = min(ALLOWED_DURATIONS, key=lambda x: abs(x - value))  # Take closest
        return value

    def to_json(self, channel_type: int) -> dict:
        if channel_type == ChannelType.GUILD_CATEGORY:
            return self.model_dump(include={"name", "type", "position"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_TEXT:
            return self.model_dump(
                include={"name", "type", "position", "topic", "nsfw", "rate_limit", "parent_id", "default_auto_archive"},
                exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_VOICE:
            return self.model_dump(include={"name", "type", "position", "nsfw", "bitrate", "user_limit", "parent_id",
                                            "video_quality_mode"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_NEWS:
            return self.model_dump(
                include={"name", "type", "position", "topic", "nsfw", "parent_id", "default_auto_archive"},
                exclude_defaults=True)


# noinspection PyMethodParameters
class BanMember(BaseModel):
    delete_message_seconds: Optional[int] = 0

    @field_validator("delete_message_seconds")
    def validate_delete_message_seconds(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 604800: value = 604800  # 7 days
        else:
            value = 0
        return value


# noinspection PyMethodParameters
class RoleCreate(BaseModel):
    name: str = "new role"
    permissions: int = 0
    color: int = 0
    hoist: bool = False
    icon: Optional[str] = None
    unicode_emoji: Optional[str] = None
    mentionable: bool = False

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            value = "new role"
        return value

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value

    @field_validator("unicode_emoji")
    def validate_unicode_emoji(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


# noinspection PyMethodParameters
class RoleUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[int] = None
    color: Optional[int] = None
    hoist: Optional[bool] = None
    icon: Optional[str] = ""
    unicode_emoji: Optional[str] = None
    mentionable: Optional[bool] = None

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            value = None
        return value

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {"image": {
                    "code": "IMAGE_INVALID", "message": "Invalid image"
                }}))
        return value

    @field_validator("unicode_emoji")
    def validate_unicode_emoji(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


class RolesPositionsChange(BaseModel):
    id: int
    position: Optional[int] = None


# noinspection PyMethodParameters
class RolesPositionsChangeList(BaseModel):
    changes: List[ChannelsPositionsChange]

    @field_validator("changes")
    def validate_changes(cls, value: List[ChannelsPositionsChange]):
        remove = []
        for change in value:
            if change.position is None:
                remove.append(change)
        for rem in remove:
            value.remove(rem)
        return value


class AddRoleMembers(BaseModel):
    member_ids: List[int] = Field(default_factory=list)


# noinspection PyMethodParameters
class MemberUpdate(BaseModel):
    nick: Optional[str] = ""
    roles: Optional[List[int]] = None
    mute: Optional[bool] = None
    deaf: Optional[bool] = None
    avatar: Optional[str] = ""

    @field_validator("nick")
    def validate_nick(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value

    @field_validator("avatar")
    def validate_avatar(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value


class SetVanityUrl(BaseModel):
    code: Optional[str] = None


# noinspection PyMethodParameters
class GuildCreateFromTemplate(BaseModel):
    name: str
    icon: Optional[str] = None

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = None
        return value


# noinspection PyMethodParameters
class GuildDelete(BaseModel):
    code: str = ""

    @field_validator("code")
    def validate_code(cls, value: str):
        return value.replace("-", "").replace(" ", "")


# noinspection PyMethodParameters
class GetAuditLogsQuery(BaseModel):
    limit: int = 50
    before: Optional[int] = None

    @field_validator("limit")
    def validate_limit(cls, value: int):
        if value < 0 or value > 50:
            value = 50
        return value


# noinspection PyMethodParameters
class CreateSticker(BaseModel):
    name: str
    description: Optional[str] = None
    tags: str

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if len(value) < 2 or len(value) > 30:
            raise InvalidDataErr(400, Errors.make(50035, {"name": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 30 in length."
            }}))
        return value

    @field_validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if len(value) > 100:
                raise InvalidDataErr(400, Errors.make(50035, {"description": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 0 and 100 in length."
                }}))
        return value

    @field_validator("tags")
    def validate_tags(cls, value: Optional[str]):
        value = value.strip()
        if len(value) < 2 or len(value) > 200:
            raise InvalidDataErr(400, Errors.make(50035, {"tags": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 200 in length."
            }}))
        return value


# noinspection PyMethodParameters
class UpdateSticker(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: str):
        if value is not None:
            value = value.strip()
            if len(value) < 2 or len(value) > 30:
                raise InvalidDataErr(400, Errors.make(50035, {"name": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 30 in length."
                }}))
        return value

    @field_validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if len(value) > 100:
                raise InvalidDataErr(400, Errors.make(50035, {"description": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 0 and 100 in length."
                }}))
        return value

    @field_validator("tags")
    def validate_tags(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if len(value) < 2 or len(value) > 200:
                raise InvalidDataErr(400, Errors.make(50035, {"tags": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 200 in length."
                }}))
        return value


class EventEntityMeta(BaseModel):
    location: str


# noinspection PyMethodParameters
class CreateEvent(BaseModel):
    name: str
    privacy_level: int
    start: int = Field(alias="scheduled_start_time")
    entity_type: int
    end: Optional[int] = Field(alias="scheduled_end_time", default=None)
    channel_id: Optional[int] = None
    entity_metadata: Optional[EventEntityMeta] = None
    description: Optional[str] = None
    image: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if len(value) < 2 or len(value) > 30:
            raise InvalidDataErr(400, Errors.make(50035, {"name": {
                "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be between 2 and 30 in length."
            }}))
        return value

    @field_validator("privacy_level")
    def validate_privacy_level(cls, value: int):
        if value != 2:
            raise InvalidDataErr(400, Errors.make(50035, {"privacy_level": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (2)."
            }}))
        return value

    @field_validator("start")
    def validate_start(cls, value: int):
        if value < datetime.utcnow().timestamp():
            raise InvalidDataErr(400, Errors.make(50035, {"scheduled_start_time": {
                "code": "BASE_TYPE_BAD_TIME", "message": "Time should be in future."
            }}))
        return value

    @field_validator("end")
    def validate_end(cls, value: Optional[int], info: ValidationInfo):
        if value is not None:
            if value < datetime.utcnow().timestamp() or value < info.data.get("start", value-1):
                raise InvalidDataErr(400, Errors.make(50035, {"scheduled_end_time": {
                    "code": "BASE_TYPE_BAD_TIME", "message": "Time should be in future."
                }}))
        else:
            if info.data["entity_type"] == ScheduledEventEntityType.EXTERNAL:
                raise InvalidDataErr(400, Errors.make(50035, {"scheduled_end_time": {
                    "code": "BASE_TYPE_REQUIRED", "message": "Required field."
                }}))
        return value

    @field_validator("entity_type")
    def validate_entity_type(cls, value: int):
        if value not in (1, 2, 3):
            raise InvalidDataErr(400, Errors.make(50035, {"entity_type": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (1, 2, 3)."
            }}))
        return value

    @field_validator("channel_id")
    def validate_channel_id(cls, value: Optional[int], info: ValidationInfo):
        if not value and info.data["entity_type"] != ScheduledEventEntityType.EXTERNAL:
            raise InvalidDataErr(400, Errors.make(50035, {"channel_id": {
                "code": "BASE_TYPE_REQUIRED", "message": "Required field."
            }}))
        return value

    @field_validator("entity_metadata")
    def validate_entity_metadata(cls, value: Optional[EventEntityMeta], info: ValidationInfo):
        if not value and info.data["entity_type"] == ScheduledEventEntityType.EXTERNAL:
            raise InvalidDataErr(400, Errors.make(50035, {"entity_metadata": {
                "code": "BASE_TYPE_REQUIRED", "message": "Required field."
            }}))
        return value

    @field_validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if len(value) > 100:
                raise InvalidDataErr(400, Errors.make(50035, {"name": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": "Must be less than 30 in length."
                }}))
        return value

    @field_validator("image")
    def validate_image(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {"image": {
                    "code": "IMAGE_INVALID", "message": "Invalid image"
                }}))
        return value

    def __init__(self, **data):
        if data.get("scheduled_start_time"):
            dt = dparse(data["scheduled_start_time"]).replace(tzinfo=timezone.utc).astimezone(tz=None)
            data["scheduled_start_time"] = mktime(dt.timetuple())
        if data.get("scheduled_end_time"):
            dt = dparse(data["scheduled_end_time"]).replace(tzinfo=timezone.utc).astimezone(tz=None)
            data["scheduled_end_time"] = mktime(dt.timetuple())
        super().__init__(**data)


class GetScheduledEvent(BaseModel):
    with_user_count: bool = False


# noinspection PyMethodParameters
class UpdateScheduledEvent(CreateEvent):
    name: Optional[str] = None
    privacy_level: Optional[int] = None
    start: Optional[int] = Field(alias="scheduled_start_time", default=None)
    entity_type: Optional[int] = None
    status: Optional[int] = None
    image: Optional[str] = ""

    @field_validator("channel_id")
    def validate_channel_id(cls, value: Optional[int], info: ValidationInfo):
        if not value and info.data["entity_type"] != ScheduledEventEntityType.EXTERNAL:
            raise InvalidDataErr(400, Errors.make(50035, {"channel_id": {
                "code": "BASE_TYPE_REQUIRED", "message": "Required field."
            }}))
        if info.data["entity_type"] == ScheduledEventEntityType.EXTERNAL:
            value = None
        return value


class GetIntegrationsQS(BaseModel):
    include_applications: bool = False
    include_role_connections_metadata: bool = False
