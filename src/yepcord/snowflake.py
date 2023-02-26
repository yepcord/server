from datetime import datetime, timezone
from os import getpid
from random import randint
from time import time

from .classes.other import Singleton


class Snowflake(Singleton):
    EPOCH = 1640995200_000
    MAX_TIMESTAMP = 1 << 42
    _INCREMENT = 0
    _WORKER = randint(0, 32)
    _PROCESS = getpid()

    def __init__(self, timestamp: int, worker: int, process: int, increment: int):
        self.timestamp = self.time = timestamp  # In milliseconds
        self.worker = worker
        self.process = process
        self.increment = increment

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
    def fromTimestamp(cls, timestamp: int) -> int:
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