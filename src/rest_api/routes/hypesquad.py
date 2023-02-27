from quart import Blueprint, request

from ..utils import usingDB, getUser, multipleDecorators
from ...yepcord.classes.user import User, UserFlags
from ...yepcord.ctx import getCore
from ...yepcord.enums import UserFlags as UserFlagsE
from ...yepcord.errors import InvalidDataErr, Errors

# Base path is /api/vX/hypesquad
hypesquad = Blueprint('hypesquad', __name__)


@hypesquad.post("/online")
@multipleDecorators(usingDB, getUser)
async def api_hypesquad_online(user: User):
    data = await request.get_json()
    if not (house_id := data.get("house_id")):
        raise InvalidDataErr(400, Errors.make(50035, {"house_id": {"code": "BASE_TYPE_REQUIRED", "message": "Required field"}}))
    if house_id not in (1, 2, 3):
        raise InvalidDataErr(400, Errors.make(50035, {"house_id": {"code": "BASE_TYPE_CHOICES", "message": "The following values are allowed: (1, 2, 3)."}}))
    data = await user.data
    flags = UserFlags(data.public_flags)
    for f in (UserFlagsE.HYPESQUAD_ONLINE_HOUSE_1, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_2, UserFlagsE.HYPESQUAD_ONLINE_HOUSE_3):
        flags.remove(f)
    flags.add(getattr(UserFlagsE, f"HYPESQUAD_ONLINE_HOUSE_{house_id}"))
    data.public_flags = flags.value
    await getCore().setUserdata(data)
    await getCore().sendUserUpdateEvent(user.id)
    return "", 204
