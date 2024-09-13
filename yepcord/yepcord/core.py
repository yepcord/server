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
from typing import Optional

import maxminddb

from . import ctx
from .classes.singleton import Singleton
from .config import Config
from .models import User, ReadState, Guild, GuildMember
from .storage import getStorage
from .utils import b64decode


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    COUNTRY_TO_LANG = {
        "UA": "uk", "US": "en-US", "BG": "bg", "CZ": "cs", "DK": "da", "DE": "de", "GR": "el", "GB": "en-GB",
        "ES": "es-ES", "FI": "fi", "FR": "fr", "IN": "hi", "HR": "hr", "HU": "hu", "IT": "it", "JP": "ja",
        "KR": "ko", "LT": "lt", "NL": "nl", "NO": "no", "PL": "pl", "BR": "pt-BR", "RO": "ro", "RU": "RU",
        "SE": "sv-SE", "TH": "th", "TR": "tr", "VN": "vi", "CN": "zh-CN", "TW": "zh-TW",
    }
    IP_DATABASE: Optional[maxminddb.Reader] = None

    def __init__(self):
        self.key = b64decode(Config.KEY)

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

    async def getReadStatesJ(self, user: User) -> list:
        states = []
        st: ReadState
        for st in await ReadState.filter(user=user).select_related("channel", "user"):
            states.append(await st.ds_json())
        return states

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
        cls = self.__class__

        if cls.IP_DATABASE is None and not os.path.exists("other/ip_database.mmdb"):
            return default
        if cls.IP_DATABASE is None:
            cls.IP_DATABASE = maxminddb.open_database("other/ip_database.mmdb")

        try:
            country_code = (cls.IP_DATABASE.get(ip) or {"country": {"iso_code": None}})["country"]["iso_code"] \
                           or default
        except (ValueError, KeyError):
            return default

        return cls.COUNTRY_TO_LANG.get(country_code, default)


ctx._get_core = Core.getInstance
ctx._get_storage = getStorage
