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

from quart import Blueprint
from quart_schema import validate_request

from ..models.hypesquad import HypesquadHouseChange
from ..utils import usingDB, getUser, multipleDecorators
from ...gateway.events import UserUpdateEvent
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore, getGw
from ...yepcord.classes.other import BitFlags
from ...yepcord.enums import UserFlags

# Base path is /api/vX/hypesquad
hypesquad = Blueprint('hypesquad', __name__)


@hypesquad.post("/online")
@multipleDecorators(validate_request(HypesquadHouseChange), usingDB, getUser)
async def api_hypesquad_online(data: HypesquadHouseChange, user: User):
    userdata = await user.data
    flags = BitFlags(userdata.public_flags, UserFlags)
    for f in (UserFlags.HYPESQUAD_ONLINE_HOUSE_1, UserFlags.HYPESQUAD_ONLINE_HOUSE_2, UserFlags.HYPESQUAD_ONLINE_HOUSE_3):
        flags.remove(f)
    flags.add(getattr(UserFlags, f"HYPESQUAD_ONLINE_HOUSE_{data.house_id}"))
    new_userdata = userdata.copy(public_flags=flags.value)
    await getCore().setUserdataDiff(userdata, new_userdata)
    await getGw().dispatch(UserUpdateEvent(user, await user.data, await user.settings), [user.id])
    return "", 204
