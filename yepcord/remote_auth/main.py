"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2024 RuslanUC

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
from asyncio import CancelledError

from quart import Quart, websocket, Websocket
from tortoise.contrib.quart import register_tortoise

from .gateway import Gateway
from ..yepcord.config import Config


class YEPcord(Quart):
    pass  # Maybe it will be needed in the future


app = YEPcord("YEPcord-RAG")
gw = Gateway()


@app.before_serving
async def before_serving():
    await gw.init()


@app.after_serving
async def after_serving():
    await gw.stop()


@app.after_request
async def set_cors_headers(response):  # pragma: no cover
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


@app.websocket("/")
async def ws_gateway():
    version = websocket.args.get("v", "")
    version = int(version) if version.isdigit() else 1

    # noinspection PyProtectedMember,PyUnresolvedReferences
    ws: Websocket = websocket._get_current_object()
    await gw.connect(ws, version)
    while True:
        try:
            data = await ws.receive_json()
            await gw.process(ws, data)
        except CancelledError:
            await gw.disconnect(ws)
            raise


register_tortoise(
    app,
    db_url=Config.DB_CONNECT_STRING,
    modules={"models": ["yepcord.yepcord.models"]},
    generate_schemas=False,
)
