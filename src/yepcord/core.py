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
import os.path
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

import maxminddb
from bcrypt import hashpw, gensalt, checkpw
from ormar import or_

from .classes.other import EmailMsg, JWT, MFA
from .classes.singleton import Singleton
from .config import Config
from .enums import RelationshipType, ChannelType, GUILD_CHANNELS
from .errors import InvalidDataErr, MfaRequiredErr, Errors
from .models import User, UserData, UserSettings, Session, Relationship, Channel, Message, ReadState, UserNote, \
    Attachment, FrecencySettings, Emoji, Invite, Guild, GuildMember, GuildTemplate, Reactions as Reaction, Sticker, \
    PermissionOverwrite, GuildBan, AuditLogEntry, Webhook, HiddenDmChannel, MfaCode, Role, GuildEvent, \
    ThreadMetadata, ThreadMember, is_sqlite
from .snowflake import Snowflake
from .utils import b64encode, b64decode, int_size, NoneType
from ..gateway.events import DMChannelCreateEvent


class CDN(Singleton):
    def __init__(self, storage, core):
        self.storage = storage
        self.core = core

    def __getattr__(self, item):
        return getattr(self.storage, item)


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    def __init__(self, key=None):
        self.key = key if key and len(key) >= 16 and type(key) == bytes else urandom(32)
        self.ipdb = None

    def prepPassword(self, password: str, uid: int) -> bytes:
        """
        Prepares user password for hashing
        :param password:
        :param uid:
        :return:
        """
        password = password.encode("utf8")
        password += uid.to_bytes(int_size(uid), "big")
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

    async def register(self, uid: int, login: str, email: Optional[str], password: str, birth: str,
                       locale: str = "en-US",
                       invite: Optional[str] = None) -> Session:
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

        user = await User.objects.create(id=uid, email=email, password=password)
        await UserData.objects.create(id=uid, user=user, birth=birth, username=login, discriminator=discriminator)
        await UserSettings.objects.create(id=uid, user=user, locale=locale)

        session = await Session.objects.create(id=Snowflake.makeId(), user=user, signature=signature)
        await self.sendVerificationEmail(user)
        return session

    async def login(self, email: str, password: str) -> Session:
        email = email.strip().lower()
        user = await User.objects.get_or_none(email=email)
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

    async def createSession(self, user: Union[int, User]) -> Optional[Session]:
        if not isinstance(user, User) and (user := await User.objects.get_or_none(id=user, deleted=False)) is None:
            return
        sig = self.generateSessionSignature()
        return await Session.objects.create(id=Snowflake.makeId(), user=user, signature=sig)

    async def getUser(self, uid: int, allow_deleted: bool = True) -> Optional[User]:
        kwargs = {} if allow_deleted else {"deleted": False}
        return await User.objects.get_or_none(id=uid, **kwargs)

    async def getUserProfile(self, uid: int, current_user: User) -> User:
        # TODO: check for relationship, mutual guilds or mutual friends
        if not (user := await self.getUser(uid, False)):
            raise InvalidDataErr(404, Errors.make(10013))
        return user

    async def checkUserPassword(self, user: User, password: str) -> bool:
        return checkpw(self.prepPassword(password, user.id), user.password.encode("utf8"))

    async def changeUserDiscriminator(self, user: User, discriminator: int, changed_username: bool = False) -> bool:
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

    async def changeUserName(self, user: User, username: str) -> None:
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

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        data = await UserData.objects.prefetch_related("user").get_or_none(username=username,
                                                                           discriminator=discriminator)
        if data is not None:
            return data.user

    async def checkRelationShipAvailable(self, target_user: User, current_user: User) -> None:
        relationship = await self.getRelationship(target_user, current_user)
        if relationship is not None:
            raise InvalidDataErr(400, Errors.make(80007))
        # TODO: check for mutual guilds or mutual friends

    async def reqRelationship(self, target_user: User, current_user: User) -> None:
        await Relationship.objects.create(user1=current_user, user2=target_user, type=RelationshipType.PENDING)

    async def getRelationships(self, user: User, with_data=False) -> list[dict]:
        rels = []
        rel: Relationship
        for rel in await Relationship.objects.filter(or_(user1=user, user2=user)).all():
            if (rel_json := await rel.ds_json(user, with_data)) is not None:
                rels.append(rel_json)
        return rels

    async def getRelationship(self, u1: Union[User, int], u2: Union[User, int]) -> Optional[Relationship]:
        id1 = u1.id if isinstance(u1, User) else u1
        id2 = u2.id if isinstance(u2, User) else u2
        return await Relationship.objects.prefetch_related(["user1", "user2"]).get_or_none(
            ((Relationship.user1.id == id1) & (Relationship.user2.id == id2)) |
            ((Relationship.user1.id == id2) & (Relationship.user2.id == id1))
        )

    async def getRelatedUsers(self, user: User, only_ids=False) -> list:
        users = []
        for r in await Relationship.objects.filter(or_(user1=user, user2=user)).all():
            other_user = r.other_user(user)
            if only_ids:
                users.append(other_user.id)
                continue
            data = await other_user.data
            users.append(data.ds_json)
        for channel in await self.getPrivateChannels(user, with_hidden=True):
            channel = await Channel.objects.get(id=channel.id)
            for recipient in await channel.recipients.all():
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

    async def accRelationship(self, user: User, uid: int) -> None:
        rel = await Relationship.objects.select_related(["user1", "user2"]).get_or_none(
            user1__id=uid, user2__id=user.id, type=RelationshipType.PENDING
        )
        if rel is None:
            return
        await rel.update(type=RelationshipType.FRIEND)

    async def delRelationship(self, user: User, uid: int) -> Optional[Relationship]:
        rel = await self.getRelationship(user, uid)
        if rel.type == RelationshipType.BLOCK:
            rel = await Relationship.objects.select_related(["user1", "user2"]).get_or_none(
                user1__id=user.id, user2__id=uid
            )
            if rel is None:
                return
        await rel.delete()
        return rel

    async def changeUserPassword(self, user: User, new_password: str) -> None:
        await user.update(password=self.hashPassword(user.id, new_password))

    async def getMfa(self, user: User) -> Optional[MFA]:
        settings = await user.settings
        mfa = MFA(settings.mfa, user.id)
        if mfa.valid:
            return mfa

    async def setBackupCodes(self, user: User, codes: list[str]) -> None:
        await self.clearBackupCodes(user)
        await MfaCode.objects.bulk_create([
            MfaCode(user=user, code=code) for code in codes
        ])

    async def clearBackupCodes(self, user: User) -> None:
        await MfaCode.objects.delete(user=user)

    async def getBackupCodes(self, user: User) -> list[MfaCode]:
        return await MfaCode.objects.filter(user=user).limit(10).all()

    def generateMfaTicketSignature(self, user: User, session_id: int) -> str:
        payload = {
            "user_id": user.id,
            "session_id": session_id
        }
        token = JWT.encode(payload, self.key, time() + 300)
        return b64encode(token)

    def verifyMfaTicketSignature(self, user: User, session_id: int, token: str) -> bool:
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

    async def generateUserMfaNonce(self, user: User) -> tuple[str, str]:
        exp = time() + 600
        code = b64encode(urandom(16))
        nonce = JWT.encode({"type": "normal", "code": code, "user_id": user.id}, self.key, exp)
        rnonce = JWT.encode({"type": "regenerate", "code": code, "user_id": user.id}, self.key, exp)
        return nonce, rnonce

    async def verifyUserMfaNonce(self, user: User, nonce: str, regenerate: bool) -> None:
        if not (payload := JWT.decode(nonce, self.key)) or payload["user_id"] != user.id:
            raise InvalidDataErr(400, Errors.make(60011))
        nonce_type = "normal" if not regenerate else "regenerate"
        if nonce_type != payload["type"]:
            raise InvalidDataErr(400, Errors.make(60011))

    async def useMfaCode(self, user: User, code: str) -> bool:
        if (code := await MfaCode.objects.get_or_none(user=user, code=code, used=False)) is None:
            return False
        await code.update(used=True)
        return True

    async def getChannel(self, channel_id: int) -> Optional[Channel]:
        if (channel := await Channel.objects.select_related(["guild", "owner", "parent"])
                .get_or_none(id=channel_id)) is None:
            return
        return await self.setLastMessageIdForChannel(channel)

    async def getDChannel(self, user1: User, user2: User) -> Optional[Channel]:
        channel_row = await Channel.Meta.database.fetch_one(
            query="SELECT * FROM `channels` WHERE `id` = ("
                  "SELECT `channel` FROM `channels_users` WHERE `user` IN (:user1, :user2) GROUP BY `channel` "
                  "HAVING COUNT(DISTINCT `user`) = 2);",
            values={"user1": user1.id, "user2": user2.id}
        )
        if channel_row is None: return
        return await Channel.from_row(channel_row, Channel).load_all()

    async def getDMChannelOrCreate(self, user1: User, user2: User) -> Channel:
        channel = await self.getDChannel(user1, user2)
        if channel is None:
            channel = await Channel.objects.create(id=Snowflake.makeId(), type=ChannelType.DM)
            await channel.recipients.add(user1)
            await channel.recipients.add(user2)
            return await Channel.objects.get(id=channel.id)

        if await self.isDmChannelHidden(user1, channel):
            await self.unhideDmChannel(user1, channel)
            await c.getGw().dispatch(DMChannelCreateEvent(channel), users=[user1.id])
        return await self.setLastMessageIdForChannel(channel)

    async def getLastMessageId(self, channel: Channel) -> Optional[int]:
        if (last_message_id := await Message.objects.filter(channel=channel).max("id")) is not None:
            return last_message_id

    async def setLastMessageIdForChannel(self, channel: Channel) -> Channel:
        channel.last_message_id = await self.getLastMessageId(channel)
        return channel

    async def getChannelMessagesCount(self, channel: Channel) -> int:
        return await Message.objects.filter(channel=channel).count()

    async def getPrivateChannels(self, user: User, with_hidden: bool = False) -> list[Channel]:
        channels = await Channel.objects.select_related("recipients").filter(recipients__id__in=[user.id]).all()
        return [await self.setLastMessageIdForChannel(channel) for channel in channels]

    async def getChannelMessages(self, channel: Channel, limit: int, before: int = 0, after: int = 0) -> list[Message]:
        id_filter = {}
        if after: id_filter["id__gt"] = after
        if before: id_filter["id__lt"] = before
        messages = await Message.objects.select_related(["thread"]).filter(channel=channel, **id_filter).order_by("-id").limit(limit).all()
        # messages.sort(key=lambda msg: msg.id, reverse=True)
        return messages

    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]:
        if not message_id: return
        return await Message.objects.select_related(["author", "channel", "thread", "guild"]) \
            .get_or_none(channel=channel, id=message_id)

    async def sendMessage(self, message: Message) -> Message:
        async def _addToReadStates():
            users = await self.getRelatedUsersToChannel(message.channel)
            if message.author.id in users:
                users.remove(message.author.id)
            for user in users:
                read_state, _ = await ReadState.objects.get_or_create(
                    user=user, channel=message.channel, _defaults={"last_read_id": message.id, "count": 0}
                )
                await read_state.update(count=read_state.count + 1)

        Context().run(get_event_loop().create_task, _addToReadStates())
        return message

    async def getRelatedUsersToChannel(self, channel: Union[Channel, int], ids: bool = True) -> list[Union[int, User]]:
        if isinstance(channel, int):
            channel = await Channel.objects.get_or_none(id=channel)
        if not channel:
            return []
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            if ids: return [recipient.id for recipient in await channel.recipients.all()]
            return await channel.recipients.all()
        elif channel.type in GUILD_CHANNELS:
            return [member.user.id for member in await self.getGuildMembers(channel.guild)]
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return [member.user.id for member in await self.getThreadMembers(channel)]

    async def setReadState(self, user: User, channel: Channel, count: int, last: int) -> None:
        read_state, _ = await ReadState.objects.get_or_create(
            user=user, channel=channel, _defaults={"last_read_id": last, "count": count}
        )
        await read_state.update(last_read_id=last, count=count)

    async def getReadStatesJ(self, user: User) -> list:
        states = []
        st: ReadState
        for st in await ReadState.objects.filter(user=user).all():
            states.append(await st.ds_json())
        return states

    async def getUserNote(self, user: User, target: User) -> Optional[UserNote]:
        return await UserNote.objects.get_or_none(user=user, target=target)

    async def getAttachment(self, attachment_id: int) -> Optional[Attachment]:
        return await Attachment.objects.get_or_none(id=attachment_id)

    async def getUserByChannelId(self, channel_id: int, user_id: int) -> Optional[User]:
        if not (channel := await self.getChannel(channel_id)):
            return None
        return await self.getUserByChannel(channel, user_id)

    async def getUserByChannel(self, channel: Channel, user_id: int) -> Optional[User]:
        if channel.type in (ChannelType.DM, ChannelType.GROUP_DM):
            if await Channel.objects.select_related("recipients").filter(id=channel.id, recipients__id__in=[user_id]) \
                    .exists():
                return await self.getUser(user_id)
        elif channel.type in GUILD_CHANNELS:
            return await self.getGuildMember(channel.guild, user_id)
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return await self.getThreadMember(channel, user_id)

    async def sendVerificationEmail(self, user: User) -> None:
        key = new(self.key, str(user.id).encode('utf-8'), sha256).digest()
        t = int(time())
        sig = b64encode(new(key, f"{user.id}:{user.email}:{t}".encode('utf-8'), sha256).digest())
        token = b64encode(jdumps({"id": user.id, "email": user.email, "time": t}))
        token += f".{sig}"
        link = f"https://{Config.PUBLIC_HOST}/verify#token={token}"
        await EmailMsg(user.email, "Confirm your e-mail in YEPCord",
                       f"Thank you for signing up for a YEPCord account!\nFirst you need to make sure that you are you!"
                       f" Click to verify your email address:\n{link}").send()

    async def verifyEmail(self, user: User, token: str) -> None:
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

    async def getUserByEmail(self, email: str) -> Optional[User]:
        return await User.objects.get_or_none(email=email)

    async def changeUserEmail(self, user: User, email: str) -> None:
        email = email.lower()
        if user.email == email:
            return
        if await self.getUserByEmail(email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))
        await user.update(email=email, verified=False)

    async def sendMfaChallengeEmail(self, user: User, nonce: str) -> None:
        code = await self.mfaNonceToCode(user, nonce)
        await EmailMsg(user.email,
                       f"Your one-time verification key is {code}",
                       f"It looks like you're trying to view your account's backup codes.\n"
                       f"This verification key expires in 10 minutes. This key is extremely sensitive, treat it like a "
                       f"password and do not share it with anyone.\n"
                       f"Enter it in the app to unlock your backup codes:\n{code}").send()

    async def mfaNonceToCode(self, user: User, nonce: str) -> Optional[str]:
        if not (payload := JWT.decode(nonce, self.key)):
            return
        token = JWT.encode({"code": payload["code"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

    async def createDMGroupChannel(self, user: User, recipients: list[User], name: Optional[str] = None) -> Channel:
        if user.id not in recipients:
            recipients.append(user)
        channel = await Channel.objects.create(id=Snowflake.makeId(), type=ChannelType.GROUP_DM, name=name, owner=user)
        for recipient in recipients:
            await channel.recipients.add(recipient)
        return channel

    async def pinMessage(self, message: Message) -> None:
        if await Message.objects.filter(pinned=True, channel=message.channel).count() >= 50:
            raise InvalidDataErr(400, Errors.make(30003))
        message.extra_data["pinned_at"] = int(time())
        await message.update(extra_data=message.extra_data, pinned=True)

    async def getLastPinnedMessage(self, channel: Channel) -> Optional[Message]:
        # TODO: order by pinned timestamp
        return await Message.objects.filter(pinned=True, channel=channel).order_by("-id").get_or_none()

    async def getLastPinTimestamp(self, channel: Channel) -> str:
        last = await self.getLastPinnedMessage(channel)
        last_ts = last.extra_data["pinned_at"] if last is not None else 0
        return datetime.utcfromtimestamp(last_ts).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    async def getPinnedMessages(self, channel: Channel) -> list[Message]:
        return await Message.objects.filter(pinned=True, channel=channel).all()

    async def addReaction(self, message: Message, user: User, emoji: Emoji, emoji_name: str) -> Reaction:
        return await Reaction.objects.get_or_create(user=user, message=message, emoji=emoji, emoji_name=emoji_name)

    async def removeReaction(self, message: Message, user: User, emoji: Emoji, emoji_name: str) -> None:
        await Reaction.objects.delete(user=user, message=message, emoji=emoji, emoji_name=emoji_name)

    async def getMessageReactionsJ(self, message: Message, user: Union[User, int]) -> list:
        if isinstance(user, User):
            user = user.id
        reactions = []
        result = await Channel.Meta.database.fetch_all(
           query=f'SELECT `emoji_name`, `emoji`, COUNT(*) AS ecount, (SELECT COUNT(*) > 0 FROM '
                 f'`reactionss` r2 WHERE `emoji_name`=r1.emoji_name AND (`emoji`=r1.emoji OR (`emoji` IS NULL AND r1.emoji IS NULL)) '
                 f'AND `user`=:user_id) as me FROM `reactionss` r1 WHERE `message`=:message_id GROUP BY '
                 f'`emoji_name`, `emoji`' + ('' if is_sqlite else ' COLLATE utf8mb4_unicode_520_ci'),
           values={"user_id": user, "message_id": message.id}
        )
        for r in result:
            reactions.append(
               {"emoji": {"id": str(r[1]) if r[1] else None, "name": r[0]}, "count": r[2], "me": bool(r[3])}
            )
        return reactions

    async def getReactedUsersJ(self, message: Message, limit: int, emoji: Emoji, emoji_name: str) -> list[dict]:
        users = []
        reactions = await Reaction.objects.select_related("user").filter(
            message=message, emoji=emoji, emoji_name=emoji_name
        ).limit(limit).all()
        for reaction in reactions:
            data = await reaction.user.data
            users.append(data.ds_json)
        return users

    async def searchMessages(self, search_filter: dict) -> tuple[list[Message], int]:
        filter_args = {}
        query = Message.objects.order_by("-id").limit(25)
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

    async def createInvite(self, channel: Channel, inviter: User, max_age: int = 86400, max_uses: int = 0) -> Invite:
        return await Invite.objects.create(
            id=Snowflake.makeId(), channel=channel, inviter=inviter, max_age=max_age, max_uses=max_uses
        )

    async def getInvite(self, invite_id: int) -> Optional[Invite]:
        return await Invite.objects.select_related(["channel", "channel__guild", "inviter"]).get_or_none(id=invite_id)

    async def createGuild(self, guild_id: int, user: User, name: str, icon: str = None) -> Guild:
        guild = await Guild.objects.create(id=guild_id, owner=user, name=name, icon=icon)
        await Role.objects.create(id=guild.id, guild=guild, name="@everyone")

        text_category = await Channel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Text Channels", position=0,
            flags=0, rate_limit=0
        )
        voice_category = await Channel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Voice Channels", position=0,
            flags=0, rate_limit=0
        )
        system_channel = await Channel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_TEXT, guild=guild.id, name="general", position=0, flags=0,
            parent=text_category, rate_limit=0
        )
        await Channel.objects.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_VOICE, guild=guild.id, name="General", position=0, flags=0,
            parent=voice_category, bitrate=64000, user_limit=0, rate_limit=0
        )
        await guild.update(system_channel=system_channel.id)

        await GuildMember.objects.create(id=Snowflake.makeId(), user=user, guild=guild)

        return guild

    async def createGuildFromTemplate(self, guild_id: int, user: User, template: GuildTemplate, name: Optional[str],
                                      icon: Optional[str]) -> Guild:
        guild = await Guild.objects.create(id=guild_id, owner=user.id)

        serialized = template.serialized_guild
        serialized["name"] = name or serialized["name"]
        serialized["icon"] = icon
        replaced_ids: dict[Union[int, NoneType], Union[int, NoneType]] = {None: None, 0: guild_id}
        channels = {}

        for role in serialized["roles"]:
            if role["id"] not in replaced_ids:
                replaced_ids[role["id"]] = Snowflake.makeId()
            role["id"] = replaced_ids[role["id"]]
            await Role.objects.create(guild=guild, **role)

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

            channels[channel_id] = await Channel.objects.create(guild=guild, **channel)
            for overwrite in permission_overwrites:
                overwrite["target_id"] = replaced_ids[overwrite["id"]]
                overwrite["channel"] = channels[channel_id]
                del overwrite["id"]
                await PermissionOverwrite.objects.create(**overwrite)

        serialized["afk_channel"] = replaced_ids.get(serialized["afk_channel_id"], None)
        serialized["system_channel"] = replaced_ids.get(serialized["system_channel_id"], None)
        del serialized["afk_channel_id"]
        del serialized["system_channel_id"]

        del serialized["roles"]
        del serialized["channels"]

        await guild.update(**serialized)
        await GuildMember.objects.create(id=Snowflake.makeId(), user=user, guild=guild)

        return guild

    async def getRole(self, role_id: int) -> Role:
        return await Role.objects.get_or_none(id=role_id)

    async def getRoles(self, guild: Guild, exclude_default=False) -> list[Role]:
        query = Role.objects.filter(guild=guild)
        if exclude_default:
            query = query.exclude(id=guild.id)
        return await query.all()

    async def getGuildMember(self, guild: Guild, user_id: int) -> Optional[GuildMember]:
        return await GuildMember.objects.select_related(["user", "guild"]).get_or_none(guild=guild, user__id=user_id)

    async def getGuildMembers(self, guild: Guild) -> list[GuildMember]:
        return await GuildMember.objects.select_related("user").filter(guild=guild).all()

    async def getGuildMembersIds(self, guild: Guild) -> list[int]:
        return [member.user.id for member in await self.getGuildMembers(guild)]

    async def getGuildChannels(self, guild: Guild) -> list[Channel]:
        return await Channel.objects.filter(guild=guild) \
            .exclude(type__in=[ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD]).all()

    async def getUserGuilds(self, user: User) -> list[Guild]:
        return [member.guild for member in await GuildMember.objects.select_related("guild").filter(user=user).all()]

    async def getGuildMemberCount(self, guild: Guild) -> int:
        return await GuildMember.objects.filter(guild=guild).count()

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        return await Guild.objects.select_related("owner").get_or_none(id=guild_id)

    async def blockUser(self, user: User, block_user: User) -> None:
        rel = await self.getRelationship(user.id, block_user)
        if rel and rel.type != RelationshipType.BLOCK:
            await rel.delete()
        elif rel and rel.type == RelationshipType.BLOCK and rel.user1 == user:
            return
        await Relationship.objects.create(user1=user, user2=block_user, type=RelationshipType.BLOCK)

    async def getEmojis(self, guild_id: int) -> list[Emoji]:
        return await Emoji.objects.filter(guild__id=guild_id).all()

    async def getEmoji(self, emoji_id: int) -> Optional[Emoji]:
        return await Emoji.objects.get_or_none(id=emoji_id)

    async def getEmojiByReaction(self, reaction: str) -> Optional[Emoji]:
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

    async def getGuildInvites(self, guild: Guild) -> list[Invite]:
        return await Invite.objects.select_related(["channel", "channel__guild", "inviter"]) \
            .filter(channel__guild=guild).all()

    async def banGuildMember(self, member: GuildMember, reason: str = None) -> None:
        await GuildBan.objects.create(user=member.user, guild=member.guild, reason=reason)

    async def getGuildBan(self, guild: Guild, user_id: int) -> Optional[GuildMember]:
        return await GuildBan.objects.get_or_none(guild=guild, user__id=user_id)

    async def getGuildBans(self, guild: Guild) -> list[GuildBan]:
        return await GuildBan.objects.filter(guild=guild).all()

    async def bulkDeleteGuildMessagesFromBanned(self, guild: Guild, user_id: int, after_id: int) -> dict[
        int, list[int]]:
        messages = await Message.objects.select_related("channel").filter(
            guild=guild, author__id=user_id, id__gt=after_id
        ).limit(500).all()
        result = {}
        messages_ids = []
        for message in messages:
            if message.channel.id not in result:
                result[message.channel.id] = []
            result[message.channel.id].append(message.id)
            messages_ids.append(message.id)

        await Message.objects.delete(id__in=messages_ids)

        return result

    async def getRolesMemberCounts(self, guild: Guild) -> dict[int, int]:
        counts = {}
        for role in await Role.objects.select_related("guildmembers").filter(guild=guild).all():
            counts[role.id] = len(role.guildmembers)
        return counts

    async def getMutualGuildsJ(self, user: User, current_user: User) -> list[dict[str, str]]:
        user_guilds_member = await GuildMember.objects.select_related("guild").filter(user=user).all()
        user_guild_ids = [member.guild.id for member in user_guilds_member]
        user_guilds_member = {member.guild.id: member for member in user_guilds_member}

        current_user_guilds_member = await GuildMember.objects.select_related("guild").filter(user=current_user).all()
        current_user_guild_ids = [member.guild.id for member in current_user_guilds_member]

        mutual_guilds_ids = set(user_guild_ids) & set(current_user_guild_ids)
        mutual_guilds_json = []
        for guild_id in mutual_guilds_ids:
            member = user_guilds_member[guild_id]
            mutual_guilds_json.append({"id": str(guild_id), "nick": member.nick})

        return mutual_guilds_json

    async def getAttachments(self, message: Message) -> list[Attachment]:
        return await Attachment.objects.filter(message=message).all()

    async def getMemberRolesIds(self, member: GuildMember, include_default: bool = False) -> list[int]:
        roles = await member.roles.all() if not member.roles else member.roles
        roles_ids = [role.id for role in roles]
        if include_default:
            roles_ids.append(member.guild.id)
        return roles_ids

    async def setMemberRolesFromList(self, member: GuildMember, roles: list[Role]) -> None:
        current_roles = await member.roles.all()
        for role in roles:
            if role not in current_roles:
                await member.roles.add(role)
        for role in current_roles:
            if role not in roles:
                await member.roles.remove(role)

    async def getMemberRoles(self, member: GuildMember, include_default: bool = False) -> list[Role]:
        roles = await member.roles.all()
        if include_default:
            roles.append(await Role.objects.get(id=member.guild.id))

        roles.sort(key=lambda r: r.position)
        return roles

    async def removeGuildBan(self, guild: Guild, user_id: int) -> None:
        await GuildBan.objects.delete(guild=guild, user__id=user_id)

    async def getRoleMemberIds(self, role: Role) -> list[int]:
        role = await Role.objects.select_related("guildmembers").get(id=role.id)
        return [member.id for member in role.guildmembers]

    async def getGuildMembersGw(self, guild: Guild, query: str, limit: int) -> list[GuildMember]:
        # noinspection PyUnresolvedReferences
        return await GuildMember.objects.filter(
            (GuildMember.guild == guild) &
            (GuildMember.nick.startswith(query) | GuildMember.user.userdatas.username.istartswith(query))
        ).limit(limit).all()

    async def memberHasRole(self, member: GuildMember, role: Role) -> bool:
        return await member.roles.filter(id=role.id).exists()

    async def getPermissionOverwrite(self, channel: Channel, target_id: int) -> Optional[PermissionOverwrite]:
        return await PermissionOverwrite.objects.select_related(["channel", "channel__guild"])\
            .get_or_none(channel=channel, target_id=target_id)

    async def getPermissionOverwrites(self, channel: Channel) -> list[PermissionOverwrite]:
        return await PermissionOverwrite.objects.filter(channel=channel).all()

    async def deletePermissionOverwrite(self, channel: Channel, target_id: int) -> None:
        if (overwrite := await self.getPermissionOverwrite(channel, target_id)) is not None:
            await overwrite.delete()

    async def getOverwritesForMember(self, channel: Channel, member: GuildMember) -> list[PermissionOverwrite]:
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

    async def getChannelInvites(self, channel: Channel) -> list[Invite]:
        await Invite.Meta.database.execute(
            query="DELETE FROM `invites` WHERE channel=:channel_id AND `max_age` > 0 AND "
                  "`max_age` + (((`id` >> 22) + :sf_epoch) / 1000) < :current_time;",
            values={"channel_id": channel.id, "current_time": int(time()), "sf_epoch": Snowflake.EPOCH}
        )
        return await Invite.objects.select_related(["channel__guild", "inviter"]) \
            .filter(channel=channel, vanity_code__isnull=True).all()

    async def getVanityCodeInvite(self, code: str) -> Optional[Invite]:
        if code is None: return
        return await Invite.objects.filter(vanity_code=code).all()

    async def useInvite(self, invite: Invite) -> None:
        if 0 < invite.max_uses <= invite.uses + 1:
            await invite.delete()
        else:
            await invite.update(uses=invite.uses + 1)

    async def getAuditLogEntries(self, guild: Guild, limit: int, before: Optional[int] = None) -> list[AuditLogEntry]:
        before = {} if before is None else {"id__lt": before}
        return await AuditLogEntry.objects.filter(guild=guild, **before).limit(limit).all()

    async def getGuildTemplate(self, guild: Guild) -> Optional[GuildTemplate]:
        return await GuildTemplate.objects.get_or_none(guild=guild)

    async def getGuildTemplateById(self, template_id: int) -> Optional[GuildTemplate]:
        return await GuildTemplate.objects.get_or_none(id=template_id)

    async def setTemplateDirty(self, guild: Guild) -> None:
        if not (template := await self.getGuildTemplate(guild)):
            return
        await template.update(is_dirty=True)

    async def getWebhooks(self, guild: Guild) -> list[Webhook]:
        return await Webhook.objects.select_related(["channel", "channel__guild", "user"])\
            .filter(channel__guild=guild).all()

    async def getChannelWebhooks(self, channel: Channel) -> list[Webhook]:
        return await Webhook.objects.select_related(["channel", "channel__guild", "user"]).filter(channel=channel).all()

    async def getWebhook(self, webhook_id: int) -> Optional[Webhook]:
        return await Webhook.objects.select_related(["channel", "channel__guild", "user"]).get_or_none(id=webhook_id)

    async def hideDmChannel(self, user: User, channel: Channel) -> None:
        await HiddenDmChannel.objects.get_or_create(user=user, channel=channel)

    async def unhideDmChannel(self, user: User, channel: Channel) -> None:
        await HiddenDmChannel.objects.delete(user=user, channel=channel)

    async def isDmChannelHidden(self, user: User, channel: Channel) -> bool:
        return await HiddenDmChannel.objects.filter(user=user, channel=channel).exists()

    async def getGuildStickers(self, guild: Guild) -> list[Sticker]:
        return await Sticker.objects.filter(guild=guild).all()

    async def getSticker(self, sticker_id: int) -> Optional[Sticker]:
        return await Sticker.objects.get_or_none(id=sticker_id)

    async def getUserOwnedGuilds(self, user: User) -> list[Guild]:
        return await Guild.objects.filter(owner=user).all()

    async def getUserOwnedGroups(self, user: User) -> list[Channel]:
        return await Channel.objects.filter(owner=user, type=ChannelType.GROUP_DM).all()

    async def deleteUser(self, user: User) -> None:
        await user.update(deleted=True, email=f"deleted_{user.id}@yepcord.ml", password="")
        data = await user.data
        await data.update(discriminator=0, username=f"Deleted User {hex(user.id)[2:]}", avatar=None,
                          avatar_decoration=None, public_flags=0)
        await Session.objects.delete(user=user)
        await Relationship.objects.delete(or_(user1=user, user2=user))
        await MfaCode.objects.delete(user=user)
        await GuildMember.objects.delete(user=user)
        await UserSettings.objects.delete(user=user)
        await FrecencySettings.objects.delete(user=user)
        await Invite.objects.delete(inviter=user)
        await ReadState.objects.delete(user=user)

    async def getGuildEventUserCount(self, event: GuildEvent) -> int:
        return await event.subscribers.count()

    async def getGuildEvent(self, event_id: int) -> Optional[GuildEvent]:
        return await GuildEvent.objects.get_or_none(id=event_id)

    async def getGuildEvents(self, guild: Guild) -> list[GuildEvent]:
        return await GuildEvent.objects.filter(guild=guild).all()

    async def getSubscribedGuildEventIds(self, user: User, guild_id: int) -> list[int]:
        _user = await User.objects.select_related("guildmembers__guildevents") \
            .get(id=user.id, guildmembers__guild__id=guild_id)
        events_ids = []
        for member in _user.guildmembers:
            for event in member.guildevents:
                events_ids.append(event.id)
        return events_ids

    async def getThreadMetadata(self, thread: Channel) -> Optional[ThreadMetadata]:
        return await ThreadMetadata.objects.get_or_none(channel=thread)

    async def getThreadMembersCount(self, thread: Channel) -> int:
        return await ThreadMember.objects.filter(channel=thread).count()

    async def getThreadMembers(self, thread: Channel, limit: int = 100) -> list[ThreadMember]:
        return await ThreadMember.objects.select_related("user").filter(channel=thread).limit(limit).all()

    async def getGuildMemberThreads(self, guild: Guild, user_id: int) -> list[Channel]:
        return await ThreadMember.objects.select_related("channel").filter(guild=guild, user__id=user_id).all()

    async def getThreadMember(self, thread: Channel, user_id: int) -> Optional[ThreadMember]:
        return await ThreadMember.objects.get_or_none(channel=thread, user__id=user_id)

    def getLanguageCode(self, ip: str, default: str="en-US") -> str:
        if self.ipdb is None and not os.path.exists("other/ip_database.mmdb"):
            return default
        if self.ipdb is None:
            self.ipdb = maxminddb.open_database("other/ip_database.mmdb")

        try:
            country_code = (self.ipdb.get(ip) or {"country": {"iso_code": None}})["country"]["iso_code"] or default
        except (ValueError, KeyError):
            return default
        country_to_language = {
            "UA": "uk", "US": "en-US", "BG": "bg", "CZ": "cs", "DK": "da", "DE": "de", "GR": "el", "GB": "en-GB",
            "ES": "es-ES", "FI": "fi", "FR": "fr", "IN": "hi", "HR": "hr", "HU": "hu", "IT": "it", "JP": "ja",
            "KR": "ko", "LT": "lt", "NL": "nl", "NO": "no", "PL": "pl", "BR": "pt-BR", "RO": "ro", "RU": "RU",
            "SE": "sv-SE", "TH": "th", "TR": "tr", "VN": "vi", "CN": "zh-CN", "TW": "zh-TW",
        }

        return country_to_language.get(country_code, default)


import src.yepcord.ctx as c

c._getCore = lambda: Core.getInstance()
c._getCDNStorage = lambda: CDN.getInstance().storage
