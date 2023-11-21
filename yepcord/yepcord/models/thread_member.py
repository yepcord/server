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
from datetime import datetime

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake


class ThreadMember(Model):
    id: int = SnowflakeField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    guild: models.Guild = fields.ForeignKeyField("models.Guild")

    @property
    def joined_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    def ds_json(self) -> dict:
        return {
            "user_id": str(self.user.id),
            "muted": False,
            "mute_config": None,
            "join_timestamp": self.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "id": str(self.channel.id),
            "guild_id": str(self.guild.id),
            "flags": 1
        }
