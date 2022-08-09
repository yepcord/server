from quart import Quart, request
from functools import wraps
from ..core import Core, CDN
from ..utils import b64decode, b64encode, mksf, c_json, ALLOWED_SETTINGS, ALLOWED_USERDATA, ECODES, ERRORS, getImage, \
    validImage, unpack_token, MFA, execute_after, ChannelType
from ..responses import userSettingsResponse, userdataResponse, userConsentResponse, userProfileResponse
from ..storage import FileStorage
from os import environ
from json import dumps as jdumps
from random import choice

class YEPcord(Quart):
    async def process_response(self, response, request_context):
        response = await super(YEPcord, self).process_response(response, request_context)
        response.headers['Server'] = "YEPcord"
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Headers'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "*"
        response.headers['Content-Security-Policy'] = "connect-src *;"
        
        return response

app = YEPcord("YEPcord-api")
core = Core(b64decode(environ.get("KEY")))
cdn = CDN(FileStorage(), core)

def NOT_IMP():
    print("Warning: route not implemented.")
    return ("405 Not implemented yet.", 405)

@app.before_serving
async def before_serving():
    await core.initDB(
        host=environ.get("DB_HOST"),
        port=3306,
        user=environ.get("DB_USER"),
        password=environ.get("DB_PASS"),
        db=environ.get("DB_NAME"),
        autocommit=True
    )
    await core.initMCL()

# Decorators

def getUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (token := request.headers.get("Authorization")):
            return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        if not (user := await core.getUser(token)):
            return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        kwargs["user"] = user
        return await f(*args, **kwargs)
    return wrapped

def getSession(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (token := request.headers.get("Authorization")):
            return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        if not (session := await core.getSession(*unpack_token(token))):
            return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        kwargs["session"] = session
        return await f(*args, **kwargs)
    return wrapped

def getChannel(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (channel := kwargs.get("channel")):
            return c_json(ERRORS[17], ECODES[17])
        if not (user := kwargs.get("user")):
            return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        if not (channel := await core.getChannel(channel)):
            return c_json(ERRORS[17], ECODES[17])
        if channel.type == ChannelType.DM:
            if user.id not in channel.recipients:
                return c_json({"message": "401: Unauthorized", "code": 0}, 401)
        kwargs["channel"] = channel
        return await f(*args, **kwargs)
    return wrapped

# Auth

@app.route("/api/v9/auth/register", methods=["POST"])
async def api_auth_register():
    data = await request.get_json()
    res = await core.register(
        mksf(),
        data["username"],
        data["email"],
        data["password"],
        data["date_of_birth"]
    )
    if type(res) == int:
        return c_json(ERRORS[res], ECODES[res])
    return c_json({"token": res.token})

@app.route("/api/v9/auth/login", methods=["POST"])
async def api_auth_login():
    data = await request.get_json()
    res = await core.login(data["login"], data["password"])
    if type(res) == int:
        return c_json(ERRORS[res], ECODES[res])
    if type(res) == tuple:
        if res[0] == 1:
            ticket = b64encode(jdumps([res[1], "login"]))
            ticket += f".{res[2]}.{res[3]}"
            return c_json({"token": None, "sms": False, "mfa": True, "ticket": ticket})
    return c_json({"token": res.token, "user_settings": {"locale": res.locale, "theme": res.theme}, "user_id": str(res.id)})

@app.route("/api/v9/auth/mfa/totp", methods=["POST"])
async def api_auth_mfa_totp():
    data = await request.get_json()
    if not (ticket := data.get("ticket")):
        return c_json(ERRORS[16], ECODES[16])
    if not (code := data.get("code")):
        return c_json(ERRORS[13], ECODES[13])
    if not (mfa := await core.getMfaFromTicket(ticket)):
        return c_json(ERRORS[16], ECODES[16])
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            return c_json(ERRORS[13], ECODES[13])
    user = await core.getLoginUser(mfa.uid)
    return c_json({"token": user.token, "user_settings": {"locale": user.locale, "theme": user.theme}, "user_id": str(user.id)})

@app.route("/api/v9/auth/logout", methods=["POST"])
@getSession
async def api_auth_logout(session):
    await core.logoutUser(session)
    return "", 204

@app.route("/api/v9/auth/verify/view-backup-codes-challenge", methods=["POST"])
@getUser
async def api_auth_verify_viewbackupcodeschallenge(user):
    data = await request.get_json()
    if not (password := data.get("password")):
        return c_json(ERRORS[15], ECODES[15])
    if not await core.checkUserPassword(user, password):
        return c_json(ERRORS[15], ECODES[15])
    nonce = await core.generateUserMfaNonce(user)
    return c_json({"nonce": nonce[0], "regenerate_nonce": nonce[1]})

# Users (@me)

@app.route("/api/v9/users/@me", methods=["GET"])
@getUser
async def api_users_me_get(user):
    return c_json(await userdataResponse(user))

@app.route("/api/v9/users/@me", methods=["PATCH"])
@getUser
async def api_users_me_patch(user):
    data = await user.data
    _settings = await request.get_json()
    d = "discriminator" in _settings and _settings.get("discriminator") != data["discriminator"]
    u = "username" in _settings and _settings.get("username") != data["username"]
    ures = dres = None
    if d or u:
        if "password" not in _settings:
            return c_json(ERRORS[6], ECODES[6])
        if not await core.checkUserPassword(user, _settings["password"]):
            return c_json(ERRORS[6], ECODES[6])
        if u:
            ures = await core.changeUserName(user, str(_settings["username"]))
            if type(ures) == int:
                return c_json(ERRORS[ures], ECODES[ures])
            del _settings["username"]
        if d:
            dres = await core.changeUserDiscriminator(user, int(_settings["discriminator"]))
            if type(dres) == int:
                if u and type(ures) != int:
                    return c_json(await userdataResponse(user))
                return c_json(ERRORS[dres], ECODES[dres])
            del _settings["discriminator"]
    if "new_password" in _settings:
        if "password" not in _settings:
            return c_json(ERRORS[6], ECODES[6])
        if not await core.checkUserPassword(user, _settings["password"]):
            return c_json(ERRORS[6], ECODES[6])
        await core.changeUserPassword(user, _settings["new_password"])
        del _settings["new_password"]

    settings = {}
    for k,v in _settings.items():
        k = k.lower()
        if k not in ALLOWED_USERDATA:
            continue
        t = ALLOWED_USERDATA[k]
        if not isinstance(v, t):
            if isinstance(t, tuple):
                t = t[-1]
            try:
                v = t(v)
            except:
                v = t()
        if k == "avatar":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await cdn.setAvatarFromBytesIO(user.id, img)):
                continue
        elif k == "banner":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await cdn.setBannerFromBytesIO(user.id, img)):
                continue
        settings[k] = v
    await core.setUserdata(user, settings)
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userdataResponse(user))

@app.route("/api/v9/users/@me/consent", methods=["GET"])
@getUser
async def api_users_me_consent_get(user):
    settings = await user.settings
    return c_json(await userdataResponse(user))

@app.route("/api/v9/users/@me/consent", methods=["POST"])
@getUser
async def api_users_me_consent_set(user):
    data = await request.get_json()
    if data["grant"] or data["revoke"]:
        settings = {}
        for g in data["grant"]:
            settings[g] = True
        for r in data["revoke"]:
            settings[r] = False
        await core.setSettings(user, settings)
    return c_json(await userConsentResponse(user))

@app.route("/api/v9/users/@me/settings", methods=["GET"])
@getUser
async def api_users_me_settings_get(user):
    return c_json(await userSettingsResponse(user))

@app.route("/api/v9/users/@me/settings", methods=["PATCH"])
@getUser
async def api_users_me_settings_patch(user):
    _settings = await request.get_json()
    if "status" in _settings:
        await core.updatePresence(user.id, {"status": _settings["status"]})
        await core.sendPresenceUpdateEvent(user.id, {"status": _settings["status"]})
        del _settings["status"]
    if "custom_status" in _settings:
        presence = await core.updatePresence(user.id, {"custom_status": _settings["custom_status"]})
        await core.sendPresenceUpdateEvent(user.id, presence)
        del _settings["custom_status"]
    settings = {}
    for k,v in _settings.items():
        k = k.lower()
        if k not in ALLOWED_SETTINGS:
            continue
        t = ALLOWED_SETTINGS[k]
        if not isinstance(v, t):
            try:
                v = t(v)
            except:
                v = t()
        if k == "friend_source_flags":
            for _k,_v in list(v.items()):
                if _k not in ["all", "mutual_friends", "mutual_guilds"]:
                    del v[_k]
                    continue
                if type(_v) != bool:
                    _v = bool(_v)
        settings[k] = v
    await core.setSettings(user, settings)
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userSettingsResponse(user))

@app.route("/api/v9/users/@me/connections", methods=["GET"])
@getUser
async def api_users_me_connections(user):
    return c_json("[]") # TODO

@app.route("/api/v9/users/@me/relationships", methods=["POST"])
@getUser
async def api_users_me_relationships_post(user):
    udata = await request.get_json()
    if not (rUser := await core.getUserByUsername(**udata)):
        return c_json(ERRORS[9], ECODES[9])
    if rUser == user:
        return c_json(ERRORS[10], ECODES[10])
    if (res := await core.relationShipAvailable(rUser, user)):
        return c_json(ERRORS[res], ECODES[res])
    await core.reqRelationship(rUser, user)
    return "", 204

@app.route("/api/v9/users/@me/relationships", methods=["GET"])
@getUser
async def api_users_me_relationships_get(user):
    return c_json(await core.getRelationships(user, with_data=True))

@app.route("/api/v9/users/@me/mfa/totp/enable", methods=["POST"])
@getSession
async def api_users_me_mfa_totp_enable(session):
    data = await request.get_json()
    if not (password := data.get("password")):
        return c_json(ERRORS[15], ECODES[15])
    if not await core.checkUserPassword(session, password):
        return c_json(ERRORS[15], ECODES[15])
    if not (secret := data.get("secret")):
        return c_json(ERRORS[12], ECODES[12])
    mfa = MFA(secret, session.id)
    if not mfa.valid:
        return c_json(ERRORS[12], ECODES[12])
    if not (code := data.get("code")):
        return c_json(ERRORS[13], ECODES[13])
    if mfa.getCode() != code:
        return c_json(ERRORS[13], ECODES[13])
    await core.setSettings(session, {"mfa": secret})
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await core.setBackupCodes(session, codes)
    await execute_after(core.sendUserUpdateEvent(session.id), 3)
    codes = [{"user_id": str(session.id), "code": code, "consumed": False} for code in codes]
    await core.logoutUser(session)
    session = await core.createSessionWithoutKey(session.id)
    return c_json({"token": session.token, "backup_codes": codes})

@app.route("/api/v9/users/@me/mfa/totp/disable", methods=["POST"])
@getSession
async def api_users_me_mfa_totp_disable(session):
    data = await request.get_json()
    if not (code := data.get("code")):
        return c_json(ERRORS[13], ECODES[13])
    if not (mfa := await core.getMfa(session)):
        return c_json(ERRORS[14], ECODES[14])
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            return c_json(ERRORS[13], ECODES[13])
    await core.setSettings(session, {"mfa": None})
    await core.clearBackupCodes(session)
    await core.sendUserUpdateEvent(session.id)
    await core.logoutUser(session)
    session = await core.createSessionWithoutKey(session.id)
    return c_json({"token": session.token})

@app.route("/api/v9/users/@me/mfa/codes-verification", methods=["POST"])
@getUser
async def api_users_me_mfa_codesverification(user):
    data = await request.get_json()
    if not (unonce := data.get("nonce")):
        return c_json(ERRORS[17], ECODES[17])
    reg = data.get("regenerate", False)
    nonce = await core.generateUserMfaNonce(user)
    nonce = nonce[1] if reg else nonce[0]
    if nonce != unonce:
        return c_json(ERRORS[17], ECODES[17])
    if reg:
        codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
        await core.setBackupCodes(user, codes)
        codes = [{"user_id": str(user.id), "code": code, "consumed": False} for code in codes]
    else:
        _codes = await core.getBackupCodes(user)
        codes = []
        for code, used in _codes:
            codes.append({"user_id": str(user.id), "code": code, "consumed": bool(used)})
    return c_json({"backup_codes": codes})

@app.route("/api/v9/users/@me/relationships/<int:uid>", methods=["PUT"])
@getUser
async def api_users_me_relationships_put(uid, user):
    await core.accRelationship(user, uid)
    return "", 204

@app.route("/api/v9/users/@me/relationships/<int:uid>", methods=["DELETE"])
@getUser
async def api_users_me_relationships_delete(uid, user):
    await core.delRelationship(user, uid)
    return "", 204

@app.route("/api/v9/users/@me/harvest", methods=["GET"])
@getUser
async def api_users_me_harvest(user):
    return "", 204

# Users

@app.route("/api/v9/users/<int:t_user_id>/profile", methods=["GET"])
@getUser
async def api_users_user_profile(user, t_user_id):
    user = await core.getUserProfile(t_user_id, user)
    if isinstance(user, int):
        return c_json(ERRORS[user], ECODES[user])
    return c_json(await userProfileResponse(user))

# Channels

@app.route("/api/v9/channels/<channel>", methods=["GET"])
async def api_channels_channel(channel):
    return NOT_IMP()

@app.route("/api/v9/channels/<int:channel>/messages", methods=["GET"])
@getUser
@getChannel
async def api_channels_channel_messages_get(user, channel):
    messages = await channel.messages(request.args.get("limit", 50))
    messages = [await m.json for m in messages]
    return c_json(messages)

@app.route("/api/v9/channels/<int:channel>/messages", methods=["POST"])
@getUser
@getChannel
async def api_channels_channel_messages_post(user, channel):
    data = await request.get_json()
    if not (content := data.get("content")):
        return c_json(ERRORS[19], ECODES[19])
    message = await core.sendMessage(channel, content=content, nonce=data.get("nonce"), author=user)
    message = await message.json
    if (nonce := data.get("nonce")):
        message["nonce"] = nonce
    return c_json(message)

# Other

@app.route("/api/v9/auth/location-metadata", methods=["GET"])
async def api_auth_locationmetadata():
    return c_json("{\"consent_required\": false, \"country_code\": \"US\", \"promotional_email_opt_in\": {\"required\": true, \"pre_checked\": false}}")

@app.route("/api/v9/science", methods=["POST"])
async def api_science():
    return "", 204

@app.route("/api/v9/experiments", methods=["GET"])
async def api_experiments():
    return c_json("{}")

@app.route("/api/v9/applications/detectable", methods=["GET"])
async def api_applications_detectable():
    return c_json("[]")

@app.route("/api/v9/users/@me/survey", methods=["GET"])
async def api_users_me_survey():
    return c_json("{\"survey\":null}")

@app.route("/api/v9/users/@me/affinities/guilds", methods=["GET"])
async def api_users_me_affinities_guilds():
    return c_json("{\"guild_affinities\":[]}")

@app.route("/api/v9/users/@me/affinities/users", methods=["GET"])
async def api_users_me_affinities_users():
    return c_json("{\"user_affinities\":[],\"inverse_user_affinities\":[]}")

@app.route("/api/v9/users/@me/library", methods=["GET"])
async def api_users_me_library():
    return c_json("[]")

@app.route("/api/v9/users/@me/billing/payment-sources", methods=["GET"])
async def api_users_me_billing_paymentsources():
    return c_json("[]")

@app.route("/api/v9/users/@me/billing/country-code", methods=["GET"])
async def api_users_me_billing_countrycode():
    return c_json("{\"country_code\": \"US\"}")

@app.route("/api/v9/users/@me/billing/localized-pricing-promo", methods=["GET"])
async def api_users_me_billing_localizedpricingpromo():
    return c_json("{\"country_code\": \"US\", \"localized_pricing_promo\": null}")

@app.route("/api/v9/users/@me/billing/user-trial-offer", methods=["GET"])
async def api_users_me_billing_usertrialoffer():
    return c_json("{\"message\": \"404: Not Found\", \"code\": 0}", 404)

@app.route("/api/v9/users/@me/billing/subscriptions", methods=["GET"])
async def api_users_me_billing_subscriptions():
    return c_json("[]")

@app.route("/api/v9/users/@me/billing/subscription-slots", methods=["GET"])
async def api_users_me_billing_subscriptionslots():
    return c_json("[]")

@app.route("/api/v9/users/@me/guilds/premium/subscription-slots", methods=["GET"])
async def api_users_me_guilds_premium_subscriptionslots():
    return c_json("[]")

@app.route("/api/v9/outbound-promotions", methods=["GET"])
async def api_outboundpromotions():
    return c_json("[]")

@app.route("/api/v9/users/@me/applications/<aid>/entitlements", methods=["GET"])
async def api_users_me_applications_id_entitlements(aid):
    return c_json("[]")

@app.route("/api/v9/store/published-listings/skus/<int:sku>/subscription-plans", methods=["GET"])
async def api_store_publishedlistings_skus_id_subscriptionplans(sku):
    if sku == 978380684370378762:
        return c_json("[{\"id\": \"978380692553465866\",\"name\": \"Nitro Basic Monthly\",\"interval\": 1,\"interval_count\": 1,\"tax_inclusive\": true,\"sku_id\": \"978380684370378762\",\"currency\": \"usd\",\"price\": 0,\"price_tier\": null}]")
    elif sku == 521846918637420545:
        return c_json("[{\"id\":\"511651871736201216\",\"name\":\"Premium Classic Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651876987469824\",\"name\":\"Premium Classic Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 521847234246082599:
        return c_json("[{\"id\":\"642251038925127690\",\"name\":\"Premium Quarterly\",\"interval\":1,\"interval_count\":3,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651880837840896\",\"name\":\"Premium Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651885459963904\",\"name\":\"Premium Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 590663762298667008:
        return c_json("[{\"id\":\"590665532894740483\",\"name\":\"Server Boost Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"590665538238152709\",\"name\":\"Server Boost Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    return c_json("[]")

@app.route("/api/v9/users/@me/outbound-promotions/codes", methods=["GET"])
async def api_users_me_outboundpromotions_codes():
    return c_json("[]")

@app.route("/api/v9/users/@me/entitlements/gifts", methods=["GET"])
async def api_users_me_entitlements_gifts():
    return c_json("[]")

@app.route("/api/v9/users/@me/activities/statistics/applications", methods=["GET"])
async def api_users_me_activities_statistics_applications():
    return c_json("[]")

@app.route("/api/v9/users/@me/billing/payments", methods=["GET"])
async def api_users_me_billing_payments():
    return c_json("[]")

# OAuth

@app.route("/api/v9/oauth2/tokens", methods=["GET"])
async def api_oauth_tokens():
    return c_json("[]")

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)