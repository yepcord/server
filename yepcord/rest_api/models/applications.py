from __future__ import annotations

from typing import Optional, Literal, Union

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from ...yepcord.enums import Locales, ApplicationCommandOptionType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.utils import getImage, validImage


class CreateApplication(BaseModel):
    name: str
    team_id: Optional[int] = None


class UpdateApplication(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = ""
    icon: Optional[str] = ""
    interactions_endpoint_url: Optional[str] = ""
    privacy_policy_url: Optional[str] = ""
    terms_of_service_url: Optional[str] = ""
    role_connections_verification_url: Optional[str] = ""
    tags: list[str] = Field(default_factory=list, max_items=5)
    redirect_uris: list[str] = Field(default_factory=list, max_items=9)
    max_participants: Optional[int] = None
    bot_public: bool = None
    bot_require_code_grant: bool = None
    flags: int = None

    @field_validator("icon")
    def validate_icon(cls, value: Optional[str]):
        if value and len(value) == 32:
            value = ""
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {"icon": {
                    "code": "IMAGE_INVALID", "message": "Invalid image"
                }}))
        return value


class UpdateApplicationBot(BaseModel):
    username: Optional[str] = None
    avatar: Optional[str] = ""

    @field_validator("avatar")
    def validate_avatar(cls, value: Optional[str]):
        if value and len(value) == 32:
            value = ""
        if value:
            if not (img := getImage(value)) or not validImage(img):
                raise InvalidDataErr(400, Errors.make(50035, {"avatar": {
                    "code": "IMAGE_INVALID", "message": "Invalid image"
                }}))
        return value


class GetCommandsQS(BaseModel):
    with_localizations: Optional[bool] = False


class CommandBase(BaseModel):
    name: str = Field(max_length=32)
    description: str = Field(max_length=100)
    name_localizations: Optional[dict] = None
    description_localizations: Optional[dict] = None
    options: Optional[list[CommandOption]] = Field(default=None)

    @field_validator("name_localizations", "description_localizations")
    def validate_localizations(cls, value: Optional[dict], info: ValidationInfo) -> Optional[dict]:
        if value is not None and any(k not in Locales.values_set() for k in value):
            raise InvalidDataErr(400, Errors.make(50035, {info.field_name: {
                "code": "ENUM_TYPE_COERCE", "message": f"Value is not a valid enum value."
            }}))
        if value is not None:
            lim = 32 if info.field_name == "name_localizations" else 100
            if any(len(val) > lim for val in value.values()):
                raise InvalidDataErr(400, Errors.make(50035, {"name_localizations": {
                    "code": "BASE_TYPE_BAD_LENGTH", "message": f"Must be between 1 and {lim} in length."
                }}))
        return value

    @field_validator("options")
    def validate_options(cls, value: Optional[list[CommandOption]]) -> Optional[list[CommandOption]]:
        T = ApplicationCommandOptionType
        if value is None:
            return
        not_sub = []
        for idx, option in enumerate(value):
            if option.type not in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
                not_sub.append(idx)
        if len(not_sub) != 0 and len(not_sub) != len(value):
            raise InvalidDataErr(400, Errors.make(50035, {"options": {
                "code": "APPLICATION_COMMAND_OPTIONS_TYPE_INVALID",
                "message": "Sub-command and sub-command group option types are mutually exclusive to all other types"}}))
        return value

    def __init__(self, **kwargs):
        if (options := kwargs.get("options")) and isinstance(options, list) and len(options) > 25:
            kwargs["options"] = options[:25]
        super().__init__(**kwargs)


ChoicesType = Optional[list[Union[str, int, float]]]


class CommandOption(CommandBase):
    type: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    required: bool = True
    choices: ChoicesType = Field(default=None, max_items=25)
    channel_types: Optional[list[Literal[0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14]]] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    autocomplete: Optional[bool] = None

    @field_validator("choices")
    def validate_choices(cls, value: ChoicesType, info: ValidationInfo) -> ChoicesType:
        T = ApplicationCommandOptionType
        if info.data["type"] not in {T.STRING, T.INTEGER, T.NUMBER} and value is not None:
            return None
        return value

    @field_validator("channel_types")
    def validate_channel_types(cls, value, info: ValidationInfo):
        if info.data["type"] != ApplicationCommandOptionType.CHANNEL and value is not None:
            return None
        return value

    @field_validator("min_value", "max_value")
    def validate_min_max_value(cls, value: Optional[int], info: ValidationInfo) -> Optional[int]:
        T = ApplicationCommandOptionType
        if info.data["type"] not in {T.INTEGER, T.NUMBER} and value is not None:
            return None
        return value

    @field_validator("min_length", "max_length")
    def validate_min_max_length(cls, value: Optional[int], info: ValidationInfo) -> Optional[int]:
        if info.data["type"] != ApplicationCommandOptionType.STRING and value is not None:
            return None
        if value is not None:
            if value < 0: value = 0
            if value > 6000: value = 6000
            if (info.field_name == "min_length" and value > info.data.get("max_length", value)) \
                    or (info.field_name == "max_length" and value < info.data.get("min_length", value)):
                raise InvalidDataErr(400, Errors.make(50035, {info.field_name: {
                    "code": "BASE_TYPE_BAD_INTEGER", "message": "Bad integer."
                }}))
        return value

    @field_validator("options")
    def validate_options(cls, value: Optional[list[CommandOption]], info: ValidationInfo) \
            -> Optional[list[CommandOption]]:
        T = ApplicationCommandOptionType
        if info.data.get("type", 1) not in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
            return None
        return value


class CreateCommand(CommandBase):
    type: Literal[1, 2, 3] = 1
    dm_permission: bool = True
