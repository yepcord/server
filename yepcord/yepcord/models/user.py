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
from os import urandom
from random import randint, choice
from time import time
from typing import Optional, cast

from bcrypt import checkpw, hashpw, gensalt
from tortoise import fields
from tortoise.expressions import Q, Subquery
from tortoise.functions import Count
from tortoise.transactions import atomic

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model
from ..utils.mfa import MFA
from ..utils.jwt import JWT
from ..utils.email_msg import EmailMsg
from ..config import Config
from ..enums import RelationshipType, MfaNonceType
from ..errors import InvalidDataErr, Errors, MfaRequiredErr, UnknownUser, InvalidKey
from ..snowflake import Snowflake
from ..utils import int_size, b64encode, b64decode, assert_


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

    @staticmethod
    def hash_password(password: str, user_id: int) -> str:
        password = UserUtils.prepare_password(password, user_id)
        return hashpw(password, gensalt(Config.BCRYPT_ROUNDS)).decode("utf8")

    # noinspection PyUnusedLocal
    @staticmethod
    @atomic()
    async def register(
            login: str, email: Optional[str], password: str, birth: str, locale: str = "en-US",
            invite: Optional[str] = None
    ) -> User:
        user_id = Snowflake.makeId()

        birth = datetime.strptime(birth, "%Y-%m-%d")

        email = email.lower()
        if await User.exists(email=email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))

        discriminator = await User.y.get_free_discriminator(login)
        if discriminator is None:
            raise InvalidDataErr(400, Errors.make(50035, {"login": {"code": "USERNAME_TOO_MANY_USERS",
                                                                    "message": "Too many users have this username, "
                                                                               "please try another."}}))

        user = await User.create(id=user_id, email=email, password=UserUtils.hash_password(password, user_id))
        await models.UserData.create(id=user_id, user=user, birth=birth, username=login, discriminator=discriminator)
        await models.UserSettings.create(id=user_id, user=user, locale=locale)

        await user.send_verification_email()
        return user

    @staticmethod
    async def login(email: str, password: str) -> models.Session:
        email = email.strip().lower()
        user = await User.get_or_none(email=email)
        if not user or not user.check_password(password):
            raise InvalidDataErr(400, Errors.make(50035, {
                "login": {"code": "INVALID_LOGIN", "message": "Invalid login or password."},
                "password": {"code": "INVALID_LOGIN", "message": "Invalid login or password."},
            }))
        mfa_key = await user.get_mfa_key()
        if not mfa_key:
            return await models.Session.Y.create(user)

        sid = urandom(12)
        sid_int = int.from_bytes(sid, "big")
        raise MfaRequiredErr(
            user.id,
            b64encode(sid),
            b64encode(JWT.encode({"u": user.id, "s": sid_int}, b64decode(Config.KEY), time() + 300)),
        )

    @staticmethod
    async def get_free_discriminator(login: str) -> Optional[int]:
        for _ in range(5):
            discriminator = randint(1, 9999)
            if not await User.y.getByUsername(login, discriminator):
                return discriminator


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
        mfa = MFA(await self.get_mfa_key(), self.id)
        return mfa if mfa.valid else None

    async def profile_json(
            self, other_user: User, with_mutual_guilds: bool = False, mutual_friends_count: bool = False,
            guild_id: int = None
    ) -> dict:
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
        if guild_id and (guild := await models.Guild.get_or_none(id=guild_id)):
            if member := await guild.get_member(self.id):
                data["guild_member_profile"] = {"guild_id": str(guild_id)}
                data["guild_member"] = await member.ds_json()
        if mutual_friends_count:
            data["mutual_friends_count"] = 0  # TODO: add mutual friends count
        if with_mutual_guilds:
            query = Q(user=self)
            if self != other_user:
                query &= Q(guild__id__in=Subquery(
                    models.GuildMember
                    .filter(user__id__in=[self.id, other_user.id])
                    .group_by("guild_id")
                    .annotate(user_count=Count("user__id", distinct=True))
                    .filter(user_count=2)
                    .values_list("guild_id", flat=True)
                ))

            data["mutual_guilds"] = [
                {"id": str(guild_id), "nick": nick}
                for nick, guild_id in await models.GuildMember.filter(query).values_list("nick", "guild_id")
            ]
        if self.is_bot:
            data["user"]["bot"] = True

        return data

    # noinspection PyMethodMayBeStatic
    async def get_another_user(self, user_id: int) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if (user := await User.y.get(user_id, False)) is None:  # TODO: add test for nonexistent user
            raise UnknownUser
        return user

    def check_password(self, password: str) -> bool:
        return checkpw(self.y.prepare_password(password, self.id), self.password.encode("utf8"))

    def hash_new_password(self, password: str) -> str:
        return self.y.hash_password(password, self.id)

    async def change_password(self, new_password: str) -> None:
        self.password = self.hash_new_password(new_password)
        await self.save(update_fields=["password"])

    async def change_username(self, username: str) -> None:
        data = await self.data
        discriminator = data.discriminator
        if await User.y.getByUsername(username, discriminator):
            discriminator = await self.y.get_free_discriminator(username)
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

    async def change_email(self, new_email: str) -> None:
        new_email = new_email.lower()
        if self.email == new_email:
            return
        if await User.exists(email=new_email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))
        self.email = new_email
        self.verified = False
        await self.save()

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
        return [code.code for code in await models.MfaCode.filter(user=self).limit(10)]

    async def use_backup_code(self, code: str) -> bool:
        if (code := await models.MfaCode.get_or_none(user=self, code=code, used=False)) is None:
            return False
        code.used = True
        await code.save(update_fields=["used"])
        return True

    async def y_delete(self) -> None:
        await self.update(deleted=True, email=f"deleted_{self.id}@yepcord.ml", password="")
        data = await self.data
        await data.update(discriminator=0, username=f"Deleted User {hex(self.id)[2:]}", avatar=None, public_flags=0,
                          avatar_decoration=None)
        await models.Session.filter(user=self).delete()
        await models.Relationship.filter(Q(from_user=self) | Q(to_user=self)).delete()
        await models.MfaCode.filter(user=self).delete()
        await models.GuildMember.filter(user=self).delete()
        await models.UserSettings.filter(user=self).delete()
        await models.FrecencySettings.filter(user=self).delete()
        await models.Invite.filter(inviter=self).delete()
        await models.ReadState.filter(user=self).delete()

    async def get_guilds(self) -> list[models.Guild]:
        return [
            member.guild for member in
            await models.GuildMember.filter(user=self).select_related("guild", "guild__owner")
        ]

    async def get_private_channels(self) -> list[models.Channel]:
        return [
            channel
            for channel in await models.Channel.filter(recipients__id=self.id).select_related("owner")
            if not await channel.dm_is_hidden(self)
        ]

    async def get_relationships(self) -> list[models.Relationship]:
        return [
            relationship
            for relationship in
            await models.Relationship.filter(Q(from_user=self) | Q(to_user=self)).select_related("from_user", "to_user")
            if not (relationship.type == RelationshipType.BLOCK and relationship.from_user.id != self.id)
        ]

    async def get_related_users(self) -> list[models.User]:
        users = {
            relationship.other_user(self).id: relationship.other_user(self)
            for relationship in await self.get_relationships()
        }
        for channel in await models.Channel.filter(recipients__id=self.id):
            for recipient in await channel.recipients.all():
                if recipient.id in users or recipient == self:
                    continue
                users[recipient.id] = recipient

        return list(users.values())

    async def get_mfa_key(self) -> str | None:
        return cast(str, await models.UserSettings.get(user=self).values_list("mfa", flat=True))

    async def generate_mfa_nonce(self) -> tuple[str, str]:
        key = b64decode(Config.KEY)
        exp = time() + 600
        code = b64encode(urandom(16))
        nonce = JWT.encode({"t": MfaNonceType.NORMAL, "c": code, "u": self.id}, key, exp)
        rnonce = JWT.encode({"t": MfaNonceType.REGENERATE, "c": code, "u": self.id}, key, exp)
        return nonce, rnonce

    async def verify_mfa_nonce(self, nonce: str, nonce_type: MfaNonceType) -> None:
        key = b64decode(Config.KEY)
        assert_(payload := JWT.decode(nonce, key), InvalidKey)
        assert_(payload["u"] == self.id, InvalidKey)
        assert_(nonce_type == payload["t"], InvalidKey)

    async def update_read_state(self, channel: models.Channel, count: int, last: int) -> None:
        await models.ReadState.update_or_create(user=self, channel=channel, defaults={
            "last_read_id": last,
            "count": count,
        })

    async def send_verification_email(self) -> None:
        token = JWT.encode({"id": self.id, "email": self.email}, b64decode(Config.KEY), expires_after=600)
        await EmailMsg.send_verification(self.email, token)

    async def get_read_states(self) -> list[models.ReadState]:
        if self.is_bot:
            return []

        return await models.ReadState.filter(user=self).select_related("channel")
