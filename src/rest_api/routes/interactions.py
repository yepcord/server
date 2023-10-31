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
from tortoise.expressions import Q

from ..models.interactions import InteractionCreate, InteractionRespond, InteractionDataOption as InteractionOption
from ..utils import getUser, get_multipart_json, getInteraction, multipleDecorators
from ...gateway.events import InteractionCreateEvent, InteractionFailureEvent, MessageCreateEvent, \
    InteractionSuccessEvent
from ...yepcord.ctx import getCore, getGw
from ...yepcord.enums import GuildPermissions, InteractionStatus, MessageFlags, InteractionCallbackType, \
    ApplicationCommandOptionType, MessageType, ApplicationCommandType
from ...yepcord.errors import Errors, InvalidDataErr
from ...yepcord.models import User, Application, ApplicationCommand, Integration, Message, Guild
from ...yepcord.models.interaction import Interaction
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import execute_after

# Base path is /api/vX/interactions
interactions = Blueprint('interactions', __name__)


async def resolve_options(interaction_options: list[InteractionOption], guild: Guild = None, result=None):
    if result is None:
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
        elif option.type in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
            await resolve_options(option.options, guild, result)
    return result


def validate_options_sub(user_options: list[InteractionOption], bot_options: dict[str, dict], result=None) \
        -> list[InteractionOption]:
    if len(user_options) != 1 or user_options[0].name not in bot_options:
        raise InvalidDataErr(400, Errors.make(50035, {"data.options": {
            "code": "INTERACTION_APPLICATION_COMMAND_OPTION_MISSING",
            "message": "Missing interaction application command option"}}))
    user_option = user_options[0]
    bot_option = bot_options[user_option.name]
    if result is None:
        result = []
    _options = []
    if bot_option.get("options"):
        validate_options(user_option.options, bot_option["options"], _options)
    result.append(InteractionOption(type=user_options[0].type, name=user_option.name, options=_options))
    return result


def validate_options_nonsub(user_options: dict[str, InteractionOption], bot_options: list[dict], result=None) \
        -> list[InteractionOption]:
    if result is None:
        result = []

    for option in bot_options:
        user_option = user_options.get(option["name"])
        if (not user_option and option.get("required", True)) or (user_option and user_option.type != option["type"]):
            raise InvalidDataErr(400, Errors.make(50035, {"data.options": {
                "code": "INTERACTION_APPLICATION_COMMAND_OPTION_MISSING",
                "message": "Missing interaction application command option"}}))
        if user_option:
            result.append(user_option)

    return result


def validate_options(user_options: list[InteractionOption], bot_options: list[dict], result=None) \
        -> list[InteractionOption]:
    T = ApplicationCommandOptionType
    if bot_options and bot_options[0]["type"] in {T.SUB_COMMAND, T.SUB_COMMAND_GROUP}:
        bot_options: dict[str, dict] = {option["name"]: option for option in bot_options}
        return validate_options_sub(user_options, bot_options, result)
    user_options: dict[str, InteractionOption] = {option.name: option for option in user_options}
    return validate_options_nonsub(user_options, bot_options, result)


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
    command_query = Q(id=data.data.id, application=application) & (Q(guild=guild) | Q(guild=None))
    if (command := await ApplicationCommand.get_or_none(command_query)) is None:
        raise InvalidDataErr(404, Errors.make(10002))
    message = None
    target_member = None
    if command.type == ApplicationCommandType.MESSAGE and \
            (message := await getCore().getMessage(channel, data.data.target_id)) is None:
        raise InvalidDataErr(404, Errors.make(10008))
    if command.type == ApplicationCommandType.USER and \
            (target_member := await getCore().getGuildMember(guild, data.data.target_id)) is None:
        raise InvalidDataErr(404, Errors.make(10013))

    if data.data.version != command.version or data.data.type != command.type or data.data.name != command.name:
        raise InvalidDataErr(400, Errors.make(50035, {"data": {
            "code": "INTERACTION_APPLICATION_COMMAND_INVALID_VERSION",
            "message": "This command is outdated, please try again in a few minutes"}}))

    settings = await user.settings
    guild_locale = guild.preferred_locale if guild is not None else None
    resolved = {}
    if command.type == ApplicationCommandType.CHAT_INPUT:
        data.data.options = validate_options(data.data.options, command.options)
        resolved = await resolve_options(data.data.options, guild)
    elif command.type == ApplicationCommandType.MESSAGE:
        data.data.options = []
        resolved = {"messages": {str(message.id): await message.ds_json()}}
    elif command.type == ApplicationCommandType.USER:
        data.data.options = []
        resolved = {
            "members": {str(target_member.user.id): await target_member.ds_json()},
            "users": {str(target_member.user.id): (await target_member.user.userdata).ds_json},
        }

    int_data = data.data.model_dump(exclude={"version"})
    int_data["id"] = str(int_data["id"])
    if int_data["target_id"]:
        int_data["target_id"] = str(int_data["target_id"])

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


async def send_interaction_response(interaction: Interaction, flags: bool, content: str) -> Message:
    is_ephemeral = flags & MessageFlags.EPHEMERAL == MessageFlags.EPHEMERAL
    is_loading = flags & MessageFlags.LOADING == MessageFlags.LOADING

    bot_user = await User.y.get(interaction.application.id)
    message = await Message.create(id=Snowflake.makeId(), author=bot_user, content=content, flags=flags,
                                   interaction=interaction, channel=interaction.channel, ephemeral=is_ephemeral,
                                   webhook_id=interaction.id, type=MessageType.CHAT_INPUT_COMMAND)
    message_obj = await message.ds_json() | {"nonce": str(interaction.nonce)}

    kw = {"session_id": interaction.session_id} if is_ephemeral else {}
    await getGw().dispatch(InteractionSuccessEvent(interaction), users=[interaction.user.id], **kw)
    if is_ephemeral:
        await getGw().dispatch(MessageCreateEvent(message_obj), users=[interaction.user.id, bot_user.id])
    else:
        await getGw().dispatch(MessageCreateEvent(message_obj), channel_id=interaction.channel.id)
    await interaction.update(status=InteractionStatus.RESPONDED if not is_loading else InteractionStatus.DEFERRED)

    return message


@interactions.post("/<int:interaction>/<string:token>/callback")
@multipleDecorators(validate_request(InteractionRespond), getInteraction)
async def respond_to_interaction(data: InteractionRespond, interaction: Interaction):
    T = InteractionCallbackType
    d = data.data
    if interaction.status != InteractionStatus.PENDING:
        raise InvalidDataErr(400, Errors.make(40060))
    if data.type == T.CHANNEL_MESSAGE_WITH_SOURCE:
        if not d.content:
            raise InvalidDataErr(400, Errors.make(50006))
        flags = d.flags & MessageFlags.EPHEMERAL
        await send_interaction_response(interaction, flags, d.content)
    elif data.type == T.DEFFERED_CHANNEL_MESSAGE_WITH_SOURCE:
        flags = d.flags & MessageFlags.EPHEMERAL if d is not None else 0
        flags |= MessageFlags.LOADING
        await send_interaction_response(interaction, flags, "")

    return "", 204
