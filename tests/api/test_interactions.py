from json import dumps

import pytest as pt
import pytest_asyncio

from src.gateway.main import app as gw_app
from src.rest_api.main import app
from src.yepcord.enums import ChannelType, GatewayOp
from src.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, create_application, create_guild, add_bot_to_guild, bot_token, \
    GatewayClient, gateway_cm, generate_slash_command_payload


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_slash_command_options():
    client: TestClientType = app.test_client()
    user, user2 = await create_users(client, 2)
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test", "options": [
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

    payload = {
        "type": 2,
        "application_id": application["id"],
        "guild_id": guild["id"],
        "channel_id": channel["id"],
        "session_id": "0",
        "nonce": str(Snowflake.makeId()),
        "data": {
            "version": command["version"],
            "id": command["id"],
            "name": command["name"],
            "type": command["type"],
            "application_command": command,
            "options": [
                {"type": 3, "name": "string", "value": "asd"},
                {"type": 4, "name": "integer", "value": "123"},
                {"type": 10, "name": "number", "value": "123.45"},
                {"type": 5, "name": "boolean", "value": True},
                {"type": 6, "name": "user", "value": user["id"]},
                {"type": 7, "name": "channel", "value": channel["id"]},
                {"type": 8, "name": "role", "value": guild["id"]},
            ],
            "attachments": [],
        }
    }

    async with gateway_cm(gw_app):
        gw_client = gw_app.test_client()
        cl = GatewayClient(bot_token_)
        async with gw_client.websocket('/') as ws:
            event_coro = await cl.awaitable_wait_for(GatewayOp.DISPATCH, "INTERACTION_CREATE")
            await cl.run(ws)

            resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
            assert resp.status_code == 204

            event = await event_coro

    assert event["type"] == 2
    assert event["version"] == 1
    assert event["application_id"] == application["id"]
    assert event["channel_id"] == channel["id"]
    assert event["guild_id"] == guild["id"]
    assert len(event["data"]["resolved"]) == 4
    assert event["data"]["resolved"]["users"][user["id"]]["id"] == user["id"]
    assert user["id"] in event["data"]["resolved"]["members"]
    assert event["data"]["resolved"]["channels"][channel["id"]]["id"] == channel["id"]
    assert event["data"]["resolved"]["roles"][guild["id"]]["id"] == guild["id"]
    assert event["data"]["options"] == [
        {"type": 3, "name": "string", "value": "asd"},
        {"type": 4, "name": "integer", "value": 123},
        {"type": 10, "name": "number", "value": 123.45},
        {"type": 5, "name": "boolean", "value": True},
        {"type": 6, "name": "user", "value": user["id"]},
        {"type": 7, "name": "channel", "value": channel["id"]},
        {"type": 8, "name": "role", "value": guild["id"]}
    ]


@pt.mark.asyncio
async def test_answer_to_slash_command():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test"})
    assert resp.status_code == 200
    command = await resp.get_json()

    payload = generate_slash_command_payload(application, guild, channel, command, [])

    async with gateway_cm(gw_app):
        gw_client = gw_app.test_client()
        cl = GatewayClient(bot_token_)
        async with gw_client.websocket('/') as ws:
            event_coro = await cl.awaitable_wait_for(GatewayOp.DISPATCH, "INTERACTION_CREATE")
            await cl.run(ws)

            resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
            assert resp.status_code == 204

            event = await event_coro

    int_id = event["id"]
    int_token = event["token"]

    resp = await client.post(f"/api/v9/interactions/{int_id}/{int_token}/callback", json={
        "type": 4, "data": {"flags": 0}})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/interactions/{int_id}/{int_token}/callback", json={
        "type": 4, "data": {"content": "test interaction response"}})
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_defer_slash_command():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test"})
    assert resp.status_code == 200
    command = await resp.get_json()

    payload = generate_slash_command_payload(application, guild, channel, command, [])
    async with gateway_cm(gw_app):
        gw_client = gw_app.test_client()
        cl = GatewayClient(bot_token_)
        async with gw_client.websocket('/') as ws:
            event_coro = await cl.awaitable_wait_for(GatewayOp.DISPATCH, "INTERACTION_CREATE")
            await cl.run(ws)

            resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
            assert resp.status_code == 204

            event = await event_coro

    int_id = event["id"]
    int_token = event["token"]

    resp = await client.post(f"/api/v9/interactions/{int_id}/{int_token}/callback", json={"type": 5})
    assert resp.status_code == 204

    resp = await client.post(f"/api/v9/interactions/{int_id}/{int_token}/callback", json={"type": 5})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/webhooks/{application['id']}/wrong_token", json={})
    assert resp.status_code == 404

    resp = await client.post(f"/api/v9/webhooks/{application['id']}/{int_token}?wait=true", json={})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/webhooks/{application['id']}/{int_token}?wait=true", json={"content": "test"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["content"] == "test"
    assert json["application_id"] == application["id"]
    assert json["interaction"]["user"]["id"] == user["id"]


@pt.mark.asyncio
async def test_slash_command_wrong_version():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test"})
    assert resp.status_code == 200
    command = await resp.get_json()
    payload = generate_slash_command_payload(application, guild, channel, command, [])

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test changed"})
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_slash_command_wrong_options():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")
    guild2 = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    channel2 = [channel for channel in guild2["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test", "options": [{"type": 3, "name": "a", "description": "-"}]})
    assert resp.status_code == 200
    command = await resp.get_json()

    payload = generate_slash_command_payload(application, guild, channel, command, [])
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 400

    payload = generate_slash_command_payload(application, guild, channel, command, [
        {"type": 3, "name": "b", "value": "asd"}
    ])
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 400

    payload = generate_slash_command_payload(application, guild, channel, command, [
        {"type": 4, "name": "a", "value": 123}
    ])
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 400

    # Wrong guild
    p = generate_slash_command_payload(application, guild2, channel2, command, [
        {"type": 3, "name": "a", "value": "123"}
    ])
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(p)})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_slash_command_wrong_resolved():
    client: TestClientType = app.test_client()
    user, user2 = await create_users(client, 2)
    guild = await create_guild(client, user, "Test")
    guild2 = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    channel2 = [channel for channel in guild2["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 1, "name": "test", "description": "test", "options": [
            {"type": 6, "name": "user", "description": "-", "required": False},
            {"type": 7, "name": "channel", "description": "-", "required": False},
            {"type": 8, "name": "role", "description": "-", "required": False},
        ]})
    assert resp.status_code == 200
    command = await resp.get_json()

    async with gateway_cm(gw_app):
        gw_client = gw_app.test_client()
        cl = GatewayClient(bot_token_)
        async with gw_client.websocket('/') as ws:
            await cl.run(ws)

            async def _resolved(type_: int, name: str, value: str, resolved_types: set[str]=None):
                event_coro = await cl.awaitable_wait_for(GatewayOp.DISPATCH, "INTERACTION_CREATE")
                p = generate_slash_command_payload(application, guild, channel, command, [
                    {"type": type_, "name": name, "value": value}
                ])
                resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(p)})
                assert resp.status_code == 204
                event = await event_coro
                if resolved_types is None:
                    assert event["data"]["resolved"] == {}
                else:
                    assert set(event["data"]["resolved"].keys()) == resolved_types

            await _resolved(6, "user", str(Snowflake.makeId()))
            await _resolved(6, "user", user2["id"], {"users"})
            await _resolved(7, "channel", str(Snowflake.makeId()))
            await _resolved(7, "channel", channel2["id"])
            await _resolved(8, "role", str(Snowflake.makeId()))
            await _resolved(8, "role", guild2["id"])
