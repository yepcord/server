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


class BitFlags:
    __slots__ = ("cls", "value", "parsed",)

    def __init__(self, value: int, cls):
        self.cls = cls
        self.value = value
        self.parsed = self.parse_flags()

    def parse_flags(self) -> list:
        flags = []
        value = self.value
        self.value = 0
        for val in self.cls.values().values():
            if (value & val) == val:
                flags.append(val)
                self.value |= val
        return flags

    def add(self, val: int):
        if val not in self.parsed:
            self.value |= val
            self.parsed.append(val)
        return self

    def remove(self, val: int):
        if val in self.parsed:
            self.value &= ~val
            self.parsed.remove(val)
        return self
