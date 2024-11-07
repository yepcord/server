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
from datetime import datetime
from typing import Optional

from pytz import UTC
from tortoise import fields

import yepcord.yepcord.models as models
from ._utils import SnowflakeField, Model


class Poll(Model):
    id: int = SnowflakeField(pk=True)
    message: models.Message = fields.ForeignKeyField("models.Message", unique=True)
    question: str = fields.CharField(max_length=300)
    expires_at: datetime = fields.DatetimeField()
    multiselect: bool = fields.BooleanField(default=False)

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    async def ds_json(self, user_id: Optional[int] = None) -> dict:
        answers = await models.PollAnswer.filter(poll=self).order_by("local_id")
        counts = []
        for answer in answers:
            count = await models.PollVote.filter(answer=answer).count()
            if not count:
                continue
            me = await models.PollVote.exists(answer=answer, user__id=user_id) \
                if user_id is not None  else 0
            counts.append({
                "id": answer.local_id,
                "count": count,
                "me_voted": me,
            })

        return {
            "question": {
                "text": self.question,
            },
            "answers": [
                answer.ds_json()
                for answer in answers
            ],
            "expiry": self.expires_at.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "allow_multiselect": self.multiselect,
            "layout_type": 1,
            "results": {
                "answer_counts": counts,
                "is_finalized": self.is_expired(),
            }
        }
