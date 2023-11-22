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

from tortoise import fields

from ..ctx import getCore
import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class ReadState(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    user: models.User = fields.ForeignKeyField("models.User")
    last_read_id: int = fields.BigIntField()
    count: int = fields.IntField()

    async def ds_json(self) -> dict:
        return {
            "mention_count": self.count,
            "last_pin_timestamp": await getCore().getLastPinTimestamp(self.channel),
            "last_message_id": str(self.last_read_id),
            "id": str(self.channel.id),
        }
