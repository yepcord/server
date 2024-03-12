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

from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import quote

from httpx import AsyncClient

from yepcord.yepcord.config import Config
from yepcord.yepcord.errors import InvalidDataErr, Errors
from yepcord.yepcord.models import User, ConnectedAccount


def get_service_settings(service_name: str, check_field: Optional[str] = None) -> dict:
    settings = Config.CONNECTIONS[service_name]
    if check_field is not None and settings[check_field] is None:
        raise InvalidDataErr(400, Errors.make(50035, {"provider_id": {
            "code": "BASE_TYPE_INVALID", "message": "This connection has been disabled server-side."
        }}))

    return settings


def parse_state(state: str) -> tuple[Optional[int], Optional[int]]:
    state = state.split(".")
    if len(state) != 2:
        return None, None
    user_id, real_state = state
    if not user_id.isdigit() or not real_state.isdigit():
        return None, None

    return int(user_id), int(real_state)


class BaseConnection(ABC):
    SERVICE_NAME = ""
    AUTHORIZE_URL = ""
    TOKEN_URL = ""
    USER_URL = ""
    SCOPE: list[str] = []

    @classmethod
    async def authorize_url(cls, user: User) -> str:
        client_id = get_service_settings(cls.SERVICE_NAME, "client_id")["client_id"]
        callback_url = quote(f"https://{Config.PUBLIC_HOST}/connections/{cls.SERVICE_NAME}/callback", safe="")

        conn, _ = await ConnectedAccount.get_or_create(user=user, type=cls.SERVICE_NAME, verified=False)

        scope = quote(" ".join(cls.SCOPE))
        return (f"{cls.AUTHORIZE_URL}?client_id={client_id}&redirect_uri={callback_url}&scope={scope}"
                f"&state={user.id}.{conn.state}")

    @classmethod
    @abstractmethod
    def exchange_code_req(cls, code: str, settings: dict[str, str]) -> tuple[str, dict]: ...

    @classmethod
    async def get_connection_from_state(cls, state: str) -> Optional[ConnectedAccount]:
        user_id, state = parse_state(state)
        if user_id is None:
            return
        return await ConnectedAccount.get_or_none(user__id=user_id, state=state, verified=False, type=cls.SERVICE_NAME)

    @classmethod
    async def exchange_code(cls, code: str) -> Optional[str]:
        settings = get_service_settings(cls.SERVICE_NAME, "client_id")

        async with AsyncClient() as cl:
            url, kwargs = cls.exchange_code_req(code, settings)
            resp = await cl.post(url, **kwargs)
            if resp.status_code >= 400 or "error" in (j := resp.json()):
                raise InvalidDataErr(400, Errors.make(0))

            return j["access_token"]

    @classmethod
    def user_info_req(cls, access_token: str) -> tuple[str, dict]:
        return cls.USER_URL, {"headers": {"Authorization": f"Bearer {access_token}"}}

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict:
        url, kwargs = cls.user_info_req(access_token)
        async with AsyncClient() as cl:
            resp = await cl.get(url, **kwargs)
            if resp.status_code >= 400:  # pragma: no cover
                raise InvalidDataErr(400, Errors.make(0))
            return resp.json()


class ConnectionGithub(BaseConnection):
    SERVICE_NAME = "github"
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"
    SCOPE: list[str] = ["read:user"]

    @classmethod
    def exchange_code_req(cls, code: str, settings: dict[str, str]) -> tuple[str, dict]:
        url = f"{cls.TOKEN_URL}?client_id={settings['client_id']}&client_secret={settings['client_secret']}&code={code}"
        kwargs = {"headers": {"Accept": "application/json"}}

        return url, kwargs


class ConnectionReddit(BaseConnection):
    SERVICE_NAME = "reddit"
    AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    USER_URL = "https://oauth.reddit.com/api/v1/me"
    SCOPE: list[str] = ["identity"]

    @classmethod
    async def authorize_url(cls, user: User) -> str:
        return f"{await super(cls, ConnectionReddit).authorize_url(user)}&response_type=code"

    @classmethod
    def exchange_code_req(cls, code: str, settings: dict[str, str]) -> tuple[str, dict]:
        callback_url = quote(f"https://{Config.PUBLIC_HOST}/connections/reddit/callback", safe="")
        kwargs = {
            "auth": (settings["client_id"], settings["client_secret"]),
            "headers": {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            "content": f"grant_type=authorization_code&code={code}&redirect_uri={callback_url}",
        }

        return cls.TOKEN_URL, kwargs


class ConnectionTwitch(BaseConnection):
    SERVICE_NAME = "twitch"
    AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    USER_URL = "https://api.twitch.tv/helix/users"
    SCOPE: list[str] = ["channel_subscriptions", "channel_check_subscription", "channel:read:subscriptions"]

    @classmethod
    async def authorize_url(cls, user: User) -> str:
        return f"{await super(cls, ConnectionTwitch).authorize_url(user)}&response_type=code"

    @classmethod
    def exchange_code_req(cls, code: str, settings: dict[str, str]) -> tuple[str, dict]:
        callback_url = quote(f"https://{Config.PUBLIC_HOST}/connections/twitch/callback", safe="")
        kwargs = {
            "headers": {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            "content": f"grant_type=authorization_code&code={code}&redirect_uri={callback_url}"
                       f"&client_id={settings['client_id']}&client_secret={settings['client_secret']}",
        }

        return cls.TOKEN_URL, kwargs

    @classmethod
    def user_info_req(cls, access_token: str) -> tuple[str, dict]:
        client_id = get_service_settings(cls.SERVICE_NAME, "client_id")["client_id"]
        return cls.USER_URL, {"headers": {"Authorization": f"Bearer {access_token}", "Client-Id": client_id}}

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict:
        return (await super(cls, ConnectionTwitch).get_user_info(access_token))["data"][0]


class ConnectionSpotify(BaseConnection):
    SERVICE_NAME = "spotify"
    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    USER_URL = "https://api.spotify.com/v1/me"
    SCOPE: list[str] = ["user-read-private", "user-read-playback-state", "user-modify-playback-state",
                        "user-read-currently-playing"]

    @classmethod
    async def authorize_url(cls, user: User) -> str:
        return f"{await super(cls, ConnectionSpotify).authorize_url(user)}&response_type=code"

    @classmethod
    def exchange_code_req(cls, code: str, settings: dict[str, str]) -> tuple[str, dict]:
        callback_url = quote(f"https://{Config.PUBLIC_HOST}/connections/spotify/callback", safe="")
        kwargs = {
            "auth": (settings["client_id"], settings["client_secret"]),
            "headers": {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            "content": f"grant_type=authorization_code&code={code}&redirect_uri={callback_url}",
        }

        return cls.TOKEN_URL, kwargs
