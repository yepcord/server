from datetime import datetime
from io import BytesIO
from json import dumps

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage
from tests.api.utils import TestClientType, create_users, create_guild, create_guild_channel, create_message, rel_block, \
    create_dm_channel, create_sticker, create_emoji, create_dm_group, create_invite, create_webhook
from tests.yep_image import YEP_IMAGE


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

    await create_message(client, user, channel["id"], exp_code=400, content="test reply",
                                 message_reference={'message_id': str(Snowflake.makeId()), "fail_if_not_exists": True})


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

    message = await create_message(client, user, channel_id, sticker_ids=[sticker["id"], str(Snowflake.makeId())])
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

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages?limit=505", headers=headers)
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

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/reactions/not-reaction",
                            headers=headers)
    assert resp.status_code == 400

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


@pt.mark.asyncio
async def test_get_messages_search():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    channel = await create_dm_group(client, user, [])
    headers = {"Authorization": user["token"]}
    await create_message(client, user, channel["id"], content="test", nonce="123456789")
    await create_message(client, user, channel["id"], content="test1", nonce="123456789")
    await create_message(client, user, channel["id"], content="123test", nonce="123456789")
    await create_message(client, user, channel["id"], content="t123est", nonce="123456789")
    await create_message(client, user, channel["id"], content="te st", nonce="123456789")
    await create_message(client, user, channel["id"], content="test 123test", nonce="123456789")

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/search?content=test", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["messages"]) == 4

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/search?content=test+123test", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["messages"]) == 1

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/search?content=test&author_id=123",
                            headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["messages"]) == 0

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/search?author_id={user['id']}",
                            headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["messages"]) == 6


@pt.mark.asyncio
async def test_message_delete_not_own_guild():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    channel = await create_guild_channel(client, user1, guild, "test_channel")
    invite = await create_invite(client, user1, channel["id"])
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.post(f"/api/v9/invites/{invite['code']}", headers=headers2)
    assert resp.status_code == 200

    message = await create_message(client, user2, channel["id"], content="test", nonce="123456789", tts=False)

    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers1)
    assert resp.status_code == 204

    message = await create_message(client, user1, channel["id"], content="test", nonce="123456789", tts=False)
    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers2)
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_message_delete_not_own_dm():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    channel = await create_dm_channel(client, user1, user2)
    message = await create_message(client, user1, channel["id"], content="test", nonce="123456789", tts=False)
    headers2 = {"Authorization": user2["token"]}

    resp = await client.delete(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers2)
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_webhook_message_with_embed():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{
                                 "title": "test",
                                 "type": "qwe",
                                 "description": "test embed",
                                 "url": "https://example.com/",
                                 "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                 "color": 0xff0000,
                                 "footer": {"text": "test footer", "icon_url": "http://example.com/icon.png"},
                                 "image": {"url": "https://example.com/image.png"},
                                 "thumbnail": {"url": "https://example.com/thumb.png"},
                                 "video": {"url": "https://example.com/video.mp4"},
                                 "author": {"name": "test author", "icon_url": "http://example.com/icon.png"},
                                 "fields": [{"name": "test name 1", "value": "test value 1"},
                                            {"name": "test name 2", "value": "test value 2"}],
                             }]})
    assert resp.status_code == 200
    message = await resp.get_json()
    assert not message["content"]
    assert len(message["embeds"]) == 1
    embed = message["embeds"][0]
    assert embed["title"] == "test"
    assert embed["type"] == "rich"
    assert embed["description"] == "test embed"
    assert embed["url"] == "https://example.com/"
    assert embed["color"] == 0xff0000
    assert embed["footer"] == {"text": "test footer", "icon_url": "http://example.com/icon.png"}
    assert embed["image"] == {"url": "https://example.com/image.png"}
    assert embed["thumbnail"] == {"url": "https://example.com/thumb.png"}
    assert embed["video"] == {"url": "https://example.com/video.mp4"}
    assert embed["author"] == {"name": "test author", "icon_url": "http://example.com/icon.png"}
    assert embed["fields"] == [{"name": "test name 1", "value": "test value 1"},
                               {"name": "test name 2", "value": "test value 2"}]


@pt.mark.asyncio
async def test_message_with_embed_errors():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test" * 256}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "description": "a" * 4097}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "url": "wrong://example.com"}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "timestamp": "not-a-timestamp"}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "color": -1}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "color": 0xffffff + 1}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test"}]*15})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_message_with_embed_footer_errors():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "footer": {"text": ""}}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "footer" not in json["embeds"][0]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "footer": {"text": "a" * 2049}}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "footer": {
                                 "text": "a", "icon_url": "wrong://example.com/icon.png"}}]})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_message_with_embed_media_errors():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "image": {"url": None}}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "image" not in json["embeds"][0]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "thumbnail": {"url": None}}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "thumbnail" not in json["embeds"][0]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "video": {"url": None}}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "video" not in json["embeds"][0]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "image": {"url": "wrong://example.com/icon.png"}}]})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_message_with_embed_author_errors():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "author": {"name": ""}}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "author" not in json["embeds"][0]

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "author": {"name": "a" * 257}}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "author": {"name": "a", "url": "wrong://idk"}}]})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_message_with_embed_fields_errors():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, 'test_text_channel')
    webhook = await create_webhook(client, user, channel["id"])

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "fields": [{"name": "k", "value": "v"}]*30}]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["embeds"][0]["fields"]) == 25

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "fields": [{"name": "", "value": "v"}]}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "fields": [{"name": "", "value": ""}]}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "fields": [{"name": "k" * 257, "value": "v"}]}]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/webhooks/{webhook['id']}/{webhook['token']}?wait=true",
                             json={"embeds": [{"title": "test", "fields": [{"name": "k", "value": "v" * 1025}]}]})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_message_pings():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    message = await create_message(client, user, channel["id"], content=f"<@!{user['id']}>")
    assert len(message["mentions"]) == 1
    assert message["mentions"][0]["id"] == user["id"]

    message = await create_message(client, user, channel["id"], content=f"<@{Snowflake.makeId()}>")
    assert len(message["mentions"]) == 0

    message = await create_message(client, user, channel["id"], content=f"<@&{guild['id']}>")
    assert len(message["mentions"]) == 0
    assert len(message["mention_roles"]) == 1
    assert message["mention_roles"][0] == guild["id"]


@pt.mark.asyncio
async def test_get_message():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    headers = {"Authorization": user["token"]}

    nonce = str(Snowflake.makeId())
    message = await create_message(client, user, channel["id"], content="test message", nonce=nonce)
    assert message["author"]["id"] == user['id']
    assert message["content"] == "test message"
    assert message["type"] == 0
    assert message["guild_id"] == guild['id']

    del message["nonce"]
    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/{message['id']}", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == message


@pt.mark.asyncio
async def test_get_message_interaction_without_interaction():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    headers = {"Authorization": user["token"]}

    message = await create_message(client, user, channel["id"], content="test message")

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages/{message['id']}/interaction-data",
                            headers=headers)
    assert resp.status_code == 404
