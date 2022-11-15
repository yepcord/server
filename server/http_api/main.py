from io import BytesIO
from time import time
from uuid import uuid4
from PIL import Image
from async_timeout import timeout
from magic import from_buffer
from quart import Quart, request
from functools import wraps
from os import urandom
from json import dumps as jdumps, loads as jloads
from random import choice
from base64 import b64encode as _b64encode, b64decode as _b64decode
from emoji import is_emoji
from quart.globals import request_ctx

from server.ctx import Ctx
from server.geoip import getLanguageCode
from ..proto import PreloadedUserSettings, FrecencyUserSettings
from ..config import Config
from ..errors import InvalidDataErr, MfaRequiredErr, YDataError, EmbedErr
from ..classes import Session, UserSettings, UserData, Message, UserNote, UserConnection, Attachment, Channel, \
    UserFlags, Reaction, SearchFilter, Emoji
from ..core import Core, CDN
from ..utils import b64decode, b64encode, mksf, c_json, getImage, validImage, MFA, execute_after, mkError, \
    parseMultipartRequest, LOCALES
from ..enums import ChannelType, MessageType, UserFlags as UserFlagsE, RelationshipType
from ..responses import userSettingsResponse, userdataResponse, userConsentResponse, userProfileResponse, channelInfoResponse
from ..storage import FileStorage


class YEPcord(Quart):
    async def process_response(self, response, request_context=None):
        response = await super(YEPcord, self).process_response(response, request_context)
        response.headers['Server'] = "YEPcord"
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Headers'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "*"
        response.headers['Content-Security-Policy'] = "connect-src *;"
        
        return response

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
cdn = CDN(FileStorage(), core)

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
        if not (session := Session.from_token(request.headers.get("Authorization", ""))):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        if not (user := await core.getUserFromSession(session)):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        Ctx["user_id"] = user.id
        kwargs["user"] = user
        return await f(*args, **kwargs)
    return wrapped

def getSession(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (session := Session.from_token(request.headers.get("Authorization", ""))):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        if not await core.validSession(session):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        Ctx["user_id"] = session.id
        kwargs["session"] = session
        return await f(*args, **kwargs)
    return wrapped

def getChannel(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        if not (channel := kwargs.get("channel")):
            raise InvalidDataErr(404, mkError(10003))
        if not (user := kwargs.get("user")):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        if not (channel := await core.getChannel(channel)):
            raise InvalidDataErr(404, mkError(10003))
        if not await core.getUserByChannel(channel, user.id):
            raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
        kwargs["channel"] = channel
        return await f(*args, **kwargs)
    return wrapped

async def _getMessage(user, channel, message_id):
    if not channel:
        raise InvalidDataErr(404, mkError(10003))
    if not user:
        raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
    if not message_id:
        raise InvalidDataErr(404, mkError(10008))
    if not (message := await core.getMessage(channel, message_id)):
        raise InvalidDataErr(404, mkError(10008))
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
            raise InvalidDataErr(404, mkError(10006))
        try:
            invite = b64decode(invite)
        except:
            raise InvalidDataErr(404, mkError(10006))
        invite = int.from_bytes(invite, "big")
        if not (invite := await core.getInvite(invite)):
            raise InvalidDataErr(404, mkError(10006))
        kwargs["invite"] = invite
        return await f(*args, **kwargs)
    return wrapped

def getGuild(with_member):
    def _getGuild(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            if not (guild := int(kwargs.get("guild"))):
                raise InvalidDataErr(404, mkError(10004))
            if not (user := kwargs.get("user")):
                raise InvalidDataErr(401, mkError(0, message="401: Unauthorized"))
            if not (guild := await core.getGuild(guild)):
                raise InvalidDataErr(404, mkError(10004))
            if not (member := await core.getGuildMember(guild, user.id)):
                raise InvalidDataErr(403, mkError(50001))
            kwargs["guild"] = guild
            if with_member:
                kwargs["member"] = member
            return await f(*args, **kwargs)
        return wrapped
    return _getGuild

getGuildWithMember = getGuild(with_member=True)
getGuildWithoutMember = getGuild(with_member=False)
getGuildWM = getGuildWithMember
getGuildWoM = getGuildWithoutMember

# Auth


@app.route("/api/v9/auth/register", methods=["POST"])
@usingDB
async def api_auth_register():
    data = await request.get_json()
    loc = getLanguageCode(request.remote_addr, request.accept_languages.best_match(LOCALES, "en-US"))
    sess = await core.register(mksf(), data["username"], data.get("email"), data["password"], data["date_of_birth"], loc)
    return c_json({"token": sess.token})


@app.route("/api/v9/auth/login", methods=["POST"])
@usingDB
async def api_auth_login():
    data = await request.get_json()
    sess = await core.login(data["login"], data["password"])
    user = await core.getUserFromSession(sess)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@app.route("/api/v9/auth/mfa/totp", methods=["POST"])
@usingDB
async def api_auth_mfa_totp(): # TODO: test
    data = await request.get_json()
    if not (ticket := data.get("ticket")):
        raise InvalidDataErr(400, mkError(60006))
    if not (code := data.get("code")):
        raise InvalidDataErr(400, mkError(60008))
    if not (mfa := await core.getMfaFromTicket(ticket)):
        raise InvalidDataErr(400, mkError(60006))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, mkError(60008))
    sess = await core.createSessionWithoutKey(mfa.uid)
    user = await core.getUserFromSession(sess)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@app.route("/api/v9/auth/logout", methods=["POST"])
@multipleDecorators(usingDB, getSession)
async def api_auth_logout(session):
    await core.logoutUser(session)
    return "", 204


@app.route("/api/v9/auth/verify/view-backup-codes-challenge", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_auth_verify_viewbackupcodeschallenge(user):
    data = await request.get_json()
    if not (password := data.get("password")):
        raise InvalidDataErr(400, mkError(50018))
    if not await core.checkUserPassword(user, password):
        raise InvalidDataErr(400, mkError(50018))
    nonce = await core.generateUserMfaNonce(user)
    await core.sendMfaChallengeEmail(user, nonce[0])
    return c_json({"nonce": nonce[0], "regenerate_nonce": nonce[1]})


@app.route("/api/v9/auth/verify/resend", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_auth_verify_resend(user):
    if not user.verified:
        await core.sendVerificationEmail(user)
    return "", 204


@app.route("/api/v9/auth/verify", methods=["POST"])
@usingDB
async def api_auth_verify():
    data = await request.get_json()
    if not data.get("token"):
        raise InvalidDataErr(400, mkError(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    try:
        email = jloads(b64decode(data["token"].split(".")[0]).decode("utf8"))["email"]
    except:
        raise InvalidDataErr(400, mkError(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    user = await core.getUserByEmail(email)
    await core.verifyEmail(user, data["token"])
    await core.sendUserUpdateEvent(user.id)
    return c_json({"token": (await core.createSession(user.id, user.key)).token, "user_id": str(user.id)})


# Users (@me)


@app.route("/api/v9/users/@me", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_get(user):
    return c_json(await userdataResponse(user))

@app.route("/api/v9/users/@me", methods=["PATCH"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_patch(user):
    data = await user.data
    _settings = await request.get_json()
    d = "discriminator" in _settings and _settings.get("discriminator") != data.discriminator
    u = "username" in _settings and _settings.get("username") != data.username
    if d or u:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, mkError(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        if u:
            await core.changeUserName(user, str(_settings["username"]))
            del _settings["username"]
        if d:
            if not await core.changeUserDiscriminator(user, int(_settings["discriminator"])):
                if u:
                    return c_json(await userdataResponse(user))
                raise InvalidDataErr(400, mkError(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This discriminator already used by someone. Please enter something else."}}))
            del _settings["discriminator"]
    if "new_password" in _settings:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, mkError(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await core.changeUserPassword(user, _settings["new_password"])
        del _settings["new_password"]
    if "email" in _settings:
        if "password" not in _settings or not await core.checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, mkError(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await core.changeUserEmail(user, _settings["email"])
        await core.sendVerificationEmail(user)
        del _settings["email"]

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

@app.route("/api/v9/users/@me/profile", methods=["PATCH"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_profile_patch(user):
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

@app.route("/api/v9/users/@me/consent", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_consent_get(user):
    return c_json(await userConsentResponse(user))

@app.route("/api/v9/users/@me/consent", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_consent_set(user):
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


@app.route("/api/v9/users/@me/settings", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settings_get(user):
    return c_json(await userSettingsResponse(user))


@app.route("/api/v9/users/@me/settings", methods=["PATCH"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settings_patch(user):
    settings = await request.get_json()
    if "uid" in settings: del settings["uid"]
    s = UserSettings(user.id, **settings)
    await core.setSettings(s)
    await core.sendUserUpdateEvent(user.id)
    return c_json(await userSettingsResponse(user))


@app.route("/api/v9/users/@me/settings-proto/1", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_1_get(user):
    proto = await user.settings_proto
    return c_json({"settings": _b64encode(proto.SerializeToString()).decode("utf8")})


@app.route("/api/v9/users/@me/settings-proto/1", methods=["PATCH"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_1_patch(user): # TODO
    data = await request.get_json()
    if not data.get("settings"):
        raise InvalidDataErr(400, mkError(50013, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto = PreloadedUserSettings()
        proto.ParseFromString(_b64decode(data.get("settings").encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, mkError(50104))
    settings_old = await user.settings
    settings = UserSettings(user.id)
    settings.from_proto(proto)
    await core.setSettingsDiff(settings_old, settings)
    user._uSettings = None
    settings = await user.settings
    proto = _b64encode(settings.to_proto().SerializeToString()).decode("utf8")
    await core.sendSettingsProtoUpdateEvent(user.id, proto, 1)
    return c_json({"settings": proto})


@app.route("/api/v9/users/@me/settings-proto/2", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_2_get(user):
    proto = await user.frecency_settings_proto
    return c_json({"settings": _b64encode(proto).decode("utf8")})


@app.route("/api/v9/users/@me/settings-proto/2", methods=["PATCH"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_settingsproto_2_patch(user):
    data = await request.get_json()
    if not data.get("settings"):
        raise InvalidDataErr(400, mkError(50013, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto_new = FrecencyUserSettings()
        proto_new.ParseFromString(_b64decode(data.get("settings").encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, mkError(50104))
    proto = FrecencyUserSettings()
    proto.ParseFromString(await user.frecency_settings_proto)
    proto.MergeFrom(proto_new)
    proto = proto.SerializeToString()
    proto = _b64encode(proto).decode("utf8")
    await core.setFrecencySettings(user.id, proto)
    await core.sendSettingsProtoUpdateEvent(user.id, proto, 2)
    return c_json({"settings": proto})


@app.route("/api/v9/users/@me/connections", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_connections(user): # TODO
    return c_json("[]") # friend_sync: bool, id: str(int), integrations: list, name: str, revoked: bool, show_activity: bool, two_way_link: bool, type: str, verified: bool, visibility: int


@app.route("/api/v9/users/@me/relationships", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_post(user):
    udata = await request.get_json()
    if not (rUser := await core.getUserByUsername(**udata)):
        raise InvalidDataErr(400, mkError(80004))
    if rUser == user:
        raise InvalidDataErr(400, mkError(80007))
    await core.checkRelationShipAvailable(rUser, user)
    await core.reqRelationship(rUser, user)
    return "", 204


@app.route("/api/v9/users/@me/relationships", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_get(user):
    return c_json(await core.getRelationships(user, with_data=True))


@app.route("/api/v9/users/@me/notes/<int:target_uid>", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_notes_get(user, target_uid):
    if not (note := await core.getUserNote(user.id, target_uid)):
        raise InvalidDataErr(404, mkError(10013))
    return c_json(note.to_response())


@app.route("/api/v9/users/@me/notes/<int:target_uid>", methods=["PUT"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_notes_put(user, target_uid):
    data = await request.get_json()
    if note := data.get("note"):
        await core.putUserNote(UserNote(user.id, target_uid, note))
    return "", 204


@app.route("/api/v9/users/@me/mfa/totp/enable", methods=["POST"])
@multipleDecorators(usingDB, getSession)
async def api_users_me_mfa_totp_enable(session):
    data = await request.get_json()
    if not (password := data.get("password")) or not await core.checkUserPassword(session, password):
        raise InvalidDataErr(400, mkError(50018))
    if not (secret := data.get("secret")):
        raise InvalidDataErr(400, mkError(60005))
    mfa = MFA(secret, session.id)
    if not mfa.valid:
        raise InvalidDataErr(400, mkError(60005))
    if not (code := data.get("code")):
        raise InvalidDataErr(400, mkError(60008))
    if mfa.getCode() != code:
        raise InvalidDataErr(400, mkError(60008))
    await core.setSettings(UserSettings(session.id, mfa=secret))
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await core.setBackupCodes(session, codes)
    await execute_after(core.sendUserUpdateEvent(session.id), 3)
    codes = [{"user_id": str(session.id), "code": code, "consumed": False} for code in codes]
    await core.logoutUser(session)
    session = await core.createSessionWithoutKey(session.id)
    return c_json({"token": session.token, "backup_codes": codes})


@app.route("/api/v9/users/@me/mfa/totp/disable", methods=["POST"])
@multipleDecorators(usingDB, getSession)
async def api_users_me_mfa_totp_disable(session):
    data = await request.get_json()
    if not (code := data.get("code")):
        raise InvalidDataErr(400, mkError(60008))
    if not (mfa := await core.getMfa(session)):
        raise InvalidDataErr(400, mkError(50018))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await core.useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, mkError(60008))
    await core.setSettings(UserSettings(session.id, mfa=None))
    await core.clearBackupCodes(session)
    await core.sendUserUpdateEvent(session.id)
    await core.logoutUser(session)
    session = await core.createSessionWithoutKey(session.id)
    return c_json({"token": session.token})


@app.route("/api/v9/users/@me/mfa/codes-verification", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_mfa_codesverification(user):
    data = await request.get_json()
    if not (unonce := data.get("nonce")):
        raise InvalidDataErr(400, mkError(60011))
    if not (key := data.get("key")):
        raise InvalidDataErr(400, mkError(50035, {"key": {"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}}))
    reg = data.get("regenerate", False)
    nonce = await core.generateUserMfaNonce(user)
    nonce = nonce[1] if reg else nonce[0]
    if nonce != unonce:
        raise InvalidDataErr(400, mkError(60011))
    if core.mfaNonceToCode(nonce) != key:
        raise InvalidDataErr(400, mkError(60011))
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


@app.route("/api/v9/users/@me/relationships/<int:uid>", methods=["PUT"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_put(uid, user):
    data = await request.get_json()
    if not data or "type" not in data:
        await core.accRelationship(user, uid)
    elif data["type"] == 2:
        await core.blockUser(user, uid)
    return "", 204


@app.route("/api/v9/users/@me/relationships/<int:uid>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_relationships_delete(uid, user):
    await core.delRelationship(user, uid)
    return "", 204


@app.route("/api/v9/users/@me/harvest", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_harvest(user):
    return "", 204


# Connections


@app.route("/api/v9/connections/<string:connection>/authorize", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_connections_connection_authorize(user, connection):
    url = ""
    kwargs = {}
    if connection == "github":
        CLIENT_ID = ""
        state = urandom(16).hex()
        kwargs["state"] = state
        url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=https%3A%2F%2F127.0.0.1:8080%2Fapi%2Fconnections%2Fgithub%2Fcallback&scope=read%3Auser&state={state}"
    await core.putUserConnection(UserConnection(user, connection, **kwargs))
    return c_json({"url": url})


@app.route("/api/v9/connections/<string:connection>/callback", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_connections_connection_callback(user, connection):
    data = await request.get_json()
    if connection == "github":
        ...
    return ...


@app.route("/api/v9/users/@me/channels", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_channels_get(user):
    return c_json(await core.getPrivateChannels(user))


@app.route("/api/v9/users/@me/channels", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_users_me_channels_post(user):
    data = await request.get_json()
    rep = data.get("recipients", [])
    rep = [int(r) for r in rep]
    if len(rep) == 1:
        if int(rep[0]) == user.id:
            raise InvalidDataErr(400, mkError(50007))
        ch = await core.getDMChannelOrCreate(user.id, rep[0])
    elif len(rep) == 0:
        ch = await core.createDMGroupChannel(user, [])
    else:
        if user.id in rep:
            rep.remove(user.id)
        if len(rep) == 0:
            raise InvalidDataErr(400, mkError(50007))
        elif len(rep) == 1:
            ch = await core.getDMChannelOrCreate(user.id, rep[0])
        else:
            ch = await core.createDMGroupChannel(user, rep)
    await core.sendDMChannelCreateEvent(ch)
    return c_json(await channelInfoResponse(ch, user, ids=False))


# Users


@app.route("/api/v9/users/<int:t_user_id>/profile", methods=["GET"])
@multipleDecorators(usingDB, getUser)
async def api_users_user_profile(user, t_user_id):
    user = await core.getUserProfile(t_user_id, user)
    return c_json(await userProfileResponse(user))


# Channels


@app.route("/api/v9/channels/<channel>", methods=["GET"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel(user, channel):
    return c_json(await channelInfoResponse(channel, user))


@app.route("/api/v9/channels/<int:channel>", methods=["PATCH"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_patch(user, channel):
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
            raise InvalidDataErr(403, mkError(50013))
        data["owner_id"] = int(data["owner"])
        del data["owner"]
    if "id" in data: del data["id"]
    if "type" in data: del data["type"]
    nChannel = Channel(channel.id, channel.type, **data)
    await core.updateChannelDiff(channel, nChannel)
    await core.sendDMChannelUpdateEvent(channel)
    diff = channel.get_diff(nChannel)
    if "name" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=mksf(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_NAME_CHANGE, content=nChannel.name)
        await core.sendMessage(message)
    if "icon" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=mksf(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_ICON_CHANGE, content="")
        await core.sendMessage(message)
    channel.set(**data)
    return c_json(await channelInfoResponse(channel, user))


@app.route("/api/v9/channels/<int:channel>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_delete(user, channel):
    if channel.type == ChannelType.DM:
        return "", 204 # TODO
    elif channel.type == ChannelType.GROUP_DM:
        msg = Message(id=mksf(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": user.id})
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
    return "", 204


@app.route("/api/v9/channels/<int:channel>/messages", methods=["GET"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_get(user, channel):
    args = request.args
    messages = await channel.messages(args.get("limit", 50), int(args.get("before", 0)), int(args.get("after", 0)))
    messages = [await m.json for m in messages]
    return c_json(messages)


@app.route("/api/v9/channels/<int:channel>/messages", methods=["POST"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_post(user, channel):
    if channel.type == ChannelType.DM:
        oth = channel.recipients.copy()
        oth.remove(user.id)
        oth = oth[0]
        rel = await core.getRelationship(user.id, oth)
        if not rel:
            ... # TODO: Check
        if rel and rel.type == RelationshipType.BLOCK:
            raise InvalidDataErr(403, mkError(50007))
    data = await request.get_json()
    if data is None and (ct := request.headers.get("Content-Type", "")).startswith("multipart/form-data;"):
        data = {}
        if request.content_length > 1024*1024*100:
            raise InvalidDataErr(400, mkError(50006)) # TODO: replace with correct error
        async with timeout(100):
            boundary = ct.split(";")[1].strip().split("=")[1].split("WebKitFormBoundary")[1]
            body = await request.body
            if len(body) > 1024*1024*100:
                raise InvalidDataErr(400, mkError(50006)) # TODO: replace with correct error
            data = parseMultipartRequest(body, boundary)
            files = data["files"]
            data = jloads(data["payload_json"]["data"].decode("utf8"))
            if len(files) > 10:
                raise InvalidDataErr(400, mkError(50013, {"files": {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."}}))
            atts = data["attachments"]
            data["attachments"] = []
            for idx, file in enumerate(files):
                uuid = str(uuid4())
                att = {"filename": None}
                if idx+1 <= len(atts):
                    att = atts[idx]
                name = att.get("filename") or file.get("filename") or "unknown"
                data["attachments"].append({"uploaded_filename": f"{uuid}/{name}"})
                att = Attachment(mksf(), channel.id, name, len(file["data"]), uuid)
                if file.get("content_type"):
                    cot = file.get("content_type").strip()
                    att.set(content_type=cot)
                    if cot.startswith("image/"):
                        img = Image.open(BytesIO(file["data"]))
                        att.set(metadata={"height": img.height, "width": img.width})
                        img.close()
                else:
                    cot = from_buffer(file["data"][:1024], mime=True)
                    att.set(content_type=cot)
                    if cot.startswith("image/"):
                        img = Image.open(BytesIO(file["data"]))
                        att.set(metadata={"height": img.height, "width": img.width})
                        img.close()
                await core.putAttachment(att)
                await cdn.uploadAttachment(file["data"], att)
    if not data.get("content") and not data.get("embeds") and not data.get("attachments"):
        raise InvalidDataErr(400, mkError(50006))
    if "id" in data: del data["id"]
    if "channel_id" in data: del data["channel_id"]
    if "author" in data: del data["author"]
    message = Message(id=mksf(), channel_id=channel.id, author=user.id, **data, **({} if not channel.guild_id else {"guild_id": channel.guild_id}))
    await message.check()
    message = await core.sendMessage(message)
    if await core.delReadStateIfExists(user.id, channel.id):
        await core.sendMessageAck(user.id, channel.id, message.id)
    return c_json(await message.json)


@app.route("/api/v9/channels/<int:channel>/messages/<int:message>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_delete(user, channel, message):
    if message.author != user.id:
        raise InvalidDataErr(403, mkError(50003))
    await core.deleteMessage(message)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/messages/<int:message>", methods=["PATCH"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_patch(user, channel, message):
    data = await request.get_json()
    if message.author != user.id:
        raise InvalidDataErr(403, mkError(50005))
    before = message
    if "id" in data: del data["id"]
    if "channel_id" in data: del data["channel_id"]
    if "author" in data: del data["author"]
    if "edit_timestamp" in data: del data["edit_timestamp"]
    after = before.copy().set(edit_timestamp=int(time()), **data)
    after = await core.editMessage(before, after)
    return c_json(await after.json)

@app.route("/api/v9/channels/<int:channel>/messages/<int:message>/ack", methods=["POST"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_message_ack(user, channel, message):
    data = await request.get_json()
    if data.get("manual") and (ct := int(data.get("mention_count"))):
        if isinstance((message := await _getMessage(user, channel, message)), tuple):
            return message
        await core.setReadState(user.id, channel.id, ct, message.id)
        await core.sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        await core.delReadStateIfExists(user.id, channel.id)
        await core.sendMessageAck(user.id, channel.id, message)
    return c_json({"token": None})


@app.route("/api/v9/channels/<int:channel>/messages/ack", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_ack_delete(user, channel):
    await core.deleteMessagesAck(channel, user)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/typing", methods=["POST"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_typing(user, channel):
    await core.sendTypingEvent(user, channel)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/attachments", methods=["POST"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_attachments_post(user, channel):
    data = await request.get_json()
    if not (files := data.get("files")):
        raise InvalidDataErr(400, mkError(50013, {"files": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if len(files) > 10:
        raise InvalidDataErr(400, mkError(50013, {"files": {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 10 or less in length."}}))
    attachments = []
    for idx, file in enumerate(files):
        if not (filename := file.get("filename")) or not (filename := filename.replace("\\", "/").split("/")[-1]):
            raise InvalidDataErr(400, mkError(50013, {f"files.{idx}.filename": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if not (size := file.get("file_size")):
            try:
                size = int(size)
            except ValueError:
                raise InvalidDataErr(400, mkError(50013, {f"files.{idx}.file_size": {"code": "NUMBER_TYPE_COERCE", "message": f"The value '{size}' is not an int."}}))
            raise InvalidDataErr(400, mkError(50013, {f"files.{idx}.file_size": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        if not (fid := file.get("id")):
            raise InvalidDataErr(400, mkError(50013, {f"files.{idx}.id": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
        att = Attachment(mksf(), channel.id, filename, size)
        await core.putAttachment(att)
        attachments.append({
            "id": int(fid),
            "upload_filename": f"{att.uuid}/{att.filename}",
            "upload_url": f"https://{Config('CDN_HOST')}/upload/attachment/{att.uuid}/{att.filename}",
        })
    return {"attachments": attachments}

@app.route("/api/v9/channels/<int:channel>/recipients/<int:nUser>", methods=["PUT"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_repicients_recipient_put(user, channel, nUser):
    if channel.type not in (ChannelType.DM, ChannelType.GROUP_DM):
        raise InvalidDataErr(403, mkError(50013))
    if channel.type == ChannelType.DM:
        rep = channel.recipients
        rep.remove(user.id)
        rep.append(nUser)
        ch = await core.createDMGroupChannel(user, rep)
        await core.sendDMChannelCreateEvent(ch)
    elif channel.type == ChannelType.GROUP_DM:
        if nUser not in channel.recipients and len(channel.recipients) < 10:
            msg = Message(id=mksf(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": nUser})
            await core.sendMessage(msg)
            await core.addUserToGroupDM(channel, nUser)
            await core.sendDMRepicientAddEvent(channel.recipients, channel.id, nUser)
            await core.sendDMChannelCreateEvent(channel, users=[nUser])
    return "", 204


@app.route("/api/v9/channels/<int:channel>/recipients/<int:nUser>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_repicients_recipient_delete(user, channel, nUser):
    if channel.type not in (ChannelType.GROUP_DM,):
        raise InvalidDataErr(403, mkError(50013))
    if channel.owner_id != user.id:
        raise InvalidDataErr(403, mkError(50013))
    if nUser in channel.recipients:
        msg = Message(id=mksf(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": nUser})
        await core.sendMessage(msg)
        await core.removeUserFromGroupDM(channel, nUser)
        await core.sendDMRepicientRemoveEvent(channel.recipients, channel.id, nUser)
        await core.sendDMChannelDeleteEvent(channel, users=[nUser])
    return "", 204


@app.route("/api/v9/channels/<int:channel>/pins/<int:message>", methods=["PUT"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_pins_message_put(user, channel, message):
    if not message.pinned:
        await core.pinMessage(message)
        msg = Message(
            mksf(),
            author=user.id,
            channel_id=channel.id,
            type=MessageType.CHANNEL_PINNED_MESSAGE,
            content="",
            message_reference=message.id,
            **({} if not channel.guild_id else {"guild_id": channel.guild_id})
        )
        await core.sendMessage(msg)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/pins/<int:message>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_pins_message_delete(user, channel, message):
    if message.pinned:
        await core.unpinMessage(message)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/pins", methods=["GET"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_pins_get(user, channel):
    messages = await core.getPinnedMessages(channel.id)
    messages = [await message.json for message in messages]
    return messages


@app.route("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me", methods=["PUT"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_put(user, channel, message, reaction):
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, mkError(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await core.addReaction(Reaction(message.id, user.id, **r), channel)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_delete(user, channel, message, reaction):
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, mkError(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await core.removeReaction(Reaction(message.id, user.id, **r), channel)
    return "", 204


@app.route("/api/v9/channels/<int:channel>/messages/<int:message>/reactions/<string:reaction>", methods=["GET"])
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def api_channels_channel_messages_message_reactions_reaction_get(user, channel, message, reaction):
    if not is_emoji(reaction) and not (reaction := await core.getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, mkError(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    limit = int(request.args.get("limit", 3))
    if limit > 10:
        limit = 10
    return await core.getReactedUsers(Reaction(message.id, 0, **r), limit)


@app.route("/api/v9/channels/<int:channel>/messages/search", methods=["GET"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_messages_search(user, channel):
    messages, total = await core.searchMessages(SearchFilter(**request.args))
    Ctx["search"] = True
    messages = [[await message.json] for message in messages]
    for message in messages:
        message[0]["hit"] = True
    return c_json({"messages": messages, "total_results": total})


# Invites


@app.route("/api/v9/channels/<int:channel>/invites", methods=["POST"])
@multipleDecorators(usingDB, getUser, getChannel)
async def api_channels_channel_invites_post(user, channel):
    data = await request.get_json()
    max_age = data.get("max_age", 86400)
    invite = await core.createInvite(channel, user, max_age)
    return c_json(await invite.json)


@app.route("/api/v9/invites/<string:invite>", methods=["GET"])
@multipleDecorators(usingDB, getInvite)
async def api_invites_invite_get(invite):
    data = request.args
    with_counts = data.get("with_counts", "false").lower == "true"
    inv = await invite.getJson(with_counts, without=["max_age", "created_at"])
    return c_json(inv)


@app.route("/api/v9/invites/<string:invite>", methods=["POST"])
@multipleDecorators(usingDB, getUser, getInvite)
async def api_invites_invite_post(user, invite):
    channel = await core.getChannel(invite.channel_id)
    if user.id not in channel.recipients and len(channel.recipients) >= 10:
        raise InvalidDataErr(404, mkError(10006))
    inv = await invite.getJson(without=["max_age", "created_at"])
    if channel.type == ChannelType.GROUP_DM:
        inv["new_member"] = user.id not in channel.recipients
        if inv["new_member"]:
            msg = Message(id=mksf(), author=channel.owner_id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": user.id})
            await core.addUserToGroupDM(channel, user.id)
            await core.sendDMRepicientAddEvent(channel.recipients, channel.id, user.id)
            await core.sendMessage(msg)
        await core.sendDMChannelCreateEvent(channel, users=[user.id])
    #elif channel.guild_id:
    #    guild = await core.getGuild(channel.guild_id)
    #    inv["new_member"] = not await core.getGuildMember(GuildId(channel.guild_id), user.id)
    #    if inv["new_member"]:
    #        msg = Message(id=mksf(), author=user.id, channel_id=channel.id, content="", type=MessageType.USER_JOIN)
    #        member = await core.addUserToGuild(guild, user.id)
    #        #await core.sendMessage(msg)
    #    #await core.sendGuildCreateEvent(channel, users=[user.id])
    return c_json(inv)


# Guilds


@app.route("/api/v9/guilds", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_guilds_post(user):
    data = await request.get_json()
    guild = await core.createGuild(user, data["name"])
    Ctx["with_channels"] = True
    return c_json(await guild.json)


@app.route("/api/v9/guilds/<int:guild>", methods=["PATCH"])
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_patch(user, guild):
    if guild.owner_id != user.id: # TODO: check permissions
        raise InvalidDataErr(403, mkError(50013))
    data = await request.get_json()
    for j in ("id", "owner_id", "features", "emojis", "stickers", "roles", "max_members"):
        if j in data: del data[j]
    if "icon" in data:
        img = data["icon"]
        del data["icon"]
        if (img := getImage(img)) or not validImage(img):
            if h := await cdn.setGuildIconFromBytesIO(guild.id, img):
                data["icon"] = h
    nguild = guild.copy()
    nguild.set(**data)
    await core.updateGuildDiff(guild, nguild)
    return c_json(await nguild.json)


@app.route("/api/v9/guilds/<int:guild>/templates", methods=["GET"])
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_templates_get(user, guild):
    return c_json([])


@app.route("/api/v9/guilds/<int:guild>/emojis", methods=["GET"])
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_emojis_get(user, guild):
    emojis = await core.getEmojis(guild.id)
    Ctx["with_user"] = True
    emojis = [await emoji.json for emoji in emojis]
    return c_json(emojis)


@app.route("/api/v9/guilds/<int:guild>/emojis", methods=["POST"])
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_emojis_post(user, guild):
    if guild.owner_id != user.id: # TODO: check permissions
        raise InvalidDataErr(403, mkError(50013))
    data = await request.get_json()
    if not data.get("image"):
        raise InvalidDataErr(400, mkError(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not data.get("name"):
        raise InvalidDataErr(400, mkError(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not (img := getImage(data["image"])) or not validImage(img):
        raise InvalidDataErr(400, mkError(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    eid = mksf()
    if not (emd := await cdn.setEmojiFromBytesIO(eid, img)):
        raise InvalidDataErr(400, mkError(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    emoji = Emoji(eid, data["name"], user.id, guild.id, animated=emd["animated"])
    await core.addEmoji(emoji, guild)
    emoji.fill_defaults()
    return c_json(await emoji.json)


@app.route("/api/v9/guilds/<int:guild>/emojis/<int:emoji>", methods=["DELETE"])
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def api_guilds_guild_emojis_emoji_delete(user, guild, emoji):
    if guild.owner_id != user.id: # TODO: check permissions
        raise InvalidDataErr(403, mkError(50013))
    emoji = await core.getEmoji(emoji)
    if not emoji:
        return "", 204
    if emoji.guild_id != guild.id:
        return "", 204
    await core.deleteEmoji(emoji, guild)
    return "", 204


# Stickers & gifs


@app.route("/api/v9/sticker-packs", methods=["GET"])
async def api_stickerpacks_get():
    return c_json('{"sticker_packs": []}') # TODO


@app.route("/api/v9/gifs/trending", methods=["GET"])
async def api_gifs_trending_get():
    return c_json('{"gifs": [], "categories": []}') # TODO


# Hypesquad


@app.route("/api/v9/hypesquad/online", methods=["POST"])
@multipleDecorators(usingDB, getUser)
async def api_hypesquad_online(user):
    data = await request.get_json()
    if not (house_id := data.get("house_id")):
        raise InvalidDataErr(400, mkError(50035, {"house_id": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if house_id not in (1, 2, 3):
        raise InvalidDataErr(400, mkError(50035, {"house_id": {"code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (1, 2, 3)."}}))
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


@app.route("/api/v9/auth/location-metadata", methods=["GET"])
async def api_auth_locationmetadata():
    return c_json("{\"consent_required\": false, \"country_code\": \"US\", \"promotional_email_opt_in\": {\"required\": true, \"pre_checked\": false}}")


@app.route("/api/v9/science", methods=["POST"])
async def api_science():
    return "", 204


@app.route("/api/v9/experiments", methods=["GET"])
async def api_experiments():
    return c_json("{\"fingerprint\":\"0.A\",\"assignments\":[],\"guild_experiments\":[]}")


@app.route("/api/v9/applications/detectable", methods=["GET"])
async def api_applications_detectable():
    return c_json("[]")

@app.route("/api/v9/users/@me/survey", methods=["GET"])
async def api_users_me_survey():
    return c_json("{\"survey\":null}")


@app.route("/api/v9/users/@me/affinities/guilds", methods=["GET"])
async def api_users_me_affinities_guilds():
    return c_json("{\"guild_affinities\":[]}")


@app.route("/api/v9/users/@me/affinities/users", methods=["GET"])
async def api_users_me_affinities_users():
    return c_json("{\"user_affinities\":[],\"inverse_user_affinities\":[]}")


@app.route("/api/v9/users/@me/library", methods=["GET"])
async def api_users_me_library():
    return c_json("[]")


@app.route("/api/v9/users/@me/billing/payment-sources", methods=["GET"])
async def api_users_me_billing_paymentsources():
    return c_json("[]")


@app.route("/api/v9/users/@me/billing/country-code", methods=["GET"])
async def api_users_me_billing_countrycode():
    return c_json("{\"country_code\": \"US\"}")


@app.route("/api/v9/users/@me/billing/localized-pricing-promo", methods=["GET"])
async def api_users_me_billing_localizedpricingpromo():
    return c_json("{\"country_code\": \"US\", \"localized_pricing_promo\": null}")


@app.route("/api/v9/users/@me/billing/user-trial-offer", methods=["GET"])
async def api_users_me_billing_usertrialoffer():
    return c_json("{\"message\": \"404: Not Found\", \"code\": 0}", 404)


@app.route("/api/v9/users/@me/billing/subscriptions", methods=["GET"])
async def api_users_me_billing_subscriptions():
    return c_json("[{\"items\": [{\"id\": 1, \"plan_id\": 511651880837840896, \"quantity\": 1200}], \"id\": 1, \"type\": 2, \"created_at\": 1640995200000, \"canceled_at\": null, \"current_period_start\": 1640995200000, \"current_period_end\": 4794595201000, \"status\": \"idk\", \"payment_source_id\": 0, \"payment_gateway\": null, \"payment_gateway_plan_id\": null, \"payment_gateway_subscription_id\": null, \"trial_id\": null, \"trial_ends_at\": null, \"renewal_mutations\": null, \"streak_started_at\": 1640995200000, \"currency\": \"USD\", \"metadata\": null}]")


@app.route("/api/v9/users/@me/billing/subscription-slots", methods=["GET"])
async def api_users_me_billing_subscriptionslots():
    return c_json("[]")


@app.route("/api/v9/users/@me/guilds/premium/subscription-slots", methods=["GET"])
async def api_users_me_guilds_premium_subscriptionslots():
    return c_json("[]")


@app.route("/api/v9/outbound-promotions", methods=["GET"])
async def api_outboundpromotions():
    return c_json("[]")


@app.route("/api/v9/users/@me/applications/<aid>/entitlements", methods=["GET"])
async def api_users_me_applications_id_entitlements(aid):
    return c_json("[]")


@app.route("/api/v9/store/published-listings/skus/<int:sku>/subscription-plans", methods=["GET"])
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


@app.route("/api/v9/users/@me/outbound-promotions/codes", methods=["GET"])
async def api_users_me_outboundpromotions_codes():
    return c_json("[]")


@app.route("/api/v9/users/@me/entitlements/gifts", methods=["GET"])
async def api_users_me_entitlements_gifts():
    return c_json("[]")


@app.route("/api/v9/users/@me/activities/statistics/applications", methods=["GET"])
async def api_users_me_activities_statistics_applications():
    return c_json("[]")


@app.route("/api/v9/users/@me/billing/payments", methods=["GET"])
async def api_users_me_billing_payments():
    return c_json("[]")


@app.route("/api/v9/users/@me/settings-proto/3", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_3():
    return c_json("{\"settings\": \"\"}")


@app.route("/api/v9/users/@me/settings-proto/<int:t>", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_type(t):
    raise InvalidDataErr(400, mkError(50013, {"type": {"code": "BASE_TYPE_CHOICES", "message": "Value must be one of (<UserSettingsTypes.PRELOADED_USER_SETTINGS: 1>, <UserSettingsTypes.FRECENCY_AND_FAVORITES_SETTINGS: 2>, <UserSettingsTypes.TEST_SETTINGS: 3>)."}}))


# OAuth


@app.route("/api/v9/oauth2/tokens", methods=["GET"])
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
    return "Not Implemented!", 502


if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8000, reload=True, use_colors=False)