from aiomysql import create_pool
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES
from .utils import b64encode, b64decode, unpack_token
from .classes import Session, User, LoginUser

def _usingDB(f):
    async def wrapper(self, *args, **kwargs):
        if "db" in kwargs or "cur" in kwargs:
            return await f(self, *args, **kwargs)
        if "db" not in f.__code__.co_varnames and "cur" not in f.__code__.co_varnames:
            return await f(self, *args, **kwargs)
        async with self.pool.acquire() as db:
            async with db.cursor() as cur:
                if "db" in f.__code__.co_varnames:
                    kwargs["db"] = db
                if "cur" in f.__code__.co_varnames:
                    kwargs["cur"] = cur
                return await f(self, *args, **kwargs)
    return wrapper

class Core:
    def __init__(self, key=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b'' 
        self.pool = None
        self.loop = loop or get_event_loop()

    async def initDB(self, *db_args, **db_kwargs):
        self.pool = await create_pool(*db_args, **db_kwargs)
        return self

    def encryptPassword(self, password):
        return new(self.key, password.encode('utf-8'), sha256).hexdigest()

    def generateKey(self, password_key):
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid, sid, key):
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    @_usingDB
    async def userExists(self, email, cur):
        await cur.execute(f"SELECT id FROM `users` WHERE `email`=\"{email}\";")
        r = await cur.fetchone()
        return bool(r)

    @_usingDB
    async def getHighestDiscriminator(self, login, cur):
        await cur.execute(f'SELECT `discriminator` FROM `userdata` WHERE `username`="{login}" ORDER BY discriminator DESC LIMIT 1;')
        if (r := await cur.fetchone()):
            return r[0]
        return 0

    @_usingDB
    async def register(self, uid, login, email, password, birth, cur):
        email = email.lower()
        if await self.userExists(email):
            return 1
        password = self.encryptPassword(password)
        key = self.generateKey(bytes.fromhex(password))
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))

        discrim = await self.getHighestDiscriminator(login, cur=cur)+1
        if discrim >= 10000:
            return 3

        await cur.execute(f'INSERT INTO `users` VALUES ({uid}, "{email}", "{password}", "{key}");')
        await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{signature}");')
        await cur.execute(f'INSERT INTO `settings`(`uid`) VALUES ({uid});')
        await cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES ({uid}, "{birth}", "{login}", {discrim});')
        return Session(uid, session, signature)

    @_usingDB
    async def login(self, email, password, cur):
        email = email.lower()
        await cur.execute(f'SELECT `password`, `key`, `id` FROM `users` WHERE `email`="{email}"')
        r = await cur.fetchone()
        if not r:
            return 2
        if self.encryptPassword(password) != r[0]:
            return 2
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(r[2], session, b64decode(r[1]))
        await cur.execute(f'INSERT INTO `sessions` VALUES ({r[2]}, {session}, "{signature}");')
        await cur.execute(f'SELECT `theme`, `locale` FROM `settings` WHERE `uid`="{r[2]}"')
        sr = await cur.fetchone()
        return LoginUser(r[2], Session(r[2], session, signature), sr[0], sr[1])

    @_usingDB
    async def getSession(self, uid, sid, sig, cur):
        await cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={uid} AND `sid`={sid} AND `sig`="{sig}";')
        r = await cur.fetchone()
        if r:
            return Session(r[0], sid, sig)

    @_usingDB
    async def getUser(self, token, cur):
        uid, sid, sig = unpack_token(token)
        if not (session := await self.getSession(uid, sid, sig, cur=cur)):
            return None
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getUserById(self, uid, cur):
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getSettings(self, uid, cur):
         await cur.execute(f'SELECT * FROM `settings` WHERE `uid`={uid};')
         r = await cur.fetchone()
         ret = []
         for idx, item in enumerate(r):
             ret.append((cur.description[idx][0], item))
         ret = dict(ret)
         del ret["uid"]
         return ret

    async def getSettingsForUser(self, user):
        return await self.getSettings(user.id)

    @_usingDB
    async def getUserData(self, uid, cur):
        await cur.execute(f'SELECT userdata.*, users.email FROM userdata INNER JOIN users on userdata.uid = users.id WHERE `uid`={uid};')
        r = await cur.fetchone()
        ret = []
        for idx, item in enumerate(r):
            ret.append((cur.description[idx][0], item))
        ret = dict(ret)
        del ret["uid"]
        return ret

    async def getDataForUser(self, user):
        return await self.getUserData(user.id)

    def _formatSettings(self, _settings):
        settings = []
        for k,v in _settings.items():
            if isinstance(v, str):
                v = f'"{v}"'
            elif isinstance(v, bool):
                v = "true" if v else "false"
            settings.append(f"`{k}`={v}")
        return ", ".join(settings)

    @_usingDB
    async def setSettings(self, user, settings, cur):
        if not settings:
            return        
        await cur.execute(f'UPDATE `settings` SET {self._formatSettings(settings)} WHERE `uid`={user.id};')

    @_usingDB
    async def setUserdata(self, user, settings, cur):
        if not settings:
            return
        await cur.execute(f'UPDATE `userdata` SET {self._formatSettings(settings)} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserProfile(self, uid, cUser, cur):
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUserById(uid, cur=cur)):
            return 4
        return user