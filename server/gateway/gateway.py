from ..msg_client import Client
from ..utils import unpack_token
from os import urandom
from json import dumps as jdumps

class OP:
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    STATUS = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    GUILD_MEMBERS = 8
    INV_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

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
    def __init__(self, core):
        self.core = core
        self.mcl = Client()
        self.clients = []

    async def init(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        await self.mcl.subscribe("gateway", self.mclCallback)

    async def mclCallback(self, data):
        ...

    async def send(self, client, op, **data):
        r = {"op": op}
        r.update(data)
        await client.send(r)

    async def sendws(self, ws, op, **data):
        r = {"op": op}
        r.update(data)
        if getattr(ws, "zlib", None):
            return await ws.send(ws.zlib(jdumps(r).encode("utf8")))
        await ws.send_json(r)

    async def _generateReadyPayload(self, client):
        user = await self.core.getUserById(client.id)
        userdata = await user.data
        settings = await user.settings
        settings["activity_restricted_guild_ids"] = []
        settings["friend_source_flags"] = {"all": True}
        settings["guild_positions"] = []
        settings["guild_folders"] = []
        settings["restricted_guilds"] = []
        return {
            "v": 9,
            "user": {
                "email": userdata["email"],
                "phone": userdata["phone"],
                "username": userdata["username"],
                "discriminator": str(userdata["discriminator"]).rjust(4, "0"), # TODO: get from db
                "bio": userdata["bio"],
                "avatar": userdata["avatar"],
                "avatar_decoration": userdata["avatar_decoration"],
                "accent_color": userdata["accent_color"],
                "banner": userdata["banner"],
                "banner_color": userdata["banner_color"],
                "premium": userdata["premium"],
                "verified":  True,
                "purchased_flags": 0,
                "nsfw_allowed":  True, # TODO: check
                "mobile":  True, # TODO: check
                "mfa_enabled":  False, # TODO: get from db
                "id": str(client.id),
                "flags": 0,
            },
            "users": [],
            "guilds": [],
            "session_id": client.sid,
            "presences": [],
            "relationships": [],
            "analytics_token": "MA.AA",
            "auth_session_id_hash": "zZDamQ9DHuByuVpwZS7vfCHr5R6XSjCWEFexmMY8MuU=",
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
        if op == OP.IDENTIFY:
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
            await self.send(cl, OP.DISPATCH, t="READY", s=1, d=await self._generateReadyPayload(cl))
        elif op == OP.RESUME:
            if not (cl := [w for w in self.clients if w.sid == data["d"]["session_id"]]):
                await self.sendws(ws, OP.INV_SESSION)
                await self.sendws(ws, OP.RECONNECT)
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
            await self.send(cl, OP.DISPATCH, t="READY", s=1, d=await self._generateReadyPayload(cl))
        elif op == OP.HEARTBEAT:
            if not (cl := [w for w in self.clients if w.ws == ws]):
                print("close 8")
                return await ws.close(4005)
            cl = cl[0]
            await self.send(cl, OP.HEARTBEAT_ACK, t=None, d=None)

    async def sendHello(self, ws):
        await self.sendws(ws, OP.HELLO, t=None, s=None, d={"heartbeat_interval": 45000})