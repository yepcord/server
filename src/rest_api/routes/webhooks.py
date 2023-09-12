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

from typing import Optional

from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.webhooks import WebhookUpdate, WebhookMessageCreate, WebhookMessageCreateQuery
from ..utils import getUser, multipleDecorators, allowWithoutUser, processMessageData
from ...gateway.events import MessageCreateEvent, WebhooksUpdateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, MessageType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Channel, Message
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage

# Base path is /api/vX/webhooks
webhooks = Blueprint('webhooks', __name__)


@webhooks.delete("/<int:webhook>")
@webhooks.delete("/<int:webhook>/<string:token>")
@multipleDecorators(allowWithoutUser, getUser)
async def api_webhooks_webhook_delete(user: Optional[User], webhook: int, token: Optional[str]=None):
    if webhook := await getCore().getWebhook(webhook):
        if webhook.token != token:
            guild = webhook.channel.guild
            if not (member := await getCore().getGuildMember(guild, user.id)):
                raise InvalidDataErr(403, Errors.make(50013))
            await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
        await webhook.delete()
        await getGw().dispatch(WebhooksUpdateEvent(webhook.channel.guild.id, webhook.channel.id),
                               guild_id=webhook.channel.guild.id, permissions=GuildPermissions.MANAGE_WEBHOOKS)

    return "", 204


@webhooks.patch("/<int:webhook>")
@webhooks.patch("/<int:webhook>/<string:token>")
@multipleDecorators(validate_request(WebhookUpdate), allowWithoutUser, getUser)
async def api_webhooks_webhook_patch(data: WebhookUpdate, user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    channel = webhook.channel
    guild = channel.guild
    if webhook.token != token:
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    if data.channel_id:
        if user.id == 0:
            data.channel_id = None
        else:
            channel = await Channel.objects.get_or_none(guild=webhook.channel.guild, id=data.channel_id)
            if not channel: data.channel_id = None
    if (img := data.avatar) or img is None:
        if img is not None:
            img = getImage(img)
            if h := await getCDNStorage().setAvatarFromBytesIO(webhook.id, img):
                img = h
        data.avatar = img

    changes = data.dict(exclude_defaults=True)
    if "channel_id" in changes:
        changes["channel"] = channel
        del changes["channel_id"]

    await webhook.update(**changes)
    await getGw().dispatch(WebhooksUpdateEvent(guild.id, webhook.channel.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@webhooks.get("/<int:webhook>")
@webhooks.get("/<int:webhook>/<string:token>")
@multipleDecorators(allowWithoutUser, getUser)
async def api_webhooks_webhook_get(user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        guild = webhook.channel.guild
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@webhooks.post("/<int:webhook>/<string:token>")
@multipleDecorators(validate_querystring(WebhookMessageCreateQuery))
async def api_webhooks_webhook_post(query_args: WebhookMessageCreateQuery, webhook: int, token: str):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        raise InvalidDataErr(403, Errors.make(50013))

    channel = webhook.channel
    data = await request.get_json()
    data, attachments = await processMessageData(data, channel)
    author = {
        "bot": True,
        "id": str(webhook.id),
        "username": data.get("username", webhook.name),
        "avatar": data.get("avatar", webhook.avatar),
        "discriminator": "0000"
    }
    data = WebhookMessageCreate(**data)

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

    message = await Message.objects.create(id=Snowflake.makeId(), channel=webhook.channel, author=None,
                                           guild=channel.guild, webhook_author=author, type=message_type,
                                           **stickers_data, **data_json)
    for attachment in attachments:
        await attachment.update(message=message)

    message_json = await message.ds_json()
    await getCore().sendMessage(message)
    await getGw().dispatch(MessageCreateEvent(message_json), channel_id=channel.id)

    if query_args.wait:
        return message_json
    else:
        return "", 204
