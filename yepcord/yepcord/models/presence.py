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
from time import time
from typing import Optional

from tortoise import fields
from tortoise.fields import BigIntField

import yepcord.yepcord.models as models
from ._utils import Model, ChoicesValidator


class Presence(Model):
    id: int = BigIntField(pk=True, generated=False)
    user: models.User = fields.OneToOneField("models.User")
    updated_at: int = fields.IntField(default=lambda: int(time()))
    status: str = fields.CharField(max_length=12, default="online", validators=[
        ChoicesValidator({"online", "idle", "offline", "dnd", "invisible"})
    ])
    activities: list = fields.JSONField(default=list)

    def ds_json(self, full: bool = True) -> dict:
        data = {
            "status": self.public_status,
            "client_status": {} if self.is_offline else {"desktop": self.public_status},
            "activities": self.activities,
        }
        if full:
            data["user_id"] = str(self.id)
            data["last_modified"] = 0 if self.is_offline else int(self.updated_at * 1000)

        return data

    @property
    def is_offline(self) -> bool:
        return self.status in {"offline", "invisible"}

    @property
    def public_status(self) -> str:
        return self.status if self.status != "invisible" else "offline"

    def fill_from_settings(self, settings: models.UserSettings) -> None:
        self.status = settings.status
        self.activities = []
        if (activity := Presence.activity_from_custom_status(settings.custom_status)) is not None:
            self.activities.append(activity)

    @staticmethod
    def activity_from_custom_status(custom_status: dict) -> Optional[dict]:
        if custom_status is None:
            return
        activity = {
            "name": "Custom Status",
            "type": 4,
            "state": custom_status.get("text"),
            "emoji": None,
        }
        if "expires_at_ms" in custom_status:
            activity["timestamps"] = {
                "end": custom_status.get("expires_at_ms"),
            }
        if "emoji_id" in custom_status or "emoji_name" in custom_status:
            activity["emoji"] = {
                "emoji_id": custom_status.get("emoji_id"),
                "emoji_name": custom_status.get("emoji_name"),
            }

        return activity

    @staticmethod
    def ds_json_offline(user_id: int = 0, full: bool = True) -> dict:
        data = {
            "status": "offline",
            "client_status": {},
            "activities": [],
        }
        if full:
            data["user_id"] = str(user_id)
            data["last_modified"] = 0

        return data
