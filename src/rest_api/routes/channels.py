from os import urandom
from random import choice
from time import time

from emoji import is_emoji
from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.channels import ChannelUpdate, MessageCreate, MessageUpdate, InviteCreate, PermissionOverwriteModel, \
    WebhookCreate, SearchQuery, GetMessagesQuery, GetReactionsQuery, MessageAck, CreateThread
from ..utils import usingDB, getUser, multipleDecorators, getChannel, getMessage, _getMessage, processMessageData
from ...yepcord.classes.channel import Channel, PermissionOverwrite, ThreadMetadata
from ...yepcord.classes.guild import GuildId, AuditLogEntry, Webhook
from ...yepcord.classes.message import Reaction, SearchFilter, Message
from ...yepcord.classes.user import User, UserId, ThreadMember
from ...yepcord.ctx import getCore, getCDNStorage, Ctx
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
    send_event = None
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
        send_event = getCore().sendDMChannelUpdateEvent
    elif channel.type in GUILD_CHANNELS:
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        new_channel = channel.copy(**data.to_json(channel.type))
        send_event = getCore().sendChannelUpdateEvent

    await getCore().updateChannelDiff(channel, new_channel)

    if channel.type == ChannelType.GROUP_DM:
        diff = channel.getDiff(new_channel)
        if "name" in diff:
            message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id,
                              type=MessageType.CHANNEL_NAME_CHANGE, content=new_channel.name)
            await getCore().sendMessage(message)
        if "icon" in diff:
            message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id,
                              type=MessageType.CHANNEL_ICON_CHANGE, content="")
            await getCore().sendMessage(message)
    elif channel.type in GUILD_CHANNELS:
        entry = AuditLogEntry.channel_update(channel, new_channel, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))

    await send_event(new_channel)
    return c_json(await new_channel.json)


@channels.delete("/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_channel(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        await getCore().hideDmChannel(user, channel)
        await getCore().sendDMChannelDeleteEvent(channel, users=[user.id])
        return c_json(await channel.json)
    elif channel.type == ChannelType.GROUP_DM:
        msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": user.id})
        await getCore().sendMessage(msg)
        await getCore().removeUserFromGroupDM(channel, user.id)
        await getCore().sendDMRepicientRemoveEvent(channel.recipients, channel.id, user.id)
        await getCore().sendDMChannelDeleteEvent(channel, users=[user.id])
        if len(channel.recipients) == 1:
            await getCore().deleteChannel(channel)
        elif channel.owner_id == user.id:
            channel.recipients.remove(user.id)
            new_channel = channel.copy()
            new_channel.owner_id = choice(channel.recipients)
            await getCore().updateChannelDiff(channel, new_channel)
            await getCore().sendDMChannelUpdateEvent(channel)
    elif channel.type in GUILD_CHANNELS:
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        entry = AuditLogEntry.channel_delete(channel, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)

        await getCore().deleteChannel(channel)
        await getCore().sendGuildChannelDeleteEvent(channel)

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
            await getCore().sendDMChannelCreateEvent(channel=channel, users=[other_user])
    message = await getCore().sendMessage(message)
    if await getCore().setReadState(user.id, channel.id, 0, message.id):
        await getCore().sendMessageAck(user.id, channel.id, message.id)
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
    return c_json(await new_message.json)

@channels.post("/<int:channel>/messages/<int:message>/ack")
@multipleDecorators(validate_request(MessageAck), usingDB, getUser, getChannel)
async def send_message_ack(data: MessageAck, user: User, channel: Channel, message: int):
    if data.manual and (ct := data.mention_count):
        message = await _getMessage(user, channel, message)
        await getCore().setReadState(user.id, channel.id, ct, message.id)
        await getCore().sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        ct = len(await getCore().getChannelMessages(channel, 99, channel.last_message_id, message))
        await getCore().setReadState(user.id, channel.id, ct, message)
        await getCore().sendMessageAck(user.id, channel.id, message)
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
    await getCore().sendTypingEvent(user, channel)
    return "", 204


@channels.put("/<int:channel>/recipients/<int:nUser>")
@multipleDecorators(usingDB, getUser, getChannel)
async def add_recipient(user: User, channel: Channel, nUser: int):
    if channel.type not in (ChannelType.DM, ChannelType.GROUP_DM):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.type == ChannelType.DM:
        rep = channel.recipients
        rep.remove(user.id)
        rep.append(nUser)
        ch = await getCore().createDMGroupChannel(user, rep)
        await getCore().sendDMChannelCreateEvent(ch)
    elif channel.type == ChannelType.GROUP_DM:
        if nUser not in channel.recipients and len(channel.recipients) < 10:
            msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_ADD, extra_data={"user": nUser})
            await getCore().sendMessage(msg)
            await getCore().addUserToGroupDM(channel, nUser)
            await getCore().sendDMRepicientAddEvent(channel.recipients, channel.id, nUser)
            await getCore().sendDMChannelCreateEvent(channel, users=[nUser])
    return "", 204


@channels.delete("/<int:channel>/recipients/<int:nUser>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_recipient(user: User, channel: Channel, nUser: int):
    if channel.type not in (ChannelType.GROUP_DM,):
        raise InvalidDataErr(403, Errors.make(50013))
    if channel.owner_id != user.id:
        raise InvalidDataErr(403, Errors.make(50013))
    if nUser in channel.recipients:
        msg = Message(id=Snowflake.makeId(), author=user.id, channel_id=channel.id, content="", type=MessageType.RECIPIENT_REMOVE, extra_data={"user": nUser})
        await getCore().sendMessage(msg)
        await getCore().removeUserFromGroupDM(channel, nUser)
        await getCore().sendDMRepicientRemoveEvent(channel.recipients, channel.id, nUser)
        await getCore().sendDMChannelDeleteEvent(channel, users=[nUser])
    return "", 204


@channels.put("/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def pin_message(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if not message.pinned:
        await getCore().pinMessage(message)
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
    return "", 204


@channels.delete("/<int:channel>/pins/<int:message>")
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def unpin_message(user: User, channel: Channel, message: Message):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.VIEW_CHANNEL, channel=channel)
    if message.pinned:
        await getCore().unpinMessage(message)
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
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().addReaction(Reaction(message.id, user.id, **r), channel)
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
    r = {
        "emoji_id": None if isinstance(reaction, str) else reaction.id,
        "emoji_name": reaction if isinstance(reaction, str) else reaction.name
    }
    await getCore().removeReaction(Reaction(message.id, user.id, **r), channel)
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
        await getCore().sendAuditLogEntryCreateEvent(entry)
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
    await getCore().sendChannelUpdateEvent(channel)

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
    await getCore().sendAuditLogEntryCreateEvent(entry)

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
    await getCore().sendChannelUpdateEvent(channel)

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
        await getCore().sendAuditLogEntryCreateEvent(entry)

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
    await getCore().sendWebhooksUpdateEvent(webhook)

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


@channels.post("/<int:channel>/messages/<int:message>/threads")
@multipleDecorators(validate_request(CreateThread), usingDB, getUser, getChannel, getMessage)
async def create_thread(data: CreateThread, user: User, channel: Channel, message: Message):
    if not channel.get("guild_id"):
        raise InvalidDataErr(403, Errors.make(50003))
    guild = await getCore().getGuild(channel.guild_id)
    member = await getCore().getGuildMember(guild, user.id)
    await member.checkPermission(GuildPermissions.CREATE_PUBLIC_THREADS, channel=channel)

    thread = Channel(message.id, ChannelType.GUILD_PUBLIC_THREAD, guild.id, name=data.name, owner_id=user.id,
                     parent_id=channel.id, flags=0)
    thread_member = ThreadMember(user.id, thread.id, guild.id, int(time()))
    thread_message = Message(Snowflake.makeId(), thread.id, user.id, content="",
                             message_reference={"message_id": message.id, "channel_id": channel.id, "guild_id": guild.id},
                             type=MessageType.THREAD_STARTER_MESSAGE)
    thread_create_message = Message(Snowflake.makeId(), channel.id, user.id, content=thread.name,
                             message_reference={"message_id": message.id, "channel_id": channel.id, "guild_id": guild.id},
                             type=MessageType.THREAD_CREATED)
    thread = await getCore().createGuildChannel(thread)
    await getCore().putThreadMetadata(ThreadMetadata(thread.id, False, 0, data.auto_archive_duration, False))
    await getCore().putThreadMember(thread_member)

    await getCore().sendThreadCreateEvent(thread, {"newly_created": True})
    await getCore().sendThreadMemberUpdateEvent(thread, thread_member)
    await getCore().editMessage(message, message.copy(thread=thread.id))
    await getCore().sendMessage(thread_message)
    await getCore().sendMessage(thread_create_message)

    return c_json(await thread.json)