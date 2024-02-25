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

from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model, ChoicesValidator
from ..enums import ApplicationCommandType
from ..snowflake import Snowflake


class ApplicationCommand(Model):
    id: int = SnowflakeField(pk=True)
    application: models.Application = fields.ForeignKeyField("models.Application")
    guild: Optional[models.Guild] = fields.ForeignKeyField("models.Guild", null=True, default=None)
    name: str = fields.CharField(min_length=1, max_length=32)
    description: str = fields.CharField(max_length=100)
    type: int = fields.IntField(default=1, validators=[ChoicesValidator(ApplicationCommandType.values_set())])
    name_localizations: dict = fields.JSONField(null=True, default=None)
    description_localizations: dict = fields.JSONField(null=True, default=None)
    options: list[dict] = fields.JSONField(default=[])
    default_member_permissions: Optional[int] = fields.BigIntField(null=True, default=None)
    dm_permission: bool = fields.BooleanField(default=True)
    nsfw: bool = fields.BooleanField(default=False)
    version: int = fields.BigIntField(default=Snowflake.makeId)

    def ds_json(self, with_localizations: bool=False) -> dict:
        default_member_permissions = str(self.default_member_permissions) if self.default_member_permissions else None

        data = {
            "id": str(self.id),
            "type": self.type,
            "application_id": str(self.application.id),
            "name": self.name,
            "description": self.description,
            "options": self.options,
            "default_member_permissions": default_member_permissions,
            "dm_permission": self.dm_permission,
            "nsfw": self.nsfw,
            "version": str(self.version),
            "integration_types": [0],
            "contexts": None,
        }
        if self.guild:
            data["guild_id"] = str(self.guild.id)
        if with_localizations:
            data["name_localizations"] = self.name_localizations
            data["description_localizations"] = self.description_localizations

        return data
