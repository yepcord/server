from os import urandom
from random import choice
from time import time

from emoji import is_emoji
from quart import Blueprint, request

from ..utils import usingDB, getUser, multipleDecorators, getChannel, getMessage, _getMessage, processMessageData
from ...yepcord.classes.channel import Channel, PermissionOverwrite
from ...yepcord.classes.guild import GuildId, AuditLogEntry, Webhook
from ...yepcord.classes.message import Reaction, SearchFilter, Message
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore, getCDNStorage, Ctx
from ...yepcord.enums import GuildPermissions, MessageType, ChannelType, RelationshipType, AuditLogEntryType, \
    WebhookType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.responses import channelInfoResponse
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, validImage, getImage, b64encode

# Base path is /api/vX/channels
channels = Blueprint('channels', __name__)


@channels.get("/<channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_channel(user: User, channel: Channel):
    return c_json(await channelInfoResponse(channel, user))


@channels.patch("/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def update_channel(user: User, channel: Channel):
    data: dict = dict(await request.get_json())
    if "icon" in data:
        if not (img := getImage(data["icon"])) or not validImage(img):
            del data["icon"]
        else:
            if not (v := await getCDNStorage().setChannelIconFromBytesIO(channel.id, img)):
                del data["icon"]
            else:
                data["icon"] = v
    if "owner" in data:
        if channel.owner_id != user.id:
            raise InvalidDataErr(403, Errors.make(50013))
        data["owner_id"] = int(data["owner"])
        del data["owner"]
    if "id" in data: del data["id"]
    if "type" in data: del data["type"]
    if "rate_limit_per_user" in data: del data["rate_limit_per_user"] # TODO
    if "default_thread_rate_limit_per_user" in data: del data["default_thread_rate_limit_per_user"] # TODO
    if "default_reaction_emoji" in data: del data["default_reaction_emoji"] # TODO
    if "guild_id" in data: del data["guild_id"]
    new_channel = channel.copy(**data)
    await getCore().updateChannelDiff(channel, new_channel)
    if channel.type == ChannelType.GROUP_DM:
        await getCore().sendDMChannelUpdateEvent(new_channel)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)
        await getCore().sendChannelUpdateEvent(new_channel)

        entry = AuditLogEntry.channel_update(channel, new_channel, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))
    diff = channel.getDiff(new_channel)
    if "name" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_NAME_CHANGE, content=new_channel.name)
        await getCore().sendMessage(message)
    if "icon" in diff and channel.type == ChannelType.GROUP_DM:
        message = Message(id=Snowflake.makeId(), channel_id=channel.id, author=user.id, type=MessageType.CHANNEL_ICON_CHANGE, content="")
        await getCore().sendMessage(message)
    channel.set(**data)
    return c_json(await channelInfoResponse(channel, user))


@channels.delete("/<int:channel>")
@multipleDecorators(usingDB, getUser, getChannel)
async def delete_channel(user: User, channel: Channel):
    if channel.type == ChannelType.DM:
        return "", 204 # TODO: hide dm channel
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
            nChannel = channel.copy()
            nChannel.owner_id = choice(channel.recipients)
            await getCore().updateChannelDiff(channel, nChannel)
            await getCore().sendDMChannelUpdateEvent(channel)
    elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, channel=channel)

        entry = AuditLogEntry.channel_delete(channel, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)

        await getCore().deleteChannel(channel)
        await getCore().sendGuildChannelDeleteEvent(channel)

        await getCore().setTemplateDirty(GuildId(channel.guild_id))

        return await channelInfoResponse(channel)
    return "", 204


@channels.get("/<int:channel>/messages")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_messages(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.VIEW_CHANNEL, GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    args = request.args
    messages = await channel.messages(args.get("limit", 50), int(args.get("before", 0)), int(args.get("after", 0)))
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
    message = Message(id=message_id, channel_id=channel.id, author=user.id, **data, **({} if not channel.guild_id else {"guild_id": channel.guild_id}))
    await message.check()
    message = await getCore().sendMessage(message)
    if await getCore().delReadStateIfExists(user.id, channel.id):
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
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def edit_message(user: User, channel: Channel, message: Message):
    data = await request.get_json()
    if message.author != user.id:
        raise InvalidDataErr(403, Errors.make(50005))
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.SEND_MESSAGES, GuildPermissions.VIEW_CHANNEL,
                                     GuildPermissions.READ_MESSAGE_HISTORY, channel=channel)
    before = message
    if "id" in data: del data["id"]
    if "channel_id" in data: del data["channel_id"]
    if "author" in data: del data["author"]
    if "edit_timestamp" in data: del data["edit_timestamp"]
    after = before.copy().set(edit_timestamp=int(time()), **data)
    after = await getCore().editMessage(before, after)
    return c_json(await after.json)

@channels.post("/<int:channel>/messages/<int:message>/ack")
@multipleDecorators(usingDB, getUser, getChannel)
async def send_message_ack(user: User, channel: Channel, message: Message):
    data = await request.get_json()
    if data.get("manual") and (ct := int(data.get("mention_count"))):
        if isinstance((message := await _getMessage(user, channel, message)), tuple):
            return message
        await getCore().setReadState(user.id, channel.id, ct, message.id)
        await getCore().sendMessageAck(user.id, channel.id, message.id, ct, True)
    else:
        await getCore().delReadStateIfExists(user.id, channel.id)
        await getCore().sendMessageAck(user.id, channel.id, message.id)
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
            message_reference=message.id,
            **({} if not channel.guild_id else {"guild_id": channel.guild_id})
        )
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
@multipleDecorators(usingDB, getUser, getChannel, getMessage)
async def get_message_reactions(user: User, channel: Channel, message: Message, reaction: str):
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
    limit = int(request.args.get("limit", 3))
    if limit > 10:
        limit = 10
    return await getCore().getReactedUsers(Reaction(message.id, 0, **r), limit)


@channels.get("/<int:channel>/messages/search")
@multipleDecorators(usingDB, getUser, getChannel)
async def search_messages(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.READ_MESSAGE_HISTORY, GuildPermissions.VIEW_CHANNEL, channel=channel)
    messages, total = await getCore().searchMessages(SearchFilter(**request.args))
    Ctx["search"] = True
    messages = [[await message.json] for message in messages]
    for message in messages:
        message[0]["hit"] = True
    return c_json({"messages": messages, "total_results": total})


@channels.post("/<int:channel>/invites")
@multipleDecorators(usingDB, getUser, getChannel)
async def create_invite(user: User, channel: Channel):
    if channel.get("guild_id"):
        member = await getCore().getGuildMember(GuildId(channel.guild_id), user.id)
        await member.checkPermission(GuildPermissions.CREATE_INSTANT_INVITE)
    data = await request.get_json()
    max_age = data.get("max_age", 86400)
    max_uses = data.get("max_uses", 0)
    invite = await getCore().createInvite(channel, user, max_age=max_age, max_uses=max_uses)
    if channel.get("guild_id"):
        entry = AuditLogEntry.invite_create(invite, user)
        await getCore().putAuditLogEntry(entry)
        await getCore().sendAuditLogEntryCreateEvent(entry)
    return c_json(await invite.json)


@channels.put("/<int:channel>/permissions/<int:target_id>")
@multipleDecorators(usingDB, getUser, getChannel)
async def create_or_update_permission_overwrite(user: User, channel: Channel, target_id: int):
    if not channel.guild_id:
        raise InvalidDataErr(403, Errors.make(50003))
    if not (guild := await getCore().getGuild(channel.guild_id)):
        raise InvalidDataErr(404, Errors.make(10004))
    if not (member := await getCore().getGuildMember(guild, user.id)):
        raise InvalidDataErr(403, Errors.make(50001))
    await member.checkPermission(GuildPermissions.MANAGE_CHANNELS, GuildPermissions.MANAGE_ROLES, channel=channel)
    data = await request.get_json()
    del data["id"]
    old_overwrite = await getCore().getPermissionOverwrite(channel, target_id)
    overwrite = PermissionOverwrite(**data, channel_id=channel.id, target_id=target_id)
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
@multipleDecorators(usingDB, getUser, getChannel)
async def create_webhook(user: User, channel: Channel):
    if not channel.get("guild_id"):
        raise InvalidDataErr(403, Errors.make(50003))
    guild = await getCore().getGuild(channel.guild_id)
    member = await getCore().getGuildMember(guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    data = await request.get_json()
    if not (name := data.get("name")):
        raise InvalidDataErr(400,
                             Errors.make(50035, {"name": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))

    webhook = Webhook(Snowflake.makeId(), guild.id, channel.id, user.id, WebhookType.INCOMING, name,
                      b64encode(urandom(48)), None, None)
    await getCore().putWebhook(webhook)
    await getCore().sendWebhooksUpdateEvent(webhook)

    return c_json(await webhook.json)


@channels.get("/api/v9/channels/<int:channel>/webhooks")
@multipleDecorators(usingDB, getUser, getChannel)
async def get_channel_webhooks(user: User, channel: Channel):
    if not channel.get("guild_id"):
        raise InvalidDataErr(403, Errors.make(50003))
    guild = await getCore().getGuild(channel.guild_id)
    member = await getCore().getGuildMember(guild, user.id)
    await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    webhooks = [await webhook.json for webhook in await getCore().getWebhooks(guild)] # TODO: Return webhooks from channels, not from guild
    return c_json(webhooks)