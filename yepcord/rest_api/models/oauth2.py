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

from typing import Optional, Literal

from pydantic import BaseModel, validator

from ...yepcord.errors import InvalidDataErr, Errors


class AppAuthorizeGetQs(BaseModel):
    client_id: Optional[int] = None
    scope: Optional[str] = None

    def __init__(self, *args, **kwargs):
        if "client_id" not in kwargs or not kwargs.get("client_id", "").strip():
            raise InvalidDataErr(400, Errors.make(50035, {"client_id": {
                "code": "BASE_TYPE_REQUIRED", "message": "This field is required"
            }}))
        super().__init__(*args, **kwargs)


class AppAuthorizePostQs(BaseModel):
    client_id: Optional[int] = None
    scope: Optional[str] = None
    response_type: Optional[Literal["code"]] = None
    redirect_uri: Optional[str] = None


class AppAuthorizePost(BaseModel):
    authorize: bool
    permissions: Optional[int] = None
    guild_id: Optional[int] = None


class ExchangeCode(BaseModel):
    grant_type: Literal["authorization_code", "refresh_token", "client_credentials"]
    code: Optional[str] = None
    scope: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
