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

import warnings
from os import environ
from os.path import exists, isdir
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator

from .classes.singleton import Singleton


def _load_config() -> dict:
    if not (config_path := environ.get("YEPCORD_CONFIG", None)):  # pragma: no cover
        return {}

    if not exists(config_path) or isdir(config_path):  # pragma: no cover
        return {}

    with open(config_path, encoding="utf8") as f:
        config_code = f.read()

    config = {}
    exec(config_code, globals(), config)

    variables = {}
    if config:
        variables = {k: v for k, v in config.items() if not k.startswith("__")}

    return variables


class ConfigStoragesLocal(BaseModel):
    path: str = "files"


class ConfigStoragesS3(BaseModel):
    key_id: str = ""
    access_key: str = ""
    bucket: str = ""
    endpoint: str = ""


class ConfigStoragesFtp(BaseModel):
    host: str = ""
    port: int = 21
    user: str = ""
    password: str = ""


class ConfigStorage(BaseModel):
    type: str = "local"
    local: ConfigStoragesLocal = Field(default_factory=ConfigStoragesLocal)
    s3: ConfigStoragesS3 = Field(default_factory=ConfigStoragesS3)
    ftp: ConfigStoragesFtp = Field(default_factory=ConfigStoragesFtp)


class ConfigMessageBrokerUrl(BaseModel):
    url: str = ""


class ConfigMessageBrokerKafka(BaseModel):
    bootstrap_servers: list = Field(default_factory=list)


class ConfigMessageBrokerNats(BaseModel):
    servers: list = Field(default_factory=list)


class ConfigMessageBrokers(BaseModel):
    type: str = "ws"
    redis: ConfigMessageBrokerUrl = Field(default_factory=ConfigMessageBrokerUrl)
    rabbitmq: ConfigMessageBrokerUrl = Field(default_factory=ConfigMessageBrokerUrl)
    sqs: ConfigMessageBrokerUrl = Field(default_factory=ConfigMessageBrokerUrl)
    kafka: ConfigMessageBrokerKafka = Field(default_factory=ConfigMessageBrokerKafka)
    nats: ConfigMessageBrokerNats = Field(default_factory=ConfigMessageBrokerNats)
    ws: ConfigMessageBrokerUrl = Field(default_factory=lambda: ConfigMessageBrokerUrl(url="ws://127.0.0.1:5055"))


class ConfigCaptchaService(BaseModel):
    sitekey: str = ""
    secret: str = ""


class ConfigCaptcha(BaseModel):
    enabled: Literal["hcaptcha", "recaptcha", None] = None
    hcaptcha: ConfigCaptchaService = Field(default_factory=ConfigCaptchaService)
    recaptcha: ConfigCaptchaService = Field(default_factory=ConfigCaptchaService)


class ConfigModel(BaseModel):
    DB_CONNECT_STRING: str = "sqlite:///db.sqlite"
    MAIL_CONNECT_STRING: str = "smtp://127.0.0.1:10025?timeout=3"
    MIGRATIONS_DIR: str = "./migrations"
    KEY: str = "XUJHVU0nUn51TifQuy9H1j0gId0JqhQ+PUz16a2WOXE="
    PUBLIC_HOST: str = "127.0.0.1:8080"
    GATEWAY_HOST: str = "127.0.0.1:8080/gateway"
    CDN_HOST: str = "127.0.0.1:8080/media"
    STORAGE: ConfigStorage = Field(default_factory=ConfigStorage)
    TENOR_KEY: Optional[str] = None
    MESSAGE_BROKER: ConfigMessageBrokers = Field(default_factory=ConfigMessageBrokers)
    REDIS_URL: Optional[str] = None
    GATEWAY_KEEP_ALIVE_DELAY: int = 45
    BCRYPT_ROUNDS: int = 15
    CAPTCHA: ConfigCaptcha = Field(default_factory=ConfigCaptcha)

    @field_validator("KEY")
    def validate_key(cls, value: str) -> str:
        if value == cls.model_fields["KEY"].default:
            warnings.warn("It seems like KEY variable is set to default value. It must be changed in production!")

        return value

    @field_validator("GATEWAY_KEEP_ALIVE_DELAY")
    def validate_gw_keep_alive(cls, value: int) -> int:
        if value < 5 or value > 150:
            warnings.warn("It is not recommended to set GATEWAY_KEEP_ALIVE_DELAY to less than 5 or greater than 150!")
        if value < 5:
            value = 5
        if value > 150:
            value = 150

        return value

    @field_validator("BCRYPT_ROUNDS")
    def validate_bcrypt_rounds(cls, value: int) -> int:
        if value < 12:
            warnings.warn("It is not recommended to set BCRYPT_ROUNDS to less than 12!")
        if value < 4 or value > 31:
            value = 15
            warnings.warn("BCRYPT_ROUNDS can not be lower than 4 or higher than 31! BCRYPT_ROUNDS set to 15")

        return value

    class Config:
        validate_default = True


class _Config(Singleton):
    def update(self, variables: dict) -> _Config:
        self.__dict__.update(variables)
        return self


Config = _Config().update(ConfigModel(**_load_config()).model_dump())
