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
from __future__ import annotations

from functools import wraps
from json import loads
from typing import Optional, Union, TYPE_CHECKING

from PIL import Image
from async_timeout import timeout
from magic import from_buffer
from quart import request, current_app, g

import yepcord.yepcord.models as models
from ..yepcord.classes.captcha import Captcha
from ..yepcord.config import Config
from ..yepcord.ctx import getCore, getCDNStorage
from ..yepcord.enums import MessageType
from ..yepcord.errors import Errors, InvalidDataErr
from ..yepcord.models import Session, User, Channel, Attachment, Authorization, Bot, Webhook, Message
from ..yepcord.snowflake import Snowflake

if TYPE_CHECKING:  # pragma: no cover
    from .models.channels import MessageCreate


async def getSessionFromToken(token: str) -> Optional[Union[Session, Authorization, Bot]]:
    if not token:
        return

    token = token.split(" ")
    if len(token) == 1:  # Regular token
        return await Session.from_token(token[0])
    elif len(token) == 2 and token[0].lower() == "bearer" and g.get("oauth_allowed"):  # oauth2 token
        auth = await Authorization.from_token(token[1])
        oauth_scopes = g.get("oauth_scopes", set())
        if auth is None or oauth_scopes & auth.scope_set != oauth_scopes:
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        return auth
    elif len(token) == 2 and token[0].lower() == "bot" and g.get("bots_allowed"):
        return await Bot.from_token(token[1])


async def _getMessage(user: User, channel: Channel, message_id: int) -> Message:
    if not channel:
        raise InvalidDataErr(404, Errors.make(10003))
    if not user:
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
    if not message_id or not (message := await getCore().getMessage(channel, message_id)):
        raise InvalidDataErr(404, Errors.make(10008))
    return message


def captcha(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if request.method == "GET" or (service_name := Config.CAPTCHA["enabled"]) is None:
            return await f(*args, **kwargs)

        service = Captcha.get(service_name)
        data = await request.get_json()
        if data is None or not (captcha_key := data.get("captcha_key")):
            return service.error_response(["captcha-required"])

        success, errors = await service.verify(captcha_key)
        if not success:
            return service.error_response(errors)

        return await f(*args, **kwargs)

    return wrapped


# Idk


async def get_multipart_json() -> dict:
    try:
        form = await request.form
        if not form:
            raise ValueError
        return loads(form["payload_json"])
    except (ValueError, KeyError):
        raise InvalidDataErr(400, Errors.make(50035))


async def processMessageData(data: Optional[dict], channel: Channel) -> tuple[dict, list[Attachment]]:
    attachments = []
    if data is None:  # Multipart request
        if request.content_length is not None and request.content_length > 1024 * 1024 * 100:
            raise InvalidDataErr(400, Errors.make(50045))
        async with timeout(current_app.config["BODY_TIMEOUT"]):
            files = list((await request.files).values())
            data = await get_multipart_json()
            if len(files) > 10:
                raise InvalidDataErr(400, Errors.make(50013, {"files": {
                    "code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."
                }}))
            total_size = 0
            for idx, file in enumerate(files):
                att = {"filename": None}
                if idx + 1 <= len(data["attachments"]):
                    att = data["attachments"][idx]
                name = att.get("filename") or file.filename or "unknown"
                get_content = getattr(file, "getvalue", file.read)
                content = get_content()
                total_size += len(content)
                if total_size > 1024 * 1024 * 100: raise InvalidDataErr(400, Errors.make(50045))
                content_type = file.content_type.strip() if file.content_type else from_buffer(content[:1024], mime=True)
                metadata = {}
                if content_type.startswith("image/"):
                    img = Image.open(file)
                    metadata = {"height": img.height, "width": img.width}
                    img.close()
                att = await Attachment.create(
                    id=Snowflake.makeId(), channel=channel, message=None, filename=name, size=len(content),
                    content_type=content_type, metadata=metadata
                )
                await getCDNStorage().uploadAttachment(content, att)
                attachments.append(att)
    if not data.get("content") and \
            not data.get("embeds") and \
            not data.get("attachments") and \
            not data.get("sticker_ids"):
        raise InvalidDataErr(400, Errors.make(50006))
    return data, attachments


def makeEmbedError(code, path=None, replaces=None):
    if replaces is None: replaces = {}
    base_error = {"code": 50035, "errors": {"embeds": {}}, "message": "Invalid Form Body"}

    def insertError(error):
        errors = base_error["errors"]["embeds"]
        if path is None:
            errors["_errors"] = error
            return
        for el in path.split("."):
            errors[el] = {}
            errors = errors[el]
        errors["_errors"] = error

    if code == 23:
        insertError([{"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}])
        return base_error
    elif code == 24:
        m = "Scheme \"%SCHEME%\" is not supported. Scheme must be one of ('http', 'https')."
        for k, v in replaces.items():
            m = m.replace(f"%{k.upper()}%", v)
        insertError([{"code": "URL_TYPE_INVALID_SCHEME", "message": m}])
        return base_error
    elif code == 25:
        m = "Could not parse %VALUE%. Should be ISO8601."
        for k, v in replaces.items():
            m = m.replace(f"%{k.upper()}%", v)
        insertError([{"code": "DATE_TIME_TYPE_PARSE", "message": m}])
        return base_error
    elif code == 26:
        insertError([{"code": "NUMBER_TYPE_MAX", "message": "int value should be <= 16777215 and >= 0."}])
        return base_error
    elif code == 27:
        m = "Must be %LENGTH% or fewer in length."
        for k, v in replaces.items():
            m = m.replace(f"%{k.upper()}%", v)
        insertError([{"code": "BASE_TYPE_MAX_LENGTH", "message": m}])
        return base_error
    elif code == 28:
        insertError([{"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or fewer in length."}])
        return base_error


async def process_stickers(sticker_ids: list[int]):
    stickers = [await getCore().getSticker(sticker_id) for sticker_id in sticker_ids]
    stickers_data = {"sticker_items": [], "stickers": []}
    for sticker in stickers:
        if sticker is None:
            continue
        stickers_data["stickers"].append(await sticker.ds_json(False))
        stickers_data["sticker_items"].append({
            "format_type": sticker.format,
            "id": str(sticker.id),
            "name": sticker.name,
        })
    return stickers_data


async def validate_reply(data: MessageCreate, channel: Channel) -> int:
    message_type = MessageType.DEFAULT
    if data.message_reference:
        data.validate_reply(channel, await getCore().getMessage(channel, data.message_reference.message_id))
    if data.message_reference:
        message_type = MessageType.REPLY
    return message_type


async def processMessage(data: dict, channel: Channel, author: Optional[User], validator_class,
                         webhook: Webhook=None) -> models.Message:
    data, attachments = await processMessageData(data, channel)
    w_author = {}
    if webhook is not None:
        w_author = {
            "bot": True,
            "id": str(webhook.id),
            "username": data.get("username", webhook.name),
            "avatar": data.get("avatar", webhook.avatar),
            "discriminator": "0000"
        }

    data = validator_class(**data)

    message_type = await validate_reply(data, channel)
    stickers_data = await process_stickers(data.sticker_ids)
    if not data.content and not data.embeds and not attachments and not stickers_data["stickers"]:
        raise InvalidDataErr(400, Errors.make(50006))

    data_json = data.to_json()
    if webhook is not None:
        data_json["webhook_id"] = webhook.id
    message = await models.Message.create(
        id=Snowflake.makeId(), channel=channel, author=author, **data_json, **stickers_data, type=message_type,
        guild=channel.guild, webhook_author=w_author)
    message.nonce = data_json.get("nonce")

    for attachment in attachments:
        attachment.message = message
        await attachment.save()

    return message
