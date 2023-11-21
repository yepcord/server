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

from datetime import datetime, timezone
from os import getpid
from random import randint
from time import time
from typing import Union

from .classes.singleton import Singleton


class Snowflake(Singleton):
    EPOCH = 1640995200_000
    MAX_TIMESTAMP = 1 << 42
    _INCREMENT = 0
    _WORKER = randint(0, 32)
    _PROCESS = getpid()

    @classmethod
    def makeId(cls, increment=True) -> int:
        timestamp = int(time() * 1000) - cls.EPOCH

        snowflake = (timestamp % cls.MAX_TIMESTAMP) << 22
        snowflake += (cls._WORKER % 32) << 17
        snowflake += (cls._PROCESS % 32) << 12
        snowflake += cls._INCREMENT % 4096

        if increment:
            cls._INCREMENT += 1

        return snowflake

    @classmethod
    def fromTimestamp(cls, timestamp: Union[int, float]) -> int:
        """
        Creates id from timestamp
        :param timestamp: Timestamp in seconds
        :return:
        """
        timestamp = int(timestamp * 1000) - cls.EPOCH

        snowflake = (timestamp % cls.MAX_TIMESTAMP) << 22
        snowflake += (cls._WORKER % 32) << 17
        snowflake += (cls._PROCESS % 32) << 12
        snowflake += cls._INCREMENT % 4096

        return snowflake

    @classmethod
    def toTimestamp(cls, snowflake: int) -> int:
        return (snowflake >> 22) + cls.EPOCH

    @classmethod
    def toDatetime(cls, snowflake: int) -> datetime:
        timestamp = ((snowflake >> 22) + cls.EPOCH) / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
