from asyncio import get_event_loop

import pytest as pt
import pytest_asyncio
from quart.testing.connections import WebsocketDisconnectError
from quart.typing import TestWebsocketConnectionProtocol

from src.remote_auth.main import app as ra_app
from src.rest_api.main import app
from src.yepcord.utils import b64encode
from .utils import TestClientType, create_users, RemoteAuthClient


@pt.fixture()
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    for func in ra_app.before_serving_funcs:
        await ra_app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()
    for func in ra_app.after_serving_funcs:
        await ra_app.ensure_async(func)()


@pt.mark.asyncio
async def test_remote_auth_success():
    client: TestClientType = app.test_client()
    ra_client: TestClientType = ra_app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}
    state = {"fingerprint": None, "handshake_token": None}

    async def on_fp(fp: str) -> None:
        resp = await client.post("/api/v9/users/@me/remote-auth/login", headers=headers, json={"fingerprint": fp})
        assert resp.status_code == 200
        json = await resp.get_json()
        assert "handshake_token" in json
        state.update({"fingerprint": fp, "handshake_token": json["handshake_token"]})

    async def on_userdata(userdata: str) -> None:
        uid, disc, avatar, username = userdata.split(":")
        assert uid == user["id"]
        assert disc == user["discriminator"]
        assert username == user["username"]

        resp = await client.post("/api/v9/users/@me/remote-auth/finish", headers=headers, json={
            "handshake_token": state["handshake_token"], "temporary_token": False
        })
        assert resp.status_code == 204

    async def on_token(token: str) -> None:
        resp = await client.get("/api/v9/users/@me", headers={"Authorization": token})
        assert resp.status_code == 200
        json = await resp.get_json()
        assert json["id"] == user["id"]

    cl = RemoteAuthClient(on_fp, on_userdata, on_token)

    async with ra_client.websocket('/') as ws:
        await cl.run(ws)

    assert not cl.results["cancel"]


@pt.mark.asyncio
async def test_remote_auth_cancel():
    client: TestClientType = app.test_client()
    ra_client: TestClientType = ra_app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}
    state = {"fingerprint": None, "handshake_token": None}

    async def on_fp(fp: str) -> None:
        resp = await client.post("/api/v9/users/@me/remote-auth/login", headers=headers, json={"fingerprint": fp})
        assert resp.status_code == 200
        json = await resp.get_json()
        state.update({"fingerprint": fp, "handshake_token": json["handshake_token"]})

    async def on_userdata(userdata: str) -> None:
        resp = await client.post("/api/v9/users/@me/remote-auth/cancel", headers=headers, json={
            "handshake_token": state["handshake_token"]
        })
        assert resp.status_code == 204

    cl = RemoteAuthClient(on_fp, on_userdata)

    async with ra_client.websocket('/') as ws:
        await cl.run(ws)

    assert cl.results["cancel"]


@pt.mark.asyncio
async def test_remote_auth_unknown_fp_and_token():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.post("/api/v9/users/@me/remote-auth/login", headers=headers, json={
        "fingerprint": b64encode("a" * 32)
    })
    assert resp.status_code == 404

    resp = await client.post("/api/v9/users/@me/remote-auth/finish", headers=headers, json={
        "handshake_token": "123456789", "temporary_token": False
    })
    assert resp.status_code == 404

    resp = await client.post("/api/v9/users/@me/remote-auth/cancel", headers=headers, json={
        "handshake_token": "123456789", "temporary_token": False
    })
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_remote_auth_same_keys():
    ra_client: TestClientType = ra_app.test_client()

    cl = RemoteAuthClient()
    cl.genKeys()

    async with ra_client.websocket('/') as ws:
        await ws.receive_json()
        await ws.send_json({"op": "init", "encoded_public_key": cl.pubKeyS})
        async with ra_client.websocket('/') as ws2:
            await ws2.receive_json()
            await ws2.send_json({"op": "init", "encoded_public_key": cl.pubKeyS})

            with pt.raises(WebsocketDisconnectError):
                await ws2.receive_json()


@pt.mark.asyncio
async def test_remote_auth_without_init():
    ra_client: TestClientType = ra_app.test_client()

    cl = RemoteAuthClient()
    cl.genKeys()

    async with ra_client.websocket('/') as ws:
        await ws.receive_json()
        await ws.send_json({"op": "nonce_proof", "encoded_public_key": cl.pubKeyS})
        with pt.raises(WebsocketDisconnectError):
            await ws.receive_json()

    async with ra_client.websocket('/') as ws:
        await ws.receive_json()
        await ws.send_json({"op": "heartbeat"})
        with pt.raises(WebsocketDisconnectError):
            await ws.receive_json()


@pt.mark.asyncio
async def test_remote_auth_wrong_nonce_hash():
    ra_client: TestClientType = ra_app.test_client()

    cl = RemoteAuthClient()
    cl.genKeys()

    async with ra_client.websocket('/') as ws:
        await ws.receive_json()
        await ws.send_json({"op": "init", "encoded_public_key": cl.pubKeyS})
        await ws.receive_json()
        await ws.send_json({"op": 'nonce_proof', "proof": b64encode("wrong proof")})
        with pt.raises(WebsocketDisconnectError):
            await ws.receive_json()
