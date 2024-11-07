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

from base64 import b64encode as _b64encode, b64decode as _b64decode
from time import time
from typing import Union, Optional

from ..dependencies import DepUser, DepSession, DepGuildMember, DepGuild, DepUserO
from ..models.users_me import UserUpdate, UserProfileUpdate, ConsentSettingsUpdate, SettingsUpdate, PutNote, \
    RelationshipRequest, SettingsProtoUpdate, MfaEnable, MfaDisable, MfaCodesVerification, RelationshipPut, \
    DmChannelCreate, DeleteRequest, GetScheduledEventsQuery, RemoteAuthLogin, RemoteAuthFinish, RemoteAuthCancel, \
    EditConnection
from ..y_blueprint import YBlueprint
from ...gateway.events import RelationshipAddEvent, DMChannelCreateEvent, RelationshipRemoveEvent, UserUpdateEvent, \
    UserNoteUpdateEvent, UserSettingsProtoUpdateEvent, GuildDeleteEvent, GuildMemberRemoveEvent, UserDeleteEvent, \
    UserConnectionsUpdate
from ...yepcord.utils.mfa import MFA
from ...yepcord.config import Config
from ...yepcord.ctx import getGw
from ...yepcord.enums import RelationshipType, ChannelType, MfaNonceType
from ...yepcord.errors import InvalidDataErr, Errors, UnknownToken, UnknownUser, UnknownConnection, UnknownDiscordTag, \
    AlreadyFriends, MalformedUserSettings, Already2Fa, PasswordDoesNotMatch, Invalid2FaSecret, Invalid2FaCode, \
    NotYet2Fa, InvalidKey, InvalidGuild, InvalidRecipient, MustTransferGuildsBeforeDelete, MissingAccess
from ...yepcord.models import User, UserSettingsProto, FrecencySettings, UserNote, Session, UserData, Guild, \
    GuildMember, RemoteAuthSession, Relationship, Authorization, Bot, ConnectedAccount, GuildEvent, Channel
from ...yepcord.models.remote_auth_session import time_plus_150s
from ...yepcord.proto import FrecencyUserSettings, PreloadedUserSettings
from ...yepcord.storage import getStorage
from ...yepcord.utils import execute_after, validImage, getImage

# Base path is /api/vX/users/@me
users_me = YBlueprint('users_@me', __name__)


@users_me.get("/", strict_slashes=False, allow_bots=True, oauth_scopes=["identify"])
async def get_me(session: Union[Session, Authorization, Bot] = DepSession, user: User = DepUser):
    userdata = await user.data
    return await userdata.ds_json_full(isinstance(session, Authorization) and "email" not in session.scope_set)


@users_me.patch("/", strict_slashes=False, body_cls=UserUpdate)
async def update_me(data: UserUpdate, user: User = DepUser):
    userdata = await user.data
    discrim = data.discriminator if data.discriminator and data.discriminator != userdata.discriminator else None
    username = data.username if data.username and data.username != userdata.username else None
    if discrim or username or data.new_password is not None or data.email is not None:
        if data.password is not None and not user.check_password(data.password):
            raise InvalidDataErr(400, Errors.make(50035, {"password": {
                "code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."
            }}))
        data.password = None
    if username:
        await user.change_username(username)
        data.username = None
    if discrim:
        if not await user.change_discriminator(discrim, bool(username)):
            await userdata.refresh_from_db(fields=["username", "discriminator"])
            return await userdata.ds_json_full()
        data.discriminator = None
    if data.new_password is not None:
        await user.change_password(data.new_password)
        data.new_password = None
    if data.email is not None:
        await user.change_email(data.email)
        await user.send_verification_email()
        data.email = None
    if data.avatar != "" and data.avatar is not None:
        if (img := getImage(data.avatar)) and validImage(img):
            if avatar := await getStorage().setUserAvatar(user.id, img):
                data.avatar = avatar

    await userdata.refresh_from_db()
    await userdata.user.refresh_from_db()
    changes = data.model_dump(include={"avatar"}, exclude_defaults=True)
    if changes:
        await userdata.update(**changes)
    await getGw().dispatch(UserUpdateEvent(user, userdata, await user.settings), [user.id])
    return await userdata.ds_json_full()


@users_me.patch("/profile", body_cls=UserProfileUpdate)
async def get_my_profile(data: UserProfileUpdate, user: User = DepUser):
    if data.banner != "" and data.banner is not None:
        if (img := getImage(data.banner)) and validImage(img):
            if banner := await getStorage().setGuildBanner(user.id, img):
                data.banner = banner

    userdata = await user.data
    await userdata.update(**data.model_dump(exclude_defaults=True))
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return await userdata.ds_json_full()


@users_me.get("/consent")
async def get_consent_settings(user: User = DepUser):
    settings = await user.settings
    return settings.ds_json_consent()


@users_me.post("/consent", body_cls=ConsentSettingsUpdate)
async def update_consent_settings(data: ConsentSettingsUpdate, user: User = DepUser):
    ALLOWED_SETTINGS = ("personalization", "usage_statistics")
    settings = await user.settings
    if data.grant or data.revoke:
        new_settings = {}
        for grant in data.grant:
            if grant not in ALLOWED_SETTINGS: continue
            new_settings[grant] = True
        for revoke in data.revoke:
            if revoke not in ALLOWED_SETTINGS: continue
            new_settings[revoke] = False
        await settings.update(**new_settings)
    return settings.ds_json_consent()


@users_me.get("/settings")
async def get_settings(user: User = DepUser):
    settings = await user.settings
    return settings.ds_json()


@users_me.patch("/settings", body_cls=SettingsUpdate)
async def update_settings(data: SettingsUpdate, user: User = DepUser):
    settings = await user.settings
    await settings.update(**data.model_dump(exclude_defaults=True))
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return settings.ds_json()


@users_me.get("/settings-proto/1")
async def get_protobuf_settings(user: User = DepUser):
    proto = UserSettingsProto(await user.settings).get()
    return {"settings": _b64encode(proto.SerializeToString()).decode("utf8")}


@users_me.patch("/settings-proto/1", body_cls=SettingsProtoUpdate)
async def update_protobuf_settings(data: SettingsProtoUpdate, user: User = DepUser):
    if not data.settings:
        raise InvalidDataErr(400, Errors.make(50035, {"settings": {
            "code": "BASE_TYPE_REQUIRED", "message": "Required field."
        }}))
    try:
        proto = PreloadedUserSettings()
        proto.ParseFromString(_b64decode(data.settings.encode("utf8")))
    except ValueError:
        raise MalformedUserSettings
    settings = await user.settings
    settings_proto = UserSettingsProto(settings)
    await settings_proto.update(proto)
    proto = _b64encode(settings_proto.get().SerializeToString()).decode("utf8")
    await execute_after(getGw().dispatch(UserSettingsProtoUpdateEvent(proto, 1), user_ids=[user.id]), 1)
    return {"settings": proto}


@users_me.get("/settings-proto/2")
async def get_protobuf_frecency_settings(user: User = DepUser):
    proto = await FrecencySettings.get_or_none(id=user.id)
    return {"settings": proto.settings if proto is not None else ""}


@users_me.patch("/settings-proto/2", body_cls=SettingsProtoUpdate)
async def update_protobuf_frecency_settings(data: SettingsProtoUpdate, user: User = DepUser):
    if not data.settings:
        raise InvalidDataErr(400, Errors.make(50035, {"settings": {
            "code": "BASE_TYPE_REQUIRED", "message": "Required field."
        }}))
    try:
        proto_new = FrecencyUserSettings()
        proto_new.ParseFromString(_b64decode(data.settings.encode("utf8")))
    except ValueError:
        raise MalformedUserSettings
    fsettings, _ = await FrecencySettings.get_or_create(id=user.id, user=user, settings="")
    proto = fsettings.to_proto() if fsettings else FrecencyUserSettings()
    proto.MergeFrom(proto_new)
    proto_string = _b64encode(proto.SerializeToString()).decode("utf8")
    fsettings.settings = proto_string
    await fsettings.save(update_fields=["settings"])
    await execute_after(getGw().dispatch(UserSettingsProtoUpdateEvent(proto_string, 2), user_ids=[user.id]), 1)
    return {"settings": proto_string}


@users_me.get("/connections", oauth_scopes=["connections"])
async def get_connections(user: User = DepUser):
    connections = await ConnectedAccount.filter(user=user, verified=True)
    return [conn.ds_json() for conn in connections]


@users_me.patch("/connections/<string:service>/<string:ext_id>", body_cls=EditConnection)
async def edit_connection(service: str, ext_id: str, data: EditConnection, user: User = DepUser):
    if service not in Config.CONNECTIONS:
        raise InvalidDataErr(400, Errors.make(50035, {"provider_id": {
            "code": "ENUM_TYPE_COERCE", "message": f"Value '{service}' is not a valid enum value."
        }}))

    connection = await ConnectedAccount.get_or_none(user=user, service_id=ext_id, type=service, verified=True)
    if connection is None:
        raise UnknownConnection

    await connection.update(**data.model_dump(exclude_none=True))

    await getGw().dispatch(UserConnectionsUpdate(connection), user_ids=[user.id])
    return connection.ds_json()


@users_me.delete("/connections/<string:service>/<string:ext_id>")
async def delete_connection(service: str, ext_id: str, user: User = DepUser):
    if service not in Config.CONNECTIONS:
        raise InvalidDataErr(400, Errors.make(50035, {"provider_id": {
            "code": "ENUM_TYPE_COERCE", "message": f"Value '{service}' is not a valid enum value."
        }}))

    connection = await ConnectedAccount.get_or_none(user=user, service_id=ext_id, type=service, verified=True)
    if connection is None:
        raise UnknownConnection

    await connection.delete()
    await getGw().dispatch(UserConnectionsUpdate(connection), user_ids=[user.id])

    return "", 204


@users_me.post("/relationships", body_cls=RelationshipRequest)
async def new_relationship(data: RelationshipRequest, user: User = DepUser):
    if not (target_user := await User.y.getByUsername(**data.model_dump())):
        raise UnknownDiscordTag
    if target_user == user:
        raise AlreadyFriends
    await Relationship.utils.request(user, target_user)

    await getGw().dispatch(RelationshipAddEvent(user.id, await user.userdata, 3), [target_user.id])
    await getGw().dispatch(RelationshipAddEvent(target_user.id, await target_user.userdata, 4), [user.id])

    return "", 204


@users_me.get("/relationships", oauth_scopes=["relationships.read"])
async def get_relationships(user: User = DepUser):
    return [
        await relationship.ds_json(user, True)
        for relationship in await user.get_relationships()
    ]


@users_me.get("/notes/<int:target_uid>", allow_bots=True)
async def get_notes(target_uid: int, user: User = DepUser):
    if not (target_user := await User.y.get(target_uid, False)):
        raise UnknownUser
    if not (note := await UserNote.get_or_none(user=user, target=target_user).select_related("user", "target")):
        raise UnknownUser
    return note.ds_json()


@users_me.put("/notes/<int:target_uid>", body_cls=PutNote, allow_bots=True)
async def set_notes(data: PutNote, target_uid: int, user: User = DepUser):
    if not (target_user := await User.y.get(target_uid, False)):
        raise UnknownUser
    if data.note:
        note, _ = await UserNote.get_or_create(user=user, target=target_user, defaults={"text": data.note})
        await getGw().dispatch(UserNoteUpdateEvent(target_uid, data.note), user_ids=[user.id])
    return "", 204


@users_me.post("/mfa/totp/enable", body_cls=MfaEnable)
async def enable_mfa(data: MfaEnable, session: Session = DepSession):
    user = session.user
    settings = await user.settings
    if settings.mfa is not None:
        raise Already2Fa
    if not (password := data.password) or not user.check_password(password):
        raise PasswordDoesNotMatch
    if not (secret := data.secret):
        raise Invalid2FaSecret
    mfa = MFA(secret, user.id)
    if not mfa.valid:
        raise Invalid2FaSecret
    if not (code := data.code) or code not in mfa.get_codes():
        raise Invalid2FaCode
    settings.mfa = secret
    await settings.save(update_fields=["mfa"])
    codes = [
        {"user_id": str(user.id), "code": code, "consumed": False}
        for code in await user.create_backup_codes()
    ]
    await execute_after(getGw().dispatch(UserUpdateEvent(user, await user.data, settings), [user.id]), 1.5)
    await session.delete()
    session = await Session.Y.create(user)
    return {"token": session.token, "backup_codes": codes}


@users_me.post("/mfa/totp/disable", body_cls=MfaDisable)
async def disable_mfa(data: MfaDisable, session: Session = DepSession):
    if not (code := data.code):
        raise Invalid2FaCode
    user = session.user
    settings = await user.settings
    if settings.mfa is None:
        raise NotYet2Fa
    mfa = await user.mfa
    code = code.replace("-", "").replace(" ", "")
    if code not in mfa.get_codes():
        if not (len(code) == 8 and await user.use_backup_code(code)):
            raise Invalid2FaCode
    settings.mfa = None
    await settings.save(update_fields=["mfa"])
    await user.clear_backup_codes()
    await getGw().dispatch(UserUpdateEvent(user, await user.data, settings), [user.id])
    await session.delete()
    session = await Session.Y.create(user)
    return {"token": session.token}


@users_me.post("/mfa/codes-verification", body_cls=MfaCodesVerification)
async def get_backup_codes(data: MfaCodesVerification, user: User = DepUser):
    if not (nonce := data.nonce):
        raise InvalidKey
    if not (key := data.key):
        raise InvalidDataErr(400, Errors.make(50035, {"key": {
            "code": "BASE_TYPE_REQUIRED", "message": "This field is required"
        }}))
    regenerate = data.regenerate
    await user.verify_mfa_nonce(nonce, MfaNonceType.REGENERATE if regenerate else MfaNonceType.NORMAL)
    if await MFA.nonce_to_code(nonce) != key:
        raise InvalidKey

    codes = await user.create_backup_codes() if regenerate else await user.get_backup_codes()
    return {"backup_codes": [
        {"user_id": str(user.id), "code": code, "consumed": False}
        for code in codes
    ]}


@users_me.put("/relationships/<int:user_id>", body_cls=RelationshipPut)
async def accept_relationship_or_block(data: RelationshipPut, user_id: int, user: User = DepUser):
    if not (target_user_data := await UserData.get_or_none(id=user_id).select_related("user")):
        raise UnknownUser
    if not data.type or data.type == 1:
        from_user = target_user_data.user

        if not await Relationship.utils.accept(from_user, user):
            await Relationship.utils.request(user, from_user)

            await getGw().dispatch(RelationshipAddEvent(user.id, await user.userdata, 3), [from_user.id])
            await getGw().dispatch(RelationshipAddEvent(from_user.id, await from_user.userdata, 4), [user.id])
        else:
            await getGw().dispatch(RelationshipAddEvent(user.id, await user.data, 1), [user_id])
            await getGw().dispatch(RelationshipAddEvent(user_id, target_user_data, 1), [user.id])
            channel = await Channel.Y.get_dm(user, target_user_data.user)
            await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": user_id}), [user_id])
            await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": user.id}), [user.id])
    elif data.type == 2:
        block_user = target_user_data.user
        result = await Relationship.utils.block(user, block_user)
        for d in result["delete"]:
            await getGw().dispatch(RelationshipRemoveEvent(d["rel"], d["type"]), [d["id"]])
        if result["block"]:
            await getGw().dispatch(RelationshipAddEvent(user_id, target_user_data, RelationshipType.BLOCK), [user.id])

    return "", 204


@users_me.delete("/relationships/<int:user_id>")
async def delete_relationship(user_id: int, user: User = DepUser):
    if (target_user := await User.y.get(user_id)) is None:
        return "", 204
    result = await Relationship.utils.delete(user, target_user)
    for d in result["delete"]:
        await getGw().dispatch(RelationshipRemoveEvent(d["rel"], d["type"]), [d["id"]])
    return "", 204


@users_me.get("/harvest")
async def api_users_me_harvest():
    return "", 204


@users_me.delete("/guilds/<int:guild>", allow_bots=True)
async def leave_guild(user: User = DepUser, guild: Guild = DepGuild, member: GuildMember = DepGuildMember):
    if user == guild.owner:
        raise InvalidGuild
    await getGw().dispatchUnsub([user.id], guild.id)
    for role in await member.roles.all():
        await getGw().dispatchUnsub([user.id], role_id=role.id)

    await member.delete()
    await getGw().dispatch(GuildMemberRemoveEvent(guild.id, (await user.data).ds_json), user_ids=[user.id])
    await getGw().dispatch(GuildDeleteEvent(guild.id), user_ids=[member.id])
    return "", 204


@users_me.get("/channels")
async def get_dm_channels(user: User = DepUser):
    return [
        await channel.ds_json(user_id=user.id)
        for channel in await user.get_private_channels()
    ]


@users_me.post("/channels", body_cls=DmChannelCreate)
async def new_dm_channel(data: DmChannelCreate, user: User = DepUser):
    recipients = data.recipients
    if user.id in recipients:
        recipients.remove(user.id)
    recipients_users = [await User.y.get(recipient) for recipient in recipients]
    if None in recipients_users:
        raise InvalidRecipient
    if len(recipients) == 1:
        channel = await Channel.Y.get_dm(user, recipients_users[0])
    elif len(recipients) == 0:
        channel = await Channel.Y.create_dm_group(user, [], data.name)
    else:
        channel = await Channel.Y.create_dm_group(user, recipients_users, data.name)
    await getGw().dispatch(DMChannelCreateEvent(channel), channel=channel)
    return await channel.ds_json(with_ids=False, user_id=user.id)


@users_me.post("/delete", body_cls=DeleteRequest)
async def delete_user(data: DeleteRequest, user: User = DepUser):
    if not user.check_password(data.password):
        raise PasswordDoesNotMatch
    if await Guild.exists(owner=user) or await Channel.exists(owner=user, type=ChannelType.GROUP_DM):
        raise MustTransferGuildsBeforeDelete
    await user.y_delete()
    await getGw().dispatch(UserDeleteEvent(user.id), user_ids=[user.id])
    return "", 204


@users_me.get("/scheduled-events", qs_cls=GetScheduledEventsQuery)
async def get_scheduled_events(query_args: GetScheduledEventsQuery, user: User = DepUser):
    events = []
    for guild_id in query_args.guild_ids[:5]:
        if not await GuildMember.get_or_none(guild__id=guild_id, user__id=user.id):
            raise MissingAccess
        for event_id in await GuildEvent.filter(
                guild__id=guild_id, subscribers__user__id__in=[user.id]
        ).values_list("id", flat=True):
            events.append({
                "guild_scheduled_event_id": str(event_id),
                "user_id": str(user.id)
            })

    return events


@users_me.post("/remote-auth/login", body_cls=RemoteAuthLogin)
async def remote_auth_login(data: RemoteAuthLogin, user: Optional[User] = DepUserO):
    if data.fingerprint is not None and user is not None:
        ra_session = await RemoteAuthSession.get_or_none(fingerprint=data.fingerprint, user=None,
                                                         expires_at__gt=int(time()))
        if ra_session is None:
            raise UnknownToken

        await ra_session.update(user=user)
        userdata = await user.userdata
        avatar = userdata.avatar if userdata.avatar else ""
        await getGw().dispatchRA("pending_finish", {
            "fingerprint": data.fingerprint,
            "userdata": f"{user.id}:{userdata.s_discriminator}:{avatar}:{userdata.username}"
        })

        return {"handshake_token": str(ra_session.id)}
    elif data.ticket is not None:
        ticket = Session.extract_token(data.ticket)
        if ticket is None:
            raise UnknownToken

        user_id, session_id, fingerprint = ticket

        ra_session = await RemoteAuthSession.get_or_none(
            fingerprint=fingerprint, expires_at__gt=int(time()), v2_session__id=session_id, user__id=user_id
        )
        if ra_session is None:
            raise UnknownToken

        await ra_session.delete()

        return {"encrypted_token": ra_session.v2_encrypted_token}

    raise UnknownToken


@users_me.post("/remote-auth/finish", body_cls=RemoteAuthFinish)
async def remote_auth_finish(data: RemoteAuthFinish, user: User = DepUser):
    ra_session = await RemoteAuthSession.get_or_none(id=int(data.handshake_token), expires_at__gt=int(time()),
                                                     user=user, v2_session=None)
    if ra_session is None:
        raise UnknownToken

    session = await Session.Y.create(user)
    if ra_session.version == 2:
        await ra_session.update(v2_session=session, expires_at=time_plus_150s())
    else:
        await ra_session.delete()

    await getGw().dispatchRA("finish", {
        "fingerprint": ra_session.fingerprint,
        "token": session.token
    })

    return "", 204


@users_me.post("/remote-auth/cancel", body_cls=RemoteAuthCancel)
async def remote_auth_cancel(data: RemoteAuthCancel, user: User = DepUser):
    ra_session = await RemoteAuthSession.get_or_none(id=int(data.handshake_token), expires_at__gt=int(time()),
                                                     user=user)
    if ra_session is None:
        raise UnknownToken

    await getGw().dispatchRA("cancel", {"fingerprint": ra_session.fingerprint})

    await ra_session.delete()

    return "", 204


@users_me.get("/guilds", allow_bots=True, oauth_scopes=["guilds"])
async def get_guilds(user: User = DepUser):
    async def ds_json(guild: Guild) -> dict:
        member = await guild.get_member(user.id)
        return {
            "approximate_member_count": await guild.get_member_count(),
            "approximate_presence_count": 0,
            "features": ["ANIMATED_ICON", "BANNER", "INVITE_SPLASH", "VANITY_URL", "PREMIUM_TIER_3_OVERRIDE",
                         "ROLE_ICONS", *guild.features],
            "icon": guild.icon,
            "id": str(guild.id),
            "name": guild.name,
            "owner": guild.owner == user,
            "permissions": str(await member.permissions),
        }

    return [await ds_json(guild) for guild in await user.get_guilds()]


@users_me.get("/mfa/webauthn/credentials")
async def get_webauthn_credentials(user: User = DepUser):
    return []  # TODO


# TODO: route GET /application-command-index
