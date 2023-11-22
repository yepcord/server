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
from __future__ import annotations
from functools import wraps
from json import loads
from random import choice
from time import time
from typing import Optional, Union, TYPE_CHECKING, Literal

from PIL import Image
from async_timeout import timeout
from magic import from_buffer
from quart import request, current_app, g

from ..yepcord.classes.captcha import Captcha
from ..yepcord.config import Config
from ..yepcord.ctx import Ctx, getCore, getCDNStorage
from ..yepcord.enums import MessageType
from ..yepcord.errors import Errors, InvalidDataErr
from ..yepcord.models import Session, User, Channel, Attachment, Application, Authorization, Bot, Interaction, Webhook, \
    Message
from ..yepcord.snowflake import Snowflake
from ..yepcord.utils import b64decode
import yepcord.yepcord.models as models

if TYPE_CHECKING:  # pragma: no cover
    from .models.channels import MessageCreate


def multipleDecorators(*decorators):
    def _multipleDecorators(f):
        for dec in decorators[::-1]:
            f = dec(f)
        return f
    return _multipleDecorators


def allowWithoutUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        Ctx["allow_without_user"] = True
        return await f(*args, **kwargs)

    return wrapped


def allowOauth(scopes: list[str]):
    def decorator(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            g.oauth_allowed = True
            g.oauth_scopes = set(scopes)
            return await f(*args, **kwargs)

        return wrapped
    return decorator


def allowBots(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        g.bots_allowed = True
        return await f(*args, **kwargs)

    return wrapped


async def getSessionFromToken(token: str) -> Optional[Union[Session, Authorization, Bot]]:
    if not token:
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))

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
    else:
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))


def getUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        try:
            if not (session := await getSessionFromToken(request.headers.get("Authorization", ""))):
                raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
            g.auth = session
            g.user = user = session.user
        except InvalidDataErr as e:
            if e.code != 401 or not Ctx.get("allow_without_user"):
                raise
            user = User(id=0, email="", password="")
        kwargs["user"] = user
        return await f(*args, **kwargs)
    return wrapped


def getSession(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (session := await Session.from_token(request.headers.get("Authorization", ""))):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        g.auth = session
        kwargs["session"] = session
        return await f(*args, **kwargs)
    return wrapped


def getChannel(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (user := kwargs.get("user")) and not (user := g.get("user")):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        if not (channel := kwargs.get("channel")) or not (channel := await getCore().getChannel(channel)):
            raise InvalidDataErr(404, Errors.make(10003))
        if not await getCore().getUserByChannel(channel, user.id):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        kwargs["channel"] = channel
        return await f(*args, **kwargs)
    return wrapped


async def _getMessage(user: User, channel: Channel, message_id: int) -> Message:
    if not channel:
        raise InvalidDataErr(404, Errors.make(10003))
    if not user:
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
    if not message_id or not (message := await getCore().getMessage(channel, message_id)):
        raise InvalidDataErr(404, Errors.make(10008))
    return message


async def _getMessageWebhook(webhook_id: int, message_id: int) -> Message:
    if not message_id or not webhook_id:
        raise InvalidDataErr(404, Errors.make(10008))
    message = await Message.get_or_none(id=message_id, webhook_id=webhook_id).select_related(*Message.DEFAULT_RELATED)
    if message is None:
        raise InvalidDataErr(404, Errors.make(10008))
    return message


def getMessage(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if "webhook" in kwargs:
            kwargs["message"] = await _getMessageWebhook(kwargs["webhook"].id, kwargs.get("message"))
        else:
            kwargs["message"] = await _getMessage(kwargs.get("user"), kwargs.get("channel"), kwargs.get("message"))
        return await f(*args, **kwargs)
    return wrapped


def getInvite(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (invite := kwargs.get("invite")):
            raise InvalidDataErr(404, Errors.make(10006))
        try:
            invite_id = int.from_bytes(b64decode(invite), "big")
            if not (inv := await getCore().getInvite(invite_id)):
                raise ValueError
            invite = inv
        except ValueError:
            if not (invite := await getCore().getVanityCodeInvite(invite)):
                raise InvalidDataErr(404, Errors.make(10006))
        kwargs["invite"] = invite
        return await f(*args, **kwargs)
    return wrapped


def getGuild(with_member: bool, allow_without: bool=False):
    def _getGuild(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            if "guild" not in kwargs and allow_without:
                return await f(*args, **(kwargs | {"guild": None}))
            if not (user := kwargs.get("user")):
                raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
            if not (guild := int(kwargs.get("guild"))) or not (guild := await getCore().getGuild(guild)):
                raise InvalidDataErr(404, Errors.make(10004))
            if not (member := await getCore().getGuildMember(guild, user.id)):
                raise InvalidDataErr(403, Errors.make(50001))
            kwargs["guild"] = guild
            if with_member:
                kwargs["member"] = member
            return await f(*args, **kwargs)
        return wrapped
    return _getGuild


def getRole(f):
    # noinspection PyUnboundLocalVariable
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (role := kwargs.get("role")) or \
                not (guild := kwargs.get("guild")) or \
                not (role := await getCore().getRole(role)) or \
                role.guild != guild:
            raise InvalidDataErr(404, Errors.make(10011))
        kwargs["role"] = role
        return await f(*args, **kwargs)
    return wrapped


def getGuildTemplate(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (template := kwargs.get("template")):
            raise InvalidDataErr(404, Errors.make(10057))
        if not (guild := kwargs.get("guild")):
            raise InvalidDataErr(404, Errors.make(10004))
        try:
            template_id = int.from_bytes(b64decode(template), "big")
            if not (template := await getCore().getGuildTemplateById(template_id)):
                raise ValueError
            if template.guild.id != guild.id:
                raise ValueError
        except ValueError:
            raise InvalidDataErr(404, Errors.make(10057))
        kwargs["template"] = template
        return await f(*args, **kwargs)

    return wrapped


def getApplication(f):
    # noinspection PyUnboundLocalVariable
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (app_id := kwargs.get("application_id")) or \
                not (user := kwargs.get("user")):
            raise InvalidDataErr(404, Errors.make(10002))
        if user.is_bot and app_id != user.id:
            raise InvalidDataErr(404, Errors.make(10002))
        kw = {"id": app_id, "deleted": False}
        if not user.is_bot:
            kw["owner"] = user
        if (app := await Application.get_or_none(**kw).select_related("owner")) is None:
            raise InvalidDataErr(404, Errors.make(10002))
        del kwargs["application_id"]
        kwargs["application"] = app
        return await f(*args, **kwargs)
    return wrapped


def getInteraction(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (int_id := kwargs.get("interaction")) or not (token := kwargs.get("token")):
            raise InvalidDataErr(404, Errors.make(10002))
        if not token.startswith("int___"):
            raise InvalidDataErr(404, Errors.make(10002))
        interaction = await (Interaction.get_or_none(id=int_id)
                             .select_related("application", "user", "channel", "command"))
        if interaction is None or interaction.ds_token != token:
            raise InvalidDataErr(404, Errors.make(10002))
        del kwargs["token"]
        kwargs["interaction"] = interaction
        return await f(*args, **kwargs)

    return wrapped


def getWebhook(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (webhook_id := kwargs.get("webhook")) or not (token := kwargs.get("token")):
            raise InvalidDataErr(404, Errors.make(10015))
        webhook = await (Webhook.get_or_none(id=webhook_id).select_related("channel"))
        if webhook is None or webhook.token != token:
            raise InvalidDataErr(404, Errors.make(10015))
        del kwargs["webhook"]
        del kwargs["token"]
        kwargs["webhook"] = webhook
        return await f(*args, **kwargs)

    return wrapped


def getInteractionW(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (application_id := kwargs.get("application_id")) or not (token := kwargs.get("token")):
            raise InvalidDataErr(404, Errors.make(10002))
        if not (inter := await Interaction.from_token(f"int___{token}")) or inter.application.id != application_id:
            raise InvalidDataErr(404, Errors.make(10002))
        message = await Message.get_or_none(interaction=inter, id__gt=Snowflake.fromTimestamp(time() - 15 * 60)) \
            .select_related(*Message.DEFAULT_RELATED)
        if message is None:
            raise InvalidDataErr(404, Errors.make(10008))
        del kwargs["application_id"]
        del kwargs["token"]
        kwargs["interaction"] = inter
        kwargs["message"] = message
        return await f(*args, **kwargs)

    return wrapped


getGuildWithMember = getGuild(with_member=True)
getGuildWithoutMember = getGuild(with_member=False)
getGuildWM = getGuildWithMember
getGuildWoM = getGuildWithoutMember


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
