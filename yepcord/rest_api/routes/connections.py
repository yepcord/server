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

from ..dependencies import DepUser
from ..models.connections import ConnectionCallback
from ..y_blueprint import YBlueprint
from ...gateway.events import UserConnectionsUpdate
from ...yepcord.classes.connections import ConnectionGithub, ConnectionReddit, ConnectionTwitch, BaseConnection, \
    ConnectionSpotify
from ...yepcord.ctx import getGw
from ...yepcord.models import User, ConnectedAccount

# Base path is /api/vX/connections
connections = YBlueprint("connections", __name__)


async def unified_callback(connection_cls: type[BaseConnection], data: ConnectionCallback,
                           user_login_field: str = "login"):
    if (conn := await connection_cls.get_connection_from_state(data.state)) is None:
        return "", 204

    if (access_token := await connection_cls.exchange_code(data.code)) is None:
        return "", 204

    user_info = await connection_cls.get_user_info(access_token)
    if await ConnectedAccount.filter(type=connection_cls.SERVICE_NAME, service_id=user_info["id"]).exists():
        return "", 204

    await conn.update(service_id=user_info["id"], name=user_info[user_login_field], access_token=access_token,
                      verified=True)
    await getGw().dispatch(UserConnectionsUpdate(conn), user_ids=[int(data.state.split(".")[0])])
    return "", 204


@connections.get("/github/authorize")
async def connection_github_authorize(user: User = DepUser):
    return {"url": await ConnectionGithub.authorize_url(user)}


@connections.post("/github/callback", body_cls=ConnectionCallback)
async def connection_github_callback(data: ConnectionCallback):
    return await unified_callback(ConnectionGithub, data)


@connections.get("/reddit/authorize")
async def connection_reddit_authorize(user: User = DepUser):
    return {"url": await ConnectionReddit.authorize_url(user)}


@connections.post("/reddit/callback", body_cls=ConnectionCallback)
async def connection_reddit_callback(data: ConnectionCallback):
    return await unified_callback(ConnectionReddit, data, "name")


@connections.get("/twitch/authorize")
async def connection_twitch_authorize(user: User = DepUser):
    return {"url": await ConnectionTwitch.authorize_url(user)}


@connections.post("/twitch/callback", body_cls=ConnectionCallback)
async def connection_twitch_callback(data: ConnectionCallback):
    return await unified_callback(ConnectionTwitch, data)


@connections.get("/spotify/authorize")
async def connection_spotify_authorize(user: User = DepUser):
    return {"url": await ConnectionSpotify.authorize_url(user)}


@connections.post("/spotify/callback", body_cls=ConnectionCallback)
async def connection_spotify_callback(data: ConnectionCallback):
    return await unified_callback(ConnectionSpotify, data, "display_name")
