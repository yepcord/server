import asyncio
from base64 import urlsafe_b64encode, b64decode
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional, Union

from quart.typing import TestWebsocketConnectionProtocol

from yepcord.rest_api.main import app as _app
from yepcord.yepcord.classes.other import MFA
from yepcord.yepcord.enums import ChannelType, GatewayOp
from yepcord.yepcord.snowflake import Snowflake
from yepcord.yepcord.utils import getImage
from tests.yep_image import YEP_IMAGE

TestClientType = _app.test_client_class


async def create_user(app: TestClientType, email: str, password: str, username: str, *, exp_code: int=200) -> Optional[str]:
    response = await app.post('/api/v9/auth/register', json={
        "username": username,
        "email": email,
        "password": password,
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == exp_code
    if exp_code < 400:
        json = await response.get_json()
        assert "token" in json
        return json["token"]


async def get_userdata(app: TestClientType, token: str) -> dict:
    response = await app.get("/api/v9/users/@me", headers={
        "Authorization": token
    })
    assert response.status_code == 200
    return await response.get_json()


async def create_users(app: TestClientType, count: int = 1) -> list[dict]:
    users = []
    for _ in range(count):
        temp_id = Snowflake.makeId()
        token = await create_user(app, f"{temp_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{temp_id}")
        users.append({
            "token": token,
            "password": "test_passw0rd",
            **(await get_userdata(app, token))
        })

    return users


async def enable_mfa(app: TestClientType, user: dict, mfa: MFA) -> None:
    resp = await app.post("/api/v9/users/@me/mfa/totp/enable", headers={"Authorization": user["token"]},
                          json={"code": mfa.getCode(), "secret": mfa.key, "password": user["password"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    user["token"] = json["token"]


async def rel_count(app: TestClientType, user: dict) -> int:
    response = await app.get('/api/v9/users/@me/relationships', headers={"Authorization": user["token"]})
    assert response.status_code == 200
    return len(await response.get_json())


async def rel_request(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.post("/api/v9/users/@me/relationships", headers={"Authorization": from_["token"]},
                              json={"username": to_["username"], "discriminator": to_["discriminator"]})
    return response.status_code


async def rel_delete(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.delete(f"/api/v9/users/@me/relationships/{from_['id']}", json={},
                                headers={"Authorization": to_["token"]})
    return response.status_code


async def rel_accept(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.put(f"/api/v9/users/@me/relationships/{from_['id']}", headers={"Authorization": to_["token"]},
                             json={})
    return response.status_code


async def rel_block(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.put(f"/api/v9/users/@me/relationships/{to_['id']}", headers={"Authorization": from_["token"]},
                             json={"type": 2})
    return response.status_code


async def create_guild(app: TestClientType, user: dict, name: str, icon: str = None) -> dict:
    resp = await app.post("/api/v9/guilds", headers={"Authorization": user["token"]}, json={'name': name, 'icon': icon})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_guild_channel(app: TestClientType, user: dict, guild: dict, name: str, type_=0,
                               parent: str = None, **kwargs) -> dict:
    resp = await app.post(f"/api/v9/guilds/{guild['id']}/channels", headers={"Authorization": user["token"]},
                          json={'type': type_, 'name': name, 'parent_id': parent, **kwargs})
    assert resp.status_code == 200
    channel = await resp.get_json()
    guild["channels"].append(channel)
    return channel


async def create_invite(app: TestClientType, user: dict, channel_id: str, max_age=604800, max_uses=0) -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/invites", headers={"Authorization": user["token"]},
                          json={'max_age': max_age, 'max_uses': max_uses})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_webhook(app: TestClientType, user: dict, channel_id: str, name="Captain Hook") -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/webhooks", headers={"Authorization": user["token"]},
                          json={'name': name})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_role(app: TestClientType, user: dict, guild_id: str, name="new role", icon: str=None, perms: int=None) -> dict:
    kw = {}
    if icon is not None: kw["icon"] = icon
    if perms is not None: kw["permissions"] = perms
    resp = await app.post(f"/api/v9/guilds/{guild_id}/roles", headers={"Authorization": user["token"]},
                          json={'name': name, **kw})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_emoji(app: TestClientType, user: dict, guild_id: str, name: str, image=YEP_IMAGE, *, exp_code=200) -> dict:
    resp = await app.post(f"/api/v9/guilds/{guild_id}/emojis", headers={"Authorization": user["token"]},
                          json={'image': image, 'name': name})
    assert resp.status_code == exp_code, await resp.get_json()
    return await resp.get_json()


async def create_sticker(app: TestClientType, user: dict, guild_id: str, name: str, tags="slight_smile",
                         image=YEP_IMAGE) -> dict:
    image = getImage(image)
    assert image is not None
    image.filename = "yep.png"
    image.headers = []
    resp = await app.post(f"/api/v9/guilds/{guild_id}/stickers", headers={"Authorization": user["token"]}, files={
        "file": image
    }, form={
        "name": name,
        "tags": tags
    })

    assert resp.status_code == 200
    return await resp.get_json()


async def create_message(app: TestClientType, user: dict, channel_id: str, *, exp_code=200, **kwargs) -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/messages", headers={"Authorization": user["token"]},
                          json=kwargs)
    assert resp.status_code == exp_code
    return await resp.get_json()


async def create_dm_channel(app: TestClientType, user1: dict, user2: dict) -> dict:
    resp = await app.post(f"/api/v9/users/@me/channels", headers={"Authorization": user1["token"]},
                          json={"recipients": [user1["id"], user2["id"]]})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_dm_group(app: TestClientType, user: dict, recipient_ids: list[str], *, exp_code=200) -> dict:
    resp = await app.post(f"/api/v9/users/@me/channels", headers={"Authorization": user["token"]},
                          json={"recipients": recipient_ids})
    assert resp.status_code == exp_code
    return await resp.get_json()


async def create_ban(app: TestClientType, user: dict, guild: dict, target_id: str, seconds: int=0, *, exp_code=204) -> dict:
    resp = await app.put(f"/api/v9/guilds/{guild['id']}/bans/{target_id}", headers={"Authorization": user["token"]},
                         json=({} if not seconds else {"delete_message_seconds": seconds}))
    assert resp.status_code == exp_code
    return await resp.get_json()


async def add_user_to_guild(app: TestClientType, guild: dict, owner: dict, target: dict) -> None:
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    invite = await create_invite(app, owner, channel["id"])

    resp = await app.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": target["token"]})
    assert resp.status_code == 200


async def create_event(app: TestClientType, guild: dict, user: dict, *, exp_code: int=200, **kwargs) -> dict:
    kwargs["privacy_level"] = 2
    if "scheduled_start_time" not in kwargs:
        kwargs["scheduled_start_time"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = await app.post(f"/api/v9/guilds/{guild['id']}/scheduled-events", headers={"Authorization": user["token"]},
                          json={**kwargs})
    assert resp.status_code == exp_code
    return await resp.get_json()


async def create_application(app: TestClientType, user: dict, name: str, *, exp_code: int=200) -> dict:
    resp = await app.post(f"/api/v9/applications", headers={"Authorization": user["token"]}, json={"name": name})
    assert resp.status_code == exp_code
    return await resp.get_json()


async def add_bot_to_guild(app: TestClientType, user: dict, guild: dict, application: dict) -> None:
    resp = await app.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot",
                          headers={"Authorization": user["token"]},
                          json={"authorize": True, "permissions": "8", "guild_id": guild["id"]})
    assert resp.status_code == 200


async def bot_token(app: TestClientType, user: dict, application: dict) -> str:
    resp = await app.post(f"/api/v9/applications/{application['id']}/bot/reset",
                             headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    return json["token"]


async def create_thread(app: TestClientType, user: dict, message: dict, *, exp_code=200, **kwargs) -> dict:
    resp = await app.post(f"/api/v9/channels/{message['channel_id']}/messages/{message['id']}/threads",
                          headers={"Authorization": user["token"]}, json=kwargs)
    assert resp.status_code == exp_code, await resp.get_json()
    return await resp.get_json()


def generate_slash_command_payload(application: dict, guild: dict, channel: dict, command: dict, options: list) -> dict:
    return {
        "type": 2,
        "application_id": application["id"],
        "guild_id": guild["id"],
        "channel_id": channel["id"],
        "session_id": "0",
        "nonce": str(Snowflake.makeId()),
        "data": {
            "version": command["version"],
            "id": command["id"],
            "name": command["name"],
            "type": command["type"],
            "application_command": command,
            "options": options,
            "attachments": [],
        }
    }


class RemoteAuthClient:
    def __init__(self, on_fingerprint=None, on_userdata=None, on_token=None, on_cancel=None):
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.privKey: Optional[rsa.RSAPrivateKey] = None
        self.pubKey: Optional[rsa.RSAPublicKey] = None
        self.pubKeyS: Optional[str] = None

        self.heartbeatTask = None

        self.on_fingerprint = on_fingerprint
        self.on_userdata = on_userdata
        self.on_token = on_token
        self.on_cancel = on_cancel

        self.results: dict[str, Union[Optional[str], bool]] = {
            "fingerprint": None,
            "userdata": None,
            "token": None,
            "cancel": False,
        }

        self.handlers = {
            "hello": self.handle_hello,
            "nonce_proof": self.handle_nonce_proof,
            "pending_remote_init": self.handle_pending_remote_init,
            "pending_finish": self.handle_pending_finish,
            "finish": self.handle_finish,
            "cancel": self.handle_cancel,
        }

    def genKeys(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        self.privKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pubKey = self.privKey.public_key()
        pubKeyS = self.pubKey.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("utf8")
        self.pubKeyS = "".join(pubKeyS.split("\n")[1:-2])

    async def heartbeat(self, ws: TestWebsocketConnectionProtocol, interval: int) -> None:
        while True:
            await asyncio.sleep(interval/1000)
            await ws.send_json({"op": "heartbeat"})

    def decrypt(self, b64_payload: str) -> bytes:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes

        return self.privKey.decrypt(
            b64decode(b64_payload.encode("utf8")),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

    async def handle_hello(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        await ws.send_json({"op": "init", "encoded_public_key": self.pubKeyS})
        await ws.send_json({"op": "heartbeat"})
        self.heartbeatTask = asyncio.get_event_loop().create_task(self.heartbeat(ws, msg["heartbeat_interval"]))

    async def handle_nonce_proof(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        decryptedNonce = self.decrypt(msg["encrypted_nonce"])
        nonceHash = sha256()
        nonceHash.update(decryptedNonce)
        nonceHash = urlsafe_b64encode(nonceHash.digest()).decode("utf8")
        nonceHash = nonceHash.replace("/", "").replace("+", "").replace("=", "")
        await ws.send_json({"op": 'nonce_proof', "proof": nonceHash})

    async def handle_pending_remote_init(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        self.results["fingerprint"] = msg["fingerprint"]
        if self.on_fingerprint is not None: await self.on_fingerprint(msg["fingerprint"])

    async def handle_pending_finish(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        userdata = self.decrypt(msg["encrypted_user_payload"]).decode("utf8")
        self.results["userdata"] = userdata
        if self.on_userdata is not None: await self.on_userdata(userdata)

    async def handle_finish(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        token = self.decrypt(msg["encrypted_token"]).decode("utf8")
        self.results["token"] = token
        if self.on_token is not None: await self.on_token(token)

    async def handle_cancel(self, ws: TestWebsocketConnectionProtocol, msg: dict) -> None:
        self.results["cancel"] = True
        if self.on_cancel is not None: await self.on_cancel()

    async def run(self, ws: TestWebsocketConnectionProtocol) -> None:
        self.genKeys()
        while True:
            msg = await ws.receive_json()
            if msg["op"] not in self.handlers: continue
            handler = self.handlers[msg["op"]]
            await handler(ws, msg)
            if msg["op"] in {"finish", "cancel"}:
                break

        if self.heartbeatTask is not None:
            self.heartbeatTask.cancel()


@asynccontextmanager
async def gateway_cm(gw_app):
    for func in gw_app.before_serving_funcs:
        if func.__name__ == "init_orm":
            continue
        await gw_app.ensure_async(func)()
    yield
    for func in gw_app.after_serving_funcs:
        await gw_app.ensure_async(func)()


class GatewayClient:
    class EventListener:
        def __init__(self, event: GatewayOp, dispatch_event: Optional[str], future: asyncio.Future, raw: bool):
            self.event = event
            self.dispatch_event = dispatch_event
            self.future = future
            self.raw = raw

    def __init__(self, token: str):
        self.token = token
        self.seq = 0

        self.running = True
        self.loop = asyncio.get_event_loop()
        self.heartbeatTask: Optional[asyncio.Task] = None
        self.mainTask: Optional[asyncio.Task] = None

        self.handlers = {
            GatewayOp.HELLO: self.handle_hello
        }
        self.listeners: list[GatewayClient.EventListener] = []

    async def handle_hello(self, ws: TestWebsocketConnectionProtocol, data: dict) -> None:
        await ws.send_json({"op": GatewayOp.IDENTIFY, "d": {"token": self.token}})

    async def run(self, ws: TestWebsocketConnectionProtocol, task=True) -> None:
        if task:
            self.running = True
            self.mainTask = self.loop.create_task(self.run(ws, False))
            return

        while self.running:
            msg = await ws.receive_json()
            if msg["op"] in self.handlers:
                await self.handlers[msg["op"]](ws, msg.get("data"))

            remove = []
            for idx, listener in enumerate(self.listeners):
                if msg["op"] != listener.event:
                    continue
                if msg["op"] == GatewayOp.DISPATCH and msg.get("t") != listener.dispatch_event:
                    continue
                future = listener.future
                future.set_result(msg if listener.raw else msg.get("d"))
                remove.insert(0, idx)

            for idx in remove:
                del self.listeners[idx]

        if self.heartbeatTask is not None:
            self.heartbeatTask.cancel()

    def stop(self):
        self.running = False
        if self.mainTask is not None:
            self.mainTask.cancel()
            self.mainTask = None
        if self.heartbeatTask is not None:
            self.heartbeatTask.cancel()
            self.heartbeatTask = None

    async def wait_for(self, event: GatewayOp, dispatch_event: str=None, raw: bool=False) -> asyncio.Future:
        if event == GatewayOp.DISPATCH and dispatch_event is None:
            raise Exception("dispatch_event must be provided when event is DISPATCH!")
        elif event != GatewayOp.DISPATCH and dispatch_event is not None:
            dispatch_event = None

        future = self.loop.create_future()
        listener = self.EventListener(event, dispatch_event, future, raw)
        self.listeners.append(listener)
        return future

    async def awaitable_wait_for(self, *args, **kwargs):
        future = await self.wait_for(*args, **kwargs)

        async def _future():
            return await future

        return _future()
