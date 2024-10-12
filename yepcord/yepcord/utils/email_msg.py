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

from mailers import Mailer
from mailers.exceptions import DeliveryError

from ..config import Config


class EmailMsg:
    def __init__(self, to: str, subject: str, text: str):
        self.to = to
        self.subject = subject
        self.text = text

    async def send(self):
        mailer = Mailer(Config.MAIL_CONNECT_STRING)
        try:
            await mailer.send_message(self.to, self.subject, self.text, from_address="no-reply@yepcord.ml")
        except DeliveryError:
            pass

    @classmethod
    async def send_verification(cls, email: str, token: str) -> None:
        await cls(email, "Confirm your e-mail in YEPCord", (
            f"Thank you for signing up for a YEPCord account!\n"
            f"First you need to make sure that you are you!\n"
            f"Click to verify your email address:\n"
            f"https://{Config.PUBLIC_HOST}/verify#token={token}"
        )).send()

    @classmethod
    async def send_mfa_code(cls, email: str, code: str) -> None:
        await cls(email, f"Your one-time verification key is {code}", (
            f"It looks like you're trying to view your account's backup codes.\n"
            f"This verification key expires in 10 minutes. This key is extremely sensitive, treat it like a "
            f"password and do not share it with anyone.\n"
            f"Enter it in the app to unlock your backup codes:\n{code}"
        )).send()
