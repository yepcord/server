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

from typing import Optional
from urllib.parse import quote

from httpx import AsyncClient

from ..dependencies import DepUser
from ..models.connections import ConnectionCallback
from ..y_blueprint import YBlueprint
from ...gateway.events import UserConnectionsUpdate
from ...yepcord.config import Config
from ...yepcord.ctx import getGw
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, ConnectedAccount

# Base path is /api/vX/connections
connections = YBlueprint("connections", __name__)


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


@connections.get("/github/authorize")
async def connection_github_authorize(user: User = DepUser):
    client_id = get_service_settings("github", "client_id")["client_id"]
    callback_url = quote(f"https://{Config.PUBLIC_HOST}/connections/github/callback")

    conn, _ = await ConnectedAccount.get_or_create(user=user, type="github", verified=False)

    url = (f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={callback_url}"
           f"&scope=read%3Auser&state={user.id}.{conn.state}")

    return {"url": url}


@connections.post("/github/callback", body_cls=ConnectionCallback)
async def connection_github_callback(data: ConnectionCallback):
    settings = get_service_settings("github", "client_id")
    client_id = settings["client_id"]
    client_secret = settings["client_secret"]
    user_id, state = parse_state(data.state)
    if user_id is None:
        return "", 204
    if (conn := await ConnectedAccount.get_or_none(user__id=user_id, state=state, verified=False, type="github")) \
            is None:
        return "", 204

    async with AsyncClient() as cl:
        resp = await cl.post(f"https://github.com/login/oauth/access_token?client_id={client_id}"
                             f"&client_secret={client_secret}&code={data.code}", headers={"Accept": "application/json"})
        if resp.status_code >= 400 or "error" in (j := resp.json()):
            raise InvalidDataErr(400, Errors.make(0))

        access_token = j["access_token"]

        resp = await cl.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code >= 400:
            raise InvalidDataErr(400, Errors.make(0))
        j = resp.json()

    if await ConnectedAccount.filter(type="github", service_id=j["id"]).exists():
        return "", 204

    await conn.update(service_id=j["id"], name=j["login"], access_token=access_token, verified=True)

    await getGw().dispatch(UserConnectionsUpdate(conn), user_ids=[user_id])

    return "", 204
