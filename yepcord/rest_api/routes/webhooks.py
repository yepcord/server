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
from datetime import datetime
from typing import Optional

from quart import request

from ..dependencies import DepUserO, DepMessage, DepWebhook, DepInteractionW
from ..models.channels import MessageUpdate
from ..models.webhooks import WebhookUpdate, WebhookMessageCreate, WebhookMessageCreateQuery
from ..utils import processMessageData, process_stickers, validate_reply, processMessage
from ..y_blueprint import YBlueprint
from ...gateway.events import MessageCreateEvent, WebhooksUpdateEvent, MessageUpdateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, MessageFlags
from ...yepcord.errors import UnknownWebhook, MissingPermissions, CannotSendEmptyMessage
from ...yepcord.models import User, Channel, Message, Webhook
from ...yepcord.utils import getImage

# Base path is /api/vX/webhooks
webhooks = YBlueprint('webhooks', __name__)


@webhooks.delete("/<int:webhook_id>")
@webhooks.delete("/<int:webhook_id>/<string:token>", allow_bots=True)
async def delete_webhook(webhook_id: int, user: Optional[User] = DepUserO, token: Optional[str]=None):
    if (webhook := await Webhook.Y.get(webhook_id)) is None:
        return "", 204

    if webhook.token != token:
        guild = webhook.channel.guild
        if user is None or not (member := await guild.get_member(user.id)):
            raise MissingPermissions
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    await webhook.delete()
    await getGw().dispatch(
        WebhooksUpdateEvent(webhook.channel.guild.id, webhook.channel.id),
        guild_id=webhook.channel.guild.id,
        permissions=GuildPermissions.MANAGE_WEBHOOKS
    )

    return "", 204


@webhooks.patch("/<int:webhook_id>")
@webhooks.patch("/<int:webhook_id>/<string:token>", body_cls=WebhookUpdate, allow_bots=True)
async def edit_webhook(
        data: WebhookUpdate, webhook_id: int, user: Optional[User] = DepUserO, token: Optional[str] = None
):
    if (webhook := await Webhook.Y.get(webhook_id)) is None:
        raise UnknownWebhook
    channel = webhook.channel
    guild = channel.guild
    if webhook.token != token:
        if user is None or not (member := await guild.get_member(user.id)):
            raise MissingPermissions
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    if data.channel_id:
        if user is None:
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


@webhooks.get("/<int:webhook_id>")
@webhooks.get("/<int:webhook_id>/<string:token>", allow_bots=True)
async def get_webhook(webhook_id: int, user: Optional[User] = DepUserO, token: Optional[str]=None):
    if (webhook := await Webhook.Y.get(webhook_id)) is None:
        raise UnknownWebhook
    if webhook.token != token:
        guild = webhook.channel.guild
        if user is None or not (member := await guild.get_member(user.id)):
            raise MissingPermissions
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    return await webhook.ds_json()


@webhooks.post("/<int:webhook_id>/<string:token>", qs_cls=WebhookMessageCreateQuery)
async def post_webhook_message(query_args: WebhookMessageCreateQuery, webhook_id: int, token: str):
    if (webhook := await Webhook.Y.get(webhook_id)) is None:
        raise UnknownWebhook
    if webhook.token != token:
        raise MissingPermissions

    channel = webhook.channel
    message = await processMessage(await request.get_json(), channel, None, WebhookMessageCreate, webhook)

    message_json = await message.ds_json()
    await getGw().dispatch(MessageCreateEvent(message_json), channel=channel, permissions=GuildPermissions.VIEW_CHANNEL)

    if query_args.wait:
        return message_json
    else:
        return "", 204


@webhooks.get("/<int:webhook>/<string:token>/messages/<int:message>")
async def get_webhook_message(message: Message = DepMessage):
    return await message.ds_json()


@webhooks.delete("/<int:webhook>/<string:token>/messages/<int:message>")
async def delete_webhook_message(message: Message = DepMessage):
    await message.delete()
    return "", 204


@webhooks.patch("/<int:webhook>/<string:token>/messages/<int:message>", body_cls=MessageUpdate)
async def edit_webhook_message(data: MessageUpdate, webhook: Webhook = DepWebhook, message: Message = DepMessage):
    await message.update(**data.to_json(), edit_timestamp=datetime.now())
    await getGw().dispatch(MessageUpdateEvent(await message.ds_json()), channel=webhook.channel,
                           permissions=GuildPermissions.VIEW_CHANNEL)
    return await message.ds_json()


@webhooks.post("/<int:application_id>/int___<string:token>")
async def interaction_followup_create(message: Message = DepInteractionW):
    interaction = message.interaction
    channel = interaction.channel
    data = await request.get_json()

    data, attachments = await processMessageData(data, channel)
    data = WebhookMessageCreate(**data)

    await validate_reply(data, channel)
    stickers_data = await process_stickers(data.sticker_ids)
    if not data.content and not data.embeds and not attachments and not stickers_data["stickers"]:
        raise CannotSendEmptyMessage

    data_json = data.to_json() | stickers_data | {"flags": message.flags & ~MessageFlags.LOADING}
    await message.update(**data_json)
    message_obj = await message.ds_json()

    if message.ephemeral:
        await getGw().dispatch(MessageUpdateEvent(message_obj),
                               user_ids=[interaction.user.id, interaction.application.id])
    else:
        await getGw().dispatch(MessageUpdateEvent(message_obj), channel=message.channel,
                               permissions=GuildPermissions.VIEW_CHANNEL)

    return message_obj


@webhooks.get("/<int:application_id>/int___<string:token>/messages/<string:message>")
async def get_interaction_message(message: Message = DepInteractionW):
    return await message.ds_json()


@webhooks.delete("/<int:application_id>/int___<string:token>/messages/<string:message>")
async def delete_interaction_message(message: Message = DepInteractionW):
    await message.delete()
    return "", 204


@webhooks.patch("/<int:application_id>/int___<string:token>/messages/<string:message>", body_cls=MessageUpdate)
async def edit_interaction_message(data: MessageUpdate, message: Message = DepInteractionW):
    await message.update(**data.to_json(), edit_timestamp=datetime.now())
    await getGw().dispatch(MessageUpdateEvent(await message.ds_json()), channel=message.channel,
                           permissions=GuildPermissions.VIEW_CHANNEL)
    return await message.ds_json()
