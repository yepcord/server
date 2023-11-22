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

from pydantic import BaseModel, field_validator

from ...yepcord.errors import InvalidDataErr, Errors


# noinspection PyMethodParameters
class HypesquadHouseChange(BaseModel):
    house_id: int

    @field_validator("house_id")
    def validate_house_id(cls, value: int):
        if value not in (1, 2, 3):
            raise InvalidDataErr(400, Errors.make(50035, {"house_id": {
                "code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (1, 2, 3)."
            }}))
        return value
