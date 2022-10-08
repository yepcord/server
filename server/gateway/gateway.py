from typing import Optional

from .events import *
from ..pubsub_client import Client
from ..enums import GatewayOp
from ..core import Core
from ..classes import UserId, Session, GuildId
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

    async def relationship_req(self, current_user, target_user):
        tClient = [u for u in self.clients if u.id == target_user and u.connected]
        cClient = [u for u in self.clients if u.id == current_user and u.connected]
        d = await self.core.getUserData(UserId(current_user)) if tClient else None
        for cl in tClient:
            await cl.esend(RelationshipAddEvent(current_user, d, 3))
        d = await self.core.getUserData(UserId(target_user)) if cClient else None
        for cl in cClient:
            await cl.esend(RelationshipAddEvent(target_user, d, 4))

    async def relationship_acc(self, current_user, target_user, channel_id):
        tClient = [u for u in self.clients if u.id == target_user and u.connected]
        cClient = [u for u in self.clients if u.id == current_user and u.connected]
        channel = await self.core.getChannel(channel_id)
        d = await self.core.getUserData(UserId(current_user)) if tClient else None
        for cl in tClient:
            await cl.esend(RelationshipAddEvent(current_user, d, 1))
            recipients = [{
                "username": d.username,
                "public_flags": d.public_flags,
                "id": str(current_user),
                "discriminator": d.s_discriminator,
                "avatar_decoration": d.avatar_decoration,
                "avatar": d.avatar
            }]
            await cl.esend(DMChannelCreateEvent(channel, recipients))
            await self.send(cl, GatewayOp.DISPATCH, t="NOTIFICATION_CENTER_ITEM_CREATE", d={
                "type": "friend_request_accepted",
                "other_user": {
                    "username": d.username,
                    "public_flags": d.public_flags,
                    "id": str(current_user),
                    "discriminator": d.s_discriminator,
                    "avatar_decoration": d.avatar_decoration,
                    "avatar": d.avatar
                },
                "id": str(current_user),
                "icon_url": f"https://127.0.0.1:8003/avatars/{current_user}/{d.avatar}.png",
                "deeplink": f"https://yepcord.ml/users/{current_user}",
                "body": f"**{d.username}** accepts your friend request",
                "acked": False
            })
        d = await self.core.getUserData(UserId(target_user)) if cClient else None
        for cl in cClient:
            await cl.esend(RelationshipAddEvent(target_user, d, 1))
            recipients = [{
                "username": d.username,
                "public_flags": d.public_flags,
                "id": str(target_user),
                "discriminator": d.s_discriminator,
                "avatar_decoration": d.avatar_decoration,
                "avatar": d.avatar
            }]
            await cl.esend(DMChannelCreateEvent(channel, recipients))

    async def relationship_del(self, current_user, target_user, type):
        cls = [u for u in self.clients if u.id == current_user and u.connected]
        for cl in cls:
            await cl.esend(RelationshipRemoveEvent(target_user, type))

    async def user_update(self, user):
        cls = [u for u in self.clients if u.id == user and u.connected]
        if not cls:
            return
        user = await self.core.getUser(user)
        data = await user.data
        settings = await user.settings
        for cl in cls:
            await cl.esend(UserUpdateEvent(user, data, settings))

    async def presence_update(self, user, status):
        user = UserId(user)
        d = await self.core.getUserData(user)
        users = await self.core.getRelatedUsers(user, only_ids=True)
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(PresenceUpdateEvent(user.id, d, status))

    async def message_create(self, users, message_obj):
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(MessageCreateEvent(message_obj))

    async def typing(self, user, channel):
        users = await self.core.getRelatedUsersToChannel(channel)
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(TypingEvent(user, channel))

    async def message_delete(self, message, channel):
        users = await self.core.getRelatedUsersToChannel(channel)
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(MessageDeleteEvent(message, channel))

    async def message_update(self, users, message_obj):
        clients = [c for c in self.clients if c.id in users and c.connected]
        for cl in clients:
            await cl.esend(MessageUpdateEvent(message_obj))

    async def message_ack(self, user, data):
        clients = [c for c in self.clients if c.id == user and c.connected]
        for cl in clients:
            await cl.esend(MessageAckEvent(data))

    async def dmchannel_create(self, users, channel_id):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        channel = await self.core.getChannel(channel_id)
        rec = [await self.core.getUserData(UserId(u)) for u in channel.recipients]
        rec = {r.uid: {
            "username": r.username,
            "public_flags": r.public_flags,
            "id": str(r.uid),
            "discriminator": r.s_discriminator,
            "avatar_decoration": r.avatar_decoration,
            "avatar": r.avatar
        } for r in rec}
        for cl in clients:
            r = rec.copy()
            if cl.id in r:
                del r[cl.id]
            r = list(r.values())
            await cl.esend(DMChannelCreateEvent(channel, r))

    async def dmchannel_update(self, users, channel_id):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        channel = await self.core.getChannel(channel_id)
        rec = [await self.core.getUserData(UserId(u)) for u in channel.recipients]
        rec = {r.uid: {
            "username": r.username,
            "public_flags": r.public_flags,
            "id": str(r.uid),
            "discriminator": r.s_discriminator,
            "avatar_decoration": r.avatar_decoration,
            "avatar": r.avatar
        } for r in rec}
        for cl in clients:
            r = rec.copy()
            del r[cl.id]
            r = list(r.values())
            await cl.esend(DMChannelUpdateEvent(channel, r))

    async def dm_recipient_add(self, users, channel_id, user):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        user = await self.core.getUserData(UserId(user))
        user = {
            "username": user.username,
            "public_flags": user.public_flags,
            "id": str(user.uid),
            "discriminator": user.s_discriminator,
            "avatar_decoration": user.avatar_decoration,
            "avatar": user.avatar
        }
        for cl in clients:
            await cl.esend(ChannelRecipientAddEvent(channel_id, user))

    async def dm_recipient_remove(self, users, channel_id, user):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        user = await self.core.getUserData(UserId(user))
        user = {
            "username": user.username,
            "public_flags": user.public_flags,
            "id": str(user.uid),
            "discriminator": user.s_discriminator,
            "avatar_decoration": user.avatar_decoration,
            "avatar": user.avatar
        }
        for cl in clients:
            await cl.esend(ChannelRecipientRemoveEvent(channel_id, user))

    async def dmchannel_delete(self, users, channel):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(DMChannelDeleteEvent(channel))

    async def channel_pins_update(self, users, channel_id):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        msg = await self.core.getLastPinnedMessage(channel_id)
        ts = datetime.utcfromtimestamp(msg.extra_data["pinned_at"] if msg else 0).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        for cl in clients:
            await cl.esend(ChannelPinsUpdateEvent(channel_id, ts))

    async def reaction_add(self, users, message_id, channel_id, user_id, emoji):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(MessageReactionAddEvent(user_id, message_id, channel_id, emoji))

    async def reaction_remove(self, users, message_id, channel_id, user_id, emoji):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(MessageReactionRemoveEvent(user_id, message_id, channel_id, emoji))

    async def guild_create(self, users, guild_obj):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(GuildCreateEvent(guild_obj))

    async def note_update(self, user, uid, note):
        if not (clients := [c for c in self.clients if c.id == user and c.connected]):
            return
        for cl in clients:
            await cl.esend(UserNoteUpdateEvent(uid, note))
            
    async def settings_proto_update(self, user, proto, stype):
        if not (clients := [c for c in self.clients if c.id == user and c.connected]):
            return
        for cl in clients:
            await cl.esend(UserSettingsProtoUpdateEvent(proto, stype))

    async def guild_update(self, users, guild_obj):
        if not (clients := [c for c in self.clients if c.id in users and c.connected]):
            return
        for cl in clients:
            await cl.esend(GuildUpdateEvent(guild_obj))

    async def relationship_add(self, current_user, target_user, type):
        if not (clients := [c for c in self.clients if c.id == current_user and c.connected]):
            return
        d = await self.core.getUserData(UserId(target_user))
        for cl in clients:
            await cl.esend(RelationshipAddEvent(current_user, d, type))

class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.mcl = Client()
        self.clients = []
        self.statuses = {}
        self.ev = GatewayEvents(self)

    async def init(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        await self.mcl.subscribe("user_events", self.mcl_eventsCallback)
        await self.mcl.subscribe("channel_events", self.mcl_eventsCallback)
        await self.mcl.subscribe("message_events", self.mcl_eventsCallback)
        await self.mcl.subscribe("guild_events", self.mcl_eventsCallback)

    async def mcl_eventsCallback(self, data: dict) -> None:
        ev = data["e"]
        func = getattr(self.ev, ev)
        if func:
            await func(**data["data"])

    async def send(self, client: GatewayClient, op: int, **data) -> None:
        r = {"op": op}
        r.update(data)
        await client.send(r)

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

    async def getFriendsPresences(self, uid: int):
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
