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

from pydantic import BaseModel


class UserProfileQuery(BaseModel):
    with_mutual_guilds: bool = False
    mutual_friends_count: bool = False
    guild_id: int = 0

    def __init__(self, **data):
        for arg in ("with_mutual_guilds", "mutual_friends_count"):
            if arg in data:
                data[arg] = data[arg].lower() == "true"
        super().__init__(**data)
