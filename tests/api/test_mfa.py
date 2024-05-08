import pytest as pt
import pytest_asyncio

from yepcord.rest_api.main import app
from yepcord.yepcord.classes.other import MFA, JWT
from yepcord.yepcord.config import Config
from yepcord.yepcord.utils import b64decode
from .utils import TestClientType, create_users, enable_mfa
from ..utils import register_app_error_handler

register_app_error_handler(app)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


def generateMfaVerificationKey(nonce: str, mfa_key: str, key: bytes):
    if not (payload := JWT.decode(nonce, key + b64decode(mfa_key))):
        return
    token = JWT.encode({"code": payload["code"]}, key)
    signature = token.split(".")[2]
    return signature.replace("-", "").replace("_", "")[:8].upper()


def check_codes(codes: list[dict], user_id: str):
    assert len(codes) == 10
    for code in codes:
        assert len(code["code"]) == 8
        assert code["user_id"] == user_id
        assert not code["consumed"]


@pt.mark.asyncio
async def test_mfa_enable():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]

    headers = {"Authorization": user["token"]}
    user_id = user["id"]
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'password': user["password"]})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'password': 'test_passw0rd_invalid'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': "111111", 'secret': "abcdef!@#%", 'password': user["password"]})
    assert resp.status_code == 400

    secret = "a" * 16
    mfa = MFA(secret, 0)

    code = mfa.getCode()
    invalid_code = (code + str((int(code[-1]) + 1) % 10))[1:]
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': invalid_code, 'secret': secret, 'password': user["password"]})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': mfa.getCode(), 'secret': secret, 'password': user["password"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    user["token"] = json["token"]
    headers = {"Authorization": user["token"]}
    resp = await client.post("/api/v9/users/@me/mfa/totp/enable", headers=headers,
                             json={'code': mfa.getCode(), 'secret': secret, 'password': user["password"]})
    assert resp.status_code == 404

    check_codes(json["backup_codes"], user_id)


@pt.mark.asyncio
async def test_mfa_view_backup_codes():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    user_id = user["id"]

    mfa = MFA("a" * 16, 0)

    await enable_mfa(client, user, mfa)
    headers = {"Authorization": user["token"]}

    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': ''})
    assert resp.status_code == 400
    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': 'invalid_password'})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/auth/verify/view-backup-codes-challenge", headers=headers,
                             json={'password': user["password"]})
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
                             json={'key': "", 'nonce': nonce, 'regenerate': False})
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
async def test_login_with_mfa():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    mfa = MFA("a" * 16, 0)
    await enable_mfa(client, user, mfa)

    resp = await client.post('/api/v9/auth/login', json={"login": user["email"], "password": user["password"]})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"] is None
    assert json["mfa"]
    assert (ticket := json["ticket"])

    code = mfa.getCode()
    invalid_code = (code + str((int(code[-1]) + 1) % 10))[1:]

    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "", "code": ""})  # No ticket
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "1", "code": ""})  # No code
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": "123", "code": "123456"})  # Invalid ticket
    assert resp.status_code == 400
    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": ticket, "code": invalid_code})  # Invalid code
    assert resp.status_code == 400

    resp = await client.post('/api/v9/auth/mfa/totp', json={"ticket": ticket, "code": mfa.getCode()})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]


@pt.mark.asyncio
async def test_disable_mfa():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    mfa = MFA("a" * 16, 0)
    await enable_mfa(client, user, mfa)
    headers = {"Authorization": user["token"]}

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': "........"})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': ""})
    assert resp.status_code == 400

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': mfa.getCode()})
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["token"]
    user["token"] = json["token"]
    headers = {"Authorization": user["token"]}

    resp = await client.post("/api/v9/users/@me/mfa/totp/disable", headers=headers, json={'code': mfa.getCode()})
    assert resp.status_code == 404
