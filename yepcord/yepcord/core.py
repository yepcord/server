"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2024 RuslanUC

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
from tortoise.expressions import Q, Subquery
from tortoise.functions import Count
from tortoise.transactions import atomic

from . import ctx
from .classes.other import EmailMsg, JWT, MFA
from .classes.singleton import Singleton
from .config import Config
from .enums import ChannelType, GUILD_CHANNELS
from .errors import InvalidDataErr, MfaRequiredErr, Errors
from .models import User, UserData, UserSettings, Session, Relationship, Channel, Message, ReadState, FrecencySettings, \
    Emoji, Invite, Guild, GuildMember, GuildTemplate, Reaction, Sticker, PermissionOverwrite, GuildBan, AuditLogEntry, \
    Webhook, HiddenDmChannel, MfaCode, Role, GuildEvent, ThreadMember
from .snowflake import Snowflake
from .storage import getStorage
from .utils import b64encode, b64decode, int_size, NoneType
from ..gateway.events import DMChannelCreateEvent


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    def __init__(self, key=None):
        self.key = key if key and len(key) >= 16 and isinstance(key, bytes) else urandom(32)
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
        return hashpw(password, gensalt(Config.BCRYPT_ROUNDS)).decode("utf8")

    def generateSessionSignature(self) -> str:
        return b64encode(urandom(32))

    async def getRandomDiscriminator(self, login: str) -> Optional[int]:
        for _ in range(5):
            d = randint(1, 9999)
            if not await User.y.getByUsername(login, d):
                return d

    @atomic()
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

        user = await User.create(id=uid, email=email, password=password)
        await UserData.create(id=uid, user=user, birth=birth, username=login, discriminator=discriminator)
        await UserSettings.create(id=uid, user=user, locale=locale)

        session = await Session.create(id=Snowflake.makeId(), user=user, signature=signature)
        await self.sendVerificationEmail(user)
        return session

    async def login(self, email: str, password: str) -> Session:
        email = email.strip().lower()
        user = await User.get_or_none(email=email)
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
        return await Session.Y.create(user)

    async def getRelationships(self, user: User, with_data=False) -> list[dict]:
        rels = []
        rel: Relationship
        for rel in await (Relationship.filter(Q(from_user=user) | Q(to_user=user))
                          .select_related("from_user", "to_user").all()):
            if (rel_json := await rel.ds_json(user, with_data)) is not None:
                rels.append(rel_json)
        return rels

    async def getRelatedUsers(self, user: User, only_ids=False) -> list:
        users = []
        for r in await (Relationship.filter(Q(from_user=user) | Q(to_user=user)).select_related("from_user", "to_user")
                        .all()):
            other_user = r.other_user(user)
            if only_ids:
                users.append(other_user.id)
                continue
            data = await other_user.data
            users.append(data.ds_json)
        for channel in await self.getPrivateChannels(user, with_hidden=True):
            channel = await Channel.get(id=channel.id)
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
        if not (user := await User.y.get(uid)):
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

    async def getChannel(self, channel_id: Optional[int]) -> Optional[Channel]:
        if channel_id is None:
            return
        if (channel := await Channel.get_or_none(id=channel_id).select_related("guild", "owner", "parent")) is None:
            return
        return await self.setLastMessageIdForChannel(channel)

    async def getDChannel(self, user1: User, user2: User) -> Optional[Channel]:
        return await Channel.get_or_none(
            id__in=Subquery(
                Channel
                .filter(recipients__id__in=[user1.id, user2.id])
                .annotate(user_count=Count('recipients__id', distinct=True))
                .filter(user_count=2)
                .group_by("id")
                .values_list('id', flat=True)
            )
        )

    async def getDMChannelOrCreate(self, user1: User, user2: User) -> Channel:
        channel = await self.getDChannel(user1, user2)
        if channel is None:
            channel = await Channel.create(id=Snowflake.makeId(), type=ChannelType.DM)
            await channel.recipients.add(user1)
            await channel.recipients.add(user2)
            return await Channel.get(id=channel.id)

        if await self.isDmChannelHidden(user1, channel):
            await self.unhideDmChannel(user1, channel)
            await ctx.getGw().dispatch(DMChannelCreateEvent(channel), user_ids=[user1.id])
        return await self.setLastMessageIdForChannel(channel)

    async def getLastMessageId(self, channel: Channel) -> Optional[int]:
        if (last_message := await Message.filter(channel=channel).group_by("-id").first()) is not None:
            return last_message.id

    async def setLastMessageIdForChannel(self, channel: Channel) -> Channel:
        channel.last_message_id = await self.getLastMessageId(channel)
        return channel

    async def getChannelMessagesCount(self, channel: Channel) -> int:
        return await Message.filter(channel=channel).count()

    async def getPrivateChannels(self, user: User, with_hidden: bool = False) -> list[Channel]:
        channels = await Channel.filter(recipients__id=user.id).select_related("owner").all()
        channels = [
            channel for channel in channels if not with_hidden and not await self.isDmChannelHidden(user, channel)
        ]
        return [await self.setLastMessageIdForChannel(channel) for channel in channels]

    async def getChannelMessages(self, channel: Channel, limit: int, before: int = 0, after: int = 0) -> list[Message]:
        id_filter = {}
        if after: id_filter["id__gt"] = after
        if before: id_filter["id__lt"] = before
        messages = await (Message.filter(channel=channel, ephemeral=False, **id_filter)
                          .select_related(*Message.DEFAULT_RELATED)
                          .order_by("-id").limit(limit).all())
        return messages

    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]:
        if not message_id: return
        return await (Message.get_or_none(channel=channel, id=message_id)
                      .select_related(*Message.DEFAULT_RELATED))

    async def sendMessage(self, message: Message) -> Message:
        async def _addToReadStates():
            users = await self.getRelatedUsersToChannel(message.channel, False)
            if message.author.id in users:
                users.remove(message.author.id)
            for user in users:
                read_state, _ = await ReadState.get_or_create(
                    user=user, channel=message.channel, defaults={"last_read_id": message.id, "count": 0}
                )
                read_state.count += 1
                await read_state.save(update_fields=["count"])

        Context().run(get_event_loop().create_task, _addToReadStates())
        return message

    async def getRelatedUsersToChannel(self, channel: Union[Channel, int], ids: bool = True) -> list[Union[int, User]]:
        if isinstance(channel, int):
            channel = await Channel.get_or_none(id=channel).select_related("guild")
        if not channel:
            return []
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            if ids: return [recipient.id for recipient in await channel.recipients.all()]
            return await channel.recipients.all()
        elif channel.type in GUILD_CHANNELS:
            return [member.user.id if ids else member.user for member in await self.getGuildMembers(channel.guild)]
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return [member.user.id if ids else member.user for member in await self.getThreadMembers(channel)]

    async def setReadState(self, user: User, channel: Channel, count: int, last: int) -> None:
        read_state, _ = await ReadState.get_or_create(
            user=user, channel=channel, defaults={"last_read_id": last, "count": count}
        )
        read_state.last_read_id = last
        read_state.count = count
        await read_state.save(update_fields=["last_read_id", "count"])

    async def getReadStatesJ(self, user: User) -> list:
        states = []
        st: ReadState
        for st in await ReadState.filter(user=user).select_related("channel", "user").all():
            states.append(await st.ds_json())
        return states

    async def getUserByChannelId(self, channel_id: int, user_id: int) -> Optional[User]:
        if not (channel := await self.getChannel(channel_id)):
            return None
        return await self.getUserByChannel(channel, user_id)

    async def getUserByChannel(self, channel: Channel, user_id: int) -> Optional[User]:
        if channel.type in (ChannelType.DM, ChannelType.GROUP_DM):
            if await Channel.filter(id=channel.id, recipients__id__in=[user_id]).select_related("recipients").exists():
                return await User.y.get(user_id)
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
        user.verified = True
        await user.save(update_fields=["verified"])

    async def getUserByEmail(self, email: str) -> Optional[User]:
        return await User.get_or_none(email=email)

    async def changeUserEmail(self, user: User, email: str) -> None:  # TODO
        email = email.lower()
        if user.email == email:
            return
        if await self.getUserByEmail(email):
            raise InvalidDataErr(400, Errors.make(50035, {"email": {"code": "EMAIL_ALREADY_REGISTERED",
                                                                    "message": "Email address already registered."}}))
        await user.update(email=email, verified=False)

    async def mfaNonceToCode(self, nonce: str) -> Optional[str]:
        if not (payload := JWT.decode(nonce, self.key)):
            return
        token = JWT.encode({"code": payload["code"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

    async def createDMGroupChannel(self, user: User, recipients: list[User], name: Optional[str] = None) -> Channel:
        if user.id not in recipients:
            recipients.append(user)
        channel = await Channel.create(id=Snowflake.makeId(), type=ChannelType.GROUP_DM, name=name, owner=user)
        for recipient in recipients:
            await channel.recipients.add(recipient)
        return channel

    async def getLastPinnedMessage(self, channel: Channel) -> Optional[Message]:
        return await (Message.filter(pinned_timestamp__not_isnull=True, channel=channel).order_by("-pinned_timestamp")
                      .limit(1).get_or_none())

    async def getMessageReactionsJ(self, message: Message, user: Union[User, int]) -> list:
        if isinstance(user, User):
            user = user.id
        reactions = []
        result = await (Reaction.filter(message=message)
                        .group_by("emoji_name", "emoji__id")
                        .annotate(count=Count("id"))
                        .values("id", "emoji_name", "emoji__id", "count"))

        me_results = set(await Reaction.filter(message=message, user=user).values_list("id", flat=True))

        for r in result:
            reactions.append({
                "emoji": {"id": str(r["emoji__id"]) if r["emoji__id"] else None, "name": r["emoji_name"]},
                "count": r["count"],
                "me": r["id"] in me_results
            })
        return reactions

    async def searchMessages(self, channel: Channel, search_filter: dict) -> tuple[list[Message], int]:
        filter_args = {"channel": channel}
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
        if "content" in search_filter:
            filter_args["content__icontains"] = search_filter["content"]
        query = (Message.filter(**filter_args).select_related("author", "channel", "thread", "guild")
                 .order_by("-id").limit(25))
        if "offset" in search_filter:
            query = query.offset(search_filter["offset"])
        messages = await query.all()
        count = await query.count()
        return messages, count

    @atomic()
    async def createGuild(self, guild_id: int, user: User, name: str, icon: str = None) -> Guild:
        guild = await Guild.create(id=guild_id, owner=user, name=name, icon=icon)
        await Role.create(id=guild.id, guild=guild, name="@everyone")

        text_category = await Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Text Channels", position=0,
            flags=0, rate_limit=0
        )
        voice_category = await Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_CATEGORY, guild=guild, name="Voice Channels", position=0,
            flags=0, rate_limit=0
        )
        system_channel = await Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_TEXT, guild=guild, name="general", position=0, flags=0,
            parent=text_category, rate_limit=0
        )
        await Channel.create(
            id=Snowflake.makeId(), type=ChannelType.GUILD_VOICE, guild=guild, name="General", position=0, flags=0,
            parent=voice_category, bitrate=64000, user_limit=0, rate_limit=0
        )
        guild.system_channel = system_channel.id
        await guild.save(update_fields=["system_channel"])

        await GuildMember.create(id=Snowflake.makeId(), user=user, guild=guild)

        return guild

    @atomic()
    async def createGuildFromTemplate(self, guild_id: int, user: User, template: GuildTemplate, name: Optional[str],
                                      icon: Optional[str]) -> Guild:
        serialized = template.serialized_guild
        name = serialized["name"] = name or serialized["name"]
        guild = await Guild.create(id=guild_id, owner=user, name=name)

        serialized["icon"] = icon
        replaced_ids: dict[Union[int, NoneType], Union[int, NoneType]] = {None: None, 0: guild_id}
        channels = {}
        roles = {}

        for role in serialized["roles"]:
            if role["id"] not in replaced_ids:
                replaced_ids[role["id"]] = Snowflake.makeId()
            role["id"] = replaced_ids[role["id"]]
            roles[role["id"]] = await Role.create(guild=guild, **role)

        for channel in serialized["channels"]:
            if channel["id"] not in replaced_ids:
                replaced_ids[channel["id"]] = Snowflake.makeId()
            channel["id"] = channel_id = replaced_ids[channel["id"]]
            channel["parent"] = channels.get(replaced_ids.get(channel["parent_id"], None), None)
            channel["rate_limit"] = channel["rate_limit_per_user"]
            channel["default_auto_archive"] = channel["default_auto_archive_duration"]

            del channel["parent_id"]
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

            channels[channel_id] = await Channel.create(guild=guild, **channel)
            for overwrite in permission_overwrites:
                overwrite["target_role"] = roles[replaced_ids[overwrite["id"]]]
                overwrite["channel"] = channels[channel_id]
                del overwrite["id"]
                await PermissionOverwrite.create(**overwrite)

        serialized["afk_channel"] = replaced_ids.get(serialized["afk_channel_id"], None)
        serialized["system_channel"] = replaced_ids.get(serialized["system_channel_id"], None)
        del serialized["afk_channel_id"]
        del serialized["system_channel_id"]

        del serialized["roles"]
        del serialized["channels"]

        await guild.update(**serialized)
        await GuildMember.create(id=Snowflake.makeId(), user=user, guild=guild)

        return guild

    async def getRole(self, role_id: int, guild: Optional[Guild] = None) -> Role:
        q = {"id": role_id}
        if guild is not None:
            q["guild"] = guild
        return await Role.get_or_none(**q).select_related("guild")

    async def getRoles(self, guild: Guild, exclude_default=False) -> list[Role]:
        query = Role.filter(guild=guild).select_related("guild")
        if exclude_default:
            query = query.exclude(id=guild.id)
        return await query.all()

    async def getGuildMember(self, guild: Guild, user_id: int) -> Optional[GuildMember]:
        return await GuildMember.get_or_none(guild=guild, user__id=user_id).select_related("user", "guild",
                                                                                           "guild__owner")

    async def getGuildMembers(self, guild: Guild) -> list[GuildMember]:
        return await GuildMember.filter(guild=guild).select_related("user").all()

    async def getGuildChannels(self, guild: Guild) -> list[Channel]:
        return await Channel.filter(guild=guild) \
            .exclude(type__in=[ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD])\
            .select_related("guild", "parent").all()

    async def getUserGuilds(self, user: User) -> list[Guild]:
        return [member.guild for member in await GuildMember.filter(user=user).select_related("guild", "guild__owner").all()]

    async def getGuildMemberCount(self, guild: Guild) -> int:
        return await GuildMember.filter(guild=guild).count()

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        return await Guild.get_or_none(id=guild_id).select_related("owner")

    async def getEmojis(self, guild_id: int) -> list[Emoji]:
        return await Emoji.filter(guild__id=guild_id).select_related("user").all()

    async def getEmoji(self, emoji_id: int) -> Optional[Emoji]:
        return await Emoji.get_or_none(id=emoji_id).select_related("guild")

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

    async def getGuildBan(self, guild: Guild, user_id: int) -> Optional[GuildMember]:
        return await GuildBan.get_or_none(guild=guild, user__id=user_id)

    async def bulkDeleteGuildMessagesFromBanned(
            self, guild: Guild, user_id: int, after_id: int
    ) -> dict[Channel, list[int]]:
        messages = await (Message.filter(guild=guild, author__id=user_id, id__gt=after_id).select_related("channel")
                          .limit(500).all())
        result = {}
        messages_ids = []
        for message in messages:
            if message.channel not in result:
                result[message.channel] = []
            result[message.channel].append(message.id)
            messages_ids.append(message.id)

        await Message.filter(id__in=messages_ids).delete()

        return result

    async def getMutualGuildsJ(self, user: User, current_user: User) -> list[dict[str, str]]:
        user_guilds_member = await GuildMember.filter(user=user).select_related("guild").all()
        user_guild_ids = [member.guild.id for member in user_guilds_member]
        user_guilds_member = {member.guild.id: member for member in user_guilds_member}

        current_user_guilds_member = await GuildMember.filter(user=current_user).select_related("guild").all()
        current_user_guild_ids = [member.guild.id for member in current_user_guilds_member]

        mutual_guilds_ids = set(user_guild_ids) & set(current_user_guild_ids)
        mutual_guilds_json = []
        for guild_id in mutual_guilds_ids:
            member = user_guilds_member[guild_id]
            mutual_guilds_json.append({"id": str(guild_id), "nick": member.nick})

        return mutual_guilds_json

    async def getMemberRolesIds(self, member: GuildMember, include_default: bool = False) -> list[int]:
        roles_ids = [role.id for role in await member.roles.all()]
        if include_default:
            roles_ids.append(member.guild.id)
        return roles_ids

    async def setMemberRolesFromList(self, member: GuildMember, roles: list[Role]) -> tuple[list, list]:
        current_roles = await member.roles.all()
        add = []
        remove = []
        for role in roles:
            if role not in current_roles and not role.managed:
                add.append(role.id)
                await member.roles.add(role)
        for role in current_roles:
            if role not in roles and not role.managed:
                remove.append(role.id)
                await member.roles.remove(role)

        return add, remove

    async def getMemberRoles(self, member: GuildMember, include_default: bool = False) -> list[Role]:
        roles = await member.roles.all()
        if include_default:
            roles.append(await Role.get(id=member.guild.id))

        roles.sort(key=lambda r: r.position)
        return roles

    async def getGuildMembersGw(self, guild: Guild, query: str, limit: int, user_ids: list[int]) -> list[GuildMember]:
        # noinspection PyUnresolvedReferences
        return await GuildMember.filter(
            Q(guild=guild) &
            (Q(nick__startswith=query) | Q(user__userdatas__username__istartswith=query))  #&
            #((GuildMember.user.id in user_ids) if user_ids else (GuildMember.user.id not in [0]))
        ).select_related("user").limit(limit).all()

    async def getPermissionOverwrite(self, channel: Channel, target: Union[Role, User]) -> Optional[PermissionOverwrite]:
        kw = {"target_role": target} if isinstance(target, Role) else {"target_user": target}
        return await (PermissionOverwrite.get_or_none(channel=channel, **kw)
                      .select_related("channel", "channel__guild", "target_role", "target_user"))

    async def getPermissionOverwriteUnk(self, channel: Channel, target_id: int) -> Optional[PermissionOverwrite]:
        q = Q(target_role__id=target_id) | Q(target_user__id=target_id)
        return await (PermissionOverwrite.filter(channel=channel).get_or_none(q)
                      .select_related("channel", "channel__guild", "target_role", "target_user"))

    async def getPermissionOverwrites(self, channel: Channel) -> list[PermissionOverwrite]:
        return await PermissionOverwrite.filter(channel=channel).select_related("target_role", "target_user").all()

    async def getOverwritesForMember(self, channel: Channel, member: GuildMember) -> list[PermissionOverwrite]:
        roles = await self.getMemberRoles(member, True)
        roles.sort(key=lambda r: r.position)
        roles = {role.id: role for role in roles}
        overwrites = await self.getPermissionOverwrites(channel)
        overwrites.sort(key=lambda r: r.type)
        result = []
        for overwrite in overwrites:
            if overwrite.target.id in roles or overwrite.target == member.user:
                result.append(overwrite)
        return result

    async def getVanityCodeInvite(self, code: str) -> Optional[Invite]:
        if code is None: return
        return await Invite.get_or_none(vanity_code=code)

    async def useInvite(self, invite: Invite) -> None:
        if 0 < invite.max_uses <= invite.uses + 1:
            await invite.delete()
        else:
            invite.uses += 1
            await invite.save(update_fields=["uses"])

    async def getAuditLogEntries(self, guild: Guild, limit: int, before: Optional[int] = None) -> list[AuditLogEntry]:
        before = {} if before is None else {"id__lt": before}
        return await AuditLogEntry.filter(guild=guild, **before).select_related("guild", "user").limit(limit).all()

    async def getGuildTemplate(self, guild: Guild) -> Optional[GuildTemplate]:
        return await GuildTemplate.get_or_none(guild=guild).select_related("creator", "guild")

    async def getGuildTemplateById(self, template_id: int, guild: Optional[Guild] = None) -> Optional[GuildTemplate]:
        q = {"id": template_id}
        if guild is not None:
            q["guild"] = guild
        return await GuildTemplate.get_or_none(**q).select_related("guild", "creator")

    async def setTemplateDirty(self, guild: Guild) -> None:
        if not (template := await self.getGuildTemplate(guild)):
            return
        template.is_dirty = True
        await template.save(update_fields=["is_dirty"])

    async def getWebhook(self, webhook_id: int) -> Optional[Webhook]:
        return await Webhook.get_or_none(id=webhook_id).select_related("channel", "channel__guild", "user")

    async def unhideDmChannel(self, user: User, channel: Channel) -> None:
        await HiddenDmChannel.filter(user=user, channel=channel).delete()

    async def isDmChannelHidden(self, user: User, channel: Channel) -> bool:
        return await HiddenDmChannel.filter(user=user, channel=channel).exists()

    async def getGuildStickers(self, guild: Guild) -> list[Sticker]:
        return await Sticker.filter(guild=guild).select_related("guild", "user").all()

    async def getSticker(self, sticker_id: int) -> Optional[Sticker]:
        return await Sticker.get_or_none(id=sticker_id).select_related("guild", "user")

    async def deleteUser(self, user: User) -> None:
        await user.update(deleted=True, email=f"deleted_{user.id}@yepcord.ml", password="")
        data = await user.data
        await data.update(discriminator=0, username=f"Deleted User {hex(user.id)[2:]}", avatar=None, public_flags=0,
                          avatar_decoration=None)
        await Session.filter(user=user).delete()
        await Relationship.filter(Q(from_user=user) | Q(to_user=user)).delete()
        await MfaCode.filter(user=user).delete()
        await GuildMember.filter(user=user).delete()
        await UserSettings.filter(user=user).delete()
        await FrecencySettings.filter(user=user).delete()
        await Invite.filter(inviter=user).delete()
        await ReadState.filter(user=user).delete()

    async def getGuildEvent(self, event_id: int) -> Optional[GuildEvent]:
        return await GuildEvent.get_or_none(id=event_id).select_related("channel", "guild", "creator")

    async def getGuildEvents(self, guild: Guild) -> list[GuildEvent]:
        return await GuildEvent.filter(guild=guild).select_related("channel", "guild", "creator").all()

    #async def getSubscribedGuildEventIds(self, user: User, guild_id: int) -> list[int]:
    #    events_ids = []
    #    for member in await GuildMember.filter(user=user, guild__id=guild_id).all():
    #        events_ids.extend(await member.guildevents.filter().values_list("id", flat=True))
    #    return events_ids

    async def getThreadMembers(self, thread: Channel, limit: int = 100) -> list[ThreadMember]:
        return await ThreadMember.filter(channel=thread).select_related("user").limit(limit).all()

    async def getThreadMember(self, thread: Channel, user_id: int) -> Optional[ThreadMember]:
        return await ThreadMember.get_or_none(channel=thread, user__id=user_id)

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


ctx._getCore = lambda: Core.getInstance()
ctx._getCDNStorage = lambda: getStorage()
