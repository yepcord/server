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

from json import dumps as jdumps
from typing import Optional

from .events import *
from .presences import Presences, Presence
from .utils import require_auth, get_token_type, TokenType
from ..yepcord.core import Core
from ..yepcord.ctx import getCore
from ..yepcord.enums import GatewayOp
from ..yepcord.models import Session, User, UserSettings, Bot
from ..yepcord.mq_broker import getBroker


class GatewayClient:
    def __init__(self, ws, gateway: Gateway):
        self.ws = ws
        self.gateway = gateway
        self.seq = 0
        self.sid = hex(Snowflake.makeId())[2:]
        self._connected = True

        self.z = getattr(ws, "zlib", None)
        self.id = self.user_id = None
        self.is_bot = False
        self.cached_presence: Optional[Presence] = None

    @property
    def connected(self):
        return getattr(self.ws, "ws_connected", False)

    async def send(self, data: dict):
        self.seq += 1
        data["s"] = self.seq
        if self.z:
            return await self.ws.send(self.compress(data))
        await self.ws.send_json(data)

    async def esend(self, event):
        await self.send(await event.json())

    def compress(self, json: dict):
        return self.z(jdumps(json).encode("utf8"))

    def replace(self, ws):
        self.ws = ws
        self.z = getattr(ws, "zlib", None)
        self._connected = True

    async def handle_IDENTIFY(self, data: dict) -> None:
        if self.user_id is not None:
            return await self.ws.close(4005)
        if not (token := data.get("token")) or (token_type := get_token_type(token)) is None:
            return await self.ws.close(4004)

        S = Session if token_type == TokenType.USER else Bot
        if (session := await S.from_token(token)) is None:
            return await self.ws.close(4004)

        self.id = self.user_id = session.user.id
        self.is_bot = session.user.is_bot

        settings = await session.user.settings
        self.cached_presence = await self.gateway.presences.get(self.user_id) or self.cached_presence
        if self.cached_presence is None:
            self.cached_presence = Presence(self.user_id, settings.status, settings.custom_status, [])

        await self.gateway.authenticated(self, self.cached_presence)
        await self.esend(ReadyEvent(session.user, self, getCore()))
        if not session.user.is_bot:
            guild_ids = [guild.id for guild in await getCore().getUserGuilds(session.user)]
            await self.esend(ReadySupplementalEvent(await self.gateway.getFriendsPresences(self.user_id), guild_ids))

    @require_auth
    async def handle_RESUME(self, data: dict, new_client: GatewayClient) -> None:
        if self.connected:
            await new_client.send({"op": GatewayOp.INV_SESSION})
            await new_client.send({"op": GatewayOp.RECONNECT})
            return await new_client.ws.close(4009)
        if not (token := data.get("token")) or (token_type := get_token_type(token)) is None:
            return await new_client.ws.close(4004)

        S = Session if token_type == TokenType.USER else Bot
        if (session := await S.from_token(token)) is None or self.user_id.id != session.user.id:
            return await self.ws.close(4004)

        new_client.user_id = new_client.id = self.user_id
        new_client.cached_presence = self.cached_presence
        new_client.seq = self.seq
        new_client.sid = self.sid

        self.gateway.remove_client(self)
        await self.gateway.authenticated(new_client, new_client.cached_presence)

        await new_client.send({"op": GatewayOp.DISPATCH, "t": "READY"})

    async def handle_HEARTBEAT(self, data: None) -> None:
        await self.send({"op": GatewayOp.HEARTBEAT_ACK, "t": None, "d": None})
        await self.gateway.presences.set_or_refresh(self.user_id, self.cached_presence)

    @require_auth
    async def handle_STATUS(self, data: dict) -> None:
        self.cached_presence = await self.gateway.presences.get(self.user_id) or self.cached_presence
        if self.cached_presence is None:
            settings = await UserSettings.get(id=self.user_id)
            self.cached_presence = Presence(self.user_id, settings.status, settings.custom_status, [])

        presence = self.cached_presence

        if (status := data.get("status")) and status in ["online", "idle", "offline", "dnd", "invisible"]:
            presence.status = status
        if (activities := data.get("activities")) is not None:
            presence.activities = activities

        await self.gateway.presences.set_or_refresh(self.user_id, presence, overwrite=True)
        await self.gateway.ev.presence_update(self.user_id, presence)

    @require_auth
    async def handle_LAZY_REQUEST(self, data: dict) -> None:
        if not (guild_id := int(data.get("guild_id"))): return
        if not data.get("members", True): return
        guild = await getCore().getGuild(guild_id)
        if not await getCore().getGuildMember(guild, self.user_id): return

        members = await getCore().getGuildMembers(guild)
        statuses = {}
        for member in members:
            if presence := await self.gateway.presences.get(member.user.id):
                statuses[member.user.id] = presence
            else:
                statuses[member.user.id] = Presence(member.user.id, "offline", None)
        await self.esend(GuildMembersListUpdateEvent(
            members,
            await getCore().getGuildMemberCount(guild),
            statuses,
            guild_id
        ))

    @require_auth
    async def handle_GUILD_MEMBERS(self, data: dict) -> None:
        if not (guild_id := int(data.get("guild_id")[0])): return
        guild = await getCore().getGuild(guild_id)
        if not await getCore().getGuildMember(guild, self.user_id): return

        query = data.get("query", "")
        limit = data.get("limit", 100)
        if limit > 100 or limit < 1:
            limit = 100
        members = await getCore().getGuildMembersGw(guild, query, limit, data.get("user_ids", []))
        presences = []  # TODO: add presences
        await self.esend(GuildMembersChunkEvent(members, presences, guild_id))


class GatewayEvents:
    BOTS_EVENTS_BLACKLIST = {"MESSAGE_ACK"}

    def __init__(self, gw: Gateway):
        self.gw = gw
        self.send = gw.send
        self.core = gw.core

    async def presence_update(self, user_id: int, presence: Presence):
        user = await User.get(id=user_id)
        userdata = await user.data
        users = await self.core.getRelatedUsers(user, only_ids=True)

        event = PresenceUpdateEvent(userdata, presence)

        await self.gw.broker.publish(channel="yepcord_events", message={
            "data": await event.json(),
            "event": event.NAME,
            "users": users,
            "channel_id": None,
            "guild_id": None,
            "permissions": None,
        })
        await self.sendToUsers(RawDispatchEventWrapper(event), users)

    async def sendToUsers(self, event: RawDispatchEvent, users: list[int]) -> None:
        for user_id in users:
            for client in self.gw.clients_by_user_id.get(user_id, set()):
                if not client.connected:
                    continue
                if client.is_bot and event.data.get("t") in self.BOTS_EVENTS_BLACKLIST:
                    continue
                await client.esend(event)


class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.broker = getBroker()
        self.broker.handle("yepcord_events")(self.mcl_yepcordEventsCallback)
        self.clients: set[GatewayClient] = set()
        self.clients_by_user_id: dict[int, set[GatewayClient]] = {}
        self.clients_by_session_id: dict[str, GatewayClient] = {}
        self.clients_by_socket = {}
        self.presences = Presences(self)
        self.ev = GatewayEvents(self)

    async def init(self):
        await self.broker.start()
        await self.presences.init()

    async def stop(self):
        await self.broker.close()
        await self.presences.close()

    async def mcl_yepcordEventsCallback(self, body: dict) -> None:
        event = RawDispatchEvent(body["data"])
        if body["users"] is not None:
            await self.ev.sendToUsers(event, body["users"])
        if body["channel_id"] is not None:
            # payload["permissions"]
            await self.ev.sendToUsers(event, await self.core.getRelatedUsersToChannel(body["channel_id"]))
        if body["guild_id"] is not None:
            # payload["permissions"]
            guild = await self.core.getGuild(body["guild_id"])
            await self.ev.sendToUsers(event, await self.core.getGuildMembersIds(guild))

    # noinspection PyMethodMayBeStatic
    async def send(self, client: GatewayClient, op: int, **data) -> None:
        r = {"op": op}
        r.update(data)
        await client.send(r)

    # noinspection PyMethodMayBeStatic
    async def sendws(self, ws, op: int, **data) -> None:
        r = {"op": op}
        r.update(data)
        if getattr(ws, "zlib", None):
            return await ws.send(ws.zlib(jdumps(r).encode("utf8")))
        await ws.send_json(r)

    async def add_client(self, ws) -> None:
        client = GatewayClient(ws, self)
        self.clients.add(client)
        self.clients_by_socket[ws] = client
        await client.send({"op": GatewayOp.HELLO, "t": None, "s": None, "d": {"heartbeat_interval": 45000}})

    async def authenticated(self, client: GatewayClient, presence: Presence) -> None:
        if client.user_id not in self.clients_by_user_id:
            self.clients_by_user_id[client.user_id] = set()
        self.clients_by_user_id[client.user_id].add(client)
        self.clients_by_session_id[client.sid] = client

        if presence:
            await self.ev.presence_update(client.user_id, presence)
            await self.presences.set_or_refresh(client.user_id, presence)

    def remove_client(self, client: GatewayClient) -> None:
        if client in self.clients:
            self.clients.remove(client)
        if client in self.clients_by_user_id.get(client.user_id, set()):
            self.clients_by_user_id[client.user_id].remove(client)

    async def process(self, ws, data):
        op = data["op"]
        kwargs = {}

        client = self.clients_by_socket[ws]
        if op == GatewayOp.RESUME:
            _client = self.clients_by_session_id.get(data["d"]["session_id"])
            if _client is None:
                real_client = self.clients_by_socket[ws]
                await real_client.send({"op": GatewayOp.INV_SESSION})
                await real_client.send({"op": GatewayOp.RECONNECT})
                return await ws.close(4009)
            kwargs["new_client"] = self.clients_by_socket[ws]
            client = _client

        func = getattr(client, f"handle_{GatewayOp.reversed()[op]}", None)
        if func:
            return await func(data.get("d"), **kwargs)

        print("-" * 16)
        print(f"  Unknown op code: {op}")
        print(f"  Data: {data}")

    async def disconnect(self, ws):
        client = self.clients_by_socket[ws]
        client._connected = False

    async def getFriendsPresences(self, uid: int) -> list[dict]:
        presences = []
        user = await User.get(id=uid)
        friends = await self.core.getRelationships(user)
        friends = [int(u["user_id"]) for u in friends if u["type"] == 1]
        for friend in friends:
            if presence := await self.presences.get(friend):
                presences.append({
                    "user_id": str(friend),
                    "status": presence.public_status,
                    "last_modified": int(time()*1000),
                    "client_status": {"desktop": presence.public_status} if presence.public_status != "offline" else {},
                    "activities": presence.activities
                })
                continue
            presences.append({
                "user_id": str(friend),
                "status": "offline",
                "last_modified": int(time()),
                "client_status": {},
                "activities": []
            })
        return presences
