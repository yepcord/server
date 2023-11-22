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

from quart import Quart, websocket
from tortoise.contrib.quart import register_tortoise

from ..yepcord.config import Config
from ..yepcord.classes.other import ZlibCompressor
from ..yepcord.core import Core
from ..yepcord.utils import b64decode
from json import loads as jloads
from asyncio import CancelledError
from .gateway import Gateway


class YEPcord(Quart):
    pass  # Maybe it will be needed in the future


app = YEPcord("YEPcord-Gateway")
core = Core(b64decode(Config.KEY))
gw = Gateway(core)


@app.before_serving
async def before_serving():
    await gw.init()


@app.after_serving
async def after_serving():
    await gw.stop()


@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


@app.websocket("/")
async def ws_gateway():
    # noinspection PyProtectedMember,PyUnresolvedReferences
    ws = websocket._get_current_object()
    setattr(ws, "zlib", ZlibCompressor() if websocket.args.get("compress") == "zlib-stream" else None)
    setattr(ws, "ws_connected", True)
    await gw.add_client(ws)
    while True:
        try:
            data = await ws.receive()
            await gw.process(ws, jloads(data))
        except CancelledError:
            setattr(ws, "ws_connected", False)
            await gw.disconnect(ws)
            raise


register_tortoise(
    app,
    db_url=Config.DB_CONNECT_STRING,
    modules={"models": ["yepcord.yepcord.models"]},
    generate_schemas=False,
)
