from os import urandom
from typing import Any, Optional

from aiohttp import ClientSession
from aiortc import RTCSessionDescription, RTCPeerConnection
from aiortc.contrib.media import MediaBlackhole, MediaRecorder, MediaPlayer
from aiortc.sdp import SessionDescription

from src.yepcord.enums import VoiceGatewayOp
from .events import Event, ReadyEvent, SpeakingEvent, UdpSessionDescriptionEvent, RtcSessionDescriptionEvent
from .schemas import SelectProtocol


class GatewayClient:
    def __init__(self, ws, user_id: int, session_id: str, guild_id: int, token: str, ssrc: int):
        self.ws = ws
        self.user_id = user_id
        self.session_id = session_id
        self.guild_id = guild_id
        self.token = token
        self.ssrc = ssrc
        self.video_ssrc = 0
        self.rtx_ssrc = 0
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
        self._pcs: set[RTCPeerConnection] = set()

    async def sendws(self, ws, op: int, **data) -> None:
        await ws.send_json({"op": op, **data})

    async def sendHello(self, ws) -> None:
        await self.sendws(ws, VoiceGatewayOp.HELLO, d={"v": 7, "heartbeat_interval": 13750})

    async def process(self, ws, data: dict) -> None:
        op = data["op"]
        if op == VoiceGatewayOp.IDENTIFY:
            if ws in self._clients:
                return await ws.close(4005)
            d = data["d"]
            print(f"Connected to voice with session_id={d['session_id']}")
            if d["token"] != "idk_token":
                return await ws.close(4004)
            async with ClientSession() as sess:
                p = await sess.get("http://192.168.1.155:10000/getLocalPort")
                p = int(await p.text())
                print(f"Got port {p}")
            self._clients[ws] = client = GatewayClient(ws, int(d["user_id"]), d["session_id"], d["server_id"], d["token"], self._ssrc)
            self._ssrc += 1
            client.video_ssrc = self._ssrc
            self._ssrc += 1
            client.rtx_ssrc = self._ssrc
            self._ssrc += 1
            await client.esend(ReadyEvent(client.ssrc, client.video_ssrc, client.rtx_ssrc, p))
        elif op == VoiceGatewayOp.HEARTBEAT:
            if ws not in self._clients:
                return await ws.close(4003)
            await self.sendws(ws, VoiceGatewayOp.HEARTBEAT_ACK, d=data["d"])
        elif op == VoiceGatewayOp.SELECT_PROTOCOL:
            if ws not in self._clients:
                return await ws.close(4003)
            client = self._clients[ws]
            try:
                d = SelectProtocol(**data["d"])
            except:
                return await ws.close(4012)
            if d.protocol == "webrtc":

                answer = ...

                await client.esend(RtcSessionDescriptionEvent(answer))
            elif d.protocol == "udp":
                client.mode = d.data.mode
                if client.mode not in ("xsalsa20_poly1305", "xsalsa20_poly1305_suffix", "xsalsa20_poly1305_lite", "xsalsa20_poly1305_lite_rtpsize", "aead_aes256_gcm", "aead_aes256_gcm_rtpsize"):
                    return await ws.close(4016)
                client.key = urandom(32)
                await client.esend(UdpSessionDescriptionEvent(client.mode, client.key))
        elif op == VoiceGatewayOp.SPEAKING:
            if ws not in self._clients:
                return await ws.close(4003)
            client = self._clients[ws]
            d = data["d"]
            if client.ssrc != d["ssrc"] or d["ssrc"] > 7 or d["ssrc"] < 1:
                return await ws.close(4014)
            await client.esend(SpeakingEvent(client.ssrc, client.user_id, d["speaking"]))


    async def disconnect(self, ws) -> None:
        if ws in self._clients:
            del self._clients[ws]