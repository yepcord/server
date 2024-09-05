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

from typing import TYPE_CHECKING, Optional, Callable, cast

if TYPE_CHECKING:  # pragma: no cover
    from .core import Core
    from .storage import _Storage
    from .gateway_dispatcher import GatewayDispatcher


_get_core: Callable[[], Optional[Core]] = lambda: None
_get_storage: Callable[[], Optional[_Storage]] = lambda: None
_get_gw: Callable[[], Optional[GatewayDispatcher]] = lambda: None


def getCore() -> Core:
    return cast(Core, _get_core())


def getCDNStorage() -> _Storage:
    return cast(_Storage, _get_storage())


def getGw() -> GatewayDispatcher:
    return cast(GatewayDispatcher, _get_gw())
