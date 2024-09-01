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

from __future__ import annotations

import warnings
from json import dumps as jdumps
from typing import Union

from quart import Websocket
from redis.asyncio import Redis
from tortoise.expressions import Q

from .events import *
from .utils import require_auth, get_token_type, TokenType, init_redis_pool
from ..yepcord.classes.fakeredis import FakeRedis
from ..yepcord.core import Core
from ..yepcord.ctx import getCore
from ..yepcord.enums import GatewayOp
from ..yepcord.models import Session, User, UserSettings, Bot, GuildMember, Relationship, Presence
from ..yepcord.mq_broker import getBroker


class GatewayClient:
    def __init__(self, ws, gateway: Gateway):
        self.ws = ws
        self.gateway = gateway
        self.seq = 0
        self.sid = hex(Snowflake.makeId())[2:]
        self._connected = True

        self.z = getattr(ws, "zlib", None)
        self.user_id = None
        self.is_bot = False

        self._user = None

    @property
    def connected(self):
        return self._connected

    def disconnect(self) -> None:
        self._connected = False
        self.ws = None

    async def send(self, data: dict):
        self.seq += 1
        data["s"] = self.seq
        if self.z:
            return await self.ws.send(self.compress(data))
        await self.ws.send_json(data)

    async def esend(self, event):
        if not self.connected:
            return
        await self.send(await event.json())

    def compress(self, json: dict):
        return self.z(jdumps(json).encode("utf8"))

    async def get_user(self, reload: bool = False) -> User:
        if self._user is None or reload:
            self._user = await User.get(id=self.user_id)

        return self._user

    async def handle_IDENTIFY(self, data: dict) -> None:
        if self.user_id is not None:
            return await self.ws.close(4005)
        if not (token := data.get("token")) or (token_type := get_token_type(token)) is None:
            return await self.ws.close(4004)

        S = Session if token_type == TokenType.USER else Bot
        if (session := await S.from_token(token)) is None:
            return await self.ws.close(4004)

        self.user_id = session.user.id
        self.is_bot = session.user.is_bot

        await self.gateway.authenticated(self)
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
        if (session := await S.from_token(token)) is None or self.user_id != session.user.id:
            return await self.ws.close(4004)

        self.z = new_client.z
        self.ws = new_client.ws
        setattr(self.ws, "_yepcord_client", self)

        self.gateway.remove_client(new_client)
        await self.gateway.authenticated(self)

        await self.send({"op": GatewayOp.DISPATCH, "t": "READY"})

    # noinspection PyUnusedLocal
    async def handle_HEARTBEAT(self, data: None) -> None:
        await self.send({"op": GatewayOp.HEARTBEAT_ACK, "t": None, "d": None})
        if self.user_id is not None:
            await Presence.filter(user__id=self.user_id).update(updated_at=int(time()))

    @require_auth
    async def handle_STATUS(self, data: dict) -> None:
        presence, created = await Presence.get_or_create(id=self.user_id, user=await self.get_user())
        presence.updated_at = int(time())
        if created:
            settings = await UserSettings.get(user__id=self.user_id)
            presence.fill_from_settings(settings)

        if (status := data.get("status")) and status in {"online", "idle", "offline", "dnd", "invisible"}:
            presence.status = status
        if (activities := data.get("activities")) is not None:
            presence.activities = activities

        await presence.save()
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
            # TODO: rewrite with one query?
            #if presence := await self.gateway.presences.get(member.user.id):
            #    statuses[member.user.id] = presence
            #    continue
            statuses[member.user.id] = None
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
        await self.sendToUsers(RawDispatchEventWrapper(event), users, set())

    async def _send(self, client: GatewayClient, event: RawDispatchEvent) -> None:
        if client.is_bot and event.data.get("t") in self.BOTS_EVENTS_BLACKLIST:
            return
        await client.esend(event)

    async def sendToUsers(self, event: RawDispatchEvent, user_ids: list[int], sent: set) -> None:
        for user_id in user_ids:
            for client in self.gw.store.get(user_id=user_id):
                if client in sent:
                    continue
                await self._send(client, event)
                sent.add(client)

    async def sendToGuild(self, event: RawDispatchEvent, guild_id: int, exclude_users: set[int], sent: set) -> None:
        for client in self.gw.store.get(guild_id=guild_id):
            if client.user_id in exclude_users or client in sent:
                continue
            await self._send(client, event)
            sent.add(client)

    async def sendToRoles(self, event: RawDispatchEvent, role_ids: list[int], exclude_users: set[int], sent: set) -> None:
        for role_id in role_ids:
            for client in self.gw.store.get(role_id=role_id):
                if client.user_id in exclude_users or client in sent:
                    continue
                await self._send(client, event)
                sent.add(client)


class WsStore:
    def __init__(self):
        self.by_sess_id: dict[str, GatewayClient] = {}
        self.by_user_id: dict[int, set[GatewayClient]] = {}
        self.by_guild_id: dict[int, set[GatewayClient]] = {}
        self.by_role_id: dict[int, set[GatewayClient]] = {}

    def get(self, user_id: int = None, session_id: str = None, guild_id: int = None,
            role_id: int = None) -> set[GatewayClient]:
        if user_id is not None:
            return self.by_user_id.get(user_id, set())
        elif session_id is not None:
            if client := self.by_sess_id.get(session_id, None):
                return {client}
        elif guild_id is not None:
            return self.by_guild_id.get(guild_id, set())
        elif role_id is not None:
            return self.by_role_id.get(role_id, set())
        return set()

    def subscribe(self, guild_id: int = None, role_id: int = None, *user_ids: int) -> None:
        if guild_id is not None:
            if guild_id not in self.by_guild_id:
                self.by_guild_id[guild_id] = set()
            for user_id in user_ids:
                self.by_guild_id[guild_id].update(self.get(user_id))
            self.subscribe(None, guild_id, *user_ids)

        if role_id is not None:
            if role_id not in self.by_role_id:
                self.by_role_id[role_id] = set()
            for user_id in user_ids:
                self.by_role_id[role_id].update(self.get(user_id))

    def unsubscribe(self, guild_id: int = None, role_id: int = None, *user_ids: int, delete: bool = False) -> None:
        if guild_id is not None:
            if guild_id not in self.by_guild_id:
                return
            if delete:
                del self.by_guild_id[guild_id]
            else:
                for user_id in user_ids:
                    self.by_guild_id[guild_id].difference_update(self.get(user_id))
            self.unsubscribe(role_id=guild_id, *user_ids, delete=delete)

        if role_id is not None:
            if role_id not in self.by_role_id:
                return
            if delete:
                del self.by_role_id[role_id]
            else:
                for user_id in user_ids:
                    self.by_role_id[role_id].difference_update(self.get(user_id))


class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.broker = getBroker()
        self.broker.subscriber("yepcord_events")(self.mcl_yepcordEventsCallback)
        self.broker.subscriber("yepcord_sys_events")(self.mcl_yepcordSysEventsCallback)
        self.store = WsStore()
        self.ev = GatewayEvents(self)

        self.redis: Union[Redis, FakeRedis, None] = None

    async def init(self):
        await self.broker.start()

        def _init_fake_redis():
            self.redis = FakeRedis()
            self.redis.run()

        try:
            self.redis = await init_redis_pool()
            if self.redis is None:
                _init_fake_redis()
        except Exception as e:
            warnings.warn(f"Failed to connect to redis pool: {e.__class__.__name__}: {e}.")
            _init_fake_redis()

    async def stop(self):
        await self.broker.close()
        await self.redis.close()

    async def mcl_yepcordEventsCallback(self, body: dict) -> None:
        event = RawDispatchEvent(body["data"])
        sent = set()
        if body["user_ids"] is not None:
            await self.ev.sendToUsers(event, body["user_ids"], sent)
        if body["guild_id"] is not None:
            await self.ev.sendToGuild(event, body["guild_id"], set(body.get("exclude", [])), sent)
        if body["role_ids"] is not None:
            await self.ev.sendToRoles(event, body["role_ids"], set(body.get("exclude", [])), sent)
        if body["session_id"] is not None:
            if client := self.store.get(session_id=body["session_id"]):
                await list(client)[0].esend(event)

    async def mcl_yepcordSysEventsCallback(self, body: dict) -> None:
        if body["event"] not in {"sub", "unsub"}:
            return

        if (guild_id := body["guild_id"]) is not None:
            kw = {} if body["event"] == "sub" else {"delete": body["delete"]}
            func = self.store.subscribe if body["event"] == "sub" else self.store.unsubscribe
            func(guild_id, *body["user_ids"], **kw)

        if (role_id := body["role_id"]) is not None:
            kw = {} if body["event"] == "sub" else {"delete": body["delete"]}
            func = self.store.subscribe if body["event"] == "sub" else self.store.unsubscribe
            func(role_id=role_id, *body["user_ids"], **kw)

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

    async def add_client(self, ws: Websocket) -> None:
        client = GatewayClient(ws, self)
        setattr(ws, "_yepcord_client", client)
        await client.send({"op": GatewayOp.HELLO, "t": None, "s": None, "d": {"heartbeat_interval": 45000}})

    async def authenticated(self, client: GatewayClient) -> None:
        if client.user_id not in self.store.by_user_id:
            self.store.by_user_id[client.user_id] = set()
        self.store.by_user_id[client.user_id].add(client)
        self.store.by_sess_id[client.sid] = client

        user = await client.get_user()

        for member in await GuildMember.filter(user=user).select_related("guild"):
            self.store.subscribe(member.guild.id, None, client.user_id)
            for role in await member.roles.all():
                self.store.subscribe(None, role.id, client.user_id)

        presence, created = await Presence.get_or_create(id=user.id, user=user)
        if created or time() - presence.updated_at > Config.GATEWAY_KEEP_ALIVE_DELAY * 10:
            settings = await user.settings
            presence.fill_from_settings(settings)

        presence.updated_at = int(time())
        await presence.save()

        if presence.public_status != "offline":
            await self.ev.presence_update(client.user_id, presence)

    def remove_client(self, client: GatewayClient) -> None:
        if client in self.store.get(user_id=client.user_id):
            self.store.by_user_id[client.user_id].remove(client)

    async def process(self, ws: Websocket, data: dict):
        op = data["op"]
        kwargs = {}

        client: GatewayClient = getattr(ws, "_yepcord_client")
        if op == GatewayOp.RESUME:
            _client = list(self.store.get(session_id=data["d"]["session_id"]))
            if not _client:
                await client.send({"op": GatewayOp.INV_SESSION})
                await client.send({"op": GatewayOp.RECONNECT})
                return await ws.close(4009)
            kwargs["new_client"] = client
            client = _client[0]

        func = getattr(client, f"handle_{GatewayOp.reversed()[op]}", None)
        if func:
            return await func(data.get("d"), **kwargs)

        print("-" * 16)
        print(f"  Unknown op code: {op}")
        print(f"  Data: {data}")

    @staticmethod
    async def disconnect(ws: Websocket):
        getattr(ws, "_yepcord_client").disconnect()

    @staticmethod
    async def getFriendsPresences(user_id: int) -> list[dict[str, ...]]:
        presences = []
        async for rel in Relationship.filter(Q(type=1) & (Q(from_user__id=user_id) | Q(to_user__id=user_id))) \
                .select_related("from_user", "to_user"):
            other = rel.other_user(user_id)
            if presence := await Presence.get_or_none(
                    user=other, updated_at__gt=int(time() - Config.GATEWAY_KEEP_ALIVE_DELAY * 1.25)
            ):
                presences.append(presence.ds_json())
                continue
            presences.append(Presence.ds_json_offline())

        return presences
