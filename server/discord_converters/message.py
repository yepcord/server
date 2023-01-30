from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from server.classes.user import UserId
from server.config import Config
from server.ctx import getCore, Ctx
from server.enums import MessageType
from server.utils import ping_regex, sf_ts

if TYPE_CHECKING:
    from server.classes.message import Message

async def discord_Message(message: Message) -> dict:
    data = message.toJSON(for_db=False, discord_types=True, with_private=False)
    data["author"] = await (await getCore().getUserData(UserId(message.author))).json
    data["mention_everyone"] = ("@everyone" in message.content or "@here" in message.content) if message.content else None
    data["tts"] = False
    timestamp = datetime.utcfromtimestamp(int(sf_ts(message.id) / 1000))
    data["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
    if message.edit_timestamp:
        edit_timestamp = datetime.utcfromtimestamp(int(sf_ts(message.edit_timestamp) / 1000))
        data["edit_timestamp"] = edit_timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
    data["mentions"] = []
    data["mention_roles"] = []
    data["attachments"] = []
    if message.content:
        for ping in ping_regex.findall(message.content):
            if ping.startswith("!"):
                ping = ping[1:]
            if ping.startswith("&"):
                data["mention_roles"].append(ping[1:])
            if member := await getCore().getUserByChannelId(message.channel_id, int(ping)):
                mdata = await member.data
                data["mentions"].append(await mdata.json)
    if message.type in (MessageType.RECIPIENT_ADD, MessageType.RECIPIENT_REMOVE):
        if user := message.extra_data.get("user"):
            user = await getCore().getUserData(UserId(user))
            data["mentions"].append(await user.json)
    for att in message.attachments:
        att = await getCore().getAttachment(att)
        data["attachments"].append({
            "filename": att.filename,
            "id": str(att.id),
            "size": att.size,
            "url": f"https://{Config('CDN_HOST')}/attachments/{message.channel_id}/{att.id}/{att.filename}"
        })
        if att.get("content_type"):
            data["attachments"][-1]["content_type"] = att.get("content_type")
        if att.get("metadata"):
            data["attachments"][-1].update(att.metadata)
    if message.message_reference:
        data["message_reference"] = {"message_id": str(message.message_reference), "channel_id": str(message.channel_id)}
    if message.nonce is not None:
        data["nonce"] = message.nonce
    if not Ctx.get("search", False):
        if reactions := await getCore().getMessageReactions(message.id, Ctx.get("user_id", 0)):
            data["reactions"] = reactions
    return data