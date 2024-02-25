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

from json import loads, dumps
from typing import Optional, TYPE_CHECKING

from ..yepcord.config import Config

if TYPE_CHECKING:  # pragma: no cover
    from .gateway import Gateway


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

    #async def _expiration_handler(self, message: dict[str, str]) -> None:
    #    if "presence_" not in message["data"]:
    #        return
    #    user_id = int(message["data"][9:])
    #    await self._gateway.ev.presence_update(user_id, Presence(user_id, "offline"))

    async def set_or_refresh(self, user_id: int, presence: Presence = None, overwrite=False):
        pipe = self._gateway.redis.pipeline()
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
        if (presence := await self._gateway.redis.get(f"presence_{user_id}")) is None:
            return
        return Presence(user_id, **loads(presence))
