from typing import Optional

from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.webhooks import WebhookUpdate, WebhookMessageCreate, WebhookMessageCreateQuery
from ..utils import usingDB, getUser, multipleDecorators, allowWithoutUser, processMessageData
from ...yepcord.classes.message import Message
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore, getCDNStorage
from ...yepcord.enums import GuildPermissions, MessageType
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, validImage, getImage

# Base path is /api/vX/webhooks
webhooks = Blueprint('webhooks', __name__)


@webhooks.delete("/<int:webhook>")
@webhooks.delete("/<int:webhook>/<string:token>")
@multipleDecorators(usingDB, allowWithoutUser, getUser)
async def api_webhooks_webhook_delete(user: Optional[User], webhook: int, token: Optional[str]=None):
    if webhook := await getCore().getWebhook(webhook):
        if webhook.token != token:
            guild = await getCore().getGuild(webhook.guild_id)
            if not (member := await getCore().getGuildMember(guild, user.id)):
                raise InvalidDataErr(403, Errors.make(50013))
            await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
        await getCore().deleteWebhook(webhook)
        await getCore().sendWebhooksUpdateEvent(webhook)

    return "", 204


@webhooks.patch("/<int:webhook>")
@webhooks.patch("/<int:webhook>/<string:token>")
@multipleDecorators(validate_request(WebhookUpdate), usingDB, allowWithoutUser, getUser)
async def api_webhooks_webhook_patch(data: WebhookUpdate, user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        guild = await getCore().getGuild(webhook.guild_id)
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    if user.id == 0:
        if data.channel_id: data.channel_id = None
    if (img := data.avatar) or img is None:
        if img is not None:
            img = getImage(img)
            if h := await getCDNStorage().setAvatarFromBytesIO(webhook.id, img):
                img = h
        data.avatar = img

    new_webhook = webhook.copy(**data.dict(exclude_defaults=True))

    await getCore().updateWebhookDiff(webhook, new_webhook)
    await getCore().sendWebhooksUpdateEvent(new_webhook)

    return c_json(await new_webhook.json)


@webhooks.get("/<int:webhook>")
@webhooks.get("/<int:webhook>/<string:token>")
@multipleDecorators(usingDB, allowWithoutUser, getUser)
async def api_webhooks_webhook_get(user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        guild = await getCore().getGuild(webhook.guild_id)
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)

    return c_json(await webhook.json)


@webhooks.post("/<int:webhook>/<string:token>")
@multipleDecorators(validate_querystring(WebhookMessageCreateQuery), usingDB)
async def api_webhooks_webhook_post(query_args: WebhookMessageCreateQuery, webhook: int, token: str):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        raise InvalidDataErr(403, Errors.make(50013))
    if not (channel := await getCore().getChannel(webhook.channel_id)):
        raise InvalidDataErr(404, Errors.make(10003))

    message_id = Snowflake.makeId()
    data = await request.get_json()
    data = await processMessageData(message_id, data, webhook.channel_id)
    author = {
        "bot": True,
        "id": str(webhook.id),
        "username": data.get("username", None) or webhook.name,
        "avatar": data.get("avatar", None) or webhook.avatar,
        "discriminator": "0000"
    }
    data = WebhookMessageCreate(**data)

    message_type = MessageType.DEFAULT
    if data.message_reference:
        data.validate_reply(channel, await getCore().getMessage(channel, data.message_reference.message_id))
    if data.message_reference:
        message_type = MessageType.REPLY

    message = Message(id=message_id, channel_id=webhook.channel_id, author=0, guild_id=webhook.guild_id,
                      webhook_author=author, type=message_type, **data.to_json())
    message = await getCore().sendMessage(message)

    if query_args.wait:
        return c_json(await message.json)
    else:
        return "", 204
