import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.classes.other import MFA
from src.yepcord.enums import ChannelType
from src.yepcord.snowflake import Snowflake
from tests.api.utils import TestClientType, create_users, create_guild, create_invite, enable_mfa, create_guild_channel, \
    add_user_to_guild, create_ban, create_message, create_role
from tests.yep_image import YEP_IMAGE


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_create_guild():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    assert guild["name"] == 'Test Guild'
    assert guild["icon"] is None
    assert guild["description"] is None
    assert guild["splash"] is None
    assert guild["discovery_splash"] is None
    assert guild["emojis"] == []
    assert len(guild["channels"]) > 0

    guild = await create_guild(client, user, "Test Guild", YEP_IMAGE)

    assert guild["name"] == 'Test Guild'
    assert len(guild["icon"]) == 32
    assert guild["description"] is None
    assert guild["splash"] is None
    assert guild["discovery_splash"] is None
    assert guild["emojis"] == []
    assert len(guild["channels"]) > 0


@pt.mark.asyncio
async def test_guild_subscriptions():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/premium/subscriptions", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == [{'ended': False, 'user_id': user["id"]}] * 30)


@pt.mark.asyncio
async def test_guild_templates_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/templates", headers=headers)
    assert resp.status_code == 200
    assert await resp.get_json() == []


@pt.mark.asyncio
async def test_edit_guild():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}", headers=headers, json={
        'name': 'Test Guild Renamed', 'afk_channel_id': None, 'afk_timeout': 900,
        'verification_level': 0, 'icon': YEP_IMAGE})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "Test Guild Renamed"
    assert json["afk_channel_id"] is None
    assert json["afk_timeout"] == 900
    assert len(json["icon"]) == 32

    guild2 = await create_guild(client, user, "Test Guild")
    channel = [ch for ch in guild2["channels"] if ch["type"] == ChannelType.GUILD_TEXT][0]

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}", headers=headers, json={
        'system_channel_id': str(Snowflake.makeId()), 'afk_channel_id': channel["id"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["afk_channel_id"] is None
    assert json["system_channel_id"] == guild["system_channel_id"]

    text_ch = await create_guild_channel(client, user, guild, "test-text")
    voice_ch = await create_guild_channel(client, user, guild, "test-voice", 2)

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}", headers=headers, json={
        'system_channel_id': voice_ch["id"], 'afk_channel_id': text_ch["id"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["afk_channel_id"] is None
    assert json["system_channel_id"] == guild["system_channel_id"]

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}", headers=headers, json={
        'system_channel_id': text_ch["id"], 'afk_channel_id': voice_ch["id"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["afk_channel_id"] == voice_ch["id"]
    assert json["system_channel_id"] == text_ch["id"]


@pt.mark.asyncio
async def test_guild_invites_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/invites", headers={"Authorization": user["token"]})
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_get_guild_invites():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel_id = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]["id"]
    await create_invite(client, user, channel_id)

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/invites", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1
    assert json[0]["inviter"]["id"] == user["id"]
    assert json[0]["channel"]["id"] == channel_id
    assert json[0]["guild"]["id"] == guild["id"]
    assert json[0]["max_age"] == 604800
    assert json[0]["max_uses"] == 0
    assert json[0]["uses"] == 0


@pt.mark.asyncio
async def test_get_vanity_url_empty():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/vanity-url", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    assert (await resp.get_json() == {'code': None})


@pt.mark.asyncio
async def test_create_guild_template():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers=headers,
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test"
    assert json["description"] == "test template"
    assert json["creator_id"] == user["id"]
    assert json["creator"]["id"] == user["id"]
    assert json["source_guild_id"] == guild["id"]

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/templates", headers=headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) == 1

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers=headers,
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 400


@pt.mark.asyncio
async def test_delete_guild_template():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers=headers,
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 200
    json = await resp.get_json()

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/templates/{json['code']}", headers=headers)
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_sync_update_guild_template():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers=headers,
                             json={'name': 'test', 'description': 'test template'})
    assert resp.status_code == 200
    json = await resp.get_json()

    await create_guild_channel(client, user, guild, "test")

    resp = await client.put(f"/api/v9/guilds/{guild['id']}/templates/{json['code']}", headers=headers)
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/templates/{json['code']}", headers=headers,
                              json={"name": "test template updated"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["name"] == "test template updated"


@pt.mark.asyncio
async def test_delete_guild():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    mfa = MFA("a" * 16, 0)
    await enable_mfa(client, user1, mfa)
    guild = await create_guild(client, user1, "Test")
    await add_user_to_guild(client, guild, user1, user2)
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/delete", headers=headers2, json={})
    assert resp.status_code == 403

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/delete", headers=headers1, json={})
    assert resp.status_code == 400
    resp = await client.post(f"/api/v9/guilds/{guild['id']}/delete", headers=headers1, json={"code": "wrong"})
    assert resp.status_code == 400

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/delete", headers=headers1, json={"code": mfa.getCode()})
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_leave_guild():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test")
    await add_user_to_guild(client, guild, user1, user2)
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.delete(f"/api/v9/users/@me/guilds/{guild['id']}", headers=headers1)
    assert resp.status_code == 400

    resp = await client.delete(f"/api/v9/users/@me/guilds/{guild['id']}", headers=headers2)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_kick_member():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test")
    channel = [channel for channel in guild["channels"] if channel["type"] == ChannelType.GUILD_TEXT][0]
    await add_user_to_guild(client, guild, user1, user2)
    admin_role = await create_role(client, user1, guild["id"], perms=8)
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/members/{Snowflake.makeId()}", headers=headers1)
    assert resp.status_code == 204

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/members/{user1['id']}", headers=headers2)
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user2['id']}", headers=headers1,
                              json={"roles": [admin_role["id"]]})
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/members/{user1['id']}", headers=headers2)
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/members/{user2['id']}", headers=headers1)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/channels/{channel['id']}", headers={"Authorization": user2["token"]})
    assert resp.status_code == 401


@pt.mark.asyncio
async def test_ban_member():
    client: TestClientType = app.test_client()
    user1, user2, user3 = (await create_users(client, 3))
    guild = await create_guild(client, user1, "Test")
    channel1 = await create_guild_channel(client, user1, guild, "Test 1")
    channel2 = await create_guild_channel(client, user1, guild, "Test 2")
    admin_role = await create_role(client, user1, guild["id"], perms=8)
    await add_user_to_guild(client, guild, user1, user3)
    headers = {"Authorization": user1["token"]}

    await create_ban(client, user1, guild, user2["id"])
    await create_ban(client, user1, guild, user2["id"])
    await create_ban(client, user1, guild, str(Snowflake.makeId()), exp_code=404)

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user3['id']}", headers=headers,
                              json={"roles": [admin_role["id"]]})
    assert resp.status_code == 200

    await create_ban(client, user3, guild, user1["id"], exp_code=403)

    await create_message(client, user3, channel1["id"], content="1")
    await create_message(client, user3, channel1["id"], content="2")
    await create_message(client, user3, channel1["id"], content="3")
    await create_message(client, user3, channel2["id"], content="1")

    resp = await client.get(f"/api/v9/channels/{channel1['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 3
    resp = await client.get(f"/api/v9/channels/{channel2['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1

    await create_ban(client, user1, guild, user3["id"], seconds=86400)

    resp = await client.get(f"/api/v9/channels/{channel1['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 0
    resp = await client.get(f"/api/v9/channels/{channel2['id']}/messages", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 0

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/bans", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 2


@pt.mark.asyncio
async def test_unban_member():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    guild = await create_guild(client, user1, "Test")
    headers = {"Authorization": user1["token"]}

    await create_ban(client, user1, guild, user2["id"])

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/bans", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 1

    resp = await client.delete(f"/api/v9/guilds/{guild['id']}/bans/{user2['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/bans", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 0


@pt.mark.asyncio
async def test_integrations():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test")

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/integrations", headers={"Authorization": user["token"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json) == 0


@pt.mark.asyncio
async def test_update_member():
    client: TestClientType = app.test_client()
    user1, user2 = await create_users(client, 2)
    guild = await create_guild(client, user1, "Test Guild")
    await add_user_to_guild(client, guild, user1, user2)
    role1 = await create_role(client, user1, guild["id"])
    role2 = await create_role(client, user1, guild["id"])
    headers1 = {"Authorization": user1["token"]}
    headers2 = {"Authorization": user2["token"]}

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role1['id']}", json={"permissions": "8"},
                              headers=headers1)
    assert resp.status_code == 200
    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/roles/{role2['id']}", json={"permissions": "8"},
                              headers=headers1)
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user1['id']}", headers=headers1,
                              json={"roles": [role1["id"]], "nick": "TEST", "avatar": YEP_IMAGE})
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user2['id']}", headers=headers1,
                              json={"roles": [role1["id"]]})
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user2['id']}", headers=headers1,
                              json={"avatar": YEP_IMAGE})
    assert resp.status_code == 403

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/members/{user1['id']}", headers=headers2,
                              json={"roles": [role2["id"]]})
    assert resp.status_code == 403


@pt.mark.asyncio
async def test_set_vanity_url():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    headers = {"Authorization": user["token"]}
    code = f"test_{Snowflake.makeId()}"

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers)
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": None})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": None})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": None})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": code})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": code})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": code})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": code})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": None})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": code})

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["code"] == code
    assert "uses" in json

    guild2 = await create_guild(client, user, "Test Guild 2")
    resp = await client.patch(f"/api/v9/guilds/{guild2['id']}/vanity-url", headers=headers, json={"code": f"{code}_1"})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": f"{code}_1"})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": f"{code}_1"})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": code})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": f"{code}_2"})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": f"{code}_2"})

    resp = await client.patch(f"/api/v9/guilds/{guild['id']}/vanity-url", headers=headers, json={"code": ""})
    assert resp.status_code == 200
    assert (await resp.get_json() == {"code": None})


@pt.mark.asyncio
async def test_create_guild_from_template():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    guild = await create_guild(client, user, "Test Guild")
    channel = await create_guild_channel(client, user, guild, f"test-channel-{Snowflake.makeId()}",
                                         permission_overwrites=[{"id": guild["id"], "type": 0, "allow": 0,
                                                                 "deny": 1024}])
    headers = {"Authorization": user["token"]}

    resp = await client.post(f"/api/v9/guilds/{guild['id']}/templates", headers=headers, json={"name": "test"})
    assert resp.status_code == 200
    json = await resp.get_json()
    code = json["code"]

    resp = await client.post(f"/api/v9/guilds/templates/{Snowflake.makeId()}", headers=headers, json={"name": "yep"})
    assert resp.status_code == 404

    resp = await client.post(f"/api/v9/guilds/templates/{code}", headers=headers, json={"icon": YEP_IMAGE, "name": "_"})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["id"] != guild["id"]
    assert json["name"] == "_"
    ch = [ch for ch in json["channels"] if ch["name"] == channel["name"]]
    assert len(ch) == 1
    ch = ch[0]
    assert len(ch["permission_overwrites"]) == 1


@pt.mark.asyncio
async def test_get_audit_logs():
    client: TestClientType = app.test_client()
    user1, user2 = await create_users(client, 2)
    guild = await create_guild(client, user1, "Test Guild")
    channel = await create_guild_channel(client, user1, guild, "test")
    headers = {"Authorization": user1["token"]}

    resp = await client.delete(f"/api/v9/channels/{channel['id']}", headers=headers)
    assert resp.status_code == 200

    await create_ban(client, user1, guild, user2["id"])

    resp = await client.get(f"/api/v9/guilds/{guild['id']}/audit-logs", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert len(json["audit_log_entries"]) == 3
    assert len(json["users"]) == 1


