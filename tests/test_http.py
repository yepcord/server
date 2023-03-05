from asyncio import get_event_loop
from base64 import b64encode

import pytest as pt
from src.rest_api.main import app
from src.yepcord.proto import PreloadedUserSettings, TextAndImagesSettings, RenderSpoilers


class TestVars:
    _vars = {}

    @staticmethod
    def get(item, default=None):
        return TestVars._vars.get(item, default)

    @staticmethod
    def set(item, value):
        TestVars._vars[item] = value

@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()

@pt.fixture(name='testapp')
async def _test_app():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    return app

@pt.mark.asyncio
async def test_login_fail(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": "test@yepcord.ml", "password": "test_passw0rd"})
    assert response.status_code == 400

@pt.mark.asyncio
async def test_register(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": "TestUser",
        "email": "test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])

@pt.mark.asyncio
async def test_resend_verification_email(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/verify/resend', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204

@pt.mark.asyncio
async def test_getme_success(testapp):
    client = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200

@pt.mark.asyncio
async def test_logout(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/logout', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204

@pt.mark.asyncio
async def test_getme_fail(testapp):
    client = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 401

@pt.mark.asyncio
async def test_login_success(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": "test@yepcord.ml", "password": "test_passw0rd"})
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])

@pt.mark.asyncio
async def test_change_username(testapp):
    client = (await testapp).test_client()
    response = await client.patch("/api/v9/users/@me", json={"username": "YepCordTest", "password": "test_passw0rd"}, headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200
    j = await response.get_json()
    TestVars.set("data", await response.get_json())
    assert j["username"] == "YepCordTest"

@pt.mark.asyncio
async def test_settings(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client = (await testapp).test_client()
    assert (await client.get("/api/v9/users/@me/connections", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/consent", headers=headers)).status_code == 200
    assert (await client.post("/api/v9/users/@me/consent", headers=headers, json={"grant": ["personalization"], "revoke": []})).status_code == 200
    assert (await client.patch("/api/v9/users/@me/settings", headers=headers, json={"afk_timeout": 300})).status_code == 200

@pt.mark.asyncio
async def test_settings_proto(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client = (await testapp).test_client()
    assert (await client.get("/api/v9/users/@me/settings-proto/1", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/2", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/3", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/4", headers=headers)).status_code == 400
    proto = PreloadedUserSettings(text_and_images=TextAndImagesSettings(render_spoilers=RenderSpoilers(value="ALWAYS")))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers, json={"settings": proto})).status_code == 200

@pt.mark.asyncio
async def test_register_other_user(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": "TestUser",
        "email": "user@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token_u2", j["token"])
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": j["token"]
    })
    assert response.status_code == 200
    TestVars.set("data_u2", await response.get_json())

@pt.mark.asyncio
async def test_relationships(testapp):
    headers = {"Authorization": TestVars.get("token")}
    headers_u2 = {"Authorization": TestVars.get("token_u2")}
    data = TestVars.get("data")
    data2 = TestVars.get("data_u2")
    client = (await testapp).test_client()

    response = await client.get('/api/v9/users/@me/relationships', headers=headers)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.get('/api/v9/users/@me/relationships', headers=headers_u2)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.post('/api/v9/users/@me/relationships', headers=headers, json={"username": data2["username"], "discriminator": data2["discriminator"]})
    assert response.status_code == 204
    response = await client.put(f"/api/v9/users/@me/relationships/{data['id']}", headers=headers, json={})
    assert response.status_code == 204

    response = await client.get('/api/v9/users/@me/relationships', headers=headers)
    assert response.status_code == 200
    assert len(await response.get_json()) == 1
    response = await client.get('/api/v9/users/@me/relationships', headers=headers_u2)
    assert response.status_code == 200
    assert len(await response.get_json()) == 1

    response = await client.get(f"/api/v9/users/{data2['id']}/profile", headers=headers)
    assert response.status_code == 200