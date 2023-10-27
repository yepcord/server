from datetime import date

import pytest as pt
import pytest_asyncio
from tortoise import connections

from src.rest_api.main import app
from src.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, create_application
from ..yep_image import YEP_IMAGE


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_get_teams_empty():  # TODO: move to test_teams.py when teams endpoints will be added
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    resp = await client.get(f"/api/v9/teams", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_get_applications_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    resp = await client.get(f"/api/v9/applications", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_application():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    application = await create_application(client, user, "testApp")
    assert application["name"] == "testApp"
    assert application["bot"]["id"] == application["id"]
    assert application["bot"]["username"] == application["name"]

    resp = await client.get(f"/api/v9/applications", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.get(f"/api/v9/applications/{application['id']}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == application["name"]
    assert json["bot"]["id"] == application["id"]
    assert json["bot"]["username"] == application["name"]


@pt.mark.asyncio
async def test_edit_application():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers=headers,
                              json={"name": "123", "icon": YEP_IMAGE, "bot_public": False,
                                    "bot_require_code_grant": False})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "123"
    assert json["bot"]["username"] == "testApp"
    assert len(json["icon"]) == 32
    assert len(json["bot"]["avatar"]) == 32
    assert not json["bot_public"]
    assert not json["bot_require_code_grant"]

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers=headers, json={"icon": "a"*32})
    assert resp.status_code == 200
    json_new = await resp.get_json()
    assert json["icon"] == json_new["icon"]

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers=headers, json={"icon": "not-image"})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_edit_application_bot():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/applications/{application['id']}/bot", headers=headers,
                              json={"avatar": YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["avatar"]) == 32

    resp = await client.patch(f"/api/v9/applications/{application['id']}/bot", headers=headers,
                              json={"avatar": "a"*32})
    assert resp.status_code == 200
    json_new = await resp.get_json()
    assert json["avatar"] == json_new["avatar"]

    resp = await client.patch(f"/api/v9/applications/{application['id']}/bot", headers=headers,
                              json={"avatar": "not-image"})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_application_secret_reset():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")

    resp = await client.post(f"/api/v9/applications/{application['id']}/reset",
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["secret"]


@pt.mark.asyncio
async def test_application_bot_token_reset():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")

    resp = await client.post(f"/api/v9/applications/{application['id']}/bot/reset",
                             headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]

    resp = await client.get(f"/api/v9/users/@me", headers={"Authorization": f"Bot {json['token']}"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == application["id"]
    assert json["username"] == application["name"]


@pt.mark.asyncio
async def test_application_delete():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")

    resp = await client.post(f"/api/v9/applications/{application['id']}/delete",
                             headers={"Authorization": user["token"]})
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/applications/{application['id']}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_application_no_usernames_left():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    username = str(Snowflake.makeId())
    users = []
    userdatas = []
    for d in range(1, 10000):
        uid = Snowflake.makeId()
        users.append((uid, f"test_user_{uid}@test.yepcord.ml"))
        userdatas.append((uid, uid, date(2000, 1, 1), username, d))

    conn = connections.get("default")
    await conn.execute_many("INSERT INTO `user`(`id`, `email`, `password`) VALUES (%s, %s, '123456')", users)
    await conn.execute_many(
        "INSERT INTO `userdata`(`id`, `user_id`, `birth`, `username`, `discriminator`, `flags`, `public_flags`) "
        "VALUES (%s, %s, %s, %s, %s, 0, 0)",
        userdatas
    )

    application = await create_application(client, user, username)
    assert application["name"] == username
    assert application["bot"]["id"] == application["id"]
    assert application["bot"]["username"] == application["name"] + application["id"]
