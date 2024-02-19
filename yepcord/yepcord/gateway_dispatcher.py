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

from datetime import datetime
from typing import Optional

from tortoise.expressions import RawSQL, Q

from .classes.singleton import Singleton
from .enums import ChannelType
from .models import Channel, Guild, PermissionOverwrite, Role
from .mq_broker import getBroker
from ..gateway.events import DispatchEvent, ChannelPinsUpdateEvent, MessageAckEvent, GuildEmojisUpdate, \
    StickersUpdateEvent


class GatewayDispatcher(Singleton):
    def __init__(self):
        self.broker = getBroker()

    async def init(self) -> GatewayDispatcher:
        await self.broker.start()
        return self

    async def stop(self) -> GatewayDispatcher:
        await self.broker.close()
        return self

    async def dispatch(self, event: DispatchEvent, user_ids: Optional[list[int]]=None, guild_id: Optional[int]=None,
                       role_ids: Optional[list[int]]=None, session_id: Optional[str]=None,
                       channel: Optional[Channel] = None, permissions: Optional[int] = None) -> None:
        if not user_ids and not guild_id and not role_ids and not session_id and not channel:
            return
        data = {
            "data": await event.json(),
            "event": event.NAME,
            "user_ids": user_ids,
            "guild_id": guild_id,  # TODO: if permissions is not None, replace guild_id with role_ids (with these permissions)
            "role_ids": role_ids,
            "session_id": session_id,
        }
        if channel is not None:
            data |= await self.getChannelFilter(channel, permissions)
        await self.broker.publish(channel="yepcord_events", message=data)

    async def dispatchSys(self, event: str, data: dict) -> None:
        data |= {"event": event}
        await self.broker.publish(channel="yepcord_sys_events", message=data)

    async def dispatchSub(self, user_ids: list[int], guild_id: int = None, role_id: int = None) -> None:
        await self.dispatchSys("sub", {
            "user_ids": user_ids,
            "guild_id": guild_id,
            "role_id": role_id,
        })

    async def dispatchUnsub(self, user_ids: list[int], guild_id: int = None, role_id: int = None, delete = False) -> None:
        await self.dispatchSys("unsub", {
            "user_ids": user_ids,
            "guild_id": guild_id,
            "role_id": role_id,
            "delete": delete,
        })

    async def dispatchRA(self, op: str, data: dict) -> None:
        await self.broker.publish(channel="yepcord_remote_auth", message={
            "op": op,
            **data
        })

    async def sendMessageAck(self, uid: int, channel_id: int, message_id: int, mention_count: int=None,
                             manual: bool=None) -> None:
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
        await self.dispatch(MessageAckEvent(ack), user_ids=[uid])

    async def sendPinsUpdateEvent(self, channel: Channel) -> None:
        ts = datetime(year=1970, month=1, day=1)
        if message := await c.getCore().getLastPinnedMessage(channel):
            ts = message.pinned_timestamp
        ts = ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        await self.dispatch(ChannelPinsUpdateEvent(channel.id, ts), **(await self.getChannelFilter(channel)))

    async def sendGuildEmojisUpdateEvent(self, guild: Guild) -> None:
        emojis = [await emoji.ds_json() for emoji in await c.getCore().getEmojis(guild.id)]
        await self.dispatch(GuildEmojisUpdate(guild.id, emojis), guild_id=guild.id)

    async def sendStickersUpdateEvent(self, guild: Guild) -> None:
        stickers = await c.getCore().getGuildStickers(guild)
        stickers = [await sticker.ds_json() for sticker in stickers]
        await self.dispatch(StickersUpdateEvent(guild.id, stickers), guild_id=guild.id)

    async def getChannelFilter(self, channel: Channel, permissions: int = 0) -> dict:
        if channel.type in {ChannelType.DM, ChannelType.GROUP_DM}:
            return {"user_ids": await channel.recipients.all().values_list("id", flat=True)}

        await channel.fetch_related("guild")
        return {"role_ids": [channel.guild.id]}  # TODO: return role_ids/user_ids based on channel permission overwrites


import yepcord.yepcord.ctx as c
c._getGw = lambda: GatewayDispatcher.getInstance()
