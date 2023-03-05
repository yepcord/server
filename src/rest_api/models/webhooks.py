from typing import Optional

from pydantic import BaseModel, validator

from .channels import MessageCreate
from ...yepcord.utils import getImage, validImage


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    channel_id: Optional[int] = None
    avatar: Optional[str] = ""

    @validator("avatar")
    def validate_avatar(cls, value: Optional[str]):
        if value:
            if not (img := getImage(value)) or not validImage(img):
                value = ""
        return value


class WebhookMessageCreate(MessageCreate):
    pass


class WebhookMessageCreateQuery(BaseModel):
    wait: bool = False

    def __init__(self, **data):
        if "wait" in data:
            data["wait"] = data["wait"].lower() == "true"
        super().__init__(**data)
