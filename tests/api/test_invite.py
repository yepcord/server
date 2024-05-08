import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.enums import ChannelType
from .utils import TestClientType, create_users, create_guild, create_invite, create_dm_group, create_ban
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
async def test_get_guild_invite():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    invite = await create_invite(client, user, channel["id"])

    resp = await client.get(f"/api/v9/invites/{invite['code']}?with_counts=true",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel"]["id"] == channel["id"]
    assert json["channel"]["name"] == channel["name"]
    assert json["guild"]["id"] == guild["id"]
    assert json["guild"]["name"] == guild["name"]


@pt.mark.asyncio
async def test_get_dm_invite():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    channel = await create_dm_group(client, user, [])
    invite = await create_invite(client, user, channel["id"])

    resp = await client.get(f"/api/v9/invites/{invite['code']}?with_counts=true",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel"]["id"] == channel["id"]
    assert json["channel"]["recipients"] == [{"username": user["username"]}]


@pt.mark.asyncio
async def test_use_guild_invite():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    invite = await create_invite(client, user1, channel["id"])

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel"]["id"] == channel["id"]
    assert json["channel"]["name"] == channel["name"]
    assert json["guild"]["id"] == guild["id"]
    assert json["guild"]["name"] == guild["name"]
    assert json["new_member"]

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "new_member" not in json

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == channel["id"]
    assert json["guild_id"] == channel["guild_id"]


@pt.mark.asyncio
async def test_use_dm_invite():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    channel = await create_dm_group(client, user1, [])
    invite = await create_invite(client, user1, channel["id"])

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel"]["id"] == channel["id"]
    assert json["channel"]["name"] == channel["name"]
    assert json["new_member"]

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert not json["new_member"]

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == channel["id"]


@pt.mark.asyncio
async def test_use_dm_invite_member_limit():
    client: TestClientType = app.test_client()
    user1, *users, user2 = (await create_users(client, 11))
    channel = await create_dm_group(client, user1, [u["id"] for u in users])
    invite = await create_invite(client, user1, channel["id"])

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_use_guild_invite_banned():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    invite = await create_invite(client, user1, channel["id"])
    await create_ban(client, user1, guild, user2["id"])

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_delete_guild_invite():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    invite = await create_invite(client, user1, channel["id"])

    resp = await client.delete(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user1["token"]})
    assert resp.status_code == 200
    resp = await client.delete(f"/api/v9/invites/{invite['code']}", headers={"Authorization": user1["token"]})
    assert resp.status_code == 404
