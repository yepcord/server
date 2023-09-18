from src.rest_api.main import app as _app
from src.yepcord.classes.other import MFA
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import getImage
from tests.yep_image import YEP_IMAGE

TestClientType = _app.test_client_class


async def create_user(app: TestClientType, email: str, password: str, username: str) -> str:
    response = await app.post('/api/v9/auth/register', json={
        "username": username,
        "email": email,
        "password": password,
        "date_of_birth": "2000-01-01",
    })
    assert response.status_code == 200
    json = await response.get_json()
    assert "token" in json
    return json["token"]


async def get_userdata(app: TestClientType, token: str) -> dict:
    response = await app.get("/api/v9/users/@me", headers={
        "Authorization": token
    })
    assert response.status_code == 200
    return await response.get_json()


async def create_users(app: TestClientType, count: int = 1) -> list[dict]:
    users = []
    for _ in range(count):
        temp_id = Snowflake.makeId()
        token = await create_user(app, f"{temp_id}_test@yepcord.ml", "test_passw0rd", f"TestUser_{temp_id}")
        users.append({
            "token": token,
            "password": "test_passw0rd",
            **(await get_userdata(app, token))
        })

    return users


async def enable_mfa(app: TestClientType, user: dict, mfa: MFA) -> None:
    resp = await app.post("/api/v9/users/@me/mfa/totp/enable", headers={"Authorization": user["token"]},
                          json={"code": mfa.getCode(), "secret": mfa.key, "password": user["password"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    user["token"] = json["token"]


async def rel_count(app: TestClientType, user: dict) -> int:
    response = await app.get('/api/v9/users/@me/relationships', headers={"Authorization": user["token"]})
    assert response.status_code == 200
    return len(await response.get_json())


async def rel_request(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.post("/api/v9/users/@me/relationships", headers={"Authorization": from_["token"]},
                              json={"username": to_["username"], "discriminator": to_["discriminator"]})
    return response.status_code


async def rel_delete(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.delete(f"/api/v9/users/@me/relationships/{from_['id']}", json={},
                                headers={"Authorization": to_["token"]})
    return response.status_code


async def rel_accept(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.put(f"/api/v9/users/@me/relationships/{from_['id']}", headers={"Authorization": to_["token"]},
                             json={})
    return response.status_code


async def rel_block(app: TestClientType, from_: dict, to_: dict) -> int:
    response = await app.put(f"/api/v9/users/@me/relationships/{to_['id']}", headers={"Authorization": from_["token"]},
                             json={"type": 2})
    return response.status_code


async def create_guild(app: TestClientType, user: dict, name: str, icon: str = None) -> dict:
    resp = await app.post("/api/v9/guilds", headers={"Authorization": user["token"]}, json={'name': name, 'icon': icon})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_guild_channel(app: TestClientType, user: dict, guild: dict, name: str, type_=0,
                               parent: str = None) -> dict:
    resp = await app.post(f"/api/v9/guilds/{guild['id']}/channels", headers={"Authorization": user["token"]},
                          json={'type': type_, 'name': name, 'parent_id': parent})
    assert resp.status_code == 200
    channel = await resp.get_json()
    guild["channels"].append(channel)
    return channel


async def create_invite(app: TestClientType, user: dict, channel_id: str, max_age=604800, max_uses=0) -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/invites", headers={"Authorization": user["token"]},
                          json={'max_age': max_age, 'max_uses': max_uses})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_webhook(app: TestClientType, user: dict, channel_id: str, name="Captain Hook") -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/webhooks", headers={"Authorization": user["token"]},
                          json={'name': name})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_role(app: TestClientType, user: dict, guild_id: str, name="new role") -> dict:
    resp = await app.post(f"/api/v9/guilds/{guild_id}/roles", headers={"Authorization": user["token"]},
                          json={'name': name})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_emoji(app: TestClientType, user: dict, guild_id: str, name: str, image=YEP_IMAGE) -> dict:
    resp = await app.post(f"/api/v9/guilds/{guild_id}/emojis", headers={"Authorization": user["token"]},
                          json={'image': image, 'name': name})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_sticker(app: TestClientType, user: dict, guild_id: str, name: str, tags="slight_smile",
                         image=YEP_IMAGE) -> dict:
    image = getImage(image)
    assert image is not None
    image.filename = "yep.png"
    image.headers = []
    resp = await app.post(f"/api/v9/guilds/{guild_id}/stickers", headers={"Authorization": user["token"]}, files={
        "file": image
    }, form={
        "name": name,
        "tags": tags
    })

    assert resp.status_code == 200
    return await resp.get_json()


async def create_message(app: TestClientType, user: dict, channel_id: str, *, exp_code=200, **kwargs) -> dict:
    resp = await app.post(f"/api/v9/channels/{channel_id}/messages", headers={"Authorization": user["token"]},
                          json=kwargs)
    assert resp.status_code == exp_code
    return await resp.get_json()


async def create_dm_channel(app: TestClientType, user1: dict, user2: dict) -> dict:
    resp = await app.post(f"/api/v9/users/@me/channels", headers={"Authorization": user1["token"]},
                          json={"recipients": [user1["id"], user2["id"]]})
    assert resp.status_code == 200
    return await resp.get_json()


async def create_dm_group(app: TestClientType, user: dict, recipient_ids: list[str], *, exp_code=200) -> dict:
    resp = await app.post(f"/api/v9/users/@me/channels", headers={"Authorization": user["token"]},
                          json={"recipients": recipient_ids})
    assert resp.status_code == exp_code
    return await resp.get_json()


async def create_ban(app: TestClientType, user: dict, guild: dict, target_id: str, *, exp_code=204) -> dict:
    resp = await app.put(f"/api/v9/guilds/{guild['id']}/bans/{target_id}", headers={"Authorization": user["token"]},
                         json={})
    assert resp.status_code == exp_code
    return await resp.get_json()
