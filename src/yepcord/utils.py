from asyncio import get_event_loop, sleep as asleep
from base64 import b64encode as _b64encode, b64decode as _b64decode, b32decode
from hmac import new as hnew
from io import BytesIO
from json import dumps as jdumps, loads as jloads
from re import compile as rcompile
from struct import pack as spack, unpack as sunpack
from time import time
from typing import Union, Tuple, Optional

from aiomysql import escape_string
from magic import from_buffer


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


def c_json(json, code=200, headers=None):
    if headers is None:
        headers = {}
    if not isinstance(json, str):
        json = jdumps(json)
    h = {'Content-Type': 'application/json'}
    for k, v in headers.items():
        h[k] = v
    return json, code, h


def getImage(image: Union[str, bytes, BytesIO]) -> Optional[BytesIO]:
    if isinstance(image, str) and len(image) == 32:
        return  # Image hash provided instead of actual image data
    if isinstance(image, bytes):
        image = BytesIO(image)
    elif isinstance(image, str) and (
            image.startswith("data:image/") or image.startswith("data:application/octet-stream")) and "base64" in \
            image.split(",")[0]:
        image = BytesIO(_b64decode(image.split(",")[1].encode("utf8")))
        mime = from_buffer(image.read(1024), mime=True)
        if not mime.startswith("image/"):
            return  # Not image
    elif not isinstance(image, BytesIO):
        return  # Unknown type
    return image


def imageType(image: BytesIO) -> str:
    m = from_buffer(image.getvalue()[:1024], mime=True)
    if m.startswith("image/"):
        return m[6:]


def validImage(image: BytesIO) -> bool:
    return imageType(image) in ["png", "webp", "gif", "jpeg",
                                "jpg"] and image.getbuffer().nbytes < 8 * 1024 * 1024 * 1024


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


def json_to_sql(json: dict, as_list=False, as_tuples=False, is_none=False, for_insert=False) -> Union[
    str, list, Tuple[str, str]]:
    if not as_tuples: as_tuples = for_insert
    query = []
    for k, v in json.items():
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
            v = "IS NULL" if is_none else "NULL"
        if as_tuples:
            query.append((k, v))
        else:
            query.append(f"`{k}`={v}" if v != "IS NULL" else f"`{k}` {v}")
    if as_list or as_tuples:
        if for_insert:
            return ", ".join([r[0] for r in query]), ", ".join([str(r[1]) for r in query])
        return query
    return ", ".join(query)


def result_to_json(desc: list, result: list) -> dict:
    j = {}
    for idx, value in enumerate(result):
        name = desc[idx][0]
        if name.startswith("j_"):
            name = name[2:]
            if value:
                value = jloads(value)
        j[name] = value
    return j


ping_regex = rcompile(r'<@((?:!|&)?\d{17,32})>')


def proto_get(protoObj, path, default=None):
    path = path.split(".")
    try:
        o = protoObj
        for p in path:
            if hasattr(o, "ListFields"):
                if p not in [f[0].name for f in o.ListFields()] and p != "value":
                    return default
            o = getattr(o, p)
    except:
        return default
    return o


ALLOWED_AVATAR_SIZES = [16, 20, 22, 24, 28, 32, 40, 44, 48, 56, 60, 64, 80, 96, 100, 128, 160, 240, 256, 300, 320, 480,
                        512, 600, 640, 1024, 1280, 1536, 2048, 3072, 4096]


def int_length(i: int) -> int:
    # Returns int size in bytes
    return (i.bit_length() + 7) // 8


LOCALES = ["bg", "cs", "da", "de", "el", "en-GB", "es-ES", "fi", "fr", "hi", "hr", "hu", "it", "ja", "ko", "lt", "nl",
           "no", "pl", "pt-BR", "ro", "ru", "sv-SE", "th", "tr", "uk", "vi", "zh-CN", "zh-TW", "en-US"]

NoneType = type(None)
