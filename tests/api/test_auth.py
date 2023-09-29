from hashlib import sha256
from hmac import new
from json import dumps
from time import time

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.config import Config
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import b64decode, b64encode
from .utils import TestClientType, create_user, get_userdata, create_users


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


def generateEmailVerificationToken(user_id: int, email: str, key: bytes):
    key = new(key, str(user_id).encode('utf-8'), sha256).digest()
    t = int(time())
    sig = b64encode(new(key, f"{user_id}:{email}:{t}".encode('utf-8'), sha256).digest())
    token = b64encode(dumps({"id": user_id, "email": email, "time": t}))
    token += f".{sig}"
    return token


@pt.mark.asyncio
async def test_login_nonexistent_user():
    client: TestClientType = app.test_client()
    response = await client.post('/api/v9/auth/login', json={"login": f"{Snowflake.makeId()}_test@yepcord.ml",
                                                             "password": "test_passw0rd"})
    assert response.status_code == 400


@pt.mark.asyncio
async def test_register():
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    assert await create_user(client, f"{_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{_id}")


@pt.mark.asyncio
async def test_login_success():
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    assert await create_user(client, f"{_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{_id}")
    response = await client.post('/api/v9/auth/login', json={"login": f"{_id}_test@yepcord.ml",
                                                             "password": "test_passw0rd"})
    assert response.status_code == 200
    json = await response.get_json()
    assert "token" in json


@pt.mark.asyncio
async def test_login_fail_wrong_credentials():
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    assert await create_user(client, f"{_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{_id}")
    response = await client.post('/api/v9/auth/login', json={"login": f"{_id}_test_1@yepcord.ml",
                                                             "password": "test_passw0rd"})
    assert response.status_code == 400

    response = await client.post('/api/v9/auth/login', json={"login": f"{_id}_test@yepcord.ml",
                                                             "password": "test_passw0rd1"})
    assert response.status_code == 400

    response = await client.post('/api/v9/auth/login', json={"login": f"{_id}_test1@yepcord.ml",
                                                             "password": "test_passw0rd1"})
    assert response.status_code == 400


@pt.mark.asyncio
async def test_logout():
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    token = await create_user(client, f"{_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{_id}")
    response = await client.post('/api/v9/auth/logout', headers={"Authorization": token})
    assert response.status_code == 204
    with pt.raises(AssertionError):
        await get_userdata(client, token)


@pt.mark.asyncio
async def test_resend_verification_email():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    response = await client.post('/api/v9/auth/verify/resend', headers={"Authorization": user["token"]})
    assert response.status_code == 204


@pt.mark.asyncio
async def test_verify_email():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    token = generateEmailVerificationToken(int(user["id"]), user["email"], b64decode(Config.KEY))

    resp = await client.post("/api/v9/auth/verify", json={"token": ""})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/auth/verify", json={'token': "1"})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/auth/verify", json={'token': token})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    assert json["user_id"] == user["id"]
