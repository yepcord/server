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
from ..models.users import UserProfileQuery
from ..y_blueprint import YBlueprint
from ...yepcord.ctx import getCore
from ...yepcord.models import User

# Base path is /api/vX/users
users = YBlueprint("users", __name__)


@users.get("/<string:target_user>/profile", qs_cls=UserProfileQuery)
async def get_user_profile(query_args: UserProfileQuery, target_user: str, user: User = DepUser):
    if target_user == "@me":
        target_user = user.id
    target_user = await user.get_another_user(int(target_user))
    return await target_user.profile_json(
        user, query_args.with_mutual_guilds, query_args.mutual_friends_count,  query_args.guild_id
    )
