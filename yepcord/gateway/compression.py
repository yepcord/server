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

from __future__ import annotations

from abc import ABC, abstractmethod
from zlib import compressobj, Z_FULL_FLUSH


class WsCompressor(ABC):
    CLSs = {}

    @abstractmethod
    def __call__(self, data: bytes) -> bytes: ...

    @classmethod
    def create_compressor(cls, name: str) -> WsCompressor | None:
        if name in cls.CLSs:
            return cls.CLSs[name]()


class ZlibCompressor(WsCompressor):
    __slots__ = ("_obj",)

    def __init__(self):
        self._obj = compressobj()

    def __call__(self, data: bytes) -> bytes:
        return self._obj.compress(data) + self._obj.flush(Z_FULL_FLUSH)


WsCompressor.CLSs["zlib-stream"] = ZlibCompressor
# TODO: add zstd-stream
