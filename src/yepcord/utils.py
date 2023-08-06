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
from re import compile as rcompile
from typing import Union, Optional, Any

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
    return imageType(image) in ["png", "webp", "gif", "jpeg", "jpg"] and image.getbuffer().nbytes < 8 * 1024 * 1024


async def execute_after(coro, seconds):
    async def _wait_exec(coro_, seconds_):
        await asleep(seconds_)
        await coro_

    get_event_loop().create_task(_wait_exec(coro, seconds))


ping_regex = rcompile(r'<@((?:!|&)?\d{17,32})>')


def dict_get(obj: dict, path: str, default: Any=None, output_dict: dict=None, output_name: str=None):
    path = path.split(".")
    for p in path:
        if p not in obj:
            return default
        obj = obj[p]
    if output_dict is not None and output_name is not None:
        output_dict[output_name] = obj
    return obj


def int_size(i: int) -> int:
    # Returns int size in bytes
    return (i.bit_length() + 7) // 8


LOCALES = ["bg", "cs", "da", "de", "el", "en-GB", "es-ES", "fi", "fr", "hi", "hr", "hu", "it", "ja", "ko", "lt", "nl",
           "no", "pl", "pt-BR", "ro", "ru", "sv-SE", "th", "tr", "uk", "vi", "zh-CN", "zh-TW", "en-US"]

NoneType = type(None)


def freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return frozenset({k: freeze(v) for k, v in obj.items()}.items())
    if isinstance(obj, list):
        return frozenset([freeze(v) for v in obj])
    return obj


def unfreeze(obj: Any) -> Any:
    if isinstance(obj, frozenset):
        return dict({k: unfreeze(v) for k, v in obj})
    if isinstance(obj, list):
        return [unfreeze(v) for v in obj]
    return obj
