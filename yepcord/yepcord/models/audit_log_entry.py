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

from ..enums import AuditLogEntryType
from ._utils import SnowflakeField, Model
from ..snowflake import Snowflake

import yepcord.yepcord.models as models


class AuditLogEntryUtils:
    @staticmethod
    async def channel_create(user: models.User, channel: models.Channel) -> AuditLogEntry:
        changes = [
            {"new_value": channel.name, "key": "name"},
            {"new_value": channel.type, "key": "type"},
            {"new_value": [], "key": "permission_overwrites"},
            {"new_value": channel.nsfw, "key": "nsfw"},
            {"new_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"new_value": channel.flags, "key": "flags"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                          action_type=AuditLogEntryType.CHANNEL_CREATE, changes=changes)

    @staticmethod
    async def channel_update(user: models.User, channel: models.Channel, changes: dict) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                          action_type=AuditLogEntryType.CHANNEL_UPDATE, changes=changes)

    @staticmethod
    async def channel_delete(user: models.User, channel: models.Channel) -> AuditLogEntry:
        changes = [
            {"old_value": channel.name, "key": "name"},
            {"old_value": channel.type, "key": "type"},
            {"old_value": [], "key": "permission_overwrites"},
            {"old_value": channel.nsfw, "key": "nsfw"},
            {"old_value": channel.rate_limit, "key": "rate_limit_per_user"},
            {"old_value": channel.flags, "key": "flags"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=channel.guild, user=user, target_id=channel.id,
                                          action_type=AuditLogEntryType.CHANNEL_DELETE, changes=changes)

    @staticmethod
    async def overwrite_create(user: models.User, overwrite: models.PermissionOverwrite) -> AuditLogEntry:
        changes = [
            {"new_value": str(overwrite.target_id), "key": "id"},
            {"new_value": str(overwrite.type), "key": "type"},
            {"new_value": str(overwrite.allow), "key": "allow"},
            {"new_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0 and (role := await models.Role.get_or_none(id=overwrite.target_id)) is not None:
            options["role_name"] = role.name
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=overwrite.channel.guild, user=user,
                                          changes=changes, target_id=overwrite.id, options=options,
                                          action_type=AuditLogEntryType.CHANNEL_OVERWRITE_CREATE)

    @staticmethod
    async def overwrite_update(user: models.User, old: models.PermissionOverwrite, new: models.PermissionOverwrite) -> (
            AuditLogEntry):
        changes = []
        if old.allow != new.allow:
            changes.append({"new_value": str(new.allow), "old_value": str(old.allow), "key": "allow"})
        if old.deny != new.deny:
            changes.append({"new_value": str(new.deny), "old_value": str(old.deny), "key": "deny"})
        options = {
            "type": str(new.type),
            "id": str(new.target_id)
        }
        if new.type == 0 and (role := await models.Role.get_or_none(id=new.target_id)) is not None:
            options["role_name"] = role.name
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=old.channel.guild, changes=changes, user=user,
                                          options=options, target_id=old.id,
                                          action_type=AuditLogEntryType.CHANNEL_OVERWRITE_UPDATE)

    @staticmethod
    async def overwrite_delete(user: models.User, overwrite: models.PermissionOverwrite) -> AuditLogEntry:
        changes = [
            {"old_value": str(overwrite.target_id), "key": "id"},
            {"old_value": str(overwrite.type), "key": "type"},
            {"old_value": str(overwrite.allow), "key": "allow"},
            {"old_value": str(overwrite.deny), "key": "deny"}
        ]
        options = {
            "type": str(overwrite.type),
            "id": str(overwrite.target_id)
        }
        if overwrite.type == 0 and (role := await models.Role.get_or_none(id=overwrite.target_id)) is not None:
            options["role_name"] = role.name
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=overwrite.channel.guild, user=user,
                                          changes=changes, target_id=overwrite.id, options=options,
                                          action_type=AuditLogEntryType.CHANNEL_OVERWRITE_DELETE)

    @staticmethod
    async def invite_create(user: models.User, invite: models.Invite) -> AuditLogEntry:
        changes = [
            {"new_value": invite.code, "key": "code"},
            {"new_value": invite.channel.id, "key": "channel_id"},
            {"new_value": invite.inviter.id, "key": "inviter_id"},
            {"new_value": invite.uses, "key": "uses"},
            {"new_value": invite.max_uses, "key": "max_uses"},
            {"new_value": invite.max_age, "key": "max_age"},
            {"new_value": False, "key": "temporary"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=invite.channel.guild, user=user, changes=changes,
                                          target_id=invite.id, action_type=AuditLogEntryType.INVITE_CREATE)

    @staticmethod
    async def invite_delete(user: models.User, invite: models.Invite) -> AuditLogEntry:
        changes = [
            {"old_value": invite.code, "key": "code"},
            {"old_value": invite.channel.id, "key": "channel_id"},
            {"old_value": invite.inviter.id, "key": "inviter_id"},
            {"old_value": invite.uses, "key": "uses"},
            {"old_value": invite.max_uses, "key": "max_uses"},
            {"old_value": invite.max_age, "key": "max_age"},
            {"old_value": False, "key": "temporary"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=invite.channel.guild, user=user,
                                          target_id=invite.id,
                                          action_type=AuditLogEntryType.INVITE_DELETE, changes=changes)

    @staticmethod
    async def guild_update(user: models.User, guild: models.Guild, changes: dict) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=guild.id,
                                          action_type=AuditLogEntryType.GUILD_UPDATE, changes=changes)

    @staticmethod
    async def emoji_create(user: models.User, emoji: models.Emoji) -> AuditLogEntry:
        changes = [{"new_value": emoji.name, "key": "name"}]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=emoji.guild, user=user, target_id=emoji.id,
                                          action_type=AuditLogEntryType.EMOJI_CREATE, changes=changes)

    @staticmethod
    async def emoji_delete(user: models.User, emoji: models.Emoji) -> AuditLogEntry:
        changes = [{"old_value": emoji.name, "key": "name"}]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=emoji.guild, user=user, target_id=emoji.id,
                                          action_type=AuditLogEntryType.EMOJI_DELETE, changes=changes)

    @staticmethod
    async def member_kick(user: models.User, member: models.GuildMember) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                          action_type=AuditLogEntryType.MEMBER_KICK)

    @staticmethod
    async def member_ban(user: models.User, member: models.GuildMember, reason: str = None) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                          action_type=AuditLogEntryType.MEMBER_BAN_ADD, reason=reason)

    @staticmethod
    async def member_ban_user(user: models.User, target_id: int, guild: models.Guild, reason: str = None) -> (
            AuditLogEntry):
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=target_id,
                                          action_type=AuditLogEntryType.MEMBER_BAN_ADD, reason=reason)

    @staticmethod
    async def member_unban(user: models.User, guild: models.Guild, target_user: models.User) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=target_user.id,
                                          action_type=AuditLogEntryType.MEMBER_BAN_REMOVE)

    @staticmethod
    async def member_update(user: models.User, member: models.GuildMember, changes: dict) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=member.guild, user=user, target_id=member.id,
                                          action_type=AuditLogEntryType.MEMBER_UPDATE, changes=changes)

    @staticmethod
    async def role_create(user: models.User, role: models.Role) -> AuditLogEntry:
        changes = [
            {"new_value": role.name, "key": "name"},
            {"new_value": role.permissions, "key": "permissions"},
            {"new_value": role.color, "key": "color"},
            {"new_value": role.hoist, "key": "hoist"},
            {"new_value": role.mentionable, "key": "mentionable"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                          action_type=AuditLogEntryType.ROLE_CREATE, changes=changes)

    @staticmethod
    async def role_update(user: models.User, role: models.Role, changes: dict) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                          action_type=AuditLogEntryType.ROLE_UPDATE, changes=changes)

    @staticmethod
    async def role_delete(user: models.User, role: models.Role) -> AuditLogEntry:
        changes = [
            {"old_value": role.name, "key": "name"},
            {"old_value": role.permissions, "key": "permissions"},
            {"old_value": role.color, "key": "color"},
            {"old_value": role.hoist, "key": "hoist"},
            {"old_value": role.mentionable, "key": "mentionable"}
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=role.guild, user=user, target_id=role.id,
                                          action_type=AuditLogEntryType.ROLE_DELETE, changes=changes)

    @staticmethod
    async def bot_add(user: models.User, guild: models.Guild, bot: models.User) -> AuditLogEntry:
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=bot.id,
                                 action_type=AuditLogEntryType.BOT_ADD)

    @staticmethod
    async def integration_create(user: models.User, guild: models.Guild, bot: models.User) -> AuditLogEntry:
        changes = [
            {"new_value": "discord", "key": "type"},
            {"new_value": "test", "key": (await bot.userdata).username},
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=bot.id,
                                          changes=changes, action_type=AuditLogEntryType.INTEGRATION_CREATE)

    @staticmethod
    async def integration_delete(user: models.User, guild: models.Guild, bot: models.User) -> AuditLogEntry:
        changes = [
            {"old_value": "discord", "key": "type"},
            {"old_value": "test", "key": (await bot.userdata).username},
        ]
        return await AuditLogEntry.create(id=Snowflake.makeId(), guild=guild, user=user, target_id=bot.id,
                                          changes=changes, action_type=AuditLogEntryType.INTEGRATION_DELETE)


class AuditLogEntry(Model):
    utils = AuditLogEntryUtils

    id: int = SnowflakeField(pk=True)
    guild: models.Guild = fields.ForeignKeyField("models.Guild")
    user: Optional[models.User] = fields.ForeignKeyField("models.User", on_delete=fields.SET_NULL, null=True)
    target_id: int = fields.BigIntField(null=True, default=None)
    action_type: int = fields.IntField()
    reason: Optional[str] = fields.CharField(max_length=512, null=True, default=None)
    changes: list = fields.JSONField(default=[])
    options: dict = fields.JSONField(default={})

    def ds_json(self) -> dict:
        data = {
            "user_id": str(self.user.id),
            "target_id": str(self.target_id),
            "id": str(self.id),
            "action_type": self.action_type,
            "guild_id": str(self.guild.id)
        }
        if self.changes: data["changes"] = self.changes
        if self.options: data["options"] = self.options
        if self.reason: data["reason"] = self.reason
        return data
