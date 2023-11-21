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

import sys

from quart import Quart
from quart_schema import validate_querystring, QuartSchema
from tortoise.contrib.quart import register_tortoise

from .models import CdnImageSizeQuery
from ..yepcord.config import Config
from ..yepcord.core import Core
from ..yepcord.enums import StickerFormat
from ..yepcord.storage import getStorage
from ..yepcord.utils import b64decode


class YEPcord(Quart):
    pass  # Maybe it will be needed in the future


app = YEPcord("YEPcord-Cdn")
QuartSchema(app)
core = Core(b64decode(Config.KEY))

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024


@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response


# Images (avatars, banners, emojis, icons, etc.)


@app.get("/avatars/<int:user_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_avatar(query_args: CdnImageSizeQuery, user_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (avatar := await getStorage().getAvatar(user_id, file_hash, query_args.size, format_)):
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{format_}"}


@app.get("/banners/<int:user_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_banner(query_args: CdnImageSizeQuery, user_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 600: query_args.size = 600
    if not (banner := await getStorage().getBanner(user_id, file_hash, query_args.size, format_)):
        return b'', 404
    return banner, 200, {"Content-Type": f"image/{format_}"}


@app.get("/splashes/<int:guild_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_splash(query_args: CdnImageSizeQuery, guild_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 600: query_args.size = 600
    if not (splash := await getStorage().getGuildSplash(guild_id, file_hash, query_args.size, format_)):
        return b'', 404
    return splash, 200, {"Content-Type": f"image/{format_}"}


@app.get("/channel-icons/<int:channel_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_channel_icon(query_args: CdnImageSizeQuery, channel_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await getStorage().getChannelIcon(channel_id, file_hash, query_args.size, format_)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format_}"}


@app.get("/icons/<int:guild_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_icon(query_args: CdnImageSizeQuery, guild_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await getStorage().getGuildIcon(guild_id, file_hash, query_args.size, format_)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format_}"}


@app.get("/role-icons/<int:role_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_role_icon(query_args: CdnImageSizeQuery, role_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (icon := await getStorage().getRoleIcon(role_id, file_hash, query_args.size, format_)):
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{format_}"}


@app.get("/emojis/<int:emoji_id>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_emoji(query_args: CdnImageSizeQuery, emoji_id: int, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 56: query_args.size = 56
    emoji = await core.getEmoji(emoji_id)
    if not emoji:
        # If emoji deleted or never existed
        for animated in (False, True):
            emoji = await getStorage().getEmoji(emoji_id, query_args.size, format_, animated)
            if emoji:  # If deleted from database, but file found
                break
    else:
        emoji = await getStorage().getEmoji(emoji_id, query_args.size, format_, emoji.animated)
    if not emoji:
        return b'', 404
    return emoji, 200, {"Content-Type": f"image/{format_}"}


@app.get("/guilds/<int:guild_id>/users/<int:member_id>/avatars/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_avatar(query_args: CdnImageSizeQuery, guild_id: int, member_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (avatar := await getStorage().getGuildAvatar(member_id, guild_id, file_hash, query_args.size, format_)):
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{format_}"}


@app.get("/stickers/<int:sticker_id>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_sticker(query_args: CdnImageSizeQuery, sticker_id: int, format_: str):
    if format_ not in ["webp", "png", "gif"]:
        return b'', 400
    if query_args.size > 320: query_args.size = 320
    sticker = await core.getSticker(sticker_id)
    if not sticker:
        # If sticker deleted or never existed
        for animated in (False, True):
            sticker = await getStorage().getSticker(sticker_id, query_args.size, format_, animated)
            if sticker:  # If deleted from database, but file found
                break
    else:
        sticker = await getStorage().getSticker(sticker_id, query_args.size, format_,
                                       sticker.format in (StickerFormat.APNG, StickerFormat.GIF))
    if not sticker:
        return b'', 404
    return sticker, 200, {"Content-Type": f"image/{format_}"}


@app.get("/guild-events/<int:event_id>/<string:file_hash>")
@validate_querystring(CdnImageSizeQuery)
async def get_guild_event_image(query_args: CdnImageSizeQuery, event_id: int, file_hash: str):
    if query_args.size > 600: query_args.size = 600
    for form in ("png", "jpg"):
        if event_image := await getStorage().getGuildEvent(event_id, file_hash, query_args.size, form):
            return event_image, 200, {"Content-Type": f"image/{form}"}
    return b'', 404


@app.get("/app-icons/<int:app_id>/<string:file_hash>.<string:format_>")
@validate_querystring(CdnImageSizeQuery)
async def get_app_icon(query_args: CdnImageSizeQuery, app_id: int, file_hash: str, format_: str):
    if format_ not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if query_args.size > 1024: query_args.size = 1024
    if not (avatar := await getStorage().getAppIcon(app_id, file_hash, query_args.size, format_)):
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{format_}"}


if "pytest" in sys.modules:  # pragma: no cover
    # Raise original exceptions instead of InternalServerError when testing
    from werkzeug.exceptions import InternalServerError

    @app.errorhandler(500)
    async def handle_500_for_pytest(error: InternalServerError):
        raise error.original_exception


# Attachments


@app.get("/attachments/<int:channel_id>/<int:attachment_id>/<string:name>")
async def get_attachment(channel_id: int, attachment_id: int, name: str):
    if not (attachment := await core.getAttachment(attachment_id)):
        return b'', 404
    headers = {}
    if attachment.content_type:
        headers["Content-Type"] = attachment.content_type
    if not (attachment := await getStorage().getAttachment(channel_id, attachment_id, name)):
        return b'', 404
    return attachment, 200, headers


register_tortoise(
    app,
    db_url=Config.DB_CONNECT_STRING,
    modules={"models": ["yepcord.yepcord.models"]},
    generate_schemas=False,
)
