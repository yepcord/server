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

from datetime import datetime
from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..classes.other import MFA
from ..ctx import getCore
from ..snowflake import Snowflake


class UserUtils:
    @staticmethod
    async def get(user_id: int, allow_deleted: bool = True) -> Optional[User]:
        kwargs = {} if allow_deleted else {"deleted": False}
        return await User.get_or_none(id=user_id, **kwargs)

    @staticmethod
    async def getByUsername(username: str, discriminator: int) -> Optional[User]:
        data = await models.UserData.get_or_none(username=username, discriminator=discriminator).select_related("user")
        if data is not None:
            return data.user


class User(Model):
    y = UserUtils

    id: int = SnowflakeField(pk=True)
    email: str = fields.CharField(max_length=254, unique=True)
    password: str = fields.CharField(max_length=128)
    verified: bool = fields.BooleanField(default=False)
    deleted: bool = fields.BooleanField(default=False)
    is_bot: bool = fields.BooleanField(default=False)

    @property
    async def settings(self) -> models.UserSettings:
        return await models.UserSettings.get(id=self.id)

    @property
    async def userdata(self) -> models.UserData:
        return await models.UserData.get(id=self.id).select_related("user")

    @property
    async def data(self) -> models.UserData:
        return await self.userdata

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    @property
    async def mfa(self) -> Optional[MFA]:
        settings = await self.settings
        mfa = MFA(settings.mfa, self.id)
        if mfa.valid:
            return mfa

    async def profile_json(self, other_user: User, with_mutual_guilds: bool = False, mutual_friends_count: bool = False,
                           guild_id: int = None) -> dict:
        data = await self.data
        premium_since = self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = {
            "user": {
                "id": str(self.id),
                "username": data.username,
                "avatar": data.avatar,
                "avatar_decoration": data.avatar_decoration,
                "discriminator": data.s_discriminator,
                "public_flags": data.public_flags,
                "flags": data.flags,
                "banner": data.banner,
                "banner_color": data.banner_color,
                "accent_color": data.accent_color,
                "bio": data.bio
            },
            "connected_accounts": [],  # TODO
            "premium_since": premium_since,
            "premium_guild_since": premium_since,
            "user_profile": {
                "bio": data.bio,
                "accent_color": data.accent_color
            }
        }
        if guild_id and (guild := await getCore().getGuild(guild_id)):
            if member := await getCore().getGuildMember(guild, self.id):
                data["guild_member_profile"] = {"guild_id": str(guild_id)}
                data["guild_member"] = await member.ds_json()
        if mutual_friends_count:
            data["mutual_friends_count"] = 0  # TODO: add mutual friends count
        if with_mutual_guilds:
            data["mutual_guilds"] = await getCore().getMutualGuildsJ(self, other_user)
        if self.is_bot:
            data["user"]["bot"] = True

        return data
