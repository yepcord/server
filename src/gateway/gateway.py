from typing import Optional

from .events import *
from ..yepcord.pubsub_client import Client
from ..yepcord.enums import GatewayOp
from ..yepcord.core import Core
from ..yepcord.classes.user import UserId, Session
from ..yepcord.classes.guild import GuildId
from os import urandom
from json import dumps as jdumps


class GatewayClient:
    def __init__(self, ws, uid):
        self.ws = ws
        self.id = uid
        self.seq = 0
        self.sid = urandom(16).hex()
        self.z = getattr(ws, "zlib", None)
        self._connected = True

    @property
    def connected(self):
        return self._connected and getattr(self.ws, "ws_connected", False)

    async def send(self, data):
        self.seq += 1
        data["s"] = self.seq
        if self.z:
            return await self.ws.send(self.compress(data))
        await self.ws.send_json(data)

    async def esend(self, event):
        await self.send(await event.json())

    def compress(self, json):
        return self.z(jdumps(json).encode("utf8"))

    def replace(self, ws):
        self.ws = ws
        self.z = getattr(ws, "zlib", None)
        self._connected = True


class ClientStatus:
    def __init__(self, uid, status, activities):
        self.id = uid
        self._status = status
        self._activities = activities
        self._modified = int(time())

    @property
    def status(self):
        return self._status if self._status != "invisible" else "offline"

    @property
    def activities(self):
        return self._activities if self.status != "offline" else []

    @property
    def last_modified(self):
        return self._modified

    def setStatus(self, status):
        self._modified = int(time())
        if status not in ["online", "idle", "offline", "dnd", "invisible"]:
            return
        self._status = status

    def setActivities(self, activities):
        self._modified = int(time())
        self._activities = activities

    @property
    def client_status(self):
        return {"desktop": self.status} if self.status != "offline" else {}

    @staticmethod
    def custom_status(status):
        if status is None:
            return []
        return [{
            'name': 'Custom Status',
            'type': 4,
            'state': status["text"],
            'emoji': {'id': None, 'name': status["emoji_name"], 'animated': False} if "emoji_name" in status else {}
        }]

    def __getitem__(self, item):
        return getattr(self, item, None)

    def get(self, item, default=None):
        if hasattr(self, item):
            return self.__getitem__(item)
        return default


class GatewayEvents:
    def __init__(self, gw):
        self.gw = gw
        self.send = gw.send
        self.core = gw.core
        self.clients = gw.clients

    async def presence_update(self, user_id, status):
        user = UserId(user_id)
        d = await self.core.getUserData(user)
        users = await self.core.getRelatedUsers(user, only_ids=True)
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(PresenceUpdateEvent(d, status))

    async def sendToUsers(self, event: RawDispatchEvent, users: list[int]) -> None:
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(event)

class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.mcl = Client()
        self.clients = []
        self.statuses = {}
        self.ev = GatewayEvents(self)

    async def init(self):
        await self.mcl.start(f"ws://{Config('PS_ADDRESS')}:5050")
        await self.mcl.subscribe("yepcord_events", self.mcl_yepcordEventsCallback)

    async def mcl_yepcordEventsCallback(self, payload: dict) -> None:
        event = RawDispatchEvent(payload["data"])
        if payload["users"] is not None:
            await self.ev.sendToUsers(event, payload["users"])
        if payload["channel_id"] is not None:
            # payload["permissions"]
            await self.ev.sendToUsers(event, await self.core.getRelatedUsersToChannel(payload["channel_id"]))
        if payload["guild_id"] is not None:
            # payload["permissions"]
            await self.ev.sendToUsers(event, await self.core.getGuildMembersIds(GuildId(payload["guild_id"])))

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

    async def process(self, ws, data):
        op = data["op"]
        if op == GatewayOp.IDENTIFY:
            if [w for w in self.clients if w.ws == ws]:
                return await ws.close(4005)
            if not (token := data["d"]["token"]):
                return await ws.close(4004)
            sess = Session.from_token(token)
            if not sess or not await self.core.validSession(sess):
                return await ws.close(4004)
            cl = GatewayClient(ws, sess.id)
            self.clients.append(cl)
            settings = await self.core.getUserSettings(UserId(cl.id))
            self.statuses[cl.id] = st = ClientStatus(cl.id, settings.status, ClientStatus.custom_status(settings.custom_status))
            await self.ev.presence_update(cl.id, st)
            await cl.esend(ReadyEvent(await self.core.getUser(cl.id), cl, self.core))
            guild_ids = [guild.id for guild in await self.core.getUserGuilds(sess)]
            await cl.esend(ReadySupplementalEvent(await self.getFriendsPresences(cl.id), guild_ids))
        elif op == GatewayOp.RESUME:
            if not (cl := [w for w in self.clients if w.sid == data["d"]["session_id"]]):
                await self.sendws(ws, GatewayOp.INV_SESSION)
                await self.sendws(ws, GatewayOp.RECONNECT)
                return await ws.close(4009)
            if not (token := data["d"]["token"]):
                return await ws.close(4004)
            cl = cl[0]
            sess = Session.from_token(token)
            if not sess or not await self.core.validSession(sess):
                return await ws.close(4004)
            if cl.id != sess.id:
                return await ws.close(4004)
            cl.replace(ws)
            settings = await self.core.getUserSettings(UserId(cl.id))
            self.statuses[cl.id] = st = ClientStatus(cl.id, settings.status, ClientStatus.custom_status(settings.custom_status))
            await self.ev.presence_update(cl.id, st)
            await self.send(cl, GatewayOp.DISPATCH, t="READY")
        elif op == GatewayOp.HEARTBEAT:
            if not (cl := await self.getClientFromSocket(ws)): return
            await self.send(cl, GatewayOp.HEARTBEAT_ACK, t=None, d=None)
        elif op == GatewayOp.STATUS:
            d = data["d"]
            if not (cl := await self.getClientFromSocket(ws)): return
            if not (st := self.statuses.get(cl.id)):
                settings = await self.core.getUserSettings(UserId(cl.id))
                self.statuses[cl.id] = st = ClientStatus(cl.id, settings.status, ClientStatus.custom_status(settings.custom_status))
            if status := d.get("status"):
                st.setStatus(status)
            if activities := d.get("activities"):
                st.setActivities(activities)
            await self.ev.presence_update(cl.id, st)
        elif op == GatewayOp.LAZY_REQUEST:
            d = data["d"]
            if not (guild_id := int(d.get("guild_id"))): return
            if not (cl := await self.getClientFromSocket(ws)): return
            if d.get("members", True):
                members = await self.core.getGuildMembers(GuildId(guild_id))
                statuses = {}
                for member in members:
                    if member.user_id in self.statuses:
                        statuses[member.user_id] = self.statuses[member.user_id]
                    else:
                        statuses[member.user_id] = ClientStatus(member.user_id, "offline", None)
                await cl.esend(GuildMembersListUpdateEvent(
                    members,
                    await self.core.getGuildMemberCount(GuildId(guild_id)),
                    statuses,
                    guild_id
                ))
        elif op == GatewayOp.GUILD_MEMBERS:
            d = data["d"]
            if not (guild_id := int(d.get("guild_id")[0])): return
            if not (cl := await self.getClientFromSocket(ws)): return
            query = d.get("query", "")
            limit = d.get("limit", 100)
            if limit > 100 or limit < 1:
                limit = 100
            members = await self.core.getGuildMembersGw(GuildId(guild_id), query, limit)
            presences = []  # TODO: add presences
            await cl.esend(GuildMembersChunkEvent(members, presences, guild_id))
        else:
            print("-"*16)
            print(f"  Unknown op code: {op}")
            print(f"  Data: {data}")

    async def getClientFromSocket(self, ws) -> Optional[GatewayClient]:
        if cl := [w for w in self.clients if w.ws == ws]:
            return cl[0]
        await ws.close(4005)

    async def sendHello(self, ws):
        await self.sendws(ws, GatewayOp.HELLO, t=None, s=None, d={"heartbeat_interval": 45000})

    async def disconnect(self, ws):
        if not (cl := [w for w in self.clients if w.ws == ws]):
            return
        cl = cl[0]
        cl._connected = False
        if not [w for w in self.clients if w.id == cl.id and w != cl]:
            await self.ev.presence_update(cl.id, {"status": "offline"})

    async def getFriendsPresences(self, uid: int) -> list[dict]:
        pr = []
        friends = await self.core.getRelationships(UserId(uid))
        friends = [int(u["user_id"]) for u in friends if u["type"] == 1]
        for friend in friends:
            if status := self.statuses.get(friend):
                pr.append({
                    "user_id": str(friend),
                    "status": status.status,
                    "last_modified": status.last_modified,
                    "client_status": status.client_status,
                    "activities": status.activities
                })
                continue
            pr.append({
                "user_id": str(friend),
                "status": "offline",
                "last_modified": int(time()),
                "client_status": {},
                "activities": []
            })
        return pr
