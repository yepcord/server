from datetime import datetime

from aiomysql import create_pool, Cursor
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES
from .utils import b64encode, b64decode, unpack_token, RELATIONSHIP, MFA, NoneType, ChannelType, mksf
from .classes import Session, User, LoginUser, DMChannel, UserId
from .storage import _Storage
from json import loads as jloads, dumps as jdumps
from random import randint
from .msg_client import Broadcaster
from typing import Optional, Union
from time import time, mktime


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

    async def initMCL(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        self.mcl.set_callback(self.mclCallback)
        return self

    async def mclCallback(self, data: dict) -> None:
        ...

    async def initDB(self, *db_args, **db_kwargs):
        self.pool = await create_pool(*db_args, **db_kwargs)
        return self

    def encryptPassword(self, password: str) -> str:
        return new(self.key, password.encode('utf-8'), sha256).hexdigest()

    def generateKey(self, password_key: bytes) -> str:
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid: int, sid: int, key: bytes) -> str:
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    @_usingDB
    async def userExists(self, email: str, cur: Cursor) -> bool:
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
    async def register(self, uid: int, login: str, email: str, password: str, birth: str, cur: Cursor) -> Union[Session, int]:
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
    async def login(self, email: str, password: str, cur: Cursor) -> Union[LoginUser, int, tuple]:
        email = email.lower()
        await cur.execute(f'SELECT `password`, `key`, `id` FROM `users` WHERE `email`="{email}"')
        r = await cur.fetchone()
        if not r:
            return 2
        if self.encryptPassword(password) != r[0]:
            return 2
        await cur.execute(f'SELECT `mfa` FROM `settings` WHERE `uid`={r[2]}')
        mr = await cur.fetchone()
        if mr[0]:
            _sid = bytes.fromhex(r[0][:12])
            sid = int.from_bytes(_sid, "big")
            return 1, r[2], b64encode(_sid), self.generateSessionSignature(r[2], sid, b64decode(r[1]))
        session = await self.createSession(r[2], r[1], cur=cur)
        await cur.execute(f'SELECT `theme`, `locale` FROM `settings` WHERE `uid`="{r[2]}"')
        sr = await cur.fetchone()
        return LoginUser(r[2], session, sr[0], sr[1])

    @_usingDB
    async def createSession(self, uid: int, key: str, cur) -> Session:
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))
        await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{signature}");')
        return Session(uid, session, signature)

    @_usingDB
    async def createSessionWithoutKey(self, uid: int, cur: Cursor) -> Session:
        await cur.execute(f'SELECT `key` FROM `users` WHERE `id`={uid}')
        key = await cur.fetchone()
        key = key[0]
        return await self.createSession(uid, key, cur=cur)

    @_usingDB
    async def getLoginUser(self, uid: int, cur: Cursor) -> LoginUser:
        sess = await self.createSessionWithoutKey(uid, cur=cur)
        await cur.execute(f'SELECT `theme`, `locale` FROM `settings` WHERE `uid`="{uid}"')
        r = await cur.fetchone()
        return LoginUser(uid, sess, r[0], r[1])

    @_usingDB
    async def getSession(self, uid: int, sid: int, sig: str, cur: Cursor) -> Optional[Session]:
        await cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={uid} AND `sid`={sid} AND `sig`="{sig}";')
        r = await cur.fetchone()
        if r:
            return Session(r[0], sid, sig)

    @_usingDB
    async def getUser(self, token: str, cur: Cursor) -> Optional[User]:
        uid, sid, sig = unpack_token(token)
        if not await self.getSession(uid, sid, sig, cur=cur):
            return None
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getUserById(self, uid: int, cur: Cursor) -> User:
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        r = await cur.fetchone()
        return User(uid, r[0], self)

    @_usingDB
    async def getSettings(self, uid: int, cur: Cursor) -> dict:
        await cur.execute(f'SELECT settings.*, presences.status as status FROM settings INNER JOIN presences ON settings.uid = presences.uid WHERE settings.uid={uid};')
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
    async def getUserData(self, uid: int, cur: Cursor) -> dict:
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
            elif isinstance(v, NoneType):
                v = "null"
            settings.append(f"`{k}`={v}")
        return ", ".join(settings)

    @_usingDB
    async def setSettings(self, user: User, settings: dict, cur: Cursor) -> None:
        if not settings:
            return        
        await cur.execute(f'UPDATE `settings` SET {self._formatSettings(settings)} WHERE `uid`={user.id};')

    @_usingDB
    async def setUserdata(self, user: User, userdata: dict, cur: Cursor) -> None:
        if not userdata:
            return
        await cur.execute(f'UPDATE `userdata` SET {self._formatSettings(userdata)} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserProfile(self, uid: int, cUser: User, cur: Cursor) -> Union[User, int]:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUserById(uid, cur=cur)):
            return 4
        return user

    @_usingDB
    async def checkUserPassword(self, user: User, password: str, cur: Cursor) -> bool:
        password = self.encryptPassword(password)
        await cur.execute(f'SELECT `password` FROM `users` WHERE `id`={user.id};')
        passw = await cur.fetchone()
        return passw[0] == password

    @_usingDB
    async def changeUserDiscriminator(self, user: User, discriminator: int, cur: Cursor) -> Optional[int]:
        username = (await user.data)["username"]
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{username}";')
        if await cur.fetchone():
            return 8
        await cur.execute(f'UPDATE `userdata` SET `discriminator`={discriminator} WHERE `uid`={user.id};')

    @_usingDB
    async def changeUserName(self, user: User, username: str, cur: Cursor) -> Optional[int]:
        discrim = (await user.data)["discriminator"]
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discrim} AND `username`="{username}";')
        if await cur.fetchone():
            discrim = await self.getRandomDiscriminator(username, cur=cur)
            if discrim is None:
                return 7
        await cur.execute(f'UPDATE `userdata` SET `username`="{username}", `discriminator`={discrim} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserByUsername(self, username: str, discriminator: str, cur: Cursor) -> Optional[User]:
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{username}";')
        if (r := await cur.fetchone()):
            return User(r[0], core=self)

    @_usingDB
    async def relationShipAvailable(self, tUser: User, cUser: User, cur: Cursor) -> Optional[int]:
        await cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={tUser.id} AND `u2`={cUser.id}) OR (`u1`={cUser.id} AND `u2`={tUser.id});')
        if await cur.fetchone():
            return 10
        return None # TODO: check for relationship, mutual guilds or mutual friends

    @_usingDB
    async def reqRelationship(self, tUser: User, cUser: User, cur: Cursor) -> None:
        await cur.execute(f'INSERT INTO `relationships` VALUES ({cUser.id}, {tUser.id}, {RELATIONSHIP.PENDING});')
        await self.mcl.broadcast("user_events", {"e": "relationship_req", "target_user": tUser.id, "current_user": cUser.id})

    @_usingDB
    async def getRelationships(self, user: User, cur: Cursor, with_data=False) -> list:
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
    async def getRelatedUsers(self, user: User, cur: Cursor, only_ids=False) -> list:
        users = []
        await cur.execute(f'SELECT `u1`, `u2` FROM `relationships` WHERE `u1`={user.id} OR `u2`={user.id};')
        for r in await cur.fetchall():
            uid = r[0] if r[0] != user.id else r[1]
            if only_ids:
                users.append(uid)
                continue
            d = await self.getUserData(uid)
            users.append({
                "username": d["username"],
                "public_flags": d["public_flags"],
                "id": str(uid),
                "discriminator": str(d["discriminator"]).rjust(4, "0"),
                "avatar_decoration": d["avatar_decoration"],
                "avatar": d["avatar"]
            })
        await cur.execute(f'SELECT `recipients` FROM `dm_channels` WHERE JSON_CONTAINS(recipients, {user.id}, "$");')
        for r in await cur.fetchall():
            uids = jloads(r[0])
            uids.remove(user.id)
            for uid in uids:
                if only_ids:
                    if [u for u in users if u == uid]: continue
                    users.append(uid)
                    continue
                if [u for u in users if u["id"] == str(uid)]:
                    continue
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
    async def accRelationship(self, user: User, uid: int, cur: Cursor) -> None:
        await cur.execute(f'UPDATE `relationships` SET `type`={RELATIONSHIP.FRIEND} WHERE `u1`={uid} AND `u2`={user.id} AND `type`={RELATIONSHIP.PENDING};')
        channel = await self.getDMChannelOrCreate(user.id, uid, cur=cur)
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "target_user": uid, "current_user": user.id, "channel_id": channel.id})

    @_usingDB
    async def delRelationship(self, user: User, uid: int, cur: Cursor) -> None:
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
        await cur.execute(f"DELETE FROM `relationships` WHERE (`u1`={user.id} AND `u2`={uid}) OR (`u1`={uid} AND `u2`={user.id}) LIMIT 1;")
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "current_user": user.id, "target_user": uid, "type": t or t1})
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "current_user": uid, "target_user": user.id, "type": t or t2})

    @_usingDB
    async def changeUserPassword(self, user: User, new_password: str, cur: Cursor) -> None:
        new_password = self.encryptPassword(new_password)
        await cur.execute(f'UPDATE `users` SET `password`="{new_password}" WHERE `id`={user.id}')

    @_usingDB
    async def logoutUser(self, sess: Session, cur: Cursor) -> None:
        await cur.execute(f'DELETE FROM `sessions` WHERE `uid`={sess.uid} AND `sid`={sess.sid} AND `sig`="{sess.sig}" LIMIT 1;')

    def sessionToUser(self, session: Session):
        return User(session.id, core=self)

    async def getMfa(self, user: Union[User, Session]) -> Optional[MFA]:
        if type(user) == Session:
            user = self.sessionToUser(user)
        settings = await user.settings
        mfa = MFA(settings.get("mfa"), user.id)
        if mfa.valid:
            return mfa

    @_usingDB
    async def setBackupCodes(self, user, codes: list, cur: Cursor) -> None:
        codes = [(str(user.id), code) for code in codes]
        await self.clearBackupCodes(user, cur=cur)
        await cur.executemany('INSERT INTO `mfa_codes` (`uid`, `code`) VALUES (%s, %s)', codes)

    @_usingDB
    async def clearBackupCodes(self, user, cur: Cursor) -> None:
        await cur.execute(f'DELETE FROM `mfa_codes` WHERE `uid`={user.id} LIMIT 10;')

    @_usingDB
    async def getBackupCodes(self, user, cur: Cursor) -> list:
        await cur.execute(f'SELECT `code`, `used` FROM `mfa_codes` WHERE `uid`={user.id} LIMIT 10;')
        return await cur.fetchall()

    @_usingDB
    async def getMfaFromTicket(self, ticket: str, cur: Cursor) -> Optional[MFA]:
        try:
            uid, sid, sig = ticket.split(".")
            uid = jloads(b64decode(uid).decode("utf8"))[0]
            sid = b64decode(sid)
        except (ValueError, IndexError):
            return
        await cur.execute(f'SELECT `password`, `key` FROM `users` WHERE `id`={uid}')
        if not (r := await cur.fetchone()):
            return
        if sid != bytes.fromhex(r[0][:12]):
            return
        if sig != self.generateSessionSignature(uid, int.from_bytes(sid, "big"), b64decode(r[1])):
            return
        await cur.execute(f'SELECT `mfa` FROM `settings` WHERE `uid`={uid}')
        r = await cur.fetchone()
        return MFA(r[0], uid)

    async def generateUserMfaNonce(self, user: User) -> tuple:
        mfa = await self.getMfa(user)
        nonce = f"{mfa.key}.{int(time() // 300)}"
        nonce = b64encode(new(self.key, nonce.encode('utf-8'), sha256).digest())
        rnonce = f"{int(time() // 300)}.{mfa.key}"
        rnonce = b64encode(new(self.key, rnonce.encode('utf-8'), sha256).digest())
        return nonce, rnonce

    @_usingDB
    async def useMfaCode(self, uid: int, code: str, cur: Cursor) -> bool:
        codes = dict(await self.getBackupCodes(User(uid), cur=cur))
        if code not in codes:
            return False
        if codes[code]:
            return False
        await cur.execute(f'UPDATE `mfa_codes` SET `used`=true WHERE `code`="{code}" AND `uid`={uid} LIMIT 1;')
        return True

    async def sendUserUpdateEvent(self, uid):
        await self.mcl.broadcast("user_events", {"e": "user_update", "user": uid})

    @_usingDB
    async def getChannel(self, channel_id: int, cur: Cursor):
        await cur.execute(f'SELECT `type` FROM `channels` WHERE `id`={channel_id};')
        if not (r := await cur.fetchone()):
            return
        if r[0] == ChannelType.DM:
            await cur.execute(f'SELECT `recipients` FROM `dm_channels` WHERE `id`={channel_id};')
            r = await cur.fetchone()
            r = jloads(r[0])
            return DMChannel(channel_id, r, self)

    @_usingDB
    async def getDMChannelOrCreate(self, u1: int, u2: int, cur: Cursor) -> DMChannel:
        await cur.execute(f'SELECT `id` FROM `dm_channels` WHERE JSON_CONTAINS(recipients, {u1}, "$") AND JSON_CONTAINS(recipients, {u2}, "$");')
        if not (r := await cur.fetchone()):
            return await self.createDMChannel(u1, u2, cur=cur)
        return DMChannel(r[0], [u1, u2], self)

    @_usingDB
    async def createDMChannel(self, u1: int, u2: int, cur: Cursor) -> DMChannel:
        cid = mksf()
        recipients = jdumps([u1, u2])
        await cur.execute(f'INSERT INTO `dm_channels` (`id`, `recipients`) VALUES ({cid}, "{recipients}");')
        await cur.execute(f'INSERT INTO `channels` (`id`, `type`) VALUES ({cid}, "{ChannelType.DM}");')
        return DMChannel(cid, recipients, self)

    @_usingDB
    async def getChannelInfo(self, channel, cur: Cursor):
        await cur.execute(f'SELECT `id` FROM `messages` WHERE `channel_id`={channel.id} ORDER BY `id` DESC LIMIT 1;')
        if not (r := await cur.fetchone()):
            return {"last_message_id": None}
        return {"last_message_id": r[0]}

    @_usingDB
    async def getPrivateChannels(self, user, cur: Cursor):
        channels = []
        await cur.execute(f'SELECT dm_channels.*, channels.type FROM dm_channels INNER JOIN channels ON dm_channels.id = channels.id WHERE JSON_CONTAINS(dm_channels.recipients, {user.id}, "$");')
        for r in await cur.fetchall():
            ids = jloads(r[1])
            ids.remove(user.id)
            ids = [str(i) for i in ids]
            info = await self.getChannelInfo(DMChannel(r[0], ids, self), cur=cur)
            if r[5] == ChannelType.DM:
                channels.append({
                    "type": r[5],
                    "recipient_ids": ids,
                    "last_message_id": info["last_message_id"],
                    "id": str(r[0])
                })
            elif r[5] == ChannelType.GROUP_DM:
                channels.append({
                    "type": r[5],
                    "recipient_ids": ids,
                    "last_message_id": info["last_message_id"],
                    "id": str(r[0]),
                    "owner_id": str(r[4]),
                    "name": r[2],
                    "icon": r[3]
                })
        return channels

    @_usingDB
    async def getFriendsPresences(self, uid: int, cur: Cursor) -> list:
        pr = []
        fr = await self.getRelationships(UserId(uid), cur=cur)
        fr = [int(u["user_id"]) for u in fr if u["type"] == 1]
        for f in fr:
            await cur.execute(f'SELECT `status`, `modified`, `activities`, `online` FROM `presences` WHERE presences.uid={f};')
            if not (r := await cur.fetchone()):
                continue
            pr.append({
                "user_id": str(f),
                "status": r[0] if r[3] else "offline",
                "last_modified": r[1],
                "client_status": {"desktop": r[0]} if r[0] != "offline" and not r[3] else {},
                "activities": jloads(r[2]) if r[3] else []
            })
        return pr

    @_usingDB
    async def updatePresence(self, uid: int, status: dict, cur: Cursor) -> Optional[dict]:
        if status.get("status") == "offline":
            await cur.execute(f'UPDATE `presences` SET `online`=false WHERE `uid`={uid};')
        else:
            r = {}
            q = []
            if (st := status.get("status")):
                if st == "invisible":
                    st = "offline"
                q.append(f'`status`="{st}"')
                r["status"] = st
            cs = status.get("custom_status", 0)
            if cs != 0:
                if cs is None:
                    cs = []
                else:
                    if (ex := cs.get("expires_at")):
                        ex = mktime(datetime.strptime(ex, '%Y-%m-%dT%H:%M:%S.000Z').timetuple())
                    cs = [{"type":4, "state": cs["text"], "name": "Custom Status", "id": "custom","created_at": int(time()*1000)}]
                    r["activities"] = cs.copy()
                    if ex: cs[0]["expire"] = ex
                q.append(f'`activities`="{jloads(cs)}"')
            q = ", ".join(q)
            await cur.execute(f'UPDATE `presences` SET {q} WHERE `uid`={uid};')
            return r

    @_usingDB
    async def getUserPresence(self, uid: int, cur: Cursor):
        await cur.execute(f'SELECT `status`, `online`, `modified`, `activities` FROM `presences` WHERE `uid`={uid};')
        if not (r := await cur.fetchone()):
            await cur.execute(f'INSERT INTO `presences` (`uid`, `modified`) VALUES ({uid}, {int(time()*1000)});')
            return {"status": "offline", "last_modified": int(time()*1000), "activities": []}
        ac = jloads(r[3])
        if ac and (ex := ac[0].get("expire")):
            if time() > ex:
                await self.updatePresence(uid, {"custom_status": None}, cur=cur)
            del ac[0]["expire"]
        return {"status": r[0] if r[1] else "offline", "last_modified": r[2], "activities": ac if r[1] else []}

    async def sendPresenceUpdateEvent(self, uid: int, status: dict):
        await self.mcl.broadcast("user_events", {"e": "presence_update", "user": uid, "status": status})