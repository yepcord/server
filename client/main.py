from quart import Quart, redirect
from os.path import realpath, dirname, join
from aiohttp import ClientSession
from aiofiles import open as aopen

from server.config import Config

STATIC_FOLDER = join(dirname(realpath(__file__)), "assets/")
HTML_FILE = join(dirname(realpath(__file__)), "discord.html")

_domain = Config("DOMAIN")
CONFIG = {
    "CLIENT_HOST": Config("CLIENT_HOST"),
    "API_HOST": Config("API_HOST"),
    "GATEWAY_HOST": Config("GATEWAY_HOST"),
    "REMOTEAUTH_HOST": Config("REMOTEAUTH_HOST"),
    "CDN_HOST": Config("CDN_HOST"),
    "MEDIAPROXY_HOST": Config("MEDIAPROXY_HOST"),
    "NETWORKING_HOST": Config("NETWORKING_HOST"),
    "RTCLATENCY_HOST": Config("RTCLATENCY_HOST"),
    "ACTIVITYAPPLICATION_HOST": Config("ACTIVITYAPPLICATION_HOST"),
}


async def downloadAsset(file):
    if file.endswith(".js.map"):
        return
    async with ClientSession() as sess:
        async with sess.get(f"https://discord.com/assets/{file}") as res:
            async with aopen(join(STATIC_FOLDER, file), "wb") as fp:
                async for chunk in res.content.iter_chunked(32*1024):
                    await fp.write(chunk)

with open(HTML_FILE, "r", encoding="utf8") as f:
    HTML_DATA = f.read()

for k,v in CONFIG.items():
    HTML_DATA = HTML_DATA.replace("{%s}" % k, v)

app = Quart(
    "YEPCord",
    static_url_path="/assets",
    static_folder=STATIC_FOLDER
)


@app.route("/")
async def index():
    return redirect("/app")


@app.route("/login")
@app.route("/register")
@app.route("/app")
@app.route("/channels")
@app.route("/channels/@me/<channel>")
@app.route("/channels/<channel>")
@app.route("/connections/<connection>")
async def discord(**kwargs):
    return HTML_DATA


@app.route("/assets/<file>")
async def assets(file):
    await downloadAsset(file)
    return await app.send_static_file(file)

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8080, reload=True, use_colors=False)