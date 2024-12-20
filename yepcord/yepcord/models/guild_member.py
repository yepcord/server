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

from __future__ import annotations

from datetime import datetime
from typing import Optional

from tortoise import fields

from ..enums import GuildPermissions
from ..errors import MissingPermissions
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake
import yepcord.yepcord.models as models


class PermissionsChecker:
    def __init__(self, member: GuildMember):
        self.member = member

    async def check(self, *check_permissions, channel: Optional[models.Channel]=None) -> None:
        def _check(perms: int, perm: int) -> bool:
            return (perms & perm) == perm
        guild = self.member.guild
        if guild.owner == self.member.user:
            return
        permissions = await self.member.permissions
        if _check(permissions, GuildPermissions.ADMINISTRATOR):
            return
        if channel:
            for overwrite in await channel.get_permission_overwrites(self.member):
                permissions &= ~overwrite.deny
                permissions |= overwrite.allow

        for permission in check_permissions:
            if not _check(permissions, permission):
                raise MissingPermissions

    async def canKickOrBan(self, target_member: GuildMember) -> bool:
        if self.member == target_member:
            return False
        guild = self.member.guild
        if target_member.user == guild.owner:
            return False
        if self.member.user == guild.owner:
            return True
        self_top_role = await self.member.top_role
        target_top_role = await target_member.top_role
        if self_top_role.position <= target_top_role.position:
            return False
        return True

    async def canChangeRolesPositions(self, roles_changes: dict, current_roles: Optional[list[models.Role]]=None) -> (
            bool):
        guild = self.member.guild
        if self.member.user == guild.owner:
            return True
        roles_ids = {role.id: role for role in current_roles}
        top_role = await self.member.top_role
        for role_change in roles_changes:
            role_id = int(role_change["id"])
            position = role_change["position"]
            if roles_ids[role_id].position >= top_role.position or position >= top_role.position:
                return False
        return True


class GuildMember(Model):
    id: int = SnowflakeField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    avatar: Optional[str] = fields.CharField(max_length=256, null=True, default=None)
    communication_disabled_until: Optional[int] = fields.BigIntField(null=True, default=None)
    flags: int = fields.BigIntField(default=0)
    nick: Optional[str] = fields.CharField(max_length=128, null=True, default=None)
    mute: bool = fields.BooleanField(default=False)
    deaf: bool = fields.BooleanField(default=False)
    roles = fields.ManyToManyField("models.Role")

    guildevents: fields.ReverseRelation[models.GuildEvent]

    class Meta:
        unique_together = (
            ("user", "guild"),
        )

    @property
    def joined_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    async def ds_json(self, with_user=True) -> dict:
        data = {
            "avatar": self.avatar,
            "communication_disabled_until": self.communication_disabled_until,
            "flags": self.flags,
            "joined_at": self.joined_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "nick": self.nick,
            "is_pending": False,
            "pending": False,
            "premium_since": self.user.created_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "roles": [str(role_id) for role_id in await self.roles.all().values_list("id", flat=True)],
            "mute": self.mute,
            "deaf": self.deaf
        }

        if with_user:
            data["user"] = (await self.user.userdata).ds_json

        return data

    @property
    def perm_checker(self) -> PermissionsChecker:
        return PermissionsChecker(self)

    async def get_roles(self, with_default: bool = True) -> list[models.Role]:
        roles = await self.roles.all()
        if with_default:
            roles.append(await models.Role.get(id=self.guild.id))

        return sorted(roles, key=lambda r: r.position)

    @property
    async def top_role(self) -> models.Role:
        roles = await self.get_roles()
        return roles[-1]

    async def checkPermission(self, *check_permissions, channel: Optional[models.Channel] = None) -> None:
        return await self.perm_checker.check(*check_permissions, channel=channel)

    @property
    async def permissions(self) -> int:
        if self.user == self.guild.owner:
            return 562949953421311
        permissions = 0
        for role in await self.get_roles():
            permissions |= role.permissions
        return permissions

    async def set_roles_from_list(self, roles: list[models.Role]) -> tuple[list[int], list[int]]:
        current_roles = await self.roles.all()
        added = []
        removed = []
        for role in roles:
            if role not in current_roles and not role.managed:
                added.append(role.id)
                await self.roles.add(role)
        for role in current_roles:
            if role not in roles and not role.managed:
                removed.append(role.id)
                await self.roles.remove(role)

        return added, removed
