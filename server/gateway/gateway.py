from .events import *
from ..msg_client import Client
from ..utils import snowflake_timestamp, GATEWAY_OP
from ..core import Core
from ..classes import UserId, Session
from os import urandom
from json import dumps as jdumps
from datetime import datetime

class VoiceStatus:
    def __init__(self):
        channel_id = None
        guild_id = None
        self_deaf = False
        self_mute = False
        self_video = False

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
        await self.send(event.json)

    def compress(self, json):
        return self.z(jdumps(json).encode("utf8"))

    def replace(self, ws):
        self.ws = ws
        self.z = getattr(ws, "zlib", None)
        self._connected = True

class ClientStatus:
    def __init__(self, uid, status):
        self.id = uid
        self.status = status

class GatewayEvents:
    def __init__(self, gw):
        self.gw = gw
        self.send = gw.send
        self.core = gw.core
        self.clients = gw.clients
        self.statuses = gw.statuses

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
        cinfo = await channel.info
        d = await self.core.getUserData(UserId(current_user)) if tClient else None
        for cl in tClient:
            await cl.esend(RelationshipAddEvent(current_user, d, 1))
            recipients = [{
                "username": d.username,
                "public_flags": d.public_flags,
                "id": str(current_user),
                "discriminator": str(d.discriminator).rjust(4, "0"),
                "avatar_decoration": d.avatar_decoration,
                "avatar": d.avatar
            }]
            await cl.esend(DMChannelCreate(channel_id, recipients, 1, cinfo))
            await self.send(cl, GATEWAY_OP.DISPATCH, t="NOTIFICATION_CENTER_ITEM_CREATE", d={
                "type": "friend_request_accepted",
                "other_user": {
                    "username": d.username,
                    "public_flags": d.public_flags,
                    "id": str(current_user),
                    "discriminator": str(d.discriminator).rjust(4, "0"),
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
                "discriminator": str(d.discriminator).rjust(4, "0"),
                "avatar_decoration": d.avatar_decoration,
                "avatar": d.avatar
            }]
            await cl.esend(DMChannelCreate(channel_id, recipients, 1, cinfo))

    async def relationship_del(self, current_user, target_user, type):
        cls = [u for u in self.clients if u.id == current_user and u.connected]
        for cl in cls:
            await cl.esend(RelationshipRemoveEvent(target_user, type))

    async def user_update(self, user):
        cls = [u for u in self.clients if u.id == user and u.connected]
        if not cls:
            return
        user = await self.core.getUserById(user)
        data = await user.data
        settings = await user.settings
        for cl in cls:
            await cl.esend(UserUpdateEvent(user, data, settings))

    async def presence_update(self, user, status):
        user = UserId(user)
        d = await self.core.getUserData(user)
        users = await self.core.getRelatedUsers(user, only_ids=True)
        clients = [c for c in self.clients if c.id in users and c.connected]
        st = self.statuses.get(user.id)
        if not st:
            self.statuses[user.id] = st = ClientStatus(user.id, {"status": "online"})
        st.status.update(status)
        st = st.status
        for cl in clients:
            await cl.esend(PresenceUpdateEvent(user.id, d, st))

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
        await self.mcl.subscribe("message_events", self.mcl_eventsCallback)

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

    async def _generateReadyPayload(self, client):
        user = await self.core.getUser(client.id)
        userdata = await user.data
        settings = await user.settings
        s = snowflake_timestamp(user.id)
        d = datetime.utcfromtimestamp(int(s/1000)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "v": 9,
            "user": {
                "email": user.email,
                "phone": userdata.phone,
                "username": userdata.username,
                "discriminator": str(userdata.discriminator).rjust(4, "0"),
                "bio": userdata.bio,
                "avatar": userdata.avatar,
                "avatar_decoration": userdata.avatar_decoration,
                "accent_color": userdata.accent_color,
                "banner": userdata.banner,
                "banner_color": userdata.banner_color,
                "premium": True,
                "premium_type": 2,
                "premium_since": d,
                "verified": True,
                "purchased_flags": 0,
                "nsfw_allowed": True, # TODO: check
                "mobile": True, # TODO: check
                "mfa_enabled": settings.mfa,
                "id": str(client.id),
                "flags": 0,
            },
            "users": await self.core.getRelatedUsers(user),
            "guilds": [],
            "session_id": client.sid,
            "presences": [],
            "relationships": await self.core.getRelationships(user),
            "connected_accounts": [],
            "consents": {
                "personalization": {
                    "consented":  True
                }
            },
            "country_code": "US",
            "experiments": [],
            "friend_suggestion_count": 0,
            "geo_ordered_rtc_regions": ["yepcord"],
            "guild_experiments": [],
            "guild_join_requests": [],
            "merged_members": [],
            "private_channels": await self.core.getPrivateChannels(user),
            "read_state": {
                "version": 871,
                "partial":  False,
                "entries": []
            },
            "resume_gateway_url": "wss://127.0.0.1/",
            "session_type": "normal",
            "sessions": [{
                "status": "online",
                "session_id": client.sid,
                "client_info": {
                    "version": 0,
                    "os": "windows",
                    "client": "web"
                },
                "activities": []
            }],
            "tutorial": None,
            "user_guild_settings": {
                "version": 0,
                "partial": False,
                "entries": []
            },
            "user_settings": settings.to_json(),
            "user_settings_proto": "CgIYBCILCgkRAAEAAAAAAIAqDTIDCNgEOgIIAUICCAEyL0oCCAFSAggBWgIIAWICCAFqAggBcgIIAXoAggECCAGKAQCaAQIIAaIBAKoBAggBQhBCAggBSgIIAVIAWgIIDmIAUgIaAFoOCggKBm9ubGluZRoCCAFiEwoECgJydRILCMz+/////////wFqAggBcgA="
        }

    async def process(self, ws, data):
        op = data["op"]
        if op == GATEWAY_OP.IDENTIFY:
            if [w for w in self.clients if w.ws == ws]:
                return await ws.close(4005)
            if not (token := data["d"]["token"]):
                return await ws.close(4004)
            sess = Session.from_token(token)
            if not sess or not await self.core.validSession(sess):
                return await ws.close(4004)
            cl = GatewayClient(ws, sess.id)
            self.clients.append(cl)
            self.statuses[cl.id] = ClientStatus(cl.id, await self.core.getUserPresence(cl.id))
            await self.ev.presence_update(cl.id, {"status": "online"})
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY", d=await self._generateReadyPayload(cl))
            fr = await self.core.getFriendsPresences(cl.id)
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY_SUPPLEMENTAL", d={
                "merged_presences": {
                    "guilds": [], # TODO
                    "friends": fr
                },
                "merged_members": [], # TODO
                "guilds": [] # TODO
            })
        elif op == GATEWAY_OP.RESUME:
            if not (cl := [w for w in self.clients if w.sid == data["d"]["session_id"]]):
                await self.sendws(ws, GATEWAY_OP.INV_SESSION)
                await self.sendws(ws, GATEWAY_OP.RECONNECT)
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
            self.statuses[cl.id] = st = ClientStatus(cl.id, await self.core.getUserPresence(cl.id))
            await self.ev.presence_update(cl.id, st.status)
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY")
        elif op == GATEWAY_OP.HEARTBEAT:
            if not (cl := [w for w in self.clients if w.ws == ws]):
                return await ws.close(4005)
            cl = cl[0]
            await self.send(cl, GATEWAY_OP.HEARTBEAT_ACK, t=None, d=None)

    async def sendHello(self, ws):
        await self.sendws(ws, GATEWAY_OP.HELLO, t=None, s=None, d={"heartbeat_interval": 45000})

    async def disconnect(self, ws):
        if not (cl := [w for w in self.clients if w.ws == ws]):
            return
        cl = cl[0]
        cl._connected = False
        if not [w for w in self.clients if w.id == cl.id and w != cl]:
            #await self.core.updatePresence(cl.id, {"status": "offline"})
            await self.ev.presence_update(cl.id, {"status": "offline"})
