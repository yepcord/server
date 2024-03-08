from typing import Literal, Union, Optional

from pydantic import BaseModel


class UdpProtocolData(BaseModel):
    address: str
    port: str
    mode: str


class CodecsData(BaseModel):
    name: Literal["opus", "VP9", "VP8", "H264"]
    type: Literal["audio", "video"]
    priority: int
    payload_type: int
    rtx_payload_type: Optional[int] = None


class SelectProtocol(BaseModel):
    protocol: Literal["udp", "webrtc"]
    data: Union[str, UdpProtocolData]
    sdp: Optional[str] = None
    codecs: Optional[list[CodecsData]]
