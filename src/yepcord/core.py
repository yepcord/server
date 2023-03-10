from asyncio import get_event_loop
from base64 import b64encode as _b64encode
from contextvars import Context
from datetime import datetime
from hashlib import sha256
from hmac import new
from json import loads as jloads, dumps as jdumps
from os import urandom
from random import randint
from time import time
from typing import Optional, Union, List, Tuple, Dict

from bcrypt import hashpw, gensalt, checkpw

from .classes.channel import Channel, PermissionOverwrite, _Channel
from .classes.guild import Emoji, Invite, Guild, Role, GuildId, _Guild, GuildBan, AuditLogEntry, GuildTemplate, Webhook, \
    Sticker, ScheduledEvent
from .classes.message import Message, Attachment, Reaction, SearchFilter, ReadState
from .classes.other import EmailMsg, Singleton, JWT
from .classes.user import Session, UserSettings, UserNote, User, UserId, _User, UserData, Relationship, GuildMember
from .config import Config
from .databases import MySQL
from .enums import RelationshipType, ChannelType
from .errors import InvalidDataErr, MfaRequiredErr, Errors
from .pubsub_client import Broadcaster
from .snowflake import Snowflake
from .utils import b64encode, b64decode, MFA, execute_after, int_length, NoneType


class CDN(Singleton):
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core

    def __getattr__(self, item):
        return getattr(self.storage, item)


class Core(Singleton):
    def __init__(self, key=None, db=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b''
        self.db = MySQL() if not db else db
        self.pool = None
        self.loop = loop or get_event_loop()
        self.mcl = Broadcaster("http")
        self._cache = {}

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

    def prepPassword(self, password: str, uid: int) -> bytes:
        """
        Prepares user password for hashing
        :param password:
        :param uid:
        :return:
        """
        password = password.encode("utf8")
        password += uid.to_bytes(int_length(uid), "big")
        return password.replace(b"\x00", b'')

    def hashPassword(self, uid: int, password: str) -> str:
        password = self.prepPassword(password, uid)
        return hashpw(password, gensalt()).decode("utf8")

    def generateSessionSignature(self) -> str:
        return b64encode(urandom(32))

    def generateKey(self) -> str:
        return b64encode(urandom(16))

    async def getRandomDiscriminator(self, login: str) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            if not await self.getUserByUsername(login, d):
                return d

    async def register(self, uid: int, login: str, email: Optional[str], password: str, birth: str, locale: str="en-US", invite: Optional[str]=None) -> Session:
        email = email.lower()
        async with self.db() as db:
            if await db.getUserByEmail(email):
                raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}}))
        password = self.hashPassword(uid, password)
        key = self.generateKey()
        session = int.from_bytes(urandom(6), "big")
        signature = self.generateSessionSignature()

        discriminator = await self.getRandomDiscriminator(login)
        if discriminator is None:
            raise InvalidDataErr(400, Errors.make(50035, {"login": {"code": "USERNAME_TOO_MANY_USERS", "message": "Too many users have this username, please try another."}}))

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
        if not user or not checkpw(self.prepPassword(password, user.id), user.password.encode("utf8")):
            raise InvalidDataErr(400, Errors.make(50035, {"login": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}, "password": {"code": "INVALID_LOGIN", "message": "Invalid login or password."}}))
        settings = await user.settings
        if settings.mfa:
            _sid = urandom(12)
            sid = int.from_bytes(_sid, "big")
            raise MfaRequiredErr(user.id, b64encode(_sid), self.generateMfaTicketSignature(user, sid))
        return await self.createSession(user.id)

    async def createSession(self, uid: int) -> Optional[Session]:
        if await self.getUser(uid):
            sid = int.from_bytes(urandom(6), "big")
            sig = self.generateSessionSignature()
            session = Session(uid, sid, sig)
            async with self.db() as db:
                await db.insertSession(session)
            return session

    async def getUser(self, uid: int, allow_deleted: bool=True) -> Optional[User]:
        async with self.db() as db:
            return await db.getUser(uid, allow_deleted)

    async def validSession(self, session: Session) -> bool:
        async with self.db() as db:
            return await db.validSession(session)

    async def getUserSettings(self, user: _User) -> Optional[UserSettings]:
        async with self.db() as db:
            return await db.getUserSettings(user)

    async def getUserData(self, user: _User) -> Optional[UserData]:
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

    async def setUserdataDiff(self, before: UserData, after: UserData) -> None:
        async with self.db() as db:
            await db.setUserDataDiff(before, after)

    async def getUserProfile(self, uid: int, cUser: _User) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid, False)):
            raise InvalidDataErr(404, Errors.make(10013))
        return user

    async def checkUserPassword(self, user: User, password: str) -> bool:
        return checkpw(self.prepPassword(password, user.id), user.password.encode("utf8"))

    async def changeUserDiscriminator(self, user: User, discriminator: int, changed_username: bool=False) -> bool:
        username = (await user.data).username
        if await self.getUserByUsername(username, discriminator):
            if changed_username:
                return False
            raise InvalidDataErr(400, Errors.make(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS",
                                                                       "message": "This discriminator already used by someone. Please enter something else."}}))
        data = await user.data
        ndata = data.copy(discriminator=discriminator)
        async with self.db() as db:
            await db.setUserDataDiff(data, ndata)
        return True

    async def changeUserName(self, user: User, username: str) -> None:
        discriminator = (await user.data).discriminator
        if await self.getUserByUsername(username, discriminator):
            discriminator = await self.getRandomDiscriminator(username)
            if discriminator is None:
                raise InvalidDataErr(400, Errors.make(50035, {"username": {"code": "USERNAME_TOO_MANY_USERS", "message": "This name is used by too many users. Please enter something else or try again."}}))
        data = await user.data
        ndata = data.copy(discriminator=discriminator, username=username)
        async with self.db() as db:
            await db.setUserDataDiff(data, ndata)

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        async with self.db() as db:
            return await db.getUserByUsername(username, discriminator)

    async def checkRelationShipAvailable(self, tUser: _User, cUser: _User) -> None:
        async with self.db() as db:
            if not await db.relationShipAvailable(tUser, cUser):
                raise InvalidDataErr(400, Errors.make(80007))
        return None # TODO: check for mutual guilds or mutual friends

    async def reqRelationship(self, tUser: _User, cUser: _User) -> None:
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

    async def getRelatedUsers(self, user: _User, only_ids=False) -> list:
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
            for channel in await db.getPrivateChannels(user, with_hidden=True):
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
                    users.append(await d.json)
        return users

    async def accRelationship(self, user: _User, uid: int) -> None:
        async with self.db() as db:
            await db.updateRelationship(user.id, uid, RelationshipType.FRIEND, RelationshipType.PENDING)
        channel = await self.getDMChannelOrCreate(user.id, uid)
        await self.mcl.broadcast("user_events", {"e": "relationship_acc", "data": {"target_user": uid, "current_user": user.id, "channel_id": channel.id}})

    async def delRelationship(self, user: _User, uid: int) -> None:
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

    async def changeUserPassword(self, user: _User, new_password: str) -> None:
        new_password = self.hashPassword(user.id, new_password)
        async with self.db() as db:
            await db.changeUserPassword(user, new_password)

    async def logoutUser(self, sess: Session) -> None:
        async with self.db() as db:
            await db.logoutUser(sess)

    async def getMfa(self, user: User) -> Optional[MFA]:
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

    async def getBackupCodes(self, user: _User) -> List[Tuple[str, bool]]:
        async with self.db() as db:
            return await db.getBackupCodes(user)

    def generateMfaTicketSignature(self, user: User, sid: int) -> str:
        payload = {
            "user_id": user.id,
            "session_id": sid
        }
        token = JWT.encode(payload, self.key+b64decode(user.key), time()+300)
        return b64encode(token)

    def verifyMfaTicketSignature(self, user: User, sid: int, token: str) -> bool:
        if not (payload := JWT.decode(token, self.key+b64decode(user.key))):
            return False
        if payload["user_id"] != user.id: return False
        if payload["session_id"] != sid: return False
        return True

    async def getMfaFromTicket(self, ticket: str) -> Optional[MFA]:
        try:
            uid, sid, sig = ticket.split(".")
            uid = jloads(b64decode(uid).decode("utf8"))[0]
            sid = int.from_bytes(b64decode(sid), "big")
            sig = b64decode(sig).decode("utf8")
        except (ValueError, IndexError):
            return
        if not (user := await self.getUser(uid)):
            return
        if not self.verifyMfaTicketSignature(user, sid, sig):
            return
        settings = await user.settings
        return MFA(settings.mfa, uid)

    async def generateUserMfaNonce(self, user: User) -> Tuple[str, str]:
        mfa = await self.getMfa(user)
        exp = time() + 600
        code = b64encode(urandom(16))
        nonce = JWT.encode({"type": "normal", "code": code}, self.key + b64decode(mfa.key), exp)
        rnonce = JWT.encode({"type": "regenerate", "code": code}, self.key + b64decode(mfa.key), exp)
        return nonce, rnonce

    async def verifyUserMfaNonce(self, user: User, nonce: str, regenerate: bool) -> None:
        mfa = await self.getMfa(user)
        if not (payload := JWT.decode(nonce, self.key + b64decode(mfa.key))):
            raise InvalidDataErr(400, Errors.make(60011))
        nonce_type = "normal" if not regenerate else "regenerate"
        if nonce_type != payload["type"]:
            raise InvalidDataErr(400, Errors.make(60011))

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
        if await self.isDmChannelHidden(UserId(u1), channel):
            await self.unhideDmChannel(UserId(u1), channel)
            await self.sendDMChannelCreateEvent(channel=channel, users=[u1])
        return await self.getLastMessageIdForChannel(channel)

    async def getLastMessageIdForChannel(self, channel: Channel) -> Channel:
        return channel.set(last_message_id=await self.getLastMessageId(channel, Snowflake.makeId(False), 0))

    async def getLastMessageId(self, channel: Channel, before: int, after: int) -> int:
        async with self.db() as db:
            return await db.getLastMessageId(channel, before, after)

    async def getChannelMessagesCount(self, channel: Channel, before: int, after: int) -> int:
        async with self.db() as db:
            return await db.getChannelMessagesCount(channel, before, after)

    async def createDMChannel(self, recipients: List[int]) -> Channel:
        cid = Snowflake.makeId()
        async with self.db() as db:
            channel = await db.createDMChannel(cid, recipients)
        return channel.set(last_message_id=None)

    async def getPrivateChannels(self, user: _User, with_hidden: bool=False) -> List[Channel]:
        async with self.db() as db:
            return [await self.getLastMessageIdForChannel(channel) for channel in await db.getPrivateChannels(user, with_hidden=with_hidden)]

    async def getChannelMessages(self, channel, limit: int, before: int=0, after: int=0) -> List[Message]:
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

    async def sendMessageDeleteEvent(self, message: Message) -> None:
        await self.mcl.broadcast("message_events", {"e": "message_delete",
                                                    "data": {"message": message.id, "channel": message.channel_id,
                                                             "guild": message.guild_id}})

    async def deleteMessage(self, message: Message) -> None:
        async with self.db() as db:
            await db.deleteMessage(message)
        await self.sendMessageDeleteEvent(message)

    async def getRelatedUsersToChannel(self, channel_id: int) -> List[int]:
        channel = await self.getChannel(channel_id)
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            return channel.recipients
        elif channel.type in (ChannelType.GUILD_CATEGORY, ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE):
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
        await self.mcl.broadcast("user_events", {"e": "note_update", "data": {"user": note.user_id, "uid": note.note_user_id, "note": note.note}})

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
            raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID", "message": "Invalid token."}}))
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
                raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}}))
            await db.changeUserEmail(user.id, email)
            user.email = email

    async def sendMfaChallengeEmail(self, user: User, nonce: str) -> None:
        code = await self.mfaNonceToCode(user, nonce)
        await EmailMsg(user.email, f"Your one-time verification key is {code}",
                        f"It looks like you're trying to view your account's backup codes.\n"+
                        f"This verification key expires in 10 minutes. This key is extremely sensitive, treat it like a password and do not share it with anyone.\n"+
                        f"Enter it in the app to unlock your backup codes:\n{code}").send()

    async def mfaNonceToCode(self, user: User, nonce: str) -> Optional[str]:
        mfa = await self.getMfa(user)
        if not (payload := JWT.decode(nonce, self.key + b64decode(mfa.key))):
            return
        token = JWT.encode({"code": payload["code"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

    async def createDMGroupChannel(self, user: User, recipients: list, name: Optional[str]=None) -> Channel:
        if user.id not in recipients:
            recipients.append(user.id)
        async with self.db() as db:
            return await db.createDMGroupChannel(Snowflake.makeId(), recipients, user.id, name)

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
                raise InvalidDataErr(400, Errors.make(30003))
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

    async def putInvite(self, invite: Invite) -> None:
        async with self.db() as db:
            await db.putInvite(invite)

    async def createInvite(self, channel: Channel, inviter: User, **kwargs) -> Invite:
        guild_id = channel.guild_id
        invite = Invite(Snowflake.makeId(), channel.id, inviter.id, int(time()), guild_id=guild_id, **kwargs)
        await self.putInvite(invite)
        return invite

    async def getInvite(self, invite_id: int) -> Optional[Invite]:
        async with self.db() as db:
            return await db.getInvite(invite_id)

    async def createGuild(self, guild_id: int, user: User, name: str, **kwargs) -> Guild:
        guild = Guild(guild_id, user.id, name, system_channel_id=0, features=[], **kwargs)
        roles = [Role(guild.id, guild.id, "@everyone", permissions=1071698660929)]
        channels = []
        channels.append(Channel(Snowflake.makeId(), ChannelType.GUILD_CATEGORY, guild_id=guild.id, name="Text Channels", position=0,
                                flags=0, rate_limit=0))
        channels.append(Channel(Snowflake.makeId(), ChannelType.GUILD_CATEGORY, guild_id=guild.id, name="Voice Channels", position=0,
                                flags=0, rate_limit=0))
        channels.append(Channel(Snowflake.makeId(), ChannelType.GUILD_TEXT, guild_id=guild.id, name="general", position=0,
                                parent_id=channels[0].id, flags=0, rate_limit=0))
        channels.append(Channel(Snowflake.makeId(), ChannelType.GUILD_VOICE, guild_id=guild.id, name="General", position=0,
                                parent_id=channels[1].id, bitrate=64000, user_limit=0, flags=0, rate_limit=0))
        members = [GuildMember(user.id, guild.id, int(time()))]

        guild.system_channel_id = channels[2].id
        async with self.db() as db:
            await db.createGuild(guild, roles, channels, members)
        guild.fill_defaults()
        Ctx["with_members"] = True
        Ctx["with_channels"] = True
        await self.sendGuildCreateEvent(guild, [user.id])
        Ctx["with_members"] = False
        Ctx["with_channels"] = False
        return guild

    async def createGuildFromTemplate(self, guild_id: int, user: User, template: GuildTemplate, name: Optional[str], icon: Optional[str]) -> Guild:
        serialized = template.serialized_guild
        serialized["name"] = name or serialized["name"]
        serialized["icon"] = icon
        replaced_ids: Dict[Union[int, NoneType], Union[int, NoneType]] = {None: None, 0: guild_id}
        roles = []
        channels = []
        overwrites = []

        for role in serialized["roles"]:
            if role["id"] not in replaced_ids:
                replaced_ids[role["id"]] = Snowflake.makeId()
            role["id"] = replaced_ids[role["id"]]
            roles.append(Role(guild_id=guild_id, **role))

        for channel in serialized["channels"]:
            if channel["id"] not in replaced_ids:
                replaced_ids[channel["id"]] = Snowflake.makeId()
            channel["id"] = channel_id = replaced_ids[channel["id"]]
            channel["parent_id"] = replaced_ids.get(channel["parent_id"], None)
            for overwrite in channel["permission_overwrites"]:
                overwrite["target_id"] = replaced_ids[overwrite["id"]]
                overwrite["channel_id"] = channel_id
                del overwrite["id"]
                overwrites.append(PermissionOverwrite(**overwrite))
            del channel["permission_overwrites"]

            channel["rate_limit"] = channel["rate_limit_per_user"]
            channel["default_auto_archive"] = channel["default_auto_archive_duration"]
            del channel["rate_limit_per_user"]
            del channel["default_auto_archive_duration"]

            del channel["available_tags"]
            del channel["template"]
            del channel["default_reaction_emoji"]
            del channel["default_thread_rate_limit_per_user"]
            del channel["default_sort_order"]
            del channel["default_forum_layout"]

            channels.append(Channel(guild_id=guild_id, **channel))

        serialized["afk_channel_id"] = replaced_ids.get(serialized["afk_channel_id"], None)
        serialized["system_channel_id"] = replaced_ids.get(serialized["system_channel_id"], None)

        del serialized["roles"]
        del serialized["channels"]

        guild = Guild(guild_id, user.id, features=[], **serialized)
        members = [GuildMember(user.id, guild.id, int(time()))]

        async with self.db() as db:
            await db.createGuild(guild, roles, channels, members)
            for overwrite in overwrites:
                await db.putPermissionOverwrite(overwrite)
        guild.fill_defaults()
        Ctx["with_members"] = True
        Ctx["with_channels"] = True
        await self.sendGuildCreateEvent(guild, [user.id])
        Ctx["with_members"] = False
        Ctx["with_channels"] = False
        return guild

    async def sendGuildCreateEvent(self, guild: Guild, users: List[int]) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_create", "data": {"users": users, "guild_obj": await guild.json}})

    async def getRole(self, role_id: int) -> Role:
        async with self.db() as db:
            return await db.getRole(role_id)

    async def getRoles(self, guild: Guild) -> List[Role]:
        async with self.db() as db:
            return await db.getRoles(guild)

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

    async def getUserGuilds(self, user: _User) -> List[Guild]:
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

    async def sendGuildEmojisUpdatedEvent(self, guild: Guild) -> None:
        await self.mcl.broadcast("guild_events", {"e": "emojis_update",
                                                  "data": {"users": await self.getGuildMembersIds(guild),
                                                           "guild_id": guild.id}})

    async def addEmoji(self, emoji: Emoji, guild: Guild) -> None:
        async with self.db() as db:
            await db.addEmoji(emoji)
        await self.sendGuildEmojisUpdatedEvent(guild)

    async def getEmoji(self, emoji_id: int) -> Optional[Emoji]:
        async with self.db() as db:
            return await db.getEmoji(emoji_id)

    async def deleteEmoji(self, emoji: Emoji, guild: Guild) -> None:
        async with self.db() as db:
            await db.deleteEmoji(emoji)
        await self.sendGuildEmojisUpdatedEvent(guild)

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
                                                           "channel_obj": await channel.json}})

    async def createGuildChannel(self, channel: Channel) -> Channel:
        async with self.db() as db:
            await db.createGuildChannel(channel)
        return await self.getChannel(channel.id)

    async def sendChannelCreateEvent(self, channel: Channel) -> None:
        await self.mcl.broadcast("guild_events", {"e": "channel_create",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(channel.guild_id)),
                                                      "channel_obj": await channel.json}})

    async def sendGuildChannelDeleteEvent(self, channel: Channel) -> None:
        await self.mcl.broadcast("guild_events", {"e": "channel_delete",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(channel.guild_id)),
                                                      "channel_obj": await channel.json}})

    async def createGuildMember(self, guild: Guild, user: _User) -> GuildMember:
        member = GuildMember(user.id, guild.id, int(time()))
        async with self.db() as db:
            await db.createGuildMember(member)
        return member

    async def getGuildInvites(self, guild: Guild) -> List[Invite]:
        async with self.db() as db:
            return await db.getGuildInvites(guild)

    async def deleteInvite(self, invite: Invite) -> None:
        async with self.db() as db:
            await db.deleteInvite(invite)

    async def sendInviteDeleteEvent(self, invite: Invite) -> None:
        guild = await self.getGuild(invite.guild_id)
        await self.mcl.broadcast("guild_events",
                                 {"e": "invite_delete", "data": {
                                     "users": [guild.owner_id],
                                     "payload": {
                                         "guild_id": str(invite.guild_id),
                                         "code": invite.code,
                                         "channel_id": str(invite.channel_id)
                                     }}})

    async def deleteGuildMember(self, member: GuildMember):
        async with self.db() as db:
            await db.deleteGuildMember(member)

    async def sendGuildDeleteEvent(self, guild: Guild, user: _User) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_delete", "data": {"users": [user.id], "guild_id": guild.id}})

    async def sendGuildMemberRemoveEvent(self, guild: Guild, user: User) -> None:
        user_obj = await (await user.userdata).json
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_member_remove", "data": {"users": [user.id], "guild_id": guild.id,
                                                                       "user_obj": user_obj}})

    async def banGuildMember(self, member: GuildMember, reason: str=None) -> None:
        async with self.db() as db:
            await db.banGuildMember(member, reason)

    async def sendGuildBanAddEvent(self, guild: Guild, user: User) -> None:
        user_obj = await (await user.userdata).json
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_ban_add", "data": {"users": [guild.owner_id], "guild_id": guild.id,
                                                                       "user_obj": user_obj}})

    async def getGuildBan(self, guild: Guild, user_id: int) -> Optional[GuildBan]:
        async with self.db() as db:
            return await db.getGuildBan(guild, user_id)

    async def getGuildBans(self, guild: Guild) -> List[GuildBan]:
        async with self.db() as db:
            return await db.getGuildBans(guild)

    async def bulkDeleteGuildMessagesFromBanned(self, guild: Guild, user_id: int, after_id: int) -> Dict[int, List[int]]:
        async with self.db() as db:
            return await db.bulkDeleteGuildMessagesFromBanned(guild, user_id, after_id)

    async def sendMessageBulkDeleteEvent(self, guild_id: int, channel_id: int, messages_ids: List[int]) -> None:
        users = await self.getRelatedUsersToChannel(channel_id)
        await self.mcl.broadcast("message_events", {"e": "message_delete_bulk", "data": {"users": users,
                                                                                         "guild_id": guild_id,
                                                                                         "channel_id": channel_id,
                                                                                         "messages": messages_ids}})

    async def createGuildRole(self, role: Role) -> None:
        async with self.db() as db:
            return await db.createGuildRole(role)

    async def sendGuildRoleCreateEvent(self, role: Role) -> None:
        await self.mcl.broadcast("guild_events", {"e": "role_create",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(role.guild_id)),
                                                      "guild_id": role.guild_id,
                                                      "role_obj": await role.json}})

    async def updateRoleDiff(self, before: Role, after: Role) -> None:
        async with self.db() as db:
            await db.updateRoleDiff(before, after)

    async def sendGuildRoleUpdateEvent(self, role: Role) -> None:
        await self.mcl.broadcast("guild_events", {"e": "role_update",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(role.guild_id)),
                                                      "guild_id": role.guild_id,
                                                      "role_obj": await role.json}})

    async def deleteRole(self, role: Role) -> None:
        async with self.db() as db:
            return await db.deleteRole(role)

    async def sendGuildRoleDeleteEvent(self, role: Role) -> None:
        await self.mcl.broadcast("guild_events", {"e": "role_delete",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(role.guild_id)),
                                                      "guild_id": role.guild_id, "role_id": role.id}})

    async def getRolesMemberCounts(self, guild: Guild) -> Dict[int, int]:
        async with self.db() as db:
            return await db.getRolesMemberCounts(guild)

    async def updateMemberDiff(self, before: GuildMember, after: GuildMember) -> None:
        async with self.db() as db:
            await db.updateMemberDiff(before, after)

    async def sendGuildMemberUpdateEvent(self, member: GuildMember) -> None:
        await self.mcl.broadcast("guild_events", {"e": "member_update",
                                                  "data": {
                                                      "users": await self.getGuildMembersIds(GuildId(member.guild_id)),
                                                      "guild_id": member.guild_id,
                                                      "member_obj": await member.json}})

    async def getMutualGuilds(self, user: User, currentUser: User) -> List[dict]:
        user_guilds_ids = [guild.id for guild in await self.getUserGuilds(user)]
        current_user_guilds_ids = [guild.id for guild in await self.getUserGuilds(currentUser)]
        mutual_guilds_ids = set(user_guilds_ids) & set(current_user_guilds_ids)
        mutual_guilds = []
        for guild_id in mutual_guilds_ids:
            member = await self.getGuildMember(GuildId(guild_id), user.id)
            mutual_guilds.append({"id": str(guild_id), "nick": member.nick})

        return mutual_guilds

    async def getAttachments(self, message: Message) -> List[Attachment]:
        async with self.db() as db:
            return await db.getAttachments(message)

    async def getMemberRolesIds(self, member: GuildMember, include_default: bool=False) -> List[int]:
        async with self.db() as db:
            role_ids = await db.getMemberRolesIds(member)
            if include_default:
                role_ids.append(member.guild_id)
            return role_ids

    async def setMemberRolesFromList(self, member: GuildMember, roles: List[int]) -> None:
        async with self.db() as db:
            return await db.setMemberRolesFromList(member, roles)

    async def getMemberRoles(self, member: GuildMember, include_default: bool=False) -> List[Role]:
        async with self.db() as db:
            roles = await db.getMemberRoles(member)
            if include_default:
                roles.append(await db.getRole(member.guild_id))
            roles.sort(key=lambda r: r.position)
            return roles

    async def removeGuildBan(self, guild: Guild, user_id: int) -> None:
        async with self.db() as db:
            await db.removeGuildBan(guild, user_id)

    async def sendGuildBanRemoveEvent(self, guild: Guild, user_id: int) -> None:
        user_obj = await (await self.getUserData(UserId(user_id))).json
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_ban_remove", "data": {"users": [guild.owner_id], "guild_id": guild.id,
                                                                       "user_obj": user_obj}})

    async def getRolesMemberIds(self, role: Role) -> List[int]:
        async with self.db() as db:
            return await db.getRolesMemberIds(role)

    async def getGuildMembersGw(self, guild: _Guild, query: str, limit: int) -> List[GuildMember]:
        async with self.db() as db:
            return await db.getGuildMembersGw(guild, query, limit)

    async def memberHasRole(self, member: GuildMember, role: Role) -> bool:
        async with self.db() as db:
            return await db.memberHasRole(member, role)

    async def addMemberRole(self, member: GuildMember, role: Role) -> None:
        async with self.db() as db:
            return await db.addMemberRole(member, role)

    async def getPermissionOverwrite(self, channel: _Channel, target_id: int) -> Optional[PermissionOverwrite]:
        async with self.db() as db:
            return await db.getPermissionOverwrite(channel, target_id)

    async def getPermissionOverwrites(self, channel: Channel) -> List[PermissionOverwrite]:
        async with self.db() as db:
            return await db.getPermissionOverwrites(channel)

    async def putPermissionOverwrite(self, overwrite: PermissionOverwrite) -> None:
        async with self.db() as db:
            await db.putPermissionOverwrite(overwrite)

    async def deletePermissionOverwrite(self, channel: Channel, target_id: int) -> None:
        async with self.db() as db:
            await db.deletePermissionOverwrite(channel, target_id)

    async def getOverwritesForMember(self, channel: Channel, member: GuildMember) -> List[PermissionOverwrite]:
        roles = await self.getMemberRoles(member, True)
        roles.sort(key=lambda r: r.position)
        roles = {role.id: role for role in roles}
        overwrites = await self.getPermissionOverwrites(channel)
        overwrites.sort(key=lambda r: r.type)
        result = []
        for overwrite in overwrites:
            if overwrite.target_id in roles or overwrite.target_id == member.user_id:
                result.append(overwrite)
        return result

    async def getChannelInvites(self, channel: Channel) -> List[Invite]:
        async with self.db() as db:
            return await db.getChannelInvites(channel)

    async def getVanityCodeInvite(self, code: str) -> Optional[Invite]:
        async with self.db() as db:
            return await db.getVanityCodeInvite(code)

    async def sendGuildUpdateEvent(self, guild: Guild) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "guild_update", "data": {"users": await self.getGuildMembersIds(guild),
                                                                "guild_obj": await guild.json}})

    async def useInvite(self, invite: Invite) -> None:
        async with self.db() as db:
            if 0 < invite.max_uses <= invite.uses+1:
                await db.deleteInvite(invite)
            else:
                await db.useInvite(invite)

    async def putAuditLogEntry(self, entry: AuditLogEntry) -> None:
        async with self.db() as db:
            return await db.putAuditLogEntry(entry)

    async def getAuditLogEntries(self, guild: Guild, limit: int, before: Optional[int]=None) -> List[AuditLogEntry]:
        async with self.db() as db:
            return await db.getAuditLogEntries(guild, limit, before)

    async def sendAuditLogEntryCreateEvent(self, entry: AuditLogEntry) -> None:
        guild = await self.getGuild(entry.guild_id)
        await self.mcl.broadcast("guild_events",
                                 {"e": "audit_log_entry_create", "data": {"users": [guild.owner_id],
                                                                "entry_obj": await entry.json}})

    async def getGuildTemplate(self, guild: _Guild) -> Optional[GuildTemplate]:
        async with self.db() as db:
            return await db.getGuildTemplate(guild)

    async def putGuildTemplate(self, template: GuildTemplate) -> None:
        async with self.db() as db:
            return await db.putGuildTemplate(template)

    async def getGuildTemplateById(self, template_id: int) -> Optional[GuildTemplate]:
        async with self.db() as db:
            return await db.getGuildTemplateById(template_id)

    async def deleteGuildTemplate(self, template: GuildTemplate) -> None:
        async with self.db() as db:
            return await db.deleteGuildTemplate(template)

    async def updateTemplateDiff(self, before: GuildTemplate, after: GuildTemplate) -> None:
        async with self.db() as db:
            await db.updateTemplateDiff(before, after)

    async def setTemplateDirty(self, guild: _Guild) -> None:
        if not (template := await self.getGuildTemplate(guild)):
            return
        new_template = template.copy(is_dirty=True)
        await self.updateTemplateDiff(template, new_template)

    async def deleteGuild(self, guild: Guild) -> None:
        async with self.db() as db:
            await db.deleteGuild(guild)

    async def putWebhook(self, webhook: Webhook) -> None:
        async with self.db() as db:
            await db.putWebhook(webhook)

    async def deleteWebhook(self, webhook: Webhook) -> None:
        async with self.db() as db:
            await db.deleteWebhook(webhook)

    async def updateWebhookDiff(self, before: Webhook, after: Webhook) -> None:
        async with self.db() as db:
            await db.updateWebhookDiff(before, after)

    async def getWebhooks(self, guild: Guild) -> List[Webhook]:
        async with self.db() as db:
            return await db.getWebhooks(guild)

    async def getWebhook(self, webhook_id: int) -> Optional[Webhook]:
        async with self.db() as db:
            return await db.getWebhook(webhook_id)

    async def sendWebhooksUpdateEvent(self, webhook: Webhook) -> None:
        guild = await self.getGuild(webhook.guild_id)
        await self.mcl.broadcast("guild_events",
                                 {"e": "webhooks_update", "data": {"users": [guild.owner_id],
                                                                   "guild_id": webhook.guild_id,
                                                                   "channel_id": webhook.channel_id}})

    async def hideDmChannel(self, user: _User, channel: Channel) -> None:
        async with self.db() as db:
            await db.hideDmChannel(user, channel)

    async def unhideDmChannel(self, user: _User, channel: Channel) -> None:
        async with self.db() as db:
            await db.unhideDmChannel(user, channel)

    async def isDmChannelHidden(self, user: _User, channel: Channel) -> bool:
        async with self.db() as db:
            return await db.isDmChannelHidden(user, channel)

    async def updateEmojiDiff(self, before: Emoji, after: Emoji) -> None:
        async with self.db() as db:
            await db.updateEmojiDiff(before, after)

    async def getGuildStickers(self, guild: _Guild) -> List[Sticker]:
        async with self.db() as db:
            return await db.getGuildStickers(guild)

    async def getSticker(self, sticker_id: int) -> Optional[Sticker]:
        async with self.db() as db:
            return await db.getSticker(sticker_id)

    async def putSticker(self, sticker: Sticker) -> None:
        async with self.db() as db:
            await db.putSticker(sticker)

    async def updateStickerDiff(self, before: Sticker, after: Sticker) -> None:
        async with self.db() as db:
            await db.updateStickerDiff(before, after)

    async def deleteSticker(self, sticker: Sticker) -> None:
        async with self.db() as db:
            await db.deleteSticker(sticker)

    async def sendGuildStickerUpdateEvent(self, guild: _Guild) -> None:
        stickers = await self.getGuildStickers(guild)
        stickers = [await sticker.json for sticker in stickers]
        await self.mcl.broadcast("guild_events",
                                 {"e": "stickers_update", "data": {"users": await self.getGuildMembersIds(guild),
                                                                   "stickers": stickers,
                                                                   "guild_id": guild.id}})

    async def getUserOwnedGuilds(self, user: User) -> List[Guild]:
        async with self.db() as db:
            return await db.getUserOwnedGuilds(user)

    async def getUserOwnedGroups(self, user: User) -> List[Channel]:
        async with self.db() as db:
            return await db.getUserOwnedGroups(user)

    async def deleteUser(self, user: User) -> None:
        async with self.db() as db:
            return await db.deleteUser(user)

    async def sendUserDeleteEvent(self, user: User) -> None:
        await self.mcl.broadcast("user_events",
                                 {"e": "user_delete", "data": {"users": [user.id], "user_id": user.id}})

    async def getScheduledEventUserCount(self, event: ScheduledEvent) -> int:
        async with self.db() as db:
            return await db.getScheduledEventUserCount(event)

    async def putScheduledEvent(self, event: ScheduledEvent) -> None:
        async with self.db() as db:
            await db.putScheduledEvent(event)

    async def getScheduledEvent(self, event_id: int) -> Optional[ScheduledEvent]:
        async with self.db() as db:
            return await db.getScheduledEvent(event_id)

    async def getScheduledEvents(self, guild: _Guild) -> List[ScheduledEvent]:
        async with self.db() as db:
            return await db.getScheduledEvents(guild)

    async def updateScheduledEventDiff(self, before: ScheduledEvent, after: ScheduledEvent) -> None:
        async with self.db() as db:
            await db.updateScheduledEventDiff(before, after)

    async def sendScheduledEventCreateEvent(self, event: ScheduledEvent) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "event_create",
                                  "data": {"users": await self.getGuildMembersIds(GuildId(event.guild_id)),
                                           "event_obj": await event.json}})

    async def sendScheduledEventUpdateEvent(self, event: ScheduledEvent) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "event_update", "data": {"users": await self.getGuildMembersIds(GuildId(event.guild_id)),
                                                                   "event_obj": await event.json}})

    async def subscribeToScheduledEvent(self, user: User, event: ScheduledEvent) -> None:
        async with self.db() as db:
            await db.subscribeToScheduledEvent(user, event)

    async def unsubscribeFromScheduledEvent(self, user: User, event: ScheduledEvent) -> None:
        async with self.db() as db:
            await db.unsubscribeFromScheduledEvent(user, event)

    async def sendScheduledEventUserAddEvent(self, user: User, event: ScheduledEvent) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "event_user_add",
                                  "data": {"users": await self.getGuildMembersIds(GuildId(event.guild_id)),
                                           "user_id": user.id, "event_id": event.id, "guild_id": event.guild_id}})

    async def sendScheduledEventUserRemoveEvent(self, user: User, event: ScheduledEvent) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "event_user_remove",
                                  "data": {"users": await self.getGuildMembersIds(GuildId(event.guild_id)),
                                           "user_id": user.id, "event_id": event.id, "guild_id": event.guild_id}})

    async def getSubscribedScheduledEventIds(self, user: User, guild_id: int) -> list[int]:
        async with self.db() as db:
            return await db.getSubscribedScheduledEventIds(user, guild_id)

    async def deleteScheduledEvent(self, event: ScheduledEvent) -> None:
        async with self.db() as db:
            await db.deleteScheduledEvent(event)

    async def sendScheduledEventDeleteEvent(self, event: ScheduledEvent) -> None:
        await self.mcl.broadcast("guild_events",
                                 {"e": "event_delete",
                                  "data": {"users": await self.getGuildMembersIds(GuildId(event.guild_id)),
                                           "event_obj": await event.json}})

import src.yepcord.ctx as c
c._getCore = lambda: Core.getInstance()
c._getCDNStorage = lambda: CDN.getInstance().storage
from .ctx import Ctx