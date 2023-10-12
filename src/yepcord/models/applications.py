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
from os import urandom
from time import time
from typing import Optional

import ormar
from ormar import ReferentialAction

from . import User, DefaultMeta, SnowflakeAIQuerySet, Guild
from ..utils import b64encode, b64decode


def gen_verify_key() -> str:
    return urandom(32).hex()


def gen_secret_key() -> str:
    return b64encode(urandom(32))


def gen_token_secret() -> str:
    return b64encode(urandom(48))


class Application(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    owner: User = ormar.ForeignKey(User, ondelete=ReferentialAction.SET_NULL, nullable=True, related_name="app_owner")
    name: str = ormar.String(max_length=100)
    description: str = ormar.String(default="", max_length=240)
    summary: str = ormar.String(default="", max_length=240)
    icon: Optional[str] = ormar.String(nullable=True, default=None, max_length=64)
    creator_monetization_state: int = ormar.Integer(default=1)
    monetization_state: int = ormar.Integer(default=1)
    discoverability_state: int = ormar.Integer(default=1)
    discovery_eligibility_flags: int = ormar.Integer(default=0)
    explicit_content_filter: int = ormar.Integer(default=0)
    flags: int = ormar.BigInteger(default=0)
    hook: bool = ormar.Boolean(default=True)
    integration_public: bool = ormar.Boolean(default=True)
    integration_require_code_grant: bool = ormar.Boolean(default=True)
    interactions_endpoint_url: Optional[str] = ormar.String(nullable=True, default=None, max_length=2048)
    interactions_event_types: list = ormar.JSON(default=[])
    interactions_version: int = ormar.Integer(default=1)
    redirect_uris: list[str] = ormar.JSON(default=[])
    rpc_application_state: int = ormar.Integer(default=0)
    store_application_state: int = ormar.Integer(default=1)
    verification_state: int = ormar.Integer(default=1)
    verify_key: str = ormar.String(default=gen_verify_key, max_length=128)
    deleted: bool = ormar.Boolean(default=False)
    tags: list[str] = ormar.JSON(default=[])
    privacy_policy_url: str = ormar.String(default=None, nullable=True, max_length=2048)
    terms_of_service_url: str = ormar.String(default=None, nullable=True, max_length=2048)
    role_connections_verification_url: str = ormar.String(default=None, nullable=True, max_length=2048)
    secret: str = ormar.String(default=gen_secret_key, max_length=128)

    #role_connections_verification_url: ... = ...  # ???, default=None
    #type_: ... = ...  # ???, default=None

    async def ds_json(self) -> dict:
        bot: Optional[Bot] = await Bot.objects.select_related("user").get_or_none(application=self)

        data = {
            "id": str(self.id),
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "summary": self.summary,
            "type": None,
            "hook": self.hook,
            "verify_key": self.verify_key,
            "owner": (await self.owner.userdata).ds_json,
            "flags": self.flags,
            "redirect_uris": self.redirect_uris,
            "rpc_application_state": self.rpc_application_state,
            "store_application_state": self.store_application_state,
            "creator_monetization_state": self.creator_monetization_state,
            "verification_state": self.verification_state,
            "interactions_endpoint_url": self.interactions_endpoint_url,
            "interactions_event_types": self.interactions_event_types,
            "interactions_version": self.interactions_version,
            "integration_public": self.integration_public,
            "integration_require_code_grant": self.integration_require_code_grant,
            "explicit_content_filter": self.explicit_content_filter,
            "discoverability_state": self.discoverability_state,
            "discovery_eligibility_flags": self.discovery_eligibility_flags,
            "monetization_state": self.monetization_state,
            "approximate_guild_count": 0,
            "tags": self.tags,
            "privacy_policy_url": self.privacy_policy_url,
            "terms_of_service_url": self.terms_of_service_url,
            "role_connections_verification_url": self.role_connections_verification_url,
        }

        if bot is not None:
            data["bot_public"] = bot.bot_public
            data["bot_require_code_grant"] = bot.bot_require_code_grant
            data["bot"] = (await bot.user.userdata).ds_json

        return data


class Bot(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    application: Application = ormar.ForeignKey(Application, ondelete=ReferentialAction.CASCADE, nullable=False,
                                                unique=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, nullable=True, default=None,
                                  related_name="bot_user")
    bot_public: bool = ormar.Boolean(default=True)
    bot_require_code_grant: bool = ormar.Boolean(default=True)
    token_secret: str = ormar.String(max_length=128, default=gen_token_secret)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.token_secret}"

    @staticmethod
    def extract_token(token: str) -> Optional[tuple[int, str]]:
        token = token.split(".")
        if len(token) != 2:
            return
        bot_id, secret = token
        try:
            bot_id = int(b64decode(bot_id))
            b64decode(secret)
        except ValueError:
            return
        return bot_id, secret

    @classmethod
    async def from_token(cls, token: str) -> Optional[Bot]:
        token = Authorization.extract_token(token)
        if token is None:
            return
        bot_id, secret = token
        return await Bot.objects.select_related("user").get_or_none(id=bot_id, token_secret=secret)


class Authorization(ormar.Model):
    class Meta(DefaultMeta):
        queryset_class = SnowflakeAIQuerySet

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    application: Application = ormar.ForeignKey(Application, ondelete=ReferentialAction.CASCADE)
    guild: Optional[Guild] = ormar.ForeignKey(Guild, ondelete=ReferentialAction.CASCADE, nullable=True, default=None)
    scope: str = ormar.String(max_length=1024)
    secret: str = ormar.String(max_length=128, default=gen_token_secret)
    refresh_token: str = ormar.String(max_length=128, default=gen_token_secret, nullable=True)
    expires_at: int = ormar.BigInteger(default=lambda: int(time() + 60 * 3))
    auth_code: Optional[str] = ormar.String(max_length=128, nullable=True, default=gen_secret_key)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.secret}"

    @property
    def ref_token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.refresh_token}"

    @property
    def code(self) -> str:
        return f"{b64encode(str(self.id))}.{self.auth_code}"

    @property
    def scope_set(self) -> set[str]:
        return set(self.scope.split(" "))

    @staticmethod
    def extract_token(token: str) -> Optional[tuple[int, str]]:
        token = token.split(".")
        if len(token) != 2:
            return
        auth_id, secret = token
        try:
            auth_id = int(b64decode(auth_id))
            b64decode(secret)
        except ValueError:
            return
        return auth_id, secret

    @classmethod
    async def from_token(cls, token: str) -> Optional[Authorization]:
        token = Authorization.extract_token(token)
        if token is None:
            return
        auth_id, secret = token
        return await Authorization.objects.select_related("user").get_or_none(id=auth_id, secret=secret,
                                                                              expires_at__gt=int(time()))
