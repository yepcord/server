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

from tortoise.expressions import Q
from tortoise import fields

from ..enums import RelationshipType, RelTypeDiscord
from ..errors import InvalidDataErr, Errors
from ._utils import ChoicesValidator, SnowflakeField, Model
import yepcord.yepcord.models as models


class RelationshipUtils:
    @staticmethod
    async def exists(user1: models.User, user2: models.User) -> bool:
        return await Relationship.filter(Q(from_user=user1, to_user=user2) | Q(from_user=user2, to_user=user1)).exists()

    @staticmethod
    async def get(user1: models.User, user2: models.User) -> Relationship:
        return await Relationship.get(Q(from_user=user1, to_user=user2) | Q(from_user=user2, to_user=user1))

    @staticmethod
    async def available(from_user: models.User, to_user: models.User, *, raise_: bool=False) -> bool:
        available = not await RelationshipUtils.exists(from_user, to_user)  # TODO: check for to_user settings
        if not available and raise_:
            raise InvalidDataErr(400, Errors.make(80007))
        return available

    @staticmethod
    async def request(from_user: models.User, to_user: models.User) -> Relationship:
        if not await RelationshipUtils.available(from_user, to_user):
            raise InvalidDataErr(400, Errors.make(80007))
        return await Relationship.create(from_user=from_user, to_user=to_user, type=RelationshipType.PENDING)

    @staticmethod
    async def accept(from_user: models.User, to_user: models.User) -> Optional[Relationship]:
        if ((rel := await Relationship.get_or_none(from_user=from_user, to_user=to_user, type=RelationshipType.PENDING))
                is None):
            return
        rel.type = RelationshipType.FRIEND
        await rel.save(update_fields=["type"])
        return rel

    @staticmethod
    async def block(user: models.User, block_user: models.User) -> dict:
        rels = await Relationship.filter(
            Q(from_user=user, to_user=block_user) | Q(from_user=block_user, to_user=user)
        ).select_related("from_user", "to_user").all()
        block = True
        ret = {"block": False, "delete": []}
        if not rels:
            pass
        elif len(rels) == 1 and rels[0].type != RelationshipType.BLOCK:
            rel = rels[0]
            ret["delete"] = [
                {"id": rel.from_user.id, "rel": rel.to_user.id, "type": rel.discord_rel_type(rel.from_user)},
                {"id": rel.to_user.id, "rel": rel.from_user.id, "type": rel.discord_rel_type(rel.to_user)}
            ]
            await rels[0].delete()
        elif len(rels) == 1 and rels[0].type == RelationshipType.BLOCK:
            if rels[0].from_user == user and rels[0].to_user == block_user:
                block = False
        elif len(rels) == 2:
            block = False
        if block:
            await Relationship.create(from_user=user, to_user=block_user, type=RelationshipType.BLOCK)
            ret["block"] = True
        return ret

    @staticmethod
    async def delete(current: models.User, target: models.User) -> dict:
        rels = await Relationship.filter(
            Q(from_user=current, to_user=target) | Q(from_user=target, to_user=current)
        ).select_related("from_user", "to_user").all()
        ret = {"delete": []}
        if not rels:
            pass
        elif len(rels) == 1 and rels[0].type != RelationshipType.BLOCK:
            rel = rels[0]
            ret["delete"] = [
                {"id": rel.from_user.id, "rel": rel.to_user.id, "type": rel.discord_rel_type(rel.from_user)},
                {"id": rel.to_user.id, "rel": rel.from_user.id, "type": rel.discord_rel_type(rel.to_user)}
            ]
            await rel.delete()
        elif len(rels) == 1 and rels[0].type == RelationshipType.BLOCK:
            rel = rels[0]
            if rel.from_user == current and rel.to_user == target:
                ret["delete"] = [
                    {"id": rel.from_user.id, "rel": rel.to_user.id, "type": rel.discord_rel_type(rel.from_user)}
                ]
                await rel.delete()
        elif len(rels) == 2:
            rel = [r for r in rels if r.from_user == current and r.to_user == target][0]
            ret["delete"] = [
                {"id": rel.from_user.id, "rel": rel.to_user.id, "type": rel.discord_rel_type(rel.from_user)}
            ]
            await rel.delete()
        return ret

    @staticmethod
    async def is_blocked(user: models.User, check_blocked: models.User) -> bool:
        return await Relationship.filter(from_user=user, to_user=check_blocked, type=RelationshipType.BLOCK).exists()


class Relationship(Model):
    utils = RelationshipUtils

    id: int = SnowflakeField(pk=True)
    from_user: models.User = fields.ForeignKeyField("models.User", related_name="from_user")
    to_user: models.User = fields.ForeignKeyField("models.User", related_name="to_user")
    type: int = fields.IntField(validators=[ChoicesValidator({0, 1, 2})])

    def other_user(self, current_user: models.User) -> models.User:
        return self.from_user if self.to_user == current_user else self.to_user

    def discord_rel_type(self, current_user: models.User) -> Optional[int]:
        if self.type == RelationshipType.BLOCK and self.from_user.id != current_user.id:
            return None
        elif self.type == RelationshipType.BLOCK:
            return RelTypeDiscord.BLOCK
        elif self.type == RelationshipType.FRIEND:
            return RelTypeDiscord.FRIEND
        elif self.from_user == current_user:
            return RelTypeDiscord.REQUEST_SENT
        elif self.to_user == current_user:
            return RelTypeDiscord.REQUEST_RECV

    async def ds_json(self, current_user: models.User, with_data=False) -> Optional[dict]:
        other_user = self.other_user(current_user)
        if (rel_type := self.discord_rel_type(current_user)) is None:
            return
        data = {"user_id": str(other_user.id), "type": rel_type, "nickname": None, "id": str(other_user.id)}
        if with_data:
            userdata = await other_user.data
            data["user"] = userdata.ds_json

        return data
