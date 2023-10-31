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

import asyncio
import warnings
from json import loads, dumps
from typing import Optional, Any, TYPE_CHECKING

from redis.asyncio.client import Redis, PubSub

from ..yepcord.config import Config
if TYPE_CHECKING:  # pragma: no cover
    from .gateway import Gateway


async def init_redis_pool() -> Optional[Redis]:
    if not Config.REDIS_URL:
        return
    return Redis.from_url(
        Config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


class Presence:
    def __init__(self, user_id: int, status: str, custom_status: dict = None, activities: list = None) -> None:
        self.user_id = user_id
        self.status = status
        self.activities = activities or []
        if custom_status is not None:
            self.activities.append({
                "name": "Custom Status",
                "type": 4,
                "state": custom_status.get("text"),
                "emoji": None,
            })
            if "expires_at_ms" in custom_status:
                self.activities[-1]["timestamps"] = {
                    "end": custom_status.get("expires_at_ms"),
                }
            if "emoji_id" in custom_status or "emoji_name" in custom_status:
                self.activities[-1]["emoji"] = {
                    "emoji_id": custom_status.get("emoji_id"),
                    "emoji_name": custom_status.get("emoji_name"),
                }

    @property
    def public_status(self) -> str:
        return self.status if self.status != "invisible" else "offline"


class Presences:
    def __init__(self, gateway: Gateway):
        self._gateway = gateway
        self._presences: dict[int, Presence] = {}
        self._redis: Optional[Redis] = None
        self._expiration_tasks: dict[int, Any] = {}

    async def _expiration_handler(self, message: dict[str, str]) -> None:
        if "presence_" not in message["data"]:
            return
        user_id = int(message["data"][9:])
        await self._gateway.ev.presence_update(user_id, Presence(user_id, "offline"))

    async def _pubsub_receive(self, pubsub: PubSub) -> None:
        while True:
            try:
                if pubsub and pubsub.subscribed:
                    await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                else:
                    await asyncio.sleep(1)
            except (asyncio.CancelledError, asyncio.TimeoutError, GeneratorExit):
                raise
            except BaseException:
                await asyncio.sleep(1)

    async def init(self) -> None:
        try:
            self._redis = await init_redis_pool()
            await self._redis.config_set("notify-keyspace-events", "Ex")
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe(**{"__keyevent@*__:expired": self._expiration_handler})
            asyncio.create_task(self._pubsub_receive(pubsub))
        except Exception as e:
            warnings.warn(f"Failed to connect to redis pool: {e.__class__.__name__}: {e}.")
            return

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    def _get_expiration_task(self, user_id: int, cancel_old: bool = True):
        async def expiration_task():
            await asyncio.sleep(Config.GATEWAY_KEEP_ALIVE_DELAY * 1.25)
            if user_id in self._presences:
                del self._presences[user_id]

            await self._expiration_handler({"data": f"presence_{user_id}"})

        if cancel_old and user_id in self._expiration_tasks:
            self._expiration_tasks[user_id].cancel()
            del self._expiration_tasks[user_id]

        return expiration_task

    async def set_or_refresh(self, user_id: int, presence: Presence = None, overwrite=False):
        if self._redis is None:
            if (user_id not in self._presences and not overwrite) and presence is not None:
                self._presences[user_id] = presence
            self._expiration_tasks[user_id] = asyncio.create_task(self._get_expiration_task(user_id)())
            return

        pipe = self._redis.pipeline()
        await pipe.set(
            f"presence_{user_id}",
            dumps({
                "status": presence.status if presence else "offline",
                "activities": presence.activities if presence else [],
            }),
            ex=int(Config.GATEWAY_KEEP_ALIVE_DELAY * 1.25),
            nx=not overwrite,
        )
        await pipe.expire(f"presence_{user_id}", int(Config.GATEWAY_KEEP_ALIVE_DELAY * 1.25))
        await pipe.execute()

    async def get(self, user_id: int) -> Optional[Presence]:
        if self._redis is None:
            return self._presences.get(user_id)

        if (presence := await self._redis.get(f"presence_{user_id}")) is None:
            return
        return Presence(user_id, **loads(presence))
