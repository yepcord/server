from base64 import b64encode
from datetime import datetime, timedelta
from io import BytesIO

import pytest as pt
import pytest_asyncio
from PIL import Image

from src.rest_api.main import app
from src.yepcord.enums import ChannelType, ScheduledEventStatus
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage
from tests.api.utils import TestClientType, create_users, create_guild, create_event
from tests.yep_image import YEP_IMAGE


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_create_scheduled_event():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    channel = [ch for ch in guild["channels"] if ch["type"] == ChannelType.GUILD_VOICE][0]
    await create_event(client, guild, user, name="test", entity_type=2, image=YEP_IMAGE, channel_id=channel["id"])

    await create_event(client, guild, user, name="yep", entity_type=2, channel_id=str(Snowflake.makeId()), exp_code=400)

    img = BytesIO()
    Image.open(getImage(YEP_IMAGE)).save(img, format="WEBP")
    img = f"data:image/webp;base64,{b64encode(img.getvalue()).decode('utf8')}"
    await create_event(client, guild, user, name="yep", entity_type=3, image=img, exp_code=400)


@pt.mark.asyncio
async def test_get_scheduled_event():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    channel_id = [ch for ch in guild["channels"] if ch["type"] == ChannelType.GUILD_VOICE][0]["id"]
    event = await create_event(client, guild, user, name="test", entity_type=2, image=YEP_IMAGE, channel_id=channel_id,
                               end=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/scheduled-events", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}?with_user_count=true",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test"
    assert json["guild_id"] == guild["id"]
    assert json["user_count"] == 1

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/scheduled-events/{Snowflake.makeId()}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 404

    resp = await client.get(f"/api/v9/users/@me/scheduled-events?guild_ids={guild['id']}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.get(f"/api/v9/users/@me/scheduled-events?guild_ids={Snowflake.makeId()}",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_scheduled_event_subscribe_unsubscribe():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    event = await create_event(client, guild, user, name="test", entity_type=3, image=YEP_IMAGE,
                               end=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}/users/@me",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}/users/@me",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/scheduled-events/{Snowflake.makeId()}/users/@me",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 404

    resp = await client.put(f"/api/v9/guilds/{guild['id']}/scheduled-events/{Snowflake.makeId()}/users/@me",
                            headers={"Authorization": user["token"]})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_scheduled_event_delete():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    event = await create_event(client, guild, user, name="test", entity_type=3, image=YEP_IMAGE,
                               end=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/scheduled-events/{Snowflake.makeId()}",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 404

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_edit_scheduled_event():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    channel_id = [ch for ch in guild["channels"] if ch["type"] == ChannelType.GUILD_VOICE][0]["id"]
    event = await create_event(client, guild, user, name="test", entity_type=2, image=YEP_IMAGE, channel_id=channel_id,
                               end=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                              headers={"Authorization": user["token"]}, json={"name": "123", "image": YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "123"

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                              headers={"Authorization": user["token"]}, json={"status": ScheduledEventStatus.COMPLETED})
    assert resp.status_code == 400

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                              headers={"Authorization": user["token"]}, json={"status": ScheduledEventStatus.ACTIVE})
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                              headers={"Authorization": user["token"]}, json={"status": ScheduledEventStatus.SCHEDULED})
    assert resp.status_code == 400

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{Snowflake.makeId()}",
                              headers={"Authorization": user["token"]}, json={"name": "test"})
    assert resp.status_code == 404

    img = BytesIO()
    Image.open(getImage(YEP_IMAGE)).save(img, format="WEBP")
    img = f"data:image/webp;base64,{b64encode(img.getvalue()).decode('utf8')}"
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/scheduled-events/{event['id']}",
                              headers={"Authorization": user["token"]}, json={"image": img})
    assert resp.status_code == 400
