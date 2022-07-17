from .utils import b64encode

class Session:
    def __init__(self, uid, sid, sig):
        self.uid = uid
        self.sid = sid
        self.sig = sig
        self.token = f"{b64encode(str(uid).encode('utf8'))}.{b64encode(int.to_bytes(sid, 4, 'big'))}.{sig}"

class User:
    def __init__(self, uid, email, core):
        self.id = uid
        self.email = email
        self.settings = {}
        self.data = {}
        self._core = core

    async def loadSettings(self):
        self.settings.update(await self._core.getSettingsForUser(self))

    async def loadData(self):
        self.data.update(await self._core.getDataForUser(self))
        self.login = self.data["login"]
        self.discriminator = self.data["discriminator"]