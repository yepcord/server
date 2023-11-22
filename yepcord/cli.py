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
import asyncio
import os.path
from os import environ

import click
from tortoise import Tortoise


@click.group()
def cli():
    ...


main = cli


@cli.command()
@click.option("--config", "-c", help="Config path.", default=None)
@click.option("--location", "-l", help="Migrations directory. Config value will be used if not specified",
              default=None)
def migrate(config: str, location: str = None) -> None:
    if config is not None:
        environ["YEPCORD_CONFIG"] = config

    from pathlib import Path
    from aerich import Command
    from .yepcord.config import Config

    async def _migrate():
        command = Command({
            "connections": {"default": Config.DB_CONNECT_STRING},
            "apps": {"models": {"models": ["yepcord.yepcord.models", "aerich.models"], "default_connection": "default"}},
        }, location=location or Config.MIGRATIONS_DIR)
        await command.init()
        if Path(command.location).exists():
            await command.migrate()
            await command.upgrade(True)
        else:
            await command.init_db(True)
        await Tortoise.close_connections()

    asyncio.run(_migrate())


@cli.command(name="run_all")
@click.option("--config", "-c", help="Config path.", default=None)
@click.option("--host", "-h", help="Bind socket to this host.", default="0.0.0.0")
@click.option("--port", "-p", help="Bind socket to this port.", default=8000)
@click.option("--reload", help="Enable reloading when changing code files.", is_flag=True)
@click.option("--ssl", help="Enable https. Cert file should be at ssl/cert.pem, key file at ssl/key.pem",
              is_flag=True)
def run_all(config: str, host: str, port: int, reload: bool, ssl: bool) -> None:
    import uvicorn

    if config is not None:
        environ["YEPCORD_CONFIG"] = config

    kwargs = {
        "forwarded_allow_ips": "'*'",
        "host": host,
        "port": port,
    }

    if reload:
        kwargs["reload"] = True
        kwargs["reload_dirs"] = ["src"]
    if ssl:
        kwargs["ssl_certfile"] = "ssl/cert.pem"
        kwargs["ssl_keyfile"] = "ssl/key.pem"

    uvicorn.run("yepcord.asgi:app", **kwargs)


@cli.command(name="download-ipdb")
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


if __name__ == "__main__":
    cli()
