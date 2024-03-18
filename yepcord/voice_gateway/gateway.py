from __future__ import annotations

from os import urandom
from typing import Optional

from httpx import AsyncClient
from quart import Websocket
from semanticsdp import SDPInfo, Setup

from yepcord.yepcord.enums import VoiceGatewayOp
from .default_sdp import DEFAULT_SDP
from .events import Event, ReadyEvent, SpeakingEvent, UdpSessionDescriptionEvent, RtcSessionDescriptionEvent
from .go_rpc import GoRpc
from .schemas import SelectProtocol
from ..gateway.utils import require_auth
from ..yepcord.config import Config
from ..yepcord.models import VoiceState


class GatewayClient:
    def __init__(self, ws: Websocket, gw: Gateway):
        self.ws = ws
        self.user_id = None
        self.session_id = None
        self.guild_id = None
        self.channel_id = None
        self.ssrc = 0
        self.video_ssrc = 0
        self.rtx_ssrc = 0
        self.mode: Optional[str] = None
        self.key: Optional[bytes] = None
        self.sdp = SDPInfo.from_dict(DEFAULT_SDP)

        self._gw = gw

    async def send(self, data: dict):
        await self.ws.send_json(data)

    async def esend(self, event: Event):
        await self.send(await event.json())

    async def handle_IDENTIFY(self, data: dict):
        print(f"Connected to voice with session_id={data['session_id']}")
        try:
            token = data["token"].split(".")
            if len(token) != 2:
                raise ValueError()
            state_id, token = token
            state_id = int(state_id)

            state = await VoiceState.get_or_none(id=state_id, token=token).select_related("user", "guild", "channel")
            if state is None:
                raise ValueError
        except ValueError:
            return await self.ws.close(4004)

        self.user_id = int(data["user_id"])
        self.session_id = data["session_id"]
        self.guild_id = int(data["server_id"])
        self.channel_id = state.channel.id
        if self.user_id != state.user.id or self.guild_id != state.guild.id:
            return await self.ws.close(4004)

        self.ssrc = self._gw.ssrc
        self._gw.ssrc += 1
        self.video_ssrc = self._gw.ssrc
        self._gw.ssrc += 1
        self.rtx_ssrc = self._gw.ssrc
        self._gw.ssrc += 1

        ip = "127.0.0.1"  # TODO
        port = 0
        rpc = self._gw.rpc(self.guild_id)
        if rpc is not None:
            port = await rpc.create_endpoint(self.channel_id)

        await self.esend(ReadyEvent(self.ssrc, self.video_ssrc, self.rtx_ssrc, ip, port))

    @require_auth(4003)
    async def handle_HEARTBEAT(self, data: dict):
        await self.send({"op": VoiceGatewayOp.HEARTBEAT_ACK, "d": data})

    @require_auth(4003)
    async def handle_SELECT_PROTOCOL(self, data: dict):
        rpc = self._gw.rpc(self.guild_id)
        if rpc is None:
            return

        try:
            d = SelectProtocol(**data)
        except Exception as e:
            print(e)
            return await self.ws.close(4012)

        if d.protocol == "webrtc":
            offer = SDPInfo.parse(f"m=audio\n{d.sdp}")
            self.sdp.ice = offer.ice
            self.sdp.dtls = offer.dtls
            self.sdp.dtls.setup = Setup.ACTIVE

            sdp = "v=0\r\n" + str(self.sdp) + "\r\n"

            answer = await rpc.create_peer_connection(self.channel_id, self.session_id, sdp)

            sdp = SDPInfo.parse(answer)
            c = sdp.candidates[0]
            port = c.port
            answer = "\n".join([
                f"m=audio {port} ICE/SDP",
                f"a=fingerprint:{sdp.dtls.hash} {sdp.dtls.fingerprint}",
                f"c=IN IP4 {c.address}",
                f"a=rtcp:{port}",
                f"a=ice-ufrag:{sdp.ice.ufrag}",
                f"a=ice-pwd:{sdp.ice.pwd}",
                f"a=fingerprint:{sdp.dtls.hash} {sdp.dtls.fingerprint}",
                f"a=candidate:{c.foundation} 1 {c.transport} {c.priority} {c.address} {port} typ host",
            ]) + "\n"

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
        self.channels = {}
        self._rpcs: dict[int, GoRpc] = {}

    def rpc(self, guild_id: int) -> Optional[GoRpc]:
        if not (workers := Config.VOICE_WORKERS):
            return
        idx = guild_id % len(workers)
        if idx not in self._rpcs:
            self._rpcs[idx] = GoRpc(workers[idx])

        return self._rpcs[idx]

    async def sendHello(self, ws: Websocket) -> None:
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
