from typing import Optional

from quart import Blueprint, request

from ..utils import usingDB, getUser, multipleDecorators, allowWithoutUser, processMessageData
from ...yepcord.classes.message import Message
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore, getCDNStorage
from ...yepcord.enums import GuildPermissions
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
@multipleDecorators(usingDB, allowWithoutUser, getUser)
async def api_webhooks_webhook_patch(user: Optional[User], webhook: int, token: Optional[str]=None):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        guild = await getCore().getGuild(webhook.guild_id)
        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50013))
        await member.checkPermission(GuildPermissions.MANAGE_WEBHOOKS)
    data = await request.get_json()
    if user.id == 0:
        if "channel_id" in data: del data["channel_id"]
    data = {
        "name": str(data.get("name") or webhook.name),
        "channel_id": int(data.get("channel_id") or webhook.channel_id),
        "avatar": data.get("avatar")
    }
    if (img := data["avatar"]) or img is None:
        if img is not None:
            if (img := getImage(img)) and validImage(img):
                if h := await getCDNStorage().setAvatarFromBytesIO(webhook.id, img):
                    img = h
        data["avatar"] = img
    else:
        del data["avatar"]

    new_webhook = webhook.copy(**data)

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
@multipleDecorators(usingDB)
async def api_webhooks_webhook_post(webhook: int, token: str):
    if not (webhook := await getCore().getWebhook(webhook)):
        raise InvalidDataErr(404, Errors.make(10015))
    if webhook.token != token:
        raise InvalidDataErr(403, Errors.make(50013))

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
    if "username" in data: del data["username"]
    if "avatar" in data: del data["avatar"]
    message = Message(id=message_id, channel_id=webhook.channel_id, author=0, guild_id=webhook.guild_id,
                      webhook_author=author, **data)
    await message.check()
    message = await getCore().sendMessage(message)

    if request.args.get("wait") == "true":
        return c_json(await message.json)
    else:
        return "", 204
