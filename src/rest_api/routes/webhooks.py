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
from typing import Optional

from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.channels import MessageUpdate
from ..models.webhooks import WebhookUpdate, WebhookMessageCreate, WebhookMessageCreateQuery
from ..utils import getUser, multipleDecorators, allowWithoutUser, processMessageData, allowBots, process_stickers, \
    validate_reply, processMessage, getWebhook, getMessage, getInteractionW
from ...gateway.events import MessageCreateEvent, WebhooksUpdateEvent, MessageUpdateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, MessageFlags
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Channel, Message, Interaction, Webhook
from ...yepcord.utils import getImage

# Base path is /api/vX/webhooks
webhooks = Blueprint('webhooks', __name__)


@webhooks.delete("/<int:webhook>")
@webhooks.delete("/<int:webhook>/<string:token>")
@multipleDecorators(allowWithoutUser, allowBots, getUser)
async def delete_webhook(user: Optional[User], webhook: int, token: Optional[str]=None):
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
@multipleDecorators(validate_request(WebhookUpdate), allowWithoutUser, allowBots, getUser)
async def edit_webhook(data: WebhookUpdate, user: Optional[User], webhook: int, token: Optional[str]=None):
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
            channel = await Channel.get_or_none(guild=webhook.channel.guild, id=data.channel_id).select_related("guild")
            if not channel or channel.guild != webhook.channel.guild: data.channel_id = None
    if (img := data.avatar) or img is None:
        if img is not None:
            img = getImage(img)
            if h := await getCDNStorage().setAvatarFromBytesIO(webhook.id, img):
                img = h
        data.avatar = img

    changes = data.model_dump(exclude_defaults=True)
    if "channel_id" in changes:
        changes["channel"] = channel
        del changes["channel_id"]

    await webhook.update(**changes)
    await getGw().dispatch(WebhooksUpdateEvent(guild.id, webhook.channel.id), guild_id=guild.id,
                           permissions=GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@webhooks.get("/<int:webhook>")
@webhooks.get("/<int:webhook>/<string:token>")
@multipleDecorators(allowWithoutUser, allowBots, getUser)
async def get_webhook(user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        guild = webhook.channel.guild
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@webhooks.post("/<int:webhook>/<string:token>")
@validate_querystring(WebhookMessageCreateQuery)
async def post_webhook_message(query_args: WebhookMessageCreateQuery, webhook: int, token: str):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        raise InvalidDataErr(403, Errors.make(50013))

    channel = webhook.channel
    message = await processMessage(await request.get_json(), channel, None, WebhookMessageCreate, webhook)

    message_json = await message.ds_json()
    await getCore().sendMessage(message)
    await getGw().dispatch(MessageCreateEvent(message_json), channel_id=channel.id)

    if query_args.wait:
        return message_json
    else:
        return "", 204


@webhooks.get("/<int:webhook>/<string:token>/messages/<int:message>")
@multipleDecorators(getWebhook, getMessage)
async def get_webhook_message(webhook: Webhook, message: Message):
    return await message.ds_json()


@webhooks.delete("/<int:webhook>/<string:token>/messages/<int:message>")
@multipleDecorators(getWebhook, getMessage)
async def delete_webhook_message(webhook: Webhook, message: Message):
    await message.delete()
    return "", 204


@webhooks.patch("/<int:webhook>/<string:token>/messages/<int:message>")
@multipleDecorators(validate_request(MessageUpdate), getWebhook, getMessage)
async def edit_webhook_message(data: MessageUpdate, webhook: Webhook, message: Message):
    await message.update(**data.to_json(), edit_timestamp=datetime.now())
    await getGw().dispatch(MessageUpdateEvent(await message.ds_json()), channel_id=webhook.channel.id)
    return await message.ds_json()


@webhooks.post("/<int:application_id>/int___<string:token>")
@getInteractionW
async def interaction_followup_create(interaction: Interaction, message: Message):
    channel = interaction.channel
    data = await request.get_json()

    data, attachments = await processMessageData(data, channel)
    data = WebhookMessageCreate(**data)

    await validate_reply(data, channel)
    stickers_data = await process_stickers(data.sticker_ids)
    if not data.content and not data.embeds and not attachments and not stickers_data["stickers"]:
        raise InvalidDataErr(400, Errors.make(50006))

    data_json = data.to_json() | stickers_data | {"flags": message.flags & ~MessageFlags.LOADING}
    await message.update(**data_json)
    message_obj = await message.ds_json()

    if message.ephemeral:
        await getGw().dispatch(MessageUpdateEvent(message_obj), users=[interaction.user.id, interaction.application.id])
    else:
        await getGw().dispatch(MessageUpdateEvent(message_obj), channel_id=interaction.channel.id)

    return message_obj


@webhooks.get("/<int:application_id>/int___<string:token>/messages/<string:message>")
@getInteractionW
async def get_interaction_message(interaction: Interaction, message: Message):
    return await message.ds_json()


@webhooks.delete("/<int:application_id>/int___<string:token>/messages/<string:message>")
@getInteractionW
async def delete_interaction_message(interaction: Interaction, message: Message):
    await message.delete()
    return "", 204


@webhooks.patch("/<int:application_id>/int___<string:token>/messages/<string:message>")
@multipleDecorators(validate_request(MessageUpdate), getInteractionW)
async def edit_interaction_message(data: MessageUpdate, interaction: Interaction, message: Message):
    await message.update(**data.to_json(), edit_timestamp=datetime.now())
    await getGw().dispatch(MessageUpdateEvent(await message.ds_json()), channel_id=interaction.channel.id)
    return await message.ds_json()
