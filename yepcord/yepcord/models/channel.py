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

from __future__ import annotations

from typing import Optional

from tortoise import fields
from tortoise.expressions import Q
from tortoise.fields import SET_NULL

from ..ctx import getCore
from ..enums import ChannelType
import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class Channel(Model):
    id: int = SnowflakeField(pk=True)
    type: int = fields.IntField()
    guild: Optional[models.Guild] = fields.ForeignKeyField("models.Guild", null=True, default=None)
    position: Optional[int] = fields.IntField(null=True, default=None)
    name: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    topic: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    nsfw: Optional[bool] = fields.BooleanField(null=True, default=None)
    bitrate: Optional[int] = fields.IntField(null=True, default=None)
    user_limit: Optional[int] = fields.IntField(null=True, default=None)
    rate_limit: Optional[int] = fields.IntField(null=True, default=None)
    recipients = fields.ManyToManyField("models.User", null=True, default=None, related_name="recipients")
    icon: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    owner: Optional[models.User] = fields.ForeignKeyField("models.User", null=True, default=None, related_name="owner")
    application_id: Optional[int] = fields.BigIntField(null=True, default=None)
    parent: Optional[Channel] = fields.ForeignKeyField("models.Channel", on_delete=SET_NULL, null=True,
                                                       default=None)
    rtc_region: Optional[str] = fields.CharField(max_length=64, null=True, default=None)
    video_quality_mode: Optional[int] = fields.IntField(null=True, default=None)
    default_auto_archive: Optional[int] = fields.IntField(null=True, default=None)
    flags: Optional[int] = fields.IntField(null=True, default=0)

    last_message_id: int = None

    async def ds_json(self, user_id: int=None, with_ids: bool=True) -> dict:
        if self.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            self.last_message_id = await getCore().getLastMessageId(self)
        if self.last_message_id is None:
            await getCore().setLastMessageIdForChannel(self)
        last_message_id = str(self.last_message_id) if self.last_message_id is not None else None
        recipients = []
        if self.type in (ChannelType.DM, ChannelType.GROUP_DM):
            recipients = await (self.recipients.all() if not user_id else self.recipients.filter(~Q(id=user_id)).all())
            if with_ids:
                recipients = [str(recipient.id) for recipient in recipients]
            else:
                _recipients = recipients
                recipients = []
                for recipient in _recipients:
                    userdata = await recipient.data
                    recipients.append(userdata.ds_json)

        base_data = {
            "id": str(self.id),
            "type": self.type,
        }

        if self.type == ChannelType.DM:
            return base_data | {
                "recipient_ids" if with_ids else "recipients": recipients,
                "last_message_id": last_message_id,
            }
        elif self.type == ChannelType.GROUP_DM:
            return base_data | {
                "recipient_ids" if with_ids else "recipients": recipients,
                "last_message_id": last_message_id,
                "owner_id": str(self.owner.id),
                "name": self.name,
                "icon": self.icon
            }
        elif self.type == ChannelType.GUILD_CATEGORY:
            return base_data | {
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent else None,
                "name": self.name,
                "flags": self.flags,
                "guild_id": str(self.guild.id)
            }
        elif self.type == ChannelType.GUILD_TEXT:
            return base_data | {
                "topic": self.topic,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "guild_id": str(self.guild.id),
                "nsfw": self.nsfw
            }
        elif self.type == ChannelType.GUILD_VOICE:
            return base_data | {
                "user_limit": self.user_limit,
                "rtc_region": self.rtc_region,
                "rate_limit_per_user": self.rate_limit,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "bitrate": self.bitrate,
                "guild_id": str(self.guild.id)
            }
        elif self.type == ChannelType.GUILD_NEWS:
            return base_data | {
                "topic": self.topic,
                "position": self.position,
                "permission_overwrites": [
                    overwrite.ds_json() for overwrite in await getCore().getPermissionOverwrites(self)
                ],
                "parent_id": str(self.parent.id) if self.parent else None,
                "name": self.name,
                "last_message_id": last_message_id,
                "flags": self.flags,
                "guild_id": str(self.guild.id),
                "nsfw": self.nsfw
            }
        elif self.type == ChannelType.GUILD_PUBLIC_THREAD:
            message_count = await getCore().getChannelMessagesCount(self)
            data = base_data | {
                "guild_id": str(self.guild.id),
                "parent_id": str(self.parent.id) if self.parent else None,
                "owner_id": str(self.owner.id),
                "name": self.name,
                "last_message_id": last_message_id,
                "thread_metadata": (await getCore().getThreadMetadata(self)).ds_json(),
                "message_count": message_count,
                "member_count": await getCore().getThreadMembersCount(self),
                "rate_limit_per_user": self.rate_limit,
                "flags": self.flags,
                "total_message_sent": message_count,
                "member_ids_preview": [str(member.user.id) for member in await getCore().getThreadMembers(self, 10)]
            }
            if user_id and (member := await getCore().getThreadMember(self, user_id)) is not None:
                data["member"] = {
                    "muted": False,
                    "mute_config": None,
                    "join_timestamp": member.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
                    "flags": 1
                }

            return data

    async def messages(self, limit: int=50, before: int=0, after: int=0) -> list[models.Message]:
        return await getCore().getChannelMessages(self, limit, before, after)

    async def other_user(self, current_user: models.User) -> Optional[models.User]:
        if self.type != ChannelType.DM:
            return
        return await self.recipients.filter(~Q(id=current_user.id)).get_or_none()
