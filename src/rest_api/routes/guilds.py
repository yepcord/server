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
from ...yepcord.classes.channel import Channel
from ...yepcord.classes.guild import Guild, Invite, AuditLogEntry, GuildTemplate, Emoji, Role, Sticker, ScheduledEvent
from ...yepcord.classes.message import Message
from ...yepcord.classes.user import User, GuildMember, UserId
from ...yepcord.ctx import getCore, getCDNStorage, Ctx
from ...yepcord.enums import GuildPermissions, AuditLogEntryType, StickerType, StickerFormat, ScheduledEventStatus
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, getImage, b64decode, validImage, imageType

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
    Ctx["with_channels"] = True
    return c_json(await guild.json)


@guilds.patch("/<int:guild>")
@multipleDecorators(validate_request(GuildUpdate), usingDB, getUser, getGuildWM)
async def update_guild(data: GuildUpdate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data.owner_id = None # TODO: make guild ownership transfer
    for image_type, func in (("icon", getCDNStorage().setGuildIconFromBytesIO), ("banner", getCDNStorage().setBannerFromBytesIO),
                             ("splash", getCDNStorage().setGuildSplashFromBytesIO)):
        if img := getattr(data, image_type):
            setattr(data, image_type, "")
            img = getImage(img)
            if h := await func(guild.id, img):
                setattr(data, image_type, h)
    for ch in ("afk_channel_id", "system_channel_id"):
        if (channel_id := getattr(data, ch)) is not None:
            if (channel := await getCore().getChannel(channel_id)) is None:
                setattr(data, ch, None)
            elif channel.guild_id != guild.id:
                setattr(data, ch, None)
    new_guild = guild.copy(**data.dict(exclude_defaults=True))
    await getCore().updateGuildDiff(guild, new_guild)
    await getCore().sendGuildUpdateEvent(new_guild)

    entry = AuditLogEntry.guild_update(guild, new_guild, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await new_guild.json)


@guilds.get("/<int:guild>/templates")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_templates(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    templates = []
    if template := await getCore().getGuildTemplate(guild):
        templates.append(await template.json)
    return c_json(templates)


@guilds.post("/<int:guild>/templates")
@multipleDecorators(validate_request(TemplateCreate), usingDB, getUser, getGuildWM)
async def create_guild_template(data: TemplateCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if await getCore().getGuildTemplate(guild):
        raise InvalidDataErr(400, Errors.make(30031))

    template = GuildTemplate(Snowflake.makeId(), guild.id, data.name, data.description, 0, user.id, int(time()),
                             await GuildTemplate.serialize_guild(guild))
    await getCore().putGuildTemplate(template)

    return c_json(await template.json)


@guilds.delete("/<int:guild>/templates/<string:template>")
@multipleDecorators(usingDB, getUser, getGuildWM, getGuildTemplate)
async def delete_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    await getCore().deleteGuildTemplate(template)
    return c_json(await template.json)


@guilds.put("/<int:guild>/templates/<string:template>")
@multipleDecorators(usingDB, getUser, getGuildWM, getGuildTemplate)
async def sync_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    new_template = template.copy()
    if template.is_dirty:
        new_template.set(serialized_guild=await GuildTemplate.serialize_guild(guild), is_dirty=False,
                         updated_at=int(time()))
    await getCore().updateTemplateDiff(template, new_template)
    return c_json(await new_template.json)


@guilds.patch("/<int:guild>/templates/<string:template>")
@multipleDecorators(validate_request(TemplateUpdate), usingDB, getUser, getGuildWM, getGuildTemplate)
async def update_guild_template(data: TemplateUpdate, user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    new_template = template.copy(**data.dict(exclude_defaults=True))
    await getCore().updateTemplateDiff(template, new_template)
    return c_json(await new_template.json)


@guilds.get("/<int:guild>/emojis")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def get_guild_emojis(user: User, guild: Guild):
    emojis = await getCore().getEmojis(guild.id)
    Ctx["with_user"] = True
    emojis = [await emoji.json for emoji in emojis]
    return c_json(emojis)


@guilds.post("/<int:guild>/emojis")
@multipleDecorators(validate_request(EmojiCreate), usingDB, getUser, getGuildWM)
async def create_guild_emoji(data: EmojiCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    img = getImage(data.image)
    emoji_id = Snowflake.makeId()
    if not (emd := await getCDNStorage().setEmojiFromBytesIO(emoji_id, img)):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    emoji = Emoji(emoji_id, data.name, user.id, guild.id, animated=emd["animated"])
    await getCore().addEmoji(emoji, guild) # TODO: check if emojis limit exceeded
    emoji.fill_defaults()

    entry = AuditLogEntry.emoji_create(emoji, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    return c_json(await emoji.json)


@guilds.patch("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(validate_request(EmojiUpdate), usingDB, getUser, getGuildWM)
async def update_guild_emoji(data: EmojiUpdate, user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if (emoji := await getCore().getEmoji(emoji)) is None:
        raise InvalidDataErr(400, Errors.make(10014))
    elif emoji.guild_id != guild.id:
        raise InvalidDataErr(400, Errors.make(10014))
    new_emoji = emoji.copy(**data.dict(exclude_defaults=True))

    await getCore().updateEmojiDiff(emoji, new_emoji)
    await getCore().sendGuildEmojisUpdatedEvent(guild)

    return c_json(await new_emoji.json)


@guilds.delete("/<int:guild>/emojis/<int:emoji>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def delete_guild_emoji(user: User, guild: Guild, member: GuildMember, emoji: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    emoji = await getCore().getEmoji(emoji)
    if not emoji:
        return "", 204
    if emoji.guild_id != guild.id:
        return "", 204
    await getCore().deleteEmoji(emoji, guild)

    entry = AuditLogEntry.emoji_delete(emoji, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    return "", 204


@guilds.patch("/<int:guild>/channels")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_channels_positions(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data = await request.get_json()
    if not data:
        return "", 204
    data = ChannelsPositionsChangeList(changes=data)
    for change in data.changes:
        if not (channel := await getCore().getChannel(change.id)):
            continue
        if change.parent_id:
            if not (parent_channel := await getCore().getChannel(change.parent_id)):
                change.parent_id = 0
            elif parent_channel.guild_id != guild.id:
                change.parent_id = 0
        change = change.dict(exclude_defaults=True, exclude={"id"})
        new_channel = channel.copy(**change)
        await getCore().updateChannelDiff(channel, new_channel)
        await getCore().sendChannelUpdateEvent(new_channel)
    await getCore().setTemplateDirty(guild)
    return "", 204


@guilds.post("/<int:guild>/channels")
@multipleDecorators(validate_request(ChannelCreate), usingDB, getUser, getGuildWM)
async def create_channel(data: ChannelCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    channel = Channel(Snowflake.makeId(), guild_id=guild.id, **data.to_json(data.type))
    channel = await getCore().createGuildChannel(channel)
    await getCore().sendChannelCreateEvent(channel)

    entry = AuditLogEntry.channel_create(channel, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await channel.json)


@guilds.get("/<int:guild>/invites")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_invites(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    invites = await getCore().getGuildInvites(guild)
    invites = [await invite.json for invite in invites]
    return c_json(invites)


@guilds.get("/<int:guild>/premium/subscriptions")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_premium_boosts(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    boosts = [{"ended": False, "user_id": str(guild.owner_id)}]*30
    return c_json(boosts)


@guilds.delete("/<int:guild>/members/<int:uid>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def kick_member(user: User, guild: Guild, member: GuildMember, uid: int):
    await member.checkPermission(GuildPermissions.KICK_MEMBERS)
    if target_member := await getCore().getGuildMember(guild, uid):
        if not await member.perm_checker.canKickOrBan(target_member):
            raise InvalidDataErr(403, Errors.make(50013))
        await getCore().deleteGuildMember(target_member)
        await getCore().sendGuildMemberRemoveEvent(guild, await target_member.user)
        await getCore().sendGuildDeleteEvent(guild, target_member)
        entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, target_member.id, AuditLogEntryType.MEMBER_KICK)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)
    return "", 204


@guilds.put("/<int:guild>/bans/<int:uid>")
@multipleDecorators(validate_request(BanMember), usingDB, getUser, getGuildWM)
async def ban_member(data: BanMember, user: User, guild: Guild, member: GuildMember, uid: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    if target_member := await getCore().getGuildMember(guild, uid):
        if not await member.perm_checker.canKickOrBan(target_member):
            raise InvalidDataErr(403, Errors.make(50013))
        if await getCore().getGuildBan(guild, uid) is None:
            reason = request.headers.get("x-audit-log-reason")
            await getCore().deleteGuildMember(target_member)
            await getCore().banGuildMember(target_member, reason)
            target_user = await target_member.user
            await getCore().sendGuildMemberRemoveEvent(guild, target_user)
            await getCore().sendGuildDeleteEvent(guild, target_member)
            await getCore().sendGuildBanAddEvent(guild, target_user)
            if (delete_message_seconds := data.delete_message_seconds) > 0:
                after = Snowflake.fromTimestamp(int(time() - delete_message_seconds))
                deleted_messages = await getCore().bulkDeleteGuildMessagesFromBanned(guild, uid, after)
                for channel, messages in deleted_messages.items():
                    if len(messages) > 1:
                        await getCore().sendMessageBulkDeleteEvent(guild.id, channel, messages)
                    elif len(messages) == 1:
                        await getCore().sendMessageDeleteEvent(Message(messages[0], channel, uid))

            entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, target_member.id,
                                  AuditLogEntryType.MEMBER_BAN_ADD, reason=reason)
            await getCore().putAuditLogEntry(entry)
            await getCore().sendAuditLogEntryCreateEvent(entry)
    return "", 204


@guilds.get("/<int:guild>/bans")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_bans(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    bans = [await ban.json for ban in await getCore().getGuildBans(guild)]
    return c_json(bans)


@guilds.delete("/<int:guild>/bans/<int:user_id>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def unban_member(user: User, guild: Guild, member: GuildMember, user_id: int):
    await member.checkPermission(GuildPermissions.BAN_MEMBERS)
    await getCore().removeGuildBan(guild, user_id)
    await getCore().sendGuildBanRemoveEvent(guild, user_id)

    entry = AuditLogEntry(Snowflake.makeId(), guild.id, user.id, user_id, AuditLogEntryType.MEMBER_BAN_REMOVE)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)
    return "", 204


@guilds.get("/<int:guild>/integrations")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_integrations(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    return c_json([]) # TODO


@guilds.post("/<int:guild>/roles")
@multipleDecorators(validate_request(RoleCreate), usingDB, getUser, getGuildWM)
async def create_role(data: RoleCreate, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    role_id = Snowflake.makeId()
    if data.icon:
        img = getImage(data.icon)
        if h := await getCDNStorage().setRoleIconFromBytesIO(role_id, img):
            data.icon = h
    role = Role(role_id, guild.id, **data.dict())
    await getCore().createGuildRole(role)
    await getCore().sendGuildRoleCreateEvent(role)

    entry = AuditLogEntry.role_create(role, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await role.json)


@guilds.patch("/<int:guild>/roles/<int:role>")
@multipleDecorators(validate_request(RoleUpdate), usingDB, getUser, getGuildWM, getRole)
async def update_role(data: RoleUpdate, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == guild.id:
        data = {"permissions": data.permissions} if data.permissions is not None else {} # Only allow permissions editing for @everyone role
    if data.icon != "":
        if (img := data.icon) is not None:
            data.icon = ""
            img = getImage(img)
            if h := await getCDNStorage().setRoleIconFromBytesIO(role.id, img):
                data.icon = h
    new_role = role.copy(**data.dict(exclude_defaults=True))
    await getCore().updateRoleDiff(role, new_role)
    await getCore().sendGuildRoleUpdateEvent(new_role)

    entry = AuditLogEntry.role_update(role, new_role, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await new_role.json)


@guilds.patch("/<int:guild>/roles")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_roles_positions(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    roles_data = await request.get_json()
    roles = await getCore().getRoles(guild)
    roles.remove([role for role in roles if role.id == guild.id][0]) # Remove @everyone role

    if not await member.perm_checker.canChangeRolesPositions(roles_data, roles):
        raise InvalidDataErr(403, Errors.make(50013))

    roles_data = RolesPositionsChangeList(changes=roles_data)

    changes = []
    for data in roles_data.changes:
        if not (role := [role for role in roles if role.id == data.id]): continue # Don't add non-existing roles
        role = role[0]
        if (pos := data.position) < 1: pos = 1
        new_role = role.copy(position=pos)
        changes.append(new_role)
    changes.sort(key=lambda r: (r.position, r.permissions))
    for idx, new_role in enumerate(changes):
        new_role.position = idx + 1 # Set new position
        if (old_role := [role for role in roles if role.id == new_role.id][0]).getDiff(new_role) == {}:
            continue
        await getCore().updateRoleDiff(old_role, new_role)
        await getCore().sendGuildRoleUpdateEvent(new_role)
    roles = await getCore().getRoles(guild)
    roles = [await role.json for role in roles]

    await getCore().setTemplateDirty(guild)

    return c_json(roles)


@guilds.delete("/<int:guild>/roles/<int:role>")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def delete_role(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if role.id == role.guild_id:
        raise InvalidDataErr(400, Errors.make(50028))
    await getCore().deleteRole(role)
    await getCore().sendGuildRoleDeleteEvent(role)

    entry = AuditLogEntry.role_delete(role, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return "", 204


@guilds.get("/<int:guild>/roles/<int:role>/connections/configuration")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def get_connections_configuration(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    return c_json([]) # TODO


@guilds.get("/<int:guild>/roles/member-counts")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_role_member_count(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    counts = await getCore().getRolesMemberCounts(guild)
    return c_json(counts)


@guilds.get("/<int:guild>/roles/<int:role>/member-ids")
@multipleDecorators(usingDB, getUser, getGuildWoM, getRole)
async def get_role_members(user: User, guild: Guild, role: Role):
    members = [str(member_id) for member_id in await getCore().getRolesMemberIds(role)]
    return c_json(members)


@guilds.patch("/<int:guild>/roles/<int:role>/members")
@multipleDecorators(validate_request(AddRoleMembers), usingDB, getUser, getGuildWM, getRole)
async def add_role_members(data: AddRoleMembers, user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if (role.id == guild.id or role.position >= (await member.top_role).position) and member.id != guild.owner_id:
        raise InvalidDataErr(403, Errors.make(50013))
    members = {}
    for member_id in data.member_ids:
        target_member = await getCore().getGuildMember(guild, member_id)
        if not await getCore().memberHasRole(target_member, role):
            await getCore().addMemberRole(target_member, role)
            await getCore().sendGuildMemberUpdateEvent(target_member)
            members[str(target_member.id)] = await target_member.json
    return c_json(members)


@guilds.patch("/<int:guild>/members/<string:target_user>")
@multipleDecorators(validate_request(MemberUpdate), usingDB, getUser, getGuildWM)
async def update_member(data: MemberUpdate, user: User, guild: Guild, member: GuildMember, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    target_member = await getCore().getGuildMember(guild, target_user)
    if data.roles is not None: # TODO: add MEMBER_ROLE_UPDATE audit log event
        await member.checkPermission(GuildPermissions.MANAGE_ROLES)
        roles = [int(role) for role in data.roles]
        guild_roles = {role.id: role for role in await getCore().getRoles(guild)}
        roles = [role_id for role_id in roles if role_id in guild_roles]
        user_top_role = await member.top_role
        for role_id in roles:
            if guild_roles[role_id].position >= user_top_role.position and member.id != guild.owner_id:
                raise InvalidDataErr(403, Errors.make(50013))
        await getCore().setMemberRolesFromList(target_member, roles)
        data.roles = None
    if data.nick is not None:
        await member.checkPermission(
            GuildPermissions.CHANGE_NICKNAME
            if target_member.user_id == member.user_id else
            GuildPermissions.MANAGE_NICKNAMES
        )
    if data.avatar != "":
        if target_member.user_id != member.user_id:
            raise InvalidDataErr(403, Errors.make(50013))
        img = data.avatar
        if img is not None:
            img = getImage(img)
            if av := await getCDNStorage().setGuildAvatarFromBytesIO(user.id, guild.id, img):
                data.avatar = av
            else:
                data.avatar = ""
    new_member = target_member.copy(**data.dict(exclude_defaults=True))
    await getCore().updateMemberDiff(target_member, new_member)
    await getCore().sendGuildMemberUpdateEvent(new_member)

    entry = AuditLogEntry.member_update(target_member, new_member, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    return c_json(await new_member.json)


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
    return c_json(code)


@guilds.patch("/<int:guild>/vanity-url")
@multipleDecorators(validate_request(SetVanityUrl), usingDB, getUser, getGuildWM)
async def update_vanity_url(data: SetVanityUrl, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    if data.code is None:
        return c_json({"code": guild.vanity_url_code})
    if data.code == guild.vanity_url_code:
        return c_json({"code": guild.vanity_url_code})
    if not data.code:
        new_guild = guild.copy(vanity_url_code=None)
        await getCore().updateGuildDiff(guild, new_guild)
        if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
            await getCore().deleteInvite(invite)
    else:
        if await getCore().getVanityCodeInvite(data.code):
            return c_json({"code": guild.vanity_url_code})
        if guild.vanity_url_code and (invite := await getCore().getVanityCodeInvite(guild.vanity_url_code)):
            await getCore().deleteInvite(invite)
        new_guild = guild.copy(vanity_url_code=data.code)
        await getCore().updateGuildDiff(guild, new_guild)
        invite = Invite(Snowflake.makeId(), guild.system_channel_id, guild.owner_id, int(time()), 0, vanity_code=data.code,
                        guild_id=guild.id)
        await getCore().putInvite(invite)
    await getCore().sendGuildUpdateEvent(new_guild)
    return c_json({"code": new_guild.vanity_url_code})


@guilds.get("/<int:guild>/audit-logs")
@multipleDecorators(validate_querystring(GetAuditLogsQuery), usingDB, getUser, getGuildWM)
async def get_audit_logs(query_args: GetAuditLogsQuery, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    entries = await getCore().getAuditLogEntries(guild, **query_args.dict())
    userdatas = {}
    for entry in entries:
        target_user_id = entry.target_user_id
        if target_user_id and target_user_id not in userdatas:
            userdatas[target_user_id] = await getCore().getUserData(UserId(target_user_id))
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
    Ctx["with_channels"] = True
    return c_json(await guild.json)


@guilds.post("/<int:guild>/delete")
@multipleDecorators(validate_request(GuildDelete), usingDB, getUser, getGuildWoM)
async def delete_guild(data: GuildDelete, user: User, guild: Guild):
    if user.id != guild.owner_id:
        raise InvalidDataErr(403, Errors.make(50013))

    if mfa := await getCore().getMfa(user):
        if not data.code:
            raise InvalidDataErr(400, Errors.make(60008))
        if data.code != mfa.getCode():
            if not (len(data.code) == 8 and await getCore().useMfaCode(mfa.uid, data.code)):
                raise InvalidDataErr(400, Errors.make(60008))

    await getCore().deleteGuild(guild)
    await getCore().sendGuildDeleteEvent(guild, user)

    return "", 204


@guilds.get("/<int:guild>/webhooks")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_guild_webhooks(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    webhooks = [await webhook.json for webhook in await getCore().getWebhooks(guild)]
    return c_json(webhooks)


@guilds.get("/<int:guild>/stickers")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def get_guild_stickers(user: User, guild: Guild):
    stickers = await getCore().getGuildStickers(guild)
    stickers = [await sticker.json for sticker in stickers]
    return c_json(stickers)


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
        if sticker_b.tell() > 1024 * 512 or not (img := getImage(sticker_b)) or not validImage(img):
            raise InvalidDataErr(400, Errors.make(50006))
        sticker_type = getattr(StickerFormat, str(imageType(img)).upper(), StickerFormat.PNG)
        sticker = Sticker(Snowflake.makeId(), guild.id, user.id, data.name, data.tags, StickerType.GUILD, sticker_type,
                          data.description)
        if not await getCDNStorage().setStickerFromBytesIO(sticker.id, img):
            raise InvalidDataErr(400, Errors.make(50006))
        await getCore().putSticker(sticker)
    await getCore().sendGuildStickerUpdateEvent(guild)

    return c_json(await sticker.json)


@guilds.patch("/<int:guild>/stickers/<int:sticker>")
@multipleDecorators(validate_request(UpdateSticker), usingDB, getUser, getGuildWM)
async def update_guild_sticker(data: UpdateSticker, user: User, guild: Guild, member: GuildMember, sticker: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker)):
        raise InvalidDataErr(404, Errors.make(10060))
    if sticker.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10060))
    new_sticker = sticker.copy(**data.dict(exclude_defaults=True))
    await getCore().updateStickerDiff(sticker, new_sticker)
    await getCore().sendGuildStickerUpdateEvent(guild)
    return c_json(await new_sticker.json)


@guilds.delete("/<int:guild>/stickers/<int:sticker>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def delete_guild_sticker(user: User, guild: Guild, member: GuildMember, sticker: int):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    if not (sticker := await getCore().getSticker(sticker)):
        raise InvalidDataErr(404, Errors.make(10060))
    if sticker.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10060))

    await getCore().deleteSticker(sticker)
    await getCore().sendGuildStickerUpdateEvent(guild)

    return "", 204


@guilds.post("/<int:guild>/scheduled-events")
@multipleDecorators(validate_request(CreateEvent), usingDB, getUser, getGuildWM)
async def create_scheduled_event(data: CreateEvent, user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    event_id = Snowflake.makeId()
    if (img := data.image) is not None:
        img = getImage(img)
        if imageType(img) not in ("png", "jpg", "jpeg"):
            raise InvalidDataErr(400,
                                 Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
        if h := await getCDNStorage().setGuildEventFromBytesIO(event_id, img):
            img = h
        data.image = img

    event = ScheduledEvent(event_id, guild.id, user.id, status=1, **data.dict())
    await getCore().putScheduledEvent(event)
    await getCore().sendScheduledEventCreateEvent(event)

    await getCore().subscribeToScheduledEvent(user, event)
    await getCore().sendScheduledEventUserAddEvent(user, event)

    return c_json(await event.json)


@guilds.get("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_querystring(GetScheduledEvent), usingDB, getUser, getGuildWoM)
async def get_scheduled_event(query_args: GetScheduledEvent, user: User, guild: Guild, event_id: int):
    event = await getCore().getScheduledEvent(event_id)
    if not event or event.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10070))

    if query_args.with_user_count:
        Ctx["with_user_count"] = True

    return c_json(await event.json)


@guilds.get("/<int:guild>/scheduled-events")
@multipleDecorators(validate_querystring(GetScheduledEvent), usingDB, getUser, getGuildWoM)
async def get_scheduled_events(query_args: GetScheduledEvent, user: User, guild: Guild):
    events = await getCore().getScheduledEvents(guild)

    if query_args.with_user_count:
        Ctx["with_user_count"] = True

    events = [await event.json for event in events]
    return c_json(events)


@guilds.patch("/<int:guild>/scheduled-events/<int:event_id>")
@multipleDecorators(validate_request(UpdateScheduledEvent), usingDB, getUser, getGuildWM)
async def update_scheduled_event(data: UpdateScheduledEvent, user: User, guild: Guild, member: GuildMember, event_id: int):
    await member.checkPermission(GuildPermissions.MANAGE_EVENTS)
    event = await getCore().getScheduledEvent(event_id)
    if not event or event.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10070))

    if (img := data.image) or img is None:
        if img is not None:
            img = getImage(img)
            if imageType(img) not in ("png", "jpg", "jpeg"):
                raise InvalidDataErr(400,
                                     Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
            if h := await getCDNStorage().setGuildEventFromBytesIO(event_id, img):
                img = h
        data.image = img

    new_event: ScheduledEvent = event.copy(**data.dict(exclude_defaults=True))

    valid_transition = True
    if event.status == ScheduledEventStatus.SCHEDULED:
        if new_event.status not in (ScheduledEventStatus.SCHEDULED, ScheduledEventStatus.ACTIVE, ScheduledEventStatus.CANCELED):
            valid_transition = False
    elif event.status == ScheduledEventStatus.ACTIVE and new_event.status != ScheduledEventStatus.COMPLETED:
        valid_transition = False
    elif event.status != new_event.status:
        valid_transition = False

    if not valid_transition:
        raise InvalidDataErr(400,
                             Errors.make(50035, {"status": {"code": "TRANSITION_INVALID",
                                                            "message": "Invalid Guild Scheduled Event Status Transition"}}))

    await getCore().updateScheduledEventDiff(event, new_event)
    await getCore().sendScheduledEventUpdateEvent(new_event)

    return c_json(await new_event.json)


@guilds.put("/<int:guild>/scheduled-events/<int:event_id>/users/@me")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def subscribe_to_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    event = await getCore().getScheduledEvent(event_id)
    if not event or event.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10070))

    await getCore().subscribeToScheduledEvent(user, event)
    await getCore().sendScheduledEventUserAddEvent(user, event)

    return c_json({
        "guild_scheduled_event_id": str(event.id),
        "user_id": str(user.id) # current user or creator??
    })


@guilds.delete("/<int:guild>/scheduled-events/<int:event_id>/users/@me")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def unsubscribe_from_scheduled_event(user: User, guild: Guild, member: GuildMember, event_id: int):
    event = await getCore().getScheduledEvent(event_id)
    if not event or event.guild_id != guild.id:
        raise InvalidDataErr(404, Errors.make(10070))

    await getCore().unsubscribeFromScheduledEvent(user, event)
    await getCore().sendScheduledEventUserRemoveEvent(user, event)

    return "", 204