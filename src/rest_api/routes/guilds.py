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

from datetime import datetime
from io import BytesIO
from time import time

from async_timeout import timeout
from quart import Blueprint, request, current_app
from quart_schema import validate_request, validate_querystring

from ..models.guilds import GuildCreate, GuildUpdate, TemplateCreate, TemplateUpdate, EmojiCreate, EmojiUpdate, \
    ChannelsPositionsChangeList, ChannelCreate, BanMember, RoleCreate, RoleUpdate, \
    RolesPositionsChangeList, AddRoleMembers, MemberUpdate, SetVanityUrl, GuildCreateFromTemplate, GuildDelete, \
    GetAuditLogsQuery, CreateSticker, UpdateSticker, CreateEvent, GetScheduledEvent, UpdateScheduledEvent
from ..utils import usingDB, getUser, multipleDecorators, getGuildWM, getGuildWoM, getGuildTemplate, getRole
from ...gateway.events import MessageDeleteEvent, GuildUpdateEvent, ChannelUpdateEvent, ChannelCreateEvent, \
    GuildDeleteEvent, GuildMemberRemoveEvent, GuildBanAddEvent, MessageBulkDeleteEvent, GuildRoleCreateEvent, \
    GuildRoleUpdateEvent, GuildRoleDeleteEvent, GuildMemberUpdateEvent, GuildBanRemoveEvent, \
    GuildScheduledEventCreateEvent, GuildScheduledEventUpdateEvent, GuildScheduledEventDeleteEvent, \
    ScheduledEventUserAddEvent, ScheduledEventUserRemoveEvent, GuildCreateEvent, GuildAuditLogEntryCreateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, StickerType, StickerFormat, ScheduledEventStatus
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Guild, GuildMember, GuildTemplate, Emoji, Channel, PermissionOverwrite, UserData, \
    Role, Invite, Sticker, GuildEvent, AuditLogEntry
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage, b64decode, validImage, imageType

# Base path is /api/vX/guilds
guilds = Blueprint('guilds', __name__)


@guilds.post("/", strict_slashes=False)
@multipleDecorators(validate_request(GuildCreate), usingDB, getUser)
async def create_guild(data: GuildCreate, user: User):
    guild_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setGuildIconFromBytesIO(guild_id, img):
            data.icon = h
    guild = await getCore().createGuild(guild_id, user, **data.dict(exclude_defaults=True))
    await getGw().dispatch(GuildCreateEvent(
        await guild.ds_json(user_id=user.id, with_members=True, with_channels=True)
    ), users=[user.id])
    return await guild.ds_json(user_id=user.id, with_members=False, with_channels=True)


@guilds.patch("/<int:guild>")
@multipleDecorators(validate_request(GuildUpdate), usingDB, getUser, getGuildWM)
async def update_guild(data: GuildUpdate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data.owner_id = None  # TODO: make guild ownership transfer
    for image_type, func in (("icon", getCDNStorage().setGuildIconFromBytesIO),
                             ("banner", getCDNStorage().setBannerFromBytesIO),
                             ("splash", getCDNStorage().setGuildSplashFromBytesIO)):
        if img := getattr(data, image_type):
            setattr(data, image_type, "")
            img = getImage(img)
            if h := await func(guild.id, img):
                setattr(data, image_type, h)
    for ch in ("afk_channel", "system_channel"):
        setattr(data, ch, None)  # TODO
        if (channel_id := getattr(data, ch)) is not None:
            if (channel := await getCore().getChannel(channel_id)) is None:
                setattr(data, ch, None)
            elif channel.guild != guild:
                setattr(data, ch, None)
    changes = data.dict(exclude_defaults=True)
    await guild.update(**changes)
    await getGw().dispatch(GuildUpdateEvent(await guild.ds_json(user_id=user.id)), guild_id=guild.id)

    entry = await AuditLogEntry.objects.guild_update(user, guild, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return await guild.ds_json(user_id=user.id)


@guilds.get("/<int:guild>/templates")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_templates(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    templates = []
    if template := await getCore().getGuildTemplate(guild):
        templates.append(await template.ds_json())
    return templates


@guilds.post("/<int:guild>/templates")
@multipleDecorators(validate_request(TemplateCreate), usingDB, getUser, getGuildWM)
async def create_guild_template(data: TemplateCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if await getCore().getGuildTemplate(guild):
        raise InvalidDataErr(400, Errors.make(30031))

    template: GuildTemplate = await GuildTemplate.objects.create(
        id=Snowflake.makeId(), guild=guild, name=data.name, description=data.description, creator=user,
        serialized_guild=await GuildTemplate.serialize_guild(guild)
    )

    return await template.ds_json()


@guilds.delete("/<int:guild>/templates/<string:template>")
@multipleDecorators(usingDB, getUser, getGuildWM, getGuildTemplate)
async def delete_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    await template.delete()
    return await template.ds_json()


@guilds.put("/<int:guild>/templates/<string:template>")
@multipleDecorators(usingDB, getUser, getGuildWM, getGuildTemplate)
async def sync_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if template.is_dirty:
        await template.update(
            serialized_guild=await GuildTemplate.serialize_guild(guild), is_dirty=False, updated_at=datetime.now())
    return await template.ds_json()


@guilds.patch("/<int:guild>/templates/<string:template>")
@multipleDecorators(validate_request(TemplateUpdate), usingDB, getUser, getGuildWM, getGuildTemplate)
async def update_guild_template(data: TemplateUpdate, user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    await template.update(**data.dict(exclude_defaults=True))
    return await template.ds_json()


@guilds.get("/<int:guild>/emojis")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def get_guild_emojis(user: User, guild: Guild):
    emojis = await getCore().getEmojis(guild.id)
    return [await emoji.ds_json(with_user=True) for emoji in emojis]


@guilds.post("/<int:guild>/emojis")
@multipleDecorators(validate_request(EmojiCreate), usingDB, getUser, getGuildWM)
async def create_guild_emoji(data: EmojiCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    img = getImage(data.image)
    emoji_id = Snowflake.makeId()
    if not (emd := await getCDNStorage().setEmojiFromBytesIO(emoji_id, img)):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    # TODO: check if emojis limit exceeded
    emoji = await Emoji.objects.create(id=emoji_id, name=data.name, user=user, guild=guild, animated=emd["animated"])
    await getGw().sendGuildEmojisUpdateEvent(guild)

    entry = await AuditLogEntry.objects.emoji_create(user, emoji)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return await emoji.ds_json()


@guilds.patch("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(validate_request(EmojiUpdate), usingDB, getUser, getGuildWM)
async def update_guild_emoji(data: EmojiUpdate, user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if (emoji := await getCore().getEmoji(emoji)) is None or emoji.guild != guild:
        raise InvalidDataErr(400, Errors.make(10014))
    await emoji.update(**data.dict(exclude_defaults=True))

    await getGw().sendGuildEmojisUpdateEvent(guild)

    return await emoji.ds_json()


@guilds.delete("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def delete_guild_emoji(user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)

    if not (emoji := await getCore().getEmoji(emoji)) or emoji.guild != guild:
        return "", 204

    await emoji.delete()
    await getGw().sendGuildEmojisUpdateEvent(guild)

    entry = await AuditLogEntry.objects.emoji_delete(user, emoji)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return "", 204


@guilds.patch("/<int:guild>/channels")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_channels_positions(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data = await request.get_json()
    if not data:
        return "", 204
    data = ChannelsPositionsChangeList(changes=data)
    channels = await getCore().getGuildChannels(guild)
    channels = {channel.id: channel for channel in channels}
    for change in data.changes:
        if not (channel := channels.get(change.id)):
            continue
        if change.parent_id and change.parent_id not in channels:
            change.parent_id = 0
        change = change.dict(exclude_defaults=True, exclude={"id"})
        await channel.update(**change)
        await getGw().dispatch(ChannelUpdateEvent(await channel.ds_json()), guild_id=channel.guild.id)
    await getCore().setTemplateDirty(guild)
    return "", 204


@guilds.post("/<int:guild>/channels")
@multipleDecorators(validate_request(ChannelCreate), usingDB, getUser, getGuildWM)
async def create_channel(data: ChannelCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data_json = data.to_json(data.type)
    if data_json.get("parent_id"):
        data_json["parent"] = await Channel.objects.get_or_none(guild=guild, id=data_json["parent_id"])
        del data_json["parent_id"]
    channel = await Channel.objects.create(id=Snowflake.makeId(), guild=guild, **data_json)
    for overwrite in data.permission_overwrites:
        await PermissionOverwrite.objects.create(**overwrite.dict(), channel=channel, target_id=overwrite.id)

    await getGw().dispatch(ChannelCreateEvent(await channel.ds_json()), guild_id=guild.id)

    entry = await AuditLogEntry.objects.channel_create(user, channel)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return await channel.ds_json()


@guilds.get("/<int:guild>/invites")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_invites(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    invites = await getCore().getGuildInvites(guild)
    invites = [await invite.ds_json() for invite in invites]
    return invites


@guilds.get("/<int:guild>/premium/subscriptions")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_premium_boosts(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    boosts = [{"ended": False, "user_id": str(guild.owner.id)}]*30
    return boosts


@guilds.delete("/<int:guild>/members/<int:user_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def kick_member(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.KICK_MEMBERS)
    if not (target_member := await getCore().getGuildMember(guild, user_id)):
        return "", 204
    if not await member.perm_checker.canKickOrBan(target_member):
        raise InvalidDataErr(403, Errors.make(50013))
    await target_member.delete()
    await getGw().dispatch(GuildMemberRemoveEvent(guild.id, (await target_member.data).ds_json), users=[user_id])
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[target_member.id])
    entry = await AuditLogEntry.objects.member_kick(user, target_member)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return "", 204


@guilds.put("/<int:guild>/bans/<int:user_id>")
@multipleDecorators(validate_request(BanMember), usingDB, getUser, getGuildWM)
async def ban_member(data: BanMember, user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    if not (target_member := await getCore().getGuildMember(guild, user_id)):
        return "", 204
    if not await member.perm_checker.canKickOrBan(target_member):
        raise InvalidDataErr(403, Errors.make(50013))
    if await getCore().getGuildBan(guild, user_id) is not None:
        return "", 204
    reason = request.headers.get("x-audit-log-reason")
    await target_member.delete()
    await getCore().banGuildMember(target_member, reason)
    target_user = target_member.user
    target_user_data = await target_user.data
    await getGw().dispatch(GuildMemberRemoveEvent(guild.id, target_user_data.ds_json), users=[user_id])
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[target_member.id])
    await getGw().dispatch(GuildBanAddEvent(guild.id, target_user_data.ds_json), guild_id=guild.id,
                           permissions=GuildPermissions.BAN_MEMBERS)
    if (delete_message_seconds := data.delete_message_seconds) > 0:
        after = Snowflake.fromTimestamp(int(time() - delete_message_seconds))
        deleted_messages = await getCore().bulkDeleteGuildMessagesFromBanned(guild, user_id, after)
        for channel_id, messages in deleted_messages.items():
            if len(messages) > 1:
                await getGw().dispatch(MessageBulkDeleteEvent(guild.id, channel_id, messages))
            elif len(messages) == 1:
                await getGw().dispatch(MessageDeleteEvent(messages[0], channel_id, guild.id), channel_id=channel_id)

    entry = await AuditLogEntry.objects.member_ban(user, target_member, reason)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return "", 204


@guilds.get("/<int:guild>/bans")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_bans(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    return [await ban.ds_json() for ban in await getCore().getGuildBans(guild)]


@guilds.delete("/<int:guild>/bans/<int:user_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def unban_member(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    await getCore().removeGuildBan(guild, user_id)
    target_user_data: UserData = await UserData.objects.select_related("user").get(id=user_id)
    await getGw().dispatch(GuildBanRemoveEvent(guild.id, target_user_data.ds_json), guild_id=guild.id,
                           permissions=GuildPermissions.BAN_MEMBERS)

    entry = await AuditLogEntry.objects.member_unban(user, guild, target_user_data.user)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return "", 204


@guilds.get("/<int:guild>/integrations")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_integrations(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    return []


@guilds.post("/<int:guild>/roles")
@multipleDecorators(validate_request(RoleCreate), usingDB, getUser, getGuildWM)
async def create_role(data: RoleCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    role_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setRoleIconFromBytesIO(role_id, img):
            data.icon = h
    role = await Role.objects.create(id=role_id, guild=guild, **data.dict())
    await getGw().dispatch(GuildRoleCreateEvent(guild.id, role.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.objects.role_create(user, role)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return role.ds_json()


@guilds.patch("/<int:guild>/roles/<int:role>")
@multipleDecorators(validate_request(RoleUpdate), usingDB, getUser, getGuildWM, getRole)
async def update_role(data: RoleUpdate, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == guild.id:  # Only allow permissions editing for @everyone role
        data = {"permissions": data.permissions} if data.permissions is not None else {}
    if data.icon != "":
        if (img := data.icon) is not None:
            data.icon = ""
            img = getImage(img)
            if h := await getCDNStorage().setRoleIconFromBytesIO(role.id, img):
                data.icon = h
    changes = data.dict(exclude_defaults=True)
    await role.update(**changes)
    await getGw().dispatch(GuildRoleUpdateEvent(guild.id, role.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.objects.role_update(user, role, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return role.ds_json()


@guilds.patch("/<int:guild>/roles")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_roles_positions(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    roles_data = await request.get_json()
    roles = await getCore().getRoles(guild, exclude_default=True)
    roles = {role.id: role for role in roles}

    if not await member.perm_checker.canChangeRolesPositions(roles_data, list(roles.values())):
        raise InvalidDataErr(403, Errors.make(50013))

    roles_data = RolesPositionsChangeList(changes=roles_data)

    changes = []
    for change in roles_data.changes:
        if not (role := roles.get(change.id)): continue  # Don't add non-existing roles
        if (pos := change.position) < 1: pos = 1
        role.position = pos
        changes.append(role)

    changes.sort(key=lambda r: (r.position, r.permissions))
    for idx, role in enumerate(changes):
        role.position = idx + 1  # Set new position
        await role.update(_columns=["position"])
        await getGw().dispatch(GuildRoleUpdateEvent(guild.id, role.ds_json()), guild_id=guild.id,
                               permissions=GuildPermissions.MANAGE_ROLES)

    await getCore().setTemplateDirty(guild)

    roles = await getCore().getRoles(guild)
    return [role.ds_json() for role in roles]


@guilds.delete("/<int:guild>/roles/<int:role>")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def delete_role(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == guild.id:
        raise InvalidDataErr(400, Errors.make(50028))
    await role.delete()
    await getGw().dispatch(GuildRoleDeleteEvent(guild.id, role.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.objects.role_delete(user, role)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return "", 204


@guilds.get("/<int:guild>/roles/<int:role>/connections/configuration")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def get_connections_configuration(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return []


@guilds.get("/<int:guild>/roles/member-counts")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_role_member_count(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return await getCore().getRolesMemberCounts(guild)


@guilds.get("/<int:guild>/roles/<int:role>/member-ids")
@multipleDecorators(usingDB, getUser, getGuildWoM, getRole)
async def get_role_members(user: User, guild: Guild, role: Role):
    return [str(member_id) for member_id in await getCore().getRoleMemberIds(role)]


@guilds.patch("/<int:guild>/roles/<int:role>/members")
@multipleDecorators(validate_request(AddRoleMembers), usingDB, getUser, getGuildWM, getRole)
async def add_role_members(data: AddRoleMembers, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == guild.id or (role.position >= (await member.top_role).position and user != guild.owner):
        raise InvalidDataErr(403, Errors.make(50013))
    members = {}
    for member_id in data.member_ids:
        target_member = await getCore().getGuildMember(guild, member_id)
        if not await getCore().memberHasRole(target_member, role):
            await target_member.roles.add(role)
            target_member_json = await target_member.ds_json()
            await getGw().dispatch(GuildMemberUpdateEvent(guild.id, target_member_json), guild_id=guild.id)
            members[str(target_member.id)] = target_member_json
    return members


@guilds.patch("/<int:guild>/members/<string:target_user>")
@multipleDecorators(validate_request(MemberUpdate), usingDB, getUser, getGuildWM)
async def update_member(data: MemberUpdate, user: User, guild: Guild, member: GuildMember, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    target_member = await getCore().getGuildMember(guild, target_user)
    if data.roles is not None:  # TODO: add MEMBER_ROLE_UPDATE audit log event
        await member.checkPermission(GuildPermissions.MANAGE_ROLES)
        roles = [int(role) for role in data.roles]
        guild_roles = {role.id: role for role in await getCore().getRoles(guild, exclude_default=True)}
        roles = [guild_roles[role_id] for role_id in roles if role_id in guild_roles]
        user_top_role = await member.top_role
        for role in roles:
            if guild_roles[role.id].position >= user_top_role.position and member.user != guild.owner:
                raise InvalidDataErr(403, Errors.make(50013))
        await getCore().setMemberRolesFromList(target_member, roles)
        data.roles = None
    if data.nick is not None:
        await member.checkPermission(
            GuildPermissions.CHANGE_NICKNAME
            if target_member == member else
            GuildPermissions.MANAGE_NICKNAMES
        )
    if data.avatar != "":
        if target_member != member:
            raise InvalidDataErr(403, Errors.make(50013))
        img = data.avatar
        if img is not None:
            img = getImage(img)
            data.avatar = ""
            if av := await getCDNStorage().setGuildAvatarFromBytesIO(user.id, guild.id, img):
                data.avatar = av
    changes = data.dict(exclude_defaults=True)
    await target_member.update(**changes)
    await getGw().dispatch(GuildMemberUpdateEvent(guild.id, await target_member.ds_json()), guild_id=guild.id)

    entry = await AuditLogEntry.objects.member_update(user, target_member, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return await target_member.ds_json()


@guilds.get("/<int:guild>/vanity-url")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_vanity_url(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    code = {
        "code": guild.vanity_url_code
    }
    if guild.vanity_url_code:
        if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
            code["uses"]: invite.uses
    return code


@guilds.patch("/<int:guild>/vanity-url")
@multipleDecorators(validate_request(SetVanityUrl), usingDB, getUser, getGuildWM)
async def update_vanity_url(data: SetVanityUrl, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if data.code is None:
        return {"code": guild.vanity_url_code}
    if data.code == guild.vanity_url_code:
        return {"code": guild.vanity_url_code}
    if not data.code:
        if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
            await invite.delete()
        await guild.update(vanity_url_code=None)
    else:
        if await getCore().getVanityCodeInvite(data.code):
            return {"code": guild.vanity_url_code}
        if guild.vanity_url_code and (invite := await getCore().getVanityCodeInvite(guild.vanity_url_code)):
            await invite.delete()
        await guild.update(vanity_url_code=data.code)
        channel = await getCore().getChannel(guild.system_channel_id) if guild.system_channel_id is not None else None
        if channel is None:
            channel = (await getCore().getGuildChannels(guild))[0]
        await Invite.objects.create(id=Snowflake.makeId(), channel=channel, inviter=guild.owner, vanity_code=data.code)
    await getGw().dispatch(GuildUpdateEvent(await guild.ds_json(user_id=user.id)), guild_id=guild.id)
    return {"code": guild.vanity_url_code}


@guilds.get("/<int:guild>/audit-logs")
@multipleDecorators(validate_querystring(GetAuditLogsQuery), usingDB, getUser, getGuildWM)
async def get_audit_logs(query_args: GetAuditLogsQuery, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    entries = await getCore().getAuditLogEntries(guild, **query_args.dict())
    userdatas = {}
    for entry in entries:
        target_id = entry.target_id
        if target_id and target_id not in userdatas:
            if (data := await UserData.objects.get(id=target_id)) is not None:
                userdatas[target_id] = data
    userdatas = list(userdatas.values())

    return {
        "application_commands": [],
        "audit_log_entries": [entry.ds_json() for entry in entries],
        "auto_moderation_rules": [],
        "guild_scheduled_events": [],
        "integrations": [],
        "threads": [],
        "users": [userdata.ds_json for userdata in userdatas],
        "webhooks": [],
    }


@guilds.post("/templates/<string:template>")
@multipleDecorators(validate_request(GuildCreateFromTemplate), usingDB, getUser)
async def create_from_template(data: GuildCreateFromTemplate, user: User, template: str):
    try:
        template_id = int.from_bytes(b64decode(template), "big")
        if not (template := await getCore().getGuildTemplateById(template_id)):
            raise ValueError
    except ValueError:
        raise InvalidDataErr(404, Errors.make(10057))

    guild_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setGuildIconFromBytesIO(guild_id, img):
            data.icon = h

    guild = await getCore().createGuildFromTemplate(guild_id, user, template, data.name, data.icon)
    await getGw().dispatch(GuildCreateEvent(
        await guild.ds_json(user_id=user.id, with_members=True, with_channels=True)
    ), users=[user.id])

    return await guild.ds_json(user_id=user.id, with_members=False, with_channels=True)


@guilds.post("/<int:guild>/delete")
@multipleDecorators(validate_request(GuildDelete), usingDB, getUser, getGuildWoM)
async def delete_guild(data: GuildDelete, user: User, guild: Guild):
    if user != guild.owner:
        raise InvalidDataErr(403, Errors.make(50013))

    if mfa := await getCore().getMfa(user):
        if not data.code:
            raise InvalidDataErr(400, Errors.make(60008))
        if data.code not in mfa.getCodes():
            if not (len(data.code) == 8 and await getCore().useMfaCode(user, data.code)):
                raise InvalidDataErr(400, Errors.make(60008))

    await guild.delete()
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[user.id])

    return "", 204


@guilds.get("/<int:guild>/webhooks")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_webhooks(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    return [await webhook.ds_json() for webhook in await getCore().getWebhooks(guild)]


@guilds.get("/<int:guild>/stickers")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def get_guild_stickers(user: User, guild: Guild):
    return [await sticker.ds_json() for sticker in await getCore().getGuildStickers(guild)]


@guilds.post("/<int:guild>/stickers")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def upload_guild_stickers(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if request.content_length > 1024 * 512:
        raise InvalidDataErr(400, Errors.make(50006))
    async with timeout(current_app.config["BODY_TIMEOUT"]):
        if not (file := (await request.files).get("file")):
            raise InvalidDataErr(400, Errors.make(50046))
        data = CreateSticker(**dict(await request.form))
        sticker_b = BytesIO(getattr(file, "getvalue", file.read)())
        if sticker_b.getbuffer().nbytes > 1024 * 512 or not (img := getImage(sticker_b)) or not validImage(img):
            raise InvalidDataErr(400, Errors.make(50006))
        sticker_type = getattr(StickerFormat, str(imageType(img)).upper(), StickerFormat.PNG)

        sticker_id = Snowflake.makeId()
        if not await getCDNStorage().setStickerFromBytesIO(sticker_id, img):
            raise InvalidDataErr(400, Errors.make(50006))

        sticker = await Sticker.objects.create(
            id=sticker_id, guild=guild, user=user, name=data.name, tags=data.tags, type=StickerType.GUILD,
            format=sticker_type, description=data.description
        )

    await getGw().sendStickersUpdateEvent(guild)

    return await sticker.ds_json()


@guilds.patch("/<int:guild>/stickers/<int:sticker_id>")
@multipleDecorators(validate_request(UpdateSticker), usingDB, getUser, getGuildWM)
async def update_guild_sticker(data: UpdateSticker, user: User, guild: Guild, member: GuildMember, sticker_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker_id)) or sticker.guild != guild:
        raise InvalidDataErr(404, Errors.make(10060))
    await sticker.update(**data.dict(exclude_defaults=True))
    await getGw().sendStickersUpdateEvent(guild)
    return await sticker.ds_json()


@guilds.delete("/<int:guild>/stickers/<int:sticker_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def delete_guild_sticker(user: User, guild: Guild, member: GuildMember, sticker_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker_id)) or sticker.guild != guild:
        raise InvalidDataErr(404, Errors.make(10060))

    await sticker.delete()
    await getGw().sendStickersUpdateEvent(guild)

    return "", 204


@guilds.post("/<int:guild>/scheduled-events")
@multipleDecorators(validate_request(CreateEvent), usingDB, getUser, getGuildWM)
async def create_scheduled_event(data: CreateEvent, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    event_id = Snowflake.makeId()
    if (img := data.image) is not None:
        img = getImage(img)
        if imageType(img) not in ("png", "jpg", "jpeg"):
            raise InvalidDataErr(400, Errors.make(50035, {"image": {
                "code": "IMAGE_INVALID", "message": "Invalid image"
            }}))
        if h := await getCDNStorage().setGuildEventFromBytesIO(event_id, img):
            img = h
        data.image = img

    event = await GuildEvent.objects.create(id=event_id, guild=guild, creator=user, **data.dict())
    await getGw().dispatch(GuildScheduledEventCreateEvent(await event.ds_json()), guild_id=guild.id)

    await event.subscribers.add(member)
    # TODO: Replace with list of users subscribed to event
    await getGw().dispatch(ScheduledEventUserAddEvent(user.id, event.id, guild.id), guild_id=guild.id)

    return await event.ds_json()


@guilds.get("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_querystring(GetScheduledEvent), usingDB, getUser, getGuildWoM)
async def get_scheduled_event(query_args: GetScheduledEvent, user: User, guild: Guild, event_id: int):
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    return await event.ds_json(with_user_count=query_args.with_user_count)


@guilds.get("/<int:guild>/scheduled-events")
@multipleDecorators(validate_querystring(GetScheduledEvent), usingDB, getUser, getGuildWoM)
async def get_scheduled_events(query_args: GetScheduledEvent, user: User, guild: Guild):
    events = await getCore().getGuildEvents(guild)
    return [await event.ds_json(with_user_count=query_args.with_user_count) for event in events]


@guilds.patch("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_request(UpdateScheduledEvent), usingDB, getUser, getGuildWM)
async def update_scheduled_event(data: UpdateScheduledEvent, user: User, guild: Guild, member: GuildMember, event_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    if (img := data.image) or img is None:
        if img is not None:
            img = getImage(img)
            if imageType(img) not in ("png", "jpg", "jpeg"):
                raise InvalidDataErr(400, Errors.make(50035, {"image": {
                    "code": "IMAGE_INVALID", "message": "Invalid image"
                }}))
            if h := await getCDNStorage().setGuildEventFromBytesIO(event.id, img):
                img = h
        data.image = img

    new_status = data.dict(exclude_defaults=True).get("status", event.status)

    valid_transition = True
    if event.status == ScheduledEventStatus.SCHEDULED:
        if new_status not in (ScheduledEventStatus.SCHEDULED, ScheduledEventStatus.ACTIVE, ScheduledEventStatus.CANCELED):
            valid_transition = False
    elif (event.status == ScheduledEventStatus.ACTIVE and new_status != ScheduledEventStatus.COMPLETED) \
            and event.status != new_status:
        valid_transition = False

    if not valid_transition:
        raise InvalidDataErr(400, Errors.make(50035, {"status": {
            "code": "TRANSITION_INVALID", "message": "Invalid Guild Scheduled Event Status Transition"
        }}))

    await event.update(**data.dict(exclude_defaults=True))
    event_json = await event.ds_json()
    await getGw().dispatch(GuildScheduledEventUpdateEvent(event_json), guild_id=guild.id)

    return event_json


@guilds.put("/<int:guild>/scheduled-events/<int:event_id>/users/@me")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def subscribe_to_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    await event.subscribers.add(member)
    await getGw().dispatch(ScheduledEventUserAddEvent(user.id, event_id, guild.id),
                           guild_id=guild.id)  # TODO: Replace with list of users subscribed to event

    return {
        "guild_scheduled_event_id": str(event.id),
        "user_id": str(user.id)  # current user or creator??
    }


@guilds.delete("/<int:guild>/scheduled-events/<int:event_id>/users/@me")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def unsubscribe_from_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    await event.subscribers.remove(member)
    await getGw().dispatch(ScheduledEventUserRemoveEvent(user.id, event_id, guild.id),
                           guild_id=guild.id)  # TODO: Replace with list of users subscribed to event

    return "", 204


@guilds.delete("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def delete_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    await event.delete()
    await getGw().dispatch(GuildScheduledEventDeleteEvent(await event.ds_json()), guild_id=guild.id)

    return "", 204
