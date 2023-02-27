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


app = YEPcord("YEPcord-Gateway")
core = Core(b64decode(Config("KEY")))
gw = Gateway(core)


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
    await gw.init()


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
    ws = websocket._get_current_object()
    setattr(ws, "zlib", ZlibCompressor() if websocket.args.get("compress") == "zlib-stream" else None)
    setattr(ws, "ws_connected", True)
    await gw.sendHello(ws)
    while True:
        try:
            data = await ws.receive()
            await gw.process(ws, jloads(data))
        except CancelledError:
            setattr(ws, "ws_connected", False)
            await gw.disconnect(ws)
            break # TODO: Handle disconnect

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8001, reload=True, use_colors=False)