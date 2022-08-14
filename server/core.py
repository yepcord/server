from aiomysql import create_pool, Cursor, escape_string
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES
from .utils import b64encode, b64decode, RELATIONSHIP, MFA, ChannelType, mksf, json_to_sql, result_to_json
from .classes import Session, User, Channel, UserId, Message, _User, UserSettings, UserData
from .storage import _Storage
from json import loads as jloads
from random import randint
from .msg_client import Broadcaster
from typing import Optional, Union, List
from time import time


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
        await cur.execute(f'SELECT id FROM `users` WHERE `email`="{escape_string(email)}";')
        r = await cur.fetchone()
        return bool(r)

    @_usingDB
    async def getRandomDiscriminator(self, login: str, cur) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={d} AND `username`="{escape_string(login)}";')
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

        await cur.execute(f'INSERT INTO `users` VALUES ({uid}, "{escape_string(email)}", "{password}", "{key}");')
        await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{signature}");')
        await cur.execute(f'INSERT INTO `settings`(`uid`) VALUES ({uid});')
        await cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES ({uid}, "{birth}", "{login}", {discrim});')
        return Session(uid, session, signature)

    @_usingDB
    async def login(self, email: str, password: str, cur: Cursor) -> Union[Session, int, tuple]:
        email = email.lower()
        await cur.execute(f'SELECT `password`, `key`, `id` FROM `users` WHERE `email`="{escape_string(email)}"')
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
        return await self.createSession(r[2], r[1], cur=cur)

    @_usingDB
    async def createSession(self, uid: int, key: str, cur) -> Session:
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))
        await cur.execute(f'INSERT INTO `sessions` VALUES ({uid}, {session}, "{signature}");')
        return Session(uid, session, signature)

    @_usingDB
    async def createSessionWithoutKey(self, uid: int, cur: Cursor) -> Session:
        await cur.execute(f'SELECT `key` FROM `users` WHERE `id`={uid}')
        key = (await cur.fetchone())[0]
        return await self.createSession(uid, key, cur=cur)

    @_usingDB
    async def getUser(self, uid: int, cur: Cursor) -> Optional[User]:
        await cur.execute(f'SELECT `email` FROM `users` WHERE `id`={uid};')
        if (r := await cur.fetchone()):
            return User(uid, r[0], self).setCore(self)

    async def getUserFromSession(self, session: Session) -> Optional[User]:
        if not await self.validSession(session):
            return
        return await self.getUser(session.id)

    @_usingDB
    async def validSession(self, session: Session, cur: Cursor) -> bool:
        await cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={session.id} AND `sid`={session.sid} AND `sig`="{session.sig}";')
        return bool(await cur.fetchone())

    @_usingDB
    async def getUserSettings(self, user: _User, cur: Cursor) -> UserSettings:
        await cur.execute(f'SELECT * FROM `settings` WHERE `uid`={user.id};')
        r = await cur.fetchone()
        return UserSettings(**result_to_json(cur.description, r))

    @_usingDB
    async def getUserData(self, user: _User, cur: Cursor) -> UserData:
        await cur.execute(f'SELECT * FROM `userdata` WHERE `uid`={user.id};')
        r = await cur.fetchone()
        return UserData(**result_to_json(cur.description, r))

    @_usingDB
    async def setSettings(self, settings: UserSettings, cur: Cursor) -> None:
        if not (j := settings.to_sql_json(settings.to_typed_json, with_values=True)):
            return
        await cur.execute(f'UPDATE `settings` SET {json_to_sql(j)} WHERE `uid`={settings.uid};')

    @_usingDB
    async def setUserdata(self, userdata: UserData, cur: Cursor) -> None:
        if not (j := userdata.to_sql_json(userdata.to_typed_json)):
            return
        await cur.execute(f'UPDATE `userdata` SET {json_to_sql(j)} WHERE `uid`={userdata.uid};')

    @_usingDB
    async def getUserProfile(self, uid: int, cUser: User, cur: Cursor) -> Union[User, int]:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid, cur=cur)):
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
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discrim} AND `username`="{escape_string(username)}";')
        if await cur.fetchone():
            discrim = await self.getRandomDiscriminator(username, cur=cur)
            if discrim is None:
                return 7
        await cur.execute(f'UPDATE `userdata` SET `username`="{escape_string(username)}", `discriminator`={discrim} WHERE `uid`={user.id};')

    @_usingDB
    async def getUserByUsername(self, username: str, discriminator: str, cur: Cursor) -> Optional[User]:
        await cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{username}";')
        if (r := await cur.fetchone()):
            return User(r[0]).setCore(self)

    @_usingDB
    async def relationShipAvailable(self, tUser: User, cUser: User, cur: Cursor) -> Optional[int]:
        await cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={tUser.id} AND `u2`={cUser.id}) OR (`u1`={cUser.id} AND `u2`={tUser.id});')
        if await cur.fetchone():
            return 10
        return None # TODO: check for relationship, mutual guilds or mutual friends

    @_usingDB
    async def reqRelationship(self, tUser: User, cUser: User, cur: Cursor) -> None:
        await cur.execute(f'INSERT INTO `relationships` VALUES ({cUser.id}, {tUser.id}, {RELATIONSHIP.PENDING});')
        await self.mcl.broadcast("user_events", {"e": "relationship_req", "data": {"target_user": tUser.id, "current_user": cUser.id}})

    @_usingDB
    async def getRelationships(self, user: _User, cur: Cursor, with_data=False) -> list:
        async def _d(uid, t):
            u = {"user_id": str(uid), "type": t, "nickname": None, "id": str(uid)}
            if with_data:
                d = await self.getUserData(UserId(uid))
                u["user"] = {
                    "id": str(uid),
                    "username": d.username,
                    "avatar": d.avatar,
                    "avatar_decoration": d.avatar_decoration,
                    "discriminator": str(d.discriminator).rjust(4, "0"),
                    "public_flags": d.public_flags
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
            d = await self.getUserData(UserId(uid))
            users.append({
                "username": d.username,
                "public_flags": d.public_flags,
                "id": str(uid),
                "discriminator": str(d.discriminator).rjust(4, "0"),
                "avatar_decoration": d.avatar_decoration,
                "avatar": d.avatar
            })
        await cur.execute(f'SELECT `j_recipients` FROM `channels` WHERE JSON_CONTAINS(j_recipients, {user.id}, "$");')
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
                d = await self.getUserData(UserId(uid))
                users.append({
                    "username": d.username,
                    "public_flags": d.public_flags,
                    "id": str(uid),
                    "discriminator": str(d.discriminator).rjust(4, "0"),
                    "avatar_decoration": d.avatar_decoration,
                    "avatar": d.avatar
                })
        return users

    @_usingDB
    async def accRelationship(self, user: User, uid: int, cur: Cursor) -> None:
        await cur.execute(f'UPDATE `relationships` SET `type`={RELATIONSHIP.FRIEND} WHERE `u1`={uid} AND `u2`={user.id} AND `type`={RELATIONSHIP.PENDING};')
        channel = await self.getDMChannelOrCreate(user.id, uid, cur=cur)
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "data": {"target_user": uid, "current_user": user.id, "channel_id": channel.id}})

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
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": user.id, "target_user": uid, "type": t or t1}})
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": uid, "target_user": user.id, "type": t or t2}})

    @_usingDB
    async def changeUserPassword(self, user: User, new_password: str, cur: Cursor) -> None:
        new_password = self.encryptPassword(new_password)
        await cur.execute(f'UPDATE `users` SET `password`="{new_password}" WHERE `id`={user.id}')

    @_usingDB
    async def logoutUser(self, sess: Session, cur: Cursor) -> None:
        await cur.execute(f'DELETE FROM `sessions` WHERE `uid`={sess.uid} AND `sid`={sess.sid} AND `sig`="{sess.sig}" LIMIT 1;')

    def _sessionToUser(self, session: Session):
        return User(session.id).setCore(self)

    async def getMfa(self, user: Union[User, Session]) -> Optional[MFA]:
        if type(user) == Session:
            user = self._sessionToUser(user)
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
        codes = dict(await self.getBackupCodes(UserId(uid), cur=cur))
        if code not in codes:
            return False
        if codes[code]:
            return False
        await cur.execute(f'UPDATE `mfa_codes` SET `used`=true WHERE `code`="{code}" AND `uid`={uid} LIMIT 1;')
        return True

    async def sendUserUpdateEvent(self, uid):
        await self.mcl.broadcast("user_events", {"e": "user_update", "data": {"user": uid}})

    @_usingDB
    async def getChannel(self, channel_id: int, cur: Cursor) -> Optional[Channel]:
        await cur.execute(f'SELECT * FROM `channels` WHERE `id`={channel_id};')
        if not (r := await cur.fetchone()):
            return
        return await self.getLastMessageId(Channel(**result_to_json(cur.description, r)).setCore(self), cur=cur)

    @_usingDB
    async def getDMChannelOrCreate(self, u1: int, u2: int, cur: Cursor) -> Channel:
        await cur.execute(f'SELECT `id` FROM `channels` WHERE JSON_CONTAINS(j_recipients, {u1}, "$") AND JSON_CONTAINS(j_recipients, {u2}, "$");')
        if not (r := await cur.fetchone()):
            return await self.createDMChannel([u1, u2], cur=cur)
        return await self.getLastMessageId(Channel(id=r[0], type=ChannelType.DM, recipients=[u1, u2]).setCore(self), cur=cur)

    @_usingDB
    async def getLastMessageId(self, channel: Channel, cur: Cursor) -> Channel:
        await cur.execute(f'SELECT `id` FROM `messages` WHERE `channel_id`={channel.id} ORDER BY `id` DESC LIMIT 1;')
        l = None
        if (r := await cur.fetchone()):
            l = r[0]
        return channel.set(last_message_id=l)

    @_usingDB
    async def createDMChannel(self, recipients: list, cur: Cursor) -> Channel:
        cid = mksf()
        await cur.execute(f'INSERT INTO `channels` (`id`, `type`, `j_recipients`) VALUES ({cid}, {ChannelType.DM}, "{recipients}");')
        return Channel(cid, ChannelType.DM, recipients=recipients).setCore(self).set(last_message_id=None)

    @_usingDB
    async def getPrivateChannels(self, user, cur: Cursor) -> list:
        channels = []
        await cur.execute(f'SELECT * FROM channels WHERE JSON_CONTAINS(channels.j_recipients, {user.id}, "$");')
        for r in await cur.fetchall():
            channel = await self.getLastMessageId(Channel(**result_to_json(cur.description, r)).setCore(self), cur=cur)
            ids = channel.recipients.copy()
            ids.remove(user.id)
            ids = [str(i) for i in ids]
            if channel.type == ChannelType.DM:
                channels.append({
                    "type": channel.type,
                    "recipient_ids": ids,
                    "last_message_id": channel.last_message_id,
                    "id": str(channel.id)
                })
            elif channel.type == ChannelType.GROUP_DM:
                channels.append({
                    "type": channel.tye,
                    "recipient_ids": ids,
                    "last_message_id": channel.last_message_id,
                    "id": str(channel.id),
                    "owner_id": str(channel.owner_id),
                    "name": channel.name,
                    "icon": channel.icon
                })
        return channels

    @_usingDB
    async def getChannelMessages(self, channel, limit: int, before: int=None, after: int=None, cur: Cursor=None) -> List[Message]:
        messages = []
        where = [f"`channel_id`={channel.id}"]
        if before:
            where.append(f"`id` < {before}")
        if after:
            where.append(f"`id` > {after}")
        where = " AND ".join(where)
        await cur.execute(f'SELECT * FROM `messages` WHERE {where} ORDER BY `id` DESC LIMIT {limit};')
        for r in await cur.fetchall():
            messages.append(Message.from_result(cur.description, r).setCore(self))
        return messages

    @_usingDB
    async def getMessage(self, channel, message_id: int, cur: Cursor) -> Optional[Message]:
        await cur.execute(f'SELECT * FROM `messages` WHERE `channel_id`={channel.id} AND `id`={message_id};')
        if (r := await cur.fetchone()):
            return Message.from_result(cur.description, r).setCore(self)

    @_usingDB
    async def sendMessage(self, message: Message, cur: Cursor) -> Message:
        q = json_to_sql(message.to_sql_json(message.to_typed_json, with_id=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f,v in q])
        values = ", ".join([f"{v}" for f,v in q])
        await cur.execute(f'INSERT INTO `messages` ({fields}) VALUES ({values});')
        message.fill_defaults().setCore(self)
        m = await message.json
        users = await self.getRelatedUsersToChannel(message.channel_id, cur=cur)
        await self.mcl.broadcast("message_events", {"e": "message_create", "data": {"users": users, "message_obj": m}})
        return message

    @_usingDB
    async def editMessage(self, before: Message, after: Message, cur: Cursor) -> Message:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        await cur.execute(f'UPDATE `messages` SET {diff} WHERE `id`={before.id} AND `channel_id`={before.channel_id}')
        after.fill_defaults().setCore(self)
        m = await after.json
        users = await self.getRelatedUsersToChannel(after.channel_id, cur=cur)
        await self.mcl.broadcast("message_events", {"e": "message_update", "data": {"users": users, "message_obj": m}})
        return after

    @_usingDB
    async def deleteMessage(self, message: Message, cur: Cursor):
        await cur.execute(f'DELETE FROM `messages` WHERE `id`={message.id};')
        await self.mcl.broadcast("message_events", {"e": "message_delete", "data": {"message": message.id, "channel": message.channel_id}})

    @_usingDB
    async def getRelatedUsersToChannel(self, channel: int, cur: Cursor) -> list:
        channel = await self.getChannel(channel, cur=cur)
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            return channel.recipients

    @_usingDB
    async def sendTypingEvent(self, user, channel):
        await self.mcl.broadcast("message_events", {"e": "typing", "data": {"user": user.id, "channel": channel.id}})