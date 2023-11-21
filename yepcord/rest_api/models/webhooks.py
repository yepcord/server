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

from typing import Optional

from pydantic import BaseModel, field_validator

from .channels import MessageCreate
from ...yepcord.utils import getImage, validImage


# noinspection PyMethodParameters
class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    channel_id: Optional[int] = None
    avatar: Optional[str] = ""

    @field_validator("avatar")
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
            data["wait"] = data["wait"].lower() in {"true", "1"}
        super().__init__(**data)
