from aiomysql import create_pool
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES
from utils import b64encode, b64decode
from classes import Session, User
from json import dumps as jdumps

ERRORS = {
    50035: jdumps({"code": 50035, "errors": {"email": {"_errors": [{"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}]}}, "message": "Invalid Form Body"})
}

class GatewayClient:
    def __init__(self, ws, user):
        self.ws = ws
        self.user = user

class Gateway:
    def __init__(self, core):
        self._core = core
        self.clients = []

    async def process(self, ws, data):
        op = data["op"]
        if op == 2:
            return await self.processAuth(ws, data)

    async def processAuth(self, ws, data):
        token = data["d"]["token"]
        resp = {"t": "READY", "s": 1, "op": 0, "d": {"v": 9, "user": {}, "user_settings": {}}}
        if not (user := await self._core.getUser(token)):
            await ws.close()
            return
        await user.loadData()
        await user.loadSettings()
        resp["d"]["user"].update(user.data)
        resp["d"]["user"].update({"email": user.email, "id": str(user.id)})
        resp["d"]["user_settings"].update(user.settings)
        resp["d"]["user_settings"].update({"friend_source_flags": {"all": True}, "guild_positions": [], "guild_folders": []})
        await ws.send(jdumps(resp))
        self.clients.append(GatewayClient(ws, user))

class Core:
    def __init__(self, key, loop=None):
        self.key = key if len(key) == 16 and type(key) == bytes else b'' 
        self.pool = None
        self.loop = loop or get_event_loop()
        self.gateway = Gateway(self)

    async def initDB(self, *db_args, **db_kwargs):
        self.pool = await create_pool(*db_args, **db_kwargs)
        return self

    def response(self, resp):
        if type(resp) == int:
            return ERRORS[resp]
        if type(resp) == Session:
            return jdumps({"token": resp.token})

    def encryptPassword(self, password):
        return new(self.key, password.encode('utf-8'), sha256).hexdigest()

    def generateKey(self, password_key):
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid, sid, key):
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    async def userExists(self, email):
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f"SELECT id FROM `users` WHERE `email`=\"{email}\";")
                r = await cur.fetchone()
                return bool(r)

    async def register(self, uid, login, email, password, birth):
        email = email.lower()
        if await self.userExists(email):
            return 50035
        password = self.encryptPassword(password)
        key = self.generateKey(bytes.fromhex(password))
        session = int.from_bytes(urandom(4), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f'INSERT INTO `users` VALUES ({uid}, "{email}", "{password}", "{key}");')
                await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{key}", "{signature}");')
                await cur.execute(f'INSERT INTO `settings`(`uid`) VALUES ({uid});')
                await cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`) VALUES ({uid}, "{birth}", "{login}");')
        return Session(uid, session, signature)

    async def getSession(self, uid, sid, sig):
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={uid}, `sid`="{sid}", `sig`="{sig}";')
                r = await cur.fetchone()
                if r:
                    return Session(r[0], sid, sig)

    async def getUser(self, token):
        uid, sid, sig = token.split(".")
        uid = int(uid)
        if not (session := await self.getSession(uid, sid, sig)):
            return None
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
                r = await cur.fetchone()
                return User(uid, r[0], self)

    async def getSettings(self, uid):
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f'SELECT * FROM `settings` WHERE `uid`={uid};')
                r = await cur.fetchone()
                ret = []
                for idx, item in enumerate(r):
                    qwe.append((cur.description[idx][0], item))
                ret = dict(ret)
                del ret["uid"]
                return ret

    async def getSettingsForUser(self, user):
        return await self.getSettings(user.id) 

    async def getUserData(self, uid):
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                await cur.execute(f'SELECT * FROM `userdata` WHERE `uid`={uid};')
                r = await cur.fetchone()
                ret = []
                for idx, item in enumerate(r):
                    qwe.append((cur.description[idx][0], item))
                ret = dict(ret)
                del ret["uid"]
                return ret

    async def getDataForUser(self, user):
        return await self.getUserData(user.id)

    async def processGatewayData(self, client, data):
        await self.gateway.process(client, data)