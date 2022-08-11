from os import environ
from quart import Quart, request
from ..core import Core, CDN
from ..storage import FileStorage
from ..utils import b64decode


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

@app.route("/avatars/<int:uid>/<string:name>", methods=["GET"])
async def avatars_uid_hash(uid, name):
    ahash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = request.args.get("size", 1024)
    avatar = await cdn.getAvatar(uid, ahash, size, fmt)
    if not avatar:
        return b'', 404
    return avatar, 200, {"Content-Type": "image/webp"}

@app.route("/banners/<int:uid>/<string:name>", methods=["GET"])
async def banners_uid_hash(uid, name):
    bhash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = request.args.get("size", 600)
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 404
    banner = await cdn.getBanner(uid, bhash, size, fmt)
    if not banner:
        return b'', 404
    return banner, 200, {"Content-Type": "image/webp"}

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8003, reload=True, use_colors=False)