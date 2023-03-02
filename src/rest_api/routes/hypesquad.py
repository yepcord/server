from quart import Blueprint
from quart_schema import validate_request

from ..models.hypesquad import HypesquadHouseChange
from ..utils import usingDB, getUser, multipleDecorators
from ...yepcord.classes.user import User, UserFlags
from ...yepcord.ctx import getCore
from ...yepcord.enums import UserFlags as UserFlagsE

# Base path is /api/vX/hypesquad
hypesquad = Blueprint('hypesquad', __name__)


@hypesquad.post("/online")
@multipleDecorators(validate_request(HypesquadHouseChange), usingDB, getUser)
async def api_hypesquad_online(data: HypesquadHouseChange, user: User):
    userdata = await user.data
    flags = UserFlags(userdata.public_flags)
    for f in (UserFlagsE.HYPESQUAD_ONLINE_HOUSE_1, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_2, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_3):
        flags.remove(f)
    flags.add(getattr(UserFlagsE, f"HYPESQUAD_ONLINE_HOUSE_{data.house_id}"))
    new_userdata = userdata.copy(public_flags=flags.value)
    await getCore().setUserdataDiff(userdata, new_userdata)
    await getCore().sendUserUpdateEvent(user.id)
    return "", 204
