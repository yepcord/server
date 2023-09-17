from asyncio import get_event_loop

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from .utils import TestClientType, create_users
from ..yep_image import YEP_IMAGE


@pt.fixture()
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_getme_success():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    response = await client.get("/api/v9/users/@me", headers={"Authorization": user["token"]})
    assert response.status_code == 200


@pt.mark.asyncio
async def test_change_username():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    response = await client.patch("/api/v9/users/@me", headers={"Authorization": user["token"]},
                                  json={"username": f"YepCordTest_{user['id']}", "password": user["password"]})
    assert response.status_code == 200
    response = await client.get("/api/v9/users/@me", headers={"Authorization": user["token"]})
    assert response.status_code == 200
    j = await response.get_json()
    assert j["username"] == f"YepCordTest_{user['id']}"


@pt.mark.asyncio
async def test_get_my_profile():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}
    user_id = user["id"]

    resp = await client.get(f"/api/v9/users/@me/profile?guild_id=invalid_id", headers=headers)  # Invalid id
    assert resp.status_code == 400

    # resp = await client.get(
    #    f"/api/v9/users/@me/profile?with_mutual_guilds=true&mutual_friends_count=true&guild_id={guild_id}",
    #    headers=headers)
    # assert resp.status_code == 200
    # json = await resp.get_json()
    # assert json["user"]["id"] == user_id
    # assert json["guild_member_profile"]["guild_id"] == guild_id
    # assert json["guild_member"]["user"]["id"] == user_id

    resp = await client.get(f"/api/v9/users/@me/profile?with_mutual_guilds=true&mutual_friends_count=true",
                            headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["user"]["id"] == user_id


@pt.mark.asyncio
async def test_edit_user_banner():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.patch("/api/v9/users/@me/profile", headers=headers, json={'banner': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["banner"]) == 32


@pt.mark.asyncio
async def test_edit_user_data():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.patch("/api/v9/users/@me", headers=headers,
                              json={'new_password': 'test_passw0rd_changed', 'password': 'invalid_password'})
    assert resp.status_code == 400

    resp = await client.patch("/api/v9/users/@me", headers=headers,
                              json={'email': f"new_{user['email']}", 'discriminator': '9999',
                                    'new_password': 'test_passw0rd_changed', 'password': 'test_passw0rd',
                                    'avatar': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["email"] == f"new_{user['email']}"
    assert json["discriminator"] == '9999'
    assert len(json["avatar"]) == 32
    assert not json["verified"]


@pt.mark.asyncio
async def test_change_username_dont_change_discriminator():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    headers = {"Authorization": user1["token"]}

    resp = await client.patch(f"/api/v9/users/@me", headers=headers, json={"username": user2["username"],
                                                                           "discriminator": user2["discriminator"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["username"] == user2["username"]
    assert json["discriminator"] != user2["discriminator"]


@pt.mark.asyncio
async def test_notes():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    headers = {"Authorization": user1["token"]}

    response = await client.get(f"/api/v9/users/@me/notes/{user2['id']}", headers=headers)  # No note
    assert response.status_code == 404
    response = await client.get(f"/api/v9/users/@me/notes/{user2['id'] + '1'}", headers=headers)  # No user
    assert response.status_code == 404
    response = await client.put(f"/api/v9/users/@me/notes/{user2['id'] + '1'}", headers=headers,
                                json={"note": "test"})  # No user
    assert response.status_code == 404

    response = await client.put(f"/api/v9/users/@me/notes/{user2['id']}", headers=headers,
                                json={"note": "test note 123!"})
    assert response.status_code == 204

    response = await client.get(f"/api/v9/users/@me/notes/{user2['id']}", headers=headers)
    assert response.status_code == 200
    json = await response.get_json()
    assert json["note"] == "test note 123!"


@pt.mark.asyncio
async def test_hypesquad_change_house():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 1})
    assert resp.status_code == 204
    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 2})
    assert resp.status_code == 204
    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 3})
    assert resp.status_code == 204

    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 4})
    assert resp.status_code == 400
