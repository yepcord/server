"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from asyncio import get_event_loop, sleep as asleep
from base64 import b64encode as _b64encode, b64decode as _b64decode
from io import BytesIO
from json import dumps as jdumps, loads as jloads
from re import compile as rcompile
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
    elif not isinstance(image, BytesIO):
        return  # Unknown type
    image.seek(0)
    mime = from_buffer(image.read(1024), mime=True)
    if not mime.startswith("image/"):
        return  # Not image
    image.seek(0)
    return image


def imageType(image: BytesIO) -> str:
    m = from_buffer(image.getvalue()[:1024], mime=True)
    if m.startswith("image/"):
        return m[6:]


def validImage(image: BytesIO) -> bool:
    return imageType(image) in ["png", "webp", "gif", "jpeg",
                                "jpg"] and image.getbuffer().nbytes < 8 * 1024 * 1024


async def execute_after(coro, seconds):
    async def _wait_exec(coro_, seconds_):
        await asleep(seconds_)
        await coro_

    get_event_loop().create_task(_wait_exec(coro, seconds))


def json_to_sql(json: dict, as_list=False, as_tuples=False, is_none=False, for_insert=False) \
        -> Union[str, list, Tuple[str, str]]:
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


def proto_get(proto_obj, path, default=None, output_dict=None, output_name=None):
    path = path.split(".")
    # noinspection PyBroadException
    try:
        o = proto_obj
        for p in path:
            if hasattr(o, "ListFields"):
                if p not in [f[0].name for f in o.ListFields()] and p != "value":
                    return default
            o = getattr(o, p)
    except:
        return default
    if output_dict is not None and output_name is not None:
        output_dict[output_name] = o
    return o


def int_length(i: int) -> int:
    # Returns int size in bytes
    return (i.bit_length() + 7) // 8


LOCALES = ["bg", "cs", "da", "de", "el", "en-GB", "es-ES", "fi", "fr", "hi", "hr", "hu", "it", "ja", "ko", "lt", "nl",
           "no", "pl", "pt-BR", "ro", "ru", "sv-SE", "th", "tr", "uk", "vi", "zh-CN", "zh-TW", "en-US"]

NoneType = type(None)
