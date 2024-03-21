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
from os import urandom
from time import time
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


def gen_token():
    return urandom(32).hex()


def gen_cur_time():
    return int(time())


class VoiceState(Model):
    id: int = SnowflakeField(pk=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild", default=None, null=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    user: models.User = fields.ForeignKeyField("models.User")
    session_id: str = fields.CharField(max_length=64)
    token: Optional[str] = fields.CharField(max_length=128, default=gen_token)
    last_heartbeat: int = fields.BigIntField(default=gen_cur_time)

    def ds_json(self) -> dict:
        return {
            "user_id": self.user.id,
            "suppress": False,
            "session_id": self.session_id,
            "self_video": False,
            "self_mute": False,
            "self_deaf": False,
            "request_to_speak_timestamp": None,
            "mute": False,
            "deaf": False,
            "channel_id": self.channel.id
        }
