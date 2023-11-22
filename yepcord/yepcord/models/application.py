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
from os import urandom
from typing import Optional

from tortoise import fields

from ._utils import SnowflakeField, Model

import yepcord.yepcord.models as models
from ..utils import b64encode


def gen_verify_key() -> str:
    return urandom(32).hex()


def gen_secret_key() -> str:
    return b64encode(urandom(32))


class Application(Model):
    id: int = SnowflakeField(pk=True)
    owner: models.User = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True,
                                                related_name="app_owner")
    name: str = fields.CharField(max_length=100)
    description: str = fields.CharField(default="", max_length=240)
    summary: str = fields.CharField(default="", max_length=240)
    icon: Optional[str] = fields.CharField(null=True, default=None, max_length=64)
    creator_monetization_state: int = fields.IntField(default=1)
    monetization_state: int = fields.IntField(default=1)
    discoverability_state: int = fields.IntField(default=1)
    discovery_eligibility_flags: int = fields.IntField(default=0)
    explicit_content_filter: int = fields.IntField(default=0)
    flags: int = fields.BigIntField(default=0)
    hook: bool = fields.BooleanField(default=True)
    integration_public: bool = fields.BooleanField(default=True)
    integration_require_code_grant: bool = fields.BooleanField(default=True)
    interactions_endpoint_url: Optional[str] = fields.CharField(null=True, default=None, max_length=2048)
    interactions_event_types: list = fields.JSONField(default=[])
    interactions_version: int = fields.IntField(default=1)
    redirect_uris: list[str] = fields.JSONField(default=[])
    rpc_application_state: int = fields.IntField(default=0)
    store_application_state: int = fields.IntField(default=1)
    verification_state: int = fields.IntField(default=1)
    verify_key: str = fields.CharField(default=gen_verify_key, max_length=128)
    deleted: bool = fields.BooleanField(default=False)
    tags: list[str] = fields.JSONField(default=[])
    privacy_policy_url: str = fields.CharField(default=None, null=True, max_length=2048)
    terms_of_service_url: str = fields.CharField(default=None, null=True, max_length=2048)
    role_connections_verification_url: str = fields.CharField(default=None, null=True, max_length=2048)
    secret: str = fields.CharField(default=gen_secret_key, max_length=128)

    async def ds_json(self) -> dict:
        bot: Optional[models.Bot] = await models.Bot.get_or_none(application=self).select_related("user")

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
