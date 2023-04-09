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

from os import urandom
from random import choice
from time import time

from emoji import is_emoji
from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.channels import ChannelUpdate, MessageCreate, MessageUpdate, InviteCreate, PermissionOverwriteModel, \
    WebhookCreate, SearchQuery, GetMessagesQuery, GetReactionsQuery, MessageAck
from ..utils import usingDB, getUser, multipleDecorators, getChannel, getMessage, _getMessage, processMessageData
from ...gateway.events import MessageCreateEvent, TypingEvent, MessageDeleteEvent, MessageUpdateEvent, \
    DMChannelCreateEvent, DMChannelUpdateEvent, ChannelRecipientAddEvent, ChannelRecipientRemoveEvent, \
    DMChannelDeleteEvent, MessageReactionAddEvent, MessageReactionRemoveEvent, ChannelUpdateEvent, ChannelDeleteEvent, \
    GuildAuditLogEntryCreateEvent, WebhooksUpdateEvent
from ...yepcord.classes.channel import Channel, PermissionOverwrite
from ...yepcord.classes.guild import GuildId, AuditLogEntry, Webhook
from ...yepcord.classes.message import Reaction, SearchFilter, Message
from ...yepcord.classes.user import User, UserId
from ...yepcord.ctx import getCore, getCDNStorage, Ctx, getGw
from ...yepcord.enums import GuildPermissions, MessageType, ChannelType, RelationshipType, AuditLogEntryType, \
    WebhookType, GUILD_CHANNELS
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, getImage, b64encode

# Base path is /api/vX/channels
channels = Blueprint('channels', __name__)


@channels.get("/<channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_channel(user: User, channel: Channel):
    return c_json(await channel.json)


@channels.patch("/<int:channel>")
@multipleDecorators(validate_request(ChannelUpdate), usingDB, getUser, getChannel)
async def update_channel(data: ChannelUpdate, user: User, channel: Channel):
    new_channel = channel
    if channel.type == ChannelType.GROUP_DM:
        new_channel = data.to_json(channel.type)
        if "owner_id" in new_channel and channel.owner_id != user.id:
            raise InvalidDataErr(403, Errors.make(50013))
        if "icon" in new_channel and new_channel["icon"] is not None:
            img = getImage(new_channel["icon"])
            if not (image := await getCDNStorage().setChannelIconFromBytesIO(channel.id, img)):
                del new_channel["icon"]
            else:
                new_channel["icon"] = image
        new_channel = channel.copy(**new_channel)
        Ctx["with_ids"] = False
        await getGw().dispatch(DMChannelUpdateEvent(new_channel), channel_id=channel.id)
    elif channel.type in GUILD_CHANNELS:
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        new_channel = channel.copy(**data.to_json(channel.type))
        await getGw().dispatch(ChannelUpdateEvent(await new_channel.json), guild_id=channel.guild_id)

    await getCore().updateChannelDiff(channel, new_channel)

    if channel.type == ChannelType.GROUP_DM:
        diff = channel.getDiff(new_channel)
        if "name" in diff:
            message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id,
                              type=MessageType.CHANNEL_NAME_CHANGE, content=new_channel.name)
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
        if "icon" in diff:
            message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id,
                              type=MessageType.CHANNEL_ICON_CHANGE, content="")
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
    elif channel.type in GUILD_CHANNELS:
        entry = AuditLogEntry.channel_update(channel, new_channel, user)
        await getCore().putAuditLogEntry(entry)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=channel.guild_id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))

    return c_json(await new_channel.json)


@channels.delete("/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_channel(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        await getCore().hideDmChannel(user, channel)
        await getGw().dispatch(DMChannelDeleteEvent(await channel.json), users=[user.id])
        return c_json(await channel.json)
    elif channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": user.id})
        await getCore().sendMessage(message)
        await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
        await getCore().removeUserFromGroupDM(channel, user.id)
        await getGw().dispatch(ChannelRecipientRemoveEvent(channel.id, await (await user.data).json), users=channel.recipients)
        await getGw().dispatch(DMChannelDeleteEvent(await channel.json), users=[user.id])
        if len(channel.recipients) == 1:
            await getCore().deleteChannel(channel)
        elif channel.owner_id == user.id:
            channel.recipients.remove(user.id)
            new_channel = channel.copy()
            new_channel.owner_id = choice(channel.recipients)
            await getCore().updateChannelDiff(channel, new_channel)
            Ctx["with_ids"] = False
            await getGw().dispatch(DMChannelUpdateEvent(channel), channel_id=channel.id)
    elif channel.type in GUILD_CHANNELS:
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        entry = AuditLogEntry.channel_delete(channel, user)
        await getCore().putAuditLogEntry(entry)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=channel.guild_id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getCore().deleteChannel(channel)
        await getGw().dispatch(ChannelDeleteEvent(await channel.json), guild_id=channel.guild_id)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))

        return c_json(await channel.json)
    return "", 204


@channels.get("/<int:channel>/messages")
@multipleDecorators(validate_querystring(GetMessagesQuery), usingDB, getUser, getChannel)
async def get_messages(query_args: GetMessagesQuery, user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    messages = await channel.messages(**query_args.dict())
    messages = [await m.json for m in messages]
    return c_json(messages)


@channels.post("/<int:channel>/messages")
@multipleDecorators(usingDB, getUser, getChannel)
async def send_message(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        oth = channel.recipients.copy()
        oth.remove(user.id)
        oth = oth[0]
        rel = await getCore().getRelationship(user.id, oth)
        if not rel:
            ... # TODO: Check
        if rel and rel.type == RelationshipType.BLOCK:
            raise InvalidDataErr(403, Errors.make(50007))
    elif channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    message_id = Snowflake.makeId()
    data = await request.get_json()
    data = await processMessageData(message_id, data, channel.id)
    data = MessageCreate(**data)

    message_type = MessageType.DEFAULT
    if data.message_reference:
        data.validate_reply(channel, await getCore().getMessage(channel, data.message_reference.message_id))
    if data.message_reference:
        message_type = MessageType.REPLY

    stickers = [await getCore().getSticker(sticker_id) for sticker_id in data.sticker_ids]
    if not data.content and not data.embeds and not await getCore().getAttachments(Message(message_id, 0, 0)) \
            and not data.sticker_ids:
        raise InvalidDataErr(400, Errors.make(50006))
    stickers_data = {"sticker_items": [], "stickers": []}
    Ctx["with_user"] = False
    for sticker in stickers:
        stickers_data["stickers"].append(await sticker.json)
        stickers_data["sticker_items"].append({
            "format_type": sticker.format,
            "id": str(sticker.id),
            "name": sticker.name,
        })
    message = Message(id=message_id, channel_id=channel.id, author=user.id, **data.to_json(), **stickers_data,
                      type=message_type, guild_id=channel.guild_id)
    if channel.type == ChannelType.DM:
        recipients = channel.recipients.copy()
        recipients.remove(user.id)
        other_user = recipients[0]
        if await getCore().isDmChannelHidden(UserId(other_user), channel):
            await getCore().unhideDmChannel(UserId(other_user), channel)
            Ctx["with_ids"] = False
            uid = Ctx.get("user_id")
            Ctx["user_id"] = other_user
            await getGw().dispatch(DMChannelCreateEvent(channel), users=[other_user])
            Ctx["user_id"] = uid
            Ctx["with_ids"] = True
    await getCore().sendMessage(message)
    await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
    if await getCore().setReadState(user.id, channel.id, 0, message.id):
        await getGw().sendMessageAck(user.id, channel.id, message.id)
    return c_json(await message.json)


@channels.delete("/<int:channel>/messages/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def delete_message(user: User, channel: Channel, message: Message):
    if message.author != user.id:
        if channel.get("guild_id"):
            member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
            await member.checkPermission(GuildPermissions.MANAGE_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                         GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
        else:
            raise InvalidDataErr(403, Errors.make(50003))
    await getCore().deleteMessage(message)
    await getGw().dispatch(MessageDeleteEvent(message.id, channel.id, message.guild_id), channel_id=channel.id)
    return "", 204


@channels.patch("/<int:channel>/messages/<int:message>")
@multipleDecorators(validate_request(MessageUpdate), usingDB, getUser, getChannel, getMessage)
async def edit_message(data: MessageUpdate, user: User, channel: Channel, message: Message):
    if message.author != user.id:
        raise InvalidDataErr(403, Errors.make(50005))
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    new_message = message.copy().set(edit_timestamp=int(time()), **data.to_json())
    new_message = await getCore().editMessage(message, new_message)
    await getGw().dispatch(MessageUpdateEvent(await new_message.json), channel_id=channel.id)
    return c_json(await new_message.json)

@channels.post("/<int:channel>/messages/<int:message>/ack")
@multipleDecorators(validate_request(MessageAck), usingDB, getUser, getChannel)
async def send_message_ack(data: MessageAck, user: User, channel: Channel, message: int):
    if data.manual and (ct := data.mention_count):
        message = await _getMessage(user, channel, message)
        await getCore().setReadState(user.id, channel.id, ct, message.id)
        await getGw().sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        ct = len(await getCore().getChannelMessages(channel, 99, channel.last_message_id, message))
        await getCore().setReadState(user.id, channel.id, ct, message)
        await getGw().sendMessageAck(user.id, channel.id, message)
    return c_json({"token": None})


@channels.delete("/<int:channel>/messages/ack")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_message_ack(user: User, channel: Channel):
    await getCore().deleteMessagesAck(channel, user)
    return "", 204


@channels.post("/<int:channel>/typing")
@multipleDecorators(usingDB, getUser, getChannel)
async def send_typing_event(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    await getGw().dispatch(TypingEvent(user.id, channel.id), channel_id=channel.id)
    return "", 204


@channels.put("/<int:channel>/recipients/<int:target_user>")
@multipleDecorators(usingDB, getUser, getChannel)
async def add_recipient(user: User, channel: Channel, target_user: int):
    if channel.type not in (ChannelType.DM, ChannelType.GROUP_DM):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.type == ChannelType.DM:
        rep = channel.recipients
        rep.remove(user.id)
        rep.append(target_user)
        ch = await getCore().createDMGroupChannel(user, rep)
        Ctx["with_ids"] = False
        await getGw().dispatch(DMChannelCreateEvent(ch), channel_id=channel.id)
    elif channel.type == ChannelType.GROUP_DM:
        if target_user not in channel.recipients and len(channel.recipients) < 10:
            message = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": target_user})
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.json), channel_id=message.channel_id)
            await getCore().addUserToGroupDM(channel, target_user)
            target_user_data = await getCore().getUserData(UserId(target_user))
            await getGw().dispatch(ChannelRecipientAddEvent(channel.id, await target_user_data.json), users=channel.recipients)
            Ctx["with_ids"] = False
            Ctx["user_id"] = target_user
            await getGw().dispatch(DMChannelCreateEvent(channel), users=[target_user])
    return "", 204


@channels.delete("/<int:channel>/recipients/<int:target_user>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_recipient(user: User, channel: Channel, target_user: int):
    if channel.type not in (ChannelType.GROUP_DM,):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.owner_id != user.id:
        raise InvalidDataErr(403, Errors.make(50013))
    if target_user in channel.recipients:
        msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": target_user})
        await getCore().sendMessage(msg)
        await getGw().dispatch(MessageCreateEvent(await msg.json), channel_id=msg.channel_id)
        await getCore().removeUserFromGroupDM(channel, target_user)
        target_user_data = await getCore().getUserData(UserId(target_user))
        await getGw().dispatch(ChannelRecipientRemoveEvent(channel.id, await target_user_data.json), users=channel.recipients)
        await getGw().dispatch(DMChannelDeleteEvent(await channel.json), users=[target_user])
    return "", 204


@channels.put("/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def pin_message(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not message.pinned:
        await getCore().pinMessage(message)
        await getGw().sendPinsUpdateEvent(channel)
        msg = Message(
            Snowflake.makeId(),
            author=user.id,
            channel_id=channel.id,
            type=MessageType.CHANNEL_PINNED_MESSAGE,
            content="",
            message_reference={"message_id": str(message.id), "channel_id": str(channel.id)},
            guild_id=channel.guild_id,
        )
        if channel.guild_id:
            msg.message_reference["guild_id"] = str(channel.guild_id)
        await getCore().sendMessage(msg)
        await getGw().dispatch(MessageCreateEvent(await msg.json), channel_id=msg.channel_id)
    return "", 204


@channels.delete("/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def unpin_message(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if message.pinned:
        await getCore().unpinMessage(message)
        await getGw().sendPinsUpdateEvent(channel)
    return "", 204


@channels.get("/<int:channel>/pins")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_pinned_messages(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    messages = await getCore().getPinnedMessages(channel.id)
    messages = [await message.json for message in messages]
    return messages


@channels.put("/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def add_message_reaction(user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    emoji = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().addReaction(Reaction(message.id, user.id, **emoji), channel)
    await getGw().dispatch(MessageReactionAddEvent(user.id, message.id, channel.id, emoji), channel_id=channel.id)
    return "", 204


@channels.delete("/<int:channel>/messages/<int:message>/reactions/<string:reaction>/@me")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def remove_message_reaction(user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    emoji = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().removeReaction(Reaction(message.id, user.id, **emoji), channel)
    await getGw().dispatch(MessageReactionRemoveEvent(user.id, message.id, channel.id, emoji), channel_id=channel.id)
    return "", 204


@channels.get("/<int:channel>/messages/<int:message>/reactions/<string:reaction>")
@multipleDecorators(validate_querystring(GetReactionsQuery), usingDB, getUser, getChannel, getMessage)
async def get_message_reactions(query_args: GetReactionsQuery, user: User, channel: Channel, message: Message, reaction: str):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.ADD_REACTIONS, GuildPermissions.READ_MESSAGE_HISTORY,
                                     GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not is_emoji(reaction) and not (reaction := await getCore().getEmojiByReaction(reaction)):
        raise InvalidDataErr(400, Errors.make(10014))
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    return await getCore().getReactedUsers(Reaction(message.id, 0, **r), query_args.limit)


@channels.get("/<int:channel>/messages/search")
@multipleDecorators(validate_querystring(SearchQuery), usingDB, getUser, getChannel)
async def search_messages(query: SearchQuery, user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, GuildPermissions.VIEW_CHANNEL, channel=channel)
    messages, total = await getCore().searchMessages(SearchFilter(**query.dict(exclude_defaults=True)))
    Ctx["search"] = True
    messages = [[await message.json] for message in messages]
    for message in messages:
        message[0]["hit"] = True
    return c_json({"messages": messages, "total_results": total})


@channels.post("/<int:channel>/invites")
@multipleDecorators(validate_request(InviteCreate), usingDB, getUser, getChannel)
async def create_invite(data: InviteCreate, user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.CREATE_INSTANT_INVITE)
    invite = await getCore().createInvite(channel, user, **data.dict())
    if channel.get("guild_id"):
        entry = AuditLogEntry.invite_create(invite, user)
        await getCore().putAuditLogEntry(entry)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=channel.guild_id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)
    return c_json(await invite.json)


@channels.put("/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(validate_request(PermissionOverwriteModel), usingDB, getUser, getChannel)
async def create_or_update_permission_overwrite(data: PermissionOverwriteModel, user: User, channel: Channel, target_id: int):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await getCore().getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await getCore().getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    old_overwrite = await getCore().getPermissionOverwrite(channel, target_id)
    overwrite = PermissionOverwrite(**data.dict(), channel_id=channel.id, target_id=target_id)
    await getCore().putPermissionOverwrite(overwrite)
    await getGw().dispatch(ChannelUpdateEvent(await channel.json), guild_id=channel.guild_id)

    if old_overwrite:
        t = AuditLogEntryType.CHANNEL_OVERWRITE_UPDATE
        changes = []
        if old_overwrite.allow != overwrite.allow:
            changes.append({"new_value": str(overwrite.allow), "old_value": str(old_overwrite.allow), "key": "allow"})
        if old_overwrite.deny != overwrite.deny:
            changes.append({"new_value": str(overwrite.deny), "old_value": str(old_overwrite.deny), "key": "deny"})
    else:
        t = AuditLogEntryType.CHANNEL_OVERWRITE_CREATE
        changes = [
            {"new_value": str(overwrite.target_id), "key": "id"},
            {"new_value": str(overwrite.type), "key": "type"},
            {"new_value": str(overwrite.allow), "key": "allow"},
            {"new_value": str(overwrite.deny), "key": "deny"}
        ]
    options = {
        "type": str(overwrite.type),
        "id": str(overwrite.target_id)
    }
    if overwrite.type == 0:
        role = await getCore().getRole(overwrite.target_id)
        options["role_name"] = role.name
    entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id, t, changes=changes, options=options)
    await getCore().putAuditLogEntry(entry)
    await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=channel.guild_id,
                           permissions=GuildPermissions.VIEW_AUDIT_LOG)

    await getCore().setTemplateDirty(GuildId(channel.guild_id))

    return "", 204


@channels.delete("/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_permission_overwrite(user: User, channel: Channel, target_id: int):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await getCore().getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await getCore().getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    overwrite = await getCore().getPermissionOverwrite(channel, target_id)
    await getCore().deletePermissionOverwrite(channel, target_id)
    await getGw().dispatch(ChannelUpdateEvent(await channel.json), guild_id=channel.guild_id)

    if overwrite:
        changes = [
            {"old_value": str(overwrite.target_id), "key": "id"},
            {"old_value": str(overwrite.type), "key": "type"},
            {"old_value": str(overwrite.allow), "key": "allow"},
            {"old_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0:
            role = await getCore().getRole(overwrite.target_id)
            options["role_name"] = role.name
        entry = AuditLogEntry(Snowflake.makeId(), channel.guild_id, user.id, channel.id,
                              AuditLogEntryType.CHANNEL_OVERWRITE_DELETE, changes=changes, options=options)
        await getCore().putAuditLogEntry(entry)
        await getGw().dispatch(GuildAuditLogEntryCreateEvent(await entry.json), guild_id=channel.guild_id,
                               permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))

    return "", 204


@channels.get("/<int:channel>/invites")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_channel_invites(user: User, channel: Channel):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await getCore().getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await getCore().getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.VIEW_CHANNEL, channel=channel)
    invites = await getCore().getChannelInvites(channel)
    invites = [await invite.json for invite in invites]
    return c_json(invites)


@channels.post("/<int:channel>/webhooks")
@multipleDecorators(validate_request(WebhookCreate), usingDB, getUser, getChannel)
async def create_webhook(data: WebhookCreate, user: User, channel: Channel):
    if not channel.get("guild_id"):
        raise InvalidDataErr(403, Errors.make(50003))
    guild = await getCore().getGuild(channel.guild_id)
    member = await getCore().getGuildMember(guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    webhook = Webhook(Snowflake.makeId(), guild.id, channel.id, user.id, WebhookType.INCOMING, data.name,
                      b64encode(urandom(48)), None, None)
    await getCore().putWebhook(webhook)
    await getGw().dispatch(WebhooksUpdateEvent(webhook.guild_id, webhook.channel_id), guild_id=webhook.guild_id,
                           permissions=GuildPermissions.MANAGE_WEBHOOKS)

    return c_json(await webhook.json)


@channels.get("/<int:channel>/webhooks")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_channel_webhooks(user: User, channel: Channel):
    if not channel.get("guild_id"):
        raise InvalidDataErr(403, Errors.make(50003))
    guild = await getCore().getGuild(channel.guild_id)
    member = await getCore().getGuildMember(guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    webhooks = [await webhook.json for webhook in await getCore().getWebhooks(guild)] # TODO: Return webhooks from channels, not from guild
    return c_json(webhooks)