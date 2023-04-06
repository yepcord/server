from pydantic import BaseModel, validator

from ...yepcord.errors import InvalidDataErr, Errors


# noinspection PyMethodParameters
class HypesquadHouseChange(BaseModel):
    house_id: int

    @validator("house_id")
    def validate_house_id(cls, value: int):
        if value not in (1, 2, 3):
            raise InvalidDataErr(400, Errors.make(50035, {"house_id": {"code": "BASE_TYPE_CHOICES", "message":
                "The following values are allowed: (1, 2, 3)."}}))
        return value