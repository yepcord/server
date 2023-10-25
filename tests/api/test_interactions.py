from json import dumps

import pytest as pt
import pytest_asyncio

from src.gateway.main import app as gw_app
from src.rest_api.main import app
from src.yepcord.enums import ChannelType, GatewayOp
from src.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, create_application, create_guild, add_bot_to_guild, bot_token, \
    GatewayClient, gateway_cm


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
