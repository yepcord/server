from base64 import b64encode as _b64encode, b64decode as _b64decode
from functools import wraps
from json import dumps as jdumps, loads as jloads
from random import choice
from time import time

from PIL import Image
from async_timeout import timeout
from emoji import is_emoji
from magic import from_buffer
from quart import Quart, request
from quart.globals import request_ctx

from ..classes.channel import Channel, PermissionOverwrite
from ..classes.guild import Emoji, GuildId, Invite, Guild, Role, AuditLogEntry
from ..classes.message import Message, Attachment, Reaction, SearchFilter
from ..classes.user import Session, UserSettings, UserData, UserNote, UserFlags, User, GuildMember, UserId
from ..config import Config
from ..core import Core, CDN
from ..ctx import Ctx
from ..enums import ChannelType, MessageType, UserFlags as UserFlagsE, RelationshipType, GuildPermissions, \
    AuditLogEntryType
from ..errors import InvalidDataErr, MfaRequiredErr, YDataError, EmbedErr, Errors
from ..geoip import getLanguageCode
from ..proto import PreloadedUserSettings, FrecencyUserSettings
from ..responses import userSettingsResponse, userdataResponse, userConsentResponse, userProfileResponse, \
    channelInfoResponse
from ..snowflake import Snowflake
from ..storage import FileStorage, S3Storage, FTPStorage
from ..utils import b64decode, b64encode, c_json, getImage, validImage, MFA, execute_after, LOCALES


class YEPcord(Quart):
    async def dispatch_request(self, request_context=None):
        request_ = (request_context or request_ctx).request
        if request_.routing_exception is not None:
            self.raise_routing_exception(request_)

        if request_.method == "OPTIONS" and request_.url_rule.provide_automatic_options:
            return await self.make_default_options_response()

        handler = self.view_functions[request_.url_rule.endpoint]
        Ctx.set("CORE", core)
        if getattr(handler, "__db", None):
            async with core.db() as db:
                db.dontCloseOnAExit()
                Ctx["DB"] = db
                result = await self.ensure_async(handler)(**request_.view_args)
                await db.close()
                return result
        else:
            return await self.ensure_async(handler)(**request_.view_args)


app = YEPcord("YEPcord-api")
core = Core(b64decode(Config("KEY")))
storage = Config("STORAGE_TYPE")
if storage == "local" or storage is None:
    storage = FileStorage(Config("STORAGE_PATH", "files/"))
elif storage.lower() == "s3":
    a = (Config("S3_ENDPOINT"), Config("S3_KEYID"), Config("S3_ACCESSKEY"), Config("S3_BUCKET"))
    if None in a:
        raise Exception("You must set 'S3_ENDPOINT', 'S3_KEYID', 'S3_ACCESSKEY', 'S3_BUCKET' variables for using s3 storage type.")
    storage = S3Storage(*a)
elif storage.lower() == "ftp":
    a = (Config("FTP_HOST"), Config("FTP_USER"), Config("FTP_PASSWORD"), int(Config("FTP_PORT", 21)))
    if None in a:
        raise Exception("You must set 'FTP_HOST', 'FTP_USER', 'FTP_PASSWORD' variables for using ftp storage type.")
    storage = FTPStorage(*a)
cdn = CDN(storage, core)

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
    await core.initMCL()


@app.errorhandler(YDataError)
async def ydataerror_handler(e):
    if isinstance(e, EmbedErr):
        return c_json(e.error, 400)
    elif isinstance(e, InvalidDataErr):
        return c_json(e.error, e.code)
    elif isinstance(e, MfaRequiredErr):
        ticket = b64encode(jdumps([e.uid, "login"]))
        ticket += f".{e.sid}.{e.sig}"
        return c_json({"token": None, "sms": False, "mfa": True, "ticket": ticket})


@app.after_request
async def set_cors_headers(response):
    response.headers['Server'] = "YEPcord"
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Access-Control-Allow-Headers'] = "*"
    response.headers['Access-Control-Allow-Methods'] = "*"
    response.headers['Content-Security-Policy'] = "connect-src *;"
    return response

# Decorators


def multipleDecorators(*decorators):
    def _multipleDecorators(f):
        for dec in decorators[::-1]:
            f = dec(f)
        return f
    return _multipleDecorators

def usingDB(f):
    setattr(f, "__db", True)
    return f

def getUser(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (session := Session.from_token(request.headers.get("Authorization", ""))) \
                or not await core.validSession(session):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        if not (user := await core.getUser(session.uid)):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        Ctx["user_id"] = user.id
        kwargs["user"] = user
        return await f(*args, **kwargs)
    return wrapped

def getSession(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (session := Session.from_token(request.headers.get("Authorization", ""))):
            raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
        if not await core.validSession(session):
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
        if not (channel := await core.getChannel(channel)):
            raise InvalidDataErr(404, Errors.make(10003))
        if not await core.getUserByChannel(channel, user.id):
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
    if not (message := await core.getMessage(channel, message_id)):
        raise InvalidDataErr(404, Errors.make(10008))
    return message

def getMessage(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if isinstance((message := await _getMessage(kwargs.get("user"), kwargs.get("channel"), kwargs.get("message"))), tuple):
            return message
        kwargs["message"] = message
        return await f(*args, **kwargs)
    return wrapped

def getInvite(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (invite := kwargs.get("invite")):
            raise InvalidDataErr(404, Errors.make(10006))
        try:
            invite_id = int.from_bytes(b64decode(invite), "big")
            if not (inv := await core.getInvite(invite_id)):
                raise ValueError
            invite = inv
        except ValueError:
            if not (invite := await core.getVanityCodeInvite(invite)):
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
            if not (guild := await core.getGuild(guild)):
                raise InvalidDataErr(404, Errors.make(10004))
            if not (member := await core.getGuildMember(guild, user.id)):
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
        if not (role := await core.getRole(role)):
            raise InvalidDataErr(404, Errors.make(10011))
        if role.guild_id != guild.id:
            raise InvalidDataErr(404, Errors.make(10011))
        kwargs["role"] = role
        return await f(*args, **kwargs)
    return wrapped

getGuildWithMember = getGuild(with_member=True)
getGuildWithoutMember = getGuild(with_member=False)
getGuildWM = getGuildWithMember
getGuildWoM = getGuildWithoutMember

# Auth


@app.post("/api/v9/auth/register")
@usingDB
async def api_auth_register():
    data = await request.get_json()
    loc = getLanguageCode(request.remote_addr, request.accept_languages.best_match(LOCALES, "en-US"))
    sess = await core.register(Snowflake.makeId(), data["username"], data.get("email"), data["password"], data["date_of_birth"], loc)
    return c_json({"token": sess.token})


@app.post("/api/v9/auth/login")
@usingDB
async def api_auth_login():
    data = await request.get_json()
    sess = await core.login(data["login"], data["password"])
    user = await core.getUser(sess.uid)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@app.post("/api/v9/auth/mfa/totp")
@usingDB
async def api_auth_mfa_totp(): # TODO: test
    data = await request.get_json()
    if not (ticket := data.get("ticket")):
        raise InvalidDataErr(400, Errors.make(60006))
    if not (code := data.get("code")):
        raise InvalidDataErr(400, Errors.make(60008))
    if not (mfa := await core.getMfaFromTicket(ticket)):
        raise InvalidDataErr(400, Errors.make(60006))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, Errors.make(60008))
    sess = await core.createSession(mfa.uid)
    user = await core.getUser(sess.uid)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@app.post("/api/v9/auth/logout")
@multipleDecorators(usingDB, getSession)
async def api_auth_logout(session: Session):
    await core.logoutUser(session)
    return "", 204


@app.post("/api/v9/auth/verify/view-backup-codes-challenge")
@multipleDecorators(usingDB, getUser)
async def api_auth_verify_viewbackupcodeschallenge(user: User):
    data = await request.get_json()
    if not (password := data.get("password")):
        raise InvalidDataErr(400, Errors.make(50018))
    if not await core.checkUserPassword(user, password):
        raise InvalidDataErr(400, Errors.make(50018))
    nonce = await core.generateUserMfaNonce(user)
    await core.sendMfaChallengeEmail(user, nonce[0])
    return c_json({"nonce": nonce[0], "regenerate_nonce": nonce[1]})


@app.post("/api/v9/auth/verify/resend")
@multipleDecorators(usingDB, getUser)
async def api_auth_verify_resend(user: User):
    if not user.verified:
        await core.sendVerificationEmail(user)
    return "", 204


@app.post("/api/v9/auth/verify")
@usingDB
async def api_auth_verify():
    data = await request.get_json()
    if not data.get("token"):
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    try:
        email = jloads(b64decode(data["token"].split(".")[0]).decode("utf8"))["email"]
    except:
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    user = await core.getUserByEmail(email)
    await core.verifyEmail(user, data["token"])
    await core.sendUserUpdateEvent(user.id)
    return c_json({"token": (await core.createSession(user.id)).token, "user_id": str(user.id)})


# Users (@me)


@app.get("/api/v9/users/@me")
@multipleDecorators(usingDB, getUser)
async def api_users_me_get(user: User):
    return c_json(await userdataResponse(user))

@app.patch("/api/v9/users/@me")
@multipleDecorators(usingDB, getUser)
async def api_users_me_patch(user: User):
    data = await user.data
    _settings = await request.get_json()
    d = "discriminator" in _settings and _settings.get("discriminator") != data.discriminator
    u = "username" in _settings and _settings.get("username") != data.username
    if d or u:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        if u:
            await core.changeUserName(user, str(_settings["username"]))
            del _settings["username"]
        if d:
            if not await core.changeUserDiscriminator(user, int(_settings["discriminator"])):
                if u:
                    return c_json(await userdataResponse(user))
                raise InvalidDataErr(400, Errors.make(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This discriminator already used by someone. Please enter something else."}}))
            del _settings["discriminator"]
    if "new_password" in _settings:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await core.changeUserPassword(user, _settings["new_password"])
        del _settings["new_password"]
    if "email" in _settings:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await core.changeUserEmail(user, _settings["email"])
        await core.sendVerificationEmail(user)
        del _settings["email"]
    if "password" in _settings: del _settings["password"]

    settings = {}
    for k,v in _settings.items():
        k = k.lower()
        if k == "avatar":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await cdn.setAvatarFromBytesIO(user.id, img)):
                continue
        elif k == "banner": # TODO: remove
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await cdn.setBannerFromBytesIO(user.id, img)):
                continue
        settings[k] = v
    if settings:
        if "uid" in settings: del settings["uid"]
        await core.setUserdata(UserData(user.id, **settings))
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userdataResponse(user))

@app.patch("/api/v9/users/@me/profile")
@multipleDecorators(usingDB, getUser)
async def api_users_me_profile_patch(user: User):
    _settings = await request.get_json()
    settings = {}
    for k, v in _settings.items():
        if k == "banner":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await cdn.setBannerFromBytesIO(user.id, img)):
                continue
        settings[k] = v
    if settings:
        if "uid" in settings: del settings["uid"]
        await core.setUserdata(UserData(user.id, **settings))
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userdataResponse(user))

@app.get("/api/v9/users/@me/consent")
@multipleDecorators(usingDB, getUser)
async def api_users_me_consent_get(user: User):
    return c_json(await userConsentResponse(user))

@app.post("/api/v9/users/@me/consent")
@multipleDecorators(usingDB, getUser)
async def api_users_me_consent_set(user: User):
    data = await request.get_json()
    if data["grant"] or data["revoke"]:
        settings = {}
        for g in data.get("grant", []):
            settings[g] = True
        for r in data.get("revoke", []):
            settings[r] = False
        if "uid" in settings: del settings["uid"]
        s = UserSettings(user.id, **settings)
        await core.setSettings(s)
    return c_json(await userConsentResponse(user))


@app.get("/api/v9/users/@me/settings")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settings_get(user: User):
    return c_json(await userSettingsResponse(user))


@app.patch("/api/v9/users/@me/settings")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settings_patch(user: User):
    settings = await request.get_json()
    if "uid" in settings: del settings["uid"]
    s = UserSettings(user.id, **settings)
    await core.setSettings(s)
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userSettingsResponse(user))


@app.get("/api/v9/users/@me/settings-proto/1")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_1_get(user: User):
    proto = await user.settings_proto
    return c_json({"settings": _b64encode(proto.SerializeToString()).decode("utf8")})


@app.patch("/api/v9/users/@me/settings-proto/1")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_1_patch(user: User): # TODO
    data = await request.get_json()
    if not data.get("settings"):
        raise InvalidDataErr(400, Errors.make(50013, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto = PreloadedUserSettings()
        proto.ParseFromString(_b64decode(data.get("settings").encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, Errors.make(50104))
    settings_old = await user.settings
    settings = UserSettings(user.id)
    settings.from_proto(proto)
    await core.setSettingsDiff(settings_old, settings)
    user._uSettings = None
    settings = await user.settings
    proto = _b64encode(settings.to_proto().SerializeToString()).decode("utf8")
    await core.sendSettingsProtoUpdateEvent(user.id, proto, 1)
    return c_json({"settings": proto})


@app.get("/api/v9/users/@me/settings-proto/2")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_2_get(user: User):
    proto = await user.frecency_settings_proto
    return c_json({"settings": _b64encode(proto).decode("utf8")})


@app.patch("/api/v9/users/@me/settings-proto/2")
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_2_patch(user: User):
    data = await request.get_json()
    if not data.get("settings"):
        raise InvalidDataErr(400, Errors.make(50013, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto_new = FrecencyUserSettings()
        proto_new.ParseFromString(_b64decode(data.get("settings").encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, Errors.make(50104))
    proto = FrecencyUserSettings()
    proto.ParseFromString(await user.frecency_settings_proto)
    proto.MergeFrom(proto_new)
    proto = proto.SerializeToString()
    proto = _b64encode(proto).decode("utf8")
    await core.setFrecencySettings(user.id, proto)
    await core.sendSettingsProtoUpdateEvent(user.id, proto, 2)
    return c_json({"settings": proto})


@app.get("/api/v9/users/@me/connections")
@multipleDecorators(usingDB, getUser)
async def api_users_me_connections(user: User): # TODO
    return c_json("[]") # friend_sync: bool, id: str(int), integrations: list, name: str, revoked: bool, show_activity: bool, two_way_link: bool, type: str, verified: bool, visibility: int


@app.post("/api/v9/users/@me/relationships")
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_post(user: User):
    udata = await request.get_json()
    udata["discriminator"] = int(udata["discriminator"])
    if not (rUser := await core.getUserByUsername(**udata)):
        raise InvalidDataErr(400, Errors.make(80004))
    if rUser == user:
        raise InvalidDataErr(400, Errors.make(80007))
    await core.checkRelationShipAvailable(rUser, user)
    await core.reqRelationship(rUser, user)
    return "", 204


@app.get("/api/v9/users/@me/relationships")
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_get(user: User):
    return c_json(await core.getRelationships(user, with_data=True))


@app.get("/api/v9/users/@me/notes/<int:target_uid>")
@multipleDecorators(usingDB, getUser)
async def api_users_me_notes_get(user: User, target_uid: int):
    if not (note := await core.getUserNote(user.id, target_uid)):
        raise InvalidDataErr(404, Errors.make(10013))
    return c_json(note.toJSON())


@app.put("/api/v9/users/@me/notes/<int:target_uid>")
@multipleDecorators(usingDB, getUser)
async def api_users_me_notes_put(user: User, target_uid: int):
    data = await request.get_json()
    if note := data.get("note"):
        await core.putUserNote(UserNote(user.id, target_uid, note))
    return "", 204


@app.post("/api/v9/users/@me/mfa/totp/enable")
@multipleDecorators(usingDB, getSession)
async def api_users_me_mfa_totp_enable(session: Session):
    data = await request.get_json()
    user = await core.getUser(session.uid)
    if not (password := data.get("password")) or not await core.checkUserPassword(user, password):
        raise InvalidDataErr(400, Errors.make(50018))
    if not (secret := data.get("secret")):
        raise InvalidDataErr(400, Errors.make(60005))
    mfa = MFA(secret, session.id)
    if not mfa.valid:
        raise InvalidDataErr(400, Errors.make(60005))
    if not (code := data.get("code")):
        raise InvalidDataErr(400, Errors.make(60008))
    if mfa.getCode() != code:
        raise InvalidDataErr(400, Errors.make(60008))
    await core.setSettings(UserSettings(session.id, mfa=secret))
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await core.setBackupCodes(session, codes)
    await execute_after(core.sendUserUpdateEvent(session.id), 3)
    codes = [{"user_id": str(session.id), "code": code, "consumed": False} for code in codes]
    await core.logoutUser(session)
    session = await core.createSession(session.id)
    return c_json({"token": session.token, "backup_codes": codes})


@app.post("/api/v9/users/@me/mfa/totp/disable")
@multipleDecorators(usingDB, getSession)
async def api_users_me_mfa_totp_disable(session: Session):
    data = await request.get_json()
    if not (code := data.get("code")):
        raise InvalidDataErr(400, Errors.make(60008))
    user = await core.getUser(session.id)
    if not (mfa := await core.getMfa(user)):
        raise InvalidDataErr(400, Errors.make(50018))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, Errors.make(60008))
    await core.setSettings(UserSettings(session.id, mfa=None))
    await core.clearBackupCodes(session)
    await core.sendUserUpdateEvent(session.id)
    await core.logoutUser(session)
    session = await core.createSession(session.id)
    return c_json({"token": session.token})


@app.post("/api/v9/users/@me/mfa/codes-verification")
@multipleDecorators(usingDB, getUser)
async def api_users_me_mfa_codesverification(user: User):
    data = await request.get_json()
    if not (nonce := data.get("nonce")):
        raise InvalidDataErr(400, Errors.make(60011))
    if not (key := data.get("key")):
        raise InvalidDataErr(400, Errors.make(50035, {"key": {"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}}))
    reg = data.get("regenerate", False)
    await core.verifyUserMfaNonce(user, nonce, reg)
    if await core.mfaNonceToCode(user, nonce) != key:
        raise InvalidDataErr(400, Errors.make(60011))
    if reg:
        codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
        await core.setBackupCodes(user, codes)
        codes = [{"user_id": str(user.id), "code": code, "consumed": False} for code in codes]
    else:
        _codes = await core.getBackupCodes(user)
        codes = []
        for code, used in _codes:
            codes.append({"user_id": str(user.id), "code": code, "consumed": bool(used)})
    return c_json({"backup_codes": codes})


@app.put("/api/v9/users/@me/relationships/<int:uid>")
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_put(uid: int, user: User):
    data = await request.get_json()
    if not data or "type" not in data:
        await core.accRelationship(user, uid)
    elif data["type"] == 2:
        await core.blockUser(user, uid)
    return "", 204


@app.delete("/api/v9/users/@me/relationships/<int:uid>")
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_delete(uid: int, user: User):
    await core.delRelationship(user, uid)
    return "", 204


@app.get("/api/v9/users/@me/harvest")
@multipleDecorators(usingDB, getUser)
async def api_users_me_harvest(user: User):
    return "", 204



@app.delete("/api/v9/users/@me/guilds/<int:guild>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_users_me_guilds_guild_delete(user: User, guild: Guild, member: GuildMember):
    if member.id == guild.owner_id:
        raise InvalidDataErr(400, Errors.make(50055))
    await core.deleteGuildMember(member)
    await core.sendGuildMemberRemoveEvent(guild, await member.user)
    await core.sendGuildDeleteEvent(guild, member)
    return "", 204


# Connections


#@app.route("/api/v9/connections/<string:connection>/authorize", methods=["GET"]) # TODO: implement UserConnection
#@multipleDecorators(usingDB, getUser)
#async def api_connections_connection_authorize(user, connection):
#    url = ""
#    kwargs = {}
#    if connection == "github":
#        CLIENT_ID = ""
#        state = urandom(16).hex()
#        kwargs["state"] = state
#        url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=https%3A%2F%2F127.0.0.1:8080%2Fapi%2Fconnections%2Fgithub%2Fcallback&scope=read%3Auser&state={state}"
#    await core.putUserConnection(UserConnection(user, connection, **kwargs))
#    return c_json({"url": url})
#
#
#@app.route("/api/v9/connections/<string:connection>/callback", methods=["POST"])
#@multipleDecorators(usingDB, getUser)
#async def api_connections_connection_callback(user, connection):
#    data = await request.get_json()
#    if connection == "github":
#        ...
#    return ...

# Users


@app.get("/api/v9/users/<string:target_user>/profile")
@multipleDecorators(usingDB, getUser)
async def api_users_user_profile(user: User, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = await core.getUserProfile(target_user, user)
    with_mutual_guilds = request.args.get("with_mutual_guilds", "false").lower() == "true"
    mutual_friends_count = request.args.get("mutual_friends_count", "false").lower() == "true"
    guild_id = int(request.args.get("guild_id", 0))
    return c_json(await userProfileResponse(target_user, user, with_mutual_guilds, mutual_friends_count, guild_id))


# Channels


@app.get("/api/v9/channels/<channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel(user: User, channel: Channel):
    return c_json(await channelInfoResponse(channel, user))


@app.patch("/api/v9/channels/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_patch(user: User, channel: Channel):
    data = dict(await request.get_json())
    if "icon" in data:
        if not (img := getImage(data["icon"])) or not validImage(img):
            del data["icon"]
        else:
            if not (v := await cdn.setChannelIconFromBytesIO(channel.id, img)):
                del data["icon"]
            else:
                data["icon"] = v
    if "owner" in data:
        if channel.owner_id != user.id:
            raise InvalidDataErr(403, Errors.make(50013))
        data["owner_id"] = int(data["owner"])
        del data["owner"]
    if "id" in data: del data["id"]
    if "type" in data: del data["type"]
    if "rate_limit_per_user" in data: del data["rate_limit_per_user"] # TODO
    if "default_thread_rate_limit_per_user" in data: del data["default_thread_rate_limit_per_user"] # TODO
    if "default_reaction_emoji" in data: del data["default_reaction_emoji"] # TODO
    if "guild_id" in data: del data["guild_id"]
    nChannel = channel.copy(**data)
    await core.updateChannelDiff(channel, nChannel)
    if channel.type == ChannelType.GROUP_DM:
        await core.sendDMChannelUpdateEvent(nChannel)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)
        await core.sendChannelUpdateEvent(nChannel)

        changes = []
        for k, v in channel.getDiff(nChannel).items():
            changes.append({"key": k, "old_value": channel.get(k), "new_value": nChannel.get(k)})
        entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id, AuditLogEntryType.CHANNEL_UPDATE,
                              changes=changes)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)
    diff = channel.getDiff(nChannel)
    if "name" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_NAME_CHANGE, content=nChannel.name)
        await core.sendMessage(message)
    if "icon" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_ICON_CHANGE, content="")
        await core.sendMessage(message)
    channel.set(**data)
    return c_json(await channelInfoResponse(channel, user))


@app.delete("/api/v9/channels/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_delete(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        return "", 204 # TODO
    elif channel.type == ChannelType.GROUP_DM:
        msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": user.id})
        await core.sendMessage(msg)
        await core.removeUserFromGroupDM(channel, user.id)
        await core.sendDMRepicientRemoveEvent(channel.recipients, channel.id, user.id)
        await core.sendDMChannelDeleteEvent(channel, users=[user.id])
        if len(channel.recipients) == 1:
            await core.deleteChannel(channel)
        elif channel.owner_id == user.id:
            channel.recipients.remove(user.id)
            nChannel = channel.copy()
            nChannel.owner_id = choice(channel.recipients)
            await core.updateChannelDiff(channel, nChannel)
            await core.sendDMChannelUpdateEvent(channel)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        changes = [
            {"old_value": channel.name, "key": "name"},
            {"old_value": channel.type, "key": "type"},
            {"old_value": [await overwrite.json for overwrite in await core.getPermissionOverwrites(channel)], "key": "permission_overwrites"},
            {"old_value": channel.nsfw, "key": "nsfw"},
            {"old_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"old_value": channel.flags, "key": "flags"}
        ]
        entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id, AuditLogEntryType.CHANNEL_DELETE,
                              changes=changes)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)

        await core.deleteChannel(channel)
        await core.sendGuildChannelDeleteEvent(channel)
        return await channelInfoResponse(channel)
    return "", 204


@app.get("/api/v9/channels/<int:channel>/messages")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_get(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    args = request.args
    messages = await channel.messages(args.get("limit", 50), int(args.get("before", 0)), int(args.get("after", 0)))
    messages = [await m.json for m in messages]
    return c_json(messages)


@app.post("/api/v9/channels/<int:channel>/messages")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_post(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        oth = channel.recipients.copy()
        oth.remove(user.id)
        oth = oth[0]
        rel = await core.getRelationship(user.id, oth)
        if not rel:
            ... # TODO: Check
        if rel and rel.type == RelationshipType.BLOCK:
            raise InvalidDataErr(403, Errors.make(50007))
    elif channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    message_id = Snowflake.makeId()
    data = await request.get_json()
    if data is None: # Multipart request
        if request.content_length > 1024*1024*100:
            raise InvalidDataErr(400, Errors.make(50006)) # TODO: replace with correct error
        async with timeout(app.config["BODY_TIMEOUT"]):
            files = list((await request.files).values())
            data = await request.form
            data = jloads(data["payload_json"])
            if len(files) > 10:
                raise InvalidDataErr(400, Errors.make(50013, {"files": {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."}}))
            for idx, file in enumerate(files):
                att = {"filename": None}
                if idx+1 <= len(data["attachments"]):
                    att = data["attachments"][idx]
                name = att.get("filename") or file.filename or "unknown"
                content = file.getvalue()
                att = Attachment(Snowflake.makeId(), channel.id, message_id, name, len(content), {})
                cot = file.content_type.strip() if file.content_type else from_buffer(content[:1024], mime=True)
                att.set(content_type=cot)
                if cot.startswith("image/"):
                    img = Image.open(file)
                    att.set(metadata={"height": img.height, "width": img.width})
                    img.close()
                await cdn.uploadAttachment(content, att)
                att.uploaded = True
                await core.putAttachment(att)
    if not data.get("content") and not data.get("embeds") and not data.get("attachments"):
        raise InvalidDataErr(400, Errors.make(50006))
    if "id" in data: del data["id"]
    if "channel_id" in data: del data["channel_id"]
    if "author" in data: del data["author"]
    if "attachments" in data: del data["attachments"]
    message = Message(id=message_id, channel_id=channel.id, author=user.id, **data, **({} if not channel.guild_id else {"guild_id": channel.guild_id}))
    await message.check()
    message = await core.sendMessage(message)
    if await core.delReadStateIfExists(user.id, channel.id):
        await core.sendMessageAck(user.id, channel.id, message.id)
    return c_json(await message.json)


@app.delete("/api/v9/channels/<int:channel>/messages/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_delete(user: User, channel: Channel, message: Message):
    if message.author != user.id:
        if channel.get("guild_id"):
            member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
            await member.checkPermission(GuildPermissions.MANAGE_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                         GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
        else:
            raise InvalidDataErr(403, Errors.make(50003))
    await core.deleteMessage(message)
    return "", 204


@app.patch("/api/v9/channels/<int:channel>/messages/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_patch(user: User, channel: Channel, message: Message):
    data = await request.get_json()
    if message.author != user.id:
        raise InvalidDataErr(403, Errors.make(50005))
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    before = message
    if "id" in data: del data["id"]
    if "channel_id" in data: del data["channel_id"]
    if "author" in data: del data["author"]
    if "edit_timestamp" in data: del data["edit_timestamp"]
    after = before.copy().set(edit_timestamp=int(time()), **data)
    after = await core.editMessage(before, after)
    return c_json(await after.json)

@app.post("/api/v9/channels/<int:channel>/messages/<int:message>/ack")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_message_ack(user: User, channel: Channel, message: Message):
    data = await request.get_json()
    if data.get("manual") and (ct := int(data.get("mention_count"))):
        if isinstance((message := await _getMessage(user, channel, message)), tuple):
            return message
        await core.setReadState(user.id, channel.id, ct, message.id)
        await core.sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        await core.delReadStateIfExists(user.id, channel.id)
        await core.sendMessageAck(user.id, channel.id, message.id)
    return c_json({"token": None})


@app.delete("/api/v9/channels/<int:channel>/messages/ack")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_ack_delete(user: User, channel: Channel):
    await core.deleteMessagesAck(channel, user)
    return "", 204


@app.post("/api/v9/channels/<int:channel>/typing")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_typing(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    await core.sendTypingEvent(user, channel)
    return "", 204

"""
@app.post("/api/v9/channels/<int:channel>/attachments")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_attachments_post(user, channel):
    data = await request.get_json()
    if not (files := data.get("files")):
        raise InvalidDataErr(400, Errors.make(50013, {"files": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if len(files) > 10:
        raise InvalidDataErr(400, Errors.make(50013, {"files": {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."}}))
    attachments = []
    for idx, file in enumerate(files):
        if not (filename := file.get("filename")) or not (filename := filename.replace("\\", "/").split("/")[-1]):
            raise InvalidDataErr(400, Errors.make(50013, {f"files.{idx}.filename": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if not (size := file.get("file_size")):
            try:
                size = int(size)
            except ValueError:
                raise InvalidDataErr(400, Errors.make(50013, {f"files.{idx}.file_size": {"code": "NUMBER_TYPE_COERCE", "message": f"The value '{size}' is not an int."}}))
            raise InvalidDataErr(400, Errors.make(50013, {f"files.{idx}.file_size": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if not (fid := file.get("id")):
            raise InvalidDataErr(400, Errors.make(50013, {f"files.{idx}.id": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        att = Attachment(Snowflake.makeId(), channel.id, filename, size, {})
        await core.putAttachment(att)
        attachments.append({
            "id": int(fid),
            "upload_filename": f"{att.uuid}/{att.filename}",
            "upload_url": f"https://{Config('CDN_HOST')}/upload/attachment/{att.uuid}/{att.filename}",
        })
    return {"attachments": attachments}
"""

@app.put("/api/v9/channels/<int:channel>/recipients/<int:nUser>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_repicients_recipient_put(user: User, channel: Channel, nUser: int):
    if channel.type not in (ChannelType.DM, ChannelType.GROUP_DM):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.type == ChannelType.DM:
        rep = channel.recipients
        rep.remove(user.id)
        rep.append(nUser)
        ch = await core.createDMGroupChannel(user, rep)
        await core.sendDMChannelCreateEvent(ch)
    elif channel.type == ChannelType.GROUP_DM:
        if nUser not in channel.recipients and len(channel.recipients) < 10:
            msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": nUser})
            await core.sendMessage(msg)
            await core.addUserToGroupDM(channel, nUser)
            await core.sendDMRepicientAddEvent(channel.recipients, channel.id, nUser)
            await core.sendDMChannelCreateEvent(channel, users=[nUser])
    return "", 204


@app.delete("/api/v9/channels/<int:channel>/recipients/<int:nUser>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_repicients_recipient_delete(user: User, channel: Channel, nUser: int):
    if channel.type not in (ChannelType.GROUP_DM,):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.owner_id != user.id:
        raise InvalidDataErr(403, Errors.make(50013))
    if nUser in channel.recipients:
        msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": nUser})
        await core.sendMessage(msg)
        await core.removeUserFromGroupDM(channel, nUser)
        await core.sendDMRepicientRemoveEvent(channel.recipients, channel.id, nUser)
        await core.sendDMChannelDeleteEvent(channel, users=[nUser])
    return "", 204


@app.put("/api/v9/channels/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_pins_message_put(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not message.pinned:
        await core.pinMessage(message)
        msg = Message(
            Snowflake.makeId(),
            author=user.id,
            channel_id=channel.id,
            type=MessageType.CHANNEL_PINNED_MESSAGE,
            content="",
            message_reference=message.id,
            **({} if not channel.guild_id else {"guild_id": channel.guild_id})
        )
        await core.sendMessage(msg)
    return "", 204


@app.delete("/api/v9/channels/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_pins_message_delete(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if message.pinned:
        await core.unpinMessage(message)
    return "", 204


@app.get("/api/v9/channels/<int:channel>/pins")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_pins_get(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    messages = await core.getPinnedMessages(channel.id)
    messages = [await message.json for message in messages]
    return messages


@app.put("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_put(user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await core.addReaction(Reaction(message.id, user.id, **r), channel)
    return "", 204


@app.delete("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_delete(user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await core.removeReaction(Reaction(message.id, user.id, **r), channel)
    return "", 204


@app.get("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_reaction_get(user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    limit = int(request.args.get("limit", 3))
    if limit > 10:
        limit = 10
    return await core.getReactedUsers(Reaction(message.id, 0, **r), limit)


@app.get("/api/v9/channels/<int:channel>/messages/search")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_search(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, GuildPermissions.VIEW_CHANNEL, channel=channel)
    messages, total = await core.searchMessages(SearchFilter(**request.args))
    Ctx["search"] = True
    messages = [[await message.json] for message in messages]
    for message in messages:
        message[0]["hit"] = True
    return c_json({"messages": messages, "total_results": total})


@app.get("/api/v9/users/@me/channels")
@multipleDecorators(usingDB, getUser)
async def api_users_me_channels_get(user: User):
    return c_json(await core.getPrivateChannels(user))


@app.post("/api/v9/users/@me/channels")
@multipleDecorators(usingDB, getUser)
async def api_users_me_channels_post(user: User):
    data = await request.get_json()
    rep = data.get("recipients", [])
    rep = [int(r) for r in rep]
    if len(rep) == 1:
        if int(rep[0]) == user.id:
            raise InvalidDataErr(400, Errors.make(50007))
        ch = await core.getDMChannelOrCreate(user.id, rep[0])
    elif len(rep) == 0:
        ch = await core.createDMGroupChannel(user, [])
    else:
        if user.id in rep:
            rep.remove(user.id)
        if len(rep) == 0:
            raise InvalidDataErr(400, Errors.make(50007))
        elif len(rep) == 1:
            ch = await core.getDMChannelOrCreate(user.id, rep[0])
        else:
            ch = await core.createDMGroupChannel(user, rep)
    await core.sendDMChannelCreateEvent(ch)
    return c_json(await channelInfoResponse(ch, user, ids=False))


# Invites


@app.post("/api/v9/channels/<int:channel>/invites")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_invites_post(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await core.getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.CREATE_INSTANT_INVITE)
    data = await request.get_json()
    max_age = data.get("max_age", 86400)
    max_uses = data.get("max_uses", 0)
    invite = await core.createInvite(channel, user, max_age=max_age, max_uses=max_uses)
    if channel.get("guild_id"):
        changes = [
            {"new_value": invite.code, "key": "code"},
            {"new_value": invite.channel_id, "key": "channel_id"},
            {"new_value": invite.inviter_id, "key": "inviter_id"},
            {"new_value": invite.uses, "key": "uses"},
            {"new_value": invite.max_uses, "key": "max_uses"},
            {"new_value": invite.max_age, "key": "max_age"},
            {"new_value": invite.temporary, "key": "temporary"}
        ]
        entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, invite.id, AuditLogEntryType.INVITE_CREATE,
                              changes=changes)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)
    return c_json(await invite.json)


@app.get("/api/v9/invites/<string:invite>")
@multipleDecorators(usingDB, getInvite)
async def api_invites_invite_get(invite: Invite):
    data = request.args
    Ctx["with_counts"] = data.get("with_counts", "false").lower == "true"
    invite = await invite.json
    for excl in ["max_age", "created_at"]: # Remove excluded fields
        if excl in invite:
            del invite[excl]
    return c_json(invite)


@app.post("/api/v9/invites/<string:invite>")
@multipleDecorators(usingDB, getUser, getInvite)
async def api_invites_invite_post(user: User, invite: Invite):
    channel = await core.getChannel(invite.channel_id)
    if channel.type == ChannelType.GROUP_DM:
        if user.id not in channel.recipients and len(channel.recipients) >= 10:
            raise InvalidDataErr(404, Errors.make(10006))
        inv = await invite.json
        for excl in ["max_age", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        inv["new_member"] = user.id not in channel.recipients
        if inv["new_member"]:
            msg = Message(id=Snowflake.makeId(), author=channel.owner_id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": user.id})
            await core.addUserToGroupDM(channel, user.id)
            await core.sendDMRepicientAddEvent(channel.recipients, channel.id, user.id)
            await core.sendMessage(msg)
        await core.sendDMChannelCreateEvent(channel, users=[user.id])
        await core.useInvite(invite)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
        inv = await invite.json
        for excl in ["max_age", "max_uses", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        if not await core.getGuildMember(GuildId(invite.guild_id), user.id):
            guild = await core.getGuild(invite.guild_id)
            if await core.getGuildBan(guild, user.id) is not None:
                raise InvalidDataErr(403, Errors.make(40007))
            inv["new_member"] = True
            await core.createGuildMember(guild, user)
            await core.sendGuildCreateEvent(guild, [user.id])
            if guild.system_channel_id:
                msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=guild.system_channel_id, content="",
                              type=MessageType.USER_JOIN, guild_id=guild.id)
                await core.sendMessage(msg)
            await core.useInvite(invite)
    return c_json(inv)


@app.delete("/api/v9/invites/<string:invite>")
@multipleDecorators(usingDB, getUser, getInvite)
async def api_invites_invite_delete(user: User, invite: Invite):
    if invite.guild_id:
        member = await core.getGuildMember(GuildId(invite.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_GUILD)
        await core.deleteInvite(invite)
        await core.sendInviteDeleteEvent(invite)

        changes = [
            {"old_value": invite.code, "key": "code"},
            {"old_value": invite.channel_id, "key": "channel_id"},
            {"old_value": invite.inviter_id, "key": "inviter_id"},
            {"old_value": invite.uses, "key": "uses"},
            {"old_value": invite.max_uses, "key": "max_uses"},
            {"old_value": invite.max_age, "key": "max_age"},
            {"old_value": invite.temporary, "key": "temporary"}
        ]
        entry = AuditLogEntry(Snowflake.makeId(), invite.guild_id, user.id, invite.id, AuditLogEntryType.INVITE_DELETE,
                              changes=changes)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)
    return c_json(await invite.json)


# Guilds


@app.post("/api/v9/guilds")
@multipleDecorators(usingDB, getUser)
async def api_guilds_post(user: User):
    data = await request.get_json()
    guild = await core.createGuild(user, data["name"])
    Ctx["with_channels"] = True
    return c_json(await guild.json)


@app.patch("/api/v9/guilds/<int:guild>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_patch(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    for j in ("id", "owner_id", "features", "max_members"):
        if j in data: del data[j]
    if "icon" in data:
        img = data["icon"]
        del data["icon"]
        if (img := getImage(img)) and validImage(img):
            if h := await cdn.setGuildIconFromBytesIO(guild.id, img):
                data["icon"] = h
    new_guild = guild.copy(**data)
    await core.updateGuildDiff(guild, new_guild)
    await core.sendGuildUpdateEvent(new_guild)

    changes = []
    for k, v in guild.getDiff(new_guild).items():
        changes.append({"key": k, "old_value": guild.get(k), "new_value": new_guild.get(k)})
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, guild.id, AuditLogEntryType.GUILD_UPDATE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return c_json(await new_guild.json)


@app.get("/api/v9/guilds/<int:guild>/templates")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_templates_get(user: User, guild: Guild):
    return c_json([])


@app.get("/api/v9/guilds/<int:guild>/emojis")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_emojis_get(user: User, guild: Guild):
    emojis = await core.getEmojis(guild.id)
    Ctx["with_user"] = True
    emojis = [await emoji.json for emoji in emojis]
    return c_json(emojis)


@app.post("/api/v9/guilds/<int:guild>/emojis")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_emojis_post(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    data = await request.get_json()
    if not data.get("image"):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not data.get("name"):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not (img := getImage(data["image"])) or not validImage(img):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    eid = Snowflake.makeId()
    if not (emd := await cdn.setEmojiFromBytesIO(eid, img)):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    emoji = Emoji(eid, data["name"], user.id, guild.id, animated=emd["animated"])
    await core.addEmoji(emoji, guild)
    emoji.fill_defaults()

    changes = [
        {"new_value": emoji.name, "key": "name"},
    ]
    entry = AuditLogEntry(Snowflake.makeId(), emoji.guild_id, user.id, emoji.id, AuditLogEntryType.EMOJI_CREATE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return c_json(await emoji.json)


@app.delete("/api/v9/guilds/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_emojis_emoji_delete(user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    emoji = await core.getEmoji(emoji)
    if not emoji:
        return "", 204
    if emoji.guild_id != guild.id:
        return "", 204
    await core.deleteEmoji(emoji, guild)

    changes = [
        {"old_value": emoji.name, "key": "name"},
    ]
    entry = AuditLogEntry(Snowflake.makeId(), emoji.guild_id, user.id, emoji.id, AuditLogEntryType.EMOJI_DELETE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return "", 204


@app.patch("/api/v9/guilds/<int:guild>/channels")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_channels_patch(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    if not (data := await request.get_json()):
        return "", 204
    for change in data:
        if not (channel := await core.getChannel(int(change["id"]))):
            continue
        del change["id"]
        if "type" in change: del change["type"]
        if "guild_id" in change: del change["guild_id"]
        nChannel = Channel(channel.id, channel.type, channel.guild_id, **change)
        await core.updateChannelDiff(channel, nChannel)
        channel.set(**change)
        await core.sendChannelUpdateEvent(channel)
    return "", 204


@app.post("/api/v9/guilds/<int:guild>/channels")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_channels_post(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data = await request.get_json()
    if not data.get("name"):
        raise InvalidDataErr(400, Errors.make(50035, {"name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if "id" in data: del data["id"]
    ctype = data.get("type", ChannelType.GUILD_TEXT)
    if "type" in data: del data["type"]
    channel = Channel(Snowflake.makeId(), ctype, guild_id=guild.id, **data)
    channel = await core.createGuildChannel(channel)
    await core.sendChannelCreateEvent(channel)

    changes = [
        {"new_value": channel.name, "key": "name"},
        {"new_value": channel.type, "key": "type"},
        {"new_value": [], "key": "permission_overwrites"},
        {"new_value": channel.nsfw, "key": "nsfw"},
        {"new_value": channel.rate_limit, "key": "rate_limit_per_user"},
        {"new_value": channel.flags, "key": "flags"}
    ]
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, channel.id, AuditLogEntryType.CHANNEL_CREATE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return await channelInfoResponse(channel)


@app.get("/api/v9/guilds/<int:guild>/invites")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_invites_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    invites = await core.getGuildInvites(guild)
    invites = [await invite.json for invite in invites]
    return c_json(invites)


@app.get("/api/v9/guilds/<int:guild>/premium/subscriptions")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_premium_subscriptions_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    boosts = [{"ended": False, "user_id": str(guild.owner_id)}]*30
    return c_json(boosts)


@app.delete("/api/v9/guilds/<int:guild>/members/<int:uid>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_members_user_delete(user: User, guild: Guild, member: GuildMember, uid: int):
    await member.checkPermission(GuildPermissions.KICK_MEMBERS)
    if target_member := await core.getGuildMember(guild, uid):
        if not await member.perm_checker.canKickOrBan(target_member):
            raise InvalidDataErr(403, Errors.make(50013))
        await core.deleteGuildMember(target_member)
        await core.sendGuildMemberRemoveEvent(guild, await target_member.user)
        await core.sendGuildDeleteEvent(guild, target_member)
        entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, target_member.id, AuditLogEntryType.MEMBER_KICK)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)
    return "", 204


@app.put("/api/v9/guilds/<int:guild>/bans/<int:uid>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_bans_user_put(user: User, guild: Guild, member: GuildMember, uid: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    if target_member := await core.getGuildMember(guild, uid):
        if not await member.perm_checker.canKickOrBan(target_member):
            raise InvalidDataErr(403, Errors.make(50013))
        if await core.getGuildBan(guild, uid) is None:
            reason = request.headers.get("x-audit-log-reason")
            await core.deleteGuildMember(target_member)
            await core.banGuildMember(target_member, reason)
            target_user = await target_member.user
            await core.sendGuildMemberRemoveEvent(guild, target_user)
            await core.sendGuildDeleteEvent(guild, target_member)
            await core.sendGuildBanAddEvent(guild, target_user)
            data = await request.get_json()
            if (delete_message_seconds := data.get("delete_message_seconds", 0)) > 0:
                if delete_message_seconds > 604800: delete_message_seconds = 604800 # 7 days
                after = Snowflake.fromTimestamp(int(time() - delete_message_seconds))
                deleted_messages = await core.bulkDeleteGuildMessagesFromBanned(guild, uid, after)
                for channel, messages in deleted_messages.items():
                    if len(messages) > 1:
                        await core.sendMessageBulkDeleteEvent(guild.id, channel, messages)
                    elif len(messages) == 1:
                        await core.sendMessageDeleteEvent(Message(messages[0], channel, uid))

            entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, target_member.id,
                                  AuditLogEntryType.MEMBER_BAN_ADD, reason)
            await core.putAuditLogEntry(entry)
            await core.sendAuditLogEntryCreateEvent(entry)
    return "", 204


@app.get("/api/v9/guilds/<int:guild>/bans")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_bans_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    bans = [await ban.json for ban in await core.getGuildBans(guild)]
    return c_json(bans)


@app.delete("/api/v9/guilds/<int:guild>/bans/<int:user_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_bans_user_delete(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    await core.removeGuildBan(guild, user_id)
    await core.sendGuildBanRemoveEvent(guild, user_id)

    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, user_id, AuditLogEntryType.MEMBER_BAN_REMOVE)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)
    return "", 204


@app.get("/api/v9/guilds/<int:guild>/integrations")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_integrations_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    return c_json([]) # TODO


@app.post("/api/v9/guilds/<int:guild>/roles")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_roles_post(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    data = await request.get_json()
    if "id" in data: del data["id"]
    if "guild_id" in data: del data["guild_id"]
    role = Role(Snowflake.makeId(), guild.id, **data)
    await core.createGuildRole(role)
    await core.sendGuildRoleCreateEvent(role)

    changes = [
        {"new_value": role.name, "key": "name"},
        {"new_value": role.permissions, "key": "permissions"},
        {"new_value": role.color, "key": "color"},
        {"new_value": role.hoist, "key": "hoist"},
        {"new_value": role.mentionable, "key": "mentionable"}
    ]
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, role.id, AuditLogEntryType.ROLE_CREATE, changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return c_json(await role.json)


@app.patch("/api/v9/guilds/<int:guild>/roles/<int:role>")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def api_guilds_guild_roles_role_patch(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    data = await request.get_json()
    if "id" in data: del data["id"]
    if "guild_id" in data: del data["guild_id"]
    if role.id == guild.id:
        data = {"permissions": data["permissions"]} if "permissions" in data else {} # Only allow permissions editing for @everyone role
    if "icon" in data:
        img = data["icon"]
        if img is not None:
            del data["icon"]
            if (img := getImage(img)) and validImage(img):
                if h := await cdn.setRoleIconFromBytesIO(role.id, img):
                    data["icon"] = h
    new_role = role.copy(**data)
    await core.updateRoleDiff(role, new_role)
    await core.sendGuildRoleUpdateEvent(new_role)

    changes = []
    for k, v in guild.getDiff(role).items():
        changes.append({"key": k, "old_value": role.get(k), "new_value": new_role.get(k)})
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, role.id, AuditLogEntryType.ROLE_UPDATE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return c_json(await new_role.json)


@app.patch("/api/v9/guilds/<int:guild>/roles")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_roles_patch(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    roles_data = await request.get_json()
    roles = await core.getRoles(guild)
    roles.remove([role for role in roles if role.id == guild.id][0])

    if not await member.perm_checker.canChangeRolesPositions(roles_data, roles):
        raise InvalidDataErr(403, Errors.make(50013))

    changes = []
    for data in roles_data:
        if not (role := [role for role in roles if role.id == int(data["id"])]): continue # Don't add non-existing roles
        role = role[0]
        if (pos := data["position"]) < 1: pos = 1
        new_role = role.copy(position=pos)
        changes.append(new_role)
    changes.sort(key=lambda r: (r.position, r.permissions))
    for idx, new_role in enumerate(changes):
        new_role.position = idx + 1 # Set new position
        if (old_role := [role for role in roles if role.id == new_role.id][0]).getDiff(new_role) == {}:
            continue
        await core.updateRoleDiff(old_role, new_role)
        await core.sendGuildRoleUpdateEvent(new_role)
    roles = await core.getRoles(guild)
    roles = [await role.json for role in roles]
    return c_json(roles)


@app.delete("/api/v9/guilds/<int:guild>/roles/<int:role>")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def api_guilds_guild_roles_role_delete(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == role.guild_id:
        raise InvalidDataErr(400, Errors.make(50028))
    await core.deleteRole(role)
    await core.sendGuildRoleDeleteEvent(role)

    changes = [
        {"old_value": role.name, "key": "name"},
        {"old_value": role.permissions, "key": "permissions"},
        {"old_value": role.color, "key": "color"},
        {"old_value": role.hoist, "key": "hoist"},
        {"old_value": role.mentionable, "key": "mentionable"}
    ]
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, role.id, AuditLogEntryType.ROLE_DELETE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return "", 204


@app.get("/api/v9/guilds/<int:guild>/roles/<int:role>/connections/configuration")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def api_guilds_guild_roles_role_connections_configuration(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return c_json([]) # TODO


@app.get("/api/v9/guilds/<int:guild>/roles/member-counts")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_roles_membercounts(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    counts = await core.getRolesMemberCounts(guild)
    return c_json(counts)


@app.get("/api/v9/guilds/<int:guild>/roles/<int:role>/member-ids")
@multipleDecorators(usingDB, getUser, getGuildWoM, getRole)
async def api_guilds_guild_roles_role_memberids(user: User, guild: Guild, role: Role):
    members = [str(member_id) for member_id in await core.getRolesMemberIds(role)]
    return c_json(members)


@app.patch("/api/v9/guilds/<int:guild>/roles/<int:role>/members")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def api_guilds_guild_roles_role_members(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if (role.id == guild.id or role.position >= (await member.top_role).position) and member.id != guild.owner_id:
        raise InvalidDataErr(403, Errors.make(50013))
    members = {}
    member_ids = (await request.get_json()).get("member_ids", [])
    member_ids = [int(member_id) for member_id in member_ids]
    for member_id in member_ids:
        target_member = await core.getGuildMember(guild, member_id)
        if not await core.memberHasRole(target_member, role):
            await core.addMemberRole(target_member, role)
            await core.sendGuildMemberUpdateEvent(target_member)
            members[str(target_member.id)] = await target_member.json
    return c_json(members)


@app.patch("/api/v9/guilds/<int:guild>/members/<string:target_user>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_members_member_patch(user: User, guild: Guild, member: GuildMember, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    data = await request.get_json()
    target_member = await core.getGuildMember(guild, target_user)
    new_member = target_member.copy()
    if "roles" in data: # TODO: add MEMBER_ROLE_UPDATE audit log event
        await member.checkPermission(GuildPermissions.MANAGE_ROLES)
        roles = [int(role) for role in data["roles"]]
        guild_roles = {role.id: role for role in await core.getRoles(guild)}
        roles = [role_id for role_id in roles if role_id in guild_roles]
        user_top_role = await member.top_role
        for role_id in roles:
            if guild_roles[role_id].position >= user_top_role.position:
                raise InvalidDataErr(403, Errors.make(50013))
        await core.setMemberRolesFromList(target_member, roles)
    target_member = new_member.copy()
    if "nick" in data:
        await member.checkPermission(
            GuildPermissions.CHANGE_NICKNAME
            if target_member.user_id == member.user_id else
            GuildPermissions.MANAGE_NICKNAMES
        )
        nick = data["nick"]
        if not nick.strip(): nick = None
        new_member = target_member.copy(nick=nick)
        await core.updateMemberDiff(target_member, new_member)
    target_member = new_member.copy()
    if "avatar" in data and target_member.user_id == member.user_id:
        avatar = data["avatar"]
        if (img := getImage(avatar)) and validImage(img):
            if av := await cdn.setGuildAvatarFromBytesIO(user.id, guild.id, img):
                avatar = av
            else:
                avatar = member.avatar
        elif avatar is None:
            pass
        else:
            avatar = member.avatar
        new_member = target_member.copy(avatar=avatar)
        await core.updateMemberDiff(target_member, new_member)
    await core.sendGuildMemberUpdateEvent(new_member)

    changes = []
    for k, v in member.getDiff(new_member).items():
        changes.append({"key": k, "old_value": member.get(k), "new_value": new_member.get(k)})
    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, member.user_id, AuditLogEntryType.MEMBER_UPDATE,
                          changes=changes)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return c_json(await new_member.json)


@app.put("/api/v9/channels/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_permissions_target_put(user: User, channel: Channel, target_id: int):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await core.getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await core.getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    data = await request.get_json()
    del data["id"]
    old_overwrite = await core.getPermissionOverwrite(channel, target_id)
    overwrite = PermissionOverwrite(**data, channel_id=channel.id, target_id=target_id)
    await core.putPermissionOverwrite(overwrite)
    await core.sendChannelUpdateEvent(channel)

    if old_overwrite:
        t = AuditLogEntryType.CHANNEL_OVERWRITE_UPDATE
        changes = []
        if old_overwrite.allow != overwrite.allow:
            changes.append({"new_value": str(overwrite.allow), "old_value": str(old_overwrite.allow), "key": "allow"})
        if old_overwrite.deny != overwrite.deny:
            changes.append({"new_value": str(overwrite.deny), "old_value": str(old_overwrite.deny), "key": "deny"})
    else:
        t = AuditLogEntryType.CHANNEL_OVERWRITE_CREATE
        changes = [
            {"new_value": str(overwrite.target_id), "key": "id"},
            {"new_value": str(overwrite.type), "key": "type"},
            {"new_value": str(overwrite.allow), "key": "allow"},
            {"new_value": str(overwrite.deny), "key": "deny"}
        ]
    options = {
        "type": str(overwrite.type),
        "id": str(overwrite.target_id)
    }
    if overwrite.type == 0:
        role = await core.getRole(overwrite.target_id)
        options["role_name"] = role.name
    entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id, t, changes=changes, options=options)
    await core.putAuditLogEntry(entry)
    await core.sendAuditLogEntryCreateEvent(entry)

    return "", 204


@app.delete("/api/v9/channels/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_permissions_target_delete(user: User, channel: Channel, target_id: int):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await core.getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await core.getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    overwrite = await core.getPermissionOverwrite(channel, target_id)
    await core.deletePermissionOverwrite(channel, target_id)
    await core.sendChannelUpdateEvent(channel)

    if overwrite:
        changes = [
            {"old_value": str(overwrite.target_id), "key": "id"},
            {"old_value": str(overwrite.type), "key": "type"},
            {"old_value": str(overwrite.allow), "key": "allow"},
            {"old_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0:
            role = await core.getRole(overwrite.target_id)
            options["role_name"] = role.name
        entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id,
                              AuditLogEntryType.CHANNEL_OVERWRITE_DELETE, changes=changes, options=options)
        await core.putAuditLogEntry(entry)
        await core.sendAuditLogEntryCreateEvent(entry)

    return "", 204


@app.get("/api/v9/channels/<int:channel>/invites")
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_invites_get(user: User, channel: Channel):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await core.getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await core.getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    invites = await core.getChannelInvites(channel)
    invites = [await invite.json for invite in invites]
    return c_json(invites)


@app.get("/api/v9/guilds/<int:guild>/vanity-url")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_vanityurl_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    code = {
        "code": guild.vanity_url_code
    }
    if guild.vanity_url_code:
        if invite := await core.getVanityCodeInvite(guild.vanity_url_code):
            code["uses"]: invite.uses
    return c_json(code)


@app.patch("/api/v9/guilds/<int:guild>/vanity-url")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_vanityurl_patch(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    if "code" not in data:
        return c_json({"code": guild.vanity_url_code})
    code = data.get("code")
    if code == guild.vanity_url_code:
        return c_json({"code": guild.vanity_url_code})
    if not code:
        new_guild = guild.copy(vanity_url_code=None)
        await core.updateGuildDiff(guild, new_guild)
        if invite := await core.getVanityCodeInvite(guild.vanity_url_code):
            await core.deleteInvite(invite)
    else:
        if guild.vanity_url_code and (invite := await core.getVanityCodeInvite(guild.vanity_url_code)):
            await core.deleteInvite(invite)
        new_guild = guild.copy(vanity_url_code=code)
        await core.updateGuildDiff(guild, new_guild)
        invite = Invite(Snowflake.makeId(), guild.system_channel_id, guild.owner_id, int(time()), 0, vanity_code=code,
                        guild_id=guild.id)
        await core.putInvite(invite)
    await core.sendGuildUpdateEvent(new_guild)
    return c_json({"code": new_guild.vanity_url_code})


@app.get("/api/v9/guilds/<int:guild>/audit-logs")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def api_guilds_guild_auditlogs_get(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    limit = int(request.args.get("limit", 50))
    if limit > 50: limit = 50
    before = request.args.get("before")
    if before is not None: before = int(before)
    entries = await core.getAuditLogEntries(guild, limit, before)
    userdatas = {}
    for entry in entries:
        target_user_id = entry.target_user_id
        if target_user_id and target_user_id not in userdatas:
            userdatas[target_user_id] = await core.getUserData(UserId(target_user_id))
    userdatas = list(userdatas.values())

    data = {
        "application_commands": [],
        "audit_log_entries": [await entry.json for entry in entries],
        "auto_moderation_rules": [],
        "guild_scheduled_events": [],
        "integrations": [],
        "threads": [],
        "users": [await userdata.json for userdata in userdatas],
        "webhooks": [],
    }

    return c_json(data)


# Stickers & gifs


@app.get("/api/v9/sticker-packs")
async def api_stickerpacks_get():
    return c_json('{"sticker_packs": []}') # TODO


@app.get("/api/v9/gifs/trending")
async def api_gifs_trending_get():
    return c_json('{"gifs": [], "categories": []}') # TODO


# Hypesquad


@app.post("/api/v9/hypesquad/online")
@multipleDecorators(usingDB, getUser)
async def api_hypesquad_online(user: User):
    data = await request.get_json()
    if not (house_id := data.get("house_id")):
        raise InvalidDataErr(400, Errors.make(50035, {"house_id": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if house_id not in (1, 2, 3):
        raise InvalidDataErr(400, Errors.make(50035, {"house_id": {"code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (1, 2, 3)."}}))
    data = await user.data
    flags = UserFlags(data.public_flags)
    for f in (UserFlagsE.HYPESQUAD_ONLINE_HOUSE_1, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_2, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_3):
        flags.remove(f)
    flags.add(getattr(UserFlagsE, f"HYPESQUAD_ONLINE_HOUSE_{house_id}"))
    data.public_flags = flags.value
    await core.setUserdata(data)
    await core.sendUserUpdateEvent(user.id)
    return "", 204


# Other


@app.get("/api/v9/auth/location-metadata")
async def api_auth_locationmetadata():
    return c_json("{\"consent_required\": false, \"country_code\": \"US\", \"promotional_email_opt_in\": {\"required\": true, \"pre_checked\": false}}")


@app.post("/api/v9/science")
async def api_science():
    return "", 204


@app.get("/api/v9/experiments")
async def api_experiments():
    return c_json("{\"fingerprint\":\"0.A\",\"assignments\":[],\"guild_experiments\":[]}")


@app.get("/api/v9/applications/detectable")
async def api_applications_detectable():
    return c_json("[]")

@app.get("/api/v9/users/@me/survey")
async def api_users_me_survey():
    return c_json("{\"survey\":null}")


@app.get("/api/v9/users/@me/affinities/guilds")
async def api_users_me_affinities_guilds():
    return c_json("{\"guild_affinities\":[]}")


@app.get("/api/v9/users/@me/affinities/users")
async def api_users_me_affinities_users():
    return c_json("{\"user_affinities\":[],\"inverse_user_affinities\":[]}")


@app.get("/api/v9/users/@me/library")
async def api_users_me_library():
    return c_json("[]")


@app.get("/api/v9/users/@me/billing/payment-sources")
async def api_users_me_billing_paymentsources():
    return c_json("[]")


@app.get("/api/v9/users/@me/billing/country-code")
async def api_users_me_billing_countrycode():
    return c_json("{\"country_code\": \"US\"}")


@app.get("/api/v9/users/@me/billing/localized-pricing-promo")
async def api_users_me_billing_localizedpricingpromo():
    return c_json("{\"country_code\": \"US\", \"localized_pricing_promo\": null}")


@app.get("/api/v9/users/@me/billing/user-trial-offer")
async def api_users_me_billing_usertrialoffer():
    return c_json("{\"message\": \"404: Not Found\", \"code\": 0}", 404)


@app.get("/api/v9/users/@me/billing/subscriptions")
async def api_users_me_billing_subscriptions():
    return c_json("[{\"items\": [{\"id\": 1, \"plan_id\": 511651880837840896, \"quantity\": 1200}], \"id\": 1, \"type\": 2, \"created_at\": 1640995200000, \"canceled_at\": null, \"current_period_start\": 1640995200000, \"current_period_end\": 4794595201000, \"status\": \"idk\", \"payment_source_id\": 0, \"payment_gateway\": null, \"payment_gateway_plan_id\": null, \"payment_gateway_subscription_id\": null, \"trial_id\": null, \"trial_ends_at\": null, \"renewal_mutations\": null, \"streak_started_at\": 1640995200000, \"currency\": \"USD\", \"metadata\": null}]")


@app.get("/api/v9/users/@me/billing/subscription-slots")
async def api_users_me_billing_subscriptionslots():
    return c_json("[]")


@app.get("/api/v9/users/@me/guilds/premium/subscription-slots")
async def api_users_me_guilds_premium_subscriptionslots():
    return c_json("[]")


@app.get("/api/v9/outbound-promotions")
async def api_outboundpromotions():
    return c_json("[]")


@app.get("/api/v9/users/@me/applications/<aid>/entitlements")
async def api_users_me_applications_id_entitlements(aid):
    return c_json("[]")


@app.get("/api/v9/store/published-listings/skus/<int:sku>/subscription-plans")
async def api_store_publishedlistings_skus_id_subscriptionplans(sku):
    if sku == 978380684370378762:
        return c_json("[{\"id\": \"978380692553465866\",\"name\": \"Nitro Basic Monthly\",\"interval\": 1,\"interval_count\": 1,\"tax_inclusive\": true,\"sku_id\": \"978380684370378762\",\"currency\": \"usd\",\"price\": 0,\"price_tier\": null}]")
    elif sku == 521846918637420545:
        return c_json("[{\"id\":\"511651871736201216\",\"name\":\"Premium Classic Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651876987469824\",\"name\":\"Premium Classic Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 521847234246082599:
        return c_json("[{\"id\":\"642251038925127690\",\"name\":\"Premium Quarterly\",\"interval\":1,\"interval_count\":3,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651880837840896\",\"name\":\"Premium Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651885459963904\",\"name\":\"Premium Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 590663762298667008:
        return c_json("[{\"id\":\"590665532894740483\",\"name\":\"Server Boost Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"590665538238152709\",\"name\":\"Server Boost Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    return c_json("[]")


@app.get("/api/v9/users/@me/outbound-promotions/codes")
async def api_users_me_outboundpromotions_codes():
    return c_json("[]")


@app.get("/api/v9/users/@me/entitlements/gifts")
async def api_users_me_entitlements_gifts():
    return c_json("[]")


@app.get("/api/v9/users/@me/activities/statistics/applications")
async def api_users_me_activities_statistics_applications():
    return c_json("[]")


@app.get("/api/v9/users/@me/billing/payments")
async def api_users_me_billing_payments():
    return c_json("[]")


@app.route("/api/v9/users/@me/settings-proto/3", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_3():
    return c_json("{\"settings\": \"\"}")


@app.route("/api/v9/users/@me/settings-proto/<int:t>", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_type(t):
    raise InvalidDataErr(400, Errors.make(50013, {"type": {"code": "BASE_TYPE_CHOICES", "message": "Value must be one of (<UserSettingsTypes.PRELOADED_USER_SETTINGS: 1>, <UserSettingsTypes.FRECENCY_AND_FAVORITES_SETTINGS: 2>, <UserSettingsTypes.TEST_SETTINGS: 3>)."}}))


@app.get("/api/v9/gateway")
async def api_gateway():
    return c_json("{\"url\": \"wss://gateway.yepcord.ml\"}")


# OAuth


@app.get("/api/v9/oauth2/tokens")
async def api_oauth_tokens():
    return c_json("[]")


# Other endpoints


@app.route("/api/v9/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def other_api_endpoints(path):
    print("----------------")
    print(f"  Path: /api/v9/{path}")
    print(f"  Method: {request.method}")
    print("  Headers:")
    for k,v in request.headers.items():
        print(f"    {k}: {v}")
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        print(f"  Data: {await request.get_json()}")
    print("----------------")
    return "Not Implemented!", 501


if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)