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

from datetime import datetime, timedelta

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake


class ThreadMetadata(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    archived: bool = fields.BooleanField(default=False)
    locked: bool = fields.BooleanField(default=False)
    archive_timestamp: datetime = fields.DatetimeField()
    auto_archive_duration: int = fields.BigIntField()

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    def ds_json(self) -> dict:
        archive_timestamp = self.created_at
        archive_timestamp += timedelta(minutes=self.auto_archive_duration)
        return {
            "archived": bool(self.archived),
            "archive_timestamp": archive_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "auto_archive_duration": self.auto_archive_duration,
            "locked": bool(self.locked),
            "create_timestamp": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        }
