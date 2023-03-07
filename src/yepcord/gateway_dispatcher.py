from __future__ import annotations

from typing import Optional

from .classes.other import Singleton
from .config import Config
from .pubsub_client import Broadcaster
from ..gateway.events import DispatchEvent


class GatewayDispatcher(Singleton):
    def __init__(self):
        self.bc = Broadcaster("")

    async def init(self) -> GatewayDispatcher:
        await self.bc.start(f"ws://{Config('PS_ADDRESS')}:5050")
        return self

    async def dispatch(self, event: DispatchEvent, users: Optional[list[int]]=None, channel_id: Optional[int]=None,
                       guild_id: Optional[int]=None, permissions: Optional[list[int]]=None) -> None:
        if not users and not channel_id and not guild_id:
            return
        await self.bc.broadcast("all_events", {
            "data": await event.json(),
            "users": users,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "permissions": permissions,
        })

import src.yepcord.ctx as c
c._getGw = lambda: GatewayDispatcher.getInstance()
from .ctx import Ctx