from json import dumps

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage
from tests.api.utils import TestClientType, create_users, create_guild, create_webhook, \
    create_guild_channel, create_sticker
from tests.yep_image import YEP_IMAGE


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

    resp = await client.patch(f"/api/v9/webhooks/{webhook['id']}/{webhook['token']}", json={'name': 'Test webhook 1'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "Test webhook 1"

    resp = await client.patch(f"/api/v9/webhooks/{webhook['id']}/{webhook['token']}", json={'channel_id': '123456789'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel2["id"]


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

    resp = await client.get(f"/api/v9/webhooks/{webhook['id']}/{webhook['token']}")
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel["id"]


@pt.mark.asyncio
async def test_post_webhook_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}",
                             json={'content': 'test message sent from webhook'})
    assert resp.status_code == 204

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={'content': 'test message sent from webhook 2'})
    assert resp.status_code == 200
    message = await resp.get_json()
    assert message["author"]["bot"]
    assert message["author"]["id"] == webhook["id"]
    assert message["author"]["discriminator"] == "0000"
    assert message["content"] == "test message sent from webhook 2"
    assert message["type"] == 0
    assert message["guild_id"] == guild["id"]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={'content': 'test reply', "message_reference": {'message_id': message["id"]}})
    assert resp.status_code == 200
    reply = await resp.get_json()
    assert reply["message_reference"]["message_id"] == message["id"]
    assert reply["message_reference"]["guild_id"] == guild["id"]
    assert reply["message_reference"]["channel_id"] == channel["id"]
    assert reply["referenced_message"]["id"] == message["id"]
    assert reply["referenced_message"]["content"] == message["content"]

    resp = await client.post(f"/api/webhooks/{Snowflake.makeId()}/{webhook['token']}",
                             json={'content': 'test message sent from webhook'})
    assert resp.status_code == 404

    resp = await client.post(f"/api/webhooks/{webhook['id']}/wrong-token",
                             json={'content': 'test message sent from webhook'})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_post_webhook_message_sticker():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])
    sticker = await create_sticker(client, user, guild["id"], "yep")

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={'sticker_ids': [sticker["id"]]})
    assert resp.status_code == 200
    message = await resp.get_json()
    assert len(message["stickers"]) == 1
    assert message["stickers"][0]["id"] == sticker["id"]
    assert message["sticker_items"][0]["id"] == sticker["id"]


@pt.mark.asyncio
async def test_post_webhook_message_attachment():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    file = getImage(YEP_IMAGE)
    file.filename = "yep.png"
    file.headers = []
    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true", files={
        "file": file,
    }, form={
        "payload_json": dumps({"attachments": [{"filename": "yep.png"}]})
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["attachments"]) == 1


@pt.mark.asyncio
async def test_post_webhook_empty_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}", json={'content': ''})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}", json={})
    assert resp.status_code == 400


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


@pt.mark.asyncio
async def test_edit_webhook_fail():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = await create_guild_channel(client, user1, guild, 'test_text_channel')
    webhook = await create_webhook(client, user1, channel["id"])

    resp = await client.patch(f"/api/v9/webhooks/{webhook['id']}/wrong-token", json={'name': 'Test webhook'})
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/webhooks/{Snowflake.makeId()}", json={'name': 'Test webhook'})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_get_webhook_fail():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = await create_guild_channel(client, user1, guild, 'test_text_channel')
    webhook = await create_webhook(client, user1, channel["id"])

    resp = await client.get(f"/api/v9/webhooks/{webhook['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 403

    resp = await client.get(f"/api/v9/webhooks/{webhook['id']}/wrong-token", headers={"Authorization": user2["token"]})
    assert resp.status_code == 403

    resp = await client.get(f"/api/v9/webhooks/{webhook['id']}/wrong-token")
    assert resp.status_code == 403

    resp = await client.get(f"/api/v9/webhooks/{Snowflake.makeId()}/wrong-token")
    assert resp.status_code == 404
