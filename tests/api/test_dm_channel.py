import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from src.yepcord.snowflake import Snowflake
from tests.api.utils import TestClientType, create_users, create_guild, create_dm_channel, create_dm_group, \
    create_message
from tests.yep_image import YEP_IMAGE


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_create_dm_channel():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers = {"Authorization": user1["token"]}

    channel = await create_dm_channel(client, user1, user2)
    recipients = [r["id"] for r in channel["recipients"]]
    assert recipients == [user2["id"]]
    assert channel["type"] == ChannelType.DM

    resp = await client.post(f"/api/v9/channels/{channel['id']}/messages", headers=headers,
                             json={"content": "test message"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers={"Authorization": user2["token"]})
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers={"Authorization": user3["token"]})
    assert resp.status_code == 401

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 200
    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_create_empty_dm_group():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    channel = await create_dm_group(client, user, [])
    assert channel["recipients"] == []
    assert channel["type"] == ChannelType.GROUP_DM

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 204
    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_create_empty_dm_group():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    await create_dm_group(client, user, [str(Snowflake.makeId())], exp_code=400)


@pt.mark.asyncio
async def test_create_group_from_dm():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers = {"Authorization": user1["token"]}

    channel = await create_dm_channel(client, user1, user2)

    resp = await client.put(f"/api/v9/channels/{channel['id']}/recipients/{user3['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/users/@me/channels", headers=headers)
    json = await resp.get_json()
    channel_id = [ch for ch in json if ch["type"] == ChannelType.GROUP_DM and len(ch["recipient_ids"]) == 2][0]["id"]

    resp = await client.delete(f"/api/v9/channels/{channel_id}/recipients/{user3['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/channels/{channel['id']}/recipients/{Snowflake.makeId()}", headers=headers)
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_try_add_delete_recipients_in_guild_channel():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test Guild")
    headers = {"Authorization": user1["token"]}

    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]

    resp = await client.put(f"/api/v9/channels/{channel_id}/recipients/{user2['id']}", headers=headers)
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v9/channels/{channel_id}/recipients/{user2['id']}", headers=headers)
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_try_delete_recipient_from_non_owner():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers2 = {"Authorization": user2["token"]}

    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])
    resp = await client.delete(f"/api/v9/channels/{channel['id']}/recipients/{user1['id']}", headers=headers2)
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_message_in_dm():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers2 = {"Authorization": user2["token"]}
    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])
    channel_id = channel["id"]
    message = await create_message(client, user1, channel_id, content="test message")

    resp = await client.post(f"/api/v9/channels/{channel_id}/messages/{message['id']}/ack", headers=headers2, json={})
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/channels/{channel_id}/messages/{message['id']}/ack", headers=headers2, json={
        "manual": True, "mention_count": 1
    })
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v9/channels/{channel_id}/messages/ack", headers=headers2)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_pin_message_in_dm():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers2 = {"Authorization": user2["token"]}
    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])
    channel_id = channel["id"]
    message = await create_message(client, user1, channel_id, content="test message")

    resp = await client.put(f"/api/v9/channels/{channel_id}/pins/{message['id']}", headers=headers2)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel_id}/pins", headers=headers2)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.delete(f"/api/v9/channels/{channel_id}/pins/{message['id']}", headers=headers2)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel_id}/pins", headers=headers2)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0


@pt.mark.asyncio
async def test_edit_dm_group():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers2 = {"Authorization": user2["token"]}
    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])

    resp = await client.patch(f"/api/v9/channels/{channel['id']}", headers=headers2, json={
        "icon": YEP_IMAGE,
        "name": "test_dm_channel"
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test_dm_channel"
    assert json["icon"] is not None


@pt.mark.asyncio
async def test_change_dm_group_owner():
    client: TestClientType = app.test_client()
    user1, user2, user3, user4 = (await create_users(client, 4))
    headers = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}
    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])

    resp = await client.patch(f"/api/v9/channels/{channel['id']}", headers=headers2, json={
        "owner_id": Snowflake.makeId(),
    })
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/channels/{channel['id']}", headers=headers, json={
        "owner_id": Snowflake.makeId(),
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["owner_id"] == channel["owner_id"]

    resp = await client.patch(f"/api/v9/channels/{channel['id']}", headers=headers, json={
        "owner_id": user4["id"],
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["owner_id"] == channel["owner_id"]

    resp = await client.patch(f"/api/v9/channels/{channel['id']}", headers=headers, json={
        "owner_id": user2["id"],
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["owner_id"] == user2["id"]


@pt.mark.asyncio
async def test_delete_dm_group():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    headers = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}
    headers3 = {"Authorization": user3["token"]}
    channel = await create_dm_group(client, user1, [user2["id"], user3["id"]])

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers2)
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers=headers3)
    assert resp.status_code == 200
    channel = await resp.get_json()
    assert channel["owner_id"] == user3["id"]

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers3)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers=headers3)
    assert resp.status_code == 404
