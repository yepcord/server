from asyncio import get_event_loop
from base64 import b64encode

import pytest as pt
from google.protobuf.wrappers_pb2 import StringValue

from src.rest_api.main import app
from src.yepcord.enums import ChannelType, StickerType
from src.yepcord.proto import PreloadedUserSettings, TextAndImagesSettings
from src.yepcord.utils import getImage
from tests.yep_image import YEP_IMAGE


class TestVars:
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
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    return app

@pt.mark.asyncio
async def test_login_fail(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": "test@yepcord.ml", "password": "test_passw0rd"})
    assert response.status_code == 400

@pt.mark.asyncio
async def test_register(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": "TestUser",
        "email": "test@yepcord.ml",
        "password": "test_passw0rd",
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])

@pt.mark.asyncio
async def test_resend_verification_email(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/verify/resend', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204

@pt.mark.asyncio
async def test_getme_success(testapp):
    client = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200

@pt.mark.asyncio
async def test_logout(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/logout', headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 204

@pt.mark.asyncio
async def test_getme_fail(testapp):
    client = (await testapp).test_client()
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 401

@pt.mark.asyncio
async def test_login_success(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/login', json={"login": "test@yepcord.ml", "password": "test_passw0rd"})
    assert response.status_code == 200
    j = await response.get_json()
    assert "token" in j
    TestVars.set("token", j["token"])

@pt.mark.asyncio
async def test_change_username(testapp):
    client = (await testapp).test_client()
    response = await client.patch("/api/v9/users/@me", json={"username": "YepCordTest", "password": "test_passw0rd"}, headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200
    response = await client.get("/api/v9/users/@me", headers={
        "Authorization": TestVars.get("token")
    })
    assert response.status_code == 200
    j = await response.get_json()
    TestVars.set("data", await response.get_json())
    assert j["username"] == "YepCordTest"

@pt.mark.asyncio
async def test_settings(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client = (await testapp).test_client()
    assert (await client.get("/api/v9/users/@me/connections", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/consent", headers=headers)).status_code == 200
    assert (await client.post("/api/v9/users/@me/consent", headers=headers, json={"grant": ["personalization"], "revoke": []})).status_code == 200
    assert (await client.patch("/api/v9/users/@me/settings", headers=headers, json={"afk_timeout": 300})).status_code == 200

@pt.mark.asyncio
async def test_settings_proto(testapp):
    headers = {"Authorization": TestVars.get("token")}
    client = (await testapp).test_client()
    assert (await client.get("/api/v9/users/@me/settings-proto/1", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/2", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/3", headers=headers)).status_code == 200
    assert (await client.get("/api/v9/users/@me/settings-proto/4", headers=headers)).status_code == 400
    proto = PreloadedUserSettings(text_and_images=TextAndImagesSettings(render_spoilers=StringValue(value="ALWAYS")))
    proto = proto.SerializeToString()
    proto = b64encode(proto).decode("utf8")
    assert (await client.patch("/api/v9/users/@me/settings-proto/2", headers=headers, json={"settings": proto})).status_code == 200

@pt.mark.asyncio
async def test_register_other_user(testapp):
    client = (await testapp).test_client()
    response = await client.post('/api/v9/auth/register', json={
        "username": "TestUser",
        "email": "user@yepcord.ml",
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
    client = (await testapp).test_client()

    response = await client.get('/api/v9/users/@me/relationships', headers=headers)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.get('/api/v9/users/@me/relationships', headers=headers_u2)
    assert response.status_code == 200
    assert len(await response.get_json()) == 0
    response = await client.post('/api/v9/users/@me/relationships', headers=headers, json={"username": data2["username"], "discriminator": data2["discriminator"]})
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
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"].lower() == "general"][0]["id"]
    resp = await client.get(f"/api/v9/channels/{channel_id}/messages", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []

@pt.mark.asyncio
async def test_get_subscriptions(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    data = TestVars.get("data")
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/premium/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == [{'ended': False, 'user_id': data["id"]}]*30)

@pt.mark.asyncio
async def test_guild_templates_empty(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/templates", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []

@pt.mark.asyncio
async def test_create_guild_channels(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    parent_id = [channel for channel in TestVars.get("guild_channels") if channel["type"] == ChannelType.GUILD_CATEGORY][0]["id"]

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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    channel_id = \
    [channel for channel in TestVars.get("guild_channels") if channel["type"] == ChannelType.GUILD_CATEGORY][0]["id"]
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/channels", headers=headers, json=[{'id': channel_id, 'position': 1}])
    assert resp.status_code == 204

@pt.mark.asyncio
async def test_edit_guild(testapp):
    client = (await testapp).test_client()
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
    assert json["system_channel_id"] == TestVars.get("test_channel_id")
    assert len(json["icon"]) == 32

@pt.mark.asyncio
async def test_create_role(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.post(f"/api/v9/guilds/{guild_id}/roles", headers=headers, json={'name': 'new role'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "new role"
    TestVars.set("role_id", json["id"])

@pt.mark.asyncio
async def test_change_roles_positions(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    role_id = TestVars.get("role_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/roles", headers=headers, json=[{'id': role_id, 'position': 1}])
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json[0]["id"] == str(guild_id)
    assert json[1]["id"] == role_id

@pt.mark.asyncio
async def test_edit_role(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    role_id = TestVars.get("role_id")
    resp = await client.delete(f"/api/v9/guilds/{guild_id}/roles/{role_id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/roles/{role_id}", headers=headers, json={})
    assert resp.status_code == 404

@pt.mark.asyncio
async def test_get_roles_member_counts(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/roles/member-counts", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == {str(guild_id): 0})

@pt.mark.asyncio
async def test_get_emojis_empty(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.get(f"/api/v9/guilds/{guild_id}/emojis", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []

@pt.mark.asyncio
async def test_create_emoji(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    resp = await client.post(f"/api/v9/guilds/{guild_id}/emojis", headers=headers, json={'image': YEP_IMAGE, 'name': 'YEP'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP"
    assert json["animated"] == False
    assert json["available"] == True
    TestVars.set("emoji_id", json["id"])

@pt.mark.asyncio
async def test_get_emojis(testapp):
    client = (await testapp).test_client()
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
    assert json[0]["animated"] == False
    assert json[0]["available"] == True
    assert json[0]["user"]["id"] == data["id"]

@pt.mark.asyncio
async def test_edit_emoji_name(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    emoji_id = TestVars.get("emoji_id")
    resp = await client.patch(f"/api/v9/guilds/{guild_id}/emojis/{emoji_id}", headers=headers, json={'name': 'YEP_test'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "YEP_test"
    assert json["animated"] == False
    assert json["available"] == True

@pt.mark.asyncio
async def test_emoji_delete(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = TestVars.get("guild_id")
    channel = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_voice_channel"][0]
    channel_id = channel["id"]
    resp = await client.patch(f"/api/v9/channels/{channel_id}", headers=headers, json={'bitrate': 384000, 'user_limit': 69})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["type"] == 2
    assert json["id"] == channel_id
    assert json["guild_id"] == str(guild_id)
    assert json["user_limit"] == 69
    assert json["bitrate"] == 384000

@pt.mark.asyncio
async def test_delete_channel(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
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
async def test_get_stickers_empty(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/stickers", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []

@pt.mark.asyncio
async def test_create_sticker(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token"), "Content-Length": "1"}
    guild_id = str(TestVars.get("guild_id"))
    user_id = TestVars.get("data")["id"]
    image = getImage(YEP_IMAGE)
    assert image is not None
    image.filename = "yep.png"
    image.headers = []#[("Content-Disposition", "form-data; name=\"file\"; filename=\"yep.png\""), ("Content-Type", "image/png")]
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
    assert json["available"] == True
    assert json["user"]["id"] == user_id
    TestVars.set("sticker_id", json["id"])

@pt.mark.asyncio
async def test_edit_sticker(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/webhooks", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []

@pt.mark.asyncio
async def test_create_webhook(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
    webhook_id = TestVars.get("webhook_id")
    resp = await client.patch(f"/api/v9/webhooks/{webhook_id}", headers=headers,
                              json={'channel_id': channel_id, 'name': 'Test webhook'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["channel_id"] == channel_id
    assert json["name"] == "Test webhook"
    assert json["guild_id"] == guild_id

@pt.mark.asyncio
async def test_post_webhook_message(testapp):
    client = (await testapp).test_client()
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
    assert json["author"]["bot"] == True
    assert json["author"]["id"] == webhook_id
    assert json["author"]["discriminator"] == "0000"
    assert json["content"] == "test message sent from webhook 2"
    assert json["type"] == 0
    assert json["guild_id"] == guild_id

@pt.mark.asyncio
async def test_delete_webhook(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
    resp = await client.get(f"/api/v9/channels/{channel_id}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) >= 2

@pt.mark.asyncio
async def test_send_guild_message(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
    guild_id = str(TestVars.get("guild_id"))
    user_id = TestVars.get("data")["id"]
    resp = await client.post(f"/api/v9/channels/{channel_id}/typing", headers=headers)
    assert resp.status_code == 204

    resp = await client.post(f"/api/v9/channels/{channel_id}/messages", headers=headers,
                             json={"content": "test message", 'nonce': '1086700261180702720'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["author"]["id"] == user_id
    assert json["content"] == "test message"
    assert json["type"] == 0
    assert json["guild_id"] == guild_id
    assert json["nonce"] == '1086700261180702720'

@pt.mark.asyncio
async def test_create_guild_template(testapp):
    client = (await testapp).test_client()
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/vanity-url", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == {'code': None})

@pt.mark.asyncio
async def test_get_invites_empty(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    resp = await client.get(f"/api/v9/guilds/{guild_id}/invites", headers=headers)
    assert resp.status_code == 200

@pt.mark.asyncio
async def test_create_invite(testapp):
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
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
    client = (await testapp).test_client()
    headers = {"Authorization": TestVars.get("token")}
    guild_id = str(TestVars.get("guild_id"))
    channel_id = [channel for channel in TestVars.get("guild_channels") if channel["name"] == "test_text_channel"][0]["id"]
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
