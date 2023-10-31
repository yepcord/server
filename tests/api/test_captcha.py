import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.config import Config
from src.yepcord.snowflake import Snowflake
from .utils import TestClientType


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_captcha_fail():
    Config.CAPTCHA["enabled"] = "hcaptcha"
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    resp = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{_id}",
        "email": f"{_id}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert resp.status_code == 400
    json = await resp.get_json()
    assert "captcha_key" in json
    assert "token" not in json

    resp = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{_id}",
        "email": f"{_id}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
        "captcha_key": "10000000-aaaa-bbbb-cccc-000000000000",
    })
    assert resp.status_code == 400
    json = await resp.get_json()
    assert "captcha_key" in json
    assert "token" not in json
    Config.CAPTCHA["enabled"] = None


@pt.mark.asyncio
async def test_captcha_success():
    Config.CAPTCHA["enabled"] = "hcaptcha"
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    resp = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{_id}",
        "email": f"{_id}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
        "captcha_key": "10000000-aaaa-bbbb-cccc-000000000001",
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "token" in json
    Config.CAPTCHA["enabled"] = None


@pt.mark.asyncio
async def test_captcha_success_recaptcha():
    Config.CAPTCHA["enabled"] = "recaptcha"
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    resp = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{_id}",
        "email": f"{_id}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
        "captcha_key": "anything-is-correct",
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "token" in json
    Config.CAPTCHA["enabled"] = None


@pt.mark.asyncio
async def test_captcha_incorrect():
    Config.CAPTCHA["enabled"] = "unknown-service"
    client: TestClientType = app.test_client()
    _id = Snowflake.makeId()
    resp = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{_id}",
        "email": f"{_id}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
        "captcha_key": "anything-is-correct",
    })
    assert resp.status_code == 400
    json = await resp.get_json()
    assert "captcha_key" in json
    assert "token" not in json
    Config.CAPTCHA["enabled"] = None
