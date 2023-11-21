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

from typing import Optional

from tortoise import fields

from ..config import Config
import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class Attachment(Model):
    id: int = SnowflakeField(pk=True)
    channel: models.Channel = fields.ForeignKeyField("models.Channel", on_delete=fields.SET_NULL, null=True)
    message: models.Message = fields.ForeignKeyField("models.Message", null=True, default=None)
    filename: str = fields.CharField(max_length=128)
    size: str = fields.IntField()
    content_type: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    metadata: dict = fields.JSONField(default={})

    def ds_json(self) -> dict:
        data = {
            "filename": self.filename,
            "id": str(self.id),
            "size": self.size,
            "url": f"https://{Config.CDN_HOST}/attachments/{self.channel.id}/{self.id}/{self.filename}"
        }
        if self.content_type:
            data["content_type"] = self.content_type
        if self.metadata:
            data.update(self.metadata)
        return data
