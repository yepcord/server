"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from asyncio import get_event_loop
from io import BytesIO

import pytest as pt
import pytest_asyncio
from PIL import Image

from src.cdn.main import app
from src.yepcord.config import Config
from src.yepcord.core import Core
from src.yepcord.enums import StickerFormat, StickerType, ChannelType
from src.yepcord.models import User, Sticker, Emoji, Channel, Message, Attachment
from src.yepcord.snowflake import Snowflake
from src.yepcord.storage import getStorage, _Storage
from src.yepcord.utils import getImage, b64decode
from .ftp_server import ftp_server
from .local_server import local_server
from .s3_server import s3_server
from ..yep_image import YEP_IMAGE

TestClientType = app.test_client_class
core = Core(b64decode(Config.KEY))


STORAGE_SERVERS = {
    "s3": s3_server,
    "ftp": ftp_server,
}


@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def process_test():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
        yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.fixture(params=["local", "s3", "ftp"], name="storage")
def _storage(request) -> _Storage:
    Config.STORAGE["type"] = request.param
    storage_server = STORAGE_SERVERS.get(Config.STORAGE["type"], local_server)
    with storage_server().run_in_thread():
        yield getStorage()


@pt.mark.asyncio
async def test_avatar(storage: _Storage):
    client: TestClientType = app.test_client()
    user_id = Snowflake.makeId()

    avatar_hash = await storage.setAvatarFromBytesIO(user_id, getImage(YEP_IMAGE))
    assert avatar_hash is not None and len(avatar_hash) == 32

    response = await client.get(f"/avatars/{user_id}/{avatar_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/avatars/{user_id}/{avatar_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/avatars/{Snowflake.makeId()}/{avatar_hash}.webp?size=240")
    assert response.status_code == 404

    img = BytesIO()
    Image.open(getImage(YEP_IMAGE)).convert("RGB").save(img, format="JPEG")

    avatar_hash = await storage.setAvatarFromBytesIO(user_id, img)
    assert avatar_hash is not None and len(avatar_hash) == 32


@pt.mark.asyncio
async def test_banner(storage: _Storage):
    client: TestClientType = app.test_client()
    user_id = Snowflake.makeId()

    banner_hash = await storage.setBannerFromBytesIO(user_id, getImage(YEP_IMAGE))
    assert banner_hash is not None and len(banner_hash) == 32

    response = await client.get(f"/banners/{user_id}/{banner_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/banners/{user_id}/{banner_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/banners/{Snowflake.makeId()}/{banner_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_guild_splash(storage: _Storage):
    client: TestClientType = app.test_client()
    guild_id = Snowflake.makeId()

    splash_hash = await storage.setGuildSplashFromBytesIO(guild_id, getImage(YEP_IMAGE))
    assert splash_hash is not None and len(splash_hash) == 32

    response = await client.get(f"/splashes/{guild_id}/{splash_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/splashes/{guild_id}/{splash_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/splashes/{Snowflake.makeId()}/{splash_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_channel_icon(storage: _Storage):
    client: TestClientType = app.test_client()
    channel_id = Snowflake.makeId()

    channel_icon_hash = await storage.setChannelIconFromBytesIO(channel_id, getImage(YEP_IMAGE))
    assert channel_icon_hash is not None and len(channel_icon_hash) == 32

    response = await client.get(f"/channel-icons/{channel_id}/{channel_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/channel-icons/{channel_id}/{channel_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/channel-icons/{Snowflake.makeId()}/{channel_icon_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_guild_icon(storage: _Storage):
    client: TestClientType = app.test_client()
    guild_id = Snowflake.makeId()

    guild_icon_hash = await storage.setGuildIconFromBytesIO(guild_id, getImage(YEP_IMAGE))
    assert guild_icon_hash is not None and len(guild_icon_hash) == 32

    response = await client.get(f"/icons/{guild_id}/{guild_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/icons/{guild_id}/{guild_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/icons/{Snowflake.makeId()}/{guild_icon_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_guild_avatar(storage: _Storage):
    client: TestClientType = app.test_client()
    user_id = Snowflake.makeId()
    guild_id = Snowflake.makeId()

    avatar_hash = await storage.setGuildAvatarFromBytesIO(user_id, guild_id, getImage(YEP_IMAGE))
    assert avatar_hash is not None and len(avatar_hash) == 32

    response = await client.get(f"/guilds/{guild_id}/users/{user_id}/avatars/{avatar_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/guilds/{guild_id}/users/{user_id}/avatars/{avatar_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/guilds/{guild_id}/users/{Snowflake.makeId()}/avatars/{avatar_hash}.webp?size=240")
    assert response.status_code == 404
    response = await client.get(f"/guilds/{Snowflake.makeId()}/users/{user_id}/avatars/{avatar_hash}.webp?size=240")
    assert response.status_code == 404
    response = await client.get(f"/guilds/{Snowflake.makeId()}/users/{Snowflake.makeId()}/avatars/{avatar_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_sticker(storage: _Storage):
    client: TestClientType = app.test_client()

    user = await User.objects.create(id=Snowflake.makeId(), email=f"test_{Snowflake.makeId()}@yepcord.ml", password="")
    guild = await core.createGuild(Snowflake.makeId(), user, "test")
    sticker = await Sticker.objects.create(id=Snowflake.makeId(), guild=guild, name="test", user=user,
                                           type=StickerType.GUILD, format=StickerFormat.PNG)
    sticker_hash = await storage.setStickerFromBytesIO(sticker.id, getImage(YEP_IMAGE))
    assert sticker_hash == "sticker"

    response = await client.get(f"/stickers/{sticker.id}.idk?size=240")
    assert response.status_code == 400

    async def _checkStickerSuccess():
        response = await client.get(f"/stickers/{sticker.id}.webp?size=240")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp"
        img = Image.open(BytesIO(await response.data))
        assert img.size[0] == 240

    await _checkStickerSuccess()
    await sticker.delete()
    await _checkStickerSuccess()

    response = await client.get(f"/stickers/{Snowflake.makeId()}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_event_image(storage: _Storage):
    client: TestClientType = app.test_client()
    event_id = Snowflake.makeId()

    event_hash = await storage.setGuildEventFromBytesIO(event_id, getImage(YEP_IMAGE))
    assert event_hash is not None and len(event_hash) == 32

    response = await client.get(f"/guild-events/{event_id}/{event_hash}?size=241")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/guild-events/{Snowflake.makeId()}/{event_hash}?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_emoji(storage: _Storage):
    client: TestClientType = app.test_client()

    user = await User.objects.create(id=Snowflake.makeId(), email=f"test_{Snowflake.makeId()}@yepcord.ml", password="")
    guild = await core.createGuild(Snowflake.makeId(), user, "test")
    emoji = await Emoji.objects.create(id=Snowflake.makeId(), name="test", user=user, guild=guild)
    emoji_info = await storage.setEmojiFromBytesIO(emoji.id, getImage(YEP_IMAGE))
    assert not emoji_info["animated"]

    response = await client.get(f"/emojis/{emoji.id}.idk?size=240")
    assert response.status_code == 400

    async def _checkEmojiSuccess():
        response = await client.get(f"/emojis/{emoji.id}.webp?size=240")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp"
        img = Image.open(BytesIO(await response.data))
        assert img.size[0] == 56

    await _checkEmojiSuccess()
    await emoji.delete()
    await _checkEmojiSuccess()

    response = await client.get(f"/emojis/{Snowflake.makeId()}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_role_icon(storage: _Storage):
    client: TestClientType = app.test_client()
    role_id = Snowflake.makeId()

    role_icon_hash = await storage.setRoleIconFromBytesIO(role_id, getImage(YEP_IMAGE))
    assert role_icon_hash is not None and len(role_icon_hash) == 32

    response = await client.get(f"/role-icons/{role_id}/{role_icon_hash}.idk?size=240")
    assert response.status_code == 400

    response = await client.get(f"/role-icons/{role_id}/{role_icon_hash}.webp?size=240")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/webp"
    img = Image.open(BytesIO(await response.data))
    assert img.size[0] == 240

    response = await client.get(f"/role-icons/{Snowflake.makeId()}/{role_icon_hash}.webp?size=240")
    assert response.status_code == 404


@pt.mark.asyncio
async def test_attachment(storage: _Storage):
    client: TestClientType = app.test_client()

    file = getImage(YEP_IMAGE)
    file_size = file.getbuffer().nbytes
    user = await User.objects.create(id=Snowflake.makeId(), email=f"test_{Snowflake.makeId()}@yepcord.ml", password="")
    channel = await Channel.objects.create(id=Snowflake.makeId(), type=ChannelType.GROUP_DM)
    await channel.recipients.add(user)
    message = await Message.objects.create(id=Snowflake.makeId(), channel=channel, author=user)
    attachment = await Attachment.objects.create(id=Snowflake.makeId(), channel=channel, message=message,
                                                 filename="YEP.png", size=file_size, content_type="image/png")
    bytes_written = await storage.uploadAttachment(file.getvalue(), attachment)
    assert bytes_written == file_size

    response = await client.get(f"/attachments/{channel.id}/{attachment.id}/YEP.png")
    assert response.status_code == 200
    assert await response.data == getImage(YEP_IMAGE).getvalue()

    response = await client.get(f"/attachments/{channel.id}/{attachment.id}/YEP1.png")
    assert response.status_code == 404
    response = await client.get(f"/attachments/{channel.id}/{Snowflake.makeId()}/YEP.png")
    assert response.status_code == 404
    response = await client.get(f"/attachments/{Snowflake.makeId()}/{attachment.id}/YEP.png")
    assert response.status_code == 404
