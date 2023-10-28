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
from __future__ import annotations
from abc import abstractmethod, ABCMeta
from asyncio import get_event_loop, gather
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from io import BytesIO
from os import makedirs
from os.path import join as pjoin, isfile
from typing import Optional, Tuple, Union

from PIL import Image, ImageSequence
from aiofiles import open as aopen

from .classes.singleton import SingletonMeta
from .config import Config
from .models import Attachment

try:
    from aioftp import Client, StatusCodeError

    _SUPPORT_FTP = True
except ImportError:  # pragma: no cover
    Client = object
    StatusCodeError = None
    _SUPPORT_FTP = False

try:
    from aioboto3 import Session
    from botocore.exceptions import ClientError

    _SUPPORT_S3 = True
except ImportError:  # pragma: no cover
    Session = object
    ClientError = None
    _SUPPORT_S3 = False


class FClient(Client):
    async def s_download(self, path: str) -> bytes:
        data = b''
        async with self.download_stream(path) as stream:
            async for block in stream.iter_by_block():
                data += block
        return data

    # noinspection PyShadowingBuiltins
    async def s_upload(self, path: str, data: Union[bytes, BytesIO]) -> None:
        dirs = path.split("/")[:-1]
        for dir in dirs:
            await self.make_directory(dir)
            await self.change_directory(dir)
        async with self.upload_stream(path.split("/")[-1]) as stream:
            await stream.write(data if isinstance(data, bytes) else data.getvalue())


async def resizeAnimImage(img: Image, size: Tuple[int, int], form: str) -> bytes:
    def _resize() -> bytes:
        frames = []
        for frame in ImageSequence.Iterator(img):
            frames.append(frame.resize(size))
        b = BytesIO()
        frames[0].save(b, format=form, save_all=True, append_images=frames[1:], loop=0)
        return b.getvalue()
    with ThreadPoolExecutor() as pool:
        res = await gather(get_event_loop().run_in_executor(pool, lambda: _resize()))
    return res[0]


async def resizeImage(image: Image, size: Tuple[int, int], form: str) -> bytes:
    def _resize(form_: str):
        img = image.resize(size)
        b = BytesIO()
        save_all = True
        if form_.lower() == "jpg":
            img = img.convert('RGB')
            form_ = "JPEG"
            save_all = False
        img.save(b, format=form_, save_all=save_all)
        return b.getvalue()
    with ThreadPoolExecutor() as pool:
        res = await gather(get_event_loop().run_in_executor(pool, _resize, form))
    return res[0]


def imageFrames(img: Image) -> int:
    return getattr(img, "n_frames", 1)


class SingletonABCMeta(ABCMeta, SingletonMeta):
    pass


# noinspection PyShadowingBuiltins
class _Storage(metaclass=SingletonABCMeta):

    @abstractmethod
    async def _getImage(self, type: str, id: int, hash: str, size: int, fmt: str, def_size: int, size_f) -> Optional[bytes]: ...  # pragma: no cover

    @abstractmethod
    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO, def_hash: str=None) -> str: ...  # pragma: no cover

    async def getAvatar(self, uid: int, avatar_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = avatar_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("avatar", uid, avatar_hash, size, fmt, def_size, lambda s: s)

    async def getChannelIcon(self, cid: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = icon_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("channel_icon", cid, icon_hash, size, fmt, def_size, lambda s: s)

    async def getGuildIcon(self, gid: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = icon_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("icon", gid, icon_hash, size, fmt, def_size, lambda s: s)

    async def getGuildAvatar(self, uid: int, gid: int, avatar_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = avatar_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage(f"guild/{gid}/avatar", uid, avatar_hash, size, fmt, def_size, lambda s: s)

    async def getSticker(self, sticker_id: int, size: int, fmt: str, animated: bool) -> Optional[bytes]:
        sticker_hash = "a_sticker" if animated else "sticker"
        return await self._getImage("sticker", sticker_id, sticker_hash, size, fmt, 320, lambda s: s)

    async def getGuildEvent(self, event_id: int, event_hash: str, size: int, fmt: str) -> Optional[bytes]:
        return await self._getImage("guild_event", event_id, event_hash, size, fmt, 600, lambda s: int(9 * s / 16))

    @abstractmethod
    async def getEmoji(self, eid: int, size: int, fmt: str, anim: bool) -> Optional[bytes]: ...  # pragma: no cover

    async def getRoleIcon(self, rid: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = icon_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("role_icon", rid, icon_hash, size, fmt, def_size, lambda s: s)

    async def getBanner(self, uid: int, banner_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = banner_hash.startswith("a_")
        def_size = 480 if anim else 600
        return await self._getImage("banner", uid, banner_hash, size, fmt, def_size, lambda s: int(9 * s / 16))

    async def getGuildSplash(self, gid: int, banner_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = banner_hash.startswith("a_")
        def_size = 480 if anim else 600
        return await self._getImage("splash", gid, banner_hash, size, fmt, def_size, lambda s: int(9*s/16))

    async def getAppIcon(self, aid: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = icon_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("app-icon", aid, icon_hash, size, fmt, def_size, lambda s: s)

    async def setAvatarFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("avatar", uid, size, lambda s: s, image)

    async def setBannerFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 480 if a else 600
        return await self._setImage("banner", uid, size, lambda s: int(9 * s / 16), image)

    async def setGuildSplashFromBytesIO(self, gid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 480 if a else 600
        return await self._setImage("splash", gid, size, lambda s: int(9*s/16), image)

    async def setChannelIconFromBytesIO(self, cid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("channel_icon", cid, size, lambda s: s, image)

    async def setGuildIconFromBytesIO(self, gid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("icon", gid, size, lambda s: s, image)

    async def setGuildAvatarFromBytesIO(self, uid: int, gid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage(f"guild/{gid}/avatar", uid, size, lambda s: s, image)

    async def setStickerFromBytesIO(self, sticker_id: int, image: BytesIO) -> str:
        return await self._setImage(f"sticker", sticker_id, 320, lambda s: s, image, def_hash="sticker")

    async def setGuildEventFromBytesIO(self, event_id: int, image: BytesIO) -> str:
        return await self._setImage(f"guild_event", event_id, 600, lambda s: int(9 * s / 16), image)

    @abstractmethod
    async def setEmojiFromBytesIO(self, eid: int, image: BytesIO) -> dict: ...  # pragma: no cover

    async def setRoleIconFromBytesIO(self, rid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("role_icon", rid, size, lambda s: s, image)

    async def setAppIconFromBytesIO(self, aid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("app-icon", aid, size, lambda s: s, image)

    @abstractmethod
    async def uploadAttachment(self, data, attachment: Attachment): ...  # pragma: no cover

    @abstractmethod
    async def getAttachment(self, channel_id, attachment_id, name): ...  # pragma: no cover


# noinspection PyShadowingBuiltins
class FileStorage(_Storage):
    def __init__(self, path="files/"):
        self.root = path
        makedirs(self.root, exist_ok=True)

    async def _getImage(self, type: str, id: int, hash: str, size: int, fmt: str, def_size: int, size_f) -> Optional[bytes]:
        anim = hash.startswith("a_")
        def_fmt = "gif" if anim else "png"
        paths = [f"{hash}_{size}.{fmt}", f"{hash}_{def_size}.{fmt}", f"{hash}_{def_size}.{def_fmt}"]
        paths = [pjoin(self.root, f"{type}s", str(id), name) for name in paths]
        size = (size, size_f(size))
        for i, p in enumerate(paths):
            if isfile(p):
                if i == 0:
                    async with aopen(p, "rb") as f:
                        return await f.read()
                else:
                    image = Image.open(p)
                    coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                    data = await coro
                    async with aopen(paths[0], "wb") as f:
                        await f.write(data)
                    return data

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO, def_hash: str=None) -> str:
        if def_hash is not None:
            hash = def_hash
        else:
            hash = md5()
            hash.update(image.getvalue())
            hash = hash.hexdigest()
        image = Image.open(image)
        anim = imageFrames(image) > 1
        form = "gif" if anim else "png"
        hash = f"a_{hash}" if anim else hash
        makedirs(pjoin(self.root, f"{type}s", str(id)), exist_ok=True)
        size = (size, size_f(size))
        coro = resizeImage(image, size, form) if not anim else resizeAnimImage(image, size, form)
        data = await coro
        async with aopen(pjoin(self.root, f"{type}s", str(id), f"{hash}_{size[0]}.{form}"), "wb") as f:
            await f.write(data)
        return hash

    async def getEmoji(self, eid: int, size: int, fmt: str, anim: bool) -> Optional[bytes]:
        def_fmt = "gif" if anim else "png"
        paths = [(f"{eid}", f"{size}.{fmt}"), (f"{eid}", f"56.{fmt}"), (f"{eid}", f"56.{def_fmt}")]
        paths = [pjoin(self.root, f"emojis", *name) for name in paths]
        size = (size, size)
        for i, p in enumerate(paths):
            if isfile(p):
                if i == 0:
                    async with aopen(p, "rb") as f:
                        return await f.read()
                else:
                    image = Image.open(p)
                    coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                    data = await coro
                    async with aopen(paths[0], "wb") as f:
                        await f.write(data)
                    return data

    async def setEmojiFromBytesIO(self, eid: int, image: BytesIO) -> dict:
        image = Image.open(image)
        anim = imageFrames(image) > 1
        form = "gif" if anim else "png"
        makedirs(pjoin(self.root, f"emojis", str(eid)), exist_ok=True)
        coro = resizeImage(image, (56, 56), form) if not anim else resizeAnimImage(image, (56, 56), form)
        data = await coro
        async with aopen(pjoin(self.root, f"emojis", str(eid), f"56.{form}"), "wb") as f:
            await f.write(data)
        return {"animated": anim}

    async def uploadAttachment(self, data, attachment: Attachment):
        fpath = pjoin(self.root, "attachments", str(attachment.channel.id), str(attachment.id))
        makedirs(fpath, exist_ok=True)
        async with aopen(pjoin(fpath, attachment.filename), "wb") as f:
            return await f.write(data)

    async def getAttachment(self, channel_id, attachment_id, name):
        fpath = pjoin(self.root, "attachments", str(channel_id), str(attachment_id), name)
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()


# noinspection PyShadowingBuiltins
class S3Storage(_Storage):
    def __init__(self, endpoint: str, key_id: str, access_key: str, bucket: str):
        if not _SUPPORT_S3:  # pragma: no cover
            raise RuntimeError("S3 module not found! To use s3 storage type, install dependencies "
                               "from requirements-s3.txt")
        self.endpoint = endpoint
        self.key_id = key_id
        self.access_key = access_key
        self.bucket = bucket
        self._sess = Session()
        self._args = {
            "endpoint_url": self.endpoint,
            "aws_access_key_id": self.key_id,
            "aws_secret_access_key": self.access_key
        }

    async def _getImage(self, type: str, id: int, hash: str, size: int, fmt: str, def_size: int, size_f) -> Optional[bytes]:
        async with self._sess.client("s3", **self._args) as s3:
            anim = hash.startswith("a_")
            def_fmt = "gif" if anim else "png"
            paths = [f"{hash}_{size}.{fmt}", f"{hash}_{def_size}.{fmt}", f"{hash}_{def_size}.{def_fmt}"]
            paths = [f"{type}s/{id}/{name}" for name in paths]
            size = (size, size_f(size))
            for i, p in enumerate(paths):
                f = BytesIO()
                try:
                    await s3.download_fileobj(self.bucket, p, f)
                except ClientError as ce:
                    if "(404)" not in str(ce):  # pragma: no cover
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(f)
                        coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                        data = await coro
                        await s3.upload_fileobj(BytesIO(data), self.bucket, paths[0])
                        return data

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO, def_hash: str=None) -> str:
        async with self._sess.client("s3", **self._args) as s3:
            if def_hash is not None:
                hash = def_hash
            else:
                hash = md5()
                hash.update(image.getvalue())
                hash = hash.hexdigest()
            image = Image.open(image)
            anim = imageFrames(image) > 1
            form = "gif" if anim else "png"
            hash = f"a_{hash}" if anim else hash
            size = (size, size_f(size))
            coro = resizeImage(image, size, form) if not anim else resizeAnimImage(image, size, form)
            data = await coro
            await s3.upload_fileobj(BytesIO(data), self.bucket, f"{type}s/{id}/{hash}_{size[0]}.{form}")
        return hash

    async def getEmoji(self, eid: int, size: int, fmt: str, anim: bool) -> Optional[bytes]:
        async with self._sess.client("s3", **self._args) as s3:
            def_fmt = "gif" if anim else "png"
            paths = [(f"{eid}", f"{size}.{fmt}"), (f"{eid}", f"56.{fmt}"), (f"{eid}", f"56.{def_fmt}")]
            paths = [f"emojis/{'/'.join(name)}" for name in paths]
            size = (size, size)
            for i, p in enumerate(paths):
                f = BytesIO()
                try:
                    await s3.download_fileobj(self.bucket, p, f)
                except ClientError as ce:
                    if "(404)" not in str(ce):  # pragma: no cover
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(f)
                        coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                        data = await coro
                        await s3.upload_fileobj(BytesIO(data), self.bucket, paths[0])
                        return data

    async def setEmojiFromBytesIO(self, eid: int, image: BytesIO) -> dict:
        async with self._sess.client("s3", **self._args) as s3:
            image = Image.open(image)
            anim = imageFrames(image) > 1
            form = "gif" if anim else "png"
            coro = resizeImage(image, (56, 56), form) if not anim else resizeAnimImage(image, (56, 56), form)
            data = await coro
            await s3.upload_fileobj(BytesIO(data), self.bucket, f"emojis/{eid}/56.{form}")
            return {"animated": anim}

    async def uploadAttachment(self, data, attachment: Attachment):
        async with self._sess.client("s3", **self._args) as s3:
            await s3.upload_fileobj(BytesIO(data), self.bucket,
                                    f"attachments/{attachment.channel.id}/{attachment.id}/{attachment.filename}")
            return len(data)

    async def getAttachment(self, channel_id, attachment_id, name):
        async with self._sess.client("s3", **self._args) as s3:
            f = BytesIO()
            try:
                await s3.download_fileobj(self.bucket, f"attachments/{channel_id}/{attachment_id}/{name}", f)
            except ClientError as ce:
                if "(404)" not in str(ce):  # pragma: no cover
                    raise
            else:
                return f.getvalue()


# noinspection PyShadowingBuiltins
class FTPStorage(_Storage):
    def __init__(self, host: str, user: str, password: str, port: int=21):
        if not _SUPPORT_FTP:  # pragma: no cover
            raise RuntimeError("Ftp module not found! To use ftp storage type, install dependencies "
                               "from requirements-ftp.txt")
        self.host = host
        self.user = user
        self.password = password
        self.port = port

    def _getClient(self) -> FClient:
        return FClient.context(self.host, user=self.user, password=self.password, port=self.port)

    async def _getImage(self, type: str, id: int, hash: str, size: int, fmt: str, def_size: int, size_f) -> Optional[bytes]:
        async with self._getClient() as ftp:
            anim = hash.startswith("a_")
            def_fmt = "gif" if anim else "png"
            paths = [f"{hash}_{size}.{fmt}", f"{hash}_{def_size}.{fmt}", f"{hash}_{def_size}.{def_fmt}"]
            paths = [f"{type}s/{id}/{name}" for name in paths]
            size = (size, size_f(size))
            for i, p in enumerate(paths):
                f = BytesIO()
                try:
                    f.write(await ftp.s_download(p))
                except StatusCodeError as sce:
                    if "550" not in sce.received_codes:  # pragma: no cover
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(f)
                        coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                        data = await coro
                        await ftp.s_upload(paths[0], data)
                        return data

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO, def_hash: str=None) -> str:
        async with self._getClient() as ftp:
            if def_hash is not None:
                hash = def_hash
            else:
                hash = md5()
                hash.update(image.getvalue())
                hash = hash.hexdigest()
            image = Image.open(image)
            anim = imageFrames(image) > 1
            form = "gif" if anim else "png"
            hash = f"a_{hash}" if anim else hash
            size = (size, size_f(size))
            coro = resizeImage(image, size, form) if not anim else resizeAnimImage(image, size, form)
            data = await coro
            await ftp.s_upload(f"{type}s/{id}/{hash}_{size[0]}.{form}", data)
        return hash

    async def getEmoji(self, eid: int, size: int, fmt: str, anim: bool) -> Optional[bytes]:
        async with self._getClient() as ftp:
            def_fmt = "gif" if anim else "png"
            paths = [(f"{eid}", f"{size}.{fmt}"), (f"{eid}", f"56.{fmt}"), (f"{eid}", f"56.{def_fmt}")]
            paths = [f"emojis/{'/'.join(name)}" for name in paths]
            size = (size, size)
            for i, p in enumerate(paths):
                f = BytesIO()
                try:
                    f.write(await ftp.s_download(p))
                except StatusCodeError as sce:
                    if "550" not in sce.received_codes:  # pragma: no cover
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(f)
                        coro = resizeImage(image, size, fmt) if not anim else resizeAnimImage(image, size, fmt)
                        data = await coro
                        await ftp.s_upload(paths[0], data)
                        return data

    async def setEmojiFromBytesIO(self, eid: int, image: BytesIO) -> dict:
        async with self._getClient() as ftp:
            image = Image.open(image)
            anim = imageFrames(image) > 1
            form = "gif" if anim else "png"
            coro = resizeImage(image, (56, 56), form) if not anim else resizeAnimImage(image, (56, 56), form)
            data = await coro
            await ftp.s_upload(f"emojis/{eid}/56.{form}", data)
            return {"animated": anim}

    async def uploadAttachment(self, data, attachment: Attachment):
        async with self._getClient() as ftp:
            await ftp.s_upload(f"attachments/{attachment.channel.id}/{attachment.id}/{attachment.filename}", data)
            return len(data)

    async def getAttachment(self, channel_id, attachment_id, name):
        async with self._getClient() as ftp:
            try:
                return await ftp.s_download(f"attachments/{channel_id}/{attachment_id}/{name}")
            except StatusCodeError as sce:
                if "550" not in sce.received_codes:  # pragma: no cover
                    raise


def getStorage() -> _Storage:
    storage_type = Config.STORAGE["type"]
    assert storage_type in ("local", "s3", "ftp",), "STORAGE.type must be one of ('local', 's3', 'ftp')"
    storage = Config.STORAGE[storage_type]

    if storage_type == "s3":
        if None in storage.values():  # pragma: no cover
            raise Exception(
                "You must set 'endpoint', 'key_id', 'access_key', 'bucket' variables to use s3 storage type."
            )
        return S3Storage(**storage)
    elif storage_type == "ftp":
        if None in storage.values():  # pragma: no cover
            raise Exception("You must set 'host', 'port', 'user', 'password' variables to use ftp storage type.")
        return FTPStorage(**storage)
    return FileStorage(**storage)
