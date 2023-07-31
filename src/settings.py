# Database and mail connection strings
DB_CONNECT_STRING = "sqlite:///db.sqlite"
MAIL_CONNECT_STRING = "smtp://127.0.0.1:10025?timeout=3"

# JWT key
# SECURITY WARNING: change this key and keep it in secret!
KEY = "XUJHVU0nUn51TifQuy9H1j0gId0JqhQ+PUz16a2WOXE="

# Domain which will be used in email verification links, etc.
PUBLIC_HOST = "127.0.0.1:8080"

GATEWAY_HOST = "127.0.0.1:8001"
CDN_HOST = "127.0.0.1:8003"

STORAGE = {
    "type": "local",  # Can be local, s3 or ftp

    # Storage-specific settings
    "local": {
        "path": "files"
    },
    "s3": {
        "key_id": "",
        "access_key": "",
        "bucket": "",
        "endpoint": "",
    },
    "ftp": {
        "host": "",
        "port": 21,
        "user": "",
        "password": "",
    }
}

# Acquire tenor api key from https://developers.google.com/tenor/guides/quickstart and set this  variable to enable gifs
TENOR_KEY = None

# Message broker used for communication between the API server and Gateway server. By default, 'ws' type is used
# (websocket server started on 127.0.0.1 on port 5055) to allow running YEPcord without installing 'external'
# message broker software. DO NOT use 'ws' type in production!
MESSAGE_BROKER = {
    "type": "ws",

    # Mq-specific settings
    "redis": {
        "url": "",
    },
    "rabbitmq": {
        "url": "",
    },
    "sqs": {
        "url": "",
    },
    "kafka": {
        "bootstrap_servers": [],
    },
    "nats": {
        "servers": [],
    },

    "ws": {
        "url": "ws://127.0.0.1:5055",
    },
}
