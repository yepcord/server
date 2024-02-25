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

from time import time
from typing import Optional

from tortoise import fields

from ..ctx import getCore
import yepcord.yepcord.models as models
from ..enums import Locales
from ._utils import SnowflakeField, Model, ChoicesValidator


class Guild(Model):
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

    async def ds_json(self, user_id: int, for_gateway: bool=False, with_members: bool=False,
                      with_channels: bool=False) -> dict:
        data = {
            "id": str(self.id),
            "version": int(time() * 1000),  # What is this?
            "stickers": [await sticker.ds_json() for sticker in await getCore().getGuildStickers(self)],
            "stage_instances": [],
            "roles": [role.ds_json() for role in await getCore().getRoles(self)],
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
            "member_count": await getCore().getGuildMemberCount(self),
            "lazy": True,
            "large": False,
            "guild_scheduled_events": [await event.ds_json() for event in await getCore().getGuildEvents(self)],
            "emojis": [await emoji.ds_json(False) for emoji in await getCore().getEmojis(self.id)],
            "data_mode": "full",
            "application_command_counts": [],
        }

        if not for_gateway:
            props = data["properties"]
            del data["properties"]
            data.update(props)

        if for_gateway or user_id:
            member = await getCore().getGuildMember(self, user_id)
            data["joined_at"] = member.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
            data["threads"] = [thread.ds_json() for thread in await getCore().getGuildMemberThreads(self, user_id)]
        if for_gateway or with_channels:
            data["channels"] = [await channel.ds_json() for channel in await getCore().getGuildChannels(self)]
        if with_members:
            data["members"] = [await member.ds_json() for member in await getCore().getGuildMembers(self)]

        return data
