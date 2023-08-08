"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import sys
from json import dumps as jdumps

from quart import Quart, request, Response
from quart_schema import QuartSchema, RequestSchemaValidationError

from .routes.auth import auth
from .routes.channels import channels
from .routes.gifs import gifs
from .routes.guilds import guilds
from .routes.hypesquad import hypesquad
from .routes.invites import invites
from .routes.other import other
from .routes.users import users
from .routes.users_me import users_me
from .routes.webhooks import webhooks
from ..yepcord.classes.gifs import Gifs
from ..yepcord.config import Config
from ..yepcord.core import Core, CDN
from ..yepcord.errors import InvalidDataErr, MfaRequiredErr, YDataError, EmbedErr, Errors
from ..yepcord.gateway_dispatcher import GatewayDispatcher
from ..yepcord.models import database
from ..yepcord.storage import getStorage
from ..yepcord.utils import b64decode, b64encode


class YEPcord(Quart):
    gifs: Gifs


app = YEPcord("YEPcord-api")
QuartSchema(app)
core = Core(b64decode(Config.KEY))
cdn = CDN(getStorage(), core)
gateway = GatewayDispatcher()
app.gifs = Gifs(Config.TENOR_KEY)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024


@app.before_serving
async def before_serving():
    if not database.is_connected:
        await database.connect()
    await gateway.init()


@app.after_serving
async def after_serving():
    if database.is_connected:
        await database.disconnect()
    await gateway.stop()


if "pytest" in sys.modules:  # pragma: no cover
    # Raise original exceptions instead of InternalServerError when testing
    from werkzeug.exceptions import InternalServerError


    @app.errorhandler(500)
    async def handle_500_for_pytest(error: InternalServerError):
        raise error.original_exception


@app.errorhandler(YDataError)
async def ydataerror_handler(err: YDataError):
    if isinstance(err, EmbedErr):
        return err.error, 400
    elif isinstance(err, InvalidDataErr):
        return err.error, err.code
    elif isinstance(err, MfaRequiredErr):
        ticket = b64encode(jdumps([err.uid, "login"]))
        ticket += f".{err.sid}.{err.sig}"
        return {"token": None, "sms": False, "mfa": True, "ticket": ticket}


@app.errorhandler(RequestSchemaValidationError)
async def handle_validation_error(error: RequestSchemaValidationError):
    pydantic_error = error.validation_error
    return Errors.from_pydantic(pydantic_error), 400


@app.after_request
async def set_cors_headers(response: Response) -> Response:
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
app.register_blueprint(webhooks, url_prefix="/api/webhooks")
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
    for k, v in request.headers.items():
        print(f"    {k}: {v}")
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        print(f"  Data: {await request.get_json()}")
    print("----------------")
    return "Not Implemented!", 501


if __name__ == "__main__":  # pragma: no cover
    # Deprecated
    from uvicorn import run as urun

    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)
