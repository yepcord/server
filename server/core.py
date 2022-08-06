from aiomysql import create_pool
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES
from .utils import b64encode, b64decode, unpack_token, RELATIONSHIP
from .classes import Session, User, LoginUser
from .storage import _Storage
from json import loads as jloads, dumps as jdumps
from random import randint
from .msg_client import Broadcaster
from typing import Optional, Union

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

class CDN(_Storage):
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core

class Core:
    def __init__(self, key=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b'' 
        self.pool = None
        self.loop = loop or get_event_loop()
        self.mcl = Broadcaster("http")

    async def initMCL(self) -> None:
        await self.mcl.start("ws://127.0.0.1:5050")
        self.mcl.set_callback(self.mclCallback)

    async def mclCallback(self, data: dict) -> None:
        ...

    async def initDB(self, *db_args, **db_kwargs) -> None:
        self.pool = await create_pool(*db_args, **db_kwargs)
        return self

    def encryptPassword(self, password: str) -> str:
        return new(self.key, password.encode('utf-8'), sha256).hexdigest()

    def generateKey(self, password_key: bytes) -> str:
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid: int, sid: int, key: bytes) -> str:
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    @_usingDB
    async def userExists(self, email: str, cur) -> bool:
        await cur.execute(f"SELECT id FROM `users` WHERE `email`=\"{email}\";")
        r = await cur.fetchone()
        return bool(r)

    @_usingDB
    async def getRandomDiscriminator(self, login: str, cur) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={d} AND `username`="{login}";')
            if not await cur.fetchone():
                return d

    @_usingDB
    async def register(self, uid: int, login: str, email: str, password: str, birth: str, cur) -> Union[Session, int]:
        email = email.lower()
        if await self.userExists(email):
            return 1
        password = self.encryptPassword(password)
        key = self.generateKey(bytes.fromhex(password))
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))

        discrim = await self.getRandomDiscriminator(login, cur=cur)
        if discrim is None:
            return 3

        await cur.execute(f'INSERT INTO `users` VALUES ({uid}, "{email}", "{password}", "{key}");')
        await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{signature}");')
        await cur.execute(f'INSERT INTO `settings`(`uid`) VALUES ({uid});')
        await cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES ({uid}, "{birth}", "{login}", {discrim});')
        return Session(uid, session, signature)

    @_usingDB
    async def login(self, email: str, password: str, cur) -> Union[LoginUser, int]:
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
    async def getSession(self, uid: int, sid: int, sig: str, cur) -> Optional[Session]:
        await cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={uid} AND `sid`={sid} AND `sig`="{sig}";')
        r = await cur.fetchone()
        if r:
            return Session(r[0], sid, sig)

    @_usingDB
    async def getUser(self, token: str, cur) -> User:
        uid, sid, sig = unpack_token(token)
        if not await self.getSession(uid, sid, sig, cur=cur):
            return None
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getUserById(self, uid: int, cur) -> User:
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getSettings(self, uid: int, cur) -> dict:
        await cur.execute(f'SELECT * FROM `settings` WHERE `uid`={uid};')
        r = await cur.fetchone()
        ret = []
        for idx, item in enumerate(r):
           name = cur.description[idx][0]
           if name.startswith("j_"):
               name = name[2:]
               item = jloads(item)
           ret.append((name, item))
        ret = dict(ret)
        del ret["uid"]
        return ret

    async def getSettingsForUser(self, user: User) -> dict:
        return await self.getSettings(user.id)

    @_usingDB
    async def getUserData(self, uid: int, cur) -> dict:
        await cur.execute(f'SELECT userdata.*, users.email FROM userdata INNER JOIN users on userdata.uid = users.id WHERE `uid`={uid};')
        r = await cur.fetchone()
        ret = []
        for idx, item in enumerate(r):
            ret.append((cur.description[idx][0], item))
        ret = dict(ret)
        del ret["uid"]
        return ret

    async def getDataForUser(self, user: User) -> dict:
        return await self.getUserData(user.id)

    def _formatSettings(self, _settings: dict) -> str:
        settings = []
        for k,v in _settings.items():
            if isinstance(v, str):
                v = f'"{v}"'
            elif isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, (dict, list)):
                k = f"j_{k}"
                v = jdumps(v).replace("\"", "\\\"")
                v = f"\"{v}\""
            settings.append(f"`{k}`={v}")
        return ", ".join(settings)

    @_usingDB
    async def setSettings(self, user: User, settings: dict, cur) -> None:
        if not settings:
            return        
        await cur.execute(f'UPDATE `settings` SET {self._formatSettings(settings)} WHERE `uid`={user.id};')

    @_usingDB
    async def setUserdata(self, user: User, userdata: dict, cur) -> None:
        if not userdata:
            return
        await cur.execute(f'UPDATE `userdata` SET {self._formatSettings(userdata)} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserProfile(self, uid: int, cUser: User, cur) -> Union[User, int]:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUserById(uid, cur=cur)):
            return 4
        return user

    @_usingDB
    async def checkUserPassword(self, user: User, password: str, cur) -> bool:
        password = self.encryptPassword(password)
        await cur.execute(f'SELECT `password` FROM `users` WHERE `id`={user.id};')
        passw = await cur.fetchone()
        return passw[0] == password

    @_usingDB
    async def changeUserDiscriminator(self, user: User, discriminator: int, cur) -> Optional[int]:
        username = (await user.data)["username"]
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{username}";')
        if await cur.fetchone():
            return 8
        await cur.execute(f'UPDATE `userdata` SET `discriminator`={discriminator} WHERE `uid`={user.id};')

    @_usingDB
    async def changeUserName(self, user: User, username: str, cur) -> Optional[int]:
        discrim = (await user.data)["discriminator"]
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discrim} AND `username`="{username}";')
        if await cur.fetchone():
            discrim = await self.getRandomDiscriminator(username, cur=cur)
            if discrim is None:
                return 7
        await cur.execute(f'UPDATE `userdata` SET `username`="{username}", `discriminator`={discrim} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserByUsername(self, username: str, discriminator: str, cur) -> Optional[User]:
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{username}";')
        if (r := await cur.fetchone()):
            return User(r[0], core=self)

    @_usingDB
    async def relationShipAvailable(self, tUser: User, cUser: User, cur) -> Optional[int]:
        await cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={tUser.id} AND `u2`={cUser.id}) OR (`u1`={cUser.id} AND `u2`={tUser.id});')
        if await cur.fetchone():
            return 10
        return None # TODO: check for relationship, mutual guilds or mutual friends

    @_usingDB
    async def reqRelationship(self, tUser: User, cUser: User, cur) -> None:
        await cur.execute(f'INSERT INTO `relationships` VALUES ({cUser.id}, {tUser.id}, {RELATIONSHIP.PENDING});')
        await self.mcl.broadcast("user_events", {"e": "relationship_req", "target_user": tUser.id, "current_user": cUser.id})

    @_usingDB
    async def getRelationships(self, user: User, cur, with_data=False) -> list:
        async def _d(uid, t):
            u = {"user_id": str(uid), "type": t, "nickname": None, "id": str(uid)}
            if with_data:
                d = await self.getUserData(uid)
                u["user"] = {
                    "id": str(uid),
                    "username": d["username"],
                    "avatar": d["avatar"],
                    "avatar_decoration": d["avatar_decoration"],
                    "discriminator": str(d["discriminator"]).rjust(4, "0"),
                    "public_flags": d["public_flags"]
                }
            return u
        rel = []
        await cur.execute(f'SELECT * FROM `relationships` WHERE `u1`={user.id} OR `u2`={user.id};')
        for r in await cur.fetchall():
            if r[2] == RELATIONSHIP.BLOCK:
                uid = r[0] if r[0] != user.id else r[1]
                rel.append(await _d(uid, 2))
            elif r[2] == RELATIONSHIP.FRIEND:
                uid = r[0] if r[0] != user.id else r[1]
                rel.append(await _d(uid, 1))
            elif r[0] == user.id:
                uid = r[1]
                rel.append(await _d(uid, 4))
            elif r[1] == user.id:
                uid = r[0]
                rel.append(await _d(uid, 3))
        return rel

    @_usingDB
    async def getRelatedUsers(self, user: User, cur) -> list:
        users = []
        await cur.execute(f'SELECT `u1`, `u2` FROM `relationships` WHERE `u1`={user.id} OR `u2`={user.id};')
        for r in await cur.fetchall():
            uid = r[0] if r[0] != user.id else r[1]
            d = await self.getUserData(uid)
            users.append({
                "username": d["username"],
                "public_flags": d["public_flags"],
                "id": str(uid),
                "discriminator": str(d["discriminator"]).rjust(4, "0"),
                "avatar_decoration": d["avatar_decoration"],
                "avatar": d["avatar"]
            })
        return users

    @_usingDB
    async def accRelationship(self, user: User, uid: int, cur) -> None:
        await cur.execute(f'UPDATE `relationships` SET `type`={RELATIONSHIP.FRIEND} WHERE `u1`={uid} AND `u2`={user.id} AND `type`={RELATIONSHIP.PENDING};')
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "target_user": uid, "current_user": user.id})

    @_usingDB
    async def delRelationship(self, user: User, uid: int, cur) -> None:
        await cur.execute(f'SELECT `type`, `u1`, `u2` FROM `relationships` WHERE (`u1`={user.id} AND `u2`={uid}) OR (`u1`={uid} AND `u2`={user.id});')
        if not (r := await cur.fetchone()):
            return
        t = r[0]
        t1 = 0
        t2 = 0
        if r == RELATIONSHIP.PENDING:
            if r[1] == user.id:
                t1 = 4
                t2 = 3
            else:
                t1 = 3
                t2 = 4
        await cur.execute(f"DELETE FROM `relationships` WHERE (`u1`={user.id} AND `u2`={uid}) OR (`u1`={uid} AND `u2`={user.id});")
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "current_user": user.id, "target_user": uid, "type": t or t1})
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "current_user": uid, "target_user": user.id, "type": t or t2})