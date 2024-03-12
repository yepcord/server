import re
from os import urandom
from urllib import parse

import pytest as pt
import pytest_asyncio
from pytest_httpx import HTTPXMock

from tests.api.utils import TestClientType, create_users
from tests.httpx_mock_callbacks import github_oauth_token_exchange, github_oauth_user_get, reddit_oauth_token_exchange, \
    reddit_oauth_user_get, twitch_oauth_token_exchange, spotify_oauth_token_exchange, twitch_oauth_user_get, \
    spotify_oauth_user_get
from yepcord.rest_api.main import app
from yepcord.yepcord.config import Config


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


httpx_token_callbacks = {
    "github": (github_oauth_token_exchange, {"url": re.compile(r'https://github.com/login/oauth/access_token?.+')}),
    "reddit": (reddit_oauth_token_exchange, {"url": "https://www.reddit.com/api/v1/access_token"}),
    "twitch": (twitch_oauth_token_exchange, {"url": "https://id.twitch.tv/oauth2/token"}),
    "spotify": (spotify_oauth_token_exchange, {"url": "https://accounts.spotify.com/api/token"}),
}
httpx_user_callbacks = {
    "github": (github_oauth_user_get, {"url": "https://api.github.com/user"}),
    "reddit": (reddit_oauth_user_get, {"url": "https://oauth.reddit.com/api/v1/me"}),
    "twitch": (twitch_oauth_user_get, {"url": "https://api.twitch.tv/helix/users"}),
    "spotify": (spotify_oauth_user_get, {"url": "https://api.spotify.com/v1/me"}),
}


@pt.mark.parametrize("service_name", ["github", "reddit", "twitch", "spotify"])
@pt.mark.asyncio
async def test_connection(service_name: str, httpx_mock: HTTPXMock):
    Config.update({"CONNECTIONS": {service_name: {"client_id": urandom(8).hex(), "client_secret": urandom(8).hex()}}})
    code = urandom(8).hex()
    access_token = urandom(8).hex()

    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    cb, kw = httpx_token_callbacks[service_name]
    httpx_mock.add_callback(cb(**Config.CONNECTIONS[service_name], code=code, access_token=access_token), **kw)
    cb, kw = httpx_user_callbacks[service_name]
    httpx_mock.add_callback(cb(access_token=access_token), **kw)

    resp = await client.get(f"/api/v9/connections/{service_name}/authorize", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    state = dict(parse.parse_qsl(parse.urlsplit(j["url"]).query))["state"]

    resp = await client.post(f"/api/v9/connections/{service_name}/callback", headers=headers,
                             json={"code": code, "state": state, "insecure": False, "friend_sync": False})
    assert resp.status_code == 204, await resp.get_json()

    resp = await client.get("/api/v9/users/@me/connections", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    assert len(j) == 1


@pt.mark.asyncio
async def test_connection_wrong_state():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    state = "123.456"
    resp = await client.post(f"/api/v9/connections/github/callback", headers=headers,
                             json={"code": "123456", "state": state, "insecure": False, "friend_sync": False})
    assert resp.status_code == 204, await resp.get_json()

    state = "abc-456"
    resp = await client.post(f"/api/v9/connections/github/callback", headers=headers,
                             json={"code": "123456", "state": state, "insecure": False, "friend_sync": False})
    assert resp.status_code == 204, await resp.get_json()

    resp = await client.get("/api/v9/users/@me/connections", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    assert len(j) == 0


@pt.mark.asyncio
async def test_connection_wrong_code(httpx_mock: HTTPXMock):
    Config.update({"CONNECTIONS": {"github": {"client_id": urandom(8).hex(), "client_secret": urandom(8).hex()}}})
    code = urandom(8).hex()
    access_token = urandom(8).hex()

    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    cb, kw = httpx_token_callbacks["github"]
    httpx_mock.add_callback(cb(**Config.CONNECTIONS["github"], code=code, access_token=access_token), **kw)

    resp = await client.get(f"/api/v9/connections/github/authorize", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    state = dict(parse.parse_qsl(parse.urlsplit(j["url"]).query))["state"]

    resp = await client.post(f"/api/v9/connections/github/callback", headers=headers,
                             json={"code": code+"1", "state": state, "insecure": False, "friend_sync": False})
    assert resp.status_code == 400

    resp = await client.get("/api/v9/users/@me/connections", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    assert len(j) == 0


@pt.mark.asyncio
async def test_connection_add_same_account_twice(httpx_mock: HTTPXMock):
    Config.update({"CONNECTIONS": {"github": {"client_id": urandom(8).hex(), "client_secret": urandom(8).hex()}}})
    code = urandom(8).hex()
    access_token = urandom(8).hex()

    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    cb, kw = httpx_token_callbacks["github"]
    httpx_mock.add_callback(cb(**Config.CONNECTIONS["github"], code=code, access_token=access_token), **kw)
    cb, kw = httpx_user_callbacks["github"]
    httpx_mock.add_callback(cb(access_token=access_token), **kw)

    for _ in range(2):
        resp = await client.get(f"/api/v9/connections/github/authorize", headers=headers)
        assert resp.status_code == 200
        j = await resp.get_json()
        state = dict(parse.parse_qsl(parse.urlsplit(j["url"]).query))["state"]

        resp = await client.post(f"/api/v9/connections/github/callback", headers=headers,
                                 json={"code": code, "state": state, "insecure": False, "friend_sync": False})
        assert resp.status_code == 204, await resp.get_json()

    resp = await client.get("/api/v9/users/@me/connections", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    assert len(j) == 1


@pt.mark.asyncio
async def test_connection_edit_delete(httpx_mock: HTTPXMock):
    Config.update({"CONNECTIONS": {"github": {"client_id": urandom(8).hex(), "client_secret": urandom(8).hex()}}})
    code = urandom(8).hex()
    access_token = urandom(8).hex()

    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    cb, kw = httpx_token_callbacks["github"]
    httpx_mock.add_callback(cb(**Config.CONNECTIONS["github"], code=code, access_token=access_token), **kw)
    cb, kw = httpx_user_callbacks["github"]
    httpx_mock.add_callback(cb(access_token=access_token), **kw)

    resp = await client.get(f"/api/v9/connections/github/authorize", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    state = dict(parse.parse_qsl(parse.urlsplit(j["url"]).query))["state"]

    resp = await client.post(f"/api/v9/connections/github/callback", headers=headers,
                             json={"code": code, "state": state, "insecure": False, "friend_sync": False})
    assert resp.status_code == 204, await resp.get_json()

    resp = await client.get("/api/v9/users/@me/connections", headers=headers)
    assert resp.status_code == 200
    j = await resp.get_json()
    assert len(j) == 1

    conn_id = j[0]["id"]

    resp = await client.patch(f"/api/v9/users/@me/connections/github1/{conn_id}", headers=headers,
                              json={"visibility": False})
    assert resp.status_code == 400

    resp = await client.patch(f"/api/v9/users/@me/connections/github/{conn_id}1", headers=headers,
                              json={"visibility": False})
    assert resp.status_code == 404

    resp = await client.patch(f"/api/v9/users/@me/connections/github/{conn_id}", headers=headers,
                              json={"visibility": False})
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v9/users/@me/connections/github1/{conn_id}", headers=headers)
    assert resp.status_code == 400

    resp = await client.delete(f"/api/v9/users/@me/connections/github/{conn_id}1", headers=headers)
    assert resp.status_code == 404

    resp = await client.delete(f"/api/v9/users/@me/connections/github/{conn_id}", headers=headers)
    assert resp.status_code == 204
