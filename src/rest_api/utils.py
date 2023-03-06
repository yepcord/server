# Decorators
from functools import wraps
from json import loads as jloads
from typing import Optional

from PIL import Image
from async_timeout import timeout
from magic import from_buffer
from quart import request, current_app

from ..yepcord.classes.message import Attachment
from ..yepcord.classes.user import Session, User
from ..yepcord.ctx import Ctx, getCore, getCDNStorage
from ..yepcord.errors import Errors, InvalidDataErr
from ..yepcord.snowflake import Snowflake
from ..yepcord.utils import b64decode


def multipleDecorators(*decorators):
    def _multipleDecorators(f):
        for dec in decorators[::-1]:
            f = dec(f)
        return f
    return _multipleDecorators

def usingDB(f):
    setattr(f, "__db", True)
    return f

def allowWithoutUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        Ctx["allow_without_user"] = True
        return await f(*args, **kwargs)

    return wrapped

def getUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        try:
            if not (session := Session.from_token(request.headers.get("Authorization", ""))) \
                    or not await getCore().validSession(session):
                raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
            if not (user := await getCore().getUser(session.uid)):
                raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        except InvalidDataErr as e:
            if e.code != 401:
                raise
            if not Ctx.get("allow_without_user"):
                raise
            user = User(0)
        Ctx["user_id"] = user.id
        kwargs["user"] = user
        return await f(*args, **kwargs)
    return wrapped

def getSession(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (session := Session.from_token(request.headers.get("Authorization", ""))):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        if not await getCore().validSession(session):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        Ctx["user_id"] = session.id
        kwargs["session"] = session
        return await f(*args, **kwargs)
    return wrapped

def getChannel(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (channel := kwargs.get("channel")):
            raise InvalidDataErr(404, Errors.make(10003))
        if not (user := kwargs.get("user")):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        if not (channel := await getCore().getChannel(channel)):
            raise InvalidDataErr(404, Errors.make(10003))
        if not await getCore().getUserByChannel(channel, user.id):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        kwargs["channel"] = channel
        return await f(*args, **kwargs)
    return wrapped

async def _getMessage(user, channel, message_id):
    if not channel:
        raise InvalidDataErr(404, Errors.make(10003))
    if not user:
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
    if not message_id:
        raise InvalidDataErr(404, Errors.make(10008))
    if not (message := await getCore().getMessage(channel, message_id)):
        raise InvalidDataErr(404, Errors.make(10008))
    return message

def getMessage(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
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

def getGuild(with_member):
    def _getGuild(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            if not (guild := int(kwargs.get("guild"))):
                raise InvalidDataErr(404, Errors.make(10004))
            if not (user := kwargs.get("user")):
                raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
            if not (guild := await getCore().getGuild(guild)):
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
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (role := kwargs.get("role")) or not (guild := kwargs.get("guild")):
            raise InvalidDataErr(404, Errors.make(10011))
        if not (role := await getCore().getRole(role)):
            raise InvalidDataErr(404, Errors.make(10011))
        if role.guild_id != guild.id:
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
            if template.guild_id != guild.id:
                raise ValueError
        except ValueError:
            raise InvalidDataErr(404, Errors.make(10057))
        kwargs["template"] = template
        return await f(*args, **kwargs)

    return wrapped


getGuildWithMember = getGuild(with_member=True)
getGuildWithoutMember = getGuild(with_member=False)
getGuildWM = getGuildWithMember
getGuildWoM = getGuildWithoutMember


# Idk


async def processMessageData(message_id: int, data: Optional[dict], channel_id: int) -> dict:
    if data is None:  # Multipart request
        if request.content_length > 1024 * 1024 * 100:
            raise InvalidDataErr(400, Errors.make(50006))  # TODO: replace with correct error
        async with timeout(current_app.config["BODY_TIMEOUT"]):
            files = list((await request.files).values())
            data = await request.form
            data = jloads(data["payload_json"])
            if len(files) > 10:
                raise InvalidDataErr(400, Errors.make(50013, {
                    "files": {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."}}))
            for idx, file in enumerate(files):
                att = {"filename": None}
                if idx + 1 <= len(data["attachments"]):
                    att = data["attachments"][idx]
                name = att.get("filename") or file.filename or "unknown"
                get_content = getattr(file, "getvalue", file.read)
                content = get_content()
                att = Attachment(Snowflake.makeId(), channel_id, message_id, name, len(content), {})
                cot = file.content_type.strip() if file.content_type else from_buffer(content[:1024], mime=True)
                att.set(content_type=cot)
                if cot.startswith("image/"):
                    img = Image.open(file)
                    att.set(metadata={"height": img.height, "width": img.width})
                    img.close()
                await getCDNStorage().uploadAttachment(content, att)
                att.uploaded = True
                await getCore().putAttachment(att)
    if not data.get("content") and not data.get("embeds") and not data.get("attachments") and not data.get("sticker_ids"):
        raise InvalidDataErr(400, Errors.make(50006))
    return data


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