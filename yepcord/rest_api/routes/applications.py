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
from datetime import datetime
from typing import Optional

from ..dependencies import DepApplication, DepUser, DepGuildO
from ..models.applications import CreateApplication, UpdateApplication, UpdateApplicationBot, GetCommandsQS, \
    CreateCommand
from ..y_blueprint import YBlueprint
from ...yepcord.enums import ApplicationCommandType
from ...yepcord.models import User, UserData, UserSettings, Application, Bot, gen_secret_key, gen_token_secret, \
    ApplicationCommand, Guild
from ...yepcord.snowflake import Snowflake
from ...yepcord.storage import getStorage
from ...yepcord.utils import getImage

# Base path is /api/vX/applications
applications = YBlueprint('applications', __name__)


@applications.get("/", strict_slashes=False)
async def get_applications(user: User = DepUser):
    return [
        await app.ds_json()
        for app in await Application.filter(owner=user, deleted=False).select_related("owner")
    ]


@applications.post("/", strict_slashes=False, body_cls=CreateApplication)
async def create_application(data: CreateApplication, user: User = DepUser):
    app_id = Snowflake.makeId()
    name = username = data.name
    disc = await User.y.get_free_discriminator(username)
    if disc is None:
        username = f"{username}{app_id}"
        disc = await User.y.get_free_discriminator(username)

    app = await Application.create(id=app_id, owner=user, name=name)
    bot_user = await User.create(id=app_id, email=f"bot_{app_id}", password="", is_bot=True)
    await UserData.create(id=app_id, user=bot_user, birth=datetime.now(), username=username, discriminator=disc)
    await UserSettings.create(id=app_id, user=bot_user, locale=(await user.settings).locale)
    await Bot.create(id=app_id, application=app, user=bot_user)
    return await app.ds_json()


@applications.get("/<int:application_id>")
async def get_application(application: Application = DepApplication):
    return await application.ds_json()


@applications.patch("/<int:application_id>", body_cls=UpdateApplication)
async def edit_application(data: UpdateApplication, application: Application = DepApplication):
    bot = await Bot.get(application=application).select_related("user")
    bot_data = await bot.user.userdata

    changes = data.model_dump(exclude_defaults=True)
    if "icon" in changes and changes["icon"] is not None:
        img = getImage(changes["icon"])
        image = await getStorage().setAppIcon(application.id, img)
        changes["icon"] = image
        if bot_data.avatar == application.icon:
            await bot_data.update(avatar=await getStorage().setUserAvatar(application.id, img))

    bot_changes = {}
    if bot is not None and "bot_public" in changes:
        bot_changes["bot_public"] = changes.pop("bot_public")
    if bot is not None and "bot_require_code_grant" in changes:
        bot_changes["bot_require_code_grant"] = changes.pop("bot_require_code_grant")

    if changes:
        await application.update(**changes)
    if bot_changes:
        await bot.update(**bot_changes)

    return await application.ds_json()


@applications.patch("/<int:application_id>/bot", body_cls=UpdateApplicationBot)
async def edit_application_bot(data: UpdateApplicationBot, application: Application = DepApplication):
    bot: Bot = await Bot.get(application=application).select_related("user")
    bot_data = await bot.user.userdata

    changes = data.model_dump(exclude_defaults=True)
    if "avatar" in changes and changes["avatar"] is not None:
        img = getImage(changes["avatar"])
        avatar_hash = await getStorage().setUserAvatar(application.id, img)
        changes["avatar"] = avatar_hash

    if changes:
        await bot_data.update(**changes)

    return await bot_data.ds_json_full()


@applications.post("/<int:application_id>/reset")
async def reset_application_secret(application: Application = DepApplication):
    new_secret = gen_secret_key()
    await application.update(secret=new_secret)

    return {"secret": new_secret}


@applications.post("/<int:application_id>/bot/reset")
async def reset_application_bot_token(application: Application = DepApplication):
    bot: Bot = await Bot.get(application=application).select_related("user")

    new_token = gen_token_secret()
    await bot.update(token_secret=new_token)

    return {"token": bot.token}


@applications.post("/<int:application_id>/delete")
async def delete_application(application: Application = DepApplication):
    bot = await Bot.get_or_none(application=application).select_related("user")
    await bot.user.update(deleted=True)
    data = await bot.user.data
    await data.update(discriminator=0, username=f"Deleted User {hex(bot.user.id)[2:]}", avatar=None,
                      avatar_decoration=None, public_flags=0)

    await application.update(owner=None, deleted=True)

    return "", 204


@applications.get("/<int:application_id>/commands", qs_cls=GetCommandsQS, allow_bots=True)
async def get_application_commands(query_args: GetCommandsQS, application: Application = DepApplication):
    commands: list[ApplicationCommand] = await (ApplicationCommand.filter(application=application)
                                                .select_related("application", "guild").all())
    return [command.ds_json(query_args.with_localizations) for command in commands]


@applications.post("/<int:application_id>/commands")
@applications.post("/<int:application_id>/guilds/<int:guild>/commands", body_cls=CreateCommand, allow_bots=True)
async def create_update_application_command(data: CreateCommand, application: Application = DepApplication,
                                            guild: Optional[Guild] = DepGuildO):
    command = await (ApplicationCommand.get_or_none(application=application, name=data.name, type=data.type,
                                                    guild=guild).select_related("application", "guild"))
    if command is not None:
        cmd = data.model_dump(exclude={"name", "type"}, exclude_defaults=True)
        if cmd.get("options") is None or command.type != ApplicationCommandType.CHAT_INPUT: cmd["options"] = []
        await command.update(**cmd, version=Snowflake.makeId(False))
    else:
        cmd = data.model_dump(exclude_defaults=True)
        if cmd.get("options") is None or data.type != ApplicationCommandType.CHAT_INPUT: cmd["options"] = []
        command = await ApplicationCommand.create(application=application, guild=guild, **cmd)
    return command.ds_json()


@applications.delete("/<int:application_id>/commands/<int:command_id>")
@applications.delete("/<int:application_id>/guilds/<int:guild>/commands/<int:command_id>", allow_bots=True)
async def delete_application_command(command_id: int, application: Application = DepApplication,
                                     guild: Optional[Guild] = DepGuildO):
    await ApplicationCommand.filter(application=application, id=command_id, guild=guild).delete()
    return "", 204
