from typing import Any, TypeVar, TYPE_CHECKING

import databases
import sqlalchemy
from ormar import QuerySet

from ..snowflake import Snowflake

if TYPE_CHECKING:  # pragma no cover
    from ormar.models import T
else:  # pragma no cover
    T = TypeVar("T", bound="Model")

from ..config import Config

URL = Config.DB_CONNECT_STRING
_module = Config.SETTINGS_MODULE.replace(".", "/") + ".py"
assert URL is not None, f"Database connect string is not set (set DB_CONNECT_STRING variable in {_module})."

database = databases.Database(URL)
metadata = sqlalchemy.MetaData()


class DefaultMeta:
    database = database
    metadata = metadata


is_sqlite = "sqlite" in URL.split("://")[0].lower()
collation = None if is_sqlite else "utf8mb4_general_ci"


class SnowflakeAIQuerySet(QuerySet):
    """
    Snowflake-based autoincrement
    """

    async def create(self, **kwargs: Any) -> T:
        pkname = self.model_meta.pkname
        if self.model_meta.model_fields[pkname].autoincrement and pkname not in kwargs:
            kwargs[pkname] = Snowflake.makeId()

        return await super().create(**kwargs)

    async def bulk_create(self, objects: list[T]) -> None:
        pkname = self.model_meta.pkname
        if not self.model_meta.model_fields[pkname].autoincrement:
            return await super().bulk_create(objects)

        for obj in objects:
            if getattr(obj, pkname, None) is None:
                setattr(obj, pkname, Snowflake.makeId())

        return await super().bulk_create(objects)
