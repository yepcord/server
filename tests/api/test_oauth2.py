from urllib.parse import urlparse, parse_qs

import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, create_application, create_guild, create_ban, add_user_to_guild
from ..utils import register_app_error_handler

register_app_error_handler(app)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_authorization_get():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")

    resp = await client.get(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=idk",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 400

    resp = await client.get(f"/api/v9/oauth2/authorize?scope=identify",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 400

    resp = await client.get(f"/api/v9/oauth2/authorize?client_id={Snowflake.makeId()}&scope=identify",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 404

    resp = await client.get(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["application"]["name"] == "testApp"

    resp = await client.get(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify+bot",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["application"]["name"] == application["bot"]["username"]
    assert len(json["guilds"]) == 1
    assert json["guilds"][0]["id"] == guild["id"]


@pt.mark.asyncio
async def test_authorize():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    redirect = "http://127.0.0.1/test"

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers={"Authorization": user["token"]},
                              json={"redirect_uris": [redirect]})
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=idk"
                             f"&redirect_uri={redirect}", headers={"Authorization": user["token"]},
                             json={"authorize": True})
    assert resp.status_code == 400
    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={Snowflake.makeId()}&scope=identify"
                             f"&redirect_uri={redirect}", headers={"Authorization": user["token"]},
                             json={"authorize": True})
    assert resp.status_code == 404
    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify"
                             f"&redirect_uri={redirect}1", headers={"Authorization": user["token"]},
                             json={"authorize": True})
    assert resp.status_code == 200
    assert "invalid_request" in (await resp.get_json())["location"]
    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify"
                             f"&redirect_uri={redirect}", headers={"Authorization": user["token"]},
                             json={"authorize": False})
    assert resp.status_code == 200
    assert "access_denied" in (await resp.get_json())["location"]

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify"
                             f"&redirect_uri={redirect}", headers={"Authorization": user["token"]},
                             json={"authorize": True})
    assert resp.status_code == 200
    assert "?code=" in (await resp.get_json())["location"]


@pt.mark.asyncio
async def test_exchange_token():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    redirect = "http://127.0.0.1/test"

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers={"Authorization": user["token"]},
                              json={"redirect_uris": [redirect]})
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/applications/{application['id']}/reset",
                             headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    secret = json["secret"]

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=identify"
                             f"&redirect_uri={redirect}", headers={"Authorization": user["token"]},
                             json={"authorize": True})
    assert resp.status_code == 200
    location = (await resp.get_json())["location"]
    assert "?code=" in location
    code = parse_qs(urlparse(location).query).get("code")[0]

    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret + "a"),
                             form={"grant_type": "authorization_code"})
    assert resp.status_code == 401, await resp.get_json()
    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"] + "a", secret),
                             form={"grant_type": "authorization_code"})
    assert resp.status_code == 401
    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret),
                             form={"grant_type": "authorization_code"})
    assert resp.status_code == 400
    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret),
                             form={"grant_type": "authorization_code", "code": "a" + code})
    assert resp.status_code == 400
    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret),
                             form={"grant_type": "authorization_code", "code": code + "a"})
    assert resp.status_code == 400
    resp = await client.post(f"/api/v9/oauth2/token", form={"grant_type": "authorization_code", "code": code + "a"})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret),
                             form={"grant_type": "authorization_code", "code": code})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token_type"] == "Bearer"
    assert json["expires_in"] == 604800
    assert json["scope"] == "identify"
    assert (token := json["access_token"])
    assert json["refresh_token"]

    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == user["id"]
    assert json["username"] == user["username"]
    assert "email" not in json

    resp = await client.get("/api/v9/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pt.mark.asyncio
async def test_client_credentials():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")

    resp = await client.post(f"/api/v9/applications/{application['id']}/reset",
                             headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    secret = json["secret"]

    resp = await client.post(f"/api/v9/oauth2/token", auth=(application["id"], secret),
                             form={"grant_type": "client_credentials", "scope": "identify email"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token_type"] == "Bearer"
    assert json["expires_in"] == 604800
    assert json["scope"] == "identify email"
    assert (token := json["access_token"])
    assert "refresh_token" not in json

    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == user["id"]
    assert json["username"] == user["username"]
    assert "email" in json


@pt.mark.asyncio
async def test_authorize_bot():
    client: TestClientType = app.test_client()
    user1, user2 = await create_users(client, 2)
    guild = await create_guild(client, user1, "test")
    application = await create_application(client, user1, "testApp")
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot", headers=headers1,
                             json={"authorize": True, "permissions": "8"})
    assert resp.status_code == 200
    location = (await resp.get_json())["location"]
    assert "invalid_request" in location

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot", headers=headers1,
                             json={"authorize": True, "permissions": "8", "guild_id": str(Snowflake.makeId())})
    assert resp.status_code == 404

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot", headers=headers2,
                             json={"authorize": True, "permissions": "8", "guild_id": guild["id"]})
    assert resp.status_code == 403

    await add_user_to_guild(client, guild, user1, user2)

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot", headers=headers2,
                             json={"authorize": True, "permissions": "8", "guild_id": guild["id"]})
    assert resp.status_code == 403

    await create_ban(client, user1, guild, application["id"])

    resp = await client.post(f"/api/v9/oauth2/authorize?client_id={application['id']}&scope=bot", headers=headers1,
                             json={"authorize": True, "permissions": "8", "guild_id": guild["id"]})
    assert resp.status_code == 200
    location = (await resp.get_json())["location"]
    assert "authorized" in location

    resp = await client.post(f"/api/v9/applications/{application['id']}/bot/reset",
                             headers={"Authorization": user1["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]

    resp = await client.get(f"/api/v9/users/@me/guilds", headers={"Authorization": f"Bot {json['token']}"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == guild["id"]

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/integrations", headers={"Authorization": user1["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1


@pt.mark.asyncio
async def test_wrong_token():
    client: TestClientType = app.test_client()
    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Unknown 123456789.ABCDEF"})
    assert resp.status_code == 401

    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Bearer 123456789.ABCDEF.QWE"})
    assert resp.status_code == 401

    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Bearer 123456789.ABCDEF"})
    assert resp.status_code == 401

    resp = await client.get("/api/v9/users/@me", headers={"Authorization": f"Bot 123456789.ABCDEF"})
    assert resp.status_code == 401
