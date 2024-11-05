"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2024 RuslanUC

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
from ._utils import SnowflakeField, Model
from ..enums import ChannelType, GUILD_CHANNELS


class ReadState(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    user: models.User = fields.ForeignKeyField("models.User")
    last_read_id: int = fields.BigIntField()
    count: int = fields.IntField()

    class Meta:
        unique_together = (
            ("channel", "user"),
        )

    async def ds_json(self) -> dict:
        last_pin = await self.channel.get_last_pinned_message()
        last_pin_ts = last_pin.pinned_timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00") if last_pin is not None else None
        return {
            "mention_count": self.count,
            "last_pin_timestamp": last_pin_ts,
            "last_message_id": str(self.last_read_id),
            "id": str(self.channel.id),
        }

    @classmethod
    async def create_or_add(
            cls, user: models.User, channel: models.Channel, mentions: int = 1, last_read_id: Optional[int] = None,
    ) -> ReadState:
        state, created = await cls.get_or_create(user=user, channel=channel, defaults={
            "count": mentions,
            "last_read_id": last_read_id or 0,
        })
        if not created:
            state.count += mentions
            state.last_read_id = last_read_id or state.last_read_id
            await state.save(update_fields=["count", "last_read_id"])

        return state

    @classmethod
    async def update_from_message(cls, message: models.Message) -> None:
        if message.channel.type in (ChannelType.DM, ChannelType.GROUP_DM):
            for user in await message.channel.recipients.filter(id__not=message.author.id):
                await models.ReadState.create_or_add(user, message.channel)
        elif message.channel.type in GUILD_CHANNELS:
            ...  # TODO: update read state of mentioned users
