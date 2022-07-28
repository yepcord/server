from quart import Quart
from os.path import realpath, dirname, join
from aiohttp import ClientSession
from aiofiles import open as aopen

STATIC_FOLDER = join(dirname(realpath(__file__)), "assets/")
HTML_FILE = join(dirname(realpath(__file__)), "discord.html")

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

app = Quart(
    "YEPCord",
    static_url_path="/assets",
    static_folder=STATIC_FOLDER
)

@app.route("/")
@app.route("/login")
@app.route("/register")
@app.route("/app")
@app.route("/channels")
@app.route("/channels/<channel>")
async def discord(channel=None):
    return HTML_DATA

@app.route("/assets/<file>")
async def assets(file):
    await downloadAsset(file)
    print(f"Downloaded: {file}")
    return await app.send_static_file(file)

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8080, reload=True, use_colors=False)