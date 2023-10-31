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

from quart import Blueprint
from quart_schema import validate_querystring

from ..models.invites import GetInviteQuery
from ..utils import getUser, multipleDecorators, getInvite, allowBots
from ...gateway.events import MessageCreateEvent, DMChannelCreateEvent, ChannelRecipientAddEvent, GuildCreateEvent, \
    InviteDeleteEvent
from ...yepcord.ctx import getCore, getGw
from ...yepcord.enums import ChannelType, GuildPermissions, MessageType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import Invite, User, Message, GuildMember
from ...yepcord.snowflake import Snowflake

# Base path is /api/vX/invites
invites = Blueprint('invites', __name__)


@invites.get("/<string:invite>")
@multipleDecorators(validate_querystring(GetInviteQuery), getInvite)
async def get_invite(query_args: GetInviteQuery, invite: Invite):
    invite = await invite.ds_json(with_counts=query_args.with_counts)
    for excl in ["max_age", "created_at"]:  # Remove excluded fields
        if excl in invite:
            del invite[excl]
    return invite


@invites.post("/<string:invite>")
@multipleDecorators(getUser, getInvite)
async def use_invite(user: User, invite: Invite):
    channel = invite.channel
    inv = None
    if channel.type == ChannelType.GROUP_DM:
        recipients = await channel.recipients.all()
        if user not in recipients and len(recipients) >= 10:
            raise InvalidDataErr(404, Errors.make(10006))
        inv = await invite.ds_json()
        for excl in ["max_age", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        inv["new_member"] = user not in recipients
        if inv["new_member"]:
            message = await Message.create(
                id=Snowflake.makeId(), author=channel.owner, channel=channel, content="",
                type=MessageType.RECIPIENT_ADD, extra_data={"user": user.id}
            )
            await channel.recipients.add(user)
            await getGw().dispatch(ChannelRecipientAddEvent(channel.id, (await user.data).ds_json),
                                   users=[recipient.id for recipient in recipients])
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()),
                                   users=[recipient.id for recipient in recipients])
        await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": user.id}), users=[user.id])
        await getCore().useInvite(invite)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_NEWS):
        inv = await invite.ds_json()
        for excl in ["max_age", "max_uses", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        if not await getCore().getGuildMember(channel.guild, user.id):
            guild = channel.guild
            if await getCore().getGuildBan(guild, user.id) is not None:
                raise InvalidDataErr(403, Errors.make(40007))
            inv["new_member"] = True
            await GuildMember.create(id=Snowflake.makeId(), user=user, guild=guild)
            await getGw().dispatch(GuildCreateEvent(await guild.ds_json(user_id=user.id)), users=[user.id])
            if guild.system_channel:
                sys_channel = await getCore().getChannel(guild.system_channel)
                message = await Message.create(
                    id=Snowflake.makeId(), author=user, channel=sys_channel, content="", type=MessageType.USER_JOIN,
                    guild=guild
                )
                await getCore().sendMessage(message)
                await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=sys_channel.id)
            await getCore().useInvite(invite)
    return inv


@invites.delete("/<string:invite>")
@multipleDecorators(allowBots, getUser, getInvite)
async def delete_invite(user: User, invite: Invite):
    if invite.channel.guild:
        if (member := await getCore().getGuildMember(invite.channel.guild, user.id)) is None:
            raise InvalidDataErr(403, Errors.make(50001))
        await member.checkPermission(GuildPermissions.MANAGE_GUILD)
        await invite.delete()
        await getGw().dispatch(InviteDeleteEvent(invite), guild_id=invite.channel.guild.id)

        #entry = AuditLogEntry.invite_delete(invite, user)
        #await getCore().putAuditLogEntry(entry)
        #await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=invite.guild_id,
        #                       permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return await invite.ds_json()
