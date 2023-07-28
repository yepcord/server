from os import environ as __environ

DB_CONNECT_STRING = __environ.get("DB_CONNECT_STRING")
KEY = __environ["KEY"]

STORAGE = {
    "type": __environ.get("STORAGE_TYPE", "local"),

    # Storage-specific settings
    "local": {
        "path": "tests/files"
    },
    "s3": {
        "key_id": "1",
        "access_key": "1",
        "bucket": "yepcord-test",
        "endpoint": "http://127.0.0.1:10001",
    },
    "ftp": {
        "host": "127.0.0.1",
        "port": 9021,
        "user": "root",
        "password": "123456",
    }
}

TENOR_KEY = __environ["TENOR_KEY"]
