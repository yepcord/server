from asyncio import get_event_loop
from io import BytesIO
from typing import Coroutine, Any

import pytest as pt
from PIL import Image

from src.cdn.main import app
from src.yepcord.classes.message import Attachment
from src.yepcord.config import Config
from src.yepcord.core import Core
from src.yepcord.snowflake import Snowflake
from src.yepcord.storage import getStorage
from src.yepcord.utils import getImage, b64decode
from tests.yep_image import YEP_IMAGE

TestClientType = app.test_client_class
storage = getStorage()
core = Core(b64decode(Config("KEY")))

class TestVars:
    USER_ID = Snowflake.makeId()
    CHANNEL_ID = Snowflake.makeId()
    GUILD_ID = Snowflake.makeId()
    STICKER_ID = Snowflake.makeId()
    EMOJI_ID = Snowflake.makeId()
    EVENT_ID = Snowflake.makeId()
    ROLE_ID = Snowflake.makeId()
    ATTACHMENT_ID = Snowflake.makeId()
    _vars = {}

    @staticmethod
    def get(item, default=None):
        return TestVars._vars.get(item, default)

    @staticmethod
    def set(item, value):
        TestVars._vars[item] = value

@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()

@pt.fixture(name='testApp')
async def _test_app():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    return app

@pt.fixture(name='testCore')
async def _setup_db():
    await core.initDB(
        host=Config("DB_HOST"),
        port=3306,
        user=Config("DB_USER"),
        password=Config("DB_PASS"),
        db=Config("DB_NAME"),
        autocommit=True
    )
    await core.initMCL()
    return core

@pt.mark.asyncio
async def test_set_avatar():
    avatar_hash = await storage.setAvatarFromBytesIO(TestVars.USER_ID, getImage(YEP_IMAGE))
    assert avatar_hash is not None and len(avatar_hash) == 32
    TestVars.set("avatar_hash", avatar_hash)

@pt.mark.asyncio
async def test_get_avatar(testApp):
    client: TestClientType = (await testApp).test_client()
    avatar_hash = TestVars.get("avatar_hash")

    response = await client.get(f"/avatars/{TestVars.USER_ID}/{avatar_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/avatars/{TestVars.USER_ID}/{avatar_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/avatars/{Snowflake.makeId()}/{avatar_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_banner():
    banner_hash = await storage.setBannerFromBytesIO(TestVars.USER_ID, getImage(YEP_IMAGE))
    assert banner_hash is not None and len(banner_hash) == 32
    TestVars.set("banner_hash", banner_hash)

@pt.mark.asyncio
async def test_get_banner(testApp):
    client: TestClientType = (await testApp).test_client()
    banner_hash = TestVars.get("banner_hash")

    response = await client.get(f"/banners/{TestVars.USER_ID}/{banner_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/banners/{TestVars.USER_ID}/{banner_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/banners/{Snowflake.makeId()}/{banner_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_guild_splash():
    banner_hash = await storage.setGuildSplashFromBytesIO(TestVars.GUILD_ID, getImage(YEP_IMAGE))
    assert banner_hash is not None and len(banner_hash) == 32
    TestVars.set("gsplash_hash", banner_hash)

@pt.mark.asyncio
async def test_get_guild_splash(testApp):
    client: TestClientType = (await testApp).test_client()
    gsplash_hash = TestVars.get("banner_hash")

    response = await client.get(f"/splashes/{TestVars.GUILD_ID}/{gsplash_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/splashes/{TestVars.GUILD_ID}/{gsplash_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/splashes/{Snowflake.makeId()}/{gsplash_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_channel_icon():
    channel_icon_hash = await storage.setChannelIconFromBytesIO(TestVars.CHANNEL_ID, getImage(YEP_IMAGE))
    assert channel_icon_hash is not None and len(channel_icon_hash) == 32
    TestVars.set("channel_icon_hash", channel_icon_hash)

@pt.mark.asyncio
async def test_get_channel_icon(testApp):
    client: TestClientType = (await testApp).test_client()
    channel_icon_hash = TestVars.get("channel_icon_hash")

    response = await client.get(f"/channel-icons/{TestVars.CHANNEL_ID}/{channel_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/channel-icons/{TestVars.CHANNEL_ID}/{channel_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/channel-icons/{Snowflake.makeId()}/{channel_icon_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_guild_icon():
    guild_icon_hash = await storage.setGuildIconFromBytesIO(TestVars.GUILD_ID, getImage(YEP_IMAGE))
    assert guild_icon_hash is not None and len(guild_icon_hash) == 32
    TestVars.set("guild_icon_hash", guild_icon_hash)

@pt.mark.asyncio
async def test_get_guild_icon(testApp):
    client: TestClientType = (await testApp).test_client()
    guild_icon_hash = TestVars.get("guild_icon_hash")

    response = await client.get(f"/icons/{TestVars.GUILD_ID}/{guild_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/icons/{TestVars.GUILD_ID}/{guild_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/icons/{Snowflake.makeId()}/{guild_icon_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_guild_avatar():
    gavatar_hash = await storage.setGuildAvatarFromBytesIO(TestVars.USER_ID, TestVars.GUILD_ID, getImage(YEP_IMAGE))
    assert gavatar_hash is not None and len(gavatar_hash) == 32
    TestVars.set("gavatar_hash", gavatar_hash)

@pt.mark.asyncio
async def test_get_guild_avatar(testApp):
    client: TestClientType = (await testApp).test_client()
    gavatar_hash = TestVars.get("gavatar_hash")

    response = await client.get(f"/guilds/{TestVars.GUILD_ID}/users/{TestVars.USER_ID}/avatars/{gavatar_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/guilds/{TestVars.GUILD_ID}/users/{TestVars.USER_ID}/avatars/{gavatar_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/guilds/{TestVars.GUILD_ID}/users/{Snowflake.makeId()}/avatars/{gavatar_hash}.webp?size=240")
    assert response.status_code == 404
    response = await client.get(f"/guilds/{Snowflake.makeId()}/users/{TestVars.USER_ID}/avatars/{gavatar_hash}.webp?size=240")
    assert response.status_code == 404
    response = await client.get(f"/guilds/{Snowflake.makeId()}/users/{Snowflake.makeId()}/avatars/{gavatar_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_sticker():
    sticker_hash = await storage.setStickerFromBytesIO(TestVars.STICKER_ID, getImage(YEP_IMAGE))
    assert sticker_hash == "sticker"

@pt.mark.asyncio
async def test_get_sticker(testApp):
    client: TestClientType = (await testApp).test_client()

    response = await client.get(f"/stickers/{TestVars.STICKER_ID}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/stickers/{TestVars.STICKER_ID}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/stickers/{Snowflake.makeId()}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_event_image():
    event_hash = await storage.setGuildEventFromBytesIO(TestVars.EVENT_ID, getImage(YEP_IMAGE))
    assert event_hash is not None and len(event_hash) == 32
    TestVars.set("event_hash", event_hash)

@pt.mark.asyncio
async def test_get_event_image(testApp):
    client: TestClientType = (await testApp).test_client()
    event_hash = TestVars.get("event_hash")

    response = await client.get(f"/guild-events/{TestVars.EVENT_ID}/{event_hash}?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/guild-events/{Snowflake.makeId()}/{event_hash}?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_emoji():
    emoji_info = await storage.setEmojiFromBytesIO(TestVars.EMOJI_ID, getImage(YEP_IMAGE))
    assert not emoji_info["animated"]

@pt.mark.asyncio
async def test_get_emoji(testApp):
    client: TestClientType = (await testApp).test_client()

    response = await client.get(f"/emojis/{TestVars.EMOJI_ID}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/emojis/{TestVars.EMOJI_ID}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 56

    response = await client.get(f"/emojis/{Snowflake.makeId()}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_set_role_icon():
    role_icon_hash = await storage.setRoleIconFromBytesIO(TestVars.ROLE_ID, getImage(YEP_IMAGE))
    assert role_icon_hash is not None and len(role_icon_hash) == 32
    TestVars.set("role_icon_hash", role_icon_hash)

@pt.mark.asyncio
async def test_get_role_icon(testApp):
    client: TestClientType = (await testApp).test_client()
    role_icon_hash = TestVars.get("role_icon_hash")

    response = await client.get(f"/role-icons/{TestVars.ROLE_ID}/{role_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/role-icons/{TestVars.ROLE_ID}/{role_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/role-icons/{Snowflake.makeId()}/{role_icon_hash}.webp?size=240")
    assert response.status_code == 404

@pt.mark.asyncio
async def test_upload_attachment(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    file = getImage(YEP_IMAGE)
    file_size = file.getbuffer().nbytes
    attachment = Attachment(TestVars.ATTACHMENT_ID, TestVars.CHANNEL_ID, Snowflake.makeId(), "YEP.png", file_size, {},
                            content_type="image/png", uploaded=True)
    await testCore.putAttachment(attachment)
    bytes_written = await storage.uploadAttachment(file.getvalue(), attachment)
    assert bytes_written == file_size

@pt.mark.asyncio
async def test_get_attachment(testApp):
    client: TestClientType = (await testApp).test_client()

    response = await client.get(f"/attachments/{TestVars.CHANNEL_ID}/{TestVars.ATTACHMENT_ID}/YEP.png")
    assert response.status_code == 200
    assert await response.data == getImage(YEP_IMAGE).getvalue()

    response = await client.get(f"/attachments/{TestVars.CHANNEL_ID}/{TestVars.ATTACHMENT_ID}/YEP1.png")
    assert response.status_code == 404
    response = await client.get(f"/attachments/{TestVars.CHANNEL_ID}/{Snowflake.makeId()}/YEP.png")
    assert response.status_code == 404
    response = await client.get(f"/attachments/{Snowflake.makeId()}/{TestVars.ATTACHMENT_ID}/YEP.png")
    assert response.status_code == 404
