from os import environ

import databases
import sqlalchemy

URL = environ.get("DB_CONNECT_STRING")
assert URL is not None, "Database connect string is not set (set DB_CONNECT_STRING environment variable)."

database = databases.Database(URL)
metadata = sqlalchemy.MetaData()

class DefaultMeta:
    database = database
    metadata = metadata
