from base64 import b64encode as _b64encode, b64decode as _b64decode
from os import urandom
from asyncio import sleep as asleep, get_event_loop
from time import time
from hashlib import sha256
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.hazmat.primitives.hashes import SHA256

from ..yepcord.config import Config
from ..yepcord.utils import b64encode, b64decode
from ..yepcord.pubsub_client import Client

class GatewayClient:
    def __init__(self, ws, pubkey, fp, nonce):
        self.ws = ws
        self.pubkey = load_pem_public_key(
            ("-----BEGIN PUBLIC KEY-----\n"+pubkey+"\n-----END PUBLIC KEY-----\n").encode("utf8"),
            backend=default_backend()
        )
        self.fingerprint = fp
        self.nonce = nonce
        nonceHash = sha256()
        nonceHash.update(nonce)
        self.nonceHash = nonceHash.digest()
        self.cTime = time()
        self.lastHeartbeat = time()

    def encrypt(self, data):
        return self.pubkey.encrypt(data, OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None))

    async def check_timeout(self, _task=False):
        if not _task:
            return get_event_loop().create_task(self.check_timeout(True))
        while self.ws.connected:
            if time()-self.cTime > 150:
                await self.ws.close(4003)
                break
            if time()-self.lastHeartbeat > 50:
                await self.ws.close(4004)
                break
            await asleep(5)

class Gateway:
    def __init__(self):
        self.clients = []
        self.mcl = Client()

    async def init(self):
        await self.mcl.start(f"ws://{Config('PS_ADDRESS')}:5050")
        await self.mcl.subscribe("remote_auth", self.mclCallback)

    async def mclCallback(self, data):
        if data["op"] == "pending_finish":
            await self.sendPendingFinish(data["fingerprint"], data["userdata"])
        elif data["op"] == "finish":
            await self.sendFinish(data["fingerprint"], data["token"])
        elif data["op"] == "cancel":
            await self.sendCancel(data["fingerprint"])

    # noinspection PyMethodMayBeStatic
    async def send(self, ws, op, **data):
        r = {"op": op}
        r.update(data)
        await ws.send_json(r)

    async def process(self, ws, data):
        op = data["op"]
        if op == "init":
            pubkey = data["encoded_public_key"]
            s = sha256()
            s.update(_b64decode(pubkey.encode("utf8")))
            fingerprint = b64encode(s.digest()).replace("=", "")
            nonce = urandom(32)
            cl = GatewayClient(ws, pubkey, fingerprint, nonce)
            self.clients.append(cl)
            encrypted_nonce = _b64encode(cl.encrypt(nonce)).decode("utf8")
            await self.send(ws, "nonce_proof", encrypted_nonce=encrypted_nonce)
            await cl.check_timeout()
        elif op == "nonce_proof":
            client = [cl for cl in self.clients if cl.ws == ws]
            if not client:
                return await ws.close(1001)
            client = client[0]
            proof = data["proof"]
            proof = b64decode(proof)
            if proof != client.nonceHash:
                return await ws.close(1001)
            await self.send(ws, "pending_remote_init", fingerprint=client.fingerprint)
        elif op == "heartbeat":
            client = [cl for cl in self.clients if cl.ws == ws]
            if not client:
                return await ws.close(1001)
            client = client[0]
            client.lastHeartbeat = time()
            await self.send(ws, "heartbeat_ack")

    async def sendHello(self, ws):
        await self.send(ws, "hello", heartbeat_interval=41500, timeout_ms=150*1000)

    async def sendPendingFinish(self, fingerprint, userdata):
        # userdata = id : discriminator : avatar : username
        client = [cl for cl in self.clients if cl.fingerprint == fingerprint]
        if not client:
            return
        client = client[0]
        data = _b64encode(client.encrypt(userdata.encode("utf8"))).decode("utf8")
        await self.send(client.ws, "pending_finish", encrypted_user_payload=data)

    async def sendFinish(self, fingerprint, token):
        client = [cl for cl in self.clients if cl.fingerprint == fingerprint]
        if not client:
            return
        client = client[0]
        data = _b64encode(client.encrypt(token.encode("utf8"))).decode("utf8")
        await self.send(client.ws, "finish", encrypted_token=data)
        await client.ws.close(1000)

    async def sendCancel(self, fingerprint):
        client = [cl for cl in self.clients if cl.fingerprint == fingerprint]
        if not client:
            return
        client = client[0]
        await self.send(client.ws, "cancel")
        await client.ws.close(1000)