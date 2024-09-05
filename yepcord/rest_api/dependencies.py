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

from time import time
from typing import Union, Optional, Callable, Awaitable, TypeVar

from fast_depends import Depends
from quart import request
from typing_extensions import ParamSpec

from yepcord.rest_api.utils import getSessionFromToken
from yepcord.yepcord.ctx import getCore
from yepcord.yepcord.errors import InvalidDataErr, Errors, UnknownApplication, UnknownInvite, UnknownMessage, \
    UnknownRole, UnknownGuildTemplate, MissingAccess, Unauthorized
from yepcord.yepcord.models import Session, Authorization, Bot, User, Channel, Message, Webhook, Invite, Guild, \
    GuildMember, Role, GuildTemplate, Application, Interaction
from yepcord.yepcord.snowflake import Snowflake
from yepcord.yepcord.utils import b64decode

SessionsType = Union[Session, Authorization, Bot]
T = TypeVar("T")
P = ParamSpec("P")


def depRaise(func: Callable[P, Awaitable[Optional[T]]], status_code: int, error: dict) -> Callable[P, Awaitable[T]]:
    async def wrapper(res=Depends(func)):
        if res is None:
            raise InvalidDataErr(status_code, error)
        return res

    return wrapper


async def depSessionO() -> Optional[SessionsType]:
    if session := await getSessionFromToken(request.headers.get("Authorization", "")):
        return session


depSession = depRaise(depSessionO, 401, Errors.make(0, message="401: Unauthorized"))


async def _depUser_with_user(session: SessionsType = Depends(depSession)) -> User:
    return session.user


async def _depUser_without_user(session: Optional[SessionsType] = Depends(depSessionO)) -> Optional[User]:
    if session:
        return session.user


def depUser(allow_without_user: bool = False):
    return _depUser_without_user if allow_without_user else _depUser_with_user


async def depChannelO(channel_id: Optional[int] = None, user: User = Depends(depUser())) -> Optional[Channel]:
    if (channel := await getCore().getChannel(channel_id)) is None:
        return
    if not await getCore().getUserByChannel(channel, user.id):
        raise Unauthorized

    return channel


async def depChannelONoAuth(channel_id: Optional[int] = None, user: Optional[User] = Depends(depUser(True))) \
        -> Optional[Channel]:
    if user is None:
        return
    return await depChannelO(channel_id, user)


depChannel = depRaise(depChannelO, 404, Errors.make(10003))


async def depWebhookO(webhook: Optional[int] = None, token: Optional[str] = None) -> Optional[Webhook]:
    if webhook is None or token is None:
        return
    webhook = await Webhook.get_or_none(id=webhook).select_related("channel")
    if webhook is None or webhook.token != token:
        return
    return webhook


depWebhook = depRaise(depWebhookO, 404, Errors.make(10015))


async def depMessageO(
        message: int,
        channel: Optional[Channel] = Depends(depChannelONoAuth),
        webhook: Optional[Webhook] = Depends(depWebhookO),
        user: Optional[User] = Depends(depUser(True)),
) -> Optional[Message]:
    if webhook:
        message = await Message.get_or_none(id=message, webhook_id=webhook.id).select_related(*Message.DEFAULT_RELATED)
    elif channel is not None and user is not None:
        message = await channel.get_message(message)
    else:
        raise Unauthorized

    if message is not None:
        return message

    return


depMessage = depRaise(depMessageO, 404, Errors.make(10008))


async def depInvite(invite: Optional[str] = None) -> Invite:
    try:
        invite_id = int.from_bytes(b64decode(invite), "big")
        invite = await (
            Invite.get_or_none(id=invite_id)
            .select_related("channel", "channel__guild", "inviter", "channel__guild__owner", "channel__owner")
        )
        if not invite:
            raise ValueError
    except ValueError:
        if not (invite := await getCore().getVanityCodeInvite(invite)):
            raise UnknownInvite

    return invite


async def depGuildO(guild: Optional[int] = None, user: User = Depends(depUser())) -> Optional[Guild]:
    if (guild := await getCore().getGuild(guild)) is None:
        return
    if not await GuildMember.filter(guild=guild, user=user).exists():
        raise MissingAccess

    return guild


depGuild = depRaise(depGuildO, 404, Errors.make(10004))


async def depGuildMember(guild: Guild = Depends(depGuild), user: User = Depends(depUser())) -> GuildMember:
    return await GuildMember.get(guild=guild, user=user).select_related("user", "guild", "guild__owner")


async def depRole(role: int, guild: Guild = Depends(depGuild)) -> Role:
    if not role or not (role := await getCore().getRole(role, guild)):
        raise UnknownRole
    return role


async def depGuildTemplate(template: str, guild: Guild = Depends(depGuild)) -> GuildTemplate:
    try:
        template_id = int.from_bytes(b64decode(template), "big")
        if not (template := await getCore().getGuildTemplateById(template_id, guild)):
            raise ValueError
    except ValueError:
        raise UnknownGuildTemplate
    return template


async def depApplication(application_id: int, user: User = Depends(depUser())) -> Application:
    if user.is_bot and application_id != user.id:
        raise UnknownApplication

    kw = {"id": application_id, "deleted": False}
    if not user.is_bot:
        kw["owner"] = user
    if (app := await Application.get_or_none(**kw).select_related("owner")) is None:
        raise UnknownApplication

    return app


async def depInteraction(interaction: int, token: str) -> Interaction:
    if not token.startswith("int___"):
        raise UnknownApplication

    interaction = await (Interaction.get_or_none(id=interaction)
                         .select_related("application", "user", "channel", "command"))
    if interaction is None or interaction.ds_token != token:
        raise UnknownApplication

    return interaction


async def depInteractionW(application_id: int, token: str) -> Message:
    if not (inter := await Interaction.from_token(f"int___{token}")) or inter.application.id != application_id:
        raise UnknownApplication

    message = await Message.get_or_none(interaction=inter, id__gt=Snowflake.fromTimestamp(time() - 15 * 60)) \
        .select_related(*Message.DEFAULT_RELATED)
    if message is None:
        raise UnknownMessage

    return message


DepSession = Depends(depSession)
DepUser = Depends(depUser())
DepUserO = Depends(depUser(True))
DepChannel = Depends(depChannel)
DepWebhook = Depends(depWebhook)
DepMessage = Depends(depMessage)
DepInvite = Depends(depInvite)
DepGuild = Depends(depGuild)
DepGuildO = Depends(depGuildO)
DepGuildMember = Depends(depGuildMember)
DepRole = Depends(depRole)
DepGuildTemplate = Depends(depGuildTemplate)
DepApplication = Depends(depApplication)
DepInteraction = Depends(depInteraction)
DepInteractionW = Depends(depInteractionW)
