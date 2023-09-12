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
from os import urandom
from random import choice

from emoji import is_emoji
from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.channels import ChannelUpdate, MessageCreate, MessageUpdate, InviteCreate, PermissionOverwriteModel, \
    WebhookCreate, SearchQuery, GetMessagesQuery, GetReactionsQuery, MessageAck, CreateThread
from ..utils import getUser, multipleDecorators, getChannel, getMessage, _getMessage, processMessageData
from ...gateway.events import MessageCreateEvent, TypingEvent, MessageDeleteEvent, MessageUpdateEvent, \
    DMChannelCreateEvent, DMChannelUpdateEvent, ChannelRecipientAddEvent, ChannelRecipientRemoveEvent, \
    DMChannelDeleteEvent, MessageReactionAddEvent, MessageReactionRemoveEvent, ChannelUpdateEvent, ChannelDeleteEvent, \
    WebhooksUpdateEvent, ThreadCreateEvent, ThreadMemberUpdateEvent, MessageAckEvent, GuildAuditLogEntryCreateEvent
from ...yepcord.ctx import getCore, getCDNStorage, Ctx, getGw
from ...yepcord.enums import GuildPermissions, MessageType, ChannelType, RelationshipType, WebhookType, GUILD_CHANNELS
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Channel, Message, ReadState, Emoji, PermissionOverwrite, Webhook, ThreadMember, \
    ThreadMetadata, AuditLogEntry, Relationship
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage, b64encode

# Base path is /api/vX/channels
channels = Blueprint('channels', __name__)


@channels.get("/<channel>")
@multipleDecorators(getUser, getChannel)
async def get_channel(user: User, channel: Channel):
    return await channel.ds_json()


@channels.patch("/<int:channel>")
@multipleDecorators(validate_request(ChannelUpdate), getUser, getChannel)
async def update_channel(data: ChannelUpdate, user: User, channel: Channel):
    changed = []
    changes = {}
    if channel.type == ChannelType.GROUP_DM:
        changes = data.to_json(channel.type)
        if "owner_id" in changes and channel.owner.id != user.id:
            raise InvalidDataErr(403, Errors.make(50013))
        elif "owner_id" in changes:
            new_owner = await User.objects.get_or_none(id=changes["owner_id"])
            if new_owner in await channel.recipients.all():
                changes["owner"] = new_owner
            del changes["owner_id"]
        if "icon" in changes and changes["icon"] is not None:
            img = getImage(changes["icon"])
            if not (image := await getCDNStorage().setChannelIconFromBytesIO(channel.id, img)):
                del changes["icon"]
            else:
                changes["icon"] = image
        if "icon" in changes and changes["icon"] != channel.icon: changed.append("icon")
        if "name" in changes and changes["name"] != channel.name: changed.append("name")
        await channel.update(**changes)
        Ctx["with_ids"] = False
        await getGw().dispatch(DMChannelUpdateEvent(channel), channel_id=channel.id)
    elif channel.type in GUILD_CHANNELS:

        guild = channel.guild
        member = await getCore().getGuildMember(guild, user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        changes = data.to_json(channel.type)
        if "parent_id" in changes and changes["parent_id"] is not None:
            parent = await getCore().getChannel(changes["parent_id"])
            if parent:
                changes["parent"] = parent
            del changes["parent_id"]

        await channel.update(**changes)
        await getGw().dispatch(ChannelUpdateEvent(await channel.ds_json()), guild_id=channel.guild.id)

    if channel.type == ChannelType.GROUP_DM:
        if "name" in changed:
            message = Message(id=Snowflake.makeId(), channel=channel, author=user,
                              type=MessageType.CHANNEL_NAME_CHANGE, content=channel.name)
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=message.channel.id)
        if "icon" in changed:
            message = Message(id=Snowflake.makeId(), channel=channel.id, author=user,
                              type=MessageType.CHANNEL_ICON_CHANGE, content="")
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=message.channel.id)
    elif channel.type in GUILD_CHANNELS:
        if "parent_id" in changes and changes["parent_id"] is not None:
            changes["parent_id"] = changes["parent"].id
            del changes["parent"]
        entry = await AuditLogEntry.objects.channel_update(user, channel, changes)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=channel.guild.id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getCore().setTemplateDirty(channel.guild)

    return await channel.ds_json()


@channels.delete("/<int:channel>")
@multipleDecorators(getUser, getChannel)
async def delete_channel(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        await getCore().hideDmChannel(user, channel)
        await getGw().dispatch(DMChannelDeleteEvent(await channel.ds_json()), users=[user.id])
        return await channel.ds_json()
    elif channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), author=user, channel=channel, content="",
                          type=MessageType.RECIPIENT_REMOVE, extra_data={"user": user.id})
        await getCore().sendMessage(message)
        await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=channel.id)
        await channel.recipients.remove(user)
        await getGw().dispatch(ChannelRecipientRemoveEvent(channel.id, (await user.data).ds_json),
                               users=[user.id for user in await channel.recipients.all()])
        await getGw().dispatch(DMChannelDeleteEvent(await channel.ds_json()), users=[user.id])
        if await channel.recipients.count() == 0:
            await channel.delete()
        elif channel.owner == user:
            await channel.update(owner=choice(await channel.recipients.all()))
            await getGw().dispatch(DMChannelUpdateEvent(channel), channel_id=channel.id)
    elif channel.type in GUILD_CHANNELS:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        entry = await AuditLogEntry.objects.channel_delete(user, channel)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=channel.guild.id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        if channel.id == channel.guild.system_channel:
            await channel.guild.update(system_channel=None)
        elif channel.id == channel.guild.afk_channel:
            await channel.guild.update(afk_channel=None)
        await channel.delete()
        await getGw().dispatch(ChannelDeleteEvent(await channel.ds_json()), guild_id=channel.guild.id)

        await getCore().setTemplateDirty(channel.guild)

        return await channel.ds_json()
    return "", 204


@channels.get("/<int:channel>/messages")
@multipleDecorators(validate_querystring(GetMessagesQuery), getUser, getChannel)
async def get_messages(query_args: GetMessagesQuery, user: User, channel: Channel):
    if channel.guild is not None:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    messages = await channel.messages(**query_args.dict())
    messages = [await message.ds_json(user_id=user.id) for message in messages]
    return messages


@channels.post("/<int:channel>/messages")
@multipleDecorators(getUser, getChannel)
async def send_message(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        oth = await channel.other_user(user)
        if await Relationship.objects.is_blocked(oth, user):
            raise InvalidDataErr(403, Errors.make(50007))
    elif channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    data = await request.get_json()
    data, attachments = await processMessageData(data, channel)
    data = MessageCreate(**data)

    message_type = MessageType.DEFAULT
    if data.message_reference:
        data.validate_reply(channel, await getCore().getMessage(channel, data.message_reference.message_id))
    if data.message_reference:
        message_type = MessageType.REPLY

    stickers = [await getCore().getSticker(sticker_id) for sticker_id in data.sticker_ids]
    if not data.content and not data.embeds and not attachments and not data.sticker_ids:
        raise InvalidDataErr(400, Errors.make(50006))
    stickers_data = {"sticker_items": [], "stickers": []}
    for sticker in stickers:
        stickers_data["stickers"].append(await sticker.ds_json(False))
        stickers_data["sticker_items"].append({
            "format_type": sticker.format,
            "id": str(sticker.id),
            "name": sticker.name,
        })

    data_json = data.to_json()
    if "sticker_ids" in data_json: del data_json["sticker_ids"]

    message = await Message.objects.create(id=Snowflake.makeId(), channel=channel, author=user, **data_json,
                                           **stickers_data, type=message_type, guild=channel.guild)
    for attachment in attachments:
        await attachment.update(message=message)

    if channel.type == ChannelType.DM:
        other_user = await channel.other_user(user)
        if await getCore().isDmChannelHidden(other_user, channel):
            await getCore().unhideDmChannel(other_user, channel)
            await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": other_user.id}),
                                   users=[other_user.id])
    await getCore().sendMessage(message)
    await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=message.channel.id)
    await getCore().setReadState(user, channel, 0, message.id)
    await getGw().dispatch(MessageAckEvent({"version_id": 1, "message_id": str(message.id),
                                            "channel_id": str(message.channel.id)}), users=[user.id])
    return await message.ds_json()


@channels.delete("/<int:channel>/messages/<int:message>")
@multipleDecorators(getUser, getChannel, getMessage)
async def delete_message(user: User, channel: Channel, message: Message):
    if message.author != user:
        if channel.type in GUILD_CHANNELS:
            member = await getCore().getGuildMember(channel.guild, user.id)
            await member.checkPermission(GuildPermissions.MANAGE_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                         GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
        else:
            raise InvalidDataErr(403, Errors.make(50003))
    guild_id = channel.guild.id if channel.guild else None
    await message.delete()
    await getGw().dispatch(MessageDeleteEvent(message.id, channel.id, guild_id), channel_id=channel.id)
    return "", 204


@channels.patch("/<int:channel>/messages/<int:message>")
@multipleDecorators(validate_request(MessageUpdate), getUser, getChannel, getMessage)
async def edit_message(data: MessageUpdate, user: User, channel: Channel, message: Message):
    if message.author != user:
        raise InvalidDataErr(403, Errors.make(50005))
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    await message.update(edit_timestamp=datetime.now(), **data.to_json())
    await getGw().dispatch(MessageUpdateEvent(await message.ds_json()), channel_id=channel.id)
    return await message.ds_json()


@channels.post("/<int:channel>/messages/<int:message>/ack")
@multipleDecorators(validate_request(MessageAck), getUser, getChannel)
async def send_message_ack(data: MessageAck, user: User, channel: Channel, message: int):
    message = await _getMessage(user, channel, message)
    if data.manual and (ct := data.mention_count):
        await getCore().setReadState(user, channel, ct, message.id)
        await getGw().sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        ct = len(await getCore().getChannelMessages(channel, 99, channel.last_message_id, message.id))
        await getCore().setReadState(user, channel, ct, message.id)
        await getGw().dispatch(MessageAckEvent({"version_id": 1, "message_id": str(message.id),
                                                "channel_id": str(channel.id)}), users=[user.id])
    return {"token": None}


@channels.delete("/<int:channel>/messages/ack")
@multipleDecorators(getUser, getChannel)
async def delete_message_ack(user: User, channel: Channel):
    await ReadState.objects.delete(user=user, channel=channel)
    return "", 204


@channels.post("/<int:channel>/typing")
@multipleDecorators(getUser, getChannel)
async def send_typing_event(user: User, channel: Channel):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    await getGw().dispatch(TypingEvent(user.id, channel.id), channel_id=channel.id)
    return "", 204


@channels.put("/<int:channel>/recipients/<int:target_user>")
@multipleDecorators(getUser, getChannel)
async def add_recipient(user: User, channel: Channel, target_user: int):
    if (target_user := await getCore().getUser(target_user, False)) is None:
        raise InvalidDataErr(404, Errors.make(10013))
    if channel.type not in (ChannelType.DM, ChannelType.GROUP_DM):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.type == ChannelType.DM:
        recipients = await channel.recipients.exclude(id=user.id).all()
        recipients.append(target_user)
        ch = await getCore().createDMGroupChannel(user, recipients)
        await getGw().dispatch(DMChannelCreateEvent(ch), channel_id=channel.id)
    elif channel.type == ChannelType.GROUP_DM:
        recipients = await channel.recipients.all()
        if target_user not in recipients and len(recipients) < 10:
            message = await Message.objects.create(id=Snowflake.makeId(), author=user, channel=channel, content="",
                                                   type=MessageType.RECIPIENT_ADD, extra_data={"user": target_user.id})
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=message.channel.id)
            await channel.recipients.add(target_user)
            target_user_data = await target_user.data
            await getGw().dispatch(ChannelRecipientAddEvent(channel.id, target_user_data.ds_json),
                                   users=[recipient.id for recipient in recipients])
            await getGw().dispatch(DMChannelCreateEvent(channel, channel_json_kwargs={"user_id": target_user.id}),
                                   users=[target_user.id])
    return "", 204


@channels.delete("/<int:channel>/recipients/<int:target_user>")
@multipleDecorators(getUser, getChannel)
async def delete_recipient(user: User, channel: Channel, target_user: int):
    if channel.type not in (ChannelType.GROUP_DM,):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.owner != user or target_user == user.id:
        raise InvalidDataErr(403, Errors.make(50013))
    target_user = await getCore().getUser(target_user, False)
    recipients = await channel.recipients.all()
    if target_user in recipients:
        msg = await Message.objects.create(id=Snowflake.makeId(), author=user, channel=channel, content="",
                                           type=MessageType.RECIPIENT_REMOVE, extra_data={"user": target_user.id})
        await getCore().sendMessage(msg)
        await getGw().dispatch(MessageCreateEvent(await msg.ds_json()), channel_id=msg.channel.id)
        await channel.recipients.remove(target_user)
        target_user_data = await target_user.data
        await getGw().dispatch(ChannelRecipientRemoveEvent(channel.id, target_user_data.ds_json),
                               users=[recipient.id for recipient in recipients])
        await getGw().dispatch(DMChannelDeleteEvent(await channel.ds_json()), users=[target_user.id])
    return "", 204


@channels.put("/<int:channel>/pins/<int:message>")
@multipleDecorators(getUser, getChannel, getMessage)
async def pin_message(user: User, channel: Channel, message: Message):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not message.pinned:
        await getCore().pinMessage(message)
        await getGw().sendPinsUpdateEvent(channel)
        message_ref = {"message_id": str(message.id), "channel_id": str(channel.id)}
        if channel.guild:
            message_ref["guild_id"] = str(channel.guild.id)
        msg = await Message.objects.create(
            id=Snowflake.makeId(), author=user, channel=channel, type=MessageType.CHANNEL_PINNED_MESSAGE, content="",
            message_reference=message_ref, guild=channel.guild
        )

        await getCore().sendMessage(msg)
        await getGw().dispatch(MessageCreateEvent(await msg.ds_json()), channel_id=msg.channel.id)
    return "", 204


@channels.delete("/<int:channel>/pins/<int:message>")
@multipleDecorators(getUser, getChannel, getMessage)
async def unpin_message(user: User, channel: Channel, message: Message):
    if channel.guild:
        member = await getCore().getGuildMember(message.guild, user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if message.pinned:
        await message.update(pinned=False)
        await getGw().sendPinsUpdateEvent(channel)
    return "", 204


@channels.get("/<int:channel>/pins")
@multipleDecorators(getUser, getChannel)
async def get_pinned_messages(user: User, channel: Channel):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, GuildPermissions.READ_MESSAGE_HISTORY,
                                     channel=channel)
    messages = await getCore().getPinnedMessages(channel)
    messages = [await message.ds_json() for message in messages]
    return messages


@channels.put("/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(getUser, getChannel, getMessage)
async def add_message_reaction(user: User, channel: Channel, message: Message, reaction: str):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    emoji = {
        "emoji": None if not isinstance(reaction, Emoji) else reaction,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().addReaction(message, user, **emoji)
    await getGw().dispatch(MessageReactionAddEvent(user.id, message.id, channel.id, emoji), channel_id=channel.id)
    return "", 204


@channels.delete("/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(getUser, getChannel, getMessage)
async def remove_message_reaction(user: User, channel: Channel, message: Message, reaction: str):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    emoji = {
        "emoji": None if not isinstance(reaction, Emoji) else reaction,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().removeReaction(message, user, **emoji)
    await getGw().dispatch(MessageReactionRemoveEvent(user.id, message.id, channel.id, emoji), channel_id=channel.id)
    return "", 204


@channels.get("/<int:channel>/messages/<int:message>/reactions/<string:reaction>")
@multipleDecorators(validate_querystring(GetReactionsQuery), getUser, getChannel, getMessage)
async def get_message_reactions(query_args: GetReactionsQuery, user: User, channel: Channel, message: Message, reaction: str):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    emoji_data = {
        "emoji": None if not isinstance(reaction, Emoji) else reaction,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    return await getCore().getReactedUsersJ(message, query_args.limit, **emoji_data)


@channels.get("/<int:channel>/messages/search")
@multipleDecorators(validate_querystring(SearchQuery), getUser, getChannel)
async def search_messages(query: SearchQuery, user: User, channel: Channel):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, GuildPermissions.VIEW_CHANNEL,
                                     channel=channel)
    messages, total = await getCore().searchMessages(query.dict(exclude_defaults=True))
    messages = [[await message.ds_json(search=True)] for message in messages]
    for message in messages:
        message[0]["hit"] = True
    return {"messages": messages, "total_results": total}


@channels.post("/<int:channel>/invites")
@multipleDecorators(validate_request(InviteCreate), getUser, getChannel)
async def create_invite(data: InviteCreate, user: User, channel: Channel):
    if channel.guild:
        member = await getCore().getGuildMember(channel.guild, user.id)
        await member.checkPermission(GuildPermissions.CREATE_INSTANT_INVITE)
    invite = await getCore().createInvite(channel, user, **data.dict())
    if channel.guild:
        entry = await AuditLogEntry.objects.invite_create(user, invite)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=channel.guild.id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return await invite.ds_json()


@channels.put("/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(validate_request(PermissionOverwriteModel), getUser, getChannel)
async def create_or_update_permission_overwrite(data: PermissionOverwriteModel, user: User, channel: Channel, target_id: int):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (member := await getCore().getGuildMember(channel.guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    old_overwrite = await getCore().getPermissionOverwrite(channel, target_id)
    if old_overwrite is not None:
        await old_overwrite.update(**data.dict())
        overwrite = old_overwrite
    else:
        overwrite = await PermissionOverwrite.objects.create(**data.dict(), channel=channel, target_id=target_id)
    await getGw().dispatch(ChannelUpdateEvent(await channel.ds_json()), guild_id=channel.guild.id)

    if old_overwrite:
        entry = await AuditLogEntry.objects.overwrite_update(user, old_overwrite, overwrite)
    else:
        entry = await AuditLogEntry.objects.overwrite_create(user, overwrite)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=channel.guild.id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(channel.guild)

    return "", 204


@channels.delete("/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(getUser, getChannel)
async def delete_permission_overwrite(user: User, channel: Channel, target_id: int):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (member := await getCore().getGuildMember(channel.guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    overwrite = await getCore().getPermissionOverwrite(channel, target_id)
    await getCore().deletePermissionOverwrite(channel, target_id)
    await getGw().dispatch(ChannelUpdateEvent(await channel.ds_json()), guild_id=channel.guild.id)

    if overwrite:
        entry = await AuditLogEntry.objects.overwrite_delete(user, overwrite)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=channel.guild.id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getCore().setTemplateDirty(channel.guild)

    return "", 204


@channels.get("/<int:channel>/invites")
@multipleDecorators(getUser, getChannel)
async def get_channel_invites(user: User, channel: Channel):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (member := await getCore().getGuildMember(channel.guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    invites = await getCore().getChannelInvites(channel)
    return [await invite.ds_json() for invite in invites]


@channels.post("/<int:channel>/webhooks")
@multipleDecorators(validate_request(WebhookCreate), getUser, getChannel)
async def create_webhook(data: WebhookCreate, user: User, channel: Channel):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    member = await getCore().getGuildMember(channel.guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    webhook = await Webhook.objects.create(id=Snowflake.makeId(), type=WebhookType.INCOMING, name=data.name,
                                           channel=channel, user=user, token=b64encode(urandom(48)))
    await getGw().dispatch(WebhooksUpdateEvent(channel.guild.id, channel.id), guild_id=channel.guild.id,
                           permissions=GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@channels.get("/<int:channel>/webhooks")
@multipleDecorators(getUser, getChannel)
async def get_channel_webhooks(user: User, channel: Channel):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    member = await getCore().getGuildMember(channel.guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    return [await webhook.ds_json() for webhook in await getCore().getChannelWebhooks(channel)]


@channels.post("/<int:channel>/messages/<int:message>/threads")
@multipleDecorators(validate_request(CreateThread), getUser, getChannel, getMessage)
async def create_thread(data: CreateThread, user: User, channel: Channel, message: Message):
    if not channel.guild:
        raise InvalidDataErr(403, Errors.make(50003))
    member = await getCore().getGuildMember(channel.guild, user.id)
    await member.checkPermission(GuildPermissions.CREATE_PUBLIC_THREADS, channel=channel)

    thread = await Channel.objects.create(id=message.id, type=ChannelType.GUILD_PUBLIC_THREAD, guild=channel.guild,
                                          name=data.name, owner=user, parent=channel, flags=0)
    thread_member = await ThreadMember.objects.create(id=Snowflake.makeId(), user=user, channel=thread,
                                                      guild=channel.guild)
    thread_message = await Message.objects.create(
        id=Snowflake.makeId(), channel=thread, author=user, content="", type=MessageType.THREAD_STARTER_MESSAGE,
        message_reference={"message_id": message.id, "channel_id": channel.id, "guild_id": channel.guild.id}
    )
    thread_create_message = await Message.objects.create(
        id=Snowflake.makeId(), channel=channel, author=user, content=thread.name, type=MessageType.THREAD_CREATED,
        message_reference={"message_id": message.id, "channel_id": channel.id, "guild_id": channel.guild.id}
    )
    await ThreadMetadata.objects.create(id=thread.id, channel=thread, archive_timestamp=datetime(1970, 1, 1),
                                        auto_archive_duration=data.auto_archive_duration)

    await getGw().dispatch(ThreadCreateEvent(await thread.ds_json() | {"newly_created": True}),
                           guild_id=channel.guild.id)
    await getGw().dispatch(ThreadMemberUpdateEvent(thread_member.ds_json()), guild_id=channel.guild.id)
    await message.update(thread=thread)
    await getCore().sendMessage(thread_message)
    await getCore().sendMessage(thread_create_message)

    return await thread.ds_json()
