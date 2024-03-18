from typing import Optional

from httpx import AsyncClient


class GoRpc:
    def __init__(self, rpc_addr: str):
        self._address = f"http://{rpc_addr}/rpc"

    async def create_endpoint(self, channel_id: int) -> Optional[int]:
        async with AsyncClient() as cl:
            resp = await cl.post(self._address, json={
                "id": 0, "method": "Rpc.CreateApi", "params": [{"channel_id": str(channel_id)}]
            })
            j = resp.json()
            if j["error"] is None:
                return j["result"]
            print(j["error"])

    async def create_peer_connection(self, channel_id: int, session_id: int, offer: str) -> Optional[str]:
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
