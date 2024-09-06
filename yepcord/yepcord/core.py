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
from hashlib import sha256
from hmac import new
from json import loads as jloads, dumps as jdumps
from os import urandom
from time import time
from typing import Optional

import maxminddb
from tortoise.expressions import Q

from . import ctx
from .classes.other import EmailMsg, JWT, MFA
from .classes.singleton import Singleton
from .config import Config
from .enums import ChannelType, GUILD_CHANNELS
from .errors import InvalidDataErr, Errors, InvalidKey
from .models import User, Channel, Message, ReadState, Invite, Guild, GuildMember, ThreadMember
from .storage import getStorage
from .utils import b64encode, b64decode


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    def __init__(self):
        self.key = b64decode(Config.KEY)
        self.ipdb = None

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
            raise InvalidKey
        nonce_type = "normal" if not regenerate else "regenerate"
        if nonce_type != payload["type"]:
            raise InvalidKey

    #async def sendMessage(self, message: Message) -> Message:
    #    async def _addToReadStates():  # TODO: recalculate read states when requested by user
    #        users = await self.getRelatedUsersToChannel(message.channel)
    #        if message.author in users:
    #            users.remove(message.author)
    #        for user in users:
    #            read_state, _ = await ReadState.get_or_create(
    #                user=user, channel=message.channel, defaults={"last_read_id": message.id, "count": 0}
    #            )
    #            read_state.count += 1
    #            await read_state.save(update_fields=["count"])

    #    return message

    async def getRelatedUsersToChannelCount(self, channel: Channel) -> int:
        if channel.type in [ChannelType.DM, ChannelType.GROUP_DM]:
            return await channel.recipients.filter().count()
        elif channel.type in GUILD_CHANNELS:
            return await GuildMember.filter(guild=channel.guild).count()
        elif channel.type in (ChannelType.GUILD_PUBLIC_THREAD, ChannelType.GUILD_PRIVATE_THREAD):
            return await ThreadMember.filter(channel=channel).count()

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
        for st in await ReadState.filter(user=user).select_related("channel", "user"):
            states.append(await st.ds_json())
        return states

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

    async def mfaNonceToCode(self, nonce: str) -> Optional[str]:
        if not (payload := JWT.decode(nonce, self.key)):
            return
        token = JWT.encode({"code": payload["code"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

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

        messages = await query
        count = await query.count()
        return messages, count

    async def getGuildMembers(self, guild: Guild) -> list[GuildMember]:
        return await GuildMember.filter(guild=guild).select_related("user")

    async def getGuildMemberCount(self, guild: Guild) -> int:
        return await GuildMember.filter(guild=guild).count()

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        return await Guild.get_or_none(id=guild_id).select_related("owner")

    async def bulkDeleteGuildMessagesFromBanned(
            self, guild: Guild, user_id: int, after_id: int
    ) -> dict[Channel, list[int]]:
        messages = await (Message.filter(guild=guild, author__id=user_id, id__gt=after_id).select_related("channel")
                          .limit(500))
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
        user_guilds_member = await GuildMember.filter(user=user).select_related("guild")
        user_guild_ids = [member.guild.id for member in user_guilds_member]
        user_guilds_member = {member.guild.id: member for member in user_guilds_member}

        current_user_guilds_member = await GuildMember.filter(user=current_user).select_related("guild")
        current_user_guild_ids = [member.guild.id for member in current_user_guilds_member]

        mutual_guilds_ids = set(user_guild_ids) & set(current_user_guild_ids)
        mutual_guilds_json = []
        for guild_id in mutual_guilds_ids:
            member = user_guilds_member[guild_id]
            mutual_guilds_json.append({"id": str(guild_id), "nick": member.nick})

        return mutual_guilds_json

    # noinspection PyUnusedLocal
    async def getGuildMembersGw(self, guild: Guild, query: str, limit: int, user_ids: list[int]) -> list[GuildMember]:
        # noinspection PyUnresolvedReferences
        return await GuildMember.filter(
            Q(guild=guild) &
            (Q(nick__startswith=query) | Q(user__userdatas__username__istartswith=query))  #&
            #((GuildMember.user.id in user_ids) if user_ids else (GuildMember.user.id not in [0]))
        ).select_related("user").limit(limit)

    async def getVanityCodeInvite(self, code: str) -> Optional[Invite]:
        if code is None: return
        return await Invite.get_or_none(vanity_code=code)

    async def setTemplateDirty(self, guild: Guild) -> None:
        if (template := await guild.get_template()) is None:
            return
        template.is_dirty = True
        await template.save(update_fields=["is_dirty"])

    def getLanguageCode(self, ip: str, default: str = "en-US") -> str:
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


ctx._get_core = Core.getInstance
ctx._get_storage = getStorage
