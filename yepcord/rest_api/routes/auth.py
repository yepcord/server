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

from json import loads as jloads

from quart import Blueprint, request
from quart_schema import validate_request

from ..models.auth import Register, Login, MfaLogin, ViewBackupCodes, VerifyEmail
from ..utils import getSession, getUser, multipleDecorators, captcha
from ...gateway.events import UserUpdateEvent
from ...yepcord.ctx import getCore, getGw
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import Session, User
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import LOCALES, b64decode

# Base path is /api/vX/auth
auth = Blueprint('auth', __name__)


@auth.post("/register")
@multipleDecorators(captcha, validate_request(Register))
async def register(data: Register):
    loc = getCore().getLanguageCode(request.remote_addr, request.accept_languages.best_match(LOCALES, "en-US"))
    sess = await getCore().register(Snowflake.makeId(), data.username, data.email, data.password, data.date_of_birth,
                                    loc)
    return {"token": sess.token}


@auth.post("/login")
@multipleDecorators(captcha, validate_request(Login))
async def login(data: Login):
    sess = await getCore().login(data.login, data.password)
    user = sess.user
    sett = await user.settings
    return {
        "token": sess.token,
        "user_settings": {"locale": sett.locale, "theme": sett.theme},
        "user_id": str(user.id)
    }


@auth.post("/mfa/totp")
@validate_request(MfaLogin)
async def login_with_mfa(data: MfaLogin):
    if not (ticket := data.ticket):
        raise InvalidDataErr(400, Errors.make(60006))
    if not (code := data.code):
        raise InvalidDataErr(400, Errors.make(60008))
    if not (mfa := await getCore().getMfaFromTicket(ticket)):
        raise InvalidDataErr(400, Errors.make(60006))
    code = code.replace("-", "").replace(" ", "")
    user = await User.y.get(mfa.uid)
    if code not in mfa.getCodes():
        if not (len(code) == 8 and await getCore().useMfaCode(user, code)):
            raise InvalidDataErr(400, Errors.make(60008))
    sess = await getCore().createSession(user.id)
    sett = await user.settings
    return {
        "token": sess.token,
        "user_settings": {"locale": sett.locale, "theme": sett.theme},
        "user_id": str(user.id)
    }


@auth.post("/logout")
@getSession
async def logout(session: Session):
    await session.delete()
    return "", 204


@auth.post("/verify/view-backup-codes-challenge")
@multipleDecorators(validate_request(ViewBackupCodes), getUser)
async def request_challenge_to_view_mfa_codes(data: ViewBackupCodes, user: User):
    if not (password := data.password):
        raise InvalidDataErr(400, Errors.make(50018))
    if not await getCore().checkUserPassword(user, password):
        raise InvalidDataErr(400, Errors.make(50018))
    nonce = await getCore().generateUserMfaNonce(user)
    await getCore().sendMfaChallengeEmail(user, nonce[0])
    return {"nonce": nonce[0], "regenerate_nonce": nonce[1]}


@auth.post("/verify/resend")
@getUser
async def resend_verification_email(user: User):
    if not user.verified:
        await getCore().sendVerificationEmail(user)
    return "", 204


@auth.post("/verify")
@validate_request(VerifyEmail)
async def verify_email(data: VerifyEmail):
    if not data.token:
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    # noinspection PyPep8
    try:
        email = jloads(b64decode(data.token.split(".")[0]).decode("utf8"))["email"]
    except:
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    user = await getCore().getUserByEmail(email)
    await getCore().verifyEmail(user, data.token)
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return {"token": (await getCore().createSession(user.id)).token, "user_id": str(user.id)}
