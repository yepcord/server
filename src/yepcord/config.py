from os import environ

class _Config:
    _instance = None

    def_KEY = "8Zw1h9O7nhoT8pb4z/SR4g=="
    def_DB_HOST = "127.0.0.1"
    def_DB_USER = "yepcord"
    def_DB_PASS = ""
    def_DB_NAME = "yepcord"
    def_DOMAIN = "127.0.0.1"
    def_SMTP_HOST = "127.0.0.1"
    def_SMTP_PORT = 25
    def_PS_ADDRESS = "127.0.0.1"

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(_Config, cls).__new__(cls)
            cls.def_CLIENT_HOST = f"{cls.def_DOMAIN}:8080"
            cls.def_API_HOST = f"{cls.def_DOMAIN}:8000"
            cls.def_GATEWAY_HOST = f"{cls.def_DOMAIN}:8001"
            cls.def_REMOTEAUTH_HOST = f"{cls.def_DOMAIN}:8002"
            cls.def_CDN_HOST = f"{cls.def_DOMAIN}:8003"
            cls.def_MEDIAPROXY_HOST = f"{cls.def_DOMAIN}:8004"
            cls.def_NETWORKING_HOST = f"{cls.def_DOMAIN}:8005"
            cls.def_RTCLATENCY_HOST = f"{cls.def_DOMAIN}:8006"
            cls.def_ACTIVITYAPPLICATION_HOST = f"{cls.def_DOMAIN}:8007"
        return cls._instance

    def __call__(self, var, default=None):
        if v := environ.get(var):
            return v
        return getattr(self, f"def_{var}", default)

    def __getitem__(self, item):
        return self(item)

    def get(self, name, default=None):
        return self(name, default)


Config = _Config()