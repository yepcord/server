from quart import Quart, websocket
from .gateway import Gateway
from json import loads as jloads
from asyncio import CancelledError

class YEPcord(Quart):
    pass # Maybe it will be needed in the future

app = YEPcord("YEPcord-RAG")
gw = Gateway()

@app.before_serving
async def before_serving():
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
    setattr(ws, "connected", True)
    await gw.sendHello(ws)
    while True:
        try:
            data = await ws.receive()
            await gw.process(ws, jloads(data))
        except CancelledError:
            setattr(ws, "connected", False)
            pass # TODO: Handle disconnect

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8002, reload=True, use_colors=False)