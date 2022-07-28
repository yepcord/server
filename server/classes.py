from .utils import b64encode

class Session:
    def __init__(self, uid, sid, sig):
        self.uid = uid
        self.sid = sid
        self.sig = sig
        self.token = f"{b64encode(str(uid).encode('utf8'))}.{b64encode(int.to_bytes(sid, 6, 'big'))}.{sig}"

class User:
    def __init__(self, uid, email, core):
        self.id = uid
        self.email = email
        self._core = core
    
    @property
    def settings(self):
        return self._settings()

    @property
    def data(self):
        return self._userdata()

    @property
    def userdata(self):
        return self._userdata()

    async def _settings(self):
        return await self._core.getSettingsForUser(self)

    async def _userdata(self):
        return await self._core.getDataForUser(self)

class LoginUser:
    def __init__(self, uid, session, theme, locale):
        self.id = uid
        self.session = session
        self.theme = theme
        self.locale = locale
        self.token = session.token