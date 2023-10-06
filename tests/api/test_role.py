import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from tests.api.utils import TestClientType, create_users, create_guild, create_role, add_user_to_guild
from tests.yep_image import YEP_IMAGE


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_create_role():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    role = await create_role(client, user, guild["id"])
    assert role["name"] == "new role"

    role = await create_role(client, user, guild["id"], icon=YEP_IMAGE)
    assert role["name"] == "new role"
    assert len(role["icon"]) == 32


@pt.mark.asyncio
async def test_change_roles_positions():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles", headers={"Authorization": user["token"]},
                              json=[{'id': role["id"], 'position': 1}])
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json[0]["id"] == guild["id"]
    assert json[1]["id"] == role["id"]


@pt.mark.asyncio
async def test_change_roles_members_positions_fail():
    client: TestClientType = app.test_client()
    user1, user2 = await create_users(client, 2)
    guild = await create_guild(client, user1, "Test Guild")
    await add_user_to_guild(client, guild, user1, user2)
    role1 = await create_role(client, user1, guild["id"])
    role2 = await create_role(client, user1, guild["id"])

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles", headers={"Authorization": user1["token"]},
                              json=[{"id": role1["id"], "position": 1}, {"id": role2["id"], "position": 2}])
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role1['id']}", json={"permissions": "8"},
                              headers={"Authorization": user1["token"]})
    assert resp.status_code == 200
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role2['id']}", json={"permissions": "8"},
                              headers={"Authorization": user1["token"]})
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role1['id']}/members",
                              headers={"Authorization": user1["token"]}, json={"member_ids": [user2["id"]]})
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles", headers={"Authorization": user2["token"]},
                              json=[{"id": role1["id"], "position": 2}, {"id": role2["id"], "position": 1}])
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role2['id']}/members",
                              headers={"Authorization": user2["token"]}, json={"member_ids": [user1["id"]]})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_edit_role():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])

    resp = await client.patch(
        f"/api/v9/guilds/{guild['id']}/roles/{role['id']}", headers={"Authorization": user["token"]}, json={
            "name": "test role", "permissions": "268436496", "color": 15277667, "icon": YEP_IMAGE, "unicode_emoji": None
        }
    )
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test role"
    assert json["permissions"] == "268436496"
    assert json["color"] == 15277667
    assert len(json["icon"]) == 32

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{guild['id']}", json={"name": "test role"},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "@everyone"


@pt.mark.asyncio
async def test_delete_role():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/roles/{role['id']}",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 204
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role['id']}", json={},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_get_roles_member_counts():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/roles/member-counts",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert (await resp.get_json() == {guild["id"]: 0, role["id"]: 0})


@pt.mark.asyncio
async def test_get_role_connections():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/roles/{role['id']}/connections/configuration",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0


@pt.mark.asyncio
async def test_get_role_members():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    role = await create_role(client, user, guild["id"])
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/@me", headers=headers,
                              json={"roles": [role["id"]]})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/roles/{role['id']}/member-ids",
                            headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == [user["id"]]
