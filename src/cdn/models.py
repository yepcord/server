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

ALLOWED_IMAGE_SIZES = [16, 20, 22, 24, 28, 32, 40, 44, 48, 56, 60, 64, 80, 96, 100, 128, 160, 240, 256, 300, 320, 480,
                       512, 600, 640, 1024, 1280, 1536, 2048, 3072, 4096]


# noinspection PyMethodParameters
class CdnImageSizeQuery(BaseModel):
    size: int = 128

    @field_validator("size")
    def validate_size(cls, value: int):
        if value is not None:
            if value not in ALLOWED_IMAGE_SIZES:
                value = min(ALLOWED_IMAGE_SIZES, key=lambda x: abs(x - value))  # Take closest
        return value
