from quart import Blueprint, request
from json import loads as jloads

from ..utils import usingDB, getSession, getUser, multipleDecorators
from ...yepcord.classes.user import Session, User
from ...yepcord.ctx import getCore
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.geoip import getLanguageCode
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import c_json, LOCALES, b64decode

# Base path is /api/vX/auth
auth = Blueprint('auth', __name__)


@auth.post("/register")
@usingDB
async def register():
    data = await request.get_json()
    loc = getLanguageCode(request.remote_addr, request.accept_languages.best_match(LOCALES, "en-US"))
    sess = await getCore().register(Snowflake.makeId(), data["username"], data.get("email"), data["password"], data["date_of_birth"], loc)
    return c_json({"token": sess.token})


@auth.post("/login")
@usingDB
async def login():
    data = await request.get_json()
    sess = await getCore().login(data["login"], data["password"])
    user = await getCore().getUser(sess.uid)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@auth.post("/mfa/totp")
@usingDB
async def login_with_mfa(): # TODO: test
    data = await request.get_json()
    if not (ticket := data.get("ticket")):
        raise InvalidDataErr(400, Errors.make(60006))
    if not (code := data.get("code")):
        raise InvalidDataErr(400, Errors.make(60008))
    if not (mfa := await getCore().getMfaFromTicket(ticket)):
        raise InvalidDataErr(400, Errors.make(60006))
    code = code.replace("-", "").replace(" ", "")
    if mfa.getCode() != code:
        if not (len(code) == 8 and await getCore().useMfaCode(mfa.uid, code)):
            raise InvalidDataErr(400, Errors.make(60008))
    sess = await getCore().createSession(mfa.uid)
    user = await getCore().getUser(sess.uid)
    sett = await user.settings
    return c_json({"token": sess.token, "user_settings": {"locale": sett.locale, "theme": sett.theme}, "user_id": str(user.id)})


@auth.post("/logout")
@multipleDecorators(usingDB, getSession)
async def logout(session: Session):
    await getCore().logoutUser(session)
    return "", 204


@auth.post("/verify/view-backup-codes-challenge")
@multipleDecorators(usingDB, getUser)
async def request_challenge_to_view_mfa_codes(user: User):
    data = await request.get_json()
    if not (password := data.get("password")):
        raise InvalidDataErr(400, Errors.make(50018))
    if not await getCore().checkUserPassword(user, password):
        raise InvalidDataErr(400, Errors.make(50018))
    nonce = await getCore().generateUserMfaNonce(user)
    await getCore().sendMfaChallengeEmail(user, nonce[0])
    return c_json({"nonce": nonce[0], "regenerate_nonce": nonce[1]})


@auth.post("/verify/resend")
@multipleDecorators(usingDB, getUser)
async def resend_verification_email(user: User):
    if not user.verified:
        await getCore().sendVerificationEmail(user)
    return "", 204


@auth.post("/verify")
@usingDB
async def verify_email():
    data = await request.get_json()
    if not data.get("token"):
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    try:
        email = jloads(b64decode(data["token"].split(".")[0]).decode("utf8"))["email"]
    except:
        raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
    user = await getCore().getUserByEmail(email)
    await getCore().verifyEmail(user, data["token"])
    await getCore().sendUserUpdateEvent(user.id)
    return c_json({"token": (await getCore().createSession(user.id)).token, "user_id": str(user.id)})
