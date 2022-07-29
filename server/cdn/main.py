from quart import Quart, request
from functools import wraps
from ..core import Core
from ..utils import b64decode, mksf, c_json, ALLOWED_SETTINGS, ALLOWED_USERDATA, ECODES, ERRORS
from ..responses import userSettingsResponse, userdataResponse, userConsentResponse, userProfileResponse
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

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8003, reload=True, use_colors=False)