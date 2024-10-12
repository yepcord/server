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

from .utils.singleton import Singleton


# noinspection PyMethodMayBeStatic
class Core(Singleton):
    ...
    # async def sendMessage(self, message: Message) -> Message:
    #    async def _addToReadStates():  # TODO: recalculate read states when requested by user
    #        users = await self.getRelatedUsersToChannel(message.channel)
    #        if message.author in users:
    #            users.remove(message.author)
    #        for user in users:
    #            read_state, _ = await ReadState.get_or_create(
    #                user=user, channel=message.channel, defaults={"last_read_id": message.id, "count": 0}
    #            )
    #            read_state.count += 1
    #            await read_state.save(update_fields=["count"])
    #    return message

