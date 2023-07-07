"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from asyncio import get_event_loop
# noinspection PyPackageRequirements
from contextvars import Context
from datetime import datetime
from hashlib import sha256
from hmac import new
from json import loads as jloads, dumps as jdumps
from os import urandom
from random import randint
from time import time
from typing import Optional, Union

from bcrypt import hashpw, gensalt, checkpw
from ormar import or_
from .classes.other import EmailMsg, Singleton, JWT, MFA
from .config import Config
from .enums import RelationshipType, ChannelType, GUILD_CHANNELS
from .errors import InvalidDataErr, MfaRequiredErr, Errors
from .snowflake import Snowflake
from .utils import b64encode, b64decode, int_length, NoneType
from ..gateway.events import DMChannelCreateEvent

from .models import User as mUser, UserData as mUserData, UserSettings as mUserSettings, Session as mSession, \
    Relationship as mRelationship, MfaCode, Channel as mChannel, Message as mMessage, ReadState as mReadState, \
    UserNote as mUserNote, Attachment as mAttachment, FrecencySettings as mFrecencySettings, Reactions as mReaction, \
    Emoji as mEmoji, Invite as mInvite, Guild as mGuild, Role as mRole, GuildMember as mGuildMember, \
    GuildTemplate as mGuildTemplate, PermissionOverwrite as mPermissionOverwrite, GuildBan as mGuildBan, \
    AuditLogEntry as mAuditLogEntry, Webhook as mWebhook, HiddenDmChannel as mHiddenDmChannel, Sticker as mSticker, \
    MfaCode as mMfaCode, GuildEvent as mScheduledEvent, ThreadMetadata as mThreadMetadata, ThreadMember as mThreadMember


class CDN(Singleton):
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core

    def __getattr__(self, item):
        return getattr(self.storage, item)


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    def __init__(self, key=None, loop=None):
        self.key = key if key and len(key) == 16 and type(key) == bytes else b''
        self.pool = None
        self.loop = loop or get_event_loop()
        self._cache = {}

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

    async def getRandomDiscriminator(self, login: str) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            if not await self.getUserByUsername(login, d):
                return d

    async def register(self, uid: int, login: str, email: Optional[str], password: str, birth: str, locale: str="en-US",
                       invite: Optional[str]=None) -> mSession:
        birth = datetime.strptime(birth, "%Y-%m-%d")

        email = email.lower()
        if await self.getUserByEmail(email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))
        password = self.hashPassword(uid, password)
        signature = self.generateSessionSignature()

        discriminator = await self.getRandomDiscriminator(login)
        if discriminator is None:
            raise InvalidDataErr(400, Errors.make(50035, {"login": {"code": "USERNAME_TOO_MANY_USERS",
                                                                    "message": "Too many users have this username, "
                                                                               "please try another."}}))

        user = await mUser.objects.create(id=uid, email=email, password=password)
        await mUserData.objects.create(id=uid, user=user, birth=birth, username=login, discriminator=discriminator)
        await mUserSettings.objects.create(id=uid, user=user, locale=locale)

        session = await mSession.objects.create(id=Snowflake.makeId(), user=user, signature=signature)
        await self.sendVerificationEmail(user)
        return session

    async def login(self, email: str, password: str) -> mSession:
        email = email.strip().lower()
        user = await mUser.objects.get_or_none(email=email)
        if not user or not checkpw(self.prepPassword(password, user.id), user.password.encode("utf8")):
            raise InvalidDataErr(400, Errors.make(50035, {"login": {"code": "INVALID_LOGIN",
                                                                    "message": "Invalid login or password."},
                                                          "password": {"code": "INVALID_LOGIN",
                                                                       "message": "Invalid login or password."}}))
        settings = await user.settings
        if settings.mfa:
            _sid = urandom(12)
            sid = int.from_bytes(_sid, "big")
            raise MfaRequiredErr(user.id, b64encode(_sid), self.generateMfaTicketSignature(user, sid))
        return await self.createSession(user.id)

    async def createSession(self, user: Union[int, mUser]) -> Optional[mSession]:
        if not isinstance(user, mUser) and (user := await mUser.objects.get_or_none(id=user, deleted=False)) is None:
            return
        sig = self.generateSessionSignature()
        session = await mSession.objects.create(id=Snowflake.makeId(), user=user, signature=sig)
        return session

    async def getUser(self, uid: int, allow_deleted: bool=True) -> Optional[mUser]:
        kwargs = {} if allow_deleted else {"deleted": False}
        return await mUser.objects.get_or_none(id=uid, **kwargs)

    async def getUserProfile(self, uid: int, current_user: mUser) -> mUser:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid, False)):
            raise InvalidDataErr(404, Errors.make(10013))
        return user

    async def checkUserPassword(self, user: mUser, password: str) -> bool:
        return checkpw(self.prepPassword(password, user.id), user.password.encode("utf8"))

    async def changeUserDiscriminator(self, user: mUser, discriminator: int, changed_username: bool=False) -> bool:
        data = await user.data
        username = data.username
        if await self.getUserByUsername(username, discriminator):
            if changed_username:
                return False
            raise InvalidDataErr(400, Errors.make(50035, {"username": {
                "code": "USERNAME_TOO_MANY_USERS",
                "message": "This discriminator already used by someone. Please enter something else."
            }}))
        await data.update(discriminator=discriminator)
        return True

    async def changeUserName(self, user: mUser, username: str) -> None:
        data = await user.data
        discriminator = data.discriminator
        if await self.getUserByUsername(username, discriminator):
            discriminator = await self.getRandomDiscriminator(username)
            if discriminator is None:
                raise InvalidDataErr(400, Errors.make(50035, {"username": {
                    "code": "USERNAME_TOO_MANY_USERS",
                    "message": "This name is used by too many users. Please enter something else or try again."
                }}))
        await data.update(discriminator=discriminator, username=username)

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[mUser]:
        data = await mUserData.objects.prefetch_related("user").get_or_none(username=username,
                                                                            discriminator=discriminator)
        if data is not None:
            return data.user

    async def checkRelationShipAvailable(self, target_user: mUser, current_user: mUser) -> None:
        relationship = await self.getRelationship(target_user, current_user)
        if relationship is not None:
            raise InvalidDataErr(400, Errors.make(80007))
        # TODO: check for mutual guilds or mutual friends

    async def reqRelationship(self, target_user: mUser, current_user: mUser) -> None:
        await mRelationship.objects.create(user1=current_user, user2=target_user, type=RelationshipType.PENDING)

    async def getRelationships(self, user: mUser, with_data=False) -> list[dict]:
        rels = []
        for rel in await mRelationship.objects.filter(or_(user1=user, user2=user)).all():
            if (rel_json := await rel.ds_json(user, with_data)) is not None:
                rels.append(rel_json)
        return rels

    async def getRelationship(self, u1: Union[mUser, int], u2: Union[mUser, int]) -> Optional[mRelationship]:
        id1 = u1.id if isinstance(u1, mUser) else u1
        id2 = u2.id if isinstance(u2, mUser) else u2
        return await mRelationship.objects.prefetch_related(["user1", "user2"]).get_or_none(
            ((mRelationship.user1.id == id1) & (mRelationship.user2.id == id2)) |
            ((mRelationship.user1.id == id2) & (mRelationship.user2.id == id1))
        )

    async def getRelatedUsers(self, user: mUser, only_ids=False) -> list:
        users = []
        for r in await mRelationship.objects.filter(or_(user1=user, user2=user)).all():
            other_user = r.other_user(user)
            if only_ids:
                users.append(other_user.id)
                continue
            data = await other_user.data
            users.append(data.ds_json)
        for channel in await self.getPrivateChannels(user, with_hidden=True):
            await channel.load_all()
            for recipient in channel.recipients:
                if recipient.id == user.id: continue
                if only_ids:
                    if recipient.id in users: continue
                    users.append(recipient.id)
                    continue
                if [rec for rec in users if rec["id"] == recipient.id]:
                    continue
                data = await recipient.data
                users.append(data.ds_json)
        return users

    async def accRelationship(self, user: mUser, uid: int) -> None:
        rel = await mRelationship.objects.select_related(["user1", "user2"]).get_or_none(
            user1__id=uid, user2__id=user.id, type=RelationshipType.PENDING
        )
        if rel is None:
            return
        await rel.update(type=RelationshipType.FRIEND)

    async def delRelationship(self, user: mUser, uid: int) -> Optional[mRelationship]:
        rel = await self.getRelationship(user, uid)
        if rel.type == RelationshipType.BLOCK:
            rel = await mRelationship.objects.select_related(["user1", "user2"]).get_or_none(
                user1__id=user.id, user2__id=uid
            )
            if rel is None:
                return
        await rel.delete()
        return rel

    async def changeUserPassword(self, user: mUser, new_password: str) -> None:
        await user.update(password=self.hashPassword(user.id, new_password))

    async def getMfa(self, user: mUser) -> Optional[MFA]:
        settings = await user.settings
        mfa = MFA(settings.mfa, user.id)
        if mfa.valid:
            return mfa

    async def setBackupCodes(self, user: mUser, codes: list[str]) -> None:
        await self.clearBackupCodes(user)
        await MfaCode.objects.bulk_create([
            MfaCode(user=user, code=code) for code in codes
        ])

    async def clearBackupCodes(self, user: mUser) -> None:
        await MfaCode.objects.delete(user=user)

    async def getBackupCodes(self, user: mUser) -> list[MfaCode]:
        return await MfaCode.objects.filter(user=user).limit(10).all()

    def generateMfaTicketSignature(self, user: mUser, session_id: int) -> str:
        payload = {
            "user_id": user.id,
            "session_id": session_id
        }
        token = JWT.encode(payload, self.key, time()+300)
        return b64encode(token)

    def verifyMfaTicketSignature(self, user: mUser, session_id: int, token: str) -> bool:
        if not (payload := JWT.decode(token, self.key)):
            return False
        if payload["user_id"] != user.id: return False
        if payload["session_id"] != session_id: return False
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

    async def generateUserMfaNonce(self, user: mUser) -> tuple[str, str]:
        exp = time() + 600
        code = b64encode(urandom(16))
        nonce = JWT.encode({"type": "normal", "code": code, "user_id": user.id}, self.key, exp)
        rnonce = JWT.encode({"type": "regenerate", "code": code, "user_id": user.id}, self.key, exp)
        return nonce, rnonce

    async def verifyUserMfaNonce(self, user: mUser, nonce: str, regenerate: bool) -> None:
        if not (payload := JWT.decode(nonce, self.key)) or payload["user_id"] != user.id:
            raise InvalidDataErr(400, Errors.make(60011))
        nonce_type = "normal" if not regenerate else "regenerate"
        if nonce_type != payload["type"]:
            raise InvalidDataErr(400, Errors.make(60011))

    async def useMfaCode(self, user: mUser, code: str) -> bool:
        if (code := await MfaCode.objects.get_or_none(user=user, code=code, used=False)) is None:
            return False
        await code.update(used=True)
        return True

    async def getChannel(self, channel_id: int) -> Optional[mChannel]:
        if (channel := await mChannel.objects.select_related(["guild", "owner", "parent"])
                .get_or_none(id=channel_id)) is None:
            return
        return await self.setLastMessageIdForChannel(channel)

    async def getDmChannel(self, user1: mUser, user2: mUser) -> Optional[mChannel]:
        channel_row = await mChannel.Meta.database.fetch_one(
            query="SELECT * FROM `channels` WHERE `id` = ("
                  "SELECT `channel` FROM `channels_users` WHERE `user` IN (:user1, :user2) GROUP BY `channel` "
                  "HAVING COUNT(DISTINCT `user`) = 2);",
            values={"user1": user1.id, "user2": user2.id}
        )
        if channel_row is None: return
        return await mChannel.from_row(channel_row, mChannel).load_all()

    async def getDMChannelOrCreate(self, user1: mUser, user2: mUser) -> mChannel:
        channel = await self.getDmChannel(user1, user2)
        if channel is None:
            channel = await mChannel.objects.create(id=Snowflake.makeId(), type=ChannelType.DM)
            await channel.recipients.add(user1)
            await channel.recipients.add(user2)
            return await mChannel.objects.get(id=channel.id)

        if await self.isDmChannelHidden(user1, channel):
            await self.unhideDmChannel(user1, channel)
            await c.getGw().dispatch(DMChannelCreateEvent(channel), users=[user1.id])
        return await self.setLastMessageIdForChannel(channel)

    async def getLastMessageId(self, channel: mChannel) -> Optional[int]:
        if (last_message_id := await mMessage.objects.filter(channel=channel).max("id")) is not None:
            return last_message_id

    async def setLastMessageIdForChannel(self, channel: mChannel) -> mChannel:
        channel.last_message_id = await self.getLastMessageId(channel)
        return channel

    async def getChannelMessagesCount(self, channel: mChannel) -> int:
        return await mMessage.objects.filter(channel=channel).count()

    async def getPrivateChannels(self, user: mUser, with_hidden: bool=False) -> list[mChannel]:
        channels = await mChannel.objects.select_related("recipients").filter(recipients__id__in=[user.id]).all()
        return [await self.setLastMessageIdForChannel(channel) for channel in channels]

    async def getChannelMessages(self, channel, limit: int, before: int=0, after: int=0) -> list[mMessage]:
        id_filter = {}
        if after: id_filter["id__gt"] = after
        if before: id_filter["id__lt"] = before
        return await mMessage.objects.filter(channel=channel, **id_filter).limit(limit).all()

    async def getMessage(self, channel: mChannel, message_id: int) -> Optional[mMessage]:
        if not message_id: return
        return await mMessage.objects.select_related(["author", "channel", "thread", "guild"])\
            .get_or_none(channel=channel, id=message_id)

    async def sendMessage(self, message: mMessage) -> mMessage:
        async def _addToReadStates():
            users = await self.getRelatedUsersToChannel(message.channel)
            if message.author.id in users:
                users.remove(message.author.id)
            for user in users:
                read_state, _ = await mReadState.objecs.get_or_create(
                    user=user, channel=message.channel, _defaults={"last_read_id": message.id, "count": 0}
                )
                await read_state.update(count=read_state.count+1)
        Context().run(get_event_loop().create_task, _addToReadStates())
        return message

    async def getRelatedUsersToChannel(self, channel: mChannel, ids: bool=True) -> list[Union[int, mUser]]:
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            await channel.load_all()
            if ids: return [recipient.id for recipient in channel.recipients]
            return channel.recipients
        elif channel.type in GUILD_CHANNELS:
            return [member.user_id for member in await self.getGuildMembers(channel.guild)]
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return [member.user_id for member in await self.getThreadMembers(channel)]

    async def setReadState(self, user: mUser, channel: mChannel, count: int, last: int) -> None:
        read_state, _ = await mReadState.objects.get_or_create(
            user=user, channel=channel, _defaults={"last_read_id": last, "count": count}
        )
        await read_state.update(last_read_id=last, count=count)

    async def getReadStatesJ(self, user: mUser) -> list:
        states = []
        for st in await mReadState.objects.filter(user=user).all:
            states.append({  # TODO: replace with st.ds_json
                "mention_count": st.count,
                "last_pin_timestamp": await self.getLastPinTimestamp(st.channel),
                "last_message_id": str(st.last_read_id),
                "id": str(st.channel_id),
            })
        return states

    async def getUserNote(self, user: mUser, target: mUser) -> Optional[mUserNote]:
        return await mUserNote.objects.get_or_none(user=user, target=target)

    async def getAttachment(self, attachment_id: int) -> Optional[mAttachment]:
        return await mAttachment.objects.get_or_none(id=attachment_id)

    async def getUserByChannelId(self, channel_id: int, user_id: int) -> Optional[mUser]:
        if not (channel := await self.getChannel(channel_id)):
            return None
        return await self.getUserByChannel(channel, user_id)

    async def getUserByChannel(self, channel: mChannel, user_id: int) -> Optional[mUser]:
        if channel.type in (ChannelType.DM, ChannelType.GROUP_DM):
            if await mChannel.objects.select_related("recipients").filter(id=channel.id, recipients__id__in=[user_id])\
                    .exists():
                return await self.getUser(user_id)
        elif channel.type in GUILD_CHANNELS:
            return await self.getGuildMember(channel.guild, user_id)
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return await self.getThreadMember(channel, user_id)

    async def sendVerificationEmail(self, user: mUser) -> None:
        key = new(self.key, str(user.id).encode('utf-8'), sha256).digest()
        t = int(time())
        sig = b64encode(new(key, f"{user.id}:{user.email}:{t}".encode('utf-8'), sha256).digest())
        token = b64encode(jdumps({"id": user.id, "email": user.email, "time": t}))
        token += f".{sig}"
        link = f"https://{Config('CLIENT_HOST')}/verify#token={token}"
        await EmailMsg(user.email, "Confirm your e-mail in YEPCord",
                       f"Thank you for signing up for a YEPCord account!\nFirst you need to make sure that you are you!"
                       f" Click to verify your email address:\n{link}").send()

    async def verifyEmail(self, user: mUser, token: str) -> None:
        try:
            data, sig = token.split(".")
            data = jloads(b64decode(data).decode("utf8"))
            sig = b64decode(sig)
            t = data["time"]
            assert data["email"] == user.email and data["id"] == user.id and time() - t < 600
            key = new(self.key, str(user.id).encode('utf-8'), sha256).digest()
            vsig = new(key, f"{user.id}:{user.email}:{t}".encode('utf-8'), sha256).digest()
            assert sig == vsig
        except:
            raise InvalidDataErr(400, Errors.make(50035, {"token": {"code": "TOKEN_INVALID",
                                                                    "message": "Invalid token."}}))
        await user.update(verified=True)

    async def getUserByEmail(self, email: str) -> Optional[mUser]:
        return await mUser.objects.get_or_none(email=email)

    async def changeUserEmail(self, user: mUser, email: str) -> None:
        email = email.lower()
        if user.email == email:
            return
        if await self.getUserByEmail(email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))
        await user.update(email=email, verified=False)

    async def sendMfaChallengeEmail(self, user: mUser, nonce: str) -> None:
        code = await self.mfaNonceToCode(user, nonce)
        await EmailMsg(user.email,
                       f"Your one-time verification key is {code}",
                       f"It looks like you're trying to view your account's backup codes.\n"
                       f"This verification key expires in 10 minutes. This key is extremely sensitive, treat it like a "
                       f"password and do not share it with anyone.\n"
                       f"Enter it in the app to unlock your backup codes:\n{code}").send()

    async def mfaNonceToCode(self, user: mUser, nonce: str) -> Optional[str]:
        if not (payload := JWT.decode(nonce, self.key)):
            return
        token = JWT.encode({"code": payload["code"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

    async def createDMGroupChannel(self, user: mUser, recipients: list[mUser], name: Optional[str]=None) -> mChannel:
        if user.id not in recipients:
            recipients.append(user)
        channel = await mChannel.objects.create(id=Snowflake.makeId(), type=ChannelType.GROUP_DM, name=name, owner=user)
        for recipient in recipients:
            await channel.recipients.add(recipient)
        return channel

    async def pinMessage(self, message: mMessage) -> None:
        if await mMessage.objects.filter(pinned=True, channel=message.channel).count() >= 50:
            raise InvalidDataErr(400, Errors.make(30003))
        message.extra_data["pinned_at"] = int(time())
        await message.update(extra_data=message.extra_data, pinned=True)

    async def getLastPinnedMessage(self, channel: mChannel) -> Optional[mMessage]:
        # TODO: order by pinned timestamp
        return await mMessage.objects.filter(pinned=True, channel=channel).order_by("-id").first()

    async def getLastPinTimestamp(self, channel: mChannel) -> str:
        last = await self.getLastPinnedMessage(channel)
        last_ts = last.extra_data["pinned_at"] if last is not None else 0
        return datetime.utcfromtimestamp(last_ts).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    async def getPinnedMessages(self, channel: mChannel) -> list[mMessage]:
        return await mMessage.objects.filter(pinned=True, channel=channel).all()

    async def addReaction(self, message: mMessage, user: mUser, emoji: mEmoji, emoji_name: str) -> mReaction:
        return await mReaction.objects.get_or_create(user=user, message=message, emoji=emoji, emoji_name=emoji_name)

    async def removeReaction(self, message: mMessage, user: mUser, emoji: mEmoji, emoji_name: str) -> None:
        await mReaction.objects.delete(user=user, message=message, emoji=emoji, emoji_name=emoji_name)

    async def getMessageReactionsJ(self, message: mMessage, user: mUser) -> list:
        reactions = []
        # TODO: test and maybe rewrite whole method
        #result = await mChannel.Meta.database.fetch_all(
        #    query=f'SELECT `emoji_name` as ename, `emoji` as eid, COUNT(*) AS ecount, (SELECT COUNT(*) > 0 FROM '
        #          f'`reactions` WHERE `emoji_name`=ename AND (`emoji`=eid OR (`emoji` IS NULL AND eid IS NULL)) '
        #          f'AND `user_id`=:user_id) as me FROM `reactions` WHERE `message_id`=:message_id GROUP BY '
        #          f'CONCAT(`emoji_name`, `emoji`) COLLATE utf8mb4_unicode_520_ci;',
        #    values={"user_id": user.id, "message_id": message.id}
        #)
        #for r in result:
        #    reactions.append(
        #        {"emoji": {"id": str(r[1]) if r[1] else None, "name": r[0]}, "count": r[2], "me": bool(r[3])})
        return reactions

    async def getReactedUsersJ(self, message: mMessage, limit: int, emoji: mEmoji, emoji_name: str) -> list[dict]:
        users = []
        reactions = await mReaction.objects.select_related("user").filter(
            message=message, emoji=emoji, emoji_name=emoji_name
        ).limit(limit).all()
        for reaction in reactions:
            data = await reaction.user.data
            users.append(data.ds_json)
        return users

    async def searchMessages(self, search_filter: dict) -> tuple[list[mMessage], int]:
        filter_args = {}
        query = mMessage.objects.order_by("-id").limit(25)
        if "author_id" in search_filter:
            filter_args["author__id"] = search_filter["author_id"]
        if "mentions" in search_filter:
            filter_args["content__contains"] = f"<@{search_filter['mentions']}>"
        if "has" in search_filter:
            ...  # TODO: add `has` filter
        if "min_id" in search_filter:
            filter_args["id__gt"] = search_filter["min_id"]
        if "max_id" in search_filter:
            filter_args["id__lt"] = search_filter["max_id"]
        if "pinned" in search_filter:
            filter_args["pinned"] = search_filter["pinned"].lower() == "true"
        if "offset" in search_filter:
            query = query.offset(search_filter["offset"])
        if "content" in search_filter:
            filter_args["content__icontains"] = search_filter["content"]
        query = query.filter(**filter_args)
        messages = await query.all()
        count = await query.count()
        return messages, count

    async def createInvite(self, channel: mChannel, inviter: mUser, max_age: int=86400, max_uses: int=0) -> mInvite:
        return await mInvite.objects.create(
            id=Snowflake.makeId(), channel=channel, inviter=inviter, max_age=max_age, max_uses=max_uses
        )

    async def getInvite(self, invite_id: int) -> Optional[mInvite]:
        return await mInvite.objects.select_related(["channel", "channel__guild", "inviter"]).get_or_none(id=invite_id)

    async def createGuild(self, guild_id: int, user: mUser, name: str, icon: str=None) -> mGuild:
        guild = await mGuild.objects.create(id=guild_id, owner=user, name=name, icon=icon)
        await mRole.objects.create(id=guild.id, guild=guild, name="@everyone")

        text_category = await mChannel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Text Channels", position=0,
            flags=0, rate_limit=0
        )
        voice_category = await mChannel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Voice Channels", position=0,
            flags=0, rate_limit=0
        )
        system_channel = await mChannel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_TEXT, guild=guild.id, name="general", position=0, flags=0,
            parent=text_category, rate_limit=0
        )
        await mChannel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_VOICE, guild=guild.id, name="General", position=0, flags=0,
            parent=voice_category, bitrate=64000, user_limit=0, rate_limit=0
        )
        await guild.update(system_channel=system_channel.id)

        await mGuildMember.objects.create(id=user.id, user=user, guild=guild)

        return guild

    async def createGuildFromTemplate(self, guild_id: int, user: mUser, template: mGuildTemplate, name: Optional[str],
                                      icon: Optional[str]) -> mGuild:
        guild = await mGuild.objects.create(id=guild_id, owner=user.id)

        serialized = template.serialized_guild
        serialized["name"] = name or serialized["name"]
        serialized["icon"] = icon
        replaced_ids: dict[Union[int, NoneType], Union[int, NoneType]] = {None: None, 0: guild_id}
        channels = {}

        for role in serialized["roles"]:
            if role["id"] not in replaced_ids:
                replaced_ids[role["id"]] = Snowflake.makeId()
            role["id"] = replaced_ids[role["id"]]
            await mRole.objects.create(guild=guild, **role)

        for channel in serialized["channels"]:
            if channel["id"] not in replaced_ids:
                replaced_ids[channel["id"]] = Snowflake.makeId()
            channel["id"] = channel_id = replaced_ids[channel["id"]]
            channel["parent"] = channels.get(replaced_ids.get(channel["parent_id"], None), None)
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

            permission_overwrites = channel["permission_overwrites"]
            del channel["permission_overwrites"]

            channels[channel_id] = await mChannel.objects.create(guild=guild, **channel)
            for overwrite in permission_overwrites:
                overwrite["target_id"] = replaced_ids[overwrite["id"]]
                overwrite["channel"] = channels[channel_id]
                del overwrite["id"]
                await mPermissionOverwrite.objects.create(**overwrite)

        serialized["afk_channel"] = replaced_ids.get(serialized["afk_channel_id"], None)
        serialized["system_channel"] = replaced_ids.get(serialized["system_channel_id"], None)
        del serialized["afk_channel_id"]
        del serialized["system_channel_id"]

        del serialized["roles"]
        del serialized["channels"]

        await guild.update(**serialized)
        await mGuildMember.objects.create(id=user.id, user=user, guild=guild)

        return guild

    async def getRole(self, role_id: int) -> mRole:
        return await mRole.objects.get_or_none(id=role_id)

    async def getRoles(self, guild: mGuild, exclude_default=False) -> list[mRole]:
        query = mRole.objects.filter(guild=guild)
        if exclude_default:
            query = query.exclude(id=guild.id)
        return await query.all()

    async def getGuildMember(self, guild: mGuild, user_id: int) -> Optional[mGuildMember]:
        return await mGuildMember.objects.select_related(["user", "guild"]).get_or_none(guild=guild, user__id=user_id)

    async def getGuildMembers(self, guild: mGuild) -> list[mGuildMember]:
        return await mGuildMember.objects.filter(guild=guild).all()

    async def getGuildMembersIds(self, guild: mGuild) -> list[int]:
        return [member.id for member in await self.getGuildMembers(guild)]

    async def getGuildChannels(self, guild: mGuild) -> list[mChannel]:
        return await mChannel.objects.filter(guild=guild)\
            .exclude(type__in=[ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD]).all()

    async def getUserGuilds(self, user: mUser) -> list[mGuild]:
        return [member.guild for member in await mGuildMember.select_related("guild").filter(user=user).all()]

    async def getGuildMemberCount(self, guild: mGuild) -> int:
        return await mGuildMember.objects.filter(guild=guild).count()

    async def getGuild(self, guild_id: int) -> Optional[mGuild]:
        return await mGuild.objects.select_related("owner").get_or_none(id=guild_id)

    async def blockUser(self, user: mUser, block_user: mUser) -> None:
        rel = await self.getRelationship(user.id, block_user)
        if rel and rel.type != RelationshipType.BLOCK:
            await rel.delete()
        elif rel and rel.type == RelationshipType.BLOCK and rel.user1 == user:
            return
        await mRelationship.objects.create(user1=user, user2=block_user, type=RelationshipType.BLOCK)

    async def getEmojis(self, guild_id: int) -> list[mEmoji]:
        return await mEmoji.objects.filter(guild__id=guild_id).all()

    async def getEmoji(self, emoji_id: int) -> Optional[mEmoji]:
        return await mEmoji.objects.get_or_none(id=emoji_id)

    async def getEmojiByReaction(self, reaction: str) -> Optional[mEmoji]:
        try:
            name, emoji_id = reaction.split(":")
            emoji_id = int(emoji_id)
            if "~" in name:
                name = name.split("~")[0]
        except ValueError:
            return
        if not (emoji := await self.getEmoji(emoji_id)):
            return
        return emoji if emoji.name == name else None

    async def getGuildInvites(self, guild: mGuild) -> list[mInvite]:
        return await mInvite.objects.select_related(["channel", "channel__guild", "inviter"])\
            .filter(channel__guild=guild).all()

    async def banGuildMember(self, member: mGuildMember, reason: str=None) -> None:
        await mGuildBan.objects.create(user=member.user, guild=member.guild, reason=reason)

    async def getGuildBan(self, guild: mGuild, user_id: int) -> Optional[mGuildMember]:
        return await mGuildBan.objects.get_or_none(guild=guild, user__id=user_id)

    async def getGuildBans(self, guild: mGuild) -> list[mGuildBan]:
        return await mGuildBan.objects.filter(guild=guild).all()

    async def bulkDeleteGuildMessagesFromBanned(self, guild: mGuild, user_id: int, after_id: int) -> dict[int, list[int]]:
        messages = await mMessage.objects.select_related("channel").filter(
            guild=guild, author__id=user_id, id__gt=after_id
        ).limit(500).all()
        result = {}
        messages_ids = []
        for message in messages:
            if message.channel.id not in result:
                result[message.channel.id] = []
            result[message.channel.id].append(message.id)
            messages_ids.append(message.id)

        await mMessage.objects.delete(id__in=messages_ids)

        return result

    async def getRolesMemberCounts(self, guild: mGuild) -> dict[int, int]:
        counts = {}
        for role in await mRole.objects.select_related("guildmembers").filter(guild=guild).all():
            counts[role.id] = len(role.guildmembers)
        return counts

    async def getMutualGuildsJ(self, user: mUser, current_user: mUser) -> list[dict[str, str]]:
        user_guilds_member = await mGuildMember.objects.select_related("guild").filter(user=user).all()
        user_guild_ids = [member.guild.id for member in user_guilds_member]
        user_guilds_member = {member.guild.id: member for member in user_guilds_member}

        current_user_guilds_member = await mGuildMember.objects.select_related("guild").filter(user=current_user).all()
        current_user_guild_ids = [member.guild.id for member in current_user_guilds_member]

        mutual_guilds_ids = set(user_guild_ids) & set(current_user_guild_ids)
        mutual_guilds_json = []
        for guild_id in mutual_guilds_ids:
            member = user_guilds_member[guild_id]
            mutual_guilds_json.append({"id": str(guild_id), "nick": member.nick})

        return mutual_guilds_json

    async def getAttachments(self, message: mMessage) -> list[mAttachment]:
        return await mAttachment.objects.filter(message=message).all()

    async def getMemberRolesIds(self, member: mGuildMember, include_default: bool=False) -> list[int]:
        roles = await member.roles.all() if not member.roles else member.roles
        roles_ids = [role.id for role in roles]
        if include_default:
            roles_ids.append(member.guild.id)
        return roles_ids

    async def setMemberRolesFromList(self, member: mGuildMember, roles: list[mRole]) -> None:
        current_roles = await member.roles.all()
        for role in roles:
            if role not in current_roles:
                await member.roles.add(role)
        for role in current_roles:
            if role not in roles:
                await member.roles.remove(role)

    async def getMemberRoles(self, member: mGuildMember, include_default: bool=False) -> list[mRole]:
        roles = await member.roles.all()
        if include_default:
            roles.append(await mRole.objects.get(guild=member.guild))

        roles.sort(key=lambda r: r.position)
        return roles

    async def removeGuildBan(self, guild: mGuild, user_id: int) -> None:
        await mGuildBan.objects.delete(guild=guild, user__id=user_id)

    async def getRoleMemberIds(self, role: mRole) -> list[int]:
        role = await mRole.objects.select_related("guildmembers").get(id=role.id)
        return [member.id for member in role.guildmembers]

    async def getGuildMembersGw(self, guild: mGuild, query: str, limit: int) -> list[mGuildMember]:
        # noinspection PyUnresolvedReferences
        return await mGuildMember.objects.filter(
            (mGuildMember.guild == guild) &
            (mGuildMember.nick.startswith(query) | mGuildMember.user.userdata.username.istartswith(query))
        ).limit(limit).all()

    async def memberHasRole(self, member: mGuildMember, role: mRole) -> bool:
        return await member.roles.filter(id=role.id).exists()

    async def getPermissionOverwrite(self, channel: mChannel, target_id: int) -> Optional[mPermissionOverwrite]:
        return await mPermissionOverwrite.objects.get_or_none(channel=channel, target_id=target_id)

    async def getPermissionOverwrites(self, channel: mChannel) -> list[mPermissionOverwrite]:
        return await mPermissionOverwrite.objects.filter(channel=channel).all()

    async def deletePermissionOverwrite(self, channel: mChannel, target_id: int) -> None:
        if (overwrite := await self.getPermissionOverwrite(channel, target_id)) is not None:
            await overwrite.delete()

    async def getOverwritesForMember(self, channel: mChannel, member: mGuildMember) -> list[mPermissionOverwrite]:
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

    async def getChannelInvites(self, channel: mChannel) -> list[mInvite]:
        await mInvite.Meta.database.execute(
            query="DELETE FROM `invites` WHERE channel=:channel_id AND `max_age` > 0 AND "
                  "`max_age` + (((`id` >> 22) + :sf_epoch) / 1000) < :current_time;",
            values={"channel_id": channel.id, "current_time": int(time()), "sf_epoch": Snowflake.EPOCH}
        )
        return await mInvite.objects.select_related(["channel__guild", "inviter"])\
            .filter(channel=channel, vanity_code__isnull=True).all()

    async def getVanityCodeInvite(self, code: str) -> Optional[mInvite]:
        if code is None: return
        return await mInvite.objects.filter(vanity_code=code).all()

    async def useInvite(self, invite: mInvite) -> None:
        if 0 < invite.max_uses <= invite.uses+1:
            await invite.delete()
        else:
            await invite.update(uses=invite.uses+1)

    async def getAuditLogEntries(self, guild: mGuild, limit: int, before: Optional[int]=None) -> list[mAuditLogEntry]:
        before = {} if before is None else {"id__lt": before}
        return await mAuditLogEntry.objects.filter(guild=guild, **before).limit(limit).all()

    async def getGuildTemplate(self, guild: mGuild) -> Optional[mGuildTemplate]:
        return await mGuildTemplate.objects.get_or_none(guild=guild)

    async def getGuildTemplateById(self, template_id: int) -> Optional[mGuildTemplate]:
        return await mGuildTemplate.objects.get_or_none(id=template_id)

    async def setTemplateDirty(self, guild: mGuild) -> None:
        if not (template := await self.getGuildTemplate(guild)):
            return
        await template.update(is_dirty=True)

    async def getWebhooks(self, guild: mGuild) -> list[mWebhook]:
        return await mWebhook.objects.filter(channel__guild=guild).all()

    async def getWebhook(self, webhook_id: int) -> Optional[mWebhook]:
        return await mWebhook.objects.select_related(["channel", "channel__guild", "user"]).get_or_none(id=webhook_id)

    async def hideDmChannel(self, user: mUser, channel: mChannel) -> None:
        await mHiddenDmChannel.objects.get_or_create(user=user, channel=channel)

    async def unhideDmChannel(self, user: mUser, channel: mChannel) -> None:
        await mHiddenDmChannel.objects.delete(user=user, channel=channel)

    async def isDmChannelHidden(self, user: mUser, channel: mChannel) -> bool:
        return await mHiddenDmChannel.objects.filter(user=user, channel=channel).exists()

    async def getGuildStickers(self, guild: mGuild) -> list[mSticker]:
        return await mSticker.objects.filter(guild=guild).all()

    async def getSticker(self, sticker_id: int) -> Optional[mSticker]:
        return await mSticker.objects.get_or_none(id=sticker_id)

    async def getUserOwnedGuilds(self, user: mUser) -> list[mGuild]:
        return await mGuild.objects.filter(owner=user).all()

    async def getUserOwnedGroups(self, user: mUser) -> list[mChannel]:
        return await mChannel.objects.filter(owner=user, type=ChannelType.GROUP_DM).all()

    async def deleteUser(self, user: mUser) -> None:
        await user.update(deleted=True, email=f"deleted_{user.id}@yepcord.ml", password="")
        data = await user.data
        await data.update(discriminator=0, username=f"Deleted User {hex(user.id)[2:]}", avatar=None,
                          avatar_decoration=None, public_flags=0)
        await mSession.objects.delete(user=user)
        await mRelationship.objects.delete(or_(user1=user, user2=user))
        await mMfaCode.objects.delete(user=user)
        await mGuildMember.objects.delete(user=user)
        await mUserSettings.objects.delete(user=user)
        await mFrecencySettings.objects.delete(user=user)
        await mInvite.objects.delete(inviter=user)
        await mReadState.objects.delete(user=user)

    async def getScheduledEventUserCount(self, event: mScheduledEvent) -> int:
        return await event.subscribers.count()

    async def getScheduledEvent(self, event_id: int) -> Optional[mScheduledEvent]:
        return await mScheduledEvent.objects.get_or_none(id=event_id)

    async def getScheduledEvents(self, guild: mGuild) -> list[mScheduledEvent]:
        return await mScheduledEvent.objects.filter(guild=guild).all()

    async def getSubscribedScheduledEventIds(self, user: mUser, guild_id: int) -> list[int]:
        _user = await mUser.objects.select_related("guildmembers__guildevents")\
            .get(id=user.id, guildmembers__guild__id=guild_id)
        events_ids = []
        for member in _user.guildmembers:
            for event in member.guildevents:
                events_ids.append(event.id)
        return events_ids

    async def getThreadMetadata(self, thread: mChannel) -> Optional[mThreadMetadata]:
        return await mThreadMetadata.objects.get_or_none(channel=thread)

    async def getThreadMembersCount(self, thread: mChannel) -> int:
        return await mThreadMember.objects.filter(channel=thread).count()

    async def getThreadMembers(self, thread: mChannel, limit: int=100) -> list[mThreadMember]:
        return await mThreadMember.objects.select_related("user").filter(channel=thread).limit(limit).all()

    async def getGuildMemberThreads(self, guild: mGuild, user_id: int) -> list[mChannel]:
        return await mThreadMember.objects.select_related("channel").filter(guild=guild, user__id=user_id).all()

    async def getThreadMember(self, thread: mChannel, user_id: int) -> Optional[mThreadMember]:
        return await mThreadMember.objects.get_or_none(channel=thread, user__id=user_id)


import src.yepcord.ctx as c
c._getCore = lambda: Core.getInstance()
c._getCDNStorage = lambda: CDN.getInstance().storage
