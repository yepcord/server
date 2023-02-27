from quart import Blueprint, request, current_app

from ...yepcord.utils import c_json

# Base path is 
gifs = Blueprint('gifs', __name__)


@gifs.get("/trending")
async def api_gifs_trending_get():
    result = {"gifs": [], "categories": []}
    for category in await current_app.gifs.categories:
        result["categories"].append(category.json)
        result["categories"][-1]["src"] = result["categories"][-1]["src"][:-4]+".mp4"
    return c_json(result)


@gifs.get("/trending-gifs")
async def api_gifs_trendinggifs_get():
    return c_json('[]')  # ???


@gifs.post("/select")
async def api_gifs_select_post():
    return "", 204


@gifs.get("/search")
async def api_gifs_search():
    search = await current_app.gifs.search(**request.args)
    result = [gif.json for gif in search.gifs]
    return c_json(result)

@gifs.get("/suggest")
async def api_gifs_suggest():
    args: dict = {**request.args}
    if "limit" in args: args["limit"] = int(args["limit"])
    return await current_app.gifs.suggest(**args)
