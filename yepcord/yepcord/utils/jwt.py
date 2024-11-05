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

from __future__ import annotations

import hmac
import json
from hashlib import sha512
from time import time
from typing import Union, Optional

from ..utils import b64decode, b64encode


class JWT:
    """
    Json Web Token Hmac-sha512 implementation
    """

    @staticmethod
    def decode(token: str, secret: Union[str, bytes]) -> Optional[dict]:
        try:
            header, payload, signature = token.split(".")
            header_dict = json.loads(b64decode(header).decode("utf8"))
            assert header_dict.get("alg") == "HS512"
            assert header_dict.get("typ") == "JWT"
            assert (exp := header_dict.get("exp", 0)) > time() or exp == 0
            signature = b64decode(signature)
        except (IndexError, AssertionError, ValueError):
            return

        sig = f"{header}.{payload}".encode("utf8")
        sig = hmac.new(secret, sig, sha512).digest()
        if sig == signature:
            payload = b64decode(payload).decode("utf8")
            return json.loads(payload)

    @staticmethod
    def encode(
            payload: dict, secret: Union[str, bytes], expires_at: Optional[Union[int, float]] = None,
            expires_after: Optional[int] = None
    ) -> str:
        if expires_after is not None:
            expires_at = int(time() + expires_after)
        if expires_at is None:
            expires_at = 0

        header = {
            "alg": "HS512",
            "typ": "JWT",
            "exp": int(expires_at)
        }
        header = b64encode(json.dumps(header, separators=(',', ':')))
        payload = b64encode(json.dumps(payload, separators=(',', ':')))

        signature = f"{header}.{payload}".encode("utf8")
        signature = hmac.new(secret, signature, sha512).digest()
        signature = b64encode(signature)

        return f"{header}.{payload}.{signature}"
