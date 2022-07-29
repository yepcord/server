from quart import Quart, request
from functools import wraps
from ..core import Core, CDN
from ..utils import b64decode, mksf, c_json, ALLOWED_SETTINGS, ALLOWED_USERDATA, ECODES, ERRORS
from ..responses import userSettingsResponse, userdataResponse, userConsentResponse, userProfileResponse
from ..storage import FileStorage
from os import environ

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

def getChannel(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
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
    return c_json({"token": res.token, "user_settings": {"locale": res.locale, "theme": res.theme}, "user_id": str(res.id)})

# Users (@me)

@app.route("/api/v9/users/@me", methods=["GET"])
@getUser
async def api_users_me_get(user):
    return c_json(await userdataResponse(user))

@app.route("/api/v9/users/@me", methods=["PATCH"])
@getUser
async def api_users_me_patch(user):
    settings = {}
    for k,v in (await request.get_json()).items():
        k = k.lower()
        if k not in ALLOWED_USERDATA:
            continue
        t = ALLOWED_USERDATA[k]
        if not isinstance(v, t):
            try:
                v = t(v)
            except:
                v = t()
        if k == "avatar":
            if not (img := await cdn.convertImgToWebp(v)):
                continue
            v = await cdn.setAvatarFromBytesIO(user.id, img)
            if not v:
                continue
        elif k == "banner":
            v = None # TODO: make banner upload
        settings[k] = v
    await core.setUserdata(user, settings)
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
    settings = await user.settings
    return c_json(await userConsentResponse(user))

@app.route("/api/v9/users/@me/settings", methods=["GET"])
@getUser
async def api_users_me_settings_get(user):
    return c_json(await userSettingsResponse(user))

@app.route("/api/v9/users/@me/settings", methods=["PATCH"])
@getUser
async def api_users_me_settings_patch(user):
    settings = {}
    for k,v in (await request.get_json()).items():
        k = k.lower()
        if k not in ALLOWED_SETTINGS:
            continue
        t = ALLOWED_SETTINGS[k]
        if not isinstance(v, t):
            try:
                v = t(v)
            except:
                v = t()
        settings[k] = v
    await core.setSettings(user, settings)
    return c_json(await userSettingsResponse(user))

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

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)