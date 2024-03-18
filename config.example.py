# Database and mail connection strings
DB_CONNECT_STRING = "sqlite:///db.sqlite"
MAIL_CONNECT_STRING = "smtp://127.0.0.1:10025?timeout=3"

# Directory used to save migration files
MIGRATIONS_DIR = "./migrations"

# JWT key
# SECURITY WARNING: change this key and keep it in secret!
KEY = "XUJHVU0nUn51TifQuy9H1j0gId0JqhQ+PUz16a2WOXE="

# Domain which will be used in email verification links, etc.
PUBLIC_HOST = "127.0.0.1:8080"

GATEWAY_HOST = "127.0.0.1:8000/gateway"
CDN_HOST = "127.0.0.1:8000/media"

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

# Acquire tenor api key from https://developers.google.com/tenor/guides/quickstart and set this variable to enable gifs
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

# Redis used for users presences and statuses. If empty, presences will be stored in memory.
REDIS_URL = ""

# How often gateway clients must send keep-alive packets (also, presences expiration time is this variable times 1.25).
# Default value is 45 seconds, do not set it too big or too small.
GATEWAY_KEEP_ALIVE_DELAY = 45

BCRYPT_ROUNDS = 15

# Captcha settings, acquire your hcaptcha/recaptcha sitekey and secret and paste it here. You can disable captcha
# completely, enable one of the services or both
CAPTCHA = {
    "enabled": None,  # "hcaptcha", "recaptcha" or None
    "hcaptcha": {
        "sitekey": "",
        "secret": "",
    },
    "recaptcha": {
        "sitekey": "",
        "secret": "",
    },
}

# Settings for external application connections
# For every application, use https://PUBLIC_HOST/connections/SERVICE_NAME/callback as redirect (callback) url,
# for example, if you need to create GitHub app and your yepcord instance (frontend) is running on 127.0.0.1:8888,
# redirect url will be https://127.0.0.1:8888/connections/github/callback
CONNECTIONS = {
    "github": {
        # Create at https://github.com/settings/applications/new
        "client_id": None,
        "client_secret": None,
    },
    "reddit": {
        # Create at https://www.reddit.com/prefs/apps
        "client_id": None,
        "client_secret": None,
    },
    "twitch": {
        # Create at https://dev.twitch.tv/console/apps/create
        "client_id": None,
        "client_secret": None,
    },
    "spotify": {
        # Create at https://developer.spotify.com/dashboard/create
        "client_id": None,
        "client_secret": None,
    },
}

# Voice workers addresses
VOICE_WORKERS = []
