from base64 import b64encode as _b64encode, b64decode as _b64decode
from random import choice

from quart import Blueprint, request

from ..utils import usingDB, getSession, getUser, multipleDecorators, getGuildWM
from ...yepcord.classes.guild import Guild
from ...yepcord.classes.user import Session, User, GuildMember, UserSettings, UserNote, UserData
from ...yepcord.ctx import getCore, getCDNStorage
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.proto import FrecencyUserSettings, PreloadedUserSettings
from ...yepcord.responses import userSettingsResponse, userConsentResponse, userdataResponse, channelInfoResponse
from ...yepcord.utils import c_json, execute_after, MFA, validImage, getImage

# Base path is /api/vX/users/@me
users_me = Blueprint('users_@me', __name__)


@users_me.get("/", strict_slashes=False)
@multipleDecorators(usingDB, getUser)
async def get_me(user: User):
    return c_json(await userdataResponse(user))


@users_me.patch("/", strict_slashes=False)
@multipleDecorators(usingDB, getUser)
async def update_me(user: User):
    data = await user.data
    _settings = await request.get_json()
    d = "discriminator" in _settings and _settings.get("discriminator") != data.discriminator
    u = "username" in _settings and _settings.get("username") != data.username
    if d or u:
        if "password" not in _settings or not await getCore().checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        if u:
            await getCore().changeUserName(user, str(_settings["username"]))
            del _settings["username"]
        if d:
            if not await getCore().changeUserDiscriminator(user, int(_settings["discriminator"])):
                if u:
                    return c_json(await userdataResponse(user))
                raise InvalidDataErr(400, Errors.make(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This discriminator already used by someone. Please enter something else."}}))
            del _settings["discriminator"]
    if "new_password" in _settings:
        if "password" not in _settings or not await getCore().checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await getCore().changeUserPassword(user, _settings["new_password"])
        del _settings["new_password"]
    if "email" in _settings:
        if "password" not in _settings or not await getCore().checkUserPassword(user, _settings["password"]):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
        await getCore().changeUserEmail(user, _settings["email"])
        await getCore().sendVerificationEmail(user)
        del _settings["email"]
    if "password" in _settings: del _settings["password"]

    settings = {}
    for k,v in _settings.items():
        k = k.lower()
        if k == "avatar":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await getCDNStorage().setAvatarFromBytesIO(user.id, img)):
                continue
        elif k == "banner": # TODO: remove
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await getCDNStorage().setBannerFromBytesIO(user.id, img)):
                continue
        settings[k] = v
    if settings:
        if "uid" in settings: del settings["uid"]
        await getCore().setUserdata(UserData(user.id, **settings))
    await getCore().sendUserUpdateEvent(user.id)
    return c_json(await userdataResponse(user))


@users_me.patch("/profile")
@multipleDecorators(usingDB, getUser)
async def get_my_profile(user: User):
    _settings = await request.get_json()
    settings = {}
    for k, v in _settings.items():
        if k == "banner":
            if not (img := getImage(v)) or not validImage(img):
                continue
            if not (v := await getCDNStorage().setBannerFromBytesIO(user.id, img)):
                continue
        settings[k] = v
    if settings:
        if "uid" in settings: del settings["uid"]
        await getCore().setUserdata(UserData(user.id, **settings))
    await getCore().sendUserUpdateEvent(user.id)
    return c_json(await userdataResponse(user))


@users_me.get("/consent")
@multipleDecorators(usingDB, getUser)
async def get_consent_settings(user: User):
    return c_json(await userConsentResponse(user))


@users_me.post("/consent")
@multipleDecorators(usingDB, getUser)
async def update_consent_settings(user: User):
    data = await request.get_json()
    if data["grant"] or data["revoke"]:
        settings = {}
        for g in data.get("grant", []):
            settings[g] = True
        for r in data.get("revoke", []):
            settings[r] = False
        if "uid" in settings: del settings["uid"]
        s = UserSettings(user.id, **settings)
        await getCore().setSettings(s)
    return c_json(await userConsentResponse(user))


@users_me.get("/settings")
@multipleDecorators(usingDB, getUser)
async def get_settings(user: User):
    return c_json(await userSettingsResponse(user))


@users_me.patch("/settings")
@multipleDecorators(usingDB, getUser)
async def update_settings(user: User):
    settings = await request.get_json()
    if "uid" in settings: del settings["uid"]
    s = UserSettings(user.id, **settings)
    await getCore().setSettings(s)
    await getCore().sendUserUpdateEvent(user.id)
    return c_json(await userSettingsResponse(user))


@users_me.get("/settings-proto/1")
@multipleDecorators(usingDB, getUser)
async def get_protobuf_settings(user: User):
    proto = await user.settings_proto
    return c_json({"settings": _b64encode(proto.SerializeToString()).decode("utf8")})


@users_me.patch("/settings-proto/1")
@multipleDecorators(usingDB, getUser)
async def update_protobuf_settings(user: User):
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
    await getCore().setSettingsDiff(settings_old, settings)
    user._uSettings = None
    settings = await user.settings
    proto = _b64encode(settings.to_proto().SerializeToString()).decode("utf8")
    await getCore().sendSettingsProtoUpdateEvent(user.id, proto, 1)
    return c_json({"settings": proto})


@users_me.get("/settings-proto/2")
@multipleDecorators(usingDB, getUser)
async def get_protobuf_frecency_settings(user: User):
    proto = await user.frecency_settings_proto
    return c_json({"settings": _b64encode(proto).decode("utf8")})


@users_me.patch("/settings-proto/2")
@multipleDecorators(usingDB, getUser)
async def update_protobuf_frecency_settings(user: User):
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
    await getCore().setFrecencySettings(user.id, proto)
    await getCore().sendSettingsProtoUpdateEvent(user.id, proto, 2)
    return c_json({"settings": proto})


@users_me.get("/connections")
@multipleDecorators(usingDB, getUser)
async def get_connections(user: User): # TODO: add connections
    return c_json("[]")


@users_me.post("/relationships")
@multipleDecorators(usingDB, getUser)
async def new_relationship(user: User):
    udata = await request.get_json()
    udata["discriminator"] = int(udata["discriminator"])
    if not (rUser := await getCore().getUserByUsername(**udata)):
        raise InvalidDataErr(400, Errors.make(80004))
    if rUser == user:
        raise InvalidDataErr(400, Errors.make(80007))
    await getCore().checkRelationShipAvailable(rUser, user)
    await getCore().reqRelationship(rUser, user)
    return "", 204


@users_me.get("/relationships")
@multipleDecorators(usingDB, getUser)
async def get_relationships(user: User):
    return c_json(await getCore().getRelationships(user, with_data=True))


@users_me.get("/notes/<int:target_uid>")
@multipleDecorators(usingDB, getUser)
async def get_notes(user: User, target_uid: int):
    if not (note := await getCore().getUserNote(user.id, target_uid)):
        raise InvalidDataErr(404, Errors.make(10013))
    return c_json(note.toJSON())


@users_me.put("/notes/<int:target_uid>")
@multipleDecorators(usingDB, getUser)
async def set_notes(user: User, target_uid: int):
    data = await request.get_json()
    if note := data.get("note"):
        await getCore().putUserNote(UserNote(user.id, target_uid, note))
    return "", 204


@users_me.post("/mfa/totp/enable")
@multipleDecorators(usingDB, getSession)
async def enable_mfa(session: Session):
    data = await request.get_json()
    user = await getCore().getUser(session.uid)
    if not (password := data.get("password")) or not await getCore().checkUserPassword(user, password):
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
    await getCore().setSettings(UserSettings(session.id, mfa=secret))
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await getCore().setBackupCodes(session, codes)
    await execute_after(getCore().sendUserUpdateEvent(session.id), 2)
    codes = [{"user_id": str(session.id), "code": code, "consumed": False} for code in codes]
    await getCore().logoutUser(session)
    session = await getCore().createSession(session.id)
    return c_json({"token": session.token, "backup_codes": codes})


@users_me.post("/mfa/totp/disable")
@multipleDecorators(usingDB, getSession)
async def disable_mfa(session: Session):
    data = await request.get_json()
    if not (code := data.get("code")):
        raise InvalidDataErr(400, Errors.make(60008))
    user = await getCore().getUser(session.id)
    if not (mfa := await getCore().getMfa(user)):
        raise InvalidDataErr(400, Errors.make(50018))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await getCore().useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, Errors.make(60008))
    await getCore().setSettings(UserSettings(session.id, mfa=None))
    await getCore().clearBackupCodes(session)
    await getCore().sendUserUpdateEvent(session.id)
    await getCore().logoutUser(session)
    session = await getCore().createSession(session.id)
    return c_json({"token": session.token})


@users_me.post("/mfa/codes-verification")
@multipleDecorators(usingDB, getUser)
async def get_backup_codes(user: User):
    data = await request.get_json()
    if not (nonce := data.get("nonce")):
        raise InvalidDataErr(400, Errors.make(60011))
    if not (key := data.get("key")):
        raise InvalidDataErr(400, Errors.make(50035, {"key": {"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}}))
    reg = data.get("regenerate", False)
    await getCore().verifyUserMfaNonce(user, nonce, reg)
    if await getCore().mfaNonceToCode(user, nonce) != key:
        raise InvalidDataErr(400, Errors.make(60011))
    if reg:
        codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
        await getCore().setBackupCodes(user, codes)
        codes = [{"user_id": str(user.id), "code": code, "consumed": False} for code in codes]
    else:
        _codes = await getCore().getBackupCodes(user)
        codes = []
        for code, used in _codes:
            codes.append({"user_id": str(user.id), "code": code, "consumed": bool(used)})
    return c_json({"backup_codes": codes})


@users_me.put("/relationships/<int:uid>")
@multipleDecorators(usingDB, getUser)
async def accept_relationship_or_block(uid: int, user: User):
    data = await request.get_json()
    if not data or "type" not in data:
        await getCore().accRelationship(user, uid)
    elif data["type"] == 2:
        await getCore().blockUser(user, uid)
    return "", 204


@users_me.delete("/relationships/<int:uid>")
@multipleDecorators(usingDB, getUser)
async def delete_relationship(uid: int, user: User):
    await getCore().delRelationship(user, uid)
    return "", 204


@users_me.get("/harvest")
@multipleDecorators(usingDB, getUser)
async def api_users_me_harvest(user: User):
    return "", 204


@users_me.delete("/guilds/<int:guild>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def leave_guild(user: User, guild: Guild, member: GuildMember):
    if member.id == guild.owner_id:
        raise InvalidDataErr(400, Errors.make(50055))
    await getCore().deleteGuildMember(member)
    await getCore().sendGuildMemberRemoveEvent(guild, await member.user)
    await getCore().sendGuildDeleteEvent(guild, member)
    return "", 204


@users_me.get("/api/v9/users/@me/channels")
@multipleDecorators(usingDB, getUser)
async def get_dm_channels(user: User):
    return c_json(await getCore().getPrivateChannels(user))


@users_me.post("/api/v9/users/@me/channels")
@multipleDecorators(usingDB, getUser)
async def new_dm_channel(user: User):
    data = await request.get_json()
    rep = data.get("recipients", [])
    rep = [int(r) for r in rep]
    if len(rep) == 1:
        if int(rep[0]) == user.id:
            raise InvalidDataErr(400, Errors.make(50007))
        ch = await getCore().getDMChannelOrCreate(user.id, rep[0])
    elif len(rep) == 0:
        ch = await getCore().createDMGroupChannel(user, [])
    else:
        if user.id in rep:
            rep.remove(user.id)
        if len(rep) == 0:
            raise InvalidDataErr(400, Errors.make(50007))
        elif len(rep) == 1:
            ch = await getCore().getDMChannelOrCreate(user.id, rep[0])
        else:
            ch = await getCore().createDMGroupChannel(user, rep)
    await getCore().sendDMChannelCreateEvent(ch)
    return c_json(await channelInfoResponse(ch, user, ids=False))
