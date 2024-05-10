from typing import Optional

from httpx import AsyncClient


class GoRpc:
    def __init__(self, rpc_addr: str):
        self._address = f"http://{rpc_addr}/rpc"

    async def create_endpoint(self, channel_id: int) -> Optional[int]:
        """
        Sends request to pion webrtc server to create new webrtc endpoint.
        :param channel_id: Id of channel/guild to associate created endpoint with
        :return: Endpoint port answer on success or None on error
        """
        async with AsyncClient() as cl:
            resp = await cl.post(self._address, json={
                "id": 0, "method": "Rpc.CreateApi", "params": [{"channel_id": str(channel_id)}]
            })
            j = resp.json()
            if j["error"] is None:
                return j["result"]
            print(j["error"])

    async def create_peer_connection(self, channel_id: int, session_id: int, offer: str) -> Optional[str]:
        """
        Sends request to pion webrtc server to create new peerConnection.
        :param channel_id: Id of channel/guild user associated with
        :param session_id: Id of voice session
        :param offer: Sdp offer
        :return: Sdp answer on success or None on error
        """
        async with AsyncClient() as cl:
            resp = await cl.post(self._address, json={
                "id": 0, "method": "Rpc.NewPeerConnection", "params": [
                    {"channel_id": str(channel_id), "session_id": str(session_id), "offer": offer}
                ]
            })
            j = resp.json()
            if j["error"] is None:
                return j["result"]
            print(j["error"])

    async def renegotiate(self, channel_id: int, session_id: int, offer: str) -> Optional[str]:
        """
        Sends re-negotiate request to pion webrtc server.
        :param channel_id: Id of channel/guild user associated with
        :param session_id: Id of voice session
        :param offer: Sdp offer
        :return: Sdp answer on success or None on error
        """
        async with AsyncClient() as cl:
            resp = await cl.post(self._address, json={
                "id": 0, "method": "Rpc.ReNegotiate", "params": [
                    {"channel_id": str(channel_id), "session_id": str(session_id), "offer": offer}
                ]
            })
            j = resp.json()
            if j["error"] is None:
                return j["result"]
            print(j["error"])
