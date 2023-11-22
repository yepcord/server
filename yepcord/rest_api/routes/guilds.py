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
from tortoise.expressions import Q

from ..models.guilds import GuildCreate, GuildUpdate, TemplateCreate, TemplateUpdate, EmojiCreate, EmojiUpdate, \
    ChannelsPositionsChangeList, ChannelCreate, BanMember, RoleCreate, RoleUpdate, \
    RolesPositionsChangeList, AddRoleMembers, MemberUpdate, SetVanityUrl, GuildCreateFromTemplate, GuildDelete, \
    GetAuditLogsQuery, CreateSticker, UpdateSticker, CreateEvent, GetScheduledEvent, UpdateScheduledEvent, \
    GetIntegrationsQS
from ..utils import getUser, multipleDecorators, getGuildWM, getGuildWoM, getGuildTemplate, getRole, allowBots
from ...gateway.events import MessageDeleteEvent, GuildUpdateEvent, ChannelUpdateEvent, ChannelCreateEvent, \
    GuildDeleteEvent, GuildMemberRemoveEvent, GuildBanAddEvent, MessageBulkDeleteEvent, GuildRoleCreateEvent, \
    GuildRoleUpdateEvent, GuildRoleDeleteEvent, GuildMemberUpdateEvent, GuildBanRemoveEvent, \
    GuildScheduledEventCreateEvent, GuildScheduledEventUpdateEvent, GuildScheduledEventDeleteEvent, \
    ScheduledEventUserAddEvent, ScheduledEventUserRemoveEvent, GuildCreateEvent, GuildAuditLogEntryCreateEvent, \
    IntegrationDeleteEvent, GuildIntegrationsUpdateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, StickerType, StickerFormat, ScheduledEventStatus, ChannelType, \
    ScheduledEventEntityType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Guild, GuildMember, GuildTemplate, Emoji, Channel, PermissionOverwrite, UserData, \
    Role, Invite, Sticker, GuildEvent, AuditLogEntry, Integration, ApplicationCommand
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage, b64decode, validImage, imageType

# Base path is /api/vX/guilds
guilds = Blueprint('guilds', __name__)


@guilds.post("/", strict_slashes=False)
@multipleDecorators(validate_request(GuildCreate), allowBots, getUser)
async def create_guild(data: GuildCreate, user: User):
    guild_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setGuildIconFromBytesIO(guild_id, img):
            data.icon = h
    guild = await getCore().createGuild(guild_id, user, **data.model_dump(exclude_defaults=True))
    await getGw().dispatch(GuildCreateEvent(
        await guild.ds_json(user_id=user.id, with_members=True, with_channels=True)
    ), users=[user.id])
    return await guild.ds_json(user_id=user.id, with_members=False, with_channels=True)


@guilds.patch("/<int:guild>")
@multipleDecorators(validate_request(GuildUpdate), allowBots, getUser, getGuildWM)
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
        if (channel_id := getattr(data, ch)) is not None:
            if (channel := await getCore().getChannel(channel_id)) is None:
                setattr(data, ch, None)
            elif channel.guild != guild:
                setattr(data, ch, None)
            elif ch == "afk_channel" and channel.type != ChannelType.GUILD_VOICE:
                setattr(data, ch, None)
            elif ch == "system_channel" and channel.type != ChannelType.GUILD_TEXT:
                setattr(data, ch, None)
            else:
                setattr(data, ch, channel.id)
    changes = data.model_dump(exclude_defaults=True)
    await guild.update(**changes)
    await getGw().dispatch(GuildUpdateEvent(await guild.ds_json(user_id=0)), guild_id=guild.id)

    entry = await AuditLogEntry.utils.guild_update(user, guild, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return await guild.ds_json(user_id=user.id)


@guilds.get("/<int:guild>/templates")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_guild_templates(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    templates = []
    if template := await getCore().getGuildTemplate(guild):
        templates.append(await template.ds_json())
    return templates


@guilds.post("/<int:guild>/templates")
@multipleDecorators(validate_request(TemplateCreate), allowBots, getUser, getGuildWM)
async def create_guild_template(data: TemplateCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if await getCore().getGuildTemplate(guild):
        raise InvalidDataErr(400, Errors.make(30031))

    template: GuildTemplate = await GuildTemplate.create(
        id=Snowflake.makeId(), guild=guild, name=data.name, description=data.description, creator=user,
        serialized_guild=await GuildTemplate.serialize_guild(guild)
    )

    return await template.ds_json()


@guilds.delete("/<int:guild>/templates/<string:template>")
@multipleDecorators(allowBots, getUser, getGuildWM, getGuildTemplate)
async def delete_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    await template.delete()
    return await template.ds_json()


@guilds.put("/<int:guild>/templates/<string:template>")
@multipleDecorators(allowBots, getUser, getGuildWM, getGuildTemplate)
async def sync_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if template.is_dirty:
        template.serialized_guild = await GuildTemplate.serialize_guild(guild)
        template.is_dirty = False
        template.updated_at = datetime.now()
        await template.save(update_fields=["serialized_guild", "is_dirty", "updated_at"])
    return await template.ds_json()


@guilds.patch("/<int:guild>/templates/<string:template>")
@multipleDecorators(validate_request(TemplateUpdate), allowBots, getUser, getGuildWM, getGuildTemplate)
async def update_guild_template(data: TemplateUpdate, user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    await template.update(**data.model_dump(exclude_defaults=True))
    return await template.ds_json()


@guilds.get("/<int:guild>/emojis")
@multipleDecorators(allowBots, getUser, getGuildWoM)
async def get_guild_emojis(user: User, guild: Guild):
    emojis = await getCore().getEmojis(guild.id)
    return [await emoji.ds_json(with_user=True) for emoji in emojis]


@guilds.post("/<int:guild>/emojis")
@multipleDecorators(validate_request(EmojiCreate), allowBots, getUser, getGuildWM)
async def create_guild_emoji(data: EmojiCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    img = getImage(data.image)
    emoji_id = Snowflake.makeId()
    result = await getCDNStorage().setEmojiFromBytesIO(emoji_id, img)
    emoji = await Emoji.create(id=emoji_id, name=data.name, user=user, guild=guild, animated=result["animated"])
    await getGw().sendGuildEmojisUpdateEvent(guild)

    entry = await AuditLogEntry.utils.emoji_create(user, emoji)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return await emoji.ds_json()


@guilds.patch("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(validate_request(EmojiUpdate), allowBots, getUser, getGuildWM)
async def update_guild_emoji(data: EmojiUpdate, user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if (emoji := await getCore().getEmoji(emoji)) is None or emoji.guild != guild:
        raise InvalidDataErr(400, Errors.make(10014))
    await emoji.update(**data.model_dump(exclude_defaults=True))

    await getGw().sendGuildEmojisUpdateEvent(guild)

    return await emoji.ds_json()


@guilds.delete("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def delete_guild_emoji(user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)

    if not (emoji := await getCore().getEmoji(emoji)) or emoji.guild != guild:
        return "", 204

    await emoji.delete()
    await getGw().sendGuildEmojisUpdateEvent(guild)

    entry = await AuditLogEntry.utils.emoji_delete(user, emoji)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return "", 204


@guilds.patch("/<int:guild>/channels")
@multipleDecorators(allowBots, getUser, getGuildWM)
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
        change = change.model_dump(exclude_defaults=True, exclude={"id"})
        await channel.update(**change)
        await getGw().dispatch(ChannelUpdateEvent(await channel.ds_json()), guild_id=channel.guild.id)
    await getCore().setTemplateDirty(guild)
    return "", 204


@guilds.post("/<int:guild>/channels")
@multipleDecorators(validate_request(ChannelCreate), allowBots, getUser, getGuildWM)
async def create_channel(data: ChannelCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data_json = data.to_json(data.type)
    if data_json.get("parent_id"):
        data_json["parent"] = await Channel.get_or_none(guild=guild, id=data_json["parent_id"])
        del data_json["parent_id"]
    channel = await Channel.create(id=Snowflake.makeId(), guild=guild, **data_json)
    for overwrite in data.permission_overwrites:
        await PermissionOverwrite.create(**overwrite.model_dump(), channel=channel, target_id=overwrite.id)

    await getGw().dispatch(ChannelCreateEvent(await channel.ds_json()), guild_id=guild.id)

    entry = await AuditLogEntry.utils.channel_create(user, channel)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return await channel.ds_json()


@guilds.get("/<int:guild>/invites")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_guild_invites(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    invites = await getCore().getGuildInvites(guild)
    invites = [await invite.ds_json() for invite in invites]
    return invites


@guilds.get("/<int:guild>/premium/subscriptions")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_premium_boosts(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    boosts = [{"ended": False, "user_id": str(guild.owner.id)}] * 30
    return boosts


async def process_bot_kick(user: User, bot_member: GuildMember) -> None:
    guild = bot_member.guild
    bot_role = [role for role in await Role.filter(guild=guild, managed=True).all()
                if role.tags["bot_id"] == str(bot_member.user.id)]
    if bot_role:
        bot_role = bot_role[0]
        await bot_role.delete()
        await getGw().dispatch(GuildRoleDeleteEvent(guild.id, bot_role.id), guild_id=guild.id,
                               permissions=GuildPermissions.MANAGE_ROLES)

    await Integration.filter(guild=guild, application=bot_member.user.id).delete()

    await getGw().dispatch(IntegrationDeleteEvent(guild.id, bot_member.user.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_GUILD)
    await getGw().dispatch(GuildIntegrationsUpdateEvent(guild.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_GUILD)

    entry = await AuditLogEntry.utils.integration_delete(user, guild, bot_member.user)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)


@guilds.delete("/<int:guild>/members/<int:user_id>")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def kick_member(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.KICK_MEMBERS)
    if not (target_member := await getCore().getGuildMember(guild, user_id)):
        return "", 204
    if not await member.perm_checker.canKickOrBan(target_member):
        raise InvalidDataErr(403, Errors.make(50013))
    await target_member.delete()
    if target_member.user.is_bot:
        await process_bot_kick(user, target_member)
    await getGw().dispatch(GuildMemberRemoveEvent(guild.id, (await target_member.user.data).ds_json), users=[user_id])
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[target_member.id])
    entry = await AuditLogEntry.utils.member_kick(user, target_member)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return "", 204


@guilds.put("/<int:guild>/bans/<int:user_id>")
@multipleDecorators(validate_request(BanMember), allowBots, getUser, getGuildWM)
async def ban_member(data: BanMember, user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    target_member = await getCore().getGuildMember(guild, user_id)
    if target_member is not None and not await member.perm_checker.canKickOrBan(target_member):
        raise InvalidDataErr(403, Errors.make(50013))
    if await getCore().getGuildBan(guild, user_id) is not None:
        return "", 204
    reason = request.headers.get("x-audit-log-reason")
    if target_member is not None:
        await target_member.delete()
        if target_member.user.is_bot:
            await process_bot_kick(user, target_member)
        await getCore().banGuildMember(target_member, reason)
        target_user = target_member.user
    else:
        if (target_user := await User.y.get(user_id, False)) is None:
            raise InvalidDataErr(404, Errors.make(10013))
        await getCore().banGuildUser(target_user, guild, reason)
    target_user_data = await target_user.data
    if target_member is not None:
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

    if target_member is not None:
        entry = await AuditLogEntry.utils.member_ban(user, target_member, reason)
    else:
        entry = await AuditLogEntry.utils.member_ban_user(user, user_id, guild, reason)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return "", 204


@guilds.get("/<int:guild>/bans")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_guild_bans(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    return [await ban.ds_json() for ban in await getCore().getGuildBans(guild)]


@guilds.delete("/<int:guild>/bans/<int:user_id>")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def unban_member(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    target_user_data: UserData = await UserData.get(id=user_id).select_related("user")
    await getCore().removeGuildBan(guild, target_user_data.user)
    await getGw().dispatch(GuildBanRemoveEvent(guild.id, target_user_data.ds_json), guild_id=guild.id,
                           permissions=GuildPermissions.BAN_MEMBERS)

    entry = await AuditLogEntry.utils.member_unban(user, guild, target_user_data.user)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return "", 204


@guilds.get("/<int:guild>/integrations")
@multipleDecorators(validate_querystring(GetIntegrationsQS), getUser, getGuildWM)
async def get_guild_integrations(query_args: GetIntegrationsQS, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    integrations = await Integration.filter(guild=guild).select_related("application", "user").all()
    return [await integration.ds_json(query_args.include_applications) for integration in integrations]


@guilds.get("/<int:guild>/roles")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_roles(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return [role.ds_json() for role in await getCore().getRoles(guild, True)]


@guilds.post("/<int:guild>/roles")
@multipleDecorators(validate_request(RoleCreate), allowBots, getUser, getGuildWM)
async def create_role(data: RoleCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    role_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setRoleIconFromBytesIO(role_id, img):
            data.icon = h
    role = await Role.create(id=role_id, guild=guild, **data.model_dump())
    await getGw().dispatch(GuildRoleCreateEvent(guild.id, role.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.utils.role_create(user, role)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return role.ds_json()


@guilds.patch("/<int:guild>/roles/<int:role>")
@multipleDecorators(validate_request(RoleUpdate), allowBots, getUser, getGuildWM, getRole)
async def update_role(data: RoleUpdate, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id != guild.id and data.icon != "" and (img := data.icon) is not None:
        data.icon = ""
        img = getImage(img)
        if h := await getCDNStorage().setRoleIconFromBytesIO(role.id, img):
            data.icon = h
    if role.id == guild.id:  # Only allow permissions editing for @everyone role
        changes = {"permissions": data.permissions} if data.permissions is not None else {}
    else:
        changes = data.model_dump(exclude_defaults=True)
    await role.update(**changes)
    await getGw().dispatch(GuildRoleUpdateEvent(guild.id, role.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.utils.role_update(user, role, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return role.ds_json()


@guilds.patch("/<int:guild>/roles")
@multipleDecorators(allowBots, getUser, getGuildWM)
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
@multipleDecorators(allowBots, getUser, getGuildWM, getRole)
async def delete_role(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.managed:
        raise InvalidDataErr(400, Errors.make(50028))
    await role.delete()
    await getGw().dispatch(GuildRoleDeleteEvent(guild.id, role.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_ROLES)

    entry = await AuditLogEntry.utils.role_delete(user, role)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(guild)

    return "", 204


@guilds.get("/<int:guild>/roles/<int:role>/connections/configuration")
@multipleDecorators(allowBots, getUser, getGuildWM, getRole)
async def get_connections_configuration(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return []


@guilds.get("/<int:guild>/roles/member-counts")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_role_member_count(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return await getCore().getRolesMemberCounts(guild)


@guilds.get("/<int:guild>/roles/<int:role>/member-ids")
@multipleDecorators(allowBots, getUser, getGuildWoM, getRole)
async def get_role_members(user: User, guild: Guild, role: Role):
    return [str(member_id) for member_id in await getCore().getRoleMemberIds(role)]


@guilds.patch("/<int:guild>/roles/<int:role>/members")
@multipleDecorators(validate_request(AddRoleMembers), allowBots, getUser, getGuildWM, getRole)
async def add_role_members(data: AddRoleMembers, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.managed:
        raise InvalidDataErr(400, Errors.make(50028))
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
@multipleDecorators(validate_request(MemberUpdate), allowBots, getUser, getGuildWM)
async def update_member(data: MemberUpdate, user: User, guild: Guild, member: GuildMember, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    target_member = await getCore().getGuildMember(guild, target_user)
    if data.roles is not None:
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
    changes = data.model_dump(exclude_defaults=True)
    await target_member.update(**changes)
    await getGw().dispatch(GuildMemberUpdateEvent(guild.id, await target_member.ds_json()), guild_id=guild.id)

    entry = await AuditLogEntry.utils.member_update(user, target_member, changes)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    return await target_member.ds_json()


@guilds.get("/<int:guild>/vanity-url")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_vanity_url(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    code = {"code": guild.vanity_url_code}
    if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
        code["uses"] = invite.uses
    return code


@guilds.patch("/<int:guild>/vanity-url")
@multipleDecorators(validate_request(SetVanityUrl), allowBots, getUser, getGuildWM)
async def update_vanity_url(data: SetVanityUrl, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if data.code is None:
        return {"code": guild.vanity_url_code}
    if data.code == guild.vanity_url_code:
        return {"code": guild.vanity_url_code}
    if not data.code:
        if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
            await invite.delete()
            guild.vanity_url_code = None
        await guild.save(update_fields=["vanity_url_code"])
    else:
        if await getCore().getVanityCodeInvite(data.code):
            return {"code": guild.vanity_url_code}
        if guild.vanity_url_code and (invite := await getCore().getVanityCodeInvite(guild.vanity_url_code)):
            await invite.delete()
        guild.vanity_url_code = data.code
        await guild.save(update_fields=["vanity_url_code"])
        channel = await getCore().getChannel(guild.system_channel) if guild.system_channel is not None else None
        if channel is None:
            channel = (await getCore().getGuildChannels(guild))[0]
        await Invite.create(id=Snowflake.makeId(), channel=channel, inviter=guild.owner, vanity_code=data.code)
    await getGw().dispatch(GuildUpdateEvent(await guild.ds_json(user_id=user.id)), guild_id=guild.id)
    return {"code": guild.vanity_url_code}


@guilds.get("/<int:guild>/audit-logs")
@multipleDecorators(validate_querystring(GetAuditLogsQuery), allowBots, getUser, getGuildWM)
async def get_audit_logs(query_args: GetAuditLogsQuery, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    entries = await getCore().getAuditLogEntries(guild, **query_args.model_dump())
    userdatas = {}
    for entry in entries:
        target_id = entry.target_id
        if target_id and target_id not in userdatas:
            if (data := await UserData.get_or_none(id=target_id).select_related("user")) is not None:
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
@multipleDecorators(validate_request(GuildCreateFromTemplate), allowBots, getUser)
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
@multipleDecorators(validate_request(GuildDelete), allowBots, getUser, getGuildWoM)
async def delete_guild(data: GuildDelete, user: User, guild: Guild):
    if user != guild.owner:
        raise InvalidDataErr(403, Errors.make(50013))

    if mfa := await user.mfa:
        if not data.code:
            raise InvalidDataErr(400, Errors.make(60008))
        if data.code not in mfa.getCodes():
            if not (len(data.code) == 8 and await getCore().useMfaCode(user, data.code)):
                raise InvalidDataErr(400, Errors.make(60008))

    await guild.delete()
    await getGw().dispatch(GuildDeleteEvent(guild.id), users=[user.id])

    return "", 204


@guilds.get("/<int:guild>/webhooks")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def get_guild_webhooks(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    return [await webhook.ds_json() for webhook in await getCore().getWebhooks(guild)]


@guilds.get("/<int:guild>/stickers")
@multipleDecorators(allowBots, getUser, getGuildWoM)
async def get_guild_stickers(user: User, guild: Guild):
    return [await sticker.ds_json() for sticker in await getCore().getGuildStickers(guild)]


@guilds.post("/<int:guild>/stickers")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def upload_guild_stickers(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if request.content_length is not None and request.content_length > 1024 * 512:
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
        await getCDNStorage().setStickerFromBytesIO(sticker_id, img)

        sticker = await Sticker.create(
            id=sticker_id, guild=guild, user=user, name=data.name, tags=data.tags, type=StickerType.GUILD,
            format=sticker_type, description=data.description
        )

    await getGw().sendStickersUpdateEvent(guild)

    return await sticker.ds_json()


@guilds.patch("/<int:guild>/stickers/<int:sticker_id>")
@multipleDecorators(validate_request(UpdateSticker), allowBots, getUser, getGuildWM)
async def update_guild_sticker(data: UpdateSticker, user: User, guild: Guild, member: GuildMember, sticker_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker_id)) or sticker.guild != guild:
        raise InvalidDataErr(404, Errors.make(10060))
    await sticker.update(**data.model_dump(exclude_defaults=True))
    await getGw().sendStickersUpdateEvent(guild)
    return await sticker.ds_json()


@guilds.delete("/<int:guild>/stickers/<int:sticker_id>")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def delete_guild_sticker(user: User, guild: Guild, member: GuildMember, sticker_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker_id)) or sticker.guild != guild:
        raise InvalidDataErr(404, Errors.make(10060))

    await sticker.delete()
    await getGw().sendStickersUpdateEvent(guild)

    return "", 204


@guilds.post("/<int:guild>/scheduled-events")
@multipleDecorators(validate_request(CreateEvent), allowBots, getUser, getGuildWM)
async def create_scheduled_event(data: CreateEvent, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    event_id = Snowflake.makeId()
    if (img := data.image) is not None:
        img = getImage(img)
        if imageType(img) not in ("png", "jpg", "jpeg"):
            raise InvalidDataErr(400, Errors.make(50035, {"image": {
                "code": "IMAGE_INVALID", "message": "Invalid image"
            }}))

        img = await getCDNStorage().setGuildEventFromBytesIO(event_id, img)
        data.image = img

    data_dict = data.model_dump()
    if data.entity_type in (ScheduledEventEntityType.STAGE_INSTANCE, ScheduledEventEntityType.VOICE):
        if ((channel := await getCore().getChannel(data.channel_id)) is None or channel.guild != guild
                or channel.type not in (ChannelType.GUILD_VOICE, ChannelType.GUILD_STAGE_VOICE)):
            raise InvalidDataErr(400, Errors.make(50035, {"channel_id": {
                "code": "CHANNEL_INVALID", "message": "Invalid channel"
            }}))
        data_dict["channel"] = channel
    del data_dict["channel_id"]

    event = await GuildEvent.create(id=event_id, guild=guild, creator=user, **data_dict)
    await getGw().dispatch(GuildScheduledEventCreateEvent(await event.ds_json()), guild_id=guild.id)

    await event.subscribers.add(member)
    # TODO: Replace with list of users subscribed to event
    await getGw().dispatch(ScheduledEventUserAddEvent(user.id, event.id, guild.id), guild_id=guild.id)

    return await event.ds_json()


@guilds.get("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_querystring(GetScheduledEvent), allowBots, getUser, getGuildWoM)
async def get_scheduled_event(query_args: GetScheduledEvent, user: User, guild: Guild, event_id: int):
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    return await event.ds_json(with_user_count=query_args.with_user_count)


@guilds.get("/<int:guild>/scheduled-events")
@multipleDecorators(validate_querystring(GetScheduledEvent), allowBots, getUser, getGuildWoM)
async def get_scheduled_events(query_args: GetScheduledEvent, user: User, guild: Guild):
    events = await getCore().getGuildEvents(guild)
    return [await event.ds_json(with_user_count=query_args.with_user_count) for event in events]


@guilds.patch("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_request(UpdateScheduledEvent), allowBots, getUser, getGuildWM)
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

    new_status = data.model_dump(exclude_defaults=True).get("status", event.status)

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

    await event.update(**data.model_dump(exclude_defaults=True))
    event_json = await event.ds_json()
    await getGw().dispatch(GuildScheduledEventUpdateEvent(event_json), guild_id=guild.id)

    return event_json


@guilds.put("/<int:guild>/scheduled-events/<int:event_id>/users/@me")
@multipleDecorators(allowBots, getUser, getGuildWM)
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
@multipleDecorators(allowBots, getUser, getGuildWM)
async def unsubscribe_from_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    if await event.subscribers.filter(user__id=user.id).get_or_none() is not None:
        await event.subscribers.remove(member)
        await getGw().dispatch(ScheduledEventUserRemoveEvent(user.id, event_id, guild.id),
                               guild_id=guild.id)  # TODO: Replace with list of users subscribed to event

    return "", 204


@guilds.delete("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(allowBots, getUser, getGuildWM)
async def delete_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    if not (event := await getCore().getGuildEvent(event_id)) or event.guild != guild:
        raise InvalidDataErr(404, Errors.make(10070))

    await event.delete()
    await getGw().dispatch(GuildScheduledEventDeleteEvent(await event.ds_json()), guild_id=guild.id)

    return "", 204


@guilds.get("/<int:guild>/application-commands/<int:application_id>")
@multipleDecorators(getUser, getGuildWM)
async def get_guild_integration_commands(user: User, guild: Guild, member: GuildMember, application_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    integration = await Integration.get_or_none(guild=guild, application__id=application_id)
    if integration is None:
        return {"application_commands": [], "permissions": []}

    commands = await ApplicationCommand.filter(
        Q(guild=guild, application__id=application_id) | Q(guild=None, application__id=application_id)
    ).select_related("application", "guild").all()

    return {"application_commands": [command.ds_json() for command in commands], "permissions": []}
