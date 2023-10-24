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

from __future__ import annotations

import importlib
import warnings
from os import environ

from .classes.singleton import Singleton

_settings_modules = ["src.settings_prod", "src.settings"]
if (env_module := environ.get("SETTINGS", "src.settings")) and env_module not in _settings_modules:  # pragma: no cover
    _settings_modules.insert(0, env_module)

_settings = None
for _module in _settings_modules:
    try:
        _settings = importlib.import_module(_module)
        print(f"Settings module '{_module}' loaded.")
        break
    except ImportError as e:  # pragma: no cover
        print(f"Settings module '{_module}' not loaded: {e}.")

_variables = {}
if _settings:
    _variables = {k: v for k, v in vars(_settings).items() if not k.startswith("__")}

_defaults = {
    "DB_CONNECT_STRING": "sqlite:///db.sqlite",
    "MAIL_CONNECT_STRING": "smtp://127.0.0.1:10025?timeout=3",
    "KEY": "XUJHVU0nUn51TifQuy9H1j0gId0JqhQ+PUz16a2WOXE=",
    "PUBLIC_HOST": "127.0.0.1:8080",
    "GATEWAY_HOST": "127.0.0.1:8001",
    "CDN_HOST": "127.0.0.1:8003",
    "STORAGE": {
        "type": "local",
        "local": {"path": "files"},
        "s3": {"key_id": "", "access_key": "", "bucket": "", "endpoint": ""},
        "ftp": {"host": "", "port": 21, "user": "", "password": ""}
    },
    "TENOR_KEY": None,
    "GENERATE_TESTS": False,
    "MESSAGE_BROKER": {
        "type": "ws",
        "redis": {
            "url": "",
        },
        "rabbitmq": {
            "url": "",
        },
        "sqs": {
            "url": "",
        },
        "kafka": {
            "bootstrap_servers": [],
        },
        "nats": {
            "servers": [],
        },
        "ws": {
            "url": "ws://127.0.0.1:5055",
        },
    },
    "REDIS_URL": "",
    "GATEWAY_KEEP_ALIVE_DELAY": 45,
    "BCRYPT_ROUNDS": 15,
}


class _Config(Singleton):
    def update(self, variables: dict) -> _Config:
        self.__dict__.update(variables)
        return self


Config = (
    _Config().update(_defaults).update(_variables).update({"SETTINGS_MODULE": environ.get("SETTINGS", "src.settings")})
)

if Config.KEY == _defaults["KEY"]:  # pragma: no cover
    warnings.warn("It seems like KEY variable is set to default value. It should be changed in production!")
if Config.BCRYPT_ROUNDS < 12:
    warnings.warn("It is not recommended to set BCRYPT_ROUNDS to less than 12!")
if Config.BCRYPT_ROUNDS < 4 or Config.BCRYPT_ROUNDS > 31:
    Config.update({"BCRYPT_ROUNDS": 15})
    warnings.warn("BCRYPT_ROUNDS can not be lower than 4 or higher than 31! BCRYPT_ROUNDS set to 15")
