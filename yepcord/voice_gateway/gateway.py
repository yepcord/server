from __future__ import annotations

from collections import defaultdict
from os import urandom
from time import time
from typing import Optional
from uuid import uuid4

from quart import Websocket
from semanticsdp import SDPInfo, Setup, Direction, StreamInfo, TrackInfo, MediaInfo, CodecInfo, RTCPFeedbackInfo

from yepcord.yepcord.enums import VoiceGatewayOp
from .default_sdp import DEFAULT_SDP_DS
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

        self.sdp = SDPInfo.from_dict(DEFAULT_SDP_DS)
        self.need_sync = False
        self.other_media_ids: dict[int, int] = {}  # ssrc to media_id

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

        self._gw.channels[self.channel_id][self.user_id] = self
        await self.esend(ReadyEvent(self.ssrc, self.video_ssrc, self.rtx_ssrc, ip, port))

    @require_auth(4003)
    async def handle_HEARTBEAT(self, data: dict):
        await VoiceState.filter(user__id=self.user_id, session_id=self.session_id).update(last_heartbeat=int(time()))

        await self.send({"op": VoiceGatewayOp.HEARTBEAT_ACK, "d": data})

    @require_auth(4003)
    async def handle_SELECT_PROTOCOL(self, data: dict):
        if (rpc := self._gw.rpc(self.guild_id)) is None:
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

        for client in self._gw.channels[self.channel_id].values():
            if client is self:
                continue
            await client.esend(SpeakingEvent(self.ssrc, self.user_id, data["speaking"]))

    @require_auth
    async def handle_VIDEO(self, data: dict):
        if (rpc := self._gw.rpc(self.guild_id)) is None:
            return

        if (audio_ssrc := data.get("audio_ssrc", 0)) < 1:
            return await self.send({"op": VoiceGatewayOp.MEDIA_SINK_WANTS, "d": {"any": "100"}})  # ?

        if audio_ssrc == self.ssrc:
            if not self.need_sync:
                return

            self.sdp.version += 1
            sdp = "v=0\r\n" + str(self.sdp) + "\r\n"
            await rpc.renegotiate(self.channel_id, self.session_id, sdp)

            self.need_sync = False

        track_id = str(uuid4())
        self.sdp.version += 1
        self.sdp.medias[0].direction = Direction.SENDRECV
        self.sdp.streams["-"] = StreamInfo(
            id="-",
            tracks={track_id: TrackInfo(
                media="audio",
                id=track_id,
                media_id="0",
                ssrcs=[audio_ssrc]
            )}
        )

        sdp = "v=0\r\n" + str(self.sdp) + "\r\n"
        await rpc.renegotiate(self.channel_id, self.session_id, sdp)

        await self.send({"op": VoiceGatewayOp.MEDIA_SINK_WANTS, "d": {"any": "100"}})

        for client in self._gw.channels[self.channel_id].values():
            if client is self:
                continue

            next_media_id = max([int(media.id) for media in client.sdp.medias]) + 1
            client.sdp.medias.append(MediaInfo(
                id=str(next_media_id),
                type="audio",
                direction=Direction.RECVONLY,
                extensions={
                    1: "urn:ietf:params:rtp-hdrext:ssrc-audio-level",
                    2: "http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time",
                    3: "http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01",
                    4: "urn:ietf:params:rtp-hdrext:sdes:mid"
                },
                codecs={
                    111: CodecInfo(
                        codec="opus",
                        type=111,
                        channels=2,
                        params={"minptime": "10", "useinbandfec": "1"},
                        rtcpfbs={RTCPFeedbackInfo(id="transport-cc", params=[])}
                    ),
                    9: CodecInfo(codec="G722", type=9),
                    0: CodecInfo(codec="PCMU", type=0),
                    8: CodecInfo(codec="PCMA", type=8),
                    13: CodecInfo(codec="CN", type=13),
                    110: CodecInfo(codec="telephone-event", type=110),
                    126: CodecInfo(codec="telephone-event", type=126),
                },
            ))
            client.other_media_ids[audio_ssrc] = next_media_id
            client.need_sync = True

            await client.send({"op": VoiceGatewayOp.VIDEO, "d": data})

    async def handle_VOICE_BACKEND_VERSION(self, data: dict) -> None:
        await self.send({"op": VoiceGatewayOp.VOICE_BACKEND_VERSION, "d": {"voice": "0.11.0", "rtc_worker": "0.4.11"}})


class Gateway:
    def __init__(self):
        self.ssrc = 1
        self.channels: defaultdict[int, dict[int, GatewayClient]] = defaultdict(dict)
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

    async def disconnect(self, ws: Websocket) -> None:
        client: GatewayClient
        if (client := getattr(ws, "_yepcord_client", None)) is None:
            return
        if client.channel_id not in self.channels or client.user_id not in self.channels[client.channel_id]:
            return

        del self.channels[client.channel_id][client.user_id]
        for cl in self.channels[client.channel_id].values():
            await cl.send({"op": VoiceGatewayOp.CLIENT_DISCONNECT, "d": {"user_id": str(client.user_id)}})
            # TODO: remove disconnected client from sdp
