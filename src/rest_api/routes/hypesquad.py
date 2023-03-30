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
