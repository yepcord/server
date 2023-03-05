from typing import Optional, List

from pydantic import BaseModel, validator, Field

from ...yepcord.classes.other import BitFlags
from ...yepcord.enums import SystemChannelFlags, ChannelType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.utils import getImage, validImage, LOCALES


class GuildCreate(BaseModel):
    name: str
    #region
    icon: Optional[str] = ""
    #verification_level
    #roles
    #channels
    #afk_channel_id
    #system_channel_id

    @validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = ""
        return value


class GuildUpdate(BaseModel):
    name: Optional[str] = None
    verification_level: Optional[int] = None
    default_message_notifications: Optional[int] = None
    explicit_content_filter: Optional[int] = None
    afk_channel_id: Optional[int] = 0
    afk_timeout: Optional[int] = None
    icon: Optional[str] = ""
    owner_id: Optional[int] = None
    splash: Optional[str] = ""
    banner: Optional[str] = ""
    system_channel_id: Optional[int] = 0
    system_channel_flags: Optional[int] = None
    #rules_channel_id
    #public_updates_channel_id
    preferred_locale: Optional[str] = None
    description: Optional[str] = None
    premium_progress_bar_enabled: Optional[bool] = None

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value

    @validator("verification_level")
    def validate_verification_level(cls, value: Optional[int]):
        if value not in range(5):
            raise InvalidDataErr(400, Errors.make(50035, {"verification_level": {"code": "BASE_TYPE_CHOICES", "message":
                "The following values are allowed: (0, 1, 2, 3, 4)."}}))
        return value

    @validator("default_message_notifications")
    def validate_default_message_notifications(cls, value: Optional[int]):
        if value not in (0, 1):
            raise InvalidDataErr(400, Errors.make(50035, {"default_message_notifications": {"code": "BASE_TYPE_CHOICES", "message":
                "The following values are allowed: (0, 1)."}}))
        return value

    @validator("explicit_content_filter")
    def validate_explicit_content_filter(cls, value: Optional[int]):
        if value not in (0, 1):
            raise InvalidDataErr(400, Errors.make(50035, {"explicit_content_filter": {"code": "BASE_TYPE_CHOICES", "message":
                "The following values are allowed: (0, 1, 2)."}}))
        return value

    @validator("afk_timeout")
    def validate_afk_timeout(cls, value: Optional[int]):
        ALLOWED_TIMEOUTS = (60, 300, 900, 1800, 3600)
        if value is not None:
            if value not in ALLOWED_TIMEOUTS:
                value = min(ALLOWED_TIMEOUTS, key=lambda x: abs(x - value))  # Take closest
        return value

    @validator("icon", "splash", "banner")
    def validate_icon_splash_banner(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = ""
        return value

    @validator("system_channel_flags")
    def validate_system_channel_flags(cls, value: Optional[int]):
        if value is not None:
            value = BitFlags(value, SystemChannelFlags).value
        return value

    @validator("preferred_locale")
    def validate_preferred_locale(cls, value: Optional[str]):
        if value is not None and value not in LOCALES:
            value = None
        return value

    @validator("description")
    def validate_description(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {
                "name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if len(value) > 100:
            value = value[:100]  # TODO: raise exception instead
        return value

    @validator("description")
    def validate_description(cls, value: str):
        if len(value) > 120:
            value = value[:120]  # TODO: raise exception instead
        return value


class TemplateUpdate(TemplateCreate):
    name: Optional[str] = None

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
            elif len(value) > 100:
                value = value[:100]  # TODO: raise exception instead
        return value


class EmojiCreate(BaseModel):
    name: str
    image: str

    @validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {
                "name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if len(value) > 32:
            value = value[:32]
        return value

    @validator("image")
    def validate_image(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value


class EmojiUpdate(BaseModel):
    name: Optional[str] = None

    @validator("name")
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


class ChannelCreate(BaseModel):
    name: str
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

    class Config:
        allow_population_by_field_name = True

    @validator("name")
    def validate_name(cls, value: Optional[str]):
        if value is not None:
            value = value[:100]
        return value

    @validator("type")
    def validate_type(cls, value: Optional[str]):
        if value not in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY): # TODO: add other guild channel types
            value = ChannelType.GUILD_TEXT
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

    @validator("default_auto_archive")
    def validate_auto_archive(cls, value: Optional[int]):
        ALLOWED_DURATIONS = (60, 1440, 4320, 10080)
        if value is not None:
            if value not in ALLOWED_DURATIONS:
                value = min(ALLOWED_DURATIONS, key=lambda x: abs(x - value)) # Take closest
        return value

    def to_json(self, channel_type: int) -> dict:
        if channel_type == ChannelType.GUILD_CATEGORY:
            return self.dict(include={"name", "type", "position"}, exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_TEXT:
            return self.dict(
                include={"name", "type", "position", "topic", "nsfw", "rate_limit", "parent_id", "default_auto_archive"},
                exclude_defaults=True)
        elif channel_type == ChannelType.GUILD_VOICE:
            return self.dict(include={"name", "type", "position", "nsfw", "bitrate", "user_limit", "parent_id",
                                      "video_quality_mode"}, exclude_defaults=True)


class BanMember(BaseModel):
    delete_message_seconds: Optional[int] = None

    @validator("delete_message_seconds")
    def validate_delete_message_seconds(cls, value: Optional[int]):
        if value is not None:
            if value < 0: value = 0
            if value > 604800: value = 604800 # 7 days
        else:
            value = 0
        return value


class RoleCreate(BaseModel):
    name: str = "new role"
    permissions: int = 0
    color: int = 0
    hoist: bool = False
    icon: Optional[str] = None
    unicode_emoji: Optional[str] = None
    mentionable: bool = False

    @validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            value = "new role"
        return value

    @validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value

    @validator("unicode_emoji")
    def validate_unicode_emoji(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[int] = None
    color: Optional[int] = None
    hoist: Optional[bool] = None
    icon: Optional[str] = ""
    unicode_emoji: Optional[str] = None
    mentionable: Optional[bool] = None

    @validator("name")
    def validate_name(cls, value: str):
        value = value.strip()
        if not value:
            value = None
        return value

    @validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value

    @validator("unicode_emoji")
    def validate_unicode_emoji(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value


class RolesPositionsChange(BaseModel):
    id: int
    position: Optional[int] = None


class RolesPositionsChangeList(BaseModel):
    changes: List[ChannelsPositionsChange]

    @validator("changes")
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


class MemberUpdate(BaseModel):
    nick: Optional[str] = ""
    roles: Optional[List[int]] = None
    mute: Optional[bool] = None
    deaf: Optional[bool] = None
    avatar: Optional[str] = ""

    @validator("nick")
    def validate_nick(cls, value: Optional[str]):
        if value is not None:
            value = value.strip()
            if not value:
                value = None
        return value

    @validator("avatar")
    def validate_avatar(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {
                    "image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        return value


class SetVanityUrl(BaseModel):
    code: Optional[str] = None


class GuildCreateFromTemplate(BaseModel):
    name: str
    icon: Optional[str] = None

    @validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = None
        return value


class GuildDelete(BaseModel):
    code: str = ""

    @validator("code")
    def validate_code(cls, value: str):
        return value.replace("-", "").replace(" ", "")


class GetAuditLogsQuery(BaseModel):
    limit: int = 50
    before: Optional[int] = None

    @validator("limit")
    def validate_limit(cls, value: int):
        if value < 0 or value > 50:
            value = 50
        return value