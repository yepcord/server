import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
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

    resp = await client.patch(f"/api/v9/applications/{application['id']}", headers={"Authorization": user["token"]},
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


@pt.mark.asyncio
async def test_edit_application_bot():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")

    resp = await client.patch(f"/api/v9/applications/{application['id']}/bot", headers={"Authorization": user["token"]},
                              json={"avatar": YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["avatar"]) == 32


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
