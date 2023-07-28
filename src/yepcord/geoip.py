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

with open("other/ip_to_lang.pkl", "rb") as f:
    IP_DB = pload(f)


def _ip2int(addr):
    try:
        return unpack("!I", inet_aton(addr))[0]
    except OSError:
        return -1


def _search(ip, low=0, high=len(IP_DB)-1, mid=0):
    if high >= low:
        mid = (high + low) // 2
        if IP_DB[mid][0] == ip:
            return mid
        elif IP_DB[mid][0] > ip:
            return _search(ip, low, mid - 1, mid)
        else:
            return _search(ip, mid + 1, high, mid)
    return mid-1


def getLanguageCode(ip, default: str="en-US"):
    if (ip := _ip2int(ip)) == -1:
        return default
    idx = _search(ip)
    tidx = len(IP_DB) - 1 if idx + 1 >= len(IP_DB) else idx + 1
    bidx = 0 if idx - 1 < 0 else idx-1
    ips = IP_DB[bidx:tidx]
    for i in ips:
        if ip in range(i[0], i[1]):
            return i[2]
    return default
