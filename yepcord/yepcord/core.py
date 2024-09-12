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
from typing import Optional, Union

import maxminddb

from . import ctx
from .classes.other import EmailMsg, JWT, MFA
from .classes.singleton import Singleton
from .config import Config
from .enums import MfaNonceType
from .errors import InvalidDataErr, Errors, InvalidKey
from .models import User, Channel, ReadState, Guild, GuildMember
from .storage import getStorage
from .utils import b64encode, b64decode


def _assert(value: ..., exc: Union[type[BaseException], BaseException] = ValueError) -> None:
    if not value:
        raise exc


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    def __init__(self):
        self.key = b64decode(Config.KEY)
        self.ipdb = None

    async def getMfaFromTicket(self, ticket: str) -> Optional[MFA]:
        try:
            user_id, session_id, sig = ticket.split(".")
            user_id = jloads(b64decode(user_id).decode("utf8"))[0]
            session_id = int.from_bytes(b64decode(session_id), "big")
            sig = b64decode(sig).decode("utf8")

            _assert(user := await User.y.get(user_id))
            _assert(payload := JWT.decode(sig, self.key))
            _assert(payload["u"] == user.id)
            _assert(payload["s"] == session_id)
        except (ValueError, IndexError):
            return

        return MFA(await user.get_mfa_key(), user_id)

    async def generateUserMfaNonce(self, user: User) -> tuple[str, str]:
        exp = time() + 600
        code = b64encode(urandom(16))
        nonce = JWT.encode({"t": MfaNonceType.NORMAL, "c": code, "u": user.id}, self.key, exp)
        rnonce = JWT.encode({"t": MfaNonceType.REGENERATE, "c": code, "u": user.id}, self.key, exp)
        return nonce, rnonce

    async def verifyUserMfaNonce(self, user: User, nonce: str, nonce_type: MfaNonceType) -> None:
        _assert(payload := JWT.decode(nonce, self.key), InvalidKey)
        _assert(payload["u"] == user.id, InvalidKey)
        _assert(nonce_type == payload["t"], InvalidKey)

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
        token = JWT.encode({"code": payload["c"]}, self.key)
        signature = token.split(".")[2]
        return signature.replace("-", "").replace("_", "")[:8].upper()

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        return await Guild.get_or_none(id=guild_id).select_related("owner")

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
