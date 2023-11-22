import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.enums import MessageFlags
from tests.api.utils import TestClientType, create_users, create_guild, create_guild_channel, create_message, \
    create_thread, create_dm_group


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_create_thread():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, "test_channel")
    headers = {"Authorization": user["token"]}

    message = await create_message(client, user, channel["id"], content="test")
    thread = await create_thread(client, user, message, name="test123", auto_archive_duration=1441)
    assert thread["thread_metadata"]["auto_archive_duration"] == 1440

    resp = await client.get(f"/api/v9/channels/{channel['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 2
    json = [msg for msg in json if msg["id"] == message["id"]][0]
    assert "thread" in json
    assert json["flags"] & MessageFlags.HAS_THREAD == MessageFlags.HAS_THREAD
    assert json["thread"]["id"] == thread["id"]
    assert json["thread"]["name"] == thread["name"]


@pt.mark.asyncio
async def test_create_thread_dm_group():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    channel = await create_dm_group(client, user, [])
    message = await create_message(client, user, channel["id"], content="test")

    await create_thread(client, user, message, name="test123", auto_archive_duration=1440, exp_code=403)
