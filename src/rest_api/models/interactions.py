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
from typing import Literal, Optional, Any

from pydantic import BaseModel, create_model, field_validator, Field
from pydantic_core.core_schema import ValidationInfo

from .channels import EmbedModel
from ...yepcord.enums import ApplicationCommandOptionType


OPTION_MODELS = {
    ApplicationCommandOptionType.STRING: create_model("OptionString", value=(str, ...)),
    ApplicationCommandOptionType.INTEGER: create_model("OptionInt", value=(int, ...)),
    ApplicationCommandOptionType.BOOLEAN: create_model("OptionBool", value=(bool, ...)),
    ApplicationCommandOptionType.NUMBER: create_model("OptionFloat", value=(float, ...)),
    ApplicationCommandOptionType.USER: create_model("OptionUser", value=(int, ...)),
    ApplicationCommandOptionType.CHANNEL: create_model("OptionChannel", value=(int, ...)),
    ApplicationCommandOptionType.ROLE: create_model("OptionRole", value=(int, ...)),
    ApplicationCommandOptionType.MENTIONABLE: create_model("OptionMentionable", value=(int, ...)),
}


class InteractionDataOption(BaseModel):
    type: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    name: str
    value: Any = None
    options: list[InteractionDataOption] = Field(default_factory=list)

    @field_validator("value")
    def validate_value(cls, value: Any, info: ValidationInfo) -> Any:
        T = ApplicationCommandOptionType
        if info.data["type"] in {T.STRING, T.INTEGER, T.BOOLEAN, T.NUMBER}:
            return OPTION_MODELS[info.data["type"]](value=value).value
        if info.data["type"] in {T.USER, T.CHANNEL, T.ROLE, T.MENTIONABLE}:
            return str(OPTION_MODELS[info.data["type"]](value=value).value)
        if info.data["type"] in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
            return None

    @field_validator("options")
    def validate_options(cls, value: list[InteractionDataOption], info: ValidationInfo) \
            -> list[InteractionDataOption]:
        T = ApplicationCommandOptionType
        if info.data["type"] not in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
            return []

        return value


class InteractionCreateData(BaseModel):
    version: int
    id: int  # Application command id
    name: str
    type: Literal[1, 2, 3]
    options: list[InteractionDataOption] = Field(default_factory=list)
    target_id: Optional[int] = None
    #application_command: dict
    #attachments: list


class InteractionCreate(BaseModel):
    type: Literal[2, 3, 4, 5]
    application_id: int
    channel_id: int
    session_id: str
    data: InteractionCreateData
    guild_id: Optional[int] = None
    nonce: Optional[int] = None


class InteractionRespondData(BaseModel):
    content: Optional[str] = None
    embeds: list[EmbedModel] = Field(default_factory=list)
    flags: int = 0
    #components: Optional[list] = None # components validation are not supported yet :(


class InteractionRespond(BaseModel):
    type: Literal[1, 4, 5, 6, 7, 8, 9, 10]
    data: Optional[InteractionRespondData] = None
