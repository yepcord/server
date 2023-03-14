from src.yepcord.enums import VoiceGatewayOp


class Event:
    OP: int

    async def json(self) -> dict: ...

class ReadyEvent(Event):
    OP = VoiceGatewayOp.READY

    def __init__(self, ssrc: int):
        self.ssrc = ssrc

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "ssrc": self.ssrc,
                "ip": "127.0.0.1",
                "port": 9999,
                "modes": ["xsalsa20_poly1305", "xsalsa20_poly1305_suffix", "xsalsa20_poly1305_lite"]
            }
        }

class SessionDescriptionEvent(Event):
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

class SpeakingEvent(Event):
    OP = VoiceGatewayOp.SPEAKING

    def __init__(self, ssrc: int, speaking: int, delay: int):
        self.ssrc = ssrc
        self.speaking = speaking
        self.delay = delay

    async def json(self) -> dict:
        return {
            "op": self.OP,
            "d": {
                "ssrc": self.ssrc,
                "speaking": self.speaking,
                "delay": self.delay
            }
        }