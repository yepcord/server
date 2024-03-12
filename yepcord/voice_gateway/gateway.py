from __future__ import annotations

from os import urandom
from typing import Optional

from quart import Websocket

from yepcord.yepcord.enums import VoiceGatewayOp
from .default_sdp import DEFAULT_SDP
from .events import Event, ReadyEvent, SpeakingEvent, UdpSessionDescriptionEvent, RtcSessionDescriptionEvent
from .schemas import SelectProtocol
from ..gateway.utils import require_auth

try:
    from semanticsdp import SDPInfo, DTLSInfo, Setup
    from pymedooze import MediaServer

    _DISABLED = False
except ImportError:
    _DISABLED = True


class GatewayClient:
    def __init__(self, ws: Websocket, gw: Gateway):
        self.ws = ws
        self.user_id = None
        self.session_id = None
        self.guild_id = None
        self.token = None
        self.ssrc = 0
        self.video_ssrc = 0
        self.rtx_ssrc = 0
        self.mode: Optional[str] = None
        self.key: Optional[bytes] = None
        self.sdp: Optional[SDPInfo] = None
        self.transport = None

        self._gw = gw

    async def send(self, data: dict):
        await self.ws.send_json(data)

    async def esend(self, event: Event):
        await self.send(await event.json())

    async def handle_IDENTIFY(self, data: dict):
        print(f"Connected to voice with session_id={data['session_id']}")
        if data["token"] != "idk_token":
            return await self.ws.close(4004)

        self.user_id = int(data["user_id"])
        self.session_id = data["session_id"]
        self.guild_id = data["server_id"]
        self.token = data["token"]

        self.ssrc = self._gw.ssrc
        self._gw.ssrc += 1
        self.video_ssrc = self._gw.ssrc
        self._gw.ssrc += 1
        self.rtx_ssrc = self._gw.ssrc
        self._gw.ssrc += 1

        self.sdp = SDPInfo.from_dict(DEFAULT_SDP)
        self.sdp.dtls = DTLSInfo(
            setup=Setup.ACTPASS, hash="sha-256", fingerprint=self._gw.endpoint.get_dtls_fingerprint()
        )

        await self.esend(ReadyEvent(self.ssrc, self.video_ssrc, self.rtx_ssrc, self._gw.endpoint.get_local_port()))

    @require_auth(4003)
    async def handle_HEARTBEAT(self, data: dict):
        await self.send({"op": VoiceGatewayOp.HEARTBEAT_ACK, "d": data["d"]})

    @require_auth(4003)
    async def handle_SELECT_PROTOCOL(self, data: dict):
        try:
            d = SelectProtocol(**data)
        except Exception as e:
            print(e)
            return await self.ws.close(4012)

        if d.protocol == "webrtc":
            offer = SDPInfo.parse(f"m=audio\n{d.sdp}")
            self.sdp.ice = offer.ice
            self.sdp.dtls = offer.dtls

            self.transport = self._gw.endpoint.create_transport(self.sdp)
            self.transport.set_remote_properties(self.sdp)
            self.transport.set_local_properties(self.sdp)

            dtls = self.transport.get_local_dtls()
            ice = self.transport.get_local_ice()
            port = self._gw.endpoint.get_local_port()
            fp = f"{dtls.hash} {dtls.fingerprint}"
            candidate = self.transport.get_local_candidates()[0]

            answer = (
                    f"m=audio {port} ICE/SDP\n" +
                    f"a=fingerprint:{fp}\n" +
                    f"c=IN IP4 127.0.0.1\n" +
                    f"a=rtcp:{port}\n" +
                    f"a=ice-ufrag:{ice.ufrag}\n" +
                    f"a=ice-pwd:{ice.pwd}\n" +
                    f"a=fingerprint:{fp}\n" +
                    f"a=candidate:1 1 {candidate.transport} {candidate.foundation} {candidate.address} {candidate.port} typ host\n"
            )

            await self.esend(RtcSessionDescriptionEvent(answer))
        elif d.protocol == "udp":
            self.mode = d.data.mode
            if self.mode not in ("xsalsa20_poly1305", "xsalsa20_poly1305_suffix", "xsalsa20_poly1305_lite",
                                 "xsalsa20_poly1305_lite_rtpsize", "aead_aes256_gcm", "aead_aes256_gcm_rtpsize"):
                return await self.ws.close(4016)
            self.key = urandom(32)
            await self.esend(UdpSessionDescriptionEvent(self.mode, self.key))

    @require_auth(4003)
    async def handle_SPEAKING(self, data: dict):
        if self.ssrc != data["ssrc"] or data["ssrc"] < 1:
            return await self.ws.close(4014)
        await self.esend(SpeakingEvent(self.ssrc, self.user_id, data["speaking"]))

    async def handle_VOICE_BACKEND_VERSION(self, data: dict) -> None:
        await self.send({"op": VoiceGatewayOp.VOICE_BACKEND_VERSION, "d": {"voice": "0.11.0", "rtc_worker": "0.4.11"}})


class Gateway:
    def __init__(self):
        self.ssrc = 1

        if not _DISABLED:
            MediaServer.initialize()
            MediaServer.set_port_range(3690, 3960)
            self.endpoint = MediaServer.create_endpoint("127.0.0.1")

    async def sendHello(self, ws: Websocket) -> None:
        if _DISABLED:
            return await ws.close(4005)
        client = GatewayClient(ws, self)
        setattr(ws, "_yepcord_client", client)
        await ws.send_json({"op": VoiceGatewayOp.HELLO, "d": {"v": 7, "heartbeat_interval": 13750}})

    async def process(self, ws: Websocket, data: dict) -> None:
        op = data["op"]
        if (client := getattr(ws, "_yepcord_client", None)) is None:
            return await ws.close(4005)

        func = getattr(client, f"handle_{VoiceGatewayOp.reversed()[op]}", None)
        if func:
            return await func(data.get("d"))
        else:
            print("-" * 16)
            print(f"  [Voice] Unknown op code: {op}")
            print(f"  [Voice] Data: {data}")
