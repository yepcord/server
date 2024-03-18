from asyncio import CancelledError

from quart import Quart, websocket, Websocket
from tortoise.contrib.quart import register_tortoise

from .gateway import Gateway
from ..yepcord.config import Config


class YEPcord(Quart):
    pass  # Maybe it will be needed in the future


app = YEPcord("YEPcord-VoiceGateway")
gw = Gateway()


@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord Voice Gateway"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


@app.websocket("/")
async def ws_gateway_voice():
    # noinspection PyProtectedMember,PyUnresolvedReferences
    ws: Websocket = websocket._get_current_object()
    await gw.sendHello(ws)
    while True:
        try:
            data = await ws.receive_json()
            await gw.process(ws, data)
        except CancelledError:
            raise


register_tortoise(
   app,
   db_url=Config.DB_CONNECT_STRING,
   modules={"models": ["yepcord.yepcord.models"]},
   generate_schemas=False,
)
