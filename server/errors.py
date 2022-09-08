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
    err_10003 = "Unknown Channel"
    err_10008 = "Unknown Message"
    err_10013 = "Unknown User"

    err_50001 = "Missing Access"
    err_50003 = "Cannot execute action on a DM channel"
    err_50005 = "Cannot edit a message authored by another user"
    err_50006 = "Cannot send an empty message"
    err_50007 = "Cannot send messages to this user"
    err_50013 = "Missing Permissions"
    err_50018 = "Password does not match"
    err_50035 = "Invalid Form Body"
    err_50104 = "Malformed user settings payload"

    err_60002 = "Password does not match"
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


Errors = _Errors()