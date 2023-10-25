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

from quart import Blueprint
from quart_schema import validate_request

from ..models.interactions import InteractionCreate, InteractionRespond, InteractionDataOption
from ..utils import getUser, get_multipart_json, getInteraction, multipleDecorators
from ...gateway.events import InteractionCreateEvent, InteractionFailureEvent, MessageCreateEvent, \
    InteractionSuccessEvent
from ...yepcord.ctx import getCore, getGw
from ...yepcord.enums import GuildPermissions, InteractionStatus, MessageFlags, InteractionCallbackType, \
    ApplicationCommandOptionType
from ...yepcord.errors import Errors, InvalidDataErr
from ...yepcord.models import User, Application, ApplicationCommand, Integration, Message, Guild
from ...yepcord.models.interaction import Interaction
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import execute_after

# Base path is /api/vX/interactions
interactions = Blueprint('interactions', __name__)


async def resolve_options(interaction_options: list[InteractionDataOption], guild: Guild = None):
    result = {}
    T = ApplicationCommandOptionType
    for option in interaction_options:
        if option.type == T.USER:
            if not (user := await User.y.get(option.value)):
                continue
            if "users" not in result:
                result["users"] = {}
            result["users"][option.value] = (await user.userdata).ds_json
            if guild is None or not (member := await getCore().getGuildMember(guild, user.id)):
                continue
            if "members" not in result:
                result["members"] = {}
            result["members"][option.value] = await member.ds_json(False)
        elif option.type == T.CHANNEL:
            if guild is None or (channel := await getCore().getChannel(option.value)) is None:
                continue
            if channel.guild != guild:
                continue
            if "channels" not in result:
                result["channels"] = {}
            result["channels"][option.value] = await channel.ds_json()
        elif option.type == T.ROLE:
            if guild is None or (role := await getCore().getRole(option.value)) is None:
                continue
            if role.guild != guild:
                continue
            if "roles" not in result:
                result["roles"] = {}
            result["roles"][option.value] = role.ds_json()
    return result


@interactions.post("/", strict_slashes=False)
@getUser
async def create_interaction(user: User):
    data = InteractionCreate(**(await get_multipart_json()))
    if (application := await Application.get_or_none(id=data.application_id, deleted=False)) is None:
        raise InvalidDataErr(404, Errors.make(10002))
    guild = None
    channel = await getCore().getChannel(data.channel_id)
    if data.guild_id:
        if (guild := await getCore().getGuild(data.guild_id)) is None:
            raise InvalidDataErr(404, Errors.make(10004))
        if (member := await getCore().getGuildMember(guild, user.id)) is None:
            raise InvalidDataErr(403, Errors.make(50001))
        P = GuildPermissions
        await member.checkPermission(P.VIEW_CHANNEL, P.USE_APPLICATION_COMMANDS, channel=channel)
    if channel.guild != guild:
        raise InvalidDataErr(404, Errors.make(10003))
    if not await getCore().getUserByChannel(channel, user.id):
        raise InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
    if guild is not None:
        if (await Integration.get_or_none(guild=guild, application=application)) is None:
            raise InvalidDataErr(404, Errors.make(10002))
    if (command := await ApplicationCommand.get_or_none(id=data.data.id, application=application)) is None:
        raise InvalidDataErr(404, Errors.make(10002))

    settings = await user.settings
    guild_locale = guild.preferred_locale if guild is not None else None
    int_data = data.data.model_dump(exclude={"version"})
    resolved = await resolve_options(data.data.options)
    interaction = await Interaction.create(
        application=application, user=user, type=data.type, data=int_data, guild=guild, channel=channel,
        locale=settings.locale, guild_locale=guild_locale, nonce=data.nonce, session_id=data.session_id,
        command=command
    )

    await getGw().dispatch(InteractionCreateEvent(interaction, False), users=[user.id], session_id=data.session_id)
    await getGw().dispatch(InteractionCreateEvent(interaction, True, resolved=resolved), users=[application.id])

    async def wait_for_interaction():
        await interaction.refresh_from_db()
        if interaction.status == InteractionStatus.PENDING:
            await interaction.delete()
            await getGw().dispatch(InteractionFailureEvent(interaction), users=[user.id], session_id=data.session_id)

    await execute_after(wait_for_interaction(), 3)

    return "", 204


@interactions.post("/<int:interaction>/<string:token>/callback")
@multipleDecorators(validate_request(InteractionRespond), getInteraction)
async def respond_to_interaction(data: InteractionRespond, interaction: Interaction):
    if data.type == InteractionCallbackType.CHANNEL_MESSAGE_WITH_SOURCE:
        d = data.data
        if not d.content:
            raise InvalidDataErr(400, Errors.make(50006))
        flags = d.flags & MessageFlags.EPHEMERAL
        is_ephemeral = bool(flags)
        bot_user = await User.y.get(interaction.application.id)
        message = await Message.create(id=Snowflake.makeId(), author=bot_user, content=d.content, flags=flags,
                                       interaction=interaction, channel=interaction.channel,
                                       ephemeral=is_ephemeral, webhook_id=interaction.id)
        message_obj = await message.ds_json() | {"nonce": interaction.nonce}

        kw = {"session_id": interaction.session_id} if is_ephemeral else {}
        await getGw().dispatch(InteractionSuccessEvent(interaction), users=[interaction.user.id], **kw)
        await getGw().dispatch(MessageCreateEvent(message_obj), users=[interaction.user.id, bot_user.id])
        if not is_ephemeral:
            await getGw().dispatch(MessageCreateEvent(message_obj), channel_id=interaction.channel.id)
        await interaction.update(status=InteractionStatus.RESPONDED)

        return message
    return "", 204
