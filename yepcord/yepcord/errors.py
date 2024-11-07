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

from pydantic import ValidationError


class YDataError(Exception):
    pass


class EmbedErr(YDataError):
    def __init__(self, error):
        super().__init__()
        self.error = error


class InvalidDataErr(YDataError):
    def __init__(self, code, error):
        super().__init__()
        self.code = code
        self.error = error


class MfaRequiredErr(YDataError):
    def __init__(self, uid, sid, sig):
        super().__init__()
        self.uid = uid
        self.sid = sid
        self.sig = sig


class _Errors:
    _instance = None
    err_0 = "General error"

    err_10002 = "Unknown Application"
    err_10003 = "Unknown Channel"
    err_10004 = "Unknown Guild"
    err_10006 = "Unknown Invite"
    err_10008 = "Unknown Message"
    err_10011 = "Unknown Role"
    err_10012 = "Unknown Token"
    err_10013 = "Unknown User"
    err_10014 = "Unknown Emoji"
    err_10015 = "Unknown Webhook"
    err_10017 = "Unknown Connection"
    err_10057 = "Unknown Guild template"
    err_10060 = "Unknown Sticker"
    err_10062 = "Unknown Interaction"
    err_10070 = "Unknown Guild Scheduled Event"
    err_10102 = "Unknown poll"

    err_30003 = "Maximum number of pins reached (50)"
    err_30008 = "Maximum number of emojis reached"
    err_30031 = "A server can only have a single template."

    err_40007 = "The user is banned from this guild."
    err_40011 = "You must transfer ownership of any owned guilds before deleting your account"
    err_40060 = "Interaction has already been acknowledged"

    err_50001 = "Missing Access"
    err_50003 = "Cannot execute action on a DM channel"
    err_50005 = "Cannot edit a message authored by another user"
    err_50006 = "Cannot send an empty message"
    err_50007 = "Cannot send messages to this user"
    err_50013 = "Missing Permissions"
    err_50018 = "Password does not match"
    err_50028 = "Invalid Role"
    err_50033 = "Invalid Recipient(s)"
    err_50035 = "Invalid Form Body"
    err_50045 = "File uploaded exceeds the maximum size"
    err_50046 = "Invalid Asset"
    err_50055 = "Invalid Guild"
    err_50104 = "Malformed user settings payload"

    err_60001 = "This account is already enrolled in two-factor authentication"
    err_60002 = "This account is not enrolled in two-factor authentication"
    err_60005 = "Invalid two-factor secret"
    err_60006 = "Invalid two-factor auth ticket"
    err_60008 = "Invalid two-factor code"
    err_60011 = "Invalid key"

    err_80000 = "Incoming friend requests disabled."
    err_80004 = "No users with DiscordTag exist"
    err_80007 = "You are already friends with that user."

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(_Errors, cls).__new__(cls)
        return cls._instance

    def __call__(self, code):
        return getattr(self, f"err_{code}", None)

    def __getitem__(self, code):
        return self(code)

    def make(self, code: int, errors: dict = None, message: str = None) -> dict:
        if errors is None:
            return {"code": code, "message": self(code) or message}
        err = {"code": code, "errors": {}, "message": self(code) or message}
        for path, error in errors.items():
            e = err["errors"]
            for p in path.split("."):
                e[p] = {}
                e = e[p]
            e["_errors"] = [error]
        return err

    @staticmethod
    def from_pydantic(exc: ValidationError):
        errors = {}
        for error in exc.errors():
            loc = error["loc"][0]
            if loc not in errors:
                errors[loc] = {"_errors": []}
            if error["type"] == "value_error.missing":
                errors[loc]["_errors"].append({"code": "BASE_TYPE_REQUIRED", "message": "Required field."})
            elif error["type"] in ("type_error.integer", "type_error.float"):
                message = "Value is not int." if error["type"] == "type_error.integer" else "Value is not float."
                errors[loc]["_errors"].append({"code": "NUMBER_TYPE_COERCE", "message": message})
            else:
                errors[loc]["_errors"].append(
                    {"code": "ERROR_TYPE_UNKNOWN", "message": "Something wrong with this value.",
                     "_error_type": error["type"]})
        return {"code": 50035, "errors": errors, "message": "Invalid Form Body"}


Errors = _Errors()


class UnknownX(InvalidDataErr):
    def __init__(self, error_code: int):
        super().__init__(404, Errors.make(error_code))


class BadRequest(InvalidDataErr):
    def __init__(self, error_code: int):
        super().__init__(400, Errors.make(error_code))


class Forbidden(InvalidDataErr):
    def __init__(self, error_code: int):
        super().__init__(403, Errors.make(error_code))


UnknownApplication = UnknownX(10002)
UnknownChannel = UnknownX(10003)
UnknownGuild = UnknownX(10004)
UnknownInvite = UnknownX(10006)
UnknownMessage = UnknownX(10008)
UnknownRole = UnknownX(10011)
UnknownToken = UnknownX(10012)
UnknownUser = UnknownX(10013)
UnknownEmoji = BadRequest(10014)
UnknownWebhook = UnknownX(10015)
UnknownConnection = UnknownX(10017)
UnknownGuildTemplate = UnknownX(10057)
UnknownSticker = UnknownX(10060)
UnknownInteraction = UnknownX(10062)
UnknownGuildEvent = UnknownX(10070)
UnknowPoll = UnknownX(10102)

MaxPinsReached = BadRequest(30003)
MaxEmojisReached = BadRequest(30008)
CanHaveOneTemplate = BadRequest(30031)

UserBanned = Forbidden(40007)
MustTransferGuildsBeforeDelete = BadRequest(40011)
InteractionAlreadyAck = BadRequest(40060)

MissingAccess = Forbidden(50001)
CannotExecuteOnDM = Forbidden(50003)
CannotEditAnotherUserMessage = Forbidden(50005)
CannotSendEmptyMessage = BadRequest(50006)
CannotSendToThisUser = Forbidden(50007)
MissingPermissions = Forbidden(50013)
PasswordDoesNotMatch = BadRequest(50018)
InvalidRole = BadRequest(50028)
InvalidRecipient = BadRequest(50033)
InvalidFormBody = BadRequest(50035)
FileExceedsMaxSize = BadRequest(50045)
InvalidAsset = BadRequest(50046)
InvalidGuild = BadRequest(50055)
MalformedUserSettings = BadRequest(50104)

Already2Fa = UnknownX(60001)
NotYet2Fa = UnknownX(60002)
Invalid2FaSecret = BadRequest(60005)
Invalid2FaAuthTicket = BadRequest(60006)
Invalid2FaCode = BadRequest(60008)
InvalidKey = BadRequest(60011)

FriendRequestsDisabled = Forbidden(80000)
UnknownDiscordTag = BadRequest(80004)
AlreadyFriends = BadRequest(80007)

Unauthorized = InvalidDataErr(401, Errors.make(0, message="401: Unauthorized"))
Error0 = InvalidDataErr(400, Errors.make(0))

InvalidToken = InvalidDataErr(400, Errors.make(50035, {"token": {
    "code": "TOKEN_INVALID",
    "message": "Invalid token."
}}))
