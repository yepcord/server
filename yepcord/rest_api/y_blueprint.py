from functools import wraps
from typing import Any, Callable, Optional

from fast_depends import inject
from flask.sansio.scaffold import T_route, setupmethod
from quart import Blueprint, g
from quart_schema import validate_request, DataSource, validate_querystring

validate_funcs = {"body": validate_request, "qs": validate_querystring}


def apply_validator(func: T_route, type_: str, cls: Optional[type], source=None) -> T_route:
    applied = getattr(func, "_patches", set())

    if cls is None or f"validate_{type_}" in applied or type_ not in validate_funcs:
        return func

    kw = {} if source is None else {"source": source}
    func = validate_funcs[type_](cls, **kw)(func)

    applied.add(f"validate_{type_}")
    setattr(func, "_patches", applied)

    return func


def apply_inject(func: T_route) -> T_route:
    applied = getattr(func, "_patches", set())

    if "fastdepends_inject" in applied:
        return func

    func = inject(func)
    applied.add("fastdepends_inject")
    setattr(func, "_patches", applied)

    return func


def apply_allow_bots(func: T_route) -> T_route:
    applied = getattr(func, "_patches", set())
    if "allow_bots" in applied:
        return func

    @wraps(func)
    async def wrapped(*args, **kwargs):
        g.bots_allowed = True
        return await func(*args, **kwargs)

    applied.add("allow_bots")
    setattr(func, "_patches", applied)
    return wrapped


def apply_oauth(func: T_route, scopes: list[str]) -> T_route:
    applied = getattr(func, "_patches", set())
    if "oauth" in applied:
        return func

    @wraps(func)
    async def wrapped(*args, **kwargs):
        g.oauth_allowed = True
        g.oauth_scopes = set(scopes)
        return await func(*args, **kwargs)

    applied.add("oauth")
    setattr(func, "_patches", applied)
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
