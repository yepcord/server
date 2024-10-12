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

from ..dependencies import DepInvite, DepUser
from ..models.invites import GetInviteQuery
from ..y_blueprint import YBlueprint
from ...gateway.events import MessageCreateEvent, DMChannelCreateEvent, ChannelRecipientAddEvent, GuildCreateEvent, \
    InviteDeleteEvent
from ...yepcord.ctx import getGw
from ...yepcord.enums import ChannelType, GuildPermissions, MessageType
from ...yepcord.errors import UnknownInvite, UserBanned, MissingAccess
from ...yepcord.models import Invite, User, Message, GuildMember, GuildBan, Channel
from ...yepcord.snowflake import Snowflake

# Base path is /api/vX/invites
invites = YBlueprint('invites', __name__)


@invites.get("/<string:invite>", qs_cls=GetInviteQuery)
async def get_invite(query_args: GetInviteQuery, invite: Invite = DepInvite):
    invite = await invite.ds_json(with_counts=query_args.with_counts)
    for excl in ["max_age", "created_at"]:  # Remove excluded fields
        if excl in invite:
            del invite[excl]
    return invite


@invites.post("/<string:invite>")
async def use_invite(user: User = DepUser, invite: Invite = DepInvite):
    channel = invite.channel
    inv = None
    if channel.type == ChannelType.GROUP_DM:
        recipients = await channel.recipients.all()
        if user not in recipients and len(recipients) >= 10:
            raise UnknownInvite
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
                                   user_ids=[recipient.id for recipient in recipients])
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()),
                                   user_ids=[recipient.id for recipient in recipients])
        await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": user.id}),
                               user_ids=[user.id])
        await invite.use()
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_NEWS):
        inv = await invite.ds_json()
        for excl in ["max_age", "max_uses", "created_at"]:  # Remove excluded fields
            if excl in inv:
                del inv[excl]
        if not await GuildMember.exists(guild=channel.guild, user=user):
            guild = channel.guild
            if await GuildBan.exists(guild=guild, user=user):
                raise UserBanned
            inv["new_member"] = True
            await GuildMember.create(id=Snowflake.makeId(), user=user, guild=guild)
            await getGw().dispatch(GuildCreateEvent(await guild.ds_json(user_id=user.id)), user_ids=[user.id])
            if guild.system_channel:
                sys_channel = await Channel.Y.get(guild.system_channel)
                message = await Message.create(
                    id=Snowflake.makeId(), author=user, channel=sys_channel, content="", type=MessageType.USER_JOIN,
                    guild=guild
                )
                await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel=sys_channel,
                                       permissions=GuildPermissions.VIEW_CHANNEL)
            await invite.use()
            await getGw().dispatchSub([user.id], guild_id=guild.id)
    return inv


@invites.delete("/<string:invite>", allow_bots=True)
async def delete_invite(user: User = DepUser, invite: Invite = DepInvite):
    if invite.channel.guild:
        if (member := await invite.channel.guild.get_member(user.id)) is None:
            raise MissingAccess
        await member.checkPermission(GuildPermissions.MANAGE_GUILD)
        await invite.delete()
        await getGw().dispatch(InviteDeleteEvent(invite), guild_id=invite.channel.guild.id)

        #entry = AuditLogEntry.invite_delete(invite, user)
        #await getCore().putAuditLogEntry(entry)
        #await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=invite.guild_id,
        #                       permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return await invite.ds_json()
