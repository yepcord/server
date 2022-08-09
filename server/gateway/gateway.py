from ..msg_client import Client
from ..utils import unpack_token, snowflake_timestamp, GATEWAY_OP
from ..core import Core
from ..classes import UserId
from os import urandom
from json import dumps as jdumps
from datetime import datetime
from time import time

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

class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.mcl = Client()
        self.clients = []
        self.statuses = {}

    async def init(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        await self.mcl.subscribe("user_events", self.mcl_userEventsCallback)

    async def mcl_userEventsCallback(self, data: dict) -> None:
        ev = data["e"]
        if ev == "relationship_req":
            tClient = [u for u in self.clients if u.id == data["target_user"] and u.connected]
            cClient = [u for u in self.clients if u.id == data["current_user"] and u.connected]
            uid = data["current_user"]
            d = await self.core.getUserData(uid) if tClient else None
            for cl in tClient:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_ADD", d={
                    "user": {
                        "username": d["username"],
                        "public_flags": d["public_flags"],
                        "id": str(uid),
                        "discriminator": str(d["discriminator"]).rjust(4, "0"),
                        "avatar_decoration": d["avatar_decoration"],
                        "avatar": d["avatar"]
                    },
                    "type": 3, "should_notify": True, "nickname": None, "id": str(uid)
                })
            uid = data["target_user"]
            d = await self.core.getUserData(uid) if cClient else None
            for cl in cClient:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_ADD", d={
                    "user": {
                        "username": d["username"],
                        "public_flags": d["public_flags"],
                        "id": str(uid),
                        "discriminator": d["discriminator"],
                        "avatar_decoration": d["avatar_decoration"],
                        "avatar": d["avatar"]
                    },
                    "type": 4, "nickname": None, "id": str(uid)
                })
        elif ev == "relationship_acc":
            tClient = [u for u in self.clients if u.id == data["target_user"] and u.connected]
            cClient = [u for u in self.clients if u.id == data["current_user"] and u.connected]
            channel = await self.core.getChannel(data["channel_id"])
            cinfo = await channel.info
            uid = data["current_user"]
            d = await self.core.getUserData(uid) if tClient else None
            for cl in tClient:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_ADD", d={
                    "user": {
                            "username": d["username"],
                            "public_flags": d["public_flags"],
                            "id": str(uid),
                            "discriminator": str(d["discriminator"]).rjust(4, "0"),
                            "avatar_decoration": d["avatar_decoration"],
                            "avatar": d["avatar"]
                        },
                    "type": 1, "should_notify": True, "nickname": None, "id": str(uid)
                })
                await self.send(cl, GATEWAY_OP.DISPATCH, t="CHANNEL_CREATE", d={
                    "type": 1,
                    "recipients": [{
                        "username": d["username"],
                         "public_flags": d["public_flags"],
                         "id": str(uid),
                         "discriminator": str(d["discriminator"]).rjust(4, "0"),
                         "avatar_decoration": d["avatar_decoration"],
                         "avatar": d["avatar"]
                    }],
                    "last_message_id": str(cinfo["last_message_id"]),
                    "id": data["channel_id"]
                })
                await self.send(cl, GATEWAY_OP.DISPATCH, t="NOTIFICATION_CENTER_ITEM_CREATE", d={
                    "type": "friend_request_accepted",
                    "other_user": {
                        "username": d["username"],
                            "public_flags": d["public_flags"],
                            "id": str(uid),
                            "discriminator": str(d["discriminator"]).rjust(4, "0"),
                            "avatar_decoration": d["avatar_decoration"],
                            "avatar": d["avatar"]
                    },
                    "id": str(uid),
                    "icon_url": f"https://127.0.0.1:8003/avatars/{uid}/{d['avatar']}.png",
                    "deeplink": f"https://discord.com/users/{uid}",
                    "body": f"**{d['username']}** accepts your friend request",
                    "acked": False
                })
            uid = data["target_user"]
            d = await self.core.getUserData(uid) if cClient else None
            for cl in cClient:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_ADD", d={
                    "user": {
                            "username": d["username"],
                            "public_flags": d["public_flags"],
                            "id": str(uid),
                            "discriminator": str(d["discriminator"]).rjust(4, "0"),
                            "avatar_decoration": d["avatar_decoration"],
                            "avatar": d["avatar"]
                        },
                    "type": 1, "nickname": None, "id": str(uid)
                })
                await self.send(cl, GATEWAY_OP.DISPATCH, t="CHANNEL_CREATE", d={
                    "type": 1,
                    "recipients": [{
                        "username": d["username"],
                        "public_flags": d["public_flags"],
                        "id": str(uid),
                        "discriminator": str(d["discriminator"]).rjust(4, "0"),
                        "avatar_decoration": d["avatar_decoration"],
                        "avatar": d["avatar"]
                    }],
                    "last_message_id": str(cinfo["last_message"]),
                    "id": data["channel_id"]
                })
        elif ev == "relationship_del":
            cls = [u for u in self.clients if u.id == data["current_user"] and u.connected]
            for cl in cls:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_REMOVE", d={
                    "type": data["type"],
                    "id": str(data["target_user"])
                })
        elif ev == "user_update":
            cls = [u for u in self.clients if u.id == data["user"] and u.connected]
            if not cls:
                return
            user = await self.core.getUserById(data["user"])
            d = await user.data
            settings = await user.settings
            for cl in cls:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="USER_UPDATE", d={
                    "verified": True,
                    "username": d["username"],
                    "public_flags": d["public_flags"],
                    "phone": d["phone"],
                    "nsfw_allowed": True, # TODO: get from age
                    "mfa_enabled": bool(settings["mfa"]),
                    "locale": settings["locale"],
                    "id": str(user.id),
                    "flags": 0,
                    "email": user.email,
                    "discriminator": str(d["discriminator"]).rjust(4, "0"),
                    "bio": d["bio"],
                    "banner_color": d["banner_color"],
                    "banner": d["banner"],
                    "avatar_decoration": d["avatar_decoration"],
                    "avatar": d["avatar"],
                    "accent_color": d["accent_color"]
                })
        elif ev == "presence_update":
            user = UserId(data["user"])
            d = await self.core.getUserData(user.id)
            users = await self.core.getRelatedUsers(user, only_ids=True)
            clients = [c for c in self.clients if c.id in users and c.connected]
            st = self.statuses.get(user.id)
            if not st:
                self.statuses[user.id] = st = ClientStatus(user.id, {"status": "online"})
            st.status.update(data["status"])
            st = st.status
            for cl in clients:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="PRESENCE_UPDATE", d={
                    "user": {
                        "username": d["username"],
                        "public_flags": d["public_flags"],
                        "id": str(user.id),
                        "discriminator": str(d["discriminator"]).rjust(4, "0"),
                        "avatar": d["avatar"]
                    },
                    "status": st["status"],
                    "last_modified": st.get("last_modified", int(time()*1000)),
                    "client_status": {} if st["status"] == "offline" else {"desktop": st["status"]},
                    "activities": st.get("activities", [])
                })

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
        user = await self.core.getUserById(client.id)
        userdata = await user.data
        settings = await user.settings
        if settings["status"] == "offline":
            settings["status"] = "invisible"
        s = snowflake_timestamp(user.id)
        d = datetime.utcfromtimestamp(int(s/1000)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "v": 9,
            "user": {
                "email": user.email,
                "phone": userdata["phone"],
                "username": userdata["username"],
                "discriminator": str(userdata["discriminator"]).rjust(4, "0"),
                "bio": userdata["bio"],
                "avatar": userdata["avatar"],
                "avatar_decoration": userdata["avatar_decoration"],
                "accent_color": userdata["accent_color"],
                "banner": userdata["banner"],
                "banner_color": userdata["banner_color"],
                "premium": True,
                "premium_type": 2,
                "premium_since": d,
                "verified": True,
                "purchased_flags": 0,
                "nsfw_allowed": True, # TODO: check
                "mobile": True, # TODO: check
                "mfa_enabled": bool(settings["mfa"]), # TODO: get from db
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
            "user_settings": settings,
            "user_settings_proto": "CgIYBCILCgkRAAEAAAAAAIAqDTIDCNgEOgIIAUICCAEyL0oCCAFSAggBWgIIAWICCAFqAggBcgIIAXoAggECCAGKAQCaAQIIAaIBAKoBAggBQhBCAggBSgIIAVIAWgIIDmIAUgIaAFoOCggKBm9ubGluZRoCCAFiEwoECgJydRILCMz+/////////wFqAggBcgA="
        }

    async def process(self, ws, data):
        op = data["op"]
        if op == GATEWAY_OP.IDENTIFY:
            if [w for w in self.clients if w.ws == ws]:
                return await ws.close(4005)
            if not (token := data["d"]["token"]):
                return await ws.close(4004)
            uid, sid, sig = unpack_token(token)
            if not await self.core.getSession(uid, sid, sig):
                return await ws.close(4004)
            cl = GatewayClient(ws, uid)
            self.clients.append(cl)
            self.statuses[cl.id] = ClientStatus(cl.id, await self.core.getUserPresence(cl.id))
            await self.mcl_userEventsCallback({"e": "presence_update", "user": cl.id, "status": {"status": "online"}})
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
            uid, sid, sig = unpack_token(token)
            if not await self.core.getSession(uid, sid, sig):
                return await ws.close(4004)
            if cl.id != uid:
                return await ws.close(4004)
            cl.replace(ws)
            self.statuses[cl.id] = st = ClientStatus(cl.id, await self.core.getUserPresence(cl.id))
            await self.mcl_userEventsCallback({"e": "presence_update", "user": cl.id, "status": st.status})
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY", d=await self._generateReadyPayload(cl))
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
            await self.core.updatePresence(cl.id, {"status": "offline"})
            await self.mcl_userEventsCallback({"e": "presence_update", "user": cl.id, "status": {"status": "offline"}})
