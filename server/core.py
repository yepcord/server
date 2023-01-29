from asyncio import get_event_loop
from contextvars import Context
from datetime import datetime
from hmac import new
from hashlib import sha256, sha512
from os import urandom
from Crypto.Cipher import AES
from base64 import b64encode as _b64encode
from json import loads as jloads, dumps as jdumps
from random import randint
from typing import Optional, Union, List, Tuple
from time import time

from .config import Config
from .databases import MySQL
from .errors import InvalidDataErr, MfaRequiredErr
from .responses import channelInfoResponse
from .utils import b64encode, b64decode, MFA, mksf, lsf, mkError, execute_after
from .classes.channel import Channel
from .classes.guild import Emoji, Invite, Guild, Role, GuildId, _Guild
from .classes.message import Message, Attachment, Reaction, SearchFilter, ReadState
from .classes.user import Session, UserSettings, UserNote, User, UserId, _User, UserData, Relationship, GuildMember
from .classes.other import EmailMsg
from .enums import RelationshipType, ChannelType
from .pubsub_client import Broadcaster

class CDN:
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core

    def __getattr__(self, item):
        return getattr(self.storage, item)

class Core:
    _instance = None

    def __init__(self, key=None, db=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b''
        self.db = MySQL() if not db else db
        self.pool = None
        self.loop = loop or get_event_loop()
        self.mcl = Broadcaster("http")
        self._cache = {}

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(Core, cls).__new__(cls)
        return cls._instance

    @classmethod
    def getInstance(cls):
        return cls._instance

    async def initMCL(self):
        try:
            await self.mcl.start(f"ws://{Config('PS_ADDRESS')}:5050")
            self.mcl.set_callback(self.mclCallback)
        except ConnectionRefusedError:
            self.mcl.online = False
            self.mcl.running = True
        return self

    async def mclCallback(self, data: dict) -> None:
        ...

    async def initDB(self, *db_args, **db_kwargs):
        await self.db.init(*db_args, **db_kwargs)
        return self

    def encryptPassword(self, uid: int, password: str) -> str:
        key = new(self.key, int.to_bytes(uid, 16, "big"), sha256).digest()
        return new(key, password.encode('utf-8'), sha512).hexdigest()

    def generateKey(self, password_key: bytes) -> str:
        return b64encode(AES.new(self.key, AES.MODE_CBC, urandom(16)).encrypt(password_key))

    def generateSessionSignature(self, uid: int, sid: int, key: bytes) -> str:
        return b64encode(new(key, f"{uid}.{sid}".encode('utf-8'), sha256).digest())

    async def getRandomDiscriminator(self, login: str) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            if not await self.getUserByUsername(login, d):
                return d

    async def register(self, uid: int, login: str, email: Optional[str], password: str, birth: str, locale: str, invite: Optional[str]=None) -> Session:
        email = email.lower()
        async with self.db() as db:
            if await db.getUserByEmail(email):
                raise InvalidDataErr(400, mkError(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}}))
        password = self.encryptPassword(uid, password)
        key = self.generateKey(bytes.fromhex(password))
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature(uid, session, b64decode(key))

        discriminator = await self.getRandomDiscriminator(login)
        if discriminator is None:
            raise InvalidDataErr(400, mkError(50035, {"login": {"code": "USERNAME_TOO_MANY_USERS", "message": "Too many users have this username, please try another."}}))

        user = User(uid, email, password, key)
        session = Session(uid, session, signature)
        data = UserData(uid, birth=birth, username=login, discriminator=discriminator)
        async with self.db() as db:
            await db.registerUser(user, session, data, UserSettings(uid, locale=locale))
        await self.sendVerificationEmail(user)
        return session

    async def login(self, email: str, password: str) -> Session:
        email = email.strip().lower()
        async with self.db() as db:
            user = await db.getUserByEmail(email)
        if not user or self.encryptPassword(user.id, password) != user.password:
            raise InvalidDataErr(400, mkError(50035, {"login": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}, "password": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}}))
        settings = await user.settings
        if settings.mfa:
            _sid = bytes.fromhex(user.password[:12])
            sid = int.from_bytes(_sid, "big")
            raise MfaRequiredErr(user.id, b64encode(_sid), self.generateSessionSignature(user.id, sid, b64decode(user.key)))
        return await self.createSession(user.id, user.key)

    async def createSession(self, uid: int, key: str) -> Session:
        sid = int.from_bytes(urandom(6), "big")
        sig = self.generateSessionSignature(uid, sid, b64decode(key))
        session = Session(uid, sid, sig)
        async with self.db() as db:
            await db.insertSession(session)
        return session

    async def createSessionWithoutKey(self, uid: int) -> Session:
        user = await self.getUser(uid)
        return await self.createSession(uid, user.key)

    async def getUser(self, uid: int) -> Optional[User]:
        async with self.db() as db:
            user = await db.getUser(uid)
        return user

    async def getUserFromSession(self, session: Session) -> Optional[User]:
        if not await self.validSession(session):
            return
        return await self.getUser(session.id)

    async def validSession(self, session: Session) -> bool:
        async with self.db() as db:
            return await db.validSession(session)

    async def getUserSettings(self, user: _User) -> UserSettings:
        async with self.db() as db:
            return await db.getUserSettings(user)

    async def getUserData(self, user: _User) -> UserData:
        async with self.db() as db:
            return await db.getUserData(user)

    async def setSettings(self, settings: UserSettings) -> None:
        async with self.db() as db:
            await db.setSettings(settings)

    async def setSettingsDiff(self, before: UserSettings, after: UserSettings) -> None:
        async with self.db() as db:
            await db.setSettingsDiff(before, after)

    async def setUserdata(self, userdata: UserData) -> None:
        async with self.db() as db:
            await db.setUserData(userdata)

    async def getUserProfile(self, uid: int, cUser: User) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid)):
            raise InvalidDataErr(404, mkError(10013))
        return user

    async def checkUserPassword(self, user: User, password: str) -> bool:
        user = await self.getUser(user.id) if not user.get("key") else user
        password = self.encryptPassword(user.id, password)
        return user.password == password

    async def changeUserDiscriminator(self, user: User, discriminator: int) -> bool:
        username = (await user.data).username
        if await self.getUserByUsername(username, discriminator):
            return False
        data = await user.data
        ndata = data.copy().set(discriminator=discriminator)
        async with self.db() as db:
            await db.setUserDataDiff(data, ndata)
        return True

    async def changeUserName(self, user: User, username: str) -> None:
        discriminator = (await user.data).discriminator
        if await self.getUserByUsername(username, discriminator):
            discriminator = await self.getRandomDiscriminator(username)
            if discriminator is None:
                raise InvalidDataErr(400, mkError(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This name is used by too many users. Please enter something else or try again."}}))
        data = await user.data
        ndata = data.copy().set(discriminator=discriminator, username=username)
        async with self.db() as db:
            await db.setUserDataDiff(data, ndata)

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        async with self.db() as db:
            user = await db.getUserByUsername(username, discriminator)
        return user

    async def checkRelationShipAvailable(self, tUser: User, cUser: User) -> None:
        async with self.db() as db:
            if not await db.relationShipAvailable(tUser, cUser):
                raise InvalidDataErr(400, mkError(80007))
        return None # TODO: check for mutual guilds or mutual friends

    async def reqRelationship(self, tUser: User, cUser: User) -> None:
        async with self.db() as db:
            await db.insertRelationShip(Relationship(cUser.id, tUser.id, RelationshipType.PENDING))
        await self.mcl.broadcast("user_events", {"e": "relationship_req", "data": {"target_user": tUser.id, "current_user": cUser.id}})

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
                    "discriminator": d.s_discriminator,
                    "public_flags": d.public_flags
                }
            return u
        rel = []
        async with self.db() as db:
            for r in await db.getRelationships(user.id):
                if r.type == RelationshipType.BLOCK:
                    if r.u1 != user.id:
                        continue
                    uid = r.u2
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

    async def getRelationship(self, u1: int, u2: int) -> Optional[Relationship]:
        async with self.db() as db:
            return await db.getRelationship(u1, u2)

    async def getRelatedUsers(self, user: User, only_ids=False) -> list:
        users = []
        async with self.db() as db:
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
                    "discriminator": d.s_discriminator,
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
                        "discriminator": d.s_discriminator,
                        "avatar_decoration": d.avatar_decoration,
                        "avatar": d.avatar
                    })
        return users

    async def accRelationship(self, user: User, uid: int) -> None:
        async with self.db() as db:
            await db.updateRelationship(user.id, uid, RelationshipType.FRIEND, RelationshipType.PENDING)
        channel = await self.getDMChannelOrCreate(user.id, uid)
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "data": {"target_user": uid, "current_user": user.id, "channel_id": channel.id}})

    async def delRelationship(self, user: User, uid: int) -> None:
        async with self.db() as db:
            if not (rel := await db.getRelationship(user.id, uid)):
                return
        if rel.type == RelationshipType.BLOCK:
            if not (rel := await db.getRelationshipEx(user.id, uid)):
                return
            async with self.db() as db:
                await db.delRelationship(rel)
            await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": user.id, "target_user": uid, "type": rel.type}})
            return
        t1 = rel.discord_type(user.id)
        t2 = rel.discord_type(uid)
        async with self.db() as db:
            await db.delRelationship(rel)
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": user.id, "target_user": uid, "type": t1}})
        await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": uid, "target_user": user.id, "type": t2}})

    async def changeUserPassword(self, user: User, new_password: str) -> None:
        new_password = self.encryptPassword(user.id, new_password)
        async with self.db() as db:
            await db.changeUserPassword(user, new_password)

    async def logoutUser(self, sess: Session) -> None:
        async with self.db() as db:
            await db.logoutUser(sess)

    def _sessionToUser(self, session: Session) -> User:
        return User(session.id)

    async def getMfa(self, user: Union[User, Session]) -> Optional[MFA]:
        if type(user) == Session:
            user = self._sessionToUser(user)
        settings = await user.settings
        mfa = MFA(settings.get("mfa"), user.id)
        if mfa.valid:
            return mfa

    async def setBackupCodes(self, user: _User, codes: List[str]) -> None:
        async with self.db() as db:
            await db.clearBackupCodes(user)
            await db.setBackupCodes(user, codes)

    async def clearBackupCodes(self, user: _User) -> None:
        async with self.db() as db:
            return await db.clearBackupCodes(user)

    async def getBackupCodes(self, user: _User) -> list:
        async with self.db() as db:
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
        return MFA(settings.mfa, uid)

    async def generateUserMfaNonce(self, user: User) -> Tuple[str, str]:
        mfa = await self.getMfa(user)
        _nonce = f"{mfa.key}.{int(time() // 600)}"
        nonce = b64encode(b'\x00'+new(self.key, _nonce.encode('utf-8'), sha256).digest())
        rnonce = b64encode(b'\x01'+new(self.key, _nonce.encode('utf-8'), sha256).digest()[::-1])
        return nonce, rnonce

    async def useMfaCode(self, uid: int, code: str) -> bool:
        codes = dict(await self.getBackupCodes(UserId(uid)))
        if code not in codes:
            return False
        if codes[code]:
            return False
        async with self.db() as db:
            await db.useMfaCode(uid, code)
        return True

    async def sendUserUpdateEvent(self, uid):
        await self.mcl.broadcast("user_events", {"e": "user_update", "data": {"user": uid}})

    async def getChannel(self, channel_id: int) -> Optional[Channel]:
        async with self.db() as db:
            if not (channel := await db.getChannel(channel_id)):
                return
        return await self.getLastMessageIdForChannel(channel)

    async def getDMChannelOrCreate(self, u1: int, u2: int) -> Channel:
        async with self.db() as db:
            if not (channel := await db.getDMChannel(u1, u2)):
                return await self.createDMChannel([u1, u2])
        return await self.getLastMessageIdForChannel(channel)

    async def getLastMessageIdForChannel(self, channel: Channel) -> Channel:
        return channel.set(last_message_id=await self.getLastMessageId(channel, lsf(), 0))

    async def getLastMessageId(self, channel: Channel, before: int, after: int) -> int:
        async with self.db() as db:
            return await db.getLastMessageId(channel, before, after)

    async def getChannelMessagesCount(self, channel: Channel, before: int, after: int) -> int:
        async with self.db() as db:
            return await db.getChannelMessagesCount(channel, before, after)

    async def createDMChannel(self, recipients: List[int]) -> Channel:
        cid = mksf()
        async with self.db() as db:
            channel = await db.createDMChannel(cid, recipients)
        return channel.set(last_message_id=None)

    async def getPrivateChannels(self, user: _User) -> list:
        async with self.db() as db:
            _channels = [await self.getLastMessageIdForChannel(channel) for channel in await db.getPrivateChannels(user)]
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

    async def getChannelMessages(self, channel, limit: int, before: int=None, after: int=None) -> List[Message]:
        async with self.db() as db:
            return await db.getChannelMessages(channel, limit, before, after)

    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]:
        async with self.db() as db:
            message = await db.getMessage(channel, message_id)
        return message

    async def sendMessage(self, message: Message) -> Message:
        async with self.db() as db:
            await db.insertMessage(message)
        message.fill_defaults()
        m = await message.json
        users = await self.getRelatedUsersToChannel(message.channel_id)
        await self.mcl.broadcast("message_events", {"e": "message_create", "data": {"users": users, "message_obj": m}})
        async def _addToReadStates():
            async with self.db() as d:
                d.dontCloseOnAExit()
                c.Ctx["DB"] = d
                _u = await self.getRelatedUsersToChannel(message.channel_id)
                if message.author in _u:
                    _u.remove(message.author)
                for u in _u:
                    await self.addMessageToReadStates(u, message.channel_id)
                await d.close()
        Context().run(get_event_loop().create_task, _addToReadStates())
        return message

    async def editMessage(self, before: Message, after: Message) -> Message:
        async with self.db() as db:
            await db.editMessage(before, after)
        after.fill_defaults()
        m = await after.json
        users = await self.getRelatedUsersToChannel(after.channel_id)
        await self.mcl.broadcast("message_events", {"e": "message_update", "data": {"users": users, "message_obj": m}})
        return after

    async def deleteMessage(self, message: Message) -> None:
        async with self.db() as db:
            await db.deleteMessage(message)
        await self.mcl.broadcast("message_events", {"e": "message_delete", "data": {"message": message.id, "channel": message.channel_id}})

    async def getRelatedUsersToChannel(self, channel_id: int) -> List[int]:
        channel = await self.getChannel(channel_id)
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            return channel.recipients
        elif channel.type in (ChannelType.GUILD_CATEGORY, ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
            print(channel.guild_id)
            return [member.user_id for member in await self.getGuildMembers(GuildId(channel.guild_id))]

    async def sendTypingEvent(self, user: _User, channel: Channel) -> None:
        await self.mcl.broadcast("message_events", {"e": "typing", "data": {"user": user.id, "channel": channel.id}})

    async def addMessageToReadStates(self, uid: int, channel_id: int) -> None:
        rs = await self.getReadStates(uid, channel_id)
        count = 1
        if rs:
            count += rs[0].count
        await self.setReadState(uid, channel_id, count)

    async def setReadState(self, uid: int, channel_id: int, count: Union[int, str], last: int=None) -> None:
        async with self.db() as db:
            await db.setReadState(uid, channel_id, count, last)

    async def getReadStates(self, uid: int, channel_id: int=None) -> List[ReadState]:
        async with self.db() as db:
            return await db.getReadStates(uid, channel_id)

    async def getReadStatesJ(self, user: _User) -> list:
        states = []
        for st in await self.getReadStates(user.id):
            states.append({
                "mention_count": st.count,
                "last_pin_timestamp": await self.getLastPinTimestamp(st.channel_id),
                "last_message_id": str(st.last_read_id),
                "id": str(st.channel_id),
            })
        return states

    async def delReadStateIfExists(self, uid: int, channel_id: int) -> bool:
        async with self.db() as db:
            return await db.delReadStateIfExists(uid, channel_id)

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
        await self.mcl.broadcast("message_events", {"e": "message_ack", "data": d})

    async def getUserNote(self, uid: int, target_uid: int) -> Optional[UserNote]:
        async with self.db() as db:
            return await db.getUserNote(uid, target_uid)

    async def putUserNote(self, note: UserNote) -> None:
        async with self.db() as db:
            await db.putUserNote(note)
        await self.mcl.broadcast("user_events", {"e": "note_update", "data": {"user": note.uid, "uid": note.target_uid, "note": note.note}})

    #async def putUserConnection(self, uc: UserConnection) -> None: # TODO: implement UserConnection
    #    async with self.db() as db:
    #        await db.putUserConnection(uc)

    async def putAttachment(self, attachment: Attachment) -> None:
        async with self.db() as db:
            await db.putAttachment(attachment)

    async def getAttachment(self, aid: int) -> Optional[Attachment]:
        async with self.db() as db:
            return await db.getAttachment(aid)

    async def getAttachmentByUUID(self, uuid: str) -> Optional[Attachment]:
        async with self.db() as db:
            return await db.getAttachmentByUUID(uuid)

    async def updateAttachment(self, before: Attachment, after: Attachment) -> None:
        async with self.db() as db:
            await db.updateAttachment(before, after)

    async def getUserByChannelId(self, channel_id: int, uid: int) -> Optional[User]:
        if not (channel := await self.getChannel(channel_id)):
            return None
        return await self.getUserByChannel(channel, uid)

    async def getUserByChannel(self, channel: Channel, uid: int) -> Optional[User]:
        if channel.type in (ChannelType.DM, ChannelType.GROUP_DM):
            if uid in channel.recipients:
                return await self.getUser(uid)
        elif channel.type in (ChannelType.GUILD_CATEGORY, ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
            return await self.getGuildMember(GuildId(channel.guild_id), uid)

    async def setFrecencySettingsBytes(self, uid: int, proto: bytes) -> None:
        proto = _b64encode(proto).decode("utf8")
        await self.setFrecencySettings(uid, proto)

    async def setFrecencySettings(self, uid: int, proto: str) -> None:
        async with self.db() as db:
            await db.setFrecencySettings(uid, proto)

    async def getFrecencySettings(self, user: _User) -> str:
        async with self.db() as db:
            return await db.getFrecencySettings(user.id)

    async def sendVerificationEmail(self, user: User) -> None:
        key = new(self.key, str(user.id).encode('utf-8'), sha256).digest()
        t = int(time())
        sig = b64encode(new(key, f"{user.id}:{user.email}:{t}".encode('utf-8'), sha256).digest())
        token = b64encode(jdumps({"id": user.id, "email": user.email, "time": t}))
        token += f".{sig}"
        link = f"https://{Config('CLIENT_HOST')}/verify#token={token}"
        await EmailMsg(user.email, "Confirm your e-mail in YEPCord",
                       f"Thank you for signing up for a YEPCord account!\nFirst you need to make sure that you are you! Click to verify your email address:\n{link}").send()

    async def verifyEmail(self, user: User, token: str) -> None:
        try:
            data, sig = token.split(".")
            data = jloads(b64decode(data).decode("utf8"))
            sig = b64decode(sig)
            t = data["time"]
            if data["email"] != user.email or data["id"] != user.id or time()-t > 600:
                raise Exception
            key = new(self.key, str(user.id).encode('utf-8'), sha256).digest()
            vsig = new(key, f"{user.id}:{user.email}:{t}".encode('utf-8'), sha256).digest()
            if sig != vsig:
                raise Exception
        except:
            raise InvalidDataErr(400, mkError(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
        async with self.db() as db:
            await db.verifyEmail(user.id)

    async def getUserByEmail(self, email: str) -> Optional[User]:
        async with self.db() as db:
            return await db.getUserByEmail(email)

    async def changeUserEmail(self, user: User, email: str) -> None:
        email = email.lower()
        if user.email == email:
            return
        async with self.db() as db:
            if await db.getUserByEmail(email):
                raise InvalidDataErr(400, mkError(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}}))
            await db.changeUserEmail(user.id, email)
            user.email = email

    async def sendMfaChallengeEmail(self, user: User, nonce: str) -> None:
        code = self.mfaNonceToCode(nonce)
        await EmailMsg(user.email, f"Your one-time verification key is {code}",
                        f"It looks like you're trying to view your account's backup codes.\n"+
                        f"This verification key expires in 30 minutes. This key is extremely sensitive, treat it like a password and do not share it with anyone.\n"+
                        f"Enter it in the app to unlock your backup codes:\n{code}").send()

    def mfaNonceToCode(self, nonce: str) -> str:
        nonce = b64decode(nonce)
        b = nonce[0]
        nonce = nonce[1:]
        if b == 1:
            nonce = nonce[::-1]
        elif b != 0:
            return ""
        return b64encode(new(self.key, nonce, sha256).digest()).replace("-", "").replace("_", "")[:8].upper()

    async def createDMGroupChannel(self, user: User, recipients: list) -> Channel:
        if user.id not in recipients:
            recipients.append(user.id)
        async with self.db() as db:
            return await db.createDMGroupChannel(mksf(), recipients, user.id)

    async def sendDMChannelCreateEvent(self, channel: Channel, *, users=None) -> None:
        if not users:
            users = await self.getRelatedUsersToChannel(channel.id)
        await self.mcl.broadcast("channel_events", {"e": "dmchannel_create", "data": {"users": users, "channel_id": channel.id}})

    async def sendDMRepicientAddEvent(self, users: List[int], channel_id: int, uid: int) -> None:
        await self.mcl.broadcast("channel_events", {"e": "dm_recipient_add", "data": {"users": users, "channel_id": channel_id, "user": uid}})

    async def sendDMRepicientRemoveEvent(self, users: List[int], channel_id: int, uid: int) -> None:
        await self.mcl.broadcast("channel_events", {"e": "dm_recipient_remove", "data": {"users": users, "channel_id": channel_id, "user": uid}})

    async def sendDMChannelDeleteEvent(self, channel: Channel, users: List[int]) -> None:
        channel = {
                "type": channel.type,
                "owner_id": str(channel.owner_id),
                "name": channel.name,
                "last_message_id": str(channel.last_message_id),
                "id": str(channel.id),
                "icon": channel.icon,
                "flags": channel.flags
            }
        await self.mcl.broadcast("channel_events", {"e": "dmchannel_delete", "data": {"users": users, "channel": channel}})

    async def addUserToGroupDM(self, channel: Channel, uid: int) -> None:
        nChannel = channel.copy()
        nChannel.recipients.append(uid)
        await self.updateChannelDiff(channel, nChannel)

    async def removeUserFromGroupDM(self, channel: Channel, uid: int) -> None:
        nChannel = channel.copy()
        nChannel.recipients.remove(uid)
        await self.updateChannelDiff(channel, nChannel)

    async def updateChannelDiff(self, before: Channel, after: Channel) -> None:
        async with self.db() as db:
            await db.updateChannelDiff(before, after)

    async def sendDMChannelUpdateEvent(self, channel: Channel) -> None:
        users = await self.getRelatedUsersToChannel(channel.id)
        await self.mcl.broadcast("channel_events", {"e": "dmchannel_update", "data": {"users": users, "channel_id": channel.id}})

    async def deleteChannel(self, channel: Channel) -> None:
        async with self.db() as db:
            await db.deleteChannel(channel)

    async def deleteMessagesAck(self, channel: Channel, user: User) -> None:
        async with self.db() as db:
            await db.deleteMessagesAck(channel, user)

    async def pinMessage(self, message: Message) -> None:
        async with self.db() as db:
            if len(await db.getPinnedMessages(message.channel_id)) >= 50:
                raise InvalidDataErr(400, mkError(30003))
            await db.pinMessage(message)
        users = await self.getRelatedUsersToChannel(message.channel_id)
        await self.mcl.broadcast("channel_events", {"e": "channel_pins_update", "data": {"users": users, "channel_id": message.channel_id}})

    async def getLastPinnedMessage(self, channel_id: int) -> Optional[Message]:
        async with self.db() as db:
            return await db.getLastPinnedMessage(channel_id)

    async def getLastPinTimestamp(self, channel_id: int) -> str:
        m = await self.getLastPinnedMessage(channel_id)
        return datetime.utcfromtimestamp(m.extra_data["pinned_at"] if m else 0).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    async def getPinnedMessages(self, channel_id: int) -> List[Message]:
        async with self.db() as db:
            return await db.getPinnedMessages(channel_id)

    async def unpinMessage(self, message: Message) -> None:
        async with self.db() as db:
            await db.unpinMessage(message)
        users = await self.getRelatedUsersToChannel(message.channel_id)
        await self.mcl.broadcast("channel_events", {"e": "channel_pins_update", "data": {"users": users, "channel_id": message.channel_id}})

    async def addReaction(self, reaction: Reaction, channel: Channel) -> None:
        async with self.db() as db:
            await db.addReaction(reaction)
        users = await self.getRelatedUsersToChannel(channel.id)
        emoji = {"id": str(reaction.emoji_id) if reaction.emoji_id is not None else None, "name": reaction.emoji_name}
        await self.mcl.broadcast("message_events", {"e": "reaction_add", "data": {"users": users, "message_id": reaction.message_id, "channel_id": channel.id, "user_id": reaction.user_id, "emoji": emoji}})

    async def removeReaction(self, reaction: Reaction, channel: Channel) -> None:
        async with self.db() as db:
            await db.removeReaction(reaction)
        users = await self.getRelatedUsersToChannel(channel.id)
        emoji = {"id": str(reaction.emoji_id) if reaction.emoji_id is not None else None, "name": reaction.emoji_name}
        await self.mcl.broadcast("message_events", {"e": "reaction_remove", "data": {"users": users, "message_id": reaction.message_id, "channel_id": channel.id, "user_id": reaction.user_id, "emoji": emoji}})

    async def getMessageReactions(self, message_id: int, user_id: int) -> list:
        async with self.db() as db:
            return await db.getMessageReactions(message_id, user_id)

    async def getReactedUsers(self, reaction: Reaction, limit: int) -> List[dict]:
        users = []
        async with self.db() as db:
            users_ids = await db.getReactedUsersIds(reaction, limit)
        for uid in users_ids:
            data = await self.getUserData(UserId(uid))
            users.append({
                "id": str(uid),
                "username": data.username,
                "avatar": data.avatar,
                "avatar_decoration": data.avatar_decoration,
                "discriminator": data.s_discriminator,
                "public_flags": data.public_flags
            })
        return users

    async def searchMessages(self, filter: SearchFilter) -> Tuple[List[Message], int]:
        async with self.db() as db:
            return await db.searchMessages(filter)

    async def createInvite(self, channel: Channel, inviter: User, max_age: int) -> Invite:
        invite = Invite(mksf(), channel.id, inviter.id, int(time()), max_age)
        async with self.db() as db:
            await db.putInvite(invite)
        return invite

    async def getInvite(self, invite_id: int) -> Optional[Invite]:
        async with self.db() as db:
            return await db.getInvite(invite_id)

    async def createGuild(self, user: User, name: str) -> Guild:
        guild = Guild(mksf(), user.id, name, roles=[], system_channel_id=0)
        roles = [Role(guild.id, guild.id, "@everyone", permissions=1071698660929)]
        channels = []
        channels.append(Channel(mksf(), ChannelType.GUILD_CATEGORY, guild_id=guild.id, name="Text Channels", position=0,
                                permission_overwrites=[], flags=0, rate_limit=0))
        channels.append(Channel(mksf(), ChannelType.GUILD_CATEGORY, guild_id=guild.id, name="Voice Channels", position=0,
                                permission_overwrites=[], flags=0, rate_limit=0))
        channels.append(Channel(mksf(), ChannelType.GUILD_TEXT, guild_id=guild.id, name="general", position=0,
                                parent_id=channels[0].id, permission_overwrites=[], flags=0, rate_limit=0))
        channels.append(Channel(mksf(), ChannelType.GUILD_VOICE, guild_id=guild.id, name="General", position=0,
                                parent_id=channels[1].id, bitrate=64000, user_limit=0, permission_overwrites=[], flags=0, rate_limit=0))
        members = [GuildMember(user.id, guild.id, int(time()))]

        guild.system_channel_id = channels[1].id
        guild.roles.append(roles[0].id)
        async with self.db() as db:
            await db.createGuild(guild, roles, channels, members)
        guild.fill_defaults()
        Ctx["with_members"] = True
        Ctx["with_channels"] = True
        await self.mcl.broadcast("guild_events", {"e": "guild_create", "data": {"users": [user.id], "guild_obj": await guild.json}})
        Ctx["with_members"] = False
        Ctx["with_channels"] = False
        return guild

    async def getRole(self, role_id: int) -> Role:
        async with self.db() as db:
            return await db.getRole(role_id)

    async def getGuildMember(self, guild: _Guild, user_id: int) -> Optional[GuildMember]:
        async with self.db() as db:
            return await db.getGuildMember(guild, user_id)

    async def getGuildMembers(self, guild: _Guild) -> List[GuildMember]:
        async with self.db() as db:
            return await db.getGuildMembers(guild)

    async def getGuildMembersIds(self, guild: _Guild) -> List[int]:
        async with self.db() as db:
            return await db.getGuildMembersIds(guild)

    async def getGuildChannels(self, guild: Guild) -> List[Channel]:
        async with self.db() as db:
            return await db.getGuildChannels(guild)

    async def getUserGuilds(self, user: User) -> List[Guild]:
        async with self.db() as db:
            return await db.getUserGuilds(user)

    async def getGuildMemberCount(self, guild: _Guild) -> int:
        async with self.db() as db:
            return await db.getGuildMemberCount(guild)

    async def sendSettingsProtoUpdateEvent(self, uid: int, proto: str, stype: int) -> None:
        await execute_after(self.mcl.broadcast("user_events", {"e": "settings_proto_update", "data": {"user": uid, "proto": proto, "stype": stype}}), 1)

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        async with self.db() as db:
            return await db.getGuild(guild_id)

    async def updateGuildDiff(self, before: Guild, after: Guild) -> None:
        async with self.db() as db:
            await db.updateGuildDiff(before, after)
        await self.mcl.broadcast("guild_events", {"e": "guild_update", "data": {"users": await self.getGuildMembersIds(before), "guild_obj": await after.json}})

    async def blockUser(self, user: User, uid: int) -> None:
        rel = await self.getRelationship(user.id, uid)
        if rel and rel.type != RelationshipType.BLOCK:
            async with self.db() as db:
                await db.delRelationship(rel)
        elif rel and rel.type == RelationshipType.BLOCK and rel.u1 == user.id:
            return
        async with self.db() as db:
            await db.insertRelationShip(Relationship(user.id, uid, RelationshipType.BLOCK))
        if rel and rel.type != RelationshipType.BLOCK:
            await self.mcl.broadcast("user_events", {"e": "relationship_del", "data": {"current_user": uid, "target_user": user.id, "type": rel.discord_type(uid)}})
        await self.mcl.broadcast("user_events", {"e": "relationship_add", "data": {"current_user": user.id, "target_user": uid, "type": RelationshipType.BLOCK}})

    async def getEmojis(self, guild_id: int) -> List[Emoji]:
        async with self.db() as db:
            return await db.getEmojis(guild_id)

    async def addEmoji(self, emoji: Emoji, guild: Guild) -> None:
        async with self.db() as db:
            await db.addEmoji(emoji)
        await self.mcl.broadcast("guild_events", {"e": "emojis_update", "data": {"users": await self.getGuildMembersIds(guild), "guild_id": guild.id}})

    async def getEmoji(self, emoji_id: int) -> Optional[Emoji]:
        async with self.db() as db:
            return await db.getEmoji(emoji_id)

    async def deleteEmoji(self, emoji: Emoji, guild: Guild) -> None:
        async with self.db() as db:
            await db.deleteEmoji(emoji)
        await self.mcl.broadcast("guild_events", {"e": "emojis_update", "data": {"users": await self.getGuildMembersIds(guild), "guild_id": guild.id}})

    async def getEmojiByReaction(self, reaction: str) -> Optional[Emoji]:
        try:
            name, emoji_id = reaction.split(":")
            emoji_id = int(emoji_id)
            if "~" in name:
                name = name.split("~")[0]
        except ValueError:
            return
        async with self.db() as db:
            if not (emoji := await db.getEmoji(emoji_id)):
                return
        return None if emoji.name != name else emoji

    async def sendChannelUpdateEvent(self, channel: Channel) -> None:
        await self.mcl.broadcast("guild_events", {"e": "channel_update",
                                                  "data": {"users": await self.getGuildMembersIds(GuildId(channel.guild_id)),
                                                           "channel_obj": await channelInfoResponse(channel)}})

    async def createGuildChannel(self, channel: Channel) -> Channel:
        async with self.db() as db:
            await db.createGuildChannel(channel)
        return await self.getChannel(channel.id)

    async def sendChannelCreateEvent(self, channel: Channel) -> None:
        await self.mcl.broadcast("guild_events", {"e": "channel_create",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(channel.guild_id)),
                                                      "channel_obj": await channelInfoResponse(channel)}})

import server.ctx as c
c._getCore = lambda: Core.getInstance()
from server.ctx import Ctx