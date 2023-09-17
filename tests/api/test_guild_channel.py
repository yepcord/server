from asyncio import get_event_loop

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from tests.api.utils import TestClientType, create_users, create_guild, create_guild_channel, create_invite


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
async def test_create_guild_channels():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    parent_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_CATEGORY][0]["id"]

    # Create text channel
    text = await create_guild_channel(client, user, guild, 'test_text_channel', 0, parent_id)
    assert text["type"] == 0
    assert text["name"] == "test_text_channel"
    assert text["parent_id"] == parent_id
    assert text["guild_id"] == guild["id"]

    # Create voice channel
    voice = await create_guild_channel(client, user, guild, 'test_voice_channel', 2, parent_id)
    assert voice["type"] == 2
    assert voice["name"] == "test_voice_channel"
    assert voice["parent_id"] == parent_id
    assert voice["guild_id"] == guild["id"]


@pt.mark.asyncio
async def test_change_guild_channels_positions():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_CATEGORY][0]["id"]
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/channels", headers={"Authorization": user["token"]},
                              json=[{'id': channel_id, 'position': 1}])
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_create_invite():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]

    invite = await create_invite(client, user, channel_id)
    assert invite["inviter"]["id"] == user["id"]
    assert invite["channel"]["id"] == channel_id
    assert invite["guild"]["id"] == guild["id"]
    assert invite["max_age"] == 604800
    assert invite["max_uses"] == 0
    assert invite["uses"] == 0


@pt.mark.asyncio
async def test_get_channel_invites():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    await create_invite(client, user, channel_id)

    resp = await client.get(f"/api/v9/channels/{channel_id}/invites", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["inviter"]["id"] == user["id"]
    assert json[0]["channel"]["id"] == channel_id
    assert json[0]["guild"]["id"] == guild["id"]
    assert json[0]["max_age"] == 604800
    assert json[0]["max_uses"] == 0
    assert json[0]["uses"] == 0


@pt.mark.asyncio
async def test_edit_channel():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_VOICE][0]["id"]

    resp = await client.patch(f"/api/v9/channels/{channel_id}", headers={"Authorization": user["token"]},
                              json={'bitrate': 384000, 'user_limit': 69})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["id"] == channel_id
    assert json["guild_id"] == guild["id"]
    assert json["user_limit"] == 69
    assert json["bitrate"] == 384000


@pt.mark.asyncio
async def test_delete_channel():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_VOICE][0]["id"]

    resp = await client.delete(f"/api/v9/channels/{channel_id}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["id"] == channel_id
    assert json["guild_id"] == guild["id"]


@pt.mark.asyncio
async def test_set_channel_permissions():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    headers = {"Authorization": user["token"]}

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user['id']}", headers=headers,
                            json={'id': user['id'], 'type': 1, 'allow': '0', 'deny': '0'})
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user['id']}", headers=headers,
                            json={'id': '160071946643243008', 'type': 1, 'allow': '1024', 'deny': '0'})
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user['id']}", headers=headers,
                            json={'id': user['id'], 'type': 0, 'allow': '0', 'deny': '1049600'})
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_delete_channel_permission_overwrite():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    headers = {"Authorization": user["token"]}

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user['id']}", headers=headers,
                            json={'id': user['id'], 'type': 1, 'allow': '0', 'deny': '0'})
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/channels/{channel_id}/permissions/{guild['id']}", headers=headers)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_channel_get():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == channel["id"]
    assert json["name"] == channel["name"]
