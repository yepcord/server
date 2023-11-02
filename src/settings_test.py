from os import environ as __environ

__db = __environ.get("DB_TYPE", "mariadb").lower()
if __db == "sqlite":
    DB_CONNECT_STRING = "sqlite://test.db"
elif __db == "mariadb":
    DB_CONNECT_STRING = "mysql://root:yepcord_test@127.0.0.1/yepcord_test?charset=utf8mb4"
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

BCRYPT_ROUNDS = 4

CAPTCHA = {  # This is test captcha keys
    "enabled": None,
    "hcaptcha": {
        "sitekey": "10000000-ffff-ffff-ffff-000000000001",
        "secret": "0x0000000000000000000000000000000000000000",
    },
    "recaptcha": {
        "sitekey": "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI",
        "secret": "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe",
    },
}
