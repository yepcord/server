from os import environ as __environ

__db = __environ.get("DB_TYPE", "mariadb").lower()
if __db == "sqlite":
    DB_CONNECT_STRING = "sqlite:///test.db"
elif __db == "mariadb":
    DB_CONNECT_STRING = "mysql+pymysql://root:yepcord_test@127.0.0.1/yepcord_test?charset=utf8mb4"
KEY = __environ.get("KEY")

STORAGE = {
    "type": "local",

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

TENOR_KEY = __environ.get("TENOR_KEY")
