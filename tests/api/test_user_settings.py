from asyncio import get_event_loop
from base64 import b64encode

import pytest as pt
import pytest_asyncio
from google.protobuf.wrappers_pb2 import StringValue

from src.rest_api.main import app
from src.yepcord.proto import PreloadedUserSettings, TextAndImagesSettings, FrecencyUserSettings, FavoriteStickers
from .utils import create_users, TestClientType


@pt.fixture()
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_settings():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    assert (await client.get("/api/v9/users/@me/connections", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/consent", headers=headers)).status_code == 200
    assert (await client.post("/api/v9/users/@me/consent", headers=headers,
                              json={"grant": ["personalization"], "revoke": ["usage_statistics"]}
                              )).status_code == 200
    assert (await client.patch("/api/v9/users/@me/settings", headers=headers,
                               json={"afk_timeout": 300})).status_code == 200


@pt.mark.asyncio
async def test_settings_proto():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    assert (await client.get("/api/v9/users/@me/settings-proto/1", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/2", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/3", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/4", headers=headers)).status_code == 400

    proto = PreloadedUserSettings(text_and_images=TextAndImagesSettings(render_spoilers=StringValue(value="ALWAYS")))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                               json={"settings": proto})).status_code == 200
    assert (await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                               json={"settings": ""})).status_code == 400
    assert (await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                               json={"settings": "1"})).status_code == 400

    proto = FrecencyUserSettings(favorite_stickers=FavoriteStickers(sticker_ids=[1, 2, 3]))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                               json={"settings": proto})).status_code == 200
    assert (await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                               json={"settings": ""})).status_code == 400
    assert (await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                               json={"settings": "1"})).status_code == 400
