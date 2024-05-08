from asyncio import sleep
from copy import deepcopy
from json import dumps

import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.enums import ChannelType
from yepcord.yepcord.snowflake import Snowflake
from yepcord.yepcord.utils import b64encode
from .utils import TestClientType, create_users, create_application, create_guild, add_bot_to_guild, bot_token, \
    create_dm_channel, create_dm_group, generate_slash_command_payload
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

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands?with_localizations=true",
                            headers=bot_headers)
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
async def test_application_get_commands_different_bot():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application1 = await create_application(client, user, "testApp1")
    application2 = await create_application(client, user, "testApp2")

    resp = await client.post(f"/api/v9/applications/{application1['id']}/bot/reset",
                             headers={"Authorization": user["token"]})
    token1 = (await resp.get_json())["token"]

    resp = await client.post(f"/api/v9/applications/{application2['id']}/bot/reset",
                             headers={"Authorization": user["token"]})
    token2 = (await resp.get_json())["token"]

    resp = await client.get(f"/api/v9/applications/{application1['id']}/commands",
                            headers={"Authorization": f"Bot {token1}"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/applications/{application2['id']}/commands",
                            headers={"Authorization": f"Bot {token2}"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/applications/{application1['id']}/commands",
                            headers={"Authorization": f"Bot {token2}"})
    assert resp.status_code == 404

    resp = await client.get(f"/api/v9/applications/{application2['id']}/commands",
                            headers={"Authorization": f"Bot {token1}"})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_create_commands():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    options = [{"name": "idk", "description": "idk", "type": 6, "choices": [1, 2, 3], "channel_types": [3],
                "min_value": 1, "max_value": 10, "min_length": -1, "max_length": 6001}]
    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc", "options": options})
    assert resp.status_code == 200, await resp.get_json()
    json = await resp.get_json()
    assert json["options"][0].get("choices") is None
    assert json["options"][0].get("channel_types") is None

    options = [{"name": "idk", "description": "idk", "type": 3, "choices": ["1", "2", "3"],
                "min_length": -1, "max_length": 6001},
               {"name": "idk2", "description": "idk", "type": 7, "channel_types": [3]},
               {"name": "idk2", "description": "idk", "type": 4, "min_value": 5, "max_value": 15}]
    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test1", "description": "desc", "options": options})
    assert resp.status_code == 200, await resp.get_json()
    json = await resp.get_json()
    assert json["options"][0]["choices"] == ["1", "2", "3"]
    assert json["options"][0]["min_length"] == 0
    assert json["options"][0]["max_length"] == 6000
    assert json["options"][1]["channel_types"] == [3]
    assert json["options"][2]["min_value"] == 5
    assert json["options"][2]["max_value"] == 15

    options = [{"name": "idk", "description": "idk", "type": 3, "min_length": 10, "max_length": 5}]
    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test1", "description": "desc", "options": options})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_get_guild_commands():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    guild2 = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    await add_bot_to_guild(client, user, guild2, application)
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    for i in range(3):
        resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                                 json={"type": 1, "name": f"test-{i}", "description": "desc"})
        assert resp.status_code == 200

    resp = await client.post(f"/api/v9/applications/{application['id']}/guilds/{guild['id']}/commands",
                             headers=bot_headers, json={"type": 1, "name": f"test-guild", "description": "desc"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["guild_id"] == guild["id"]

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/application-commands/{application['id']}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 4

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/application-commands/{Snowflake.makeId()}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 0

    resp = await client.get(f"/api/v9/guilds/{guild2['id']}/application-commands/{application['id']}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["application_commands"]) == 3


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

    options = [{"name": f"o{i}", "description": "-", "type": 3} for i in range(30)]
    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc", "options": options,
                                   "name_localizations": {"uk": "a"*31}})
    assert resp.status_code == 200
    command = await resp.get_json()
    assert len(command["options"]) == 25

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.delete(f"/api/v9/applications/{application['id']}/commands/{command['id']}",
                               headers=bot_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 0


@pt.mark.asyncio
async def test_create_command_fail():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    application = await create_application(client, user, "testApp")
    token = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {token}"}

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc", "name_localizations": {"a": "a"}})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc",
                                   "description_localizations": {"a": "a"}})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers,
                             json={"type": 1, "name": "test", "description": "desc",
                                   "name_localizations": {"uk": "a"*33}})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_execute_slash_command():
    client: TestClientType = app.test_client()
    user, user2 = await create_users(client, 2)
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    headers2 = {"Authorization": user2["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test", "option": [
            {"type": 3, "name": "string", "description": "-"},
            {"type": 4, "name": "integer", "description": "-"},
            {"type": 10, "name": "number", "description": "-"},
            {"type": 5, "name": "boolean", "description": "-"},
            {"type": 6, "name": "user", "description": "-"},
            {"type": 7, "name": "channel", "description": "-"},
            {"type": 8, "name": "role", "description": "-"},
        ]})
    assert resp.status_code == 200
    command = await resp.get_json()

    payload = generate_slash_command_payload(application, guild, channel, command, [
                    {"type": 3, "name": "string", "value": "asd"},
                    {"type": 4, "name": "integer", "value": "123"},
                    {"type": 10, "name": "number", "value": "123.45"},
                    {"type": 5, "name": "boolean", "value": True},
                    {"type": 6, "name": "user", "value": user["id"]},
                    {"type": 7, "name": "channel", "value": channel["id"]},
                    {"type": 8, "name": "role", "value": guild["id"]},
                ])

    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 204

    await sleep(3.5)  # Wait for wait_for_interaction() to execute

    wrong_payload = payload | {"application_id": str(Snowflake.makeId())}
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(wrong_payload)})
    assert resp.status_code == 404

    wrong_payload = payload | {"guild_id": str(Snowflake.makeId())}
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(wrong_payload)})
    assert resp.status_code == 404

    resp = await client.post(f"/api/v9/interactions", headers=headers2, form={"payload_json": dumps(payload)})
    assert resp.status_code == 403

    dm_group = await create_dm_group(client, user, [])
    wrong_payload = payload | {"channel_id": dm_group["id"]}
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(wrong_payload)})
    assert resp.status_code == 404

    wrong_payload = deepcopy(payload)
    wrong_payload["data"]["id"] = str(Snowflake.makeId())
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(wrong_payload)})
    assert resp.status_code == 404
