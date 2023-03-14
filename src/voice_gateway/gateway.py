from os import urandom
from typing import Any, Optional

from src.yepcord.enums import VoiceGatewayOp
from .events import Event, ReadyEvent, SessionDescriptionEvent, SpeakingEvent


class GatewayClient:
    def __init__(self, ws, user_id: int, session_id: str, guild_id: int, token: str, ssrc: int):
        self.ws = ws
        self.user_id = user_id
        self.session_id = session_id
        self.guild_id = guild_id
        self.token = token
        self.ssrc = ssrc
        self.mode: Optional[str] = None
        self.key: Optional[bytes] = None

    async def send(self, data: dict):
        await self.ws.send_json(data)

    async def esend(self, event: Event):
        await self.send(await event.json())

class Gateway:
    def __init__(self):
        self._clients: dict[Any, GatewayClient] = {}
        self._ssrc = 1

    async def sendws(self, ws, op: int, **data) -> None:
        await ws.send_json({"op": op, **data})

    async def sendHello(self, ws) -> None:
        await self.sendws(ws, VoiceGatewayOp.HELLO, d={"heartbeat_interval": 13750})

    async def process(self, ws, data: dict) -> None:
        op = data["op"]
        if op == VoiceGatewayOp.IDENTIFY:
            if ws in self._clients:
                return await ws.close(4005)
            d = data["d"]
            print(f"Connected to voice with session_id={d['session_id']}")
            if d["token"] != "idk_token":
                return await ws.close(4004)
            self._clients[ws] = client = GatewayClient(ws, int(d["user_id"]), d["session_id"], d["server_id"], d["token"], self._ssrc)
            await client.esend(ReadyEvent(self._ssrc))
            self._ssrc += 1
        elif op == VoiceGatewayOp.HEARTBEAT:
            if ws not in self._clients:
                return await ws.close(4003)
            await self.sendws(ws, VoiceGatewayOp.HEARTBEAT_ACK, d=data["d"])
        elif op == VoiceGatewayOp.SELECT_PROTOCOL:
            if ws not in self._clients:
                return await ws.close(4003)
            client = self._clients[ws]
            d = data["d"]
            if d["protocol"] != "udp":
                return await ws.close(4012)
            client.mode = d["data"]["mode"]
            if client.mode not in ("xsalsa20_poly1305", "xsalsa20_poly1305_suffix", "xsalsa20_poly1305_lite"):
                return await ws.close(4016)
            client.key = urandom(32)
            await client.esend(SessionDescriptionEvent(client.mode, client.key))
        elif op == VoiceGatewayOp.SPEAKING:
            if ws not in self._clients:
                return await ws.close(4003)
            client = self._clients[ws]
            d = data["d"]
            if client.ssrc != d["ssrc"] or d["ssrc"] > 7 or d["ssrc"] < 1:
                return await ws.close(4014)
            await client.esend(SpeakingEvent(client.ssrc, d["speaking"], d["delay"]))


    async def disconnect(self, ws) -> None:
        if ws in self._clients:
            del self._clients[ws]