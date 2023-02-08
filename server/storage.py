from asyncio import get_event_loop, gather
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from io import BytesIO
from os import makedirs
from os.path import join as pjoin, isfile

from PIL import Image, ImageSequence
from aiofiles import open as aopen
from typing import Optional, Tuple, Union

try:
    from aioftp import Client, StatusCodeError

    _SUPPORT_FTP = True
except ImportError:
    Client = None
    StatusCodeError = None
    _SUPPORT_FTP = False

try:
    from aioboto3 import Session
    from botocore.exceptions import ClientError

    _SUPPORT_S3 = True
except ImportError:
    Session = None
    ClientError = None
    _SUPPORT_S3 = False

class FClient(Client):
    async def s_download(self, path: str) -> bytes:
        data = b''
        async with self.download_stream(path) as stream:
            async for block in stream.iter_by_block():
                data += block
        return data

    async def s_upload(self, path: str, data: Union[bytes, BytesIO]) -> None:
        dirs = path.split("/")[:-1]
        for dir in dirs:
            await self.make_directory(dir)
            await self.change_directory(dir)
        async with self.upload_stream(path.split("/")[-1]) as stream:
            await stream.write(data if isinstance(data, bytes) else data.getvalue())

async def resizeAnimImage(img: Image, size: Tuple[int, int], form: str):
    def _resize(img: Image, size: Tuple[int, int], form: str) -> bytes:
        orig_size = (img.size[0], img.size[1])
        n_frames = getattr(img, 'n_frames', 1)

        def resize_frame(frame):
            if orig_size == size:
                return frame
            return frame.resize(size)

        if n_frames == 1:
            return resize_frame(img)
        frames = []
        for frame in ImageSequence.Iterator(img):
            frames.append(resize_frame(frame))
        b = BytesIO()
        frames[0].save(b, format=form, save_all=True, append_images=frames[1:], loop=0)
        return b.getvalue()
    with ThreadPoolExecutor() as pool:
        res = await gather(get_event_loop().run_in_executor(pool, lambda: _resize(img, size, form)))
    return res[0]

async def resizeImage(image: Image, size: Tuple[int, int], form: str) -> bytes:
    def _resize():
        img = image.resize(size)
        b = BytesIO()
        img.save(b, format=form, save_all=True)
        return b.getvalue()
    with ThreadPoolExecutor() as pool:
        res = await gather(get_event_loop().run_in_executor(pool, _resize))
    return res[0]

def imageFrames(img) -> int:
    return getattr(img, "n_frames", 1)

class _Storage:
    async def _getImage(self, type: str, id: int, hash: str, size: int, fmt: str, def_size: int, size_f) -> Optional[
        bytes]:
        raise NotImplementedError

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO) -> str:
        raise NotImplementedError

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

    async def getEmoji(self, eid: int, size: int, fmt: str, anim: bool) -> Optional[bytes]:
        raise NotImplementedError

    async def getBanner(self, uid: int, banner_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = banner_hash.startswith("a_")
        def_size = 480 if anim else 600
        return await self._getImage("banner", uid, banner_hash, size, fmt, def_size, lambda s: int(240*s/600))

    async def setAvatarFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 256 if a else 1024
        return await self._setImage("avatar", uid, size, lambda s: s, image)

    async def setBannerFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = imageFrames(Image.open(image)) > 1
        size = 480 if a else 600
        return await self._setImage("banner", uid, size, lambda s: int(240*s/600), image)

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

    async def setEmojiFromBytesIO(self, eid: int, image: BytesIO) -> dict:
        raise NotImplementedError

    async def uploadAttachment(self, data, attachment):
        raise NotImplementedError

    async def getAttachment(self, channel_id, attachment_id, name):
        raise NotImplementedError

class FileStorage(_Storage):
    def __init__(self, root_path="files/"):
        self.root = root_path
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

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO) -> str:
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

    async def uploadAttachment(self, data, attachment):
        fpath = pjoin(self.root, "attachments", str(attachment.channel_id), str(attachment.id))
        makedirs(fpath, exist_ok=True)
        async with aopen(pjoin(fpath, attachment.filename), "wb") as f:
            return await f.write(data)

    async def getAttachment(self, channel_id, attachment_id, name):
        fpath = pjoin(self.root, "attachments", str(channel_id), str(attachment_id), name)
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

class S3Storage(_Storage):
    def __init__(self, endpoint: str, key_id: str, access_key: str, bucket: str):
        if not _SUPPORT_S3:
            raise RuntimeError("S3 module not found! To use s3 storage type, install dependencies from requirements-s3.txt")
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
                    if "(404)" not in str(ce):
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

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO) -> str:
        async with self._sess.client("s3", **self._args) as s3:
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
                    if "(404)" not in str(ce):
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(p)
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

    async def uploadAttachment(self, data, attachment):
        async with self._sess.client("s3", **self._args) as s3:
            await s3.upload_fileobj(BytesIO(data), self.bucket, f"attachments/{attachment.channel_id}/{attachment.id}/{attachment.filename}")

    async def getAttachment(self, channel_id, attachment_id, name):
        async with self._sess.client("s3", **self._args) as s3:
            f = BytesIO()
            try:
                await s3.download_fileobj(self.bucket, f"attachments/{channel_id}/{attachment_id}/{name}", f)
            except ClientError as ce:
                if "(404)" not in str(ce):
                    raise
            else:
                return f.getvalue()

class FTPStorage(_Storage):
    def __init__(self, host: str, user: str, password: str, port: int=21):
        if not _SUPPORT_FTP:
            raise RuntimeError("Ftp module not found! To use ftp storage type, install dependencies from requirements-ftp.txt")
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
                    if "550" not in sce.received_codes:
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

    async def _setImage(self, type: str, id: int, size: int, size_f, image: BytesIO) -> str:
        async with self._getClient() as ftp:
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
                    if "550" not in sce.received_codes:
                        raise
                    continue
                else:
                    if i == 0:
                        return f.getvalue()
                    else:
                        image = Image.open(p)
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

    async def uploadAttachment(self, data, attachment):
        async with self._getClient() as ftp:
            await ftp.s_upload(f"attachments/{attachment.channel_id}/{attachment.id}/{attachment.filename}", data)

    async def getAttachment(self, channel_id, attachment_id, name):
        async with self._getClient() as ftp:
            try:
                return await ftp.s_download(f"attachments/{channel_id}/{attachment_id}/{name}")
            except ClientError as ce:
                if "(404)" not in str(ce):
                    raise