# All 'Channel' classes (ChannelId, Channel, etc.)
from dataclasses import dataclass
from typing import Optional

from schema import Or, Use

from .user import UserId
from ..ctx import getCore, Ctx
from ..enums import ChannelType
from ..model import model, field, Model
from ..utils import NoneType


class _Channel:
    id: int

    def __eq__(self, other):
        return isinstance(other, _Channel) and self.id == other.id

class ChannelId(_Channel):
    def __init__(self, cid: int):
        self.id = cid

@model
@dataclass
class Channel(_Channel, Model):
    id: int = field(id_field=True)
    type: int = field()
    guild_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    position: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    name: Optional[str] = None
    topic: Optional[str] = None
    nsfw: Optional[bool] = None
    bitrate: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    user_limit: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    rate_limit: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    recipients: Optional[list] = field(validation=Or([int], NoneType), default=None, nullable=True, db_name="j_recipients")
    icon: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    owner_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    application_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    parent_id: Optional[int] = field(validation=Or(Use(int), NoneType), default=None, nullable=True)
    rtc_region: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    video_quality_mode: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    thread_metadata: Optional[dict] = field(validation=Or(dict, NoneType), default=None, nullable=True, db_name="j_thread_metadata")
    default_auto_archive: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    flags: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    last_message_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True, excluded=True)

    async def messages(self, limit: int=50, before: int=None, after: int=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await getCore().getChannelMessages(self, limit, before, after)

    @property
    async def json(self) -> dict:
        """
        Returns dict object for discord.
        Set Ctx["user_id"] to True when Channel.type is ChannelType.DM or ChannelType.GROUP_DM to remove current user
          id from result.
        Set Ctx["user_id"] to False when Channel.type is ChannelType.DM or ChannelType.GROUP_DM to return users ids list
          in recipients field instead of users data.
        :return:
        """
        last_message_id = str(self.last_message_id) if self.last_message_id is not None else self.last_message_id
        if self.type in (ChannelType.DM, ChannelType.GROUP_DM):
            recipients = self.recipients.copy()
            if user_id := Ctx.get("user_id"):
                recipients.remove(user_id)
            with_ids = Ctx.get("with_ids", True)
            if not with_ids:
                _recipients = recipients
                recipients = []
                for u in _recipients:
                    userdata = await getCore().getUserData(UserId(u))
                    recipients.append(await userdata.json)
            else:
                recipients = [str(recipient) for recipient in recipients]
            if self.type == ChannelType.DM:
                return {
                    "type": self.type,
                    "recipient_ids" if with_ids else "recipients": recipients,
                    "last_message_id": last_message_id,
                    "id": str(self.id)
                }
            elif self.type == ChannelType.GROUP_DM:
                return {
                    "type": self.type,
                    "recipient_ids" if with_ids else "recipients": recipients,
                    "last_message_id": last_message_id,
                    "id": str(self.id),
                    "owner_id": str(self.owner_id),
                    "name": self.name,
                    "icon": self.icon
                }
        if self.type == ChannelType.GUILD_CATEGORY:
            return {
                "type": self.type,
                "position": self.position,
                "permission_overwrites": [
                    await overwrite.json for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent_id) if self.parent_id is not None else self.parent_id,
                "name": self.name,
                "id": str(self.id),
                "flags": self.flags,
                "guild_id": str(self.guild_id)
            }
        elif self.type == ChannelType.GUILD_TEXT:
            return {
                "type": self.type,
                "topic": self.topic,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    await overwrite.json for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent_id) if self.parent_id is not None else self.parent_id,
                "name": self.name,
                "last_message_id": last_message_id,
                "id": str(self.id),
                "flags": self.flags,
                "guild_id": str(self.guild_id),
                "nsfw": self.nsfw
            }
        elif self.type == ChannelType.GUILD_VOICE:
            return {
                "user_limit": self.user_limit,
                "type": self.type,
                "rtc_region": self.rtc_region,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    await overwrite.json for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent_id) if self.parent_id is not None else self.parent_id,
                "name": self.name,
                "last_message_id": last_message_id,
                "id": str(self.id),
                "flags": self.flags,
                "bitrate": self.bitrate,
                "guild_id": str(self.guild_id)
            }

@model
@dataclass
class PermissionOverwrite(Model):
    channel_id: int
    target_id: int
    type: int
    allow: int
    deny: int

    @property
    async def json(self) -> dict:
        data = {
            "type": self.type,
            "id": str(self.target_id),
            "deny": str(self.deny),
            "allow": str(self.allow)
        }
        return data