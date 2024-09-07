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
from __future__ import annotations

from time import time
from typing import Optional, Union

from tortoise import fields
from tortoise.transactions import atomic

from ..ctx import getCore
import yepcord.yepcord.models as models
from ..enums import Locales, ChannelType
from ._utils import SnowflakeField, Model, ChoicesValidator
from ..snowflake import Snowflake


class GuildUtils:
    @staticmethod
    @atomic()
    async def create(owner: models.User, name: str) -> models.Guild:
        guild = await Guild.create(id=Snowflake.makeId(), owner=owner, name=name)
        await models.Role.create(id=guild.id, guild=guild, name="@everyone")

        text_category = await models.Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Text Channels", position=0,
            flags=0, rate_limit=0
        )
        voice_category = await models.Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Voice Channels", position=0,
            flags=0, rate_limit=0
        )
        system_channel = await models.Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_TEXT, guild=guild, name="general", position=0, flags=0,
            parent=text_category, rate_limit=0
        )
        await models.Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_VOICE, guild=guild, name="General", position=0, flags=0,
            parent=voice_category, bitrate=64000, user_limit=0, rate_limit=0
        )
        guild.system_channel = system_channel.id
        await guild.save(update_fields=["system_channel"])

        await models.GuildMember.create(id=Snowflake.makeId(), user=owner, guild=guild)

        return guild

    @staticmethod
    @atomic()
    async def create_from_template(
            owner: models.User, template: models.GuildTemplate, name: Optional[str]
    ) -> models.Guild:
        serialized = template.serialized_guild
        name = serialized["name"] = name or serialized["name"]
        guild = await Guild.create(id=Snowflake.makeId(), owner=owner, name=name)

        replaced_ids: dict[Union[int, None], Union[int, None]] = {None: None, 0: guild.id}
        channels = {}
        roles = {}

        for role in serialized["roles"]:
            if role["id"] not in replaced_ids:
                replaced_ids[role["id"]] = Snowflake.makeId()
            role["id"] = replaced_ids[role["id"]]
            roles[role["id"]] = await models.Role.create(guild=guild, **role)

        for channel in serialized["channels"]:
            if channel["id"] not in replaced_ids:
                replaced_ids[channel["id"]] = Snowflake.makeId()
            channel["id"] = channel_id = replaced_ids[channel["id"]]
            channel["parent"] = channels.get(replaced_ids.get(channel["parent_id"], None), None)
            channel["rate_limit"] = channel["rate_limit_per_user"]
            channel["default_auto_archive"] = channel["default_auto_archive_duration"]

            del channel["parent_id"]
            del channel["rate_limit_per_user"]
            del channel["default_auto_archive_duration"]

            del channel["available_tags"]
            del channel["template"]
            del channel["default_reaction_emoji"]
            del channel["default_thread_rate_limit_per_user"]
            del channel["default_sort_order"]
            del channel["default_forum_layout"]

            permission_overwrites = channel["permission_overwrites"]
            del channel["permission_overwrites"]

            channels[channel_id] = await models.Channel.create(guild=guild, **channel)
            for overwrite in permission_overwrites:
                overwrite["target_role"] = roles[replaced_ids[overwrite["id"]]]
                overwrite["channel"] = channels[channel_id]
                del overwrite["id"]
                await models.PermissionOverwrite.create(**overwrite)

        serialized["afk_channel"] = replaced_ids.get(serialized["afk_channel_id"], None)
        serialized["system_channel"] = replaced_ids.get(serialized["system_channel_id"], None)
        del serialized["afk_channel_id"]
        del serialized["system_channel_id"]

        del serialized["roles"]
        del serialized["channels"]

        await guild.update(**serialized)
        await models.GuildMember.create(id=Snowflake.makeId(), user=owner, guild=guild)

        return guild


class Guild(Model):
    Y = GuildUtils

    id: int = SnowflakeField(pk=True)
    owner: models.User = fields.ForeignKeyField("models.User")
    name: str = fields.CharField(max_length=64)
    features: list = fields.JSONField(default=[])
    icon: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    description: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    splash: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    discovery_splash: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    banner: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    region: str = fields.CharField(max_length=64, default="deprecated")
    afk_channel: Optional[int] = fields.BigIntField(null=True, default=None)
    system_channel: Optional[int] = fields.BigIntField(null=True, default=None)
    afk_timeout: int = fields.IntField(default=300)
    verification_level: int = fields.IntField(default=0)
    default_message_notifications: int = fields.IntField(default=0)
    mfa_level: int = fields.IntField(default=0)
    explicit_content_filter: int = fields.IntField(default=0)
    system_channel_flags: int = fields.BigIntField(default=0)
    max_members: int = fields.IntField(default=100)
    vanity_url_code: Optional[str] = fields.CharField(max_length=64, null=True, default=None)
    preferred_locale: str = fields.CharField(max_length=8, default="en-US",
                                             validators=[ChoicesValidator(Locales.values_set())])
    premium_progress_bar_enabled: bool = fields.BooleanField(default=False)
    nsfw: bool = fields.BooleanField(default=False)
    nsfw_level: int = fields.IntField(default=0)

    async def ds_json(
            self, user_id: int, for_gateway: bool = False, with_member: Optional[models.GuildMember] = None,
            with_channels: bool = False
    ) -> dict:
        data = {
            "id": str(self.id),
            "version": int(time() * 1000),  # What is this?
            "stickers": [
                await sticker.ds_json()
                for sticker in await self.get_stickers()
            ],
            "stage_instances": [],
            "roles": [role.ds_json() for role in await self.get_roles()],
            "properties": {
                "afk_timeout": self.afk_timeout,
                "splash": self.splash,
                "owner_id": str(self.owner.id),
                "description": self.description,
                "id": str(self.id),
                "discovery_splash": self.discovery_splash,
                "icon": self.icon,
                "incidents_data": None,  # ???
                "explicit_content_filter": self.explicit_content_filter,
                "system_channel_id": str(self.system_channel) if self.system_channel is not None else None,
                "default_message_notifications": self.default_message_notifications,
                "premium_progress_bar_enabled": bool(self.premium_progress_bar_enabled),
                "public_updates_channel_id": None,  # ???
                "max_members": self.max_members,
                "nsfw": bool(self.nsfw),
                "application_id": None,
                "max_video_channel_users": 0,
                "verification_level": self.verification_level,
                "rules_channel_id": None,
                "afk_channel_id": str(self.afk_channel) if self.afk_channel is not None else None,
                "latest_onboarding_question_id": None,  # ???
                "mfa_level": self.mfa_level,
                "nsfw_level": self.nsfw_level,
                "safety_alerts_channel_id": None,  # ???
                "premium_tier": 3,
                "vanity_url_code": self.vanity_url_code,
                "features": [
                    "ANIMATED_ICON",
                    "BANNER",
                    "INVITE_SPLASH",
                    "VANITY_URL",
                    "PREMIUM_TIER_3_OVERRIDE",
                    "ROLE_ICONS",
                    *self.features
                ],
                "max_stage_video_channel_users": 0,
                "system_channel_flags": self.system_channel_flags,
                "name": self.name,
                "hub_type": None,  # ???
                "preferred_locale": self.preferred_locale,
                "home_header": None,  # ???
                "banner": self.banner,
                "region": self.region,
                "widget_enabled": False,
                "widget_channel_id": None,
            },
            "premium_subscription_count": 30,
            "member_count": await self.get_member_count(),
            "lazy": True,
            "large": False,
            "guild_scheduled_events": [
                await event.ds_json()
                for event in await self.get_events()
            ],
            "emojis": [
                await emoji.ds_json(False)
                for emoji in await self.get_emojis()
            ],
            "data_mode": "full",
            "application_command_counts": [],
        }

        if not for_gateway:
            props = data["properties"]
            del data["properties"]
            data.update(props)

        if for_gateway or user_id:
            member = await self.get_member(user_id)
            data["joined_at"] = member.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
            data["threads"] = [
                thread.ds_json()
                for thread in await models.ThreadMember.filter(guild=self, user__id=user_id).select_related(
                    "channel", "user", "guild"
                )
            ]
        if for_gateway or with_channels:
            data["channels"] = [await channel.ds_json() for channel in await self.get_channels()]
        if with_member is not None:
            data["members"] = [await with_member.ds_json()]

        return data

    async def get_roles(self, exclude_default: bool = False) -> list[models.Role]:
        query = models.Role.filter(guild=self).select_related("guild")
        if exclude_default:
            query = query.exclude(id=self.id)
        return await query

    async def get_channels(self) -> list[models.Channel]:
        return await models.Channel.filter(guild=self) \
            .exclude(type__in=[ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD]) \
            .select_related("guild", "parent")

    async def get_emojis(self) -> list[models.Emoji]:
        return await models.Emoji.filter(guild=self).select_related("user")

    async def get_audit_logs(self, limit: int, before: Optional[int] = None) -> list[models.AuditLogEntry]:
        before = {} if before is None else {"id__lt": before}
        return await models.AuditLogEntry.filter(guild=self, **before).select_related("guild", "user").limit(limit)

    async def get_stickers(self) -> list[models.Sticker]:
        return await models.Sticker.filter(guild=self).select_related("guild", "user")

    async def get_events(self) -> list[models.GuildEvent]:
        return await models.GuildEvent.filter(guild=self).select_related("channel", "guild", "creator")

    async def get_member(self, user_id: int) -> Optional[models.GuildMember]:
        return await models.GuildMember.get_or_none(
            guild=self, user__id=user_id,
        ).select_related("user", "guild", "guild__owner")

    async def get_template(self) -> Optional[models.GuildTemplate]:
        return await models.GuildTemplate.get_or_none(guild=self).select_related("creator", "guild")

    async def get_role(self, role_id: int) -> Optional[models.Role]:
        return await models.Role.get_or_none(id=role_id, guild=self).select_related("guild")

    async def get_sticker(self, sticker_id: int) -> Optional[models.Sticker]:
        return await models.Sticker.get_or_none(id=sticker_id, guild=self).select_related("guild", "user")

    async def get_scheduled_event(self, event_id: int) -> Optional[models.GuildEvent]:
        return await models.GuildEvent.get_or_none(
            id=event_id, guild=self
        ).select_related("channel", "guild", "creator")

    async def get_member_count(self) -> int:
        return await models.GuildMember.filter(guild=self).count()

    async def bulk_delete_messages_from_banned(
            self, user_id: int, after_message_id: int
    ) -> dict[models.Channel, list[int]]:
        messages = await models.Message.filter(
            guild=self, author__id=user_id, id__gt=after_message_id
        ).select_related("channel").limit(500)
        result = {}
        messages_ids = []
        for message in messages:
            if message.channel not in result:
                result[message.channel] = []
            result[message.channel].append(message.id)
            messages_ids.append(message.id)

        await models.Message.filter(id__in=messages_ids).delete()

        return result

    async def set_template_dirty(self) -> None:
        await models.GuildTemplate.filter(guild=self).update(is_dirty=True)
