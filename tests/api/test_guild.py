from asyncio import get_event_loop

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from tests.api.utils import TestClientType, create_users, create_guild, create_invite
from tests.yep_image import YEP_IMAGE


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
async def test_create_guild():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    assert guild["name"] == 'Test Guild'
    assert guild["icon"] is None
    assert guild["description"] is None
    assert guild["splash"] is None
    assert guild["discovery_splash"] is None
    assert guild["emojis"] == []
    assert len(guild["channels"]) > 0


@pt.mark.asyncio
async def test_guild_subscriptions():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/premium/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == [{'ended': False, 'user_id': user["id"]}] * 30)


@pt.mark.asyncio
async def test_guild_templates_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/templates", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_edit_guild():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}", headers=headers, json={
        'name': 'Test Guild Renamed', 'afk_channel_id': None, 'afk_timeout': 900,
        'verification_level': 0, 'icon': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "Test Guild Renamed"
    assert json["afk_channel_id"] is None
    assert json["afk_timeout"] == 900
    assert len(json["icon"]) == 32


@pt.mark.asyncio
async def test_guild_invites_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/invites", headers={"Authorization": user["token"]})
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_get_guild_invites():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    await create_invite(client, user, channel_id)

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/invites", headers={"Authorization": user["token"]})
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
async def test_get_vanity_url_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/vanity-url", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert (await resp.get_json() == {'code': None})


@pt.mark.asyncio
async def test_create_guild_template():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers={"Authorization": user["token"]},
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test"
    assert json["description"] == "test template"
    assert json["creator_id"] == user["id"]
    assert json["creator"]["id"] == user["id"]
    assert json["source_guild_id"] == guild["id"]
