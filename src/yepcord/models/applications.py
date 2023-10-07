from os import urandom
from typing import Optional

import ormar
from ormar import ReferentialAction

from . import User, DefaultMeta
from ..utils import b64encode


def gen_verify_key() -> str:
    return urandom(32).hex()


def gen_secret_key() -> str:
    return b64encode(urandom(32))


def gen_bot_token_secret() -> str:
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
    token_secret: str = ormar.String(max_length=128, default=gen_bot_token_secret)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.id))}.{self.token_secret}"
