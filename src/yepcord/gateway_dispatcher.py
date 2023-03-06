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

    async def dispatch(self, event: DispatchEvent, clients: Optional[list[int]], **kwargs) -> None:
        await self.bc.broadcast("all_events", {
            "event": event.NAME,
            "data": await event.json(),
            "clients": clients,
            **kwargs
        })

import src.yepcord.ctx as c
c._getGw = lambda: GatewayDispatcher.getInstance()
from .ctx import Ctx