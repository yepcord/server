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

from functools import wraps
from typing import Any, Callable, Optional, Awaitable

from fast_depends import inject
from flask.sansio.scaffold import T_route, setupmethod
from quart import Blueprint, g
from quart_schema import validate_request, validate_querystring

from yepcord.yepcord.config import Config

validate_funcs = {"body": validate_request, "qs": validate_querystring}


def apply_validator(src_func: T_route, type_: str, cls: Optional[type], source=None) -> T_route:
    applied = getattr(src_func, "_patches", set())

    if cls is None or f"validate_{type_}" in applied or type_ not in validate_funcs:
        return src_func

    kw = {} if source is None else {"source": source}
    func = validate_funcs[type_](cls, **kw)(src_func)

    applied.add(f"validate_{type_}")
    setattr(func, "_patches", applied)
    if len(applied) > 1:  # pragma: no cover
        delattr(src_func, "_patches")

    return func


def apply_inject(src_func: T_route) -> T_route:
    applied = getattr(src_func, "_patches", set())

    if "fastdepends_inject" in applied:
        return src_func

    if Config.LAZY_INJECT:  # pragma: no cover
        injected_func = None

        @wraps(src_func)
        async def func(*args, **kwargs):
            nonlocal injected_func

            if injected_func is None:
                injected_func = inject(src_func)

            return await injected_func(*args, **kwargs)
    else:
        func = inject(src_func)

    applied.add("fastdepends_inject")
    setattr(func, "_patches", applied)
    if len(applied) > 1:  # pragma: no cover
        delattr(src_func, "_patches")

    return func


def apply_allow_bots(src_func: T_route) -> T_route:
    applied = getattr(src_func, "_patches", set())
    if "allow_bots" in applied:
        return src_func

    @wraps(src_func)
    async def wrapped(*args, **kwargs):
        g.bots_allowed = True
        return await src_func(*args, **kwargs)

    applied.add("allow_bots")
    setattr(wrapped, "_patches", applied)
    if len(applied) > 1:  # pragma: no cover
        delattr(src_func, "_patches")

    return wrapped


def apply_oauth(src_func: T_route, scopes: list[str]) -> T_route:
    applied = getattr(src_func, "_patches", set())
    if "oauth" in applied:
        return src_func

    @wraps(src_func)
    async def wrapped(*args, **kwargs):
        g.oauth_allowed = True
        g.oauth_scopes = set(scopes)
        return await src_func(*args, **kwargs)

    applied.add("oauth")
    setattr(wrapped, "_patches", applied)
    if len(applied) > 1:  # pragma: no cover
        delattr(src_func, "_patches")

    return wrapped


class YBlueprint(Blueprint):
    @setupmethod
    def route(self, rule: str, **options: Any) -> Callable[[T_route], T_route]:
        """Decorate a view function to register it with the given URL
        rule and options. Calls :meth:`add_url_rule`, which has more
        details about the implementation.

        .. code-block:: python

            @app.route("/")
            def index():
                return "Hello, World!"

        See :ref:`url-route-registrations`.

        The endpoint name for the route defaults to the name of the view
        function if the ``endpoint`` parameter isn't passed.

        The ``methods`` parameter defaults to ``["GET"]``. ``HEAD`` and
        ``OPTIONS`` are added automatically.

        :param rule: The URL rule string.
        :param options: Extra options passed to the
            :class:`~werkzeug.routing.Rule` object
        """

        def decorator(f: T_route) -> T_route:
            f = apply_inject(f)
            f = apply_validator(f, "body", options.pop("body_cls", None), options.pop("body_cls_source", None))
            f = apply_validator(f, "qs", options.pop("qs_cls", None))
            if options.pop("allow_bots", False):
                f = apply_allow_bots(f)
            if oauth_scopes := options.pop("oauth_scopes", []):
                f = apply_oauth(f, oauth_scopes)

            endpoint = options.pop("endpoint", None)
            self.add_url_rule(rule, endpoint, f, **options)
            return f

        return decorator
