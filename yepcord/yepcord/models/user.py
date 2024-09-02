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

from datetime import datetime
from random import randint, choice
from typing import Optional

from bcrypt import checkpw, hashpw, gensalt
from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..classes.other import MFA
from ..config import Config
from ..ctx import getCore
from ..errors import InvalidDataErr, Errors
from ..snowflake import Snowflake
from ..utils import int_size


async def _get_free_discriminator(login: str) -> Optional[int]:
    for _ in range(5):
        discriminator = randint(1, 9999)
        if not await User.y.getByUsername(login, discriminator):
            return discriminator


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

    @staticmethod
    def prepare_password(password: str, user_id: int) -> bytes:
        return password.encode("utf8") + user_id.to_bytes(int_size(user_id), "big").replace(b"\x00", b'')


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
        connections = await models.ConnectedAccount.filter(user=self, verified=True, visibility=1)
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
            "connected_accounts": [conn.ds_json() for conn in connections],
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

    async def get_another_user(self, user_id: int) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if (user := await User.y.get(user_id, False)) is None:  # TODO: add test for nonexistent user
            raise InvalidDataErr(404, Errors.make(10013))
        return user

    def check_password(self, password: str) -> bool:
        return checkpw(self.y.prepare_password(password, self.id), self.password.encode("utf8"))

    def hash_new_password(self, password: str) -> str:
        password = self.y.prepare_password(password, self.id)
        return hashpw(password, gensalt(Config.BCRYPT_ROUNDS)).decode("utf8")

    async def change_password(self, new_password: str) -> None:
        self.password = self.hash_new_password(new_password)
        await self.save(update_fields=["password"])

    async def change_username(self, username: str) -> None:
        data = await self.data
        discriminator = data.discriminator
        if await User.y.getByUsername(username, discriminator):
            discriminator = await _get_free_discriminator(username)
            if discriminator is None:
                raise InvalidDataErr(400, Errors.make(50035, {"username": {
                    "code": "USERNAME_TOO_MANY_USERS",
                    "message": "This name is used by too many users. Please enter something else or try again."
                }}))
        data.username = username
        data.discriminator = discriminator
        await data.save(update_fields=["username", "discriminator"])

    async def change_discriminator(self, new_discriminator: int, username_changed: bool = False) -> bool:
        data = await self.data
        username = data.username
        if await self.y.getByUsername(username, new_discriminator):
            if username_changed:
                return False
            raise InvalidDataErr(400, Errors.make(50035, {"username": {
                "code": "USERNAME_TOO_MANY_USERS",
                "message": "This discriminator already used by someone. Please enter something else."
            }}))
        data.discriminator = new_discriminator
        await data.save(update_fields=["discriminator"])
        return True

    async def create_backup_codes(self) -> list[str]:
        codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]

        await self.clear_backup_codes()
        await models.MfaCode.bulk_create([
            models.MfaCode(user=self, code=code) for code in codes
        ])

        return codes

    async def clear_backup_codes(self) -> None:
        await models.MfaCode.filter(user=self).delete()

    async def get_backup_codes(self) -> list[str]:
        return [code.code async for code in models.MfaCode.filter(user=self).limit(10)]

    async def use_backup_code(self, code: str) -> bool:
        if (code := await models.MfaCode.get_or_none(user=self, code=code, used=False)) is None:
            return False
        code.used = True
        await code.save(update_fields=["used"])
        return True
