# All 'Channel' classes (ChannelId, Channel, etc.)
from dataclasses import dataclass
from typing import Optional

from schema import Or, Use

from server.ctx import getCore
from server.model import model, field, Model
from ..discord_converters.channel import discord_Channel
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
    type: int
    guild_id: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    position: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    permission_overwrites: Optional[list] = field(validation=Or(list, NoneType), default=None, nullable=True, db_name="j_permission_overwrites")
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

    json = property(discord_Channel)