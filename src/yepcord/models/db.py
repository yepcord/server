import databases
import sqlalchemy

from ..config import Config

URL = Config.DB_CONNECT_STRING
_module = Config.SETTINGS_MODULE.replace(".", "/")+".py"
assert URL is not None, f"Database connect string is not set (set DB_CONNECT_STRING variable in {_module})."

database = databases.Database(URL)
metadata = sqlalchemy.MetaData()


class DefaultMeta:
    database = database
    metadata = metadata


collation = None if "sqlite" in URL.split("://")[0].lower() else "utf8mb4_general_ci"
