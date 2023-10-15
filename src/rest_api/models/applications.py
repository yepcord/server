from typing import Optional

from pydantic import BaseModel, validator, Field

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

    @validator("icon")
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

    @validator("avatar")
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


class CreateCommand(BaseModel):
    name: str
    description: str
    type: int = 1
    name_localizations: Optional[str] = None
    description_localizations: Optional[str] = None
    dm_permission: bool = True

    @validator("type")
    def validate_type(cls, value: int) -> int:
        if value not in {1, 2, 3}:
            raise InvalidDataErr(400, Errors.make(50035, {"type": {
                "code": "ENUM_TYPE_COERCE", "message": f"Value \"{value}\" is not a valid enum value."
            }}))
        return value
