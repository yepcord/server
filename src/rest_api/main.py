from json import dumps as jdumps

from quart import Quart, request
from quart.globals import request_ctx
from quart_schema import QuartSchema, RequestSchemaValidationError

from .routes.webhooks import webhooks
from .routes.auth import auth
from .routes.channels import channels
from .routes.gifs import gifs
from .routes.guilds import guilds
from .routes.hypesquad import hypesquad
from .routes.invites import invites
from .routes.other import other
from .routes.users import users
from .routes.users_me import users_me
from ..yepcord.classes.gifs import Gifs
from ..yepcord.config import Config
from ..yepcord.core import Core, CDN
from ..yepcord.ctx import Ctx
from ..yepcord.errors import InvalidDataErr, MfaRequiredErr, YDataError, EmbedErr, Errors
from ..yepcord.storage import getStorage
from ..yepcord.utils import b64decode, b64encode, c_json


class YEPcord(Quart):
    gifs: Gifs

    async def dispatch_request(self, request_context=None):
        request_ = (request_context or request_ctx).request
        if request_.routing_exception is not None:
            self.raise_routing_exception(request_)

        if request_.method == "OPTIONS" and request_.url_rule.provide_automatic_options:
            return await self.make_default_options_response()

        handler = self.view_functions[request_.url_rule.endpoint]
        Ctx.set("CORE", core)
        Ctx.set("STORAGE", cdn.storage)
        if getattr(handler, "__db", None):
            async with core.db() as db:
                db.dontCloseOnAExit()
                Ctx["DB"] = db
                result = await self.ensure_async(handler)(**request_.view_args)
                await db.close()
                return result
        else:
            return await self.ensure_async(handler)(**request_.view_args)


app = YEPcord("YEPcord-api")
QuartSchema(app)
core = Core(b64decode(Config("KEY")))
cdn = CDN(getStorage(), core)
app.gifs = Gifs(Config("TENOR_KEY"))

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

@app.before_serving
async def before_serving():
    await core.initDB(
        host=Config("DB_HOST"),
        port=3306,
        user=Config("DB_USER"),
        password=Config("DB_PASS"),
        db=Config("DB_NAME"),
        autocommit=True
    )
    await core.initMCL()


@app.errorhandler(YDataError)
async def ydataerror_handler(e):
    if isinstance(e, EmbedErr):
        return c_json(e.error, 400)
    elif isinstance(e, InvalidDataErr):
        return c_json(e.error, e.code)
    elif isinstance(e, MfaRequiredErr):
        ticket = b64encode(jdumps([e.uid, "login"]))
        ticket += f".{e.sid}.{e.sig}"
        return c_json({"token": None, "sms": False, "mfa": True, "ticket": ticket})


@app.errorhandler(RequestSchemaValidationError)
async def handle_validation_error(error: RequestSchemaValidationError):
    pydantic_error = error.validation_error
    return c_json(Errors.from_pydantic(pydantic_error), 400)


@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


app.register_blueprint(auth, url_prefix="/api/v9/auth")
app.register_blueprint(users_me, url_prefix="/api/v9/users/@me")
app.register_blueprint(users, url_prefix="/api/v9/users")
app.register_blueprint(channels, url_prefix="/api/v9/channels")
app.register_blueprint(invites, url_prefix="/api/v9/invites")
app.register_blueprint(guilds, url_prefix="/api/v9/guilds")
app.register_blueprint(webhooks, url_prefix="/api/v9/webhooks")
app.register_blueprint(gifs, url_prefix="/api/v9/gifs")
app.register_blueprint(hypesquad, url_prefix="/api/v9/hypesquad")
app.register_blueprint(other, url_prefix="/")


# Unknown endpoints


@app.route("/api/v9/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def other_api_endpoints(path):
    print("----------------")
    print(f"  Path: /api/v9/{path}")
    print(f"  Method: {request.method}")
    print("  Headers:")
    for k,v in request.headers.items():
        print(f"    {k}: {v}")
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        print(f"  Data: {await request.get_json()}")
    print("----------------")
    return "Not Implemented!", 501


if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)