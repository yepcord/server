from ..msg_client import Client
from ..utils import unpack_token, snowflake_timestamp, GATEWAY_OP
from ..core import Core
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

    async def send(self, data):
        self.seq += 1
        data["s"] = self.seq
        if self.z:
            return await self.ws.send(self.compress(data))
        await self.ws.send_json(data)

    def compress(self, json):
        return self.z(jdumps(json).encode("utf8"))

class Gateway:
    def __init__(self, core: Core):
        self.core = core
        self.mcl = Client()
        self.clients = []

    async def init(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        await self.mcl.subscribe("user_events", self.mcl_userEventsCallback)

    async def mcl_userEventsCallback(self, data: dict) -> None:
        ev = data["e"]
        if ev == "relationship_req":
            tClient = [u for u in self.clients if u.id == data["target_user"] and u.ws.ws_connected]
            cClient = [u for u in self.clients if u.id == data["current_user"] and u.ws.ws_connected]
            uid = data["current_user"]
            d = await self.core.getUserData(uid) if tClient else None
            for cl in tClient:
                print(f"sent RELATIONSHIP_ADD to {cl.id}")
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
                print(f"sent RELATIONSHIP_ADD to {cl.id}")
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
            tClient = [u for u in self.clients if u.id == data["target_user"] and u.ws.ws_connected]
            cClient = [u for u in self.clients if u.id == data["current_user"] and u.ws.ws_connected]
            uid = data["current_user"]
            d = await self.core.getUserData(uid) if tClient else None
            for cl in tClient:
                print(f"sent RELATIONSHIP_ADD to {cl.id}")
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
                print(f"sent RELATIONSHIP_ADD to {cl.id}")
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
        elif ev == "relationship_del":
            cls = [u for u in self.clients if u.id == data["current_user"] and u.ws.ws_connected]
            for cl in cls:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="RELATIONSHIP_REMOVE", d={
                    "type": data["type"],
                    "id": str(data["target_user"])
                })
        elif ev == "user_update":
            cls = [u for u in self.clients if u.id == data["user"] and u.ws.ws_connected]
            if not cls:
                return
            user = await self.core.getUserById(data["user"])
            data = await user.data
            settings = await user.settings
            for cl in cls:
                await self.send(cl, GATEWAY_OP.DISPATCH, t="USER_UPDATE", d={
                    "verified": True,
                    "username": data["username"],
                    "public_flags": data["public_flags"],
                    "phone": data["phone"],
                    "nsfw_allowed": True, # TODO: get from age
                    "mfa_enabled": bool(settings["mfa"]),
                    "locale": settings["locale"],
                    "id": str(user.id),
                    "flags": 0,
                    "email": user.email,
                    "discriminator": str(data["discriminator"]).rjust(4, "0"),
                    "bio": data["bio"],
                    "banner_color": data["banner_color"],
                    "banner": data["banner"],
                    "avatar_decoration": data["avatar_decoration"],
                    "avatar": data["avatar"],
                    "accent_color": data["accent_color"]
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
        s = snowflake_timestamp(user.id)
        d = datetime.utcfromtimestamp(int(s/1000)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "v": 9,
            "user": {
                "email": userdata["email"],
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
            "private_channels": [],
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
                print("close 1")
                return await ws.close(4005)
            if not (token := data["d"]["token"]):
                print("close 2")
                return await ws.close(4004)
            uid, sid, sig = unpack_token(token)
            if not (session := await self.core.getSession(uid, sid, sig)):
                print("close 3")
                return await ws.close(4004)
            cl = GatewayClient(ws, uid)
            self.clients.append(cl)
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY", s=1, d=await self._generateReadyPayload(cl))
        elif op == GATEWAY_OP.RESUME:
            if not (cl := [w for w in self.clients if w.sid == data["d"]["session_id"]]):
                await self.sendws(ws, GATEWAY_OP.INV_SESSION)
                await self.sendws(ws, GATEWAY_OP.RECONNECT)
                print("close 4")
                return await ws.close(4009)
            if not (token := data["d"]["token"]):
                print("close 5")
                return await ws.close(4004)
            cl = cl[0]
            uid, sid, sig = unpack_token(token)
            if not (session := await self.core.getSession(uid, sid, sig)):
                print("close 6")
                return await ws.close(4004)
            if cl.id != uid:
                print("close 7")
                return await ws.close(4004)
            await self.send(cl, GATEWAY_OP.DISPATCH, t="READY", s=1, d=await self._generateReadyPayload(cl))
        elif op == GATEWAY_OP.HEARTBEAT:
            if not (cl := [w for w in self.clients if w.ws == ws]):
                print("close 8")
                return await ws.close(4005)
            cl = cl[0]
            await self.send(cl, GATEWAY_OP.HEARTBEAT_ACK, t=None, d=None)

    async def sendHello(self, ws):
        await self.sendws(ws, GATEWAY_OP.HELLO, t=None, s=None, d={"heartbeat_interval": 45000})