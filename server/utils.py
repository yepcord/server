from base64 import b64encode as _b64encode, b64decode as _b64decode
from time import time
from random import randint
from os import getpid
from json import dumps as jdumps
from zlib import compressobj, Z_FULL_FLUSH

global _INCREMENT_ID

def b64decode(data):
    if isinstance(data, str):
        data = data.encode("utf8")
    data += b'=' * (-len(data) % 4)
    for search, replace in ((b'-', b'+'), (b'_', b'/'), (b',', b'')):
        data = data.replace(search, replace)
    return _b64decode(data)

def b64encode(data):
    data = _b64encode(data).decode("utf8")
    for search, replace in (('+', '-'), ('/', '_'), ('=', '')):
        data = data.replace(search, replace)
    return data

_EPOCH = 1640995200_000
_INCREMENT_ID = 0
_MAX_TIMESTAMP = 1 << 42
_WORKER_ID = randint(0, 32)
_PROCESS_ID = getpid()

def _mksnowflake(ms, wr, pi, ic):
    sf = (ms % _MAX_TIMESTAMP) << 22
    sf += (wr % 32) << 17
    sf += (pi % 32) << 12
    sf += ic % 4096
    return sf

def mksnowflake():
    global _INCREMENT_ID
    sf = _mksnowflake(int(time()*1000) - _EPOCH, _WORKER_ID, _PROCESS_ID, _INCREMENT_ID)
    _INCREMENT_ID += 1
    return sf

mksf = mksnowflake

def snowflake_timestamp(sf):
    return (sf >> 22) + _EPOCH

def c_json(json, code=200, headers={}):
    if not isinstance(json, str):
        json = jdumps(json)
    h = {'Content-Type': 'application/json'}
    for k,v in headers.items():
        h[k] = v
    return json, code, h

class Compressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data)+self.cObj.flush(Z_FULL_FLUSH)

def unpack_token(token):
    uid, sid, sig = token.split(".")
    uid = int(b64decode(uid).decode("utf8"))
    sid = int.from_bytes(b64decode(sid), "big")
    return (uid, sid, sig)

NoneType = type(None)

ALLOWED_SETTINGS = {
    "inline_attachment_media": bool,
    "show_current_game": bool,
    "view_nsfw_guilds": bool,
    "enable_tts_command": bool,
    "render_reactions": bool,
    "gif_auto_play": bool,
    "stream_notifications_enabled": bool,
    "animate_emoji": bool,
    "afk_timeout": int,
    "view_nsfw_commands": bool,
    "detect_platform_accounts": bool,
    "status": str,
    "explicit_content_filter": int,
    "custom_status": str,
    "default_guilds_restricted": bool,
    "theme": str,
    "allow_accessibility_detection": bool,
    "locale": str,
    "native_phone_integration_enabled": bool,
    "timezone_offset": int,
    "friend_discovery_flags": int,
    "contact_sync_enabled": bool,
    "disable_games_tab": bool,
    "developer_mode": bool,
    "render_embeds": bool,
    "animate_stickers": int,
    "message_display_compact": bool,
    "convert_emoticons": bool,
    "passwordless": bool,
    "personalization": bool,
    "usage_statistics": bool,
    "activity_restricted_guild_ids": list,
    "friend_source_flags": dict,
    "guild_positions": list,
    "guild_folders": list,
    "restricted_guilds": list,
}

ALLOWED_USERDATA = {
    "birth": str,
    "username": str,
    "discriminator": int,
    "phone": (str, NoneType),
    "premium": bool,
    "accent_color": (int, NoneType),
    "avatar": (str, NoneType),
    "avatar_decoration": (str, NoneType),
    "banner": (str, NoneType),
    "banner_color": (int, NoneType),
    "bio": str,
    "flags": int,
    "public_flags": int
}

ERRORS = {
    1: jdumps({"code": 50035, "errors": {"email": {"_errors": [{"code": "EMAIL_ALREADY_REGISTERED", "message": "Email address already registered."}]}}, "message": "Invalid Form Body"}),
    2: jdumps({"code": 50035, "errors": {"login": {"_errors": [{"code": "INVALID_LOGIN", "message": "Invalid login or password."}]}, "password": {"_errors": [{"code": "INVALID_LOGIN", "message": "Invalid login or password."}]}}, "message": "Invalid Form Body"}),
    3: jdumps({"code": 50035, "errors": {"login": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "Too many users have this username, please try another.."}]}}, "message": "Invalid Form Body"}),
    4: jdumps({"code": 10013, "message": "Unknown User"}),
    5: jdumps({"code": 50001, "message": "Missing Access"}),
    6: jdumps({"code": 50035, "errors": {"password": {"_errors": [{"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}]}}, "message": "Invalid Form Body"}),
    7: jdumps({"code": 50035, "errors": {"username": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "This name is used by too many users. Please enter something else or try again."}]}}, "message": "Invalid Form Body"}),
    8: jdumps({"code": 50035, "errors": {"username": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "This discriminator already used by someone. Please enter something else."}]}}, "message": "Invalid Form Body"}),
    9: jdumps({"code": 80004, "message": "No users with DiscordTag exist"}),
}

ECODES = {
    1: 400,
    2: 400,
    3: 400,
    4: 404,
    5: 403,
    6: 400,
    7: 400,
    8: 400,
    9: 400,
}