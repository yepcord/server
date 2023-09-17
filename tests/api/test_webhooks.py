from asyncio import get_event_loop

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from tests.api.utils import TestClientType, create_users, create_guild, create_webhook, \
    create_guild_channel
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
async def test_webhooks_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/webhooks", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_webhook():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')

    webhook = await create_webhook(client, user, channel["id"])
    assert webhook["name"] == "Captain Hook"
    assert webhook["avatar"] is None
    assert webhook["guild_id"] == guild["id"]
    assert webhook["user"]["id"] == user["id"]


@pt.mark.asyncio
async def test_get_channel_webhooks():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.get(f"/api/v9/channels/{channel['id']}/webhooks", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == webhook['id']
    assert json[0]["guild_id"] == guild['id']


@pt.mark.asyncio
async def test_edit_webhook():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    channel2 = await create_guild_channel(client, user, guild, 'test_text_channel2')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.patch(f"/api/v9/webhooks/{webhook['id']}", headers={"Authorization": user["token"]},
                              json={'channel_id': channel2["id"], 'name': 'Test webhook', "avatar": YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel2["id"]
    assert json["name"] == "Test webhook"
    assert json["guild_id"] == guild["id"]
    assert len(json["avatar"]) == 32


@pt.mark.asyncio
async def test_get_webhook():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.get(f"/api/v9/webhooks/{webhook['id']}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel["id"]
    assert json["name"] == webhook["name"]
    assert json["guild_id"] == guild["id"]


@pt.mark.asyncio
async def test_post_webhook_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}",
                             headers={"Authorization": user["token"]},
                             json={'content': 'test message sent from webhook'})
    assert resp.status_code == 204

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             headers={"Authorization": user["token"]},
                             json={'content': 'test message sent from webhook 2'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["author"]["bot"]
    assert json["author"]["id"] == webhook["id"]
    assert json["author"]["discriminator"] == "0000"
    assert json["content"] == "test message sent from webhook 2"
    assert json["type"] == 0
    assert json["guild_id"] == guild["id"]


@pt.mark.asyncio
async def test_delete_webhook():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.delete(f"/api/v9/webhooks/{webhook['id']}")
    assert resp.status_code == 403
    resp = await client.delete(f"/api/v9/webhooks/{webhook['id']}", headers={"Authorization": user["token"]})
    assert resp.status_code == 204

    webhook = await create_webhook(client, user, channel["id"])
    resp = await client.delete(f"/api/v9/webhooks/{webhook['id']}/{webhook['token']}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/webhooks", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []
