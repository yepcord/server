from time import time

from quart import Blueprint, request

from ..utils import usingDB, getUser, multipleDecorators, getGuildWM, getGuildWoM, getGuildTemplate, getRole
from ...yepcord.classes.channel import Channel
from ...yepcord.classes.guild import Guild, Invite, AuditLogEntry, GuildTemplate, Emoji, Role
from ...yepcord.classes.message import Message
from ...yepcord.classes.user import User, GuildMember, UserId
from ...yepcord.ctx import getCore, getCDNStorage, Ctx
from ...yepcord.enums import GuildPermissions, AuditLogEntryType, ChannelType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.responses import channelInfoResponse
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, validImage, getImage, b64decode

# Base path is /api/vX/guilds
guilds = Blueprint('guilds', __name__)


@guilds.post("")
@multipleDecorators(usingDB, getUser)
async def create_guild(user: User):
    data = await request.get_json()
    guild = await getCore().createGuild(user, data["name"])
    Ctx["with_channels"] = True
    return c_json(await guild.json)


@guilds.patch("/<int:guild>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_guild(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    for j in ("id", "owner_id", "features", "max_members"):
        if j in data: del data[j]
    for image_type, func in (("icon", getCDNStorage().setGuildIconFromBytesIO), ("banner", getCDNStorage().setBannerFromBytesIO),
                             ("splash", getCDNStorage().setGuildSplashFromBytesIO)):
        if image_type in data:
            img = data[image_type]
            if img is not None:
                del data[image_type]
                if (img := getImage(img)) and validImage(img):
                    if h := await func(guild.id, img):
                        data[image_type] = h
    new_guild = guild.copy(**data)
    await getCore().updateGuildDiff(guild, new_guild)
    await getCore().sendGuildUpdateEvent(new_guild)

    entry = AuditLogEntry.guild_update(guild, new_guild, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await new_guild.json)


@guilds.get("/<int:guild>/templates")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def get_guild_templates(user: User, guild: Guild):
    templates = []
    if template := await getCore().getGuildTemplate(guild):
        templates.append(await template.json)
    return c_json(templates)


@guilds.post("/<int:guild>/templates")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def create_guild_template(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    if not (name := data.get("name")):
        raise InvalidDataErr(400, Errors.make(50035, {"name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    description = data.get("description")
    if await getCore().getGuildTemplate(guild):
        raise InvalidDataErr(400, Errors.make(30031))

    template = GuildTemplate(Snowflake.makeId(), guild.id, name, description, 0, user.id, int(time()),
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
@multipleDecorators(usingDB, getUser, getGuildWM, getGuildTemplate)
async def update_guild_template(user: User, guild: Guild, member: GuildMember, template: GuildTemplate):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    new_template = template.copy()
    if name := data.get("name"):
        new_template.set(name=name)
    if description := data.get("description"):
        new_template.set(description=description)
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
@multipleDecorators(usingDB, getUser, getGuildWM)
async def create_guild_emoji(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_EMOJIS_AND_STICKERS)
    data = await request.get_json()
    if not data.get("image"):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not data.get("name"):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if not (img := getImage(data["image"])) or not validImage(img):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    eid = Snowflake.makeId()
    if not (emd := await getCDNStorage().setEmojiFromBytesIO(eid, img)):
        raise InvalidDataErr(400, Errors.make(50035, {"image": {"code": "IMAGE_INVALID", "message": "Invalid image"}}))
    emoji = Emoji(eid, data["name"], user.id, guild.id, animated=emd["animated"])
    await getCore().addEmoji(emoji, guild)
    emoji.fill_defaults()

    entry = AuditLogEntry.emoji_create(emoji, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    return c_json(await emoji.json)


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
async def update_guild_channels(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    if not (data := await request.get_json()):
        return "", 204
    for change in data:
        if not (channel := await getCore().getChannel(int(change["id"]))):
            continue
        del change["id"]
        if "type" in change: del change["type"]
        if "guild_id" in change: del change["guild_id"]
        nChannel = Channel(channel.id, channel.type, channel.guild_id, **change)
        await getCore().updateChannelDiff(channel, nChannel)
        channel.set(**change)
        await getCore().sendChannelUpdateEvent(channel)
    await getCore().setTemplateDirty(guild)
    return "", 204


@guilds.post("/<int:guild>/channels")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def create_channel(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS)
    data = await request.get_json()
    if not data.get("name"):
        raise InvalidDataErr(400, Errors.make(50035, {"name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if "id" in data: del data["id"]
    ctype = data.get("type", ChannelType.GUILD_TEXT)
    if "type" in data: del data["type"]
    if "permission_overwrites" in data: del data["permission_overwrites"] # TODO: set permission_overwrites after channel creation
    channel = Channel(Snowflake.makeId(), ctype, guild_id=guild.id, **data)
    channel = await getCore().createGuildChannel(channel)
    await getCore().sendChannelCreateEvent(channel)

    entry = AuditLogEntry.channel_create(channel, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return await channelInfoResponse(channel)


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
@multipleDecorators(usingDB, getUser, getGuildWM)
async def ban_member(user: User, guild: Guild, member: GuildMember, uid: int):
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
            data = await request.get_json()
            if (delete_message_seconds := data.get("delete_message_seconds", 0)) > 0:
                if delete_message_seconds > 604800: delete_message_seconds = 604800 # 7 days
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
@multipleDecorators(usingDB, getUser, getGuildWM)
async def create_role(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    data = await request.get_json()
    if "id" in data: del data["id"]
    if "guild_id" in data: del data["guild_id"]
    role = Role(Snowflake.makeId(), guild.id, **data)
    await getCore().createGuildRole(role)
    await getCore().sendGuildRoleCreateEvent(role)

    entry = AuditLogEntry.role_create(role, user)
    await getCore().putAuditLogEntry(entry)
    await getCore().sendAuditLogEntryCreateEvent(entry)

    await getCore().setTemplateDirty(guild)

    return c_json(await role.json)


@guilds.patch("/<int:guild>/roles/<int:role>")
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def update_role(user: User, guild: Guild, member: GuildMember, role: Role):
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
                if h := await getCDNStorage().setRoleIconFromBytesIO(role.id, img):
                    data["icon"] = h
    new_role = role.copy(**data)
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
@multipleDecorators(usingDB, getUser, getGuildWM, getRole)
async def add_role_members(user: User, guild: Guild, member: GuildMember, role: Role):
    await member.checkPermission(GuildPermissions.MANAGE_ROLES)
    if (role.id == guild.id or role.position >= (await member.top_role).position) and member.id != guild.owner_id:
        raise InvalidDataErr(403, Errors.make(50013))
    members = {}
    member_ids = (await request.get_json()).get("member_ids", [])
    member_ids = [int(member_id) for member_id in member_ids]
    for member_id in member_ids:
        target_member = await getCore().getGuildMember(guild, member_id)
        if not await getCore().memberHasRole(target_member, role):
            await getCore().addMemberRole(target_member, role)
            await getCore().sendGuildMemberUpdateEvent(target_member)
            members[str(target_member.id)] = await target_member.json
    return c_json(members)


@guilds.patch("/<int:guild>/members/<string:target_user>")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_member(user: User, guild: Guild, member: GuildMember, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    data = await request.get_json()
    target_member = await getCore().getGuildMember(guild, target_user)
    new_member = target_member.copy()
    if "roles" in data: # TODO: add MEMBER_ROLE_UPDATE audit log event
        await member.checkPermission(GuildPermissions.MANAGE_ROLES)
        roles = [int(role) for role in data["roles"]]
        guild_roles = {role.id: role for role in await getCore().getRoles(guild)}
        roles = [role_id for role_id in roles if role_id in guild_roles]
        user_top_role = await member.top_role
        for role_id in roles:
            if guild_roles[role_id].position >= user_top_role.position:
                raise InvalidDataErr(403, Errors.make(50013))
        await getCore().setMemberRolesFromList(target_member, roles)
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
        await getCore().updateMemberDiff(target_member, new_member)
    target_member = new_member.copy()
    if "avatar" in data and target_member.user_id == member.user_id:
        avatar = data["avatar"]
        if (img := getImage(avatar)) and validImage(img):
            if av := await getCDNStorage().setGuildAvatarFromBytesIO(user.id, guild.id, img):
                avatar = av
            else:
                avatar = member.avatar
        elif avatar is None:
            pass
        else:
            avatar = member.avatar
        new_member = target_member.copy(avatar=avatar)
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
@multipleDecorators(usingDB, getUser, getGuildWM)
async def update_vanity_url(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    data = await request.get_json()
    if "code" not in data:
        return c_json({"code": guild.vanity_url_code})
    code = data.get("code")
    if code == guild.vanity_url_code:
        return c_json({"code": guild.vanity_url_code})
    if not code:
        new_guild = guild.copy(vanity_url_code=None)
        await getCore().updateGuildDiff(guild, new_guild)
        if invite := await getCore().getVanityCodeInvite(guild.vanity_url_code):
            await getCore().deleteInvite(invite)
    else:
        if guild.vanity_url_code and (invite := await getCore().getVanityCodeInvite(guild.vanity_url_code)):
            await getCore().deleteInvite(invite)
        new_guild = guild.copy(vanity_url_code=code)
        await getCore().updateGuildDiff(guild, new_guild)
        invite = Invite(Snowflake.makeId(), guild.system_channel_id, guild.owner_id, int(time()), 0, vanity_code=code,
                        guild_id=guild.id)
        await getCore().putInvite(invite)
    await getCore().sendGuildUpdateEvent(new_guild)
    return c_json({"code": new_guild.vanity_url_code})


@guilds.get("/<int:guild>/audit-logs")
@multipleDecorators(usingDB, getUser, getGuildWM)
async def get_audit_logs(user: User, guild: Guild, member: GuildMember):
    await member.checkPermission(GuildPermissions.MANAGE_GUILD)
    limit = int(request.args.get("limit", 50))
    if limit > 50: limit = 50
    before = request.args.get("before")
    if before is not None: before = int(before)
    entries = await getCore().getAuditLogEntries(guild, limit, before)
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
@multipleDecorators(usingDB, getUser)
async def create_from_template(user: User, template: str):
    try:
        template_id = int.from_bytes(b64decode(template), "big")
        if not (template := await getCore().getGuildTemplateById(template_id)):
            raise ValueError
    except ValueError:
        raise InvalidDataErr(404, Errors.make(10057))

    guild_id = Snowflake.makeId()
    data = await request.get_json()
    icon = None
    if img := data.get("icon"):
        if (img := getImage(img)) and validImage(img):
            if h := await getCDNStorage().setGuildIconFromBytesIO(guild_id, img):
                icon = h

    guild = await getCore().createGuildFromTemplate(guild_id, user, template, data.get("name"), icon)
    Ctx["with_channels"] = True
    return c_json(await guild.json)

@guilds.post("/<int:guild>/delete")
@multipleDecorators(usingDB, getUser, getGuildWoM)
async def delete_guild(user: User, guild: Guild):
    if user.id != guild.owner_id:
        raise InvalidDataErr(403, Errors.make(50013))

    data = await request.get_json()
    if mfa := await getCore().getMfa(user):
        code = data.get("code")
        code = code.replace("-", "").replace(" ", "")
        if not code:
            raise InvalidDataErr(400, Errors.make(60008))
        if code != mfa.getCode():
            if not (len(code) == 8 and await getCore().useMfaCode(mfa.uid, code)):
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
