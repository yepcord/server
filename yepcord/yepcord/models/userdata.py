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

from datetime import date, timedelta
from typing import Optional

from quart import g
from tortoise import fields
from tortoise.validators import MinValueValidator, MaxValueValidator

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class UserData(Model):
    class Meta:
        unique_together = (("username", "discriminator"),)

    id: int = SnowflakeField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    birth: date = fields.DateField()
    username: str = fields.CharField(max_length=128)
    discriminator: int = fields.IntField(validators=[MinValueValidator(0), MaxValueValidator(9999)])
    premium: bool = fields.BooleanField(default=True)
    flags: int = fields.BigIntField(default=0)
    public_flags: int = fields.BigIntField(default=0)
    phone: Optional[str] = fields.CharField(max_length=32, null=True, default=None)
    bio: str = fields.CharField(max_length=256, default="")
    accent_color: Optional[int] = fields.BigIntField(null=True, default=None)
    avatar: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    avatar_decoration: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    banner: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    banner_color: Optional[int] = fields.BigIntField(null=True, default=None)

    @property
    def s_discriminator(self) -> str:
        return str(self.discriminator).rjust(4, "0")

    @property
    def nsfw_allowed(self) -> bool:
        dn = date.today()
        return dn - self.birth > timedelta(days=18 * 365 + 4)

    @property
    def ds_json(self) -> dict:
        data = {
            "id": str(self.id),
            "username": self.username,
            "avatar": self.avatar,
            "avatar_decoration": self.avatar_decoration,
            "discriminator": self.s_discriminator,
            "public_flags": self.public_flags
        }
        if self.user.is_bot:
            data["bot"] = True

        return data

    async def ds_json_full(self) -> dict:
        settings = await self.user.settings
        data = {
            "id": str(self.id),
            "username": self.username,
            "avatar": self.avatar,
            "avatar_decoration": self.avatar_decoration,
            "discriminator": self.s_discriminator,
            "public_flags": self.public_flags,
            "flags": self.flags,
            "banner": self.banner if not self.user.is_bot else None,
            "banner_color": self.banner_color if not self.user.is_bot else None,
            "accent_color": self.accent_color if not self.user.is_bot else None,
            "bio": self.bio,
            "locale": settings.locale,
            "nsfw_allowed": self.nsfw_allowed,
            "mfa_enabled": settings.mfa,
            "email": self.user.email if not self.user.is_bot else None,
            "verified": self.user.verified,
            "phone": self.phone
        }
        if self.user.is_bot:
            data["bot"] = True
        if isinstance(auth := g.get("auth"), models.Authorization) and "email" not in auth.scope_set:
            del data["email"]

        return data
