from quart import Blueprint
from quart_schema import validate_querystring

from ..models.users import UserProfileQuery
from ..utils import usingDB, getUser, multipleDecorators
from ...yepcord.classes.user import User
from ...yepcord.ctx import getCore
from ...yepcord.utils import c_json

# Base path is /api/vX/users
users = Blueprint('users', __name__)


@users.get("/<string:target_user>/profile")
@multipleDecorators(validate_querystring(UserProfileQuery), usingDB, getUser)
async def get_user_profile(query_args: UserProfileQuery, user: User, target_user: str):
    if target_user == "@me":
        target_user = user.id
    target_user = int(target_user)
    target_user = await getCore().getUserProfile(target_user, user)
    return c_json(await target_user.profile(user, query_args.with_mutual_guilds, query_args.mutual_friends_count,
                                            query_args.guild_id))
