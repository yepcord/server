from quart import Quart
from quart_schema import validate_querystring, QuartSchema

from src.yepcord.enums import StickerFormat
from .models import CdnImageSizeQuery
from ..yepcord.config import Config
from ..yepcord.core import Core, CDN
from ..yepcord.storage import getStorage
from ..yepcord.utils import b64decode


class YEPcord(Quart):
    pass # Maybe it will be needed in the future

app = YEPcord("YEPcord-Cdn")
QuartSchema(app)
core = Core(b64decode(Config("KEY")))
cdn = CDN(getStorage(), core)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

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

@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


# Images (avatars, banners, emojis, icons, etc.)


@app.get("/avatars/<int:user_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_avatar(query_args: CdnImageSizeQuery, user_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (avatar := await cdn.getAvatar(user_id, file_hash, query_args.size, format)):
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{format}"}


@app.get("/banners/<int:user_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_banner(query_args: CdnImageSizeQuery, user_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 600: query_args.size = 600
    if not (banner := await cdn.getBanner(user_id, file_hash, query_args.size, format)):
        return b'', 404
    return banner, 200, {"Content-Type": f"image/{format}"}


@app.get("/splashes/<int:guild_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_splash(query_args: CdnImageSizeQuery, guild_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 600: query_args.size = 600
    if not (splash := await cdn.getGuildSplash(guild_id, file_hash, query_args.size, format)):
        return b'', 404
    return splash, 200, {"Content-Type": f"image/{format}"}


@app.get("/channel-icons/<int:channel_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_channel_icon(query_args: CdnImageSizeQuery, channel_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await cdn.getChannelIcon(channel_id, file_hash, query_args.size, format)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format}"}


@app.get("/icons/<int:guild_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_icon(query_args: CdnImageSizeQuery, guild_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await cdn.getGuildIcon(guild_id, file_hash, query_args.size, format)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format}"}


@app.get("/role-icons/<int:role_id>/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_role_icon(query_args: CdnImageSizeQuery, role_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await cdn.getRoleIcon(role_id, file_hash, query_args.size, format)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format}"}


@app.get("/emojis/<int:emoji_id>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_emoji(query_args: CdnImageSizeQuery, emoji_id: int, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 56: query_args.size = 56
    emoji = await core.getEmoji(emoji_id)
    if not emoji:
        # If emoji deleted or never existed
        for animated in (False, True):
            emoji = await cdn.getEmoji(emoji_id, query_args.size, format, animated)
            if emoji: # If deleted from database, but file found
                break
    else:
        emoji = await cdn.getEmoji(emoji_id, query_args.size, format, emoji.animated)
    if not emoji:
        return b'', 404
    return emoji, 200, {"Content-Type": f"image/{format}"}


@app.get("/guilds/<int:guild_id>/users/<int:member_id>/avatars/<string:file_hash>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_avatar(query_args: CdnImageSizeQuery, guild_id: int, member_id: int, file_hash: str, format: str):
    if format not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (avatar := await cdn.getGuildAvatar(member_id, guild_id, file_hash, query_args.size, format)):
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{format}"}


@app.get("/stickers/<int:sticker_id>.<string:format>")
@validate_querystring(CdnImageSizeQuery)
async def get_sticker(query_args: CdnImageSizeQuery, sticker_id: int, format: str):
    if format not in ["webp", "png", "gif"]:
        return b'', 400
    if query_args.size > 320: query_args.size = 320
    sticker = await core.getSticker(sticker_id)
    if not sticker:
        # If sticker deleted or never existed
        for animated in (False, True):
            sticker = await cdn.getSticker(sticker_id, query_args.size, format, animated)
            if sticker: # If deleted from database, but file found
                break
    else:
        sticker = await cdn.getSticker(sticker_id, query_args.size, format,
                                       sticker.format in (StickerFormat.APNG, StickerFormat.GIF))
    if not sticker:
        return b'', 404
    return sticker, 200, {"Content-Type": f"image/{format}"}


@app.get("/guild-events/<int:event_id>/<string:file_hash>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_event_image(query_args: CdnImageSizeQuery, event_id: int, file_hash: str):
    if query_args.size > 600: query_args.size = 600
    for form in ("png", "jpg"):
        if event_image := await cdn.getGuildEvent(event_id, file_hash, query_args.size, form):
            return event_image, 200, {"Content-Type": f"image/{form}"}
    return b'', 404


# Attachments


@app.get("/attachments/<int:channel_id>/<int:attachment_id>/<string:name>")
async def get_attachment(channel_id: int, attachment_id: int, name: str):
    if not (attachment := await core.getAttachment(attachment_id)):
        return b'', 404
    headers = {}
    if attachment.get("content_type"):
        headers["Content-Type"] = attachment.content_type
    if not (attachment := await cdn.getAttachment(channel_id, attachment_id, name)):
        return b'', 404
    return attachment, 200, headers


if __name__ == "__main__": # pragma: no cover
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8003, reload=True, use_colors=False)