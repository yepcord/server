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

from asyncio import sleep as asleep, get_event_loop
from base64 import b64encode as _b64encode, b64decode as _b64decode
from hashlib import sha256
from os import urandom
from time import time
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from ..yepcord.models import RemoteAuthSession
from ..yepcord.mq_broker import getBroker
from ..yepcord.utils import b64encode, b64decode


class GatewayClient:
    def __init__(self, ws, pubkey: str, fp: str, nonce: bytes):
        self.ws = ws
        self.pubkey = load_pem_public_key(
            f"-----BEGIN PUBLIC KEY-----\n{pubkey}\n-----END PUBLIC KEY-----\n".encode("utf8"),
            backend=default_backend()
        )
        self.fingerprint = fp
        self.nonce = nonce
        nonceHash = sha256()
        nonceHash.update(nonce)
        self.nonceHash = nonceHash.digest()
        self.cTime = time()
        self.lastHeartbeat = time()

    def encrypt(self, data: bytes):
        return self.pubkey.encrypt(data, OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None))

    async def check_timeout(self, _task=False):
        if not _task:
            return get_event_loop().create_task(self.check_timeout(True))
        while self.ws.connected:  # pragma: no cover
            if time()-self.cTime > 150:
                await self.ws.close(4003)
                break
            if time()-self.lastHeartbeat > 50:
                await self.ws.close(4004)
                break
            await asleep(5)


class Gateway:
    def __init__(self):
        self.clients_by_fingerprint: dict[str, GatewayClient] = {}
        self.clients_by_socket: dict[Any, GatewayClient] = {}
        self.broker = getBroker()
        self.broker.handle("yepcord_remote_auth")(self.mq_callback)

    async def init(self):
        await self.broker.start()

    async def stop(self):
        await self.broker.close()

    async def mq_callback(self, body: dict) -> None:
        if body["op"] == "pending_finish":
            await self.sendPendingFinish(body["fingerprint"], body["userdata"])
        elif body["op"] == "finish":
            await self.sendFinishV1(body["fingerprint"], body["token"])
        elif body["op"] == "cancel":
            await self.sendCancel(body["fingerprint"])

    # noinspection PyMethodMayBeStatic
    async def send(self, ws, op: str, **data) -> None:
        await ws.send_json({"op": op, **data})

    async def process(self, ws, data: dict) -> None:
        op = data["op"]
        if op == "init":
            pubkey = data["encoded_public_key"]
            s = sha256()
            s.update(_b64decode(pubkey.encode("utf8")))
            fingerprint = b64encode(s.digest()).replace("=", "")
            if self.clients_by_fingerprint.get(fingerprint):
                return await ws.close(1001)
            nonce = urandom(32)
            cl = GatewayClient(ws, pubkey, fingerprint, nonce)
            self.clients_by_fingerprint[fingerprint] = self.clients_by_socket[ws] = cl
            await RemoteAuthSession.create(fingerprint=fingerprint)
            encrypted_nonce = _b64encode(cl.encrypt(nonce)).decode("utf8")
            await self.send(ws, "nonce_proof", encrypted_nonce=encrypted_nonce)
            await cl.check_timeout()
        elif op == "nonce_proof":
            if not (client := self.clients_by_socket.get(ws)):
                return await ws.close(1001)
            proof = b64decode(data["proof"])
            if proof != client.nonceHash:
                return await ws.close(1001)
            await self.send(ws, "pending_remote_init", fingerprint=client.fingerprint)
        elif op == "heartbeat":
            if not (client := self.clients_by_socket.get(ws)):
                return await ws.close(1001)
            client.lastHeartbeat = time()
            await self.send(ws, "heartbeat_ack")

    async def sendHello(self, ws) -> None:
        await self.send(ws, "hello", heartbeat_interval=41500, timeout_ms=150*1000)

    async def sendPendingFinish(self, fingerprint: str, userdata: str) -> None:
        # userdata = id : discriminator : avatar : username
        if not (client := self.clients_by_fingerprint.get(fingerprint)):  # pragma: no cover
            return
        data = _b64encode(client.encrypt(userdata.encode("utf8"))).decode("utf8")
        await self.send(client.ws, "pending_finish", encrypted_user_payload=data)

    async def sendFinishV1(self, fingerprint: str, token: str) -> None:
        if not (client := self.clients_by_fingerprint.get(fingerprint)):  # pragma: no cover
            return
        data = _b64encode(client.encrypt(token.encode("utf8"))).decode("utf8")
        await self.send(client.ws, "finish", encrypted_token=data)
        await client.ws.close(1000)

    async def sendCancel(self, fingerprint: str) -> None:
        if not (client := self.clients_by_fingerprint.get(fingerprint)):  # pragma: no cover
            return
        await self.send(client.ws, "cancel")
        await client.ws.close(1000)

    async def disconnect(self, ws) -> None:
        if not (client := self.clients_by_socket.get(ws)):
            return

        await RemoteAuthSession.filter(fingerprint=client.fingerprint).delete()
