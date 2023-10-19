from typing import Literal, Optional, Any

from pydantic import BaseModel, validator, create_model

from ...yepcord.enums import ApplicationCommandOptionType


OPTION_MODELS = {
    ApplicationCommandOptionType.STRING: create_model("OptionString", value=(str, ...)),
    ApplicationCommandOptionType.INTEGER: create_model("OptionInt", value=(int, ...)),
    ApplicationCommandOptionType.BOOLEAN: create_model("OptionBool", value=(bool, ...)),
    ApplicationCommandOptionType.NUMBER: create_model("OptionFloat", value=(float, ...)),
}


class InteractionDataOption(BaseModel):
    type: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    name: str
    value: Any

    @validator("value")
    def validate_value(cls, value: Any, values: dict) -> Any:
        T = ApplicationCommandOptionType
        if values["type"] in {T.STRING, T.INTEGER, T.BOOLEAN, T.NUMBER}:
            return OPTION_MODELS[values["type"]](value=value).value

        return value


class InteractionCreateData(BaseModel):
    version: int
    id: int  # Application command id
    name: str
    type: Literal[1, 2, 3]
    options: list[InteractionDataOption]
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
    #embeds: Optional[list] = None
    flags: Optional[int] = None
    #components: Optional[list] = None # components validation are not supported now :(


class InteractionRespond(BaseModel):
    type: Literal[1, 4, 5, 6, 7, 8, 9, 10]
    data: Optional[InteractionRespondData] = None
