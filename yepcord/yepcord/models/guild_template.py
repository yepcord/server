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
from typing import Optional, Union

from tortoise import fields

from ..ctx import getCore
from ..enums import ChannelType
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake
from ..utils import b64encode, int_size, NoneType

import yepcord.yepcord.models as models


class GuildTemplate(Model):
    id: int = SnowflakeField(pk=True)
    name: str = fields.CharField(max_length=64)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    description: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    usage_count: int = fields.BigIntField(default=0)
    creator: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)
    serialized_guild: dict = fields.JSONField(default={})
    updated_at: Optional[datetime] = fields.DatetimeField(null=True, default=None)
    is_dirty: bool = fields.BooleanField(default=False)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_size(self.id), 'big'))

    async def ds_json(self) -> dict:
        creator_data = await self.creator.data if self.creator is not None else None
        updated_at = self.updated_at
        if updated_at is None:
            updated_at = self.created_at
        data = {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "usage_count": self.usage_count,
            "creator_id": str(self.creator.id) if self.creator is not None else None,
            "creator": creator_data.ds_json if creator_data is not None else None,
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "source_guild_id": str(self.guild.id),
            "serialized_source_guild": self.serialized_guild,
            "is_dirty": self.is_dirty
        }
        return data

    @staticmethod
    async def serialize_guild(guild: models.Guild) -> dict:
        replaced_ids: dict[Union[int, NoneType], Union[int, NoneType]] = {None: None}
        last_replaced_id = 0
        serialized_roles = []
        serialized_channels = []

        # Serialize roles
        roles = await getCore().getRoles(guild)
        roles.sort(key=lambda r: r.id)
        for role in roles:
            if role.managed:
                continue
            replaced_ids[role.id] = last_replaced_id
            role.id = last_replaced_id
            last_replaced_id += 1
            serialized_roles.append({
                "id": role.id,
                "name": role.name,
                "color": role.color,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": str(role.permissions),
                "icon": None,
                "unicode_emoji": role.unicode_emoji
            })

        # Serialize channels
        channels = await getCore().getGuildChannels(guild)
        channels.sort(key=lambda ch: (int(ch.type == ChannelType.GUILD_CATEGORY), ch.id), reverse=True)
        for channel in channels:
            serialized_permission_overwrites = []
            for overwrite in await getCore().getPermissionOverwrites(channel):
                if overwrite.type == 0:  # Overwrite for role
                    role_id = replaced_ids[overwrite.target_id]
                    if role_id is None:
                        continue
                    overwrite = overwrite.ds_json()
                    overwrite["id"] = role_id
                    serialized_permission_overwrites.append(overwrite)
            replaced_ids[channel.id] = last_replaced_id
            channel.id = last_replaced_id
            last_replaced_id += 1

            serialized_channels.append({
                "id": channel.id,
                "type": channel.type,
                "name": channel.name,
                "position": channel.position,
                "topic": channel.topic,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "nsfw": channel.nsfw,
                "rate_limit_per_user": channel.rate_limit,
                "parent_id": replaced_ids.get(channel.parent.id if channel.parent is not None else None),
                "default_auto_archive_duration": channel.default_auto_archive,
                "permission_overwrites": serialized_permission_overwrites,
                "available_tags": None,  # ???
                "template": "",  # ???
                "default_reaction_emoji": None,  # ???
                "default_thread_rate_limit_per_user": None,  # ???
                "default_sort_order": None,  # ???
                "default_forum_layout": None  # ???
            })

        # Serialize guild
        data = {
            "name": guild.name,
            "description": guild.description,
            "region": guild.region,
            "verification_level": guild.verification_level,
            "default_message_notifications": guild.default_message_notifications,
            "explicit_content_filter": guild.explicit_content_filter,
            "preferred_locale": guild.preferred_locale,
            "afk_timeout": guild.afk_timeout,
            "roles": serialized_roles,
            "channels": serialized_channels,
            "afk_channel_id": replaced_ids.get(guild.afk_channel),
            "system_channel_id": replaced_ids.get(guild.system_channel),
            "system_channel_flags": guild.system_channel_flags
        }

        return data
