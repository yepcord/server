from asyncio import get_event_loop
from io import BytesIO
from json import dumps

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage
from tests.api.utils import TestClientType, create_users, create_guild, create_guild_channel, create_message, rel_block, \
    create_dm_channel, create_sticker, create_emoji
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
async def test_get_messages_in_empty_channel():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_send_guild_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    headers = {"Authorization": user["token"]}

    resp = await client.post(f"/api/v9/channels/{channel['id']}/typing", headers=headers)
    assert resp.status_code == 204

    nonce = str(Snowflake.makeId())
    message = await create_message(client, user, channel["id"], content="test message", nonce=nonce)
    assert message["author"]["id"] == user['id']
    assert message["content"] == "test message"
    assert message["type"] == 0
    assert message["guild_id"] == guild['id']
    assert message["nonce"] == nonce

    nonce = str(Snowflake.makeId())
    message = await create_message(client, user, channel["id"], content="message with emoji 💀", nonce=nonce)
    assert message["author"]["id"] == user['id']
    assert message["content"] == "message with emoji 💀"
    assert message["type"] == 0
    assert message["guild_id"] == guild['id']
    assert message["nonce"] == nonce

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) >= 2


@pt.mark.asyncio
async def test_messages_replying():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")

    nonce = "1087430130973802496"
    message = await create_message(client, user, channel["id"], content=" test ", nonce=nonce, tts=False)
    assert message["channel_id"] == channel["id"]
    assert message["author"]["id"] == user["id"]
    assert message["content"] == "test"
    assert message["edit_timestamp"] is None
    assert message["embeds"] == []
    assert not message["pinned"]
    assert message["type"] == 0
    assert message["nonce"] == nonce
    assert message["guild_id"] == guild["id"]

    reply = await create_message(client, user, channel["id"], content="test reply", nonce=nonce, tts=False,
                                 message_reference={'message_id': message["id"]})
    assert reply["channel_id"] == channel["id"]
    assert reply["author"]["id"] == user["id"]
    assert reply["content"] == "test reply"
    assert reply["message_reference"]["message_id"] == message["id"]
    assert reply["message_reference"]["guild_id"] == guild["id"]
    assert reply["message_reference"]["channel_id"] == channel["id"]
    assert reply["referenced_message"]["id"] == message["id"]
    assert reply["referenced_message"]["content"] == message["content"]


@pt.mark.asyncio
async def test_message_editing():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content="test", nonce="123456789", tts=False)
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers,
                              json={'content': 'test edited'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["content"] == "test edited"


@pt.mark.asyncio
async def test_message_deleting():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content="test", nonce="123456789", tts=False)
    headers = {"Authorization": user["token"]}

    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_send_message_blocked():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    channel = await create_dm_channel(client, user1, user2)
    assert await rel_block(client, user2, user1) == 204  # Block first user

    resp = await client.post(f"/api/v9/channels/{channel['id']}/messages", headers={"Authorization": user1["token"]},
                             json={"content": "test"})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_send_message_in_hidden_channel():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    channel = await create_dm_channel(client, user1, user2)

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user1["token"]})
    assert resp.status_code == 200

    await create_message(client, user2, channel["id"], content="test", nonce="123456789")


@pt.mark.asyncio
async def test_edit_message_from_other_user():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    channel = await create_dm_channel(client, user1, user2)
    message = await create_message(client, user2, channel["id"], content="test", nonce="123456789")

    resp = await client.patch(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", json={"content": "123456"},
                              headers={"Authorization": user1["token"]})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_send_empty_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")

    await create_message(client, user, channel["id"], exp_code=400)
    await create_message(client, user, channel["id"], content="", exp_code=400)


@pt.mark.asyncio
async def test_message_with_stickers():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    sticker = await create_sticker(client, user, guild["id"], "yep")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]

    message = await create_message(client, user, channel_id, sticker_ids=[sticker["id"]])
    assert len(message["stickers"]) == 1
    assert message["stickers"][0]["id"] == sticker["id"]
    assert message["sticker_items"][0]["id"] == sticker["id"]


@pt.mark.asyncio
async def test_message_with_attachment():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    headers = {"Authorization": user["token"]}

    def get_file() -> BytesIO:
        image = getImage(YEP_IMAGE)
        assert image is not None
        image.filename = "yep.png"
        image.headers = []
        return image
    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers, files={
        "file": get_file(),
    }, form={
        "payload_json": dumps({"attachments": [{"filename": "yep.png"}]})
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["attachments"]) == 1

    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers, files={
        f"files[{i}]": get_file() for i in range(11)
    }, form={
        "payload_json": dumps({"attachments": [{"filename": "yep.png"}]})
    })
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_add_message_reaction():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content="test", nonce="123456789")
    emoji = await create_emoji(client, user, guild["id"], "YEP")
    headers = {"Authorization": user["token"]}

    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/👍/@me",
                            headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    messages = await resp.get_json()
    assert len(messages) == 1
    assert messages[0]["id"] == message["id"]
    assert len(messages[0]["reactions"]) == 1
    assert messages[0]["reactions"][0] == {"count": 1, "emoji": {"id": None, "name": "👍"}, "me": True}

    resp = await client.put(
        f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/{emoji['name']}:{emoji['id']}/@me",
        headers=headers
    )
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    messages = await resp.get_json()
    assert len(messages[0]["reactions"]) == 2
    assert {"count": 1, "emoji": {"id": None, "name": "👍"}, "me": True} in messages[0]["reactions"]
    assert {"count": 1, "emoji": {"id": emoji['id'], "name": emoji['name']}, "me": True} in messages[0]["reactions"]

    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/notemoji/@me",
                            headers=headers)
    assert resp.status_code == 400
    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/not:emoji/@me",
                            headers=headers)
    assert resp.status_code == 400
    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/notemoji:123456/@me",
                            headers=headers)
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_remove_message_reaction():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content="test", nonce="123456789")
    emoji = await create_emoji(client, user, guild["id"], "YEP")
    headers = {"Authorization": user["token"]}

    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/👍/@me",
                            headers=headers)
    assert resp.status_code == 204

    resp = await client.put(
        f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/{emoji['name']}:{emoji['id']}/@me",
        headers=headers
    )
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    messages = await resp.get_json()
    assert len(messages[0]["reactions"]) == 2
    assert {"count": 1, "emoji": {"id": None, "name": "👍"}, "me": True} in messages[0]["reactions"]
    assert {"count": 1, "emoji": {"id": emoji['id'], "name": emoji['name']}, "me": True} in messages[0]["reactions"]

    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/👍/@me",
                               headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    messages = await resp.get_json()
    assert len(messages[0]["reactions"]) == 1
    assert messages[0]["reactions"][0] == {"count": 1, "emoji": {"id": emoji['id'], "name": emoji['name']}, "me": True}

    resp = await client.delete(
        f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/{emoji['name']}:{emoji['id']}/@me",
        headers=headers
    )
    assert resp.status_code == 204
    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    messages = await resp.get_json()
    assert "reactions" not in messages[0]

    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/notemoji/@me",
                               headers=headers)
    assert resp.status_code == 400
    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/not:emoji/@me",
                               headers=headers)
    assert resp.status_code == 400
    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/notemoji:1234/@me",
                               headers=headers)
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_get_message_reaction():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content="test", nonce="123456789")
    emoji = await create_emoji(client, user, guild["id"], "YEP")
    headers = {"Authorization": user["token"]}

    resp = await client.put(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/👍/@me",
                            headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/👍",
                            headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == user["id"]

    resp = await client.put(
        f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/{emoji['name']}:{emoji['id']}/@me",
        headers=headers
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/{emoji['name']}:{emoji['id']}",
        headers=headers
    )
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == user["id"]
