from quart import Blueprint, request
from quart_schema import validate_querystring

from ..models.invites import GetInviteQuery
from ..utils import usingDB, getUser, multipleDecorators, getInvite
from ...gateway.events import MessageCreateEvent, DMChannelCreateEvent, ChannelRecipientAddEvent, GuildCreateEvent, \
    InviteDeleteEvent
from ...yepcord.classes.guild import Invite, GuildId, AuditLogEntry
from ...yepcord.classes.message import Message
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore, Ctx, getGw
from ...yepcord.enums import ChannelType, GuildPermissions, MessageType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json

# Base path is /api/vX/invites
invites = Blueprint('invites', __name__)


@invites.get("/<string:invite>")
@multipleDecorators(validate_querystring(GetInviteQuery), usingDB, getInvite)
async def get_invite(query_args: GetInviteQuery, invite: Invite):
    Ctx["with_counts"] = query_args.with_counts
    invite = await invite.json
    for excl in ["max_age", "created_at"]: # Remove excluded fields
        if excl in invite:
            del invite[excl]
    return c_json(invite)


@invites.post("/<string:invite>")
@multipleDecorators(usingDB, getUser, getInvite)
async def use_invite(user: User, invite: Invite):
    channel = await getCore().getChannel(invite.channel_id)
    if channel.type == ChannelType.GROUP_DM:
        if user.id not in channel.recipients and len(channel.recipients) >= 10:
            raise InvalidDataErr(404, Errors.make(10006))
        inv = await invite.json
        for excl in ["max_age", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        inv["new_member"] = user.id not in channel.recipients
        if inv["new_member"]:
            message = Message(id=Snowflake.makeId(), author=channel.owner_id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": user.id})
            await getCore().addUserToGroupDM(channel, user.id)
            await getGw().dispatch(ChannelRecipientAddEvent(channel.id, await (await user.data).json), users=channel.recipients)
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.json), users=channel.recipients)
        Ctx["with_ids"] = False
        Ctx["user_id"] = user.id
        await getGw().dispatch(DMChannelCreateEvent(channel), users=[user.id])
        await getCore().useInvite(invite)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
        inv = await invite.json
        for excl in ["max_age", "max_uses", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        if not await getCore().getGuildMember(GuildId(invite.guild_id), user.id):
            guild = await getCore().getGuild(invite.guild_id)
            if await getCore().getGuildBan(guild, user.id) is not None:
                raise InvalidDataErr(403, Errors.make(40007))
            inv["new_member"] = True
            await getCore().createGuildMember(guild, user)
            await getGw().dispatch(GuildCreateEvent(await guild.json), users=[user.id])
            if guild.system_channel_id:
                message = Message(id=Snowflake.makeId(), author=user.id, channel_id=guild.system_channel_id, content="",
                              type=MessageType.USER_JOIN, guild_id=guild.id)
                await getCore().sendMessage(message)
                await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
            await getCore().useInvite(invite)
    return c_json(inv)


@invites.delete("/<string:invite>")
@multipleDecorators(usingDB, getUser, getInvite)
async def delete_invite(user: User, invite: Invite):
    if invite.guild_id:
        member = await getCore().getGuildMember(GuildId(invite.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_GUILD)
        await getCore().deleteInvite(invite)
        await getGw().dispatch(InviteDeleteEvent(invite), guild_id=invite.guild_id)

        entry = AuditLogEntry.invite_delete(invite, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)
    return c_json(await invite.json)