from aiofiles import open as aopen
from os.path import join as pjoin, isfile
from io import BytesIO
from hashlib import md5
from base64 import b64decode
from PIL import Image
from magic import from_buffer
from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from os import makedirs

class _Storage:
    def __init__(self, root_path="files/"):
        self.root = root_path

    async def convertImgToWebp(self, image):
        def convert_task(image):
            if isinstance(image, bytes):
                image = BytesIO(image)
            elif isinstance(image, str) and image.startswith("data:image/") and "base64" in image.split(",")[0]:
                image = BytesIO(b64decode(image.split(",")[1].encode("utf8")))
                mime = from_buffer(image.read(1024), mime=True)
                if not mime.startswith("image/"):
                    return
            elif not isinstance(image, BytesIO):
                return
            out = BytesIO()
            image = Image.open(image)
            s = image.size
            if s[0] != s[1]:
                return
            image.save(out, format="WEBP", lossless=True)
            return out
        with ThreadPoolExecutor() as pool:
            return await get_event_loop().run_in_executor(pool, lambda: convert_task(image))

    async def getAvatar(self, user_id, avatar_hash, size):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getAvatar(user_id, avatar_hash, size)

    async def getBanner(self, user_id, avatar_hash):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getBanner(user_id, avatar_hash)

    async def setAvatarFromBytesIO(self, user_id, image):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setAvatarFromBytesIO(user_id, image)

    async def setBannerFromBytesIO(self, user_id, image):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setBannerFromBytesIO(user_id, image)

class FileStorage(_Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        makedirs(self.root, exist_ok=True)

    async def getAvatar(self, user_id, avatar_hash, size):
        fpath = pjoin(self.root, "avatars", str(user_id), f"{avatar_hash}_{size}.webp")
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

    async def setAvatarFromBytesIO(self, user_id, image):
        avatar_hash = md5()
        avatar_hash.update(image.getvalue())
        avatar_hash = avatar_hash.hexdigest()
        image = Image.open(image)
        makedirs(pjoin(self.root, "avatars", str(user_id)), exist_ok=True)
        def save_task():
            for size in [32, 64, 80, 128, 256, 512, 1024]:
                img = image.resize((size, size))
                fpath = pjoin(self.root, "avatars", str(user_id), f"{avatar_hash}_{size}.webp")
                img.save(fpath)
        with ThreadPoolExecutor() as pool:
            await get_event_loop().run_in_executor(pool, save_task)
        return avatar_hash

    async def getBanner(self, user_id, banner_hash):
        fpath = pjoin(self.root, "banners", str(user_id), f"{banner_hash}.webp")
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

    async def setBannerFromBytesIO(self, user_id, image):
        banner_hash = md5()
        banner_hash.update(image.getvalue())
        banner_hash = banner_hash.hexdigest()
        image = Image.open(image)
        makedirs(pjoin(self.root, "banners", str(user_id)), exist_ok=True)
        def save_task():
            img = image.resize((300, 120))
            fpath = pjoin(self.root, "banners", str(user_id), f"{banner_hash}.webp")
            img.save(fpath)
        with ThreadPoolExecutor() as pool:
            await get_event_loop().run_in_executor(pool, save_task)
        return banner_hash