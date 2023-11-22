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

from __future__ import annotations

# noinspection PyPackageRequirements
from contextvars import ContextVar, copy_context
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .core import Core
    from .storage import _Storage
    from .gateway_dispatcher import GatewayDispatcher


class _Ctx:
    _CTX = ContextVar("ctx")
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(_Ctx, cls).__new__(cls)
        return cls._instance

    def get(self, item, default=None):
        self._init()
        return self.__class__._CTX.get().get(item, default)

    def set(self, key, value):
        self._init()
        self.__class__._CTX.get()[key] = value

    def _init(self):
        v = self.__class__._CTX
        if v not in copy_context():
            v.set({})
        return self

    def __setitem__(self, key, value):
        self.set(key, value)


Ctx = _Ctx()


def _getCore(): pass


def getCore() -> Core:
    return Ctx.get("CORE") or _getCore()


def _getCDNStorage(): pass


def getCDNStorage() -> _Storage:
    return Ctx.get("STORAGE") or _getCDNStorage()


def _getGw(): pass


def getGw() -> GatewayDispatcher:
    return Ctx.get("GW") or _getGw()
