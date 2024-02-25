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

from __future__ import annotations

from typing import Optional

from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class Integration(Model):
    id: int = SnowflakeField(pk=True)
    application: models.Application = fields.ForeignKeyField("models.Application")
    guild: Optional[models.Guild] = fields.ForeignKeyField("models.Guild")
    enabled: bool = fields.BooleanField(default=True)
    type: str = fields.CharField(default="discord", max_length=64)
    scopes: list[str] = fields.JSONField(default=[])
    user: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)

    async def ds_json(self, with_application=True, with_user=True, with_guild_id=False) -> dict:
        bot = await models.Bot.get(id=self.application.id).select_related("user")
        data = {
            "type": self.type,
            "scopes": self.scopes,
            "name": self.application.name,
            "id": str(self.id),
            "enabled": self.enabled,
            "account": {
                "name": self.application.name,
                "id": str(self.application.id)
            },
        }

        if with_application:
            data["application"] = {
                "type": None,
                "summary": self.application.summary,
                "name": self.application.name,
                "id": str(self.application.id),
                "icon": self.application.icon,
                "description": self.application.description,
                "bot": (await bot.user.userdata).ds_json
            }
        if with_user:
            data["user"] = (await self.user.userdata).ds_json
        if with_guild_id:
            data["guild_id"] = str(self.guild.id)

        return data
