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
from datetime import datetime

from quart import Blueprint
from quart_schema import validate_request, validate_querystring

from ..models.applications import CreateApplication, UpdateApplication, UpdateApplicationBot, GetCommandsQS, \
    CreateCommand
from ..utils import getUser, multipleDecorators, getApplication, allowBots
from ...yepcord.ctx import getCore, getCDNStorage
from ...yepcord.models import User, UserData, UserSettings
from ...yepcord.models.applications import Application, Bot, gen_secret_key, gen_token_secret, ApplicationCommand
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage

# Base path is /api/vX/applications
applications = Blueprint('applications', __name__)


@applications.get("/", strict_slashes=False)
@getUser
async def get_applications(user: User):
    apps = await getCore().getApplications(user)
    return [await app.ds_json() for app in apps]


@applications.post("/", strict_slashes=False)
@multipleDecorators(validate_request(CreateApplication), getUser)
async def create_application(data: CreateApplication, user: User):
    app_id = Snowflake.makeId()
    name = username = data.name
    disc = await getCore().getRandomDiscriminator(username)
    if disc is None:
        username = f"{username}{app_id}"
        disc = await getCore().getRandomDiscriminator(username)

    app = await Application.objects.create(id=app_id, owner=user, name=name)
    bot_user = await User.objects.create(id=app_id, email=f"bot_{app_id}", password="", is_bot=True)
    await UserData.objects.create(id=app_id, user=bot_user, birth=datetime.now(), username=username, discriminator=disc)
    await UserSettings.objects.create(id=app_id, user=user, locale=(await user.settings).locale)
    await Bot.objects.create(id=app_id, application=app, user=bot_user)
    return await app.ds_json()


@applications.get("/<int:application_id>")
@multipleDecorators(getUser, getApplication)
async def get_application(user: User, application: Application):
    return await application.ds_json()


@applications.patch("/<int:application_id>")
@multipleDecorators(validate_request(UpdateApplication), getUser, getApplication)
async def edit_application(data: UpdateApplication, user: User, application: Application):
    bot = await Bot.objects.select_related("user").get(application=application)
    bot_data = await bot.user.userdata

    changes = data.dict(exclude_defaults=True)
    if "icon" in changes and changes["icon"] is not None:
        img = getImage(changes["icon"])
        image = await getCDNStorage().setAppIconFromBytesIO(application.id, img)
        changes["icon"] = image
        if bot_data.avatar == application.icon:
            await bot_data.update(avatar=await getCDNStorage().setAvatarFromBytesIO(application.id, img))

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


@applications.patch("/<int:application_id>/bot")
@multipleDecorators(validate_request(UpdateApplicationBot), getUser, getApplication)
async def edit_application_bot(data: UpdateApplicationBot, user: User, application: Application):
    bot: Bot = await Bot.objects.select_related("user").get(application=application)
    bot_data = await bot.user.userdata

    changes = data.dict(exclude_defaults=True)
    if "avatar" in changes and changes["avatar"] is not None:
        img = getImage(changes["avatar"])
        avatar_hash = await getCDNStorage().setAvatarFromBytesIO(application.id, img)
        changes["avatar"] = avatar_hash

    if changes:
        await bot_data.update(**changes)

    return await bot_data.ds_json_full()


@applications.post("/<int:application_id>/reset")
@multipleDecorators(getUser, getApplication)
async def reset_application_secret(user: User, application: Application):
    new_secret = gen_secret_key()
    await application.update(secret=new_secret)

    return {"secret": new_secret}


@applications.post("/<int:application_id>/bot/reset")
@multipleDecorators(getUser, getApplication)
async def reset_application_bot_token(user: User, application: Application):
    bot: Bot = await Bot.objects.select_related("user").get(application=application)

    new_token = gen_token_secret()
    await bot.update(token_secret=new_token)

    return {"token": bot.token}


@applications.post("/<int:application_id>/delete")
@multipleDecorators(getUser, getApplication)
async def delete_application(user: User, application: Application):
    bot = await Bot.objects.select_related("user").get_or_none(application=application)
    await bot.user.update(deleted=True)
    data = await bot.user.data
    await data.update(discriminator=0, username=f"Deleted User {hex(bot.user.id)[2:]}", avatar=None,
                      avatar_decoration=None, public_flags=0)

    await application.update(owner=None, deleted=True)

    return "", 204


@applications.get("/<int:application_id>/commands")
@multipleDecorators(validate_querystring(GetCommandsQS), allowBots, getUser, getApplication)
async def get_application_commands(query_args: GetCommandsQS, user: User, application: Application):
    commands: list[ApplicationCommand] = await ApplicationCommand.objects.filter(application=application).all()
    return [command.ds_json(query_args.with_localizations) for command in commands]


@applications.post("/<int:application_id>/commands")
@multipleDecorators(validate_request(CreateCommand), allowBots, getUser, getApplication)
async def create_update_application_command(data: CreateCommand, user: User, application: Application):
    command = await ApplicationCommand.objects.get_or_none(application=application, name=data.name, type=data.type)
    if command is not None:
        await command.update(**data.dict(exclude={"name", "type"}), version=Snowflake.makeId(False))
    else:
        command = await ApplicationCommand.objects.create(application=application, **data.dict())
    return command.ds_json()


@applications.delete("/<int:application_id>/commands/<int:command_id>")
@multipleDecorators(allowBots, getUser, getApplication)
async def delete_application_command(user: User, application: Application, command_id: int):
    await ApplicationCommand.objects.delete(application=application, id=command_id)
    return "", 204
