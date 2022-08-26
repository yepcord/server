from aiomysql import Cursor
from asyncio import get_event_loop
from hmac import new
from hashlib import sha256
from os import urandom
from Crypto.Cipher import AES

from .databases import MySQL, Database, DBConnection
from .errors import InvalidDataErr, MfaRequiredErr
from .utils import b64encode, b64decode, RelationshipType, MFA, ChannelType, mksf, json_to_sql, lsf, mkError
from .classes import Session, User, Channel, UserId, Message, _User, UserSettings, UserData, ReadState, ChannelId, \
    UserNote, UserConnection, Attachment, Relationship
from .storage import _Storage
from json import loads as jloads
from random import randint
from .msg_client import Broadcaster
from typing import Optional, Union, List
from time import time


db: DBConnection = None

class CDN(_Storage):
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core


class Core:
    def __init__(self, key=None, db=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b''
        self.db = MySQL() if not db else db
        self.pool = None
        self.loop = loop or get_event_loop()
        self.mcl = Broadcaster("http")
        self._cache = {}

    async def initMCL(self):
        await self.mcl.start("ws://127.0.0.1:5050")
        self.mcl.set_callback(self.mclCallback)
        return self

    async def mclCallback(self, data: dict) -> None:
        ...

    async def initDB(self, *db_args, **db_kwargs):
        await self.db.init(*db_args, **db_kwargs)
        return self

    def encryptPassword(self, password: str) -> str:
        return new(self.key, password.encode('utf-8'), sha256).hexdigest()

    def generateKey(self, password_key: bytes) -> str:
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid: int, sid: int, key: bytes) -> str:
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    @Database.conn
    async def getRandomDiscriminator(self, login: str) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            if not await self.getUserByUsername(login, d):
                return d

    @Database.conn
    async def register(self, uid: int, login: str, email: str, password: str, birth: str) -> Session:
        email = email.lower()
        if await db.getUserByEmail(email):
            raise InvalidDataErr(400, mkError(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}}))
        password = self.encryptPassword(password)
        key = self.generateKey(bytes.fromhex(password))
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))

        discrim = await self.getRandomDiscriminator(login)
        if discrim is None:
            raise InvalidDataErr(400, mkError(50035, {"login": {"code": "USERNAME_TOO_MANY_USERS", "message": "Too many users have this username, please try another."}}))

        user = User(uid, email, password, key)
        session = Session(uid, session, signature)
        data = UserData(uid, birth=birth, username=login, discriminator=discrim)
        await db.registerUser(user, session, data)
        return session

    @Database.conn
    async def login(self, email: str, password: str) -> Session:
        email = email.strip().lower()
        user = await db.getUserByEmail(email)
        if not user or self.encryptPassword(password) != user.password:
            raise InvalidDataErr(400, mkError(50035, {"login": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}, "password": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}}))
        user.setCore(self)
        settings = await user.settings
        if settings.mfa:
            _sid = bytes.fromhex(user.password[:12])
            sid = int.from_bytes(_sid, "big")
            raise MfaRequiredErr(user.id, b64encode(_sid), self.generateSessionSignature(user.id, sid, b64decode(user.key)))
        return await self.createSession(user.id, user.key)

    @Database.conn
    async def createSession(self, uid: int, key: str) -> Session:
        sid = int.from_bytes(urandom(6), "big")
        sig = self.generateSessionSignature(uid, sid, b64decode(key))
        session = Session(uid, sid, sig)
        await db.insertSession(session)
        return session

    @Database.conn
    async def createSessionWithoutKey(self, uid: int) -> Session:
        user = await self.getUser(uid)
        return await self.createSession(uid, user.key)

    @Database.conn
    async def getUser(self, uid: int) -> Optional[User]:
        user = await db.getUser(uid)
        if user: user.setCore(self)
        return user

    async def getUserFromSession(self, session: Session) -> Optional[User]:
        if not await self.validSession(session):
            return
        return await self.getUser(session.id)

    @Database.conn
    async def validSession(self, session: Session) -> bool:
        return await db.validSession(session)

    @Database.conn
    async def getUserSettings(self, user: _User) -> UserSettings:
        return await db.getUserSettings(user)

    @Database.conn
    async def getUserData(self, user: _User) -> UserData:
        return await db.getUserData(user)

    @Database.conn
    async def setSettings(self, settings: UserSettings) -> None:
        await db.setSettings(settings)

    @Database.conn
    async def setSettingsDiff(self, before: UserSettings, after: UserSettings) -> None:
        await db.setSettingsDiff(before, after)

    @Database.conn
    async def setUserdata(self, userdata: UserData) -> None:
        await db.setUserData(userdata)

    async def getUserProfile(self, uid: int, cUser: User) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid)):
            raise InvalidDataErr(404, mkError(10013))
        return user

    async def checkUserPassword(self, user: User, password: str) -> bool:
        user = await self.getUser(user.id) if not user.get("key") else user
        password = self.encryptPassword(password)
        return user.password == password

    @Database.conn
    async def changeUserDiscriminator(self, user: User, discriminator: int) -> bool:
        username = (await user.data)["username"]
        if await self.getUserByUsername(username, discriminator):
            return False
        data = await user.data
        ndata = data.copy().set(discriminator=discriminator)
        await db.setUserDataDiff(data, ndata)
        return True

    @Database.conn
    async def changeUserName(self, user: User, username: str, cur: Cursor) -> None:
        discrim = (await user.data)["discriminator"]
        if await self.getUserByUsername(username, discrim):
            discrim = await self.getRandomDiscriminator(username, cur=cur)
            if discrim is None:
                raise InvalidDataErr(400, mkError(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This name is used by too many users. Please enter something else or try again."}}))
        data = await user.data
        ndata = data.copy().set(discriminator=discrim, username=username)
        await db.setUserDataDiff(data, ndata)

    @Database.conn
    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        user = await db.getUserByUsername(username, discriminator)
        if user: user.setCore(self)
        return user

    @Database.conn
    async def checkRelationShipAvailable(self, tUser: User, cUser: User) -> None:
        if not await db.relationShipAvailable(tUser, cUser):
            raise InvalidDataErr(400, mkError(80007))
        return None # TODO: check for mutual guilds or mutual friends

    @Database.conn
    async def reqRelationship(self, tUser: User, cUser: User) -> None:
        await db.insertRelationShip(Relationship(cUser, tUser, RelationshipType.PENDING))
        await self.mcl.broadcast("user_events", {"e": "relationship_req", "data": {"target_user": tUser.id, "current_user": cUser.id}})

    @Database.conn
    async def getRelationships(self, user: _User, with_data=False) -> list:
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
        for r in await db.getRelationships(user.id):
            if r.type == RelationshipType.BLOCK:
                uid = r.u1 if r.u1 != user.id else r.u2
                rel.append(await _d(uid, 2))
            elif r.type == RelationshipType.FRIEND:
                uid = r.u1 if r.u1 != user.id else r.u2
                rel.append(await _d(uid, 1))
            elif r.u1 == user.id:
                uid = r.u2
                rel.append(await _d(uid, 4))
            elif r.u2 == user.id:
                uid = r.u1
                rel.append(await _d(uid, 3))
        return rel

    @Database.conn
    async def getRelatedUsers(self, user: User, only_ids=False) -> list:
        users = []
        for r in await db.getRelationships(user.id):
            uid = r.u1 if r.u1 != user.id else r.u2
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
        for channel in await db.getPrivateChannels(user):
            uids = channel.recipients.copy()
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

    @Database.conn
    async def accRelationship(self, user: User, uid: int) -> None:
        await db.updateRelationship(user.id, uid, RelationshipType.FRIEND, RelationshipType.PENDING)
        channel = await self.getDMChannelOrCreate(user.id, uid)
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "data": {"target_user": uid, "current_user": user.id, "channel_id": channel.id}})

    @Database.conn
    async def delRelationship(self, user: User, uid: int) -> None:
        if not (rel := await db.getRelationship(user.id, uid)):
            return
        t = rel.type
        t1 = 0
        t2 = 0
        if t == RelationshipType.PENDING:
            if rel.u1 == user.id:
                t1 = 4
                t2 = 3
            else:
                t1 = 3
                t2 = 4
        await db.delRelationship(rel)
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": user.id, "target_user": uid, "type": t or t1}})
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": uid, "target_user": user.id, "type": t or t2}})

    @Database.conn
    async def changeUserPassword(self, user: User, new_password: str) -> None:
        new_password = self.encryptPassword(new_password)
        await db.changeUserPassword(user, new_password)

    @Database.conn
    async def logoutUser(self, sess: Session) -> None:
        await db.logoutUser(sess)

    def _sessionToUser(self, session: Session):
        return User(session.id).setCore(self)

    async def getMfa(self, user: Union[User, Session]) -> Optional[MFA]:
        if type(user) == Session:
            user = self._sessionToUser(user)
        settings = await user.settings
        mfa = MFA(settings.get("mfa_key"), user.id)
        if mfa.valid:
            return mfa

    @Database.conn
    async def setBackupCodes(self, user: _User, codes: List[str]) -> None:
        await db.clearBackupCodes(user)
        await db.setBackupCodes(user, codes)

    @Database.conn
    async def clearBackupCodes(self, user: _User) -> None:
        return await db.clearBackupCodes(user)

    @Database.conn
    async def getBackupCodes(self, user: _User) -> list:
        return await db.getBackupCodes(user)

    async def getMfaFromTicket(self, ticket: str) -> Optional[MFA]:
        try:
            uid, sid, sig = ticket.split(".")
            uid = jloads(b64decode(uid).decode("utf8"))[0]
            sid = b64decode(sid)
        except (ValueError, IndexError):
            return
        if not (user := await self.getUser(uid)):
            return
        if sid != bytes.fromhex(user.password[:12]):
            return
        if sig != self.generateSessionSignature(uid, int.from_bytes(sid, "big"), b64decode(user.key)):
            return
        settings = await user.settings
        return MFA(settings.mfa_key, uid)

    async def generateUserMfaNonce(self, user: User) -> tuple:
        mfa = await self.getMfa(user)
        nonce = f"{mfa.key}.{int(time() // 300)}"
        nonce = b64encode(new(self.key, nonce.encode('utf-8'), sha256).digest())
        rnonce = f"{int(time() // 300)}.{mfa.key}"
        rnonce = b64encode(new(self.key, rnonce.encode('utf-8'), sha256).digest())
        return nonce, rnonce

    @Database.conn
    async def useMfaCode(self, uid: int, code: str) -> bool:
        codes = dict(await self.getBackupCodes(UserId(uid)))
        if code not in codes:
            return False
        if codes[code]:
            return False
        await db.useMfaCode(uid, code)
        return True

    async def sendUserUpdateEvent(self, uid):
        await self.mcl.broadcast("user_events", {"e": "user_update", "data": {"user": uid}})

    @Database.conn
    async def getChannel(self, channel_id: int) -> Optional[Channel]:
        if not (channel := await db.getChannel(channel_id)):
            return
        return await self.getLastMessageIdForChannel(channel.setCore(self))

    @Database.conn
    async def getDMChannelOrCreate(self, u1: int, u2: int) -> Channel:
        if not (channel := await db.getDMChannel(u1, u2)):
            return await self.createDMChannel([u1, u2])
        return await self.getLastMessageIdForChannel(channel.setCore(self))

    async def getLastMessageIdForChannel(self, channel: Channel) -> Channel:
        return channel.set(last_message_id=await self.getLastMessageId(channel, lsf()+1, 0))

    @Database.conn
    async def getLastMessageId(self, channel: Channel, before: int, after: int) -> int:
        return await db.getLastMessageId(channel, before, after)

    @Database.conn
    async def getChannelMessagesCount(self, channel: Channel, before: int, after: int) -> int:
        return await db.getChannelMessagesCount(channel, before, after)

    @Database.conn
    async def createDMChannel(self, recipients: List[int]) -> Channel:
        cid = mksf()
        channel = await db.createDMChannel(cid, recipients)
        return channel.setCore(self).set(last_message_id=None)

    @Database.conn
    async def getPrivateChannels(self, user: _User) -> list:
        _channels = [await self.getLastMessageIdForChannel(channel.setCore(self)) for channel in await db.getPrivateChannels(user)]
        channels = []
        for channel in _channels:
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
                    "type": channel.type,
                    "recipient_ids": ids,
                    "last_message_id": channel.last_message_id,
                    "id": str(channel.id),
                    "owner_id": str(channel.owner_id),
                    "name": channel.name,
                    "icon": channel.icon
                })
        return channels

    @Database.conn
    async def getChannelMessages(self, channel, limit: int, before: int=None, after: int=None) -> List[Message]:
        return [message.setCore(self) for message in await db.getChannelMessages(channel, limit, before, after)]

    @Database.conn
    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]:
        message = await db.getMessage(channel, message_id)
        if message: message.setCore(self)
        return message

    @Database.conn
    async def sendMessage(self, message: Message) -> Message:
        await db.insertMessage(message)
        message.fill_defaults().setCore(self)
        m = await message.json
        users = await self.getRelatedUsersToChannel(message.channel_id)
        await self.mcl.broadcast("message_events", {"e": "message_create", "data": {"users": users, "message_obj": m}})
        async def _addToReadStates():
            _u = await self.getRelatedUsersToChannel(message.channel_id)
            _u.remove(message.author)
            for u in _u:
                await self.addMessageToReadStates(u, message.channel_id)
        get_event_loop().create_task(_addToReadStates())
        return message

    @Database.conn
    async def editMessage(self, before: Message, after: Message) -> Message:
        await db.editMessage(before, after)
        after.fill_defaults().setCore(self)
        m = await after.json
        users = await self.getRelatedUsersToChannel(after.channel_id)
        await self.mcl.broadcast("message_events", {"e": "message_update", "data": {"users": users, "message_obj": m}})
        return after

    @Database.conn
    async def deleteMessage(self, message: Message) -> None:
        await db.deleteMessage(message)
        await self.mcl.broadcast("message_events", {"e": "message_delete", "data": {"message": message.id, "channel": message.channel_id}})

    async def getRelatedUsersToChannel(self, channel: int) -> list:
        channel = await self.getChannel(channel)
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            return channel.recipients

    async def sendTypingEvent(self, user: _User, channel: Channel) -> None:
        await self.mcl.broadcast("message_events", {"e": "typing", "data": {"user": user.id, "channel": channel.id}})

    async def addMessageToReadStates(self, uid: int, channel_id: int) -> None:
        await self.setReadState(uid, channel_id, "`count`+1")

    @_usingDB
    async def setReadState(self, uid: int, channel_id: int, count: Union[int, str], cur: Cursor, _last: int=None) -> None:
        last = _last
        if not _last:
            last = "`last_read_id`"
        await cur.execute(f'UPDATE `read_states` set `count`={count}, `last_read_id`={last} WHERE `uid`={uid} and `channel_id`={channel_id};')
        if cur.rowcount == 0:
            if type(count) == str:
                count = 1
            last = _last
            if not _last:
                last = await self.getLastMessageId(ChannelId(channel_id), before=lsf()+1, after=0)
            await cur.execute(f'INSERT INTO `read_states` (`uid`, `channel_id`, `last_read_id`, `count`) VALUES ({uid}, {channel_id}, {last}, {count});')

    @_usingDB
    async def getReadStates(self, user: _User, cur: Cursor) -> list:
        states = []
        await cur.execute(f'SELECT * FROM `read_states` WHERE `uid`={user.id};')
        for r in await cur.fetchall():
            st = ReadState.from_result(cur.description, r)
            states.append({
                "mention_count": st.count,
                "last_pin_timestamp": "1970-01-01T00:00:00+00:00",  # TODO
                "last_message_id": str(st.last_read_id),
                "id": str(st.channel_id),
            })
        return states

    @_usingDB
    async def delReadStateIfExists(self, uid: int, channel_id: int, cur: Cursor) -> bool:
        await cur.execute(f'DELETE FROM `read_states` WHERE `uid`={uid} and `channel_id`={channel_id};')
        return cur.rowcount > 0

    async def sendMessageAck(self, uid: int, channel_id: int, message_id: int, mention_count: int=None, manual: bool=None) -> None:
        d = {
            "user": uid,
            "data": {
                "version": 1,
                "message_id": str(message_id),
                "channel_id": str(channel_id),
            }
        }
        if mention_count:
            d["data"]["mention_count"] = mention_count
        if manual:
            d["data"]["manual"] = True
            d["data"]["ack_type"] = 0
        await self.mcl.broadcast("message_ack", {"e": "typing", "data": d})

    @_usingDB
    async def getUserNote(self, uid: int, target_uid: int, cur: Cursor) -> Optional[UserNote]:
        await cur.execute(f'SELECT * FROM `notes` WHERE `uid`={uid} AND `target_uid`={target_uid};')
        if (r := await cur.fetchone()):
            return UserNote.from_result(cur.description, r)

    @_usingDB
    async def putUserNote(self, note: UserNote, cur: Cursor) -> None:
        await cur.execute(f'UPDATE `notes` SET `note`="{note.note}" WHERE `uid`={note.uid} AND `target_uid`={note.target_uid}')
        if cur.rowcount == 0:
            q = json_to_sql(note.to_sql_json(note.to_typed_json), as_tuples=True)
            fields = ", ".join([f"`{f}`" for f, v in q])
            values = ", ".join([f"{v}" for f, v in q])
            await cur.execute(f'INSERT INTO `notes` ({fields}) VALUES ({values});')

    @_usingDB
    async def putUserConnection(self, uc: UserConnection, cur: Cursor) -> None:
        q = json_to_sql(uc.to_sql_json(uc.to_typed_json, with_id=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await cur.execute(f'INSERT INTO `connections` ({fields}) VALUES ({values});')

    @_usingDB
    async def putAttachment(self, attachment: Attachment, cur: Cursor) -> None:
        q = json_to_sql(attachment.to_sql_json(attachment.to_typed_json, with_id=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await cur.execute(f'INSERT INTO `attachments` ({fields}) VALUES ({values});')

    @_usingDB
    async def getAttachment(self, id: str, cur: Cursor) -> Optional[Attachment]:
        await cur.execute(f'SELECT * FROM `attachments` WHERE `id`="{id}"')
        if (r := await cur.fetchone()):
            return Attachment.from_result(cur.description, r)

    @_usingDB
    async def getAttachmentByUUID(self, uuid: str, cur: Cursor) -> Optional[Attachment]:
        await cur.execute(f'SELECT * FROM `attachments` WHERE `uuid`="{uuid}"')
        if (r := await cur.fetchone()):
            return Attachment.from_result(cur.description, r)

    @_usingDB
    async def updateAttachment(self, before: Attachment, after: Attachment, cur: Cursor) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        await cur.execute(f'UPDATE `attachments` SET {diff} WHERE `id`={before.id};')