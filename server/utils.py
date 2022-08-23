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

from server.errors import Errors

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


def mkSnowflake():
    global _INCREMENT_ID
    sf = _mksnowflake(int(time()*1000) - _EPOCH, _WORKER_ID, _PROCESS_ID, _INCREMENT_ID)
    _INCREMENT_ID += 1
    return sf


def lastSnowflake():
    return _mksnowflake(int(time()*1000) - _EPOCH, _WORKER_ID, _PROCESS_ID, _INCREMENT_ID)


mksf = mkSnowflake
lsf = lastSnowflake


def snowflake_timestamp(sf):
    return (sf >> 22) + _EPOCH


def c_json(json, code=200, headers={}):
    if not isinstance(json, str):
        json = jdumps(json)
    h = {'Content-Type': 'application/json'}
    for k,v in headers.items():
        h[k] = v
    return json, code, h


def mkError(code, errors=None, message=None):
    if errors is None:
        return {"code": code, "message": Errors(code) or message}
    err = {"code": code, "errors": {}, "message": Errors(code) or message}
    for path, error in errors.items():
        e = err["errors"]
        for p in path.split("."):
            e[p] = {}
            e = e[p]
        e["_errors"] = [error]
    return err


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


class RelationshipType:
    PENDING = 0
    FRIEND = 1
    BLOCK = 2


class GatewayOp:
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
            if not k.startswith("j_"):
                k = f"j_{k}"
            v = escape_string(jdumps(v))
            v = f"\"{v}\""
        elif v is None:
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


ping_regex = rcompile(r'<@((?:!|&){0,1}\d{17,32})>')


def parseMultipartRequest(body, boundary):
    res = {}
    parts = body.split(f"------WebKitFormBoundary{boundary}".encode("utf8"))
    parts.pop(0)
    parts.pop(-1)
    for part in parts:
        name = None
        ct = None
        p = part.split(b"\r\n")[1:-1]
        for _ in range(10):
            data = p.pop(0)
            if data == b'':
                break
            k, v = data.decode("utf8").split(":")
            if k == "Content-Type":
                ct = v
            if k == "Content-Disposition":
                v = ";".join(v.split(";")[1:])
                args = dict([a.strip().split("=") for a in v.strip().split(";")])
                name = args["name"][1:-1]
                del args["name"]
                if "[" in name and "]" in name:
                    name, idx = name.split("[")
                    idx = int(idx.replace("]", ""))
                    if name not in res:
                        res[name] = []
                    res[name].insert(idx, {"data": ""})
                    res[name][idx].update(args)
                else:
                    res[name] = {"data": ""}
                    res[name].update(args)
        if isinstance(res[name], list):
            d = res[name][idx]
        else:
            d = res[name]
        d["data"] = b"\r\n".join(p)
        if ct:
            d["content_type"] = ct
    return res