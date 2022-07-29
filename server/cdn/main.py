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

# Auth

@app.route("/avatars/<int:uid>/<string:ahash>", methods=["GET"])
async def avatars_uid_hash(uid, ahash):
    ahash = ahash.split(".")[0]
    size = request.args.get("size", 1024)
    avatar = await cdn.getAvatar(uid, ahash, size)
    if not avatar:
        return b'', 404
    return avatar, 200, {"Content-Type": "image/webp"}

@app.route("/banners/<int:uid>/<string:ahash>", methods=["GET"])
async def banners_uid_hash(uid, bhash):
    bhash = bhash.split(".")[0]
    banner = await cdn.getBanner(uid, bhash)
    if not banner:
        return b'', 404
    return banner, 200, {"Content-Type": "image/webp"}

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8003, reload=True, use_colors=False)