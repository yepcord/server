from json import dumps

import pytest as pt
import pytest_asyncio

from yepcord.gateway.main import app as gw_app
from yepcord.rest_api.main import app
from yepcord.yepcord.enums import ChannelType, GatewayOp
from yepcord.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, create_application, create_guild, add_bot_to_guild, bot_token, \
    GatewayClient, gateway_cm, create_message


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_user_command():
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
        "type": 2, "name": "test", "description": "test"})
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
            "target_id": user["id"],
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
    assert len(event["data"]["resolved"]) == 2
    assert event["data"]["resolved"]["users"][user["id"]]["id"] == user["id"]
    assert user["id"] in event["data"]["resolved"]["members"]

    payload["data"]["target_id"] = str(Snowflake.makeId())
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_message_command():
    client: TestClientType = app.test_client()
    user, user2 = await create_users(client, 2)
    guild = await create_guild(client, user, "Test")
    application = await create_application(client, user, "testApp")
    await add_bot_to_guild(client, user, guild, application)
    headers = {"Authorization": user["token"]}
    bot_token_ = await bot_token(client, user, application)
    bot_headers = {"Authorization": f"Bot {bot_token_}"}
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    message = await create_message(client, user, channel["id"], content="test 123")

    resp = await client.post(f"/api/v9/applications/{application['id']}/commands", headers=bot_headers, json={
        "type": 3, "name": "test", "description": "test"})
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
            "target_id": message["id"],
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
    assert len(event["data"]["resolved"]) == 1
    assert event["data"]["resolved"]["messages"][message["id"]] == message

    payload["data"]["target_id"] = str(Snowflake.makeId())
    resp = await client.post(f"/api/v9/interactions", headers=headers, form={"payload_json": dumps(payload)})
    assert resp.status_code == 404
