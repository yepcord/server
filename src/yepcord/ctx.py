from __future__ import annotations

from contextvars import ContextVar, copy_context
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    def __getitem__(self, item):
        return self.get(item)

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
