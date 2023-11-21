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

from tortoise import fields

from ._utils import ChoicesValidator, SnowflakeField, Model
from ..snowflake import Snowflake
import yepcord.yepcord.models as models


class ConnectedAccount(Model):
    id: int = SnowflakeField(pk=True)
    service_id: str = fields.CharField(max_length=128, unique=True)
    user: models.User = fields.ForeignKeyField("models.User")
    name: str = fields.TextField()
    type: str = fields.CharField(max_length=64, validators=[ChoicesValidator(set())])
    revoked: bool = fields.BooleanField(default=False)
    show_activity: bool = fields.BooleanField(default=True)
    verified: bool = fields.BooleanField(default=False)
    visibility: int = fields.IntField(default=1, validators=[ChoicesValidator({0, 1})])
    metadata_visibility: int = fields.IntField(default=1, validators=[ChoicesValidator({0, 1})])
    metadata: dict = fields.JSONField(default={})
    access_token: Optional[str] = fields.TextField(null=True, default=None)
    state: int = fields.BigIntField(default=Snowflake.makeId)

    def ds_json(self) -> dict:
        return {
            "visibility": self.visibility,
            "verified": True,
            "type": self.type,
            "two_way_link": False,
            "show_activity": self.show_activity,
            "revoked": self.revoked,
            "name": self.name,
            "metadata_visibility": self.metadata_visibility,
            "id": self.service_id,
            "friend_sync": False,
        }
