from json import dumps

import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.enums import ChannelType
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import b64encode
from .utils import TestClientType, create_users, create_application, create_guild, add_bot_to_guild, bot_token, \
    create_dm_channel, create_dm_group


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_get_and_create_commands():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc 123"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["description"] == "desc 123"

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 4, "name": "test", "description": "desc"})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_get_guild_commands():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    for i in range(3):
        resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                                 json={"type": 1, "name": f"test-{i}", "description": "desc"})
        assert resp.status_code == 200

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/application-commands/{application['id']}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 3

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/application-commands/{Snowflake.makeId()}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 0


@pt.mark.asyncio
async def test_search_commands():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "asdqwe", "description": "desc"})
    assert resp.status_code == 200
    for i in range(5):
        resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                                 json={"type": 1, "name": f"test-{i}", "description": "desc"})
        assert resp.status_code == 200

    resp = await client.get(f"/api/v9/channels/{channel['id']}/application-commands/search?include_applications=true"
                            f"&limit=4", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 4
    assert len(json["applications"]) == 1

    resp = await client.get(f"/api/v9/channels/{channel['id']}/application-commands/search?limit=3"
                            f"&cursor={json['cursor']['next']}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 2
    assert len(json["applications"]) == 0

    channel = await create_dm_channel(client, user, {"id": application["id"]})
    resp = await client.get(f"/api/v9/channels/{channel['id']}/application-commands/search?limit=3"
                            f"&query=asd", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 1

    group = await create_dm_group(client, user, [])
    resp = await client.get(f"/api/v9/channels/{group['id']}/application-commands/search?limit=3",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 403

    resp = await client.get(f"/api/v9/channels/{channel['id']}/application-commands/search?limit=3"
                            f"&cursor={b64encode(dumps([1, 2, 3]))}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 3

    resp = await client.get(f"/api/v9/channels/{channel['id']}/application-commands/search?limit=3"
                            f"&cursor={b64encode(dumps(['1']))}", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 3


@pt.mark.asyncio
async def test_delete_command():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc"})
    assert resp.status_code == 200
    command = await resp.get_json()

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.delete(f"/api/v9/applications/{application['id']}/commands/{command['id']}",
                               headers=bot_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0
