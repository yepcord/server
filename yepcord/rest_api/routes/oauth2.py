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

from quart import Blueprint, request
from quart_schema import validate_querystring, validate_request, DataSource

from ..models.oauth2 import AppAuthorizeGetQs, ExchangeCode, AppAuthorizePostQs, AppAuthorizePost
from ..utils import getUser, multipleDecorators, captcha
from ...gateway.events import GuildCreateEvent, MessageCreateEvent, GuildAuditLogEntryCreateEvent, GuildRoleCreateEvent, \
    IntegrationCreateEvent
from ...yepcord.config import Config
from ...yepcord.ctx import getCore, getGw
from ...yepcord.enums import ApplicationScope, GuildPermissions, MessageType
from ...yepcord.errors import Errors, InvalidDataErr
from ...yepcord.models import User, Guild, GuildMember, Message, Role, AuditLogEntry, Application, Bot, Authorization, \
    Integration
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import b64decode

# Base path is /api/vX/oauth2
oauth2 = Blueprint('oauth2', __name__)


@oauth2.get("/authorize", strict_slashes=False)
@multipleDecorators(validate_querystring(AppAuthorizeGetQs), getUser)
async def get_application_authorization_info(query_args: AppAuthorizeGetQs, user: User):
    scopes = set(query_args.scope.split(" ") if query_args.scope else [])
    if len(scopes & ApplicationScope.values_set()) != len(scopes):
        raise InvalidDataErr(400, Errors.make(50035,
                                              {"scope": {"code": "SCOPE_INVALID", "message": "Invalid scope"}}))

    if (application := await Application.get_or_none(id=query_args.client_id, deleted=False)) is None:
        raise InvalidDataErr(404, Errors.make(10002))
    bot = await Bot.get(id=application.id).select_related("user")

    result = {
        "application": {
            "id": str(application.id),
            "name": application.name,
            "icon": application.icon,
            "description": application.description,
            "summary": application.summary,
            "type": None,
            "hook": application.hook,
            "verify_key": application.verify_key,
            "flags": application.flags,
        },
        "authorized": False,
        "user": (await user.userdata).ds_json,
    }

    if "bot" in scopes:
        async def guild_ds_json(g: Guild) -> dict:
            member = await getCore().getGuildMember(g, user.id)
            return {"id": str(g.id), "name": g.name, "icon": g.icon, "mfa_level": g.mfa_level,
                    "permissions": str(await member.permissions)}

        result["bot"] = (await bot.user.userdata).ds_json
        result["application"]["bot_public"] = bot.bot_public
        result["application"]["bot_require_code_grant"] = bot.bot_require_code_grant
        result["guilds"] = [await guild_ds_json(guild) for guild in await getCore().getUserGuilds(user)]

    return result


@oauth2.post("/authorize", strict_slashes=False)
@multipleDecorators(captcha, validate_querystring(AppAuthorizePostQs), validate_request(AppAuthorizePost), getUser)
async def authorize_application(query_args: AppAuthorizePostQs, data: AppAuthorizePost, user: User):
    scopes = set(query_args.scope.split(" ") if query_args.scope else [])
    if len(scopes & ApplicationScope.values_set()) != len(scopes):
        raise InvalidDataErr(400, Errors.make(50035,
                                              {"scope": {"code": "SCOPE_INVALID", "message": "Invalid scope"}}))

    if (application := await Application.get_or_none(id=query_args.client_id, deleted=False)) is None:
        raise InvalidDataErr(404, Errors.make(10002))

    if not data.authorize:
        return {"location": f"{query_args.redirect_uri}?error=access_denied&error_description="
                            "The+resource+owner+or+authorization+server+denied+the+request"}

    if "bot" in scopes:
        if not data.guild_id:
            return {"location": f"https://{Config.PUBLIC_HOST}/oauth2/error?error=invalid_request&error_description="
                                f"Guild+not+specified."}

        if (guild := await getCore().getGuild(data.guild_id)) is None:
            raise InvalidDataErr(404, Errors.make(10004))

        if not (member := await getCore().getGuildMember(guild, user.id)):
            raise InvalidDataErr(403, Errors.make(50001))

        await member.checkPermission(GuildPermissions.MANAGE_GUILD)
        bot = await Bot.get(id=application.id).select_related("user")
        if (ban := await getCore().getGuildBan(guild, bot.user.id)) is not None:
            await ban.delete()

        bot_userdata = await bot.user.userdata
        bot_member = await GuildMember.create(id=Snowflake.makeId(), user=bot.user, guild=guild)
        bot_role = await Role.create(id=Snowflake.makeId(), guild=guild, name=bot_userdata.username,
                                     tags={"bot_id": str(bot.id)}, permissions=data.permissions, managed=True)
        await bot_member.roles.add(bot_role)

        integration = await Integration.create(application=application, guild=guild, user=user,
                                               scopes=["bot", "application.commands"])

        await getGw().dispatch(IntegrationCreateEvent(integration), guild_id=guild.id,
                               permissions=GuildPermissions.MANAGE_GUILD)
        await getGw().dispatch(GuildRoleCreateEvent(guild.id, bot_role.ds_json()), guild_id=guild.id,
                               permissions=GuildPermissions.MANAGE_ROLES)
        entries = [
            await AuditLogEntry.utils.role_create(user, bot_role),
            await AuditLogEntry.utils.bot_add(user, guild, bot.user),
            await AuditLogEntry.utils.integration_create(user, guild, bot.user),
        ]
        for entry in entries:
            await getGw().dispatch(GuildAuditLogEntryCreateEvent(entry.ds_json()), guild_id=guild.id,
                                   permissions=GuildPermissions.VIEW_AUDIT_LOG)

        await getGw().dispatch(GuildCreateEvent(await guild.ds_json(user_id=bot.user.id)), users=[bot.user.id])
        if guild.system_channel:
            sys_channel = await getCore().getChannel(guild.system_channel)
            message = await Message.create(
                id=Snowflake.makeId(), author=bot.user, channel=sys_channel, content="", type=MessageType.USER_JOIN,
                guild=guild
            )
            await getCore().sendMessage(message)
            await getGw().dispatch(MessageCreateEvent(await message.ds_json()), channel_id=sys_channel.id)

        return {"location": f"https://{Config.PUBLIC_HOST}/oauth2/authorized"}

    if query_args.redirect_uri not in application.redirect_uris:
        return {"location": f"https://{Config.PUBLIC_HOST}/oauth2/error?error=invalid_request&error_description="
                            f"Redirect+URI+{query_args.redirect_uri}+is+not+supported+by+client."}

    authorization = await Authorization.create(user=user, application=application, scope=query_args.scope)

    return {"location": f"{query_args.redirect_uri}?code={authorization.code}"}


@oauth2.post("/token", strict_slashes=False)
@validate_request(ExchangeCode, source=DataSource.FORM)
async def exchange_code_for_token(data: ExchangeCode):
    if not request.authorization and (not data.client_id or not data.client_secret):
        return {"error": "invalid_client"}, 401

    if request.authorization:
        auth = request.authorization
        params = auth.parameters
        try:
            data.client_id, data.client_secret = int(params["username"]), params["password"]
        except (ValueError, KeyError):
            return {"error": "invalid_client"}, 401

    application = await (Application.get_or_none(id=data.client_id, deleted=False, secret=data.client_secret)
                         .select_related("owner"))
    if application is None:
        return {"error": "invalid_client"}, 401

    if data.code is None and (data.scope is None or data.grant_type != "client_credentials"):
        return {"error": "invalid_grant", "error_description": "Invalid \"code\" in request."}, 400

    authorization: Authorization
    if data.code is not None:
        try:
            authorization_id, authorization_secret = data.code.split(".")
            authorization_id = int(b64decode(authorization_id))
        except (ValueError, IndexError):
            return {"error": "invalid_grant", "error_description": "Invalid \"code\" in request."}, 400

        authorization = await Authorization.get_or_none(
            id=authorization_id, application=application, auth_code=authorization_secret, expires_at__gt=int(time())
        )
        if authorization is None:
            return {"error": "invalid_grant", "error_description": "Invalid \"code\" in request."}, 400

        await authorization.update(auth_code=None, expires_at=int(time() + 604800))
    else:
        authorization = await Authorization.create(
            user=application.owner, application=application, refresh_token=None, scope=data.scope,
            expires_at=int(time() + 604800))

    resp = {
        "token_type": "Bearer",
        "access_token": authorization.token,
        "expires_in": 604800,
        "scope": authorization.scope
    }

    if authorization.refresh_token is not None:
        resp["refresh_token"] = authorization.ref_token

    return resp
