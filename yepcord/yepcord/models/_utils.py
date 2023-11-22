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

from typing import Any, Type, Optional

import tortoise
from tortoise import BaseDBAsyncClient
from tortoise.exceptions import ValidationError
from tortoise.fields import BigIntField
from tortoise.models import MODEL
from tortoise.validators import Validator

from yepcord.yepcord.snowflake import Snowflake


class ChoicesValidator(Validator):
    def __init__(self, choices: set[Any]):
        self.choices = choices

    def __call__(self, value: Any):
        if value not in self.choices:
            raise ValidationError(f"Value '{value}' is not in {self.choices}")


class SnowflakeField(BigIntField):
    def __init__(self, *args, **kwargs):
        kwargs["default"] = Snowflake.makeId
        kwargs["generated"] = False
        super().__init__(*args, **kwargs)


class Model(tortoise.Model):
    async def update(self, **kwargs) -> None:
        await self.update_from_dict(kwargs)
        await self.save()
