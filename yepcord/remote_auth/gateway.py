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

from asyncio import sleep as asleep, get_event_loop
from base64 import b64encode as _b64encode, b64decode as _b64decode
from hashlib import sha256
from os import urandom
from time import time

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from quart import Websocket

from ..yepcord.models import RemoteAuthSession
from ..yepcord.mq_broker import getBroker
from ..yepcord.utils import b64encode, b64decode


class GatewayClient:
    __slots__ = ["ws", "pubkey", "fingerprint", "nonce", "connect_time", "last_heartbeat", "connected", "version", "gw"]

    def __init__(self, ws: Websocket, version: int, gateway):
        self.ws = ws
        self.nonce = urandom(32)
        self.connect_time = time()
        self.last_heartbeat = time()
        self.connected = True
        self.version = version
        self.gw = gateway

        self.pubkey: RSAPublicKey | None = None
        self.fingerprint: str | None = None

    def encrypt(self, data: bytes):
        return self.pubkey.encrypt(data, OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None))

    async def send(self, op: str, **data) -> None:
        if not self.connected:  # pragma: no cover
            return
        await self.ws.send_json({"op": op, **data})

    async def check_timeout(self, _task=False):
        if not _task:
            return get_event_loop().create_task(self.check_timeout(True))
        while self.connected:  # pragma: no cover
            if time()-self.connect_time > 150:
                await self.ws.close(4003)
                break
            if time()-self.last_heartbeat > 50:
                await self.ws.close(4004)
                break
            await asleep(5)

    async def handle_init(self, data: dict) -> None:
        pubkey = data["encoded_public_key"]
        fingerprint = sha256(_b64decode(pubkey.encode("utf8"))).digest()
        fingerprint = self.fingerprint = b64encode(fingerprint)

        if not self.gw.init_client(self, fingerprint):
            return await self.ws.close(1001)

        self.pubkey = load_pem_public_key(
            f"-----BEGIN PUBLIC KEY-----\n{pubkey}\n-----END PUBLIC KEY-----\n".encode("utf8"),
            backend=default_backend()
        )

        await RemoteAuthSession.create(fingerprint=fingerprint, version=self.version)
        encrypted_nonce = _b64encode(self.encrypt(self.nonce)).decode("utf8")
        await self.send("nonce_proof", encrypted_nonce=encrypted_nonce)
        await self.check_timeout()

    async def handle_nonce_proof(self, data: dict) -> None:
        proof = b64decode(data["proof"])
        if proof != sha256(self.nonce).digest():
            return await self.ws.close(1001)
        await self.send("pending_remote_init", fingerprint=self.fingerprint)

    # noinspection PyUnusedLocal
    async def handle_heartbeat(self, data: dict) -> None:
        self.last_heartbeat = time()
        await self.send("heartbeat_ack")

    async def send_pending_finish(self, userdata: str) -> None:
        # userdata = id : discriminator : avatar : username
        data = _b64encode(self.encrypt(userdata.encode("utf8"))).decode("utf8")
        await self.send("pending_finish" if self.version == 1 else "pending_ticket", encrypted_user_payload=data)

    async def send_finish_v1(self, token: str) -> None:
        data = _b64encode(self.encrypt(token.encode("utf8"))).decode("utf8")
        await self.send("finish", encrypted_token=data)
        await self.ws.close(1000)

    async def send_finish_v2(self, token: str) -> None:
        enc_token = _b64encode(self.encrypt(token.encode("utf8"))).decode("utf8")
        await RemoteAuthSession.filter(fingerprint=self.fingerprint).update(v2_encrypted_token=enc_token)
        token = ".".join(token.split(".")[:-1])
        await self.send("pending_login", ticket=f"{token}.{self.fingerprint}")
        await self.ws.close(1000)

    async def send_finish(self, token: str) -> None:
        if self.version == 1:
            return await self.send_finish_v1(token)
        await self.send_finish_v2(token)

    async def send_cancel(self) -> None:
        await self.send("cancel")
        await self.ws.close(1000)


class Gateway:
    def __init__(self):
        self.clients_by_fingerprint: dict[str, GatewayClient] = {}
        self.broker = getBroker()
        self.broker.subscriber("yepcord_remote_auth")(self.mq_callback)

    async def init(self):
        await self.broker.start()

    async def stop(self):
        await self.broker.close()

    async def mq_callback(self, body: dict) -> None:
        if body["op"] not in {"pending_finish", "finish", "cancel"}:  # pragma: no cover
            return
        if not (client := self.clients_by_fingerprint.get(body["fingerprint"])):  # pragma: no cover
            return

        if body["op"] == "pending_finish":
            await client.send_pending_finish(body["userdata"])
        elif body["op"] == "finish":
            await client.send_finish(body["token"])
        elif body["op"] == "cancel":
            await client.send_cancel()

    def init_client(self, client: GatewayClient, fingerprint: str) -> bool:
        if fingerprint in self.clients_by_fingerprint:
            return False
        self.clients_by_fingerprint[fingerprint] = client
        return True

    async def process(self, ws: Websocket, data: dict) -> None:
        if (client := getattr(ws, "_yepcord_client", None)) is None:  # pragma: no cover
            return await ws.close(1001)

        op = data["op"]
        if (func := getattr(client, f"handle_{op}", None)) is None:  # pragma: no cover
            return await ws.close(1001)

        await func(data)

    async def connect(self, ws: Websocket, version: int) -> None:
        client = GatewayClient(ws, version, self)
        setattr(ws, "_yepcord_client", client)
        await client.send("hello", heartbeat_interval=41500, timeout_ms=150*1000)

    async def disconnect(self, ws: Websocket):
        client: GatewayClient
        if (client := getattr(ws, "_yepcord_client", None)) is None:  # pragma: no cover
            return
        client.connected = False
        if client.fingerprint in self.clients_by_fingerprint:
            del self.clients_by_fingerprint[client.fingerprint]
            await RemoteAuthSession.filter(fingerprint=client.fingerprint).delete()
