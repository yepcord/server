from quart import Quart, websocket

from ..yepcord.config import Config
from ..yepcord.classes.other import ZlibCompressor
from ..yepcord.core import Core
from ..yepcord.utils import b64decode
from json import loads as jloads
from asyncio import CancelledError
from .gateway import Gateway


class YEPcord(Quart):
    pass # Maybe it will be needed in the future


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
async def ws_gateway():
    ws = websocket._get_current_object()
    await gw.sendHello(ws)
    while True:
        try:
            data = await ws.receive()
            await gw.process(ws, jloads(data))
        except CancelledError:
            await gw.disconnect(ws)
            break # TODO: Handle disconnect

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8099, reload=True, use_colors=False)