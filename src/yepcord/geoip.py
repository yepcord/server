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

from socket import inet_aton
from struct import unpack
from pickle import load as pload

from .classes.singleton import Singleton


class IpDatabase(Singleton):
    _db = []

    def __init__(self):
        IpDatabase._db = []

    def _load(self) -> None:
        with open("other/ip_to_lang.pkl", "rb") as f:
            IpDatabase._db = pload(f)

    def _ip_to_int(self, address: str) -> int:
        try:
            return unpack("!I", inet_aton(address))[0]
        except OSError:
            return -1

    def _search(self, ip: int, low=0, high=len(_db)-1, mid=0):
        if not self._db:
            self._load()

        if high >= low:
            mid = (high + low) // 2
            if self._db[mid][0] == ip:
                return mid
            elif self._db[mid][0] > ip:
                return self._search(ip, low, mid - 1, mid)
            else:
                return self._search(ip, mid + 1, high, mid)
        return mid-1

    def getLanguageCode(self, ip: str, default: str="en-US"):
        if (ip := self._ip_to_int(ip)) == -1:
            return default
        idx = self._search(ip)
        tidx = len(self._db) - 1 if idx + 1 >= len(self._db) else idx + 1
        bidx = 0 if idx - 1 < 0 else idx-1
        ips = self._db[bidx:tidx]
        for i in ips:
            if ip in range(i[0], i[1]):
                return i[2]
        return default


getLanguageCode = IpDatabase().getLanguageCode
