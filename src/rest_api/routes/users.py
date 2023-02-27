from quart import Blueprint, request

from ..utils import usingDB, getUser, multipleDecorators
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore
from ...yepcord.responses import userProfileResponse
from ...yepcord.utils import c_json

# Base path is /api/vX/users
users = Blueprint('users', __name__)


@users.get("/<string:target_user>/profile")
@multipleDecorators(usingDB, getUser)
async def get_user_profile(user: User, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = await getCore().getUserProfile(target_user, user)
    with_mutual_guilds = request.args.get("with_mutual_guilds", "false").lower() == "true"
    mutual_friends_count = request.args.get("mutual_friends_count", "false").lower() == "true"
    guild_id = int(request.args.get("guild_id", 0))
    return c_json(await userProfileResponse(target_user, user, with_mutual_guilds, mutual_friends_count, guild_id))
