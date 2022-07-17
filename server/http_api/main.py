from quart import Quart, request, websocket
from functools import wraps
from ..core import Core
from ..utils import b64decode
from os import environ
from json import dumps as jdumps
from asyncio import CancelledError

app = Quart("Fosscord-Python")
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
        int(data["fingerprint"].split(".")[0]),
        data["username"],
        data["email"],
        data["password"],
        data["date_of_birth"]
    )
    return core.response(res)

@app.route("/api/v9/auth/login", methods=["POST"])
async def api_auth_login():
    return NOT_IMP()

# Users

@app.route("/api/v9/users/<user>/survey", methods=["GET"])
async def api_users_user_survey(user):
    return "{\"survey\":null}"

@app.route("/api/v9/users/<user>/affinities/guilds", methods=["GET"])
async def api_users_user_affinities_guilds(user):
    return "{\"guild_affinities\":[]}"

@app.route("/api/v9/users/<user>/affinities/users", methods=["GET"])
async def api_users_user_affinities_users(user):
    return "{\"user_affinities\":[],\"inverse_user_affinities\":[]}"

@app.route("/api/v9/users/<user>/library", methods=["GET"])
async def api_users_user_library(user):
    return "[]"

@app.route("/api/v9/users/<user>/billing/payment-sources", methods=["GET"])
async def api_users_user_billing_paymentsources(user):
    return "[]"

# Channels

@app.route("/api/v9/channels/<channel>", methods=["GET"])
async def api_channels_channel(channel):
    return NOT_IMP()

@app.route("/api/v9/science", methods=["POST"])
async def api_science():
    return "", 204

@app.websocket("/gateway")
async def ws_gateway():
    while True:
        await websocket.send(jdumps({"t": None, "s": None, "op": 10, "d": {"heartbeat_interval": 41250}}))
        try:
            data = await websocket.receive()
            await core.processGatewayData(websocket, data)
        except CancelledError:
            pass # TODO: Disconnect

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)