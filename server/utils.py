from base64 import b64encode as _b64encode, b64decode as _b64decode, b32decode
from time import time
from random import randint
from os import getpid
from json import dumps as jdumps, loads as jloads
from io import BytesIO
from magic import from_buffer
from hmac import new as hnew
from struct import pack as spack, unpack as sunpack
from asyncio import get_event_loop, sleep as asleep
from typing import Union
from aiomysql import escape_string
from re import compile as rcompile

global _INCREMENT_ID

def b64decode(data: Union[str, bytes]) -> bytes:
    if isinstance(data, str):
        data = data.encode("utf8")
    data += b'=' * (-len(data) % 4)
    for search, replace in ((b'-', b'+'), (b'_', b'/'), (b',', b'')):
        data = data.replace(search, replace)
    return _b64decode(data)

def b64encode(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf8")
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
    3: jdumps({"code": 50035, "errors": {"login": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "Too many users have this username, please try another."}]}}, "message": "Invalid Form Body"}),
    4: jdumps({"code": 10013, "message": "Unknown User"}),
    5: jdumps({"code": 50001, "message": "Missing Access"}),
    6: jdumps({"code": 50035, "errors": {"password": {"_errors": [{"code": "PASSWORD_DOES_NOT_MATCH", "message": "Passwords does not match."}]}}, "message": "Invalid Form Body"}),
    7: jdumps({"code": 50035, "errors": {"username": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "This name is used by too many users. Please enter something else or try again."}]}}, "message": "Invalid Form Body"}),
    8: jdumps({"code": 50035, "errors": {"username": {"_errors": [{"code": "USERNAME_TOO_MANY_USERS", "message": "This discriminator already used by someone. Please enter something else."}]}}, "message": "Invalid Form Body"}),
    9: jdumps({"code": 80004, "message": "No users with DiscordTag exist"}),
    10: jdumps({"code": 80007, "message": "You are already friends with that user."}),
    11: jdumps({"code": 80000, "message": "Incoming friend requests disabled."}),
    12: jdumps({"code": 60005, "message": "Invalid two-factor secret"}),
    13: jdumps({"code": 60008, "message": "Invalid two-factor code"}),
    14: jdumps({"code": 50018, "message": "This account is not enrolled in two factor authentication"}),
    15: jdumps({"code": 60002, "message": "Password does not match"}),
    16: jdumps({"code": 60006, "message": "Invalid two-factor auth ticket"}),
    17: jdumps({"code": 60011, "message": "Invalid key"}),
    18: jdumps({"code": 10003, "message": "Unknown Channel"}),
    19: jdumps({"code": 50006, "message": "Cannot send an empty message"}),
    20: jdumps({"code": 10008, "message": "Unknown Message"}),
    21: jdumps({"code": 50003, "message": "Cannot execute action on a DM channel"}),
    22: jdumps({"code": 50005, "message": "Cannot edit a message authored by another user"}),
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
    10: 400,
    11: 400,
    12: 400,
    13: 400,
    14: 400,
    15: 404,
    16: 400,
    17: 400,
    18: 404,
    19: 400,
    20: 404,
    21: 403,
    22: 403,
}

def getImage(image):
    if isinstance(image, bytes):
        image = BytesIO(image)
    elif isinstance(image, str) and (image.startswith("data:image/") or image.startswith("data:application/octet-stream")) and "base64" in image.split(",")[0]:
        image = BytesIO(_b64decode(image.split(",")[1].encode("utf8")))
        mime = from_buffer(image.read(1024), mime=True)
        if not mime.startswith("image/"):
            return
    elif not isinstance(image, BytesIO):
        return
    return image

def imageType(image):
    m = from_buffer(image.getvalue()[:1024], mime=True)
    if m.startswith("image/"):
        return m[6:]

def validImage(image):
    return imageType(image) in ["png", "webp", "gif", "jpeg", "jpg"] and image.getbuffer().nbytes < 8*1024*1024*1024

class RELATIONSHIP:
    PENDING = 0
    FRIEND = 1
    BLOCK = 2

class GATEWAY_OP:
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    STATUS = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    GUILD_MEMBERS = 8
    INV_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

class ChannelType:
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_NEWS = 5
    GUILD_NEWS_THREAD = 10
    GUILD_PUBLIC_THREAD = 11
    GUILD_PRIVATE_THREAD = 12
    GUILD_STAGE_VOICE = 13
    GUILD_DIRECTORY = 14

class MFA:
    _re = rcompile(r'^[A-Z0-9]{16}$')

    def __init__(self, key: str, uid: int):
        self.key = str(key).upper()
        self.uid = self.id = uid

    def getCode(self) -> str:
        key = b32decode(self.key.upper() + '=' * ((8 - len(self.key)) % 8))
        counter = spack('>Q', int(time() / 30))
        mac = hnew(key, counter, "sha1").digest()
        offset = mac[-1] & 0x0f
        binary = sunpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
        return str(binary)[-6:].zfill(6)

    @property
    def valid(self) -> bool:
        return bool(self._re.match(self.key))

async def execute_after(coro, seconds):
    async def _wait_exec(coro, seconds):
        await asleep(seconds)
        await coro
    get_event_loop().create_task(_wait_exec(coro, seconds))

def json_to_sql(json: dict, as_list=False, as_tuples=False) -> Union[str, list]:
    query = []
    for k,v in json.items():
        if isinstance(v, str):
            v = f"\"{escape_string(v)}\""
        elif isinstance(v, bool):
            v = "true" if v else "false"
        elif isinstance(v, (dict, list)):
            k = f"j_{k}"
            v = escape_string(jdumps(v))
            v = f"\"{v}\""
        elif isinstance(v, NoneType):
            v = "null"
        if as_tuples:
            query.append((k,v))
        else:
            query.append(f"`{k}`={v}")
    if as_list or as_tuples:
        return query
    return ", ".join(query)

def result_to_json(desc: list, result: list):
    j = {}
    for idx, value in enumerate(result):
        name = desc[idx][0]
        if name.startswith("j_"):
            name = name[2:]
            if value:
                value = jloads(value)
        j[name] = value
    return j

ping_regex = rcompile(r'\<@((?:!|&){0,1}\d{17,32})\>')