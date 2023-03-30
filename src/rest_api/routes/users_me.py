from base64 import b64encode as _b64encode, b64decode as _b64decode
from random import choice

from quart import Blueprint
from quart_schema import validate_request, validate_querystring

from ..models.users_me import UserUpdate, UserProfileUpdate, ConsentSettingsUpdate, SettingsUpdate, SettingsProtoUpdate, \
    RelationshipRequest, PutNote, MfaEnable, MfaDisable, MfaCodesVerification, RelationshipPut, DmChannelCreate, \
    DeleteRequest, GetScheduledEventsQuery
from ..utils import usingDB, getUser, multipleDecorators, getSession, getGuildWM
from ...gateway.events import RelationshipAddEvent, DMChannelCreateEvent, RelationshipRemoveEvent, UserUpdateEvent, \
    UserNoteUpdateEvent, UserSettingsProtoUpdateEvent, GuildDeleteEvent, GuildMemberRemoveEvent
from ...yepcord.classes.guild import Guild, GuildId
from ...yepcord.classes.user import User, UserSettings, UserNote, Session, GuildMember, UserId
from ...yepcord.ctx import getCore, getCDNStorage, Ctx, getGw
from ...yepcord.enums import RelationshipType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.proto import FrecencyUserSettings, PreloadedUserSettings
from ...yepcord.utils import c_json, execute_after, MFA, validImage, getImage

# Base path is /api/vX/users/@me
users_me = Blueprint('users_@me', __name__)


@users_me.get("/", strict_slashes=False)
@multipleDecorators(usingDB, getUser)
async def get_me(user: User):
    userdata = await user.data
    return c_json(await userdata.full_json)


@users_me.patch("/", strict_slashes=False)
@multipleDecorators(validate_request(UserUpdate), usingDB, getUser)
async def update_me(data: UserUpdate, user: User):
    userdata = await user.data
    discrim = data.discriminator if data.discriminator and data.discriminator != userdata.discriminator else None
    username = data.username if data.username and data.username != userdata.username else None
    if discrim or username or data.new_password is not None or data.email is not None:
        if data.password is not None and not await getCore().checkUserPassword(user, data.password):
            raise InvalidDataErr(400, Errors.make(50035, {
                "password": {"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}}))
    if username:
        await getCore().changeUserName(user, username)
        data.username = None
    if discrim:
        if not await getCore().changeUserDiscriminator(user, discrim, bool(username)):
            return c_json(await userdata.full_json)
        data.discriminator = None
    if data.new_password is not None:
        await getCore().changeUserPassword(user, data.new_password)
        data.new_password = None
    if data.email is not None:
        await getCore().changeUserEmail(user, data.email)
        await getCore().sendVerificationEmail(user)
        data.email = None
    if data.password is not None: data.password = None
    if data.avatar != "":
        if data.avatar is not None:
            if (img := getImage(data.avatar)) and validImage(img):
                if avatar := await getCDNStorage().setAvatarFromBytesIO(user.id, img):
                    data.avatar = avatar

    user = await getCore().getUser(user.id) # Get new version of User, UserData, UserSettings
    userdata = await user.data
    new_userdata = userdata.copy()
    if data.json:
        new_userdata.set(**data.to_json)
        await getCore().setUserdataDiff(userdata, new_userdata)
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return c_json(await new_userdata.full_json)


@users_me.patch("/profile")
@multipleDecorators(validate_request(UserProfileUpdate), usingDB, getUser)
async def get_my_profile(data: UserProfileUpdate, user: User):
    if data.banner != "":
        if data.banner is not None:
            if (img := getImage(data.banner)) and validImage(img):
                if banner := await getCDNStorage().setBannerFromBytesIO(user.id, img):
                    data.banner = banner

    userdata = await user.data
    new_userdata = userdata.copy(**data.to_json)
    await getCore().setUserdataDiff(userdata, new_userdata)
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return c_json(await new_userdata.full_json)


@users_me.get("/consent")
@multipleDecorators(usingDB, getUser)
async def get_consent_settings(user: User):
    settings = await user.settings
    return c_json(settings.consent_json)


@users_me.post("/consent")
@multipleDecorators(validate_request(ConsentSettingsUpdate), usingDB, getUser)
async def update_consent_settings(data: ConsentSettingsUpdate, user: User):
    ALLOWED_SETTINGS = ("personalization", "usage_statistics")
    settings = await user.settings
    new_settings = settings
    if data.grant or data.revoke:
        new_settings = {}
        for grant in data.grant:
            if grant not in ALLOWED_SETTINGS: continue
            new_settings[grant] = True
        for revoke in data.revoke:
            if revoke not in ALLOWED_SETTINGS: continue
            new_settings[revoke] = False
        new_settings = settings.copy(**new_settings)
        await getCore().setSettingsDiff(settings, new_settings)
    return c_json(new_settings.consent_json)


@users_me.get("/settings")
@multipleDecorators(usingDB, getUser)
async def get_settings(user: User):
    settings = await user.settings
    return c_json(await settings.json)


@users_me.patch("/settings")
@multipleDecorators(validate_request(SettingsUpdate), usingDB, getUser)
async def update_settings(data: SettingsUpdate, user: User):
    settings = await user.settings
    new_settings = settings.copy(**data.to_json)
    await getCore().setSettingsDiff(settings, new_settings)
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return c_json(await new_settings.json)


@users_me.get("/settings-proto/1")
@multipleDecorators(usingDB, getUser)
async def get_protobuf_settings(user: User):
    proto = await user.settings_proto
    return c_json({"settings": _b64encode(proto.SerializeToString()).decode("utf8")})


@users_me.patch("/settings-proto/1")
@multipleDecorators(validate_request(SettingsProtoUpdate), usingDB, getUser)
async def update_protobuf_settings(data: SettingsProtoUpdate, user: User):
    if not data.settings:
        raise InvalidDataErr(400, Errors.make(50035, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto = PreloadedUserSettings()
        proto.ParseFromString(_b64decode(data.settings.encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, Errors.make(50104))
    settings = await user.settings
    new_settings = settings.copy()
    new_settings.from_proto(proto)
    await getCore().setSettingsDiff(settings, new_settings)
    proto = _b64encode(new_settings.to_proto().SerializeToString()).decode("utf8")
    await execute_after(getGw().dispatch(UserSettingsProtoUpdateEvent(proto, 1), users=[user.id]), 1)
    return c_json({"settings": proto})


@users_me.get("/settings-proto/2")
@multipleDecorators(usingDB, getUser)
async def get_protobuf_frecency_settings(user: User):
    proto = await user.frecency_settings_proto
    return c_json({"settings": _b64encode(proto).decode("utf8")})


@users_me.patch("/settings-proto/2")
@multipleDecorators(validate_request(SettingsProtoUpdate), usingDB, getUser)
async def update_protobuf_frecency_settings(data: SettingsProtoUpdate, user: User):
    if not data.settings:
        raise InvalidDataErr(400, Errors.make(50035, {"settings": {"code": "BASE_TYPE_REQUIRED", "message": "Required field."}}))
    try:
        proto_new = FrecencyUserSettings()
        proto_new.ParseFromString(_b64decode(data.settings.encode("utf8")))
    except ValueError:
        raise InvalidDataErr(400, Errors.make(50104))
    proto = FrecencyUserSettings()
    proto.ParseFromString(await user.frecency_settings_proto)
    proto.MergeFrom(proto_new)
    proto = proto.SerializeToString()
    proto = _b64encode(proto).decode("utf8")
    await getCore().setFrecencySettings(user.id, proto)
    await execute_after(getGw().dispatch(UserSettingsProtoUpdateEvent(proto, 2), users=[user.id]), 1)
    return c_json({"settings": proto})


@users_me.get("/connections")
@multipleDecorators(usingDB, getUser)
async def get_connections(user: User): # TODO: add connections
    return c_json("[]")


@users_me.post("/relationships")
@multipleDecorators(validate_request(RelationshipRequest), usingDB, getUser)
async def new_relationship(data: RelationshipRequest, user: User):
    if not (target_user := await getCore().getUserByUsername(**data.dict())):
        raise InvalidDataErr(400, Errors.make(80004))
    if target_user == user:
        raise InvalidDataErr(400, Errors.make(80007))
    await getCore().checkRelationShipAvailable(target_user, user)
    await getCore().reqRelationship(target_user, user)

    await getGw().dispatch(RelationshipAddEvent(user.id, await user.userdata, 3), [target_user.id])
    await getGw().dispatch(RelationshipAddEvent(target_user.id, await target_user.userdata, 4), [user.id])

    return "", 204


@users_me.get("/relationships")
@multipleDecorators(usingDB, getUser)
async def get_relationships(user: User):
    return c_json(await getCore().getRelationships(user, with_data=True))


@users_me.get("/notes/<int:target_uid>")
@multipleDecorators(usingDB, getUser)
async def get_notes(user: User, target_uid: int):
    if not await getCore().getUser(target_uid, False):
        raise InvalidDataErr(404, Errors.make(10013))
    if not (note := await getCore().getUserNote(user.id, target_uid)):
        raise InvalidDataErr(404, Errors.make(10013))
    return c_json(note.toJSON())


@users_me.put("/notes/<int:target_uid>")
@multipleDecorators(validate_request(PutNote), usingDB, getUser)
async def set_notes(data: PutNote, user: User, target_uid: int):
    if not await getCore().getUser(target_uid, False):
        raise InvalidDataErr(404, Errors.make(10013))
    if data.note:
        await getCore().putUserNote(UserNote(user.id, target_uid, data.note))
        await getGw().dispatch(UserNoteUpdateEvent(target_uid, data.note), users=[user.id])
    return "", 204


@users_me.post("/mfa/totp/enable")
@multipleDecorators(validate_request(MfaEnable), usingDB, getSession)
async def enable_mfa(data: MfaEnable, session: Session): # TODO: Check if mfa already enabled
    user = await getCore().getUser(session.uid)
    if not (password := data.password) or not await getCore().checkUserPassword(user, password):
        raise InvalidDataErr(400, Errors.make(50018))
    if not (secret := data.secret):
        raise InvalidDataErr(400, Errors.make(60005))
    mfa = MFA(secret, session.id)
    if not mfa.valid:
        raise InvalidDataErr(400, Errors.make(60005))
    if not (code := data.code):
        raise InvalidDataErr(400, Errors.make(60008))
    if mfa.getCode() != code:
        raise InvalidDataErr(400, Errors.make(60008))
    await getCore().setSettings(UserSettings(session.id, mfa=secret))
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await getCore().setBackupCodes(session, codes)
    await execute_after(getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id]), 1.5)
    codes = [{"user_id": str(session.id), "code": code, "consumed": False} for code in codes]
    await getCore().logoutUser(session)
    session = await getCore().createSession(session.id)
    return c_json({"token": session.token, "backup_codes": codes})


@users_me.post("/mfa/totp/disable")
@multipleDecorators(validate_request(MfaDisable), usingDB, getSession)
async def disable_mfa(data: MfaDisable, session: Session):
    if not (code := data.code):
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
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    await getCore().logoutUser(session)
    session = await getCore().createSession(session.id)
    return c_json({"token": session.token})


@users_me.post("/mfa/codes-verification")
@multipleDecorators(validate_request(MfaCodesVerification), usingDB, getUser)
async def get_backup_codes(data: MfaCodesVerification, user: User):
    if not (nonce := data.nonce):
        raise InvalidDataErr(400, Errors.make(60011))
    if not (key := data.key):
        raise InvalidDataErr(400, Errors.make(50035, {"key": {"code": "BASE_TYPE_REQUIRED", "message": "This field is required"}}))
    reg = data.regenerate
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
@multipleDecorators(validate_request(RelationshipPut), usingDB, getUser)
async def accept_relationship_or_block(data: RelationshipPut, uid: int, user: User):
    if not (target_user_data := await getCore().getUserData(UserId(uid))):
        raise InvalidDataErr(404, Errors.make(10013))
    if not data.type:
        await getCore().accRelationship(user, uid)
        await getGw().dispatch(RelationshipAddEvent(user.id, await user.data, 1), [uid])
        await getGw().dispatch(RelationshipAddEvent(uid, target_user_data, 1), [user.id])
        channel = await getCore().getDMChannelOrCreate(user.id, uid)
        Ctx["with_ids"] = False
        Ctx["user_id"] = uid
        await getGw().dispatch(DMChannelCreateEvent(channel), [uid])
        Ctx["user_id"] = user.id
        await getGw().dispatch(DMChannelCreateEvent(channel), [user.id])
    elif data.type == 2:
        if relationship := await getCore().getRelationship(user.id, uid):
            rel_type_current = relationship.discord_type(user.id)
            rel_type_target = relationship.discord_type(uid)
            await getGw().dispatch(RelationshipRemoveEvent(uid, rel_type_current), [user.id])
            await getGw().dispatch(RelationshipRemoveEvent(user.id, rel_type_target), [uid])
        await getCore().blockUser(user, uid)
        await getGw().dispatch(RelationshipAddEvent(uid, target_user_data, RelationshipType.BLOCK), [user.id])
    return "", 204


@users_me.delete("/relationships/<int:uid>")
@multipleDecorators(usingDB, getUser)
async def delete_relationship(uid: int, user: User):
    if relationship := await getCore().delRelationship(user, uid):
        rel_type_current = relationship.discord_type(user.id)
        rel_type_target = relationship.discord_type(uid)
        await getGw().dispatch(RelationshipRemoveEvent(uid, rel_type_current), [user.id])
        await getGw().dispatch(RelationshipRemoveEvent(user.id, rel_type_target), [uid])
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
    await getGw().dispatch(GuildMemberRemoveEvent(guild.id, await (await user.data).json), users=[user.id])
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[member.id])
    return "", 204


@users_me.get("/channels")
@multipleDecorators(usingDB, getUser)
async def get_dm_channels(user: User):
    channels = [await channel.json for channel in await getCore().getPrivateChannels(user)]
    return c_json(channels)


@users_me.post("/channels")
@multipleDecorators(validate_request(DmChannelCreate), usingDB, getUser)
async def new_dm_channel(data: DmChannelCreate, user: User):
    recipients = data.recipients
    recipients_users = [await getCore().getUser(recipient) for recipient in recipients]
    if None in recipients_users:
        raise InvalidDataErr(400, Errors.make(50033))
    if len(recipients) == 1:
        if int(recipients[0]) == user.id:
            raise InvalidDataErr(400, Errors.make(50007))
        channel = await getCore().getDMChannelOrCreate(user.id, recipients[0])
    elif len(recipients) == 0:
        channel = await getCore().createDMGroupChannel(user, [], data.name)
    else:
        if user.id in recipients:
            recipients.remove(user.id)
        if len(recipients) == 0:
            raise InvalidDataErr(400, Errors.make(50007))
        elif len(recipients) == 1:
            channel = await getCore().getDMChannelOrCreate(user.id, recipients[0])
        else:
            channel = await getCore().createDMGroupChannel(user, recipients, data.name)
    Ctx["with_ids"] = False
    await getGw().dispatch(DMChannelCreateEvent(channel), channel_id=channel.id)
    return c_json(await channel.json)


@users_me.post("/delete")
@multipleDecorators(validate_request(DeleteRequest), usingDB, getUser)
async def delete_user(data: DeleteRequest, user: User):
    if not await getCore().checkUserPassword(user, data.password):
        raise InvalidDataErr(400, Errors.make(50018))
    if await getCore().getUserOwnedGuilds(user) or await getCore().getUserOwnedGroups(user):
        raise InvalidDataErr(400, Errors.make(40011))
    await getCore().deleteUser(user)
    await getCore().sendUserDeleteEvent(user)
    return "", 204


@users_me.get("/scheduled-events")
@multipleDecorators(validate_querystring(GetScheduledEventsQuery), usingDB, getUser)
async def get_scheduled_events(query_args: GetScheduledEventsQuery, user: User):
    events = []
    for guild_id in query_args.guild_ids[:5]:
        if not await getCore().getGuildMember(GuildId(guild_id), user.id):
            raise InvalidDataErr(403, Errors.make(50001))
        for event_id in await getCore().getSubscribedScheduledEventIds(user, guild_id):
            events.append({
                "guild_scheduled_event_id": str(event_id),
                "user_id": str(user.id)  # current user or creator??
            })

    return c_json(events)