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
from base64 import b64encode

import pytest as pt
import pytest_asyncio
from google.protobuf.wrappers_pb2 import StringValue

from src.rest_api.main import app
from src.yepcord.classes.other import MFA
from src.yepcord.config import Config
from src.yepcord.enums import ChannelType, StickerType
from src.yepcord.proto import PreloadedUserSettings, TextAndImagesSettings, FrecencyUserSettings, FavoriteStickers
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage, b64decode
from tests.utils import generateEmailVerificationToken, generateMfaVerificationKey
from tests.yep_image import YEP_IMAGE

TestClientType = app.test_client_class


class TestVars:
    EMAIL_ID = Snowflake.makeId()
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


@pt.fixture(name='testapp')
async def _test_app():
    return app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_login_fail(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": f"{TestVars.EMAIL_ID}_test@yepcord.ml",
                                                             "password": "test_passw0rd"})
    assert response.status_code == 400


@pt.mark.asyncio
async def test_register(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{TestVars.EMAIL_ID}",
        "email": f"{TestVars.EMAIL_ID}_test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])


@pt.mark.asyncio
async def test_resend_verification_email(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/verify/resend', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204


@pt.mark.asyncio
async def test_getme_success(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200


@pt.mark.asyncio
async def test_logout(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/logout', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204


@pt.mark.asyncio
async def test_getme_fail(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 401


@pt.mark.asyncio
async def test_login_success(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": f"{TestVars.EMAIL_ID}_test@yepcord.ml",
                                                             "password": "test_passw0rd"})
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])


@pt.mark.asyncio
async def test_change_username(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.patch("/api/v9/users/@me",
                                  json={"username": f"YepCordTest_{TestVars.EMAIL_ID}", "password": "test_passw0rd"},
                                  headers={"Authorization": TestVars.get("token")})
    assert response.status_code == 200
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200
    j = await response.get_json()
    TestVars.set("data", await response.get_json())
    assert j["username"] == f"YepCordTest_{TestVars.EMAIL_ID}"


@pt.mark.asyncio
async def test_settings(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client: TestClientType = (await testapp).test_client()
    assert (await client.get("/api/v9/users/@me/connections", headers=headers)).status_code == 200
    assert (r := await client.get("/api/v9/users/@me/settings", headers=headers)).status_code == 200
    assert (r := await client.get("/api/v9/users/@me/consent", headers=headers)).status_code == 200
    assert (r := await client.post("/api/v9/users/@me/consent", headers=headers,
                                   json={"grant": ["personalization"],
                                         "revoke": ["usage_statistics"]})).status_code == 200
    assert (r := await client.patch("/api/v9/users/@me/settings", headers=headers,
                                    json={"afk_timeout": 300})).status_code == 200


@pt.mark.asyncio
async def test_settings_proto(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client: TestClientType = (await testapp).test_client()
    assert (r := await client.get("/api/v9/users/@me/settings-proto/1", headers=headers)).status_code == 200
    assert (r := await client.get("/api/v9/users/@me/settings-proto/2", headers=headers)).status_code == 200
    assert (r := await client.get("/api/v9/users/@me/settings-proto/3", headers=headers)).status_code == 200
    assert (r := await client.get("/api/v9/users/@me/settings-proto/4", headers=headers)).status_code == 400

    proto = PreloadedUserSettings(text_and_images=TextAndImagesSettings(render_spoilers=StringValue(value="ALWAYS")))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                                    json={"settings": proto})).status_code == 200
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                                    json={"settings": ""})).status_code == 400
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/1", headers=headers,
                                    json={"settings": "1"})).status_code == 400

    proto = FrecencyUserSettings(favorite_stickers=FavoriteStickers(sticker_ids=[1, 2, 3]))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                                    json={"settings": proto})).status_code == 200
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                                    json={"settings": ""})).status_code == 400
    assert (r := await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers,
                                    json={"settings": "1"})).status_code == 400


@pt.mark.asyncio
async def test_register_other_user(testapp):
    client: TestClientType = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": f"TestUser_{TestVars.EMAIL_ID}",
        "email": f"{TestVars.EMAIL_ID}_user@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token_u2", j["token"])
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": j["token"]
    })
    assert response.status_code == 200
    TestVars.set("data_u2", await response.get_json())


@pt.mark.asyncio
async def test_relationships(testapp):
    headers = {"Authorization": TestVars.get("token")}
    headers_u2 = {"Authorization": TestVars.get("token_u2")}
    data = TestVars.get("data")
    data2 = TestVars.get("data_u2")
    client: TestClientType = (await testapp).test_client()

    response = await client.post('/api/v9/users/@me/relationships', headers=headers,
                                 json={"username": data["username"], "discriminator": data["discriminator"]})
    assert response.status_code == 400
    response = await client.post('/api/v9/users/@me/relationships', headers=headers,
                                 json={"username": data["username"],
                                       "discriminator": str((int(data["discriminator"]) + 1) % 10000)})
    assert response.status_code == 400

    response = await client.get('/api/v9/users/@me/relationships', headers=headers)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.get('/api/v9/users/@me/relationships', headers=headers_u2)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.post('/api/v9/users/@me/relationships', headers=headers,
                                 json={"username": data2["username"], "discriminator": data2["discriminator"]})
    assert response.status_code == 204
    response = await client.put(f"/api/v9/users/@me/relationships/{data['id']}", headers=headers, json={})
    assert response.status_code == 204

    response = await client.get('/api/v9/users/@me/relationships', headers=headers)
    assert response.status_code == 200
    assert len(await response.get_json()) == 1
    response = await client.get('/api/v9/users/@me/relationships', headers=headers_u2)
    assert response.status_code == 200
    assert len(await response.get_json()) == 1

    response = await client.get(f"/api/v9/users/{data2['id']}/profile", headers=headers)
    assert response.status_code == 200


@pt.mark.asyncio
async def test_create_guild(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.post("/api/v9/guilds", headers=headers, json={'name': 'Test Guild', 'icon': None})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == 'Test Guild'
    assert json["icon"] is None
    assert json["description"] is None
    assert json["splash"] is None
    assert json["discovery_splash"] is None
    assert json["emojis"] == []
    TestVars.set("guild_id", int(json["id"]))
    TestVars.set("guild_channels", json["channels"])


@pt.mark.asyncio
async def test_get_messages_in_empty_channel(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"].lower() == "general"][0][
        "id"]
    resp = await client.get(f"/api/v9/channels/{channel_id}/messages", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_get_subscriptions(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    data = TestVars.get("data")
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/premium/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == [{'ended': False, 'user_id': data["id"]}] * 30)


@pt.mark.asyncio
async def test_guild_templates_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/templates", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_guild_channels(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    parent_id = \
        [channel for channel in TestVars.get("guild_channels") if channel["type"] == ChannelType.GUILD_CATEGORY][0][
            "id"]

    # Create text channel
    resp = await client.post(f"/api/v9/guilds/{guild_id}/channels", headers=headers,
                             json={'type': 0, 'name': 'test_text_channel', 'parent_id': parent_id})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 0
    assert json["name"] == "test_text_channel"
    assert json["parent_id"] == parent_id
    assert json["guild_id"] == str(guild_id)
    TestVars.set("test_channel_id", json["id"])
    TestVars.get("guild_channels").append(json)

    # Create voice channel
    resp = await client.post(f"/api/v9/guilds/{guild_id}/channels", headers=headers,
                             json={'type': 2, 'name': 'test_voice_channel', 'parent_id': parent_id})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["name"] == "test_voice_channel"
    assert json["parent_id"] == parent_id
    assert json["guild_id"] == str(guild_id)

    TestVars.get("guild_channels").append(json)


@pt.mark.asyncio
async def test_change_guild_channels_positions(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    channel_id = \
        [channel for channel in TestVars.get("guild_channels") if channel["type"] == ChannelType.GUILD_CATEGORY][0][
            "id"]
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/channels", headers=headers,
                              json=[{'id': channel_id, 'position': 1}])
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_edit_guild(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}", headers=headers, json={
        'name': 'Test Guild Renamed', 'afk_channel_id': None, 'afk_timeout': 900,
        'system_channel_id': TestVars.get("test_channel_id"), 'verification_level': 0, 'icon': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "Test Guild Renamed"
    assert json["afk_channel_id"] is None
    assert json["afk_timeout"] == 900
    # assert json["system_channel_id"] == TestVars.get("test_channel_id")
    assert len(json["icon"]) == 32


@pt.mark.asyncio
async def test_create_role(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.post(f"/api/v9/guilds/{guild_id}/roles", headers=headers, json={'name': 'new role'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "new role"
    TestVars.set("role_id", json["id"])


@pt.mark.asyncio
async def test_change_roles_positions(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    role_id = TestVars.get("role_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/roles", headers=headers,
                              json=[{'id': role_id, 'position': 1}])
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json[0]["id"] == str(guild_id)
    assert json[1]["id"] == role_id


@pt.mark.asyncio
async def test_edit_role(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    role_id = TestVars.get("role_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/roles/{role_id}", headers=headers, json={
        'name': 'test role', 'permissions': '268436496', 'color': 15277667, 'icon': YEP_IMAGE, 'unicode_emoji': None})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test role"
    assert json["permissions"] == "268436496"
    assert json["color"] == 15277667
    assert len(json["icon"]) == 32


@pt.mark.asyncio
async def test_delete_role(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    role_id = TestVars.get("role_id")
    resp = await client.delete(f"/api/v9/guilds/{guild_id}/roles/{role_id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/roles/{role_id}", headers=headers, json={})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_get_roles_member_counts(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/roles/member-counts", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == {str(guild_id): 0})


@pt.mark.asyncio
async def test_get_emojis_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/emojis", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_emoji(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.post(f"/api/v9/guilds/{guild_id}/emojis", headers=headers,
                             json={'image': YEP_IMAGE, 'name': 'YEP'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP"
    assert not json["animated"]
    assert json["available"]
    TestVars.set("emoji_id", json["id"])


@pt.mark.asyncio
async def test_get_emojis(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    emoji_id = TestVars.get("emoji_id")
    data = TestVars.get("data")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/emojis", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == emoji_id
    assert json[0]["name"] == "YEP"
    assert not json[0]["animated"]
    assert json[0]["available"]
    assert json[0]["user"]["id"] == data["id"]


@pt.mark.asyncio
async def test_edit_emoji_name(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    emoji_id = TestVars.get("emoji_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/emojis/{emoji_id}", headers=headers,
                              json={'name': 'YEP_test'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP_test"
    assert not json["animated"]
    assert json["available"]


@pt.mark.asyncio
async def test_emoji_delete(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    emoji_id = TestVars.get("emoji_id")
    resp = await client.delete(f"/api/v9/guilds/{guild_id}/emojis/{emoji_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/guilds/{guild_id}/emojis", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_edit_channel(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    channel = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_voice_channel"][0]
    channel_id = channel["id"]
    resp = await client.patch(f"/api/v9/channels/{channel_id}", headers=headers,
                              json={'bitrate': 384000, 'user_limit': 69})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["id"] == channel_id
    assert json["guild_id"] == str(guild_id)
    assert json["user_limit"] == 69
    assert json["bitrate"] == 384000


@pt.mark.asyncio
async def test_delete_channel(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    channel = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_voice_channel"][0]
    channel_id = channel["id"]
    resp = await client.delete(f"/api/v9/channels/{channel_id}", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["id"] == channel_id
    assert json["guild_id"] == str(guild_id)
    assert json["name"] == "test_voice_channel"
    TestVars.get("guild_channels").remove(channel)


@pt.mark.asyncio
async def test_set_channel_permissions(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    user_id = TestVars.get("data")["id"]

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user_id}", headers=headers,
                            json={'id': user_id, 'type': 1, 'allow': '0', 'deny': '0'})
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{user_id}", headers=headers,
                            json={'id': '160071946643243008', 'type': 1, 'allow': '1024', 'deny': '0'})
    assert resp.status_code == 204

    resp = await client.put(f"/api/v9/channels/{channel_id}/permissions/{guild_id}", headers=headers,
                            json={'id': guild_id, 'type': 0, 'allow': '0', 'deny': '1049600'})
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_delete_channel_permission_overwrite(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]

    resp = await client.delete(f"/api/v9/channels/{channel_id}/permissions/{guild_id}", headers=headers)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_get_stickers_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/stickers", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_sticker(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token"), "Content-Length": "1"}
    guild_id = str(TestVars.get("guild_id"))
    user_id = TestVars.get("data")["id"]
    image = getImage(YEP_IMAGE)
    assert image is not None
    image.filename = "yep.png"
    image.headers = []  # [("Content-Disposition", "form-data; name=\"file\"; filename=\"yep.png\""), ("Content-Type", "image/png")]
    resp = await client.post(f"/api/v9/guilds/{guild_id}/stickers", headers=headers, files={
        "file": image
    }, form={
        "name": "yep",
        "tags": "slight_smile"
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "yep"
    assert json["tags"] == "slight_smile"
    assert json["type"] == StickerType.GUILD
    assert json["guild_id"] == guild_id
    assert json["available"]
    assert json["user"]["id"] == user_id
    TestVars.set("sticker_id", json["id"])


@pt.mark.asyncio
async def test_edit_sticker(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    sticker_id = TestVars.get("sticker_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/stickers/{sticker_id}", headers=headers,
                              json={'name': 'yep_test', 'tags': 'slight_smile', 'description': 'test description'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "yep_test"
    assert json["tags"] == "slight_smile"
    assert json["description"] == "test description"


@pt.mark.asyncio
async def test_delete_sticker(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    sticker_id = TestVars.get("sticker_id")
    resp = await client.delete(f"/api/v9/guilds/{guild_id}/stickers/{sticker_id}", headers=headers)
    assert resp.status_code == 204

    # Check if sticker deleted
    resp = await client.get(f"/api/v9/guilds/{guild_id}/stickers", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_webhooks_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/webhooks", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_create_webhook(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"].lower() == "general"
                  and channel["type"] == 0][0]["id"]
    user_id = TestVars.get("data")["id"]
    resp = await client.post(f"/api/v9/channels/{channel_id}/webhooks", headers=headers, json={'name': 'Captain Hook'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "Captain Hook"
    assert json["avatar"] is None
    assert json["guild_id"] == guild_id
    assert json["user"]["id"] == user_id
    TestVars.set("webhook_id", json["id"])
    TestVars.set("webhook_token", json["token"])
    TestVars.set("webhook_channel_id", json["channel_id"])


@pt.mark.asyncio
async def test_get_channel_webhooks(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = TestVars.get("webhook_channel_id")
    webhook_id = TestVars.get("webhook_id")
    resp = await client.get(f"/api/v9/channels/{channel_id}/webhooks", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["id"] == webhook_id
    assert json[0]["guild_id"] == guild_id


@pt.mark.asyncio
async def test_edit_webhook(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    webhook_id = TestVars.get("webhook_id")
    resp = await client.patch(f"/api/v9/webhooks/{webhook_id}", headers=headers,
                              json={'channel_id': channel_id, 'name': 'Test webhook', "avatar": YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel_id
    assert json["name"] == "Test webhook"
    assert json["guild_id"] == guild_id
    assert len(json["avatar"]) == 32


@pt.mark.asyncio
async def test_get_webhook(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    webhook_id = TestVars.get("webhook_id")
    resp = await client.get(f"/api/v9/webhooks/{webhook_id}", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel_id
    assert json["name"] == "Test webhook"
    assert json["guild_id"] == guild_id
    assert len(json["avatar"]) == 32


@pt.mark.asyncio
async def test_post_webhook_message(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    webhook_id = TestVars.get("webhook_id")
    guild_id = str(TestVars.get("guild_id"))
    webhook_token = TestVars.get("webhook_token")
    resp = await client.post(f"/api/webhooks/{webhook_id}/{webhook_token}", headers=headers,
                             json={'content': 'test message sent from webhook'})
    assert resp.status_code == 204

    resp = await client.post(f"/api/webhooks/{webhook_id}/{webhook_token}?wait=true", headers=headers,
                             json={'content': 'test message sent from webhook 2'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["author"]["bot"]
    assert json["author"]["id"] == webhook_id
    assert json["author"]["discriminator"] == "0000"
    assert json["content"] == "test message sent from webhook 2"
    assert json["type"] == 0
    assert json["guild_id"] == guild_id


@pt.mark.asyncio
async def test_delete_webhook(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    webhook_id = TestVars.get("webhook_id")
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.delete(f"/api/v9/webhooks/{webhook_id}")
    assert resp.status_code == 403
    resp = await client.delete(f"/api/v9/webhooks/{webhook_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/guilds/{guild_id}/webhooks", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_get_guild_message(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    resp = await client.get(f"/api/v9/channels/{channel_id}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) >= 2


@pt.mark.asyncio
async def test_send_guild_message(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    guild_id = str(TestVars.get("guild_id"))
    user_id = TestVars.get("data")["id"]
    resp = await client.post(f"/api/v9/channels/{channel_id}/typing", headers=headers)
    assert resp.status_code == 204

    nonce = str(Snowflake.makeId())
    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers,
                             json={"content": "test message", 'nonce': nonce})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["author"]["id"] == user_id
    assert json["content"] == "test message"
    assert json["type"] == 0
    assert json["guild_id"] == guild_id
    assert json["nonce"] == nonce

    nonce = str(Snowflake.makeId())
    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers,
                             json={"content": "message with emoji 💀", 'nonce': nonce})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["author"]["id"] == user_id
    assert json["content"] == "message with emoji 💀"
    assert json["type"] == 0
    assert json["guild_id"] == guild_id
    assert json["nonce"] == nonce


@pt.mark.asyncio
async def test_create_guild_template(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    user_id = TestVars.get("data")["id"]
    resp = await client.post(f"/api/v9/guilds/{guild_id}/templates", headers=headers,
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test"
    assert json["description"] == "test template"
    assert json["creator_id"] == user_id
    assert json["creator"]["id"] == user_id
    assert json["source_guild_id"] == guild_id


@pt.mark.asyncio
async def test_get_vanity_url_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/vanity-url", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == {'code': None})


@pt.mark.asyncio
async def test_get_invites_empty(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/invites", headers=headers)
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_create_invite(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    user_id = TestVars.get("data")["id"]
    resp = await client.post(f"/api/v9/channels/{channel_id}/invites", headers=headers,
                             json={'max_age': 604800, 'max_uses': 0})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["inviter"]["id"] == user_id
    assert json["channel"]["id"] == channel_id
    assert json["guild"]["id"] == guild_id
    assert json["max_age"] == 604800
    assert json["max_uses"] == 0
    assert json["uses"] == 0


@pt.mark.asyncio
async def test_get_guild_invites(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    user_id = TestVars.get("data")["id"]
    resp = await client.get(f"/api/v9/guilds/{guild_id}/invites", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["inviter"]["id"] == user_id
    assert json[0]["channel"]["id"] == channel_id
    assert json[0]["guild"]["id"] == guild_id
    assert json[0]["max_age"] == 604800
    assert json[0]["max_uses"] == 0
    assert json[0]["uses"] == 0


@pt.mark.asyncio
async def test_get_channel_invites(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    user_id = TestVars.get("data")["id"]
    resp = await client.get(f"/api/v9/channels/{channel_id}/invites", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["inviter"]["id"] == user_id
    assert json[0]["channel"]["id"] == channel_id
    assert json[0]["guild"]["id"] == guild_id
    assert json[0]["max_age"] == 604800
    assert json[0]["max_uses"] == 0
    assert json[0]["uses"] == 0


@pt.mark.asyncio
async def test_edit_user_data(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}

    resp = await client.patch("/api/v9/users/@me", headers=headers,
                              json={'new_password': 'test_passw0rd_changed', 'password': 'invalid_password'})
    assert resp.status_code == 400

    resp = await client.patch("/api/v9/users/@me", headers=headers,
                              json={'email': f"{TestVars.EMAIL_ID}_test_changed@yepcord.ml", 'discriminator': '9999',
                                    'new_password': 'test_passw0rd_changed', 'password': 'test_passw0rd',
                                    'avatar': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["email"] == f"{TestVars.EMAIL_ID}_test_changed@yepcord.ml"
    assert json["discriminator"] == '9999'
    assert len(json["avatar"]) == 32
    assert not json["verified"]


@pt.mark.asyncio
async def test_verify_email(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {}
    user_id = TestVars.get("data")["id"]

    token = generateEmailVerificationToken(int(user_id), f"{TestVars.EMAIL_ID}_test_changed@yepcord.ml",
                                           b64decode(Config.KEY))

    resp = await client.post("/api/v9/auth/verify", headers=headers, json={"token": ""})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/auth/verify", headers=headers, json={'token': "1"})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/auth/verify", headers=headers, json={'token': token})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    assert json["user_id"] == str(user_id)


@pt.mark.asyncio
async def test_get_my_profile(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    user_id = str(TestVars.get("data")["id"])
    guild_id = str(TestVars.get("guild_id"))

    resp = await client.get(f"/api/v9/users/@me/profile?guild_id=invalid_id", headers=headers)  # Invalid id
    assert resp.status_code == 400

    resp = await client.get(
        f"/api/v9/users/@me/profile?with_mutual_guilds=true&mutual_friends_count=true&guild_id={guild_id}",
        headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["user"]["id"] == user_id
    assert json["guild_member_profile"]["guild_id"] == guild_id
    assert json["guild_member"]["user"]["id"] == user_id


@pt.mark.asyncio
async def test_hypesquad_change_house(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 1})
    assert resp.status_code == 204
    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 2})
    assert resp.status_code == 204
    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 3})
    assert resp.status_code == 204

    resp = await client.post("/api/v9/hypesquad/online", headers=headers, json={'house_id': 4})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_messages_replying_1(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    user_id = str(TestVars.get("data")["id"])
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers,
                             json={'content': ' test ', 'nonce': '1087430130973802496', 'tts': False})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel_id
    assert json["author"]["id"] == user_id
    assert json["content"] == "test"
    assert json["edit_timestamp"] is None
    assert json["embeds"] == []
    assert not json["pinned"]
    assert json["type"] == 0
    assert json["nonce"] == "1087430130973802496"
    assert json["guild_id"] == guild_id
    TestVars.set("message_id", json["id"])


@pt.mark.asyncio
async def test_messages_replying_2(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    user_id = str(TestVars.get("data")["id"])
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    message_id = TestVars.get("message_id")
    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers,
                             json={'content': 'test reply', 'nonce': '1087430157817348096', 'tts': False,
                                   'message_reference': {'message_id': message_id}})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel_id
    assert json["author"]["id"] == user_id
    assert json["content"] == "test reply"
    assert json["message_reference"]["message_id"] == message_id
    assert json["message_reference"]["guild_id"] == guild_id
    assert json["message_reference"]["channel_id"] == channel_id
    assert json["referenced_message"]["id"] == message_id


@pt.mark.asyncio
async def test_message_editing(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    message_id = TestVars.get("message_id")
    resp = await client.patch(f"/api/v9/channels/{channel_id}/messages/{message_id}", headers=headers,
                              json={'content': 'test edited'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["content"] == "test edited"


@pt.mark.asyncio
async def test_message_deleting(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0][
        "id"]
    message_id = TestVars.get("message_id")
    resp = await client.delete(f"/api/v9/channels/{channel_id}/messages/{message_id}", headers=headers)
    assert resp.status_code == 204


def check_codes(codes: list[dict], user_id: str):
    assert len(codes) == 10
    for code in codes:
        assert len(code["code"]) == 8
        assert code["user_id"] == user_id
        assert not code["consumed"]


@pt.mark.asyncio
async def test_mfa_enable(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    user_id = str(TestVars.get("data")["id"])
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'password': 'test_passw0rd_changed'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'password': 'test_passw0rd_invalid'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': "111111", 'secret': "abcdef!@#%", 'password': 'test_passw0rd_changed'})
    assert resp.status_code == 400

    secret = "a" * 16
    m = MFA(secret, 0)

    code = m.getCode()
    invalid_code = (code + str((int(code[-1]) + 1) % 10))[1:]
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': invalid_code, 'secret': secret, 'password': 'test_passw0rd_changed'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': m.getCode(), 'secret': secret, 'password': 'test_passw0rd_changed'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    TestVars.set("token", json["token"])
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': m.getCode(), 'secret': secret, 'password': 'test_passw0rd_changed'})
    assert resp.status_code == 404

    check_codes(json["backup_codes"], user_id)


@pt.mark.asyncio
async def test_mfa_view_backup_codes(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    user_id = str(TestVars.get("data")["id"])

    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': ''})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': 'invalid_password'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': 'test_passw0rd_changed'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert (nonce := json["nonce"])
    assert (regenerate_nonce := json["regenerate_nonce"])

    key = generateMfaVerificationKey(nonce, "A" * 16, b64decode(Config.KEY))

    resp = await client.post("/api/v9/users/@me/mfa/codes-verification", headers=headers,
                             json={'key': key, 'nonce': "", 'regenerate': False})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/users/@me/mfa/codes-verification", headers=headers,
                             json={'key': "", 'nonce': "", 'regenerate': False})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/users/@me/mfa/codes-verification", headers=headers,
                             json={'key': "invalidkey", 'nonce': nonce, 'regenerate': False})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/codes-verification", headers=headers,
                             json={'key': key, 'nonce': nonce, 'regenerate': False})
    assert resp.status_code == 200
    backup_codes = (await resp.get_json())["backup_codes"]
    check_codes(backup_codes, user_id)

    resp = await client.post("/api/v9/users/@me/mfa/codes-verification", headers=headers,
                             json={'key': key, 'nonce': regenerate_nonce, 'regenerate': True})
    assert resp.status_code == 200
    backup_codes_new = (await resp.get_json())["backup_codes"]
    assert backup_codes_new != backup_codes
    check_codes(backup_codes_new, user_id)


@pt.mark.asyncio
async def test_login_with_mfa(testapp):
    client: TestClientType = (await testapp).test_client()
    resp = await client.post('/api/v9/auth/login',
                             json={"login": f"{TestVars.EMAIL_ID}_test_changed@yepcord.ml",
                                   "password": "test_passw0rd_changed"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"] is None
    assert json["mfa"]
    assert (ticket := json["ticket"])

    code = MFA("a" * 16, 0).getCode()
    invalid_code = (code + str((int(code[-1]) + 1) % 10))[1:]

    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "", "code": ""})  # No ticket
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "1", "code": ""})  # No code
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "123", "code": "123456"})  # Invalid ticket
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": ticket, "code": invalid_code})  # Invalid code
    assert resp.status_code == 400

    mfa = MFA("a" * 16, 0)
    resp = await client.post('/api/v9/auth/mfa/totp',
                             json={"ticket": ticket, "code": mfa.getCode()})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]


@pt.mark.asyncio
async def test_disable_mfa(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers,
                             json={'code': "........"})  # Invalid backup code
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers,
                             json={'code': ""})
    assert resp.status_code == 400

    mfa = MFA("a" * 16, 0)
    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': mfa.getCode()})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    TestVars.set("token", json["token"])
    headers = {"Authorization": TestVars.get("token")}

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': mfa.getCode()})
    assert resp.status_code == 404


@pt.mark.asyncio
async def test_gifs_trending(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.get("/api/v9/gifs/trending", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["categories"]

    resp = await client.get("/api/v9/gifs/trending", headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v9/gifs/trending-gifs", headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/v9/gifs/trending-gifs", headers=headers)
    assert resp.status_code == 200

    resp = await client.post("/api/v9/gifs/select", headers=headers)
    assert resp.status_code == 204
    resp = await client.post("/api/v9/gifs/select", headers=headers)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_gifs_search_suggest(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.get("/api/v9/gifs/search?q=cat", headers=headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) > 0

    resp = await client.get("/api/v9/gifs/search?q=cat", headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v9/gifs/suggest?q=cat&limit=5", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert 0 < len(json) <= 5

    resp = await client.get("/api/v9/gifs/suggest?q=cat&limit=5", headers=headers)
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_edit_user_banner(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    resp = await client.patch("/api/v9/users/@me/profile", headers=headers, json={'banner': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["banner"]) == 32


@pt.mark.asyncio
async def test_notes(testapp):
    headers = {"Authorization": TestVars.get("token")}
    data2 = TestVars.get("data_u2")
    client: TestClientType = (await testapp).test_client()

    response = await client.get(f"/api/v9/users/@me/notes/{data2['id']}", headers=headers)  # No note
    assert response.status_code == 404
    response = await client.get(f"/api/v9/users/@me/notes/{data2['id'] + '1'}", headers=headers)  # No user
    assert response.status_code == 404
    response = await client.put(f"/api/v9/users/@me/notes/{data2['id'] + '1'}", headers=headers,
                                json={"note": "test"})  # No user
    assert response.status_code == 404

    response = await client.put(f"/api/v9/users/@me/notes/{data2['id']}", headers=headers,
                                json={"note": "test note 123!"})
    assert response.status_code == 204

    response = await client.get(f"/api/v9/users/@me/notes/{data2['id']}", headers=headers)  # No note
    assert response.status_code == 200
    json = await response.get_json()
    assert json["note"] == "test note 123!"


@pt.mark.asyncio
async def test_unknown_endpoints(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client: TestClientType = (await testapp).test_client()

    response = await client.get(f"/api/v9/unknown_endpoint", headers=headers)
    assert response.status_code == 501
    response = await client.get(f"/api/v9/unknown_endpoint")
    assert response.status_code == 501
    response = await client.get(f"/api/v9/unknown/nested/endpoint")
    assert response.status_code == 501
    response = await client.post(f"/api/v9/unknown_endpoint_post")
    assert response.status_code == 501
    response = await client.post(f"/api/v9/unknown/nested/endpoint/post")
    assert response.status_code == 501


@pt.mark.asyncio
async def test_channel_get(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]
    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] == channel["id"]
    assert json["name"] == channel["name"]


@pt.mark.asyncio
async def test_create_dm_channel(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    data = TestVars.get("data")
    data2 = TestVars.get("data_u2")
    resp = await client.post(f"/api/v9/users/@me/channels", headers=headers,
                             json={"recipients": [data["id"], data2["id"]]})
    assert resp.status_code == 200
    json = await resp.get_json()
    recipients = [r["id"] for r in json["recipients"]]
    assert recipients == [data2["id"]]
    assert json["type"] == ChannelType.DM
    TestVars.set("dm_channel_id", json["id"])

    resp = await client.post(f"/api/v9/channels/{json['id']}/messages", headers=headers,
                             json={"content": "test message"})
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_dm_channels(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    headers_u2 = {"Authorization": TestVars.get("token_u2")}
    data2 = TestVars.get("data_u2")
    resp = await client.post(f"/api/v9/users/@me/channels", headers=headers, json={"recipients": []})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["recipients"] == []
    assert json["type"] == ChannelType.GROUP_DM

    resp = await client.delete(f"/api/v9/channels/{json['id']}", headers=headers)
    assert resp.status_code == 204
    resp = await client.delete(f"/api/v9/channels/{TestVars.get('dm_channel_id')}", headers=headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/channels/{json['id']}", headers=headers)
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v9/channels/{TestVars.get('dm_channel_id')}", headers=headers)
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/users/@me/channels", headers=headers, json={"recipients": [Snowflake.makeId()]})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/users/@me/channels", headers=headers, json={"recipients": []})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["recipients"] == []
    assert json["type"] == ChannelType.GROUP_DM
    dm_id = json["id"]
    last_owner_id = json["owner_id"]
    TestVars.set("dmgroup_channel_id", json["id"])

    resp = await client.put(f"/api/v9/channels/{dm_id}/recipients/{Snowflake.makeId()}", headers=headers)
    assert resp.status_code == 404

    resp = await client.put(f"/api/v9/channels/{dm_id}/recipients/{data2['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.post(f"/api/v9/channels/{dm_id}/messages", headers=headers,
                             json={"content": "test message"})
    assert resp.status_code == 200
    json = await resp.get_json()

    resp = await client.post(f"/api/v9/channels/{dm_id}/messages/{json['id']}/ack", headers=headers_u2, json={})
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/channels/{dm_id}/messages/{json['id']}/ack", headers=headers_u2, json={
        "manual": True, "mention_count": 1
    })
    assert resp.status_code == 200

    resp = await client.put(f"/api/v9/channels/{dm_id}/pins/{json['id']}", headers=headers_u2)
    assert resp.status_code == 204
    resp = await client.get(f"/api/v9/channels/{dm_id}/pins", headers=headers_u2)
    assert resp.status_code == 200
    assert len(await resp.get_json()) >= 1
    resp = await client.delete(f"/api/v9/channels/{dm_id}/pins/{json['id']}", headers=headers_u2)
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/channels/{dm_id}/messages/ack", headers=headers_u2)
    assert resp.status_code == 204

    resp = await client.patch(f"/api/v9/channels/{dm_id}", headers=headers_u2, json={
        "icon": YEP_IMAGE,
        "name": "test_dm_channel"
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test_dm_channel"
    assert json["icon"] is not None

    resp = await client.patch(f"/api/v9/channels/{dm_id}", headers=headers_u2, json={
        "owner_id": Snowflake.makeId(),
    })
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/channels/{dm_id}", headers=headers, json={
        "owner_id": Snowflake.makeId(),
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["owner_id"] == str(last_owner_id)

    resp = await client.patch(f"/api/v9/channels/{dm_id}", headers=headers, json={
        "owner_id": data2['id'],
    })
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["owner_id"] == str(data2["id"])

    resp = await client.delete(f"/api/v9/channels/{dm_id}", headers=headers_u2)
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/channels/{dm_id}", headers=headers)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_change_username_dont_change_discriminator(testapp):
    client: TestClientType = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    data2 = TestVars.get("data_u2")
    resp = await client.patch(f"/api/v9/users/@me", headers=headers, json={"username": data2["username"],
                                                                           "discriminator": data2["discriminator"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["username"] == data2["username"]
    assert json["discriminator"] != data2["discriminator"]
