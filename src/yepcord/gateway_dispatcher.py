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

import warnings
from datetime import datetime
from typing import Optional

from .classes.channel import Channel
from .classes.guild import Guild
from .classes.other import Singleton
from .config import Config
from .pubsub_client import Broadcaster
from ..gateway.events import DispatchEvent, ChannelPinsUpdateEvent, MessageAckEvent, GuildEmojisUpdate, \
    StickersUpdateEvent


class GatewayDispatcher(Singleton):
    def __init__(self):
        self.bc = Broadcaster("")

    async def init(self) -> GatewayDispatcher:
        try:
            await self.bc.start(f"ws://{Config('PS_ADDRESS')}:5050")
        except ConnectionRefusedError:
            self.bc.online = False
            self.bc.running = True
        return self

    async def dispatch(self, event: DispatchEvent, users: Optional[list[int]]=None, channel_id: Optional[int]=None,
                       guild_id: Optional[int]=None, permissions: Optional[list[int]]=None) -> None:
        if not users and not channel_id and not guild_id:
            warnings.warn("users/channel_id/guild_id must be provided!")
            return
        await self.bc.broadcast("yepcord_events", {
            "data": await event.json(),
            "event": event.NAME,
            "users": users,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "permissions": permissions,
        })

    async def sendMessageAck(self, uid: int, channel_id: int, message_id: int, mention_count: int=None, manual: bool=None) -> None:
        ack = {
            "version": 1,
            "message_id": str(message_id),
            "channel_id": str(channel_id),
        }
        if mention_count:
            ack["mention_count"] = mention_count
        if manual:
            ack["manual"] = True
            ack["ack_type"] = 0
        await self.dispatch(MessageAckEvent(ack), users=[uid])

    async def sendPinsUpdateEvent(self, channel: Channel) -> None:
        ts = 0
        if message := await c.getCore().getLastPinnedMessage(channel.id):
            ts = message.extra_data["pinned_at"]
        ts = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        await self.dispatch(ChannelPinsUpdateEvent(channel.id, ts), channel_id=channel.id)

    async def sendGuildEmojisUpdateEvent(self, guild: Guild) -> None:
        emojis = [await emoji.json for emoji in await c.getCore().getEmojis(guild.id)]
        await self.dispatch(GuildEmojisUpdate(guild.id, emojis), guild_id=guild.id)

    async def sendStickersUpdateEvent(self, guild: Guild) -> None:
        stickers = await c.getCore().getGuildStickers(guild)
        stickers = [await sticker.json for sticker in stickers]
        await self.dispatch(StickersUpdateEvent(guild.id, stickers), guild_id=guild.id)

import src.yepcord.ctx as c
c._getGw = lambda: GatewayDispatcher.getInstance()
from .ctx import Ctx