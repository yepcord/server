from yepcord.yepcord.enums import VoiceGatewayOp


class Event:
    OP: int

    async def json(self) -> dict: ...


class ReadyEvent(Event):
    OP = VoiceGatewayOp.READY

    def __init__(self, ssrc: int, video_ssrc: int, rtx_ssrc: int, ip: str, port: int):
        self.ssrc = ssrc
        self.video_ssrc = video_ssrc
        self.rtx_ssrc = rtx_ssrc
        self.ip = ip
        self.port = port

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "ssrc": self.ssrc,
                "ip": self.ip,
                "port": self.port,
                "modes": ["xsalsa20_poly1305", "xsalsa20_poly1305_suffix", "xsalsa20_poly1305_lite",
                          "xsalsa20_poly1305_lite_rtpsize", "aead_aes256_gcm", "aead_aes256_gcm_rtpsize"],
                "streams": [{
                    "active": False,
                    "quality": 0,
                    "rid": "",
                    "rtx_ssrc": self.rtx_ssrc,
                    "ssrc": self.video_ssrc,
                    "type": "video"
                }]
            }
        }


class UdpSessionDescriptionEvent(Event):
    OP = VoiceGatewayOp.SESSION_DESCRIPTION

    def __init__(self, mode: str, key: bytes):
        self.mode = mode
        self.key = key

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "secret_key": [b for b in self.key],
                "mode": self.mode
            }
        }


class RtcSessionDescriptionEvent(Event):
    OP = VoiceGatewayOp.SESSION_DESCRIPTION

    def __init__(self, sdp: str):
        self.sdp = sdp

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "audio_codec": "opus",
                "video_codec": "H264",
                "media_session_id": "50d1809fc221526fd39fba2de2f5e64d",
                "sdp": self.sdp
            }
        }


class SpeakingEvent(Event):
    OP = VoiceGatewayOp.SPEAKING

    def __init__(self, ssrc: int, user_id: int, speaking: int):
        self.ssrc = ssrc
        self.speaking = speaking
        self.user_id = user_id

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "ssrc": self.ssrc,
                "speaking": self.speaking,
                "user_id": str(self.user_id)
            }
        }
