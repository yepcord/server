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

import os.path
from os import environ
import click

from quart import Quart

app = Quart("YEPCord server")


# noinspection PyTypeChecker
def create_yepcord():
    from tortoise.contrib.quart import register_tortoise
    from quart_schema import RequestSchemaValidationError, QuartSchema
    import src.rest_api.main as rest_api
    import src.gateway.main as gateway
    import src.cdn.main as cdn
    import src.remote_auth.main as remote_auth
    from src.rest_api.routes import auth
    from src.rest_api.routes import users_me
    from src.rest_api.routes import users
    from src.rest_api.routes import channels
    from src.rest_api.routes import invites
    from src.rest_api.routes import guilds
    from src.rest_api.routes import webhooks
    from src.rest_api.routes import gifs
    from src.rest_api.routes import hypesquad
    from src.rest_api.routes import other
    from src.yepcord.errors import YDataError
    from src.yepcord.config import Config

    app.gifs = rest_api.app.gifs
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
    QuartSchema(app)

    app.before_serving(rest_api.before_serving)
    app.before_serving(gateway.before_serving)
    app.before_serving(remote_auth.before_serving)

    app.after_serving(rest_api.after_serving)
    app.after_serving(gateway.after_serving)
    app.after_serving(remote_auth.after_serving)

    app.after_request(rest_api.set_cors_headers)

    app.errorhandler(YDataError)(rest_api.ydataerror_handler)
    app.errorhandler(RequestSchemaValidationError)(rest_api.handle_validation_error)

    app.register_blueprint(auth.auth, url_prefix="/api/v9/auth")
    app.register_blueprint(users_me.users_me, url_prefix="/api/v9/users/@me")
    app.register_blueprint(users.users, url_prefix="/api/v9/users")
    app.register_blueprint(channels.channels, url_prefix="/api/v9/channels")
    app.register_blueprint(invites.invites, url_prefix="/api/v9/invites")
    app.register_blueprint(guilds.guilds, url_prefix="/api/v9/guilds")
    app.register_blueprint(webhooks.webhooks, url_prefix="/api/v9/webhooks")
    app.register_blueprint(webhooks.webhooks, url_prefix="/api/webhooks")
    app.register_blueprint(gifs.gifs, url_prefix="/api/v9/gifs")
    app.register_blueprint(hypesquad.hypesquad, url_prefix="/api/v9/hypesquad")
    app.register_blueprint(other.other, url_prefix="/")

    app.route("/api/v9/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])(rest_api.other_api_endpoints)

    app.websocket("/gateway", strict_slashes=False)(gateway.ws_gateway)
    remote_auth.ws_gateway.__name__ = "ws_ra_gateway"
    app.websocket("/remote-auth", strict_slashes=False)(remote_auth.ws_gateway)

    app.get("/media/avatars/<int:user_id>/<string:file_hash>.<string:format_>")(cdn.get_avatar)
    app.get("/media/banners/<int:user_id>/<string:file_hash>.<string:format_>")(cdn.get_banner)
    app.get("/media/splashes/<int:guild_id>/<string:file_hash>.<string:format_>")(cdn.get_splash)
    app.get("/media/channel-icons/<int:channel_id>/<string:file_hash>.<string:format_>")(cdn.get_channel_icon)
    app.get("/media/icons/<int:guild_id>/<string:file_hash>.<string:format_>")(cdn.get_guild_icon)
    app.get("/media/role-icons/<int:role_id>/<string:file_hash>.<string:format_>")(cdn.get_role_icon)
    app.get("/media/emojis/<int:emoji_id>.<string:format_>")(cdn.get_emoji)
    app.get("/media/guilds/<int:guild_id>/users/<int:member_id>/avatars/<string:file_hash>.<string:format_>")(
        cdn.get_guild_avatar
    )
    app.get("/media/stickers/<int:sticker_id>.<string:format_>")(cdn.get_sticker)
    app.get("/media/guild-events/<int:event_id>/<string:file_hash>")(cdn.get_guild_event_image)
    app.get("/media/attachments/<int:channel_id>/<int:attachment_id>/<string:name>")(cdn.get_attachment)

    register_tortoise(
        app,
        db_url=Config.DB_CONNECT_STRING,
        modules={"models": ["src.yepcord.models"]},
        generate_schemas=False,
    )

    return app


@app.cli.command()
@click.option("--settings", "-s", help="Settings module.", default="src.settings")
def migrate(settings: str) -> None:
    import alembic.config

    environ["SETTINGS"] = settings
    alembic.config.main(argv=["--raiseerr", "revision", "--autogenerate"])
    alembic.config.main(argv=["--raiseerr", "upgrade", "head"])
    print("Migration complete!")


@app.cli.command(name="run_all")
@click.option("--settings", "-s", help="Settings module.", default="src.settings")
@click.option("--host", "-h", help="Bind socket to this host.", default="0.0.0.0")
@click.option("--port", "-p", help="Bind socket to this port.", default=8000)
@click.option("--reload", help="Enable reloading when changing code files.", is_flag=True)
@click.option("--ssl", help="Enable https. Cert file should be at ssl/cert.pem, key file at ssl/key.pem",
              is_flag=True)
def run_all(settings: str, host: str, port: int, reload: bool, ssl: bool) -> None:
    import uvicorn

    environ["SETTINGS"] = settings

    kwargs = {
        "forwarded_allow_ips": "'*'",
        "host": host,
        "port": port,
        "factory": True,
    }

    if reload:
        kwargs["reload"] = True
        kwargs["reload_dirs"] = ["src"]
    if ssl:
        kwargs["ssl_certfile"] = "ssl/cert.pem"
        kwargs["ssl_keyfile"] = "ssl/key.pem"

    uvicorn.run("app:create_yepcord", **kwargs)


@app.cli.command(name="download_ipdb")
@click.option("--url", "-u", help="Url of mmdb file.",
              default="https://github.com/geoacumen/geoacumen-country/raw/master/Geoacumen-Country.mmdb")
@click.option("--replace", is_flag=True, help="Replace existing mmdb file.")
def download_ipdb(url: str, replace: bool) -> None:
    from wget import download

    if os.path.exists("other/ip_database.mmdb.old"):
        os.remove("other/ip_database.mmdb.old")

    if os.path.exists("other/ip_database.mmdb") and replace:
        os.rename("other/ip_database.mmdb", "other/ip_database.mmdb.old")
    elif os.path.exists("other/ip_database.mmdb") and not replace:
        return

    try:
        download(url, out="other/ip_database.mmdb")
    except Exception as e:
        print(f"Failed to download ip database: {e.__class__.__name__}: {e}.")
        if os.path.exists("other/ip_database.mmdb"):
            os.remove("other/ip_database.mmdb")
        os.rename("other/ip_database.mmdb.old", "other/ip_database.mmdb")
