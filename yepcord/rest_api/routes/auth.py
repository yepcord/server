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

from json import loads as jloads

from quart import request
from tortoise.exceptions import DoesNotExist

from ..dependencies import DepSession, DepUser
from ..models.auth import Register, Login, MfaLogin, ViewBackupCodes, VerifyEmail
from ..utils import captcha
from ..y_blueprint import YBlueprint
from ...gateway.events import UserUpdateEvent
from ...yepcord.classes.other import EmailMsg, MFA, JWT
from ...yepcord.config import Config
from ...yepcord.ctx import getCore, getGw
from ...yepcord.errors import InvalidDataErr, Errors, PasswordDoesNotMatch, Invalid2FaCode, Invalid2FaAuthTicket, \
    InvalidToken
from ...yepcord.models import Session, User
from ...yepcord.utils import LOCALES, b64decode

# Base path is /api/vX/auth
auth = YBlueprint('auth', __name__)


@auth.post("/register", body_cls=Register)
@captcha
async def register(data: Register):
    locale = getCore().getLanguageCode(request.remote_addr, request.accept_languages.best_match(LOCALES, "en-US"))
    user = await User.y.register(data.username, data.email, data.password, data.date_of_birth, locale)
    session = await Session.Y.create(user)

    return {"token": session.token}


@auth.post("/login", body_cls=Login)
@captcha
async def login(data: Login):
    session = await User.y.login(data.login, data.password)
    user = session.user
    settings = await user.settings
    return {
        "token": session.token,
        "user_settings": {"locale": settings.locale, "theme": settings.theme},
        "user_id": str(user.id)
    }


@auth.post("/mfa/totp", body_cls=MfaLogin)
async def login_with_mfa(data: MfaLogin):
    if not (ticket := data.ticket):
        raise Invalid2FaAuthTicket
    if not (code := data.code):
        raise Invalid2FaCode
    if not (mfa := await MFA.get_from_ticket(ticket)):
        raise Invalid2FaAuthTicket
    code = code.replace("-", "").replace(" ", "")
    user = await User.y.get(mfa.uid)
    if code not in mfa.getCodes():
        if not (len(code) == 8 and await user.use_backup_code(code)):
            raise Invalid2FaCode
    sess = await Session.Y.create(user)
    sett = await user.settings
    return {
        "token": sess.token,
        "user_settings": {"locale": sett.locale, "theme": sett.theme},
        "user_id": str(user.id)
    }


@auth.post("/logout")
async def logout(session: Session = DepSession):
    await session.delete()
    return "", 204


@auth.post("/verify/view-backup-codes-challenge", body_cls=ViewBackupCodes)
async def request_challenge_to_view_mfa_codes(data: ViewBackupCodes, user: User = DepUser):
    if not (password := data.password):
        raise PasswordDoesNotMatch
    if not user.check_password(password):
        raise PasswordDoesNotMatch
    nonce = await user.generate_mfa_nonce()

    code = await MFA.nonce_to_code(nonce[0])
    await EmailMsg(
        user.email,
        f"Your one-time verification key is {code}",
        f"It looks like you're trying to view your account's backup codes.\n"
        f"This verification key expires in 10 minutes. This key is extremely sensitive, treat it like a "
        f"password and do not share it with anyone.\n"
        f"Enter it in the app to unlock your backup codes:\n{code}"
    ).send()

    return {"nonce": nonce[0], "regenerate_nonce": nonce[1]}


@auth.post("/verify/resend")
async def resend_verification_email(user: User = DepUser):
    if not user.verified:
        await user.send_verification_email()
    return "", 204


@auth.post("/verify", body_cls=VerifyEmail)
async def verify_email(data: VerifyEmail):
    if not data.token:
        raise InvalidToken

    if (data := JWT.decode(data.token, b64decode(Config.KEY))) is None:
        raise InvalidToken
    if (user := await User.get_or_none(id=data["id"], email=data["email"], verified=False)) is None:
        raise InvalidToken

    user.verified = True
    await user.save(update_fields=["verified"])

    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return {"token": (await Session.Y.create(user)).token, "user_id": str(user.id)}
