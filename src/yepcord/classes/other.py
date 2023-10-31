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

import re
from base64 import b32decode
from hashlib import sha512
from hmac import new
from json import loads, dumps
from struct import pack, unpack
from time import time
from typing import Union, Optional
from zlib import compressobj, Z_FULL_FLUSH

from mailers import Mailer
from mailers.exceptions import DeliveryError

from ..config import Config
from ..utils import b64decode, b64encode


class ZlibCompressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data) + self.cObj.flush(Z_FULL_FLUSH)


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


class JWT:
    """
    Json Web Token Hmac-sha512 implementation
    """

    @staticmethod
    def decode(token: str, secret: Union[str, bytes]) -> Optional[dict]:
        try:
            header, payload, signature = token.split(".")
            header_dict = loads(b64decode(header).decode("utf8"))
            assert header_dict.get("alg") == "HS512"
            assert header_dict.get("typ") == "JWT"
            assert (exp := header_dict.get("exp", 0)) > time() or exp == 0
            signature = b64decode(signature)
        except (IndexError, AssertionError, ValueError):
            return

        sig = f"{header}.{payload}".encode("utf8")
        sig = new(secret, sig, sha512).digest()
        if sig == signature:
            payload = b64decode(payload).decode("utf8")
            return loads(payload)

    @staticmethod
    def encode(payload: dict, secret: Union[str, bytes], expire_timestamp: Union[int, float] = 0) -> str:
        header = {
            "alg": "HS512",
            "typ": "JWT",
            "exp": int(expire_timestamp)
        }
        header = b64encode(dumps(header, separators=(',', ':')))
        payload = b64encode(dumps(payload, separators=(',', ':')))

        signature = f"{header}.{payload}".encode("utf8")
        signature = new(secret, signature, sha512).digest()
        signature = b64encode(signature)

        return f"{header}.{payload}.{signature}"


class BitFlags:
    def __init__(self, value: int, cls):
        self.cls = cls
        self.value = value
        self.parsedFlags = self.parseFlags()

    def parseFlags(self) -> list:
        flags = []
        value = self.value
        self.value = 0
        for val in self.cls.values().values():
            if (value & val) == val:
                flags.append(val)
                self.value |= val
        return flags

    def add(self, val: int):
        if val not in self.parsedFlags:
            self.value |= val
            self.parsedFlags.append(val)
        return self

    def remove(self, val: int):
        if val in self.parsedFlags:
            self.value &= ~val
            self.parsedFlags.remove(val)
        return self


class MFA:
    _re = re.compile(r'^[A-Z0-9]{16}$')

    def __init__(self, key: str, uid: int):
        self.key = str(key).upper()
        self.uid = self.id = uid

    def getCode(self, timestamp: Union[int, float] = None) -> str:
        if timestamp is None:
            timestamp = time()
        key = b32decode(self.key.upper() + '=' * ((8 - len(self.key)) % 8))
        counter = pack('>Q', int(timestamp / 30))
        mac = new(key, counter, "sha1").digest()
        offset = mac[-1] & 0x0f
        binary = unpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
        return str(binary)[-6:].zfill(6)

    def getCodes(self) -> tuple[str, str]:
        return self.getCode(time() - 5), self.getCode(time() + 1)

    @property
    def valid(self) -> bool:
        return bool(self._re.match(self.key))
