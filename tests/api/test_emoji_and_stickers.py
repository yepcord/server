from io import BytesIO

import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.enums import StickerType
from yepcord.yepcord.snowflake import Snowflake
from tests.api.utils import TestClientType, create_users, create_guild, create_emoji, create_sticker
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
async def test_get_emojis_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/emojis", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_emoji():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    emoji = await create_emoji(client, user, guild["id"], "YEP")
    assert emoji["name"] == "YEP"
    assert not emoji["animated"]
    assert emoji["available"]

    await create_emoji(client, user, guild["id"], " ", exp_code=400)
    await create_emoji(client, user, guild["id"], "123", "not image", exp_code=400)
    name = "test" * 16
    emoji = await create_emoji(client, user, guild["id"], name)
    assert emoji["name"] == name[:32]


@pt.mark.asyncio
async def test_get_emojis():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    emoji = await create_emoji(client, user, guild["id"], "YEP")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/emojis", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == emoji["id"]
    assert json[0]["name"] == "YEP"
    assert not json[0]["animated"]
    assert json[0]["available"]
    assert json[0]["user"]["id"] == user["id"]


@pt.mark.asyncio
async def test_edit_emoji_name():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    emoji = await create_emoji(client, user, guild["id"], "YEP")

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/emojis/{emoji['id']}", json={'name': 'YEP_test'},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP_test"
    assert not json["animated"]
    assert json["available"]

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/emojis/{Snowflake.makeId()}", json={'name': 'YEP_test1'},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 400

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/emojis/{emoji['id']}", json={'name': ' '},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP_test"

    name = "test"*16
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/emojis/{emoji['id']}", json={'name': name},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == name[:32]


@pt.mark.asyncio
async def test_emoji_delete():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    emoji = await create_emoji(client, user, guild["id"], "YEP")
    headers = {"Authorization": user["token"]}

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/emojis/{Snowflake.makeId()}", headers=headers)
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/emojis/{emoji['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/emojis", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_get_stickers_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/stickers", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_sticker():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    sticker = await create_sticker(client, user, guild["id"], "yep")
    assert sticker["name"] == "yep"
    assert sticker["tags"] == "slight_smile"
    assert sticker["type"] == StickerType.GUILD
    assert sticker["guild_id"] == guild["id"]
    assert sticker["available"]
    assert sticker["user"]["id"] == user["id"]


@pt.mark.asyncio
async def test_create_sticker_fail():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    image = BytesIO()
    assert image is not None
    image.filename = "yep.png"
    image.headers = []
    resp = await client.post(f"/api/v9/guilds/{guild['id']}/stickers", headers={"Authorization": user["token"]}, files={
        "file_": image
    })
    assert resp.status_code == 400

    image = BytesIO(b"not image"*1024*64)
    assert image is not None
    image.filename = "yep.png"
    image.headers = []
    resp = await client.post(f"/api/v9/guilds/{guild['id']}/stickers", headers={"Authorization": user["token"]}, files={
        "file": image
    }, form={"name": "test", "tags": "test"})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_edit_sticker():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    sticker = await create_sticker(client, user, guild["id"], "yep")

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/stickers/{sticker['id']}",
                              headers={"Authorization": user["token"]},
                              json={'name': 'yep_test', 'tags': 'slight_smile', 'description': 'test description'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "yep_test"
    assert json["tags"] == "slight_smile"
    assert json["description"] == "test description"

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/stickers/{Snowflake.makeId()}", json={'name': 'yep_tes1'},
                              headers={"Authorization": user["token"]})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_delete_sticker():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    sticker = await create_sticker(client, user, guild["id"], "yep")

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/stickers/{sticker['id']}",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 204

    # Check if sticker deleted
    resp = await client.get(f"/api/v9/guilds/{guild['id']}/stickers", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert await resp.get_json() == []

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/stickers/{Snowflake.makeId()}",
                               headers={"Authorization": user["token"]})
    assert resp.status_code == 404
