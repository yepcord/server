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
from ..models.hypesquad import HypesquadHouseChange
from ..y_blueprint import YBlueprint
from ...gateway.events import UserUpdateEvent
from ...yepcord.classes.other import BitFlags
from ...yepcord.ctx import getGw
from ...yepcord.enums import UserFlags
from ...yepcord.models import User

# Base path is /api/vX/hypesquad
hypesquad = YBlueprint('hypesquad', __name__)


@hypesquad.post("/online", body_cls=HypesquadHouseChange, allow_bots=True)
async def api_hypesquad_online(data: HypesquadHouseChange, user: User = DepUser):
    userdata = await user.data
    flags = BitFlags(userdata.public_flags, UserFlags)
    for f in (UserFlags.HYPESQUAD_ONLINE_HOUSE_1, UserFlags.HYPESQUAD_ONLINE_HOUSE_2, UserFlags.HYPESQUAD_ONLINE_HOUSE_3):
        flags.remove(f)
    flags.add(getattr(UserFlags, f"HYPESQUAD_ONLINE_HOUSE_{data.house_id}"))
    userdata.public_flags = flags.value
    await userdata.save(update_fields=["public_flags"])
    await getGw().dispatch(UserUpdateEvent(user, userdata, await user.settings), [user.id])
    return "", 204
