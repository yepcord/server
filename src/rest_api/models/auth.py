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

from pydantic import BaseModel, validator

from src.yepcord.errors import InvalidDataErr, Errors


class Register(BaseModel):
    username: str
    email: str
    password: str
    date_of_birth: str = "2000-01-01"

    @validator("email", "password", "username")
    def validate_name(cls, value: str, values, field):
        if not value:
            raise InvalidDataErr(400, Errors.make(50035, {field.name: {
                "_errors": [{"code": "BASE_TYPE_REQUIRED", "message": "Required field."}]}}))
        return value


class Login(BaseModel):
    login: str
    password: str


class MfaLogin(BaseModel):
    ticket: str
    code: str


class ViewBackupCodes(BaseModel):
    password: str


class VerifyEmail(BaseModel):
    token: str
