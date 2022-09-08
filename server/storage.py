from asyncio import get_event_loop, gather
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from io import BytesIO
from os import makedirs
from os.path import join as pjoin, isfile

from PIL import Image, ImageSequence
from aiofiles import open as aopen
from typing import Optional, Tuple


class _Storage:
    storage = None

    def __init__(self, root_path="files/"):
        self.root = root_path

    async def getAvatar(self, user_id: int, avatar_hash: str, size: int, fmt: str) -> Optional[bytes]:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getAvatar(user_id, avatar_hash, size, fmt)

    async def getBanner(self, user_id: int, avatar_hash: str, size: int, fmt: str) -> Optional[bytes]:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getBanner(user_id, avatar_hash, size, fmt)

    async def getChannelIcon(self, channel_id: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getChannelIcon(channel_id, icon_hash, size, fmt)

    async def getAttachment(self, channel_id: int, message_id: int, name: str):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getAttachment(channel_id, message_id, name)

    async def setAvatarFromBytesIO(self, user_id: int, image: BytesIO) -> str:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setAvatarFromBytesIO(user_id, image)

    async def setBannerFromBytesIO(self, user_id: int, image: BytesIO) -> str:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setBannerFromBytesIO(user_id, image)

    async def setChannelIconFromBytesIO(self, channel_id: int, image: BytesIO) -> str:
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setChannelIconFromBytesIO(channel_id, image)

    async def uploadAttachment(self, data, attachment):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.uploadAttachment(data, attachment)

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

class FileStorage(_Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        anim = image.n_frames > 1
        form = "gif" if anim else "png"
        hash = f"a_{hash}" if anim else hash
        makedirs(pjoin(self.root, f"{type}s", str(id)), exist_ok=True)
        size = (size, size_f(size))
        coro = resizeImage(image, size, form) if not anim else resizeAnimImage(image, size, form)
        data = await coro
        async with aopen(pjoin(self.root, f"{type}s", str(id), f"{hash}_{size[0]}.{form}"), "wb") as f:
            await f.write(data)
        return hash

    async def getAvatar(self, uid: int, avatar_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = avatar_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("avatar", uid, avatar_hash, size, fmt, def_size, lambda s: s)

    async def getChannelIcon(self, cid: int, icon_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = icon_hash.startswith("a_")
        def_size = 256 if anim else 1024
        return await self._getImage("channel_icon", cid, icon_hash, size, fmt, def_size, lambda s: s)

    async def getBanner(self, uid: int, banner_hash: str, size: int, fmt: str) -> Optional[bytes]:
        anim = banner_hash.startswith("a_")
        def_size = 480 if anim else 600
        return await self._getImage("banner", uid, banner_hash, size, fmt, def_size, lambda s: int(240*s/600))

    async def setAvatarFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = Image.open(image).n_frames > 1
        size = 256 if a else 1024
        return await self._setImage("avatar", uid, size, lambda s: s, image)

    async def setBannerFromBytesIO(self, uid: int, image: BytesIO) -> str:
        a = Image.open(image).n_frames > 1
        size = 480 if a else 600
        return await self._setImage("banner", uid, size, lambda s: int(240*s/600), image)

    async def setChannelIconFromBytesIO(self, cid: int, image: BytesIO) -> str:
        a = Image.open(image).n_frames > 1
        size = 256 if a else 1024
        return await self._setImage("channel_icon", cid, size, lambda s: s, image)

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