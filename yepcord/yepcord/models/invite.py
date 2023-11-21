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
from typing import Optional

from tortoise import fields

from ..ctx import getCore
from ..enums import ChannelType
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake
from ..utils import b64encode, int_size
import yepcord.yepcord.models as models


class Invite(Model):
    id: int = SnowflakeField(pk=True)
    type: int = fields.IntField(default=1)
    channel: models.Channel = fields.ForeignKeyField("models.Channel")
    inviter: models.User = fields.ForeignKeyField("models.User")
    max_age: int = fields.BigIntField(default=86400)
    max_uses: int = fields.BigIntField(default=0)
    uses: int = fields.BigIntField(default=0)
    vanity_code: Optional[str] = fields.CharField(max_length=64, null=True, default=None)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    @property
    def code(self) -> str:
        return b64encode(self.id.to_bytes(int_size(self.id), 'big'))

    async def ds_json(self, with_counts: bool=False) -> dict:
        userdata = await self.inviter.data
        expires_at = None
        if self.max_age > 0:
            expires_timestamp = int(Snowflake.toTimestamp(self.id) / 1000) + self.max_age
            expires_at = datetime.utcfromtimestamp(expires_timestamp).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        data = {
            "code": self.code,
            "inviter": userdata.ds_json,
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "expires_at": expires_at,
            "type": self.type,
            "channel": {
                "id": str(self.channel.id),
                "type": self.channel.type
            },
            "max_age": self.max_age,
        }

        if with_counts:
            related_users = await getCore().getRelatedUsersToChannel(self.channel.id, ids=False)
            data["approximate_member_count"] = len(related_users)
            if self.channel.type == ChannelType.GROUP_DM:
                data["channel"]["recipients"] = [
                    {"username": (await rel_user.data).username}
                    for rel_user in related_users
                ]

        if self.channel.type == ChannelType.GROUP_DM:
            data["channel"].update({"name": self.channel.name, "icon": self.channel.icon})
        elif self.channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
            data["channel"]["name"] = self.channel.name

        if self.channel.guild:
            guild = self.channel.guild
            data["guild"] = {
                "id": str(guild.id),
                "banner": guild.banner,
                "description": guild.description,
                "features": [
                    "ANIMATED_ICON",
                    "BANNER",
                    "INVITE_SPLASH",
                    "VANITY_URL",
                    "PREMIUM_TIER_3_OVERRIDE",
                    "ROLE_ICONS",
                    *guild.features
                ],
                "icon": guild.icon,
                "name": guild.name,
                "nsfw": guild.nsfw,
                "nsfw_level": guild.nsfw_level,
                "premium_subscription_count": 30,
                "splash": guild.splash,
                "vanity_url_code": guild.vanity_url_code,
                "verification_level": guild.verification_level
            }
            data["max_uses"] = self.max_uses
            data["uses"] = self.uses
            data["temporary"] = False
            if self.vanity_code:
                data["code"] = self.vanity_code

        return data
