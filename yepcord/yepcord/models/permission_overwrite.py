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

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class PermissionOverwrite(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    target_user: models.User = fields.ForeignKeyField("models.User", null=True, default=None)
    target_role: models.Role = fields.ForeignKeyField("models.Role", null=True, default=None)
    type: int = fields.IntField()
    allow: int = fields.BigIntField()
    deny: int = fields.BigIntField()

    @property
    def target(self) -> models.User | models.Role:
        return self.target_user if self.target_user is not None else self.target_role

    def ds_json(self) -> dict:
        return {
            "type": self.type,
            "id": str(self.target.id),
            "deny": str(self.deny),
            "allow": str(self.allow)
        }
