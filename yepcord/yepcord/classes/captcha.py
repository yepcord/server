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

from typing import Type

from aiohttp import ClientSession, FormData

from ..config import Config


class Captcha:
    NAME = ""
    VERIFY_ENDPOINT = ""

    @classmethod
    async def verify(cls, captcha_key: str) -> tuple[bool, list[str]]:
        captcha = Config.CAPTCHA[cls.NAME]
        async with ClientSession() as sess:
            form = FormData()
            form.add_field("secret", captcha["secret"])
            form.add_field("response", captcha_key)
            form.add_field("sitekey", captcha["sitekey"])

            resp = await sess.post(cls.VERIFY_ENDPOINT, data=form)
            resp = await resp.json()

            return resp["success"], resp.get("error_codes", [])

    @staticmethod
    def get(service: str) -> Type[Captcha]:
        if service == "hcaptcha":
            return HCaptcha
        if service == "recaptcha":
            return ReCaptcha
        return IncorrectCaptcha

    @classmethod
    def error_response(cls, errors: list[str]) -> tuple[dict, int]:
        sitekey = Config.CAPTCHA[cls.NAME]["sitekey"]
        return {"captcha_key": errors, "captcha_sitekey": sitekey, "captcha_service": cls.NAME}, 400


class HCaptcha(Captcha):
    NAME = "hcaptcha"
    VERIFY_ENDPOINT = "https://hcaptcha.com/siteverify"


class ReCaptcha(Captcha):
    NAME = "recaptcha"
    VERIFY_ENDPOINT = "https://www.google.com/recaptcha/api/siteverify"


class IncorrectCaptcha(Captcha):
    NAME = "incorrect"
    VERIFY_ENDPOINT = "https://0.0.0.0/"

    @classmethod
    async def verify(cls, captcha_key: str) -> tuple[bool, list[str]]:
        return False, ["improperly-configured"]

    @classmethod
    def error_response(cls, errors: list[str]) -> tuple[dict, int]:
        return {"captcha_key": errors, "captcha_sitekey": "incorrect", "captcha_service": cls.NAME}, 400
