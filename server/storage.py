from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from io import BytesIO
from os import makedirs
from os.path import join as pjoin, isfile

from PIL import Image
from aiofiles import open as aopen


class _Storage:
    def __init__(self, root_path="files/"):
        self.root = root_path

    async def convertImgToWebp(self, image):
        def convert_task(image):
            out = BytesIO()
            image = Image.open(image)
            s = image.size
            if s[0] != s[1]:
                return
            image.save(out, lossless=True, save_all=True)
            return out
        with ThreadPoolExecutor() as pool:
            return await get_event_loop().run_in_executor(pool, lambda: convert_task(image))

    async def resizeImage(self, image, size=(300, 120)):
        def res_image(image, size):
            out = BytesIO()
            image = Image.open(image).resize(size)
            image.save(out, lossless=True, save_all=True)
            return out
        with ThreadPoolExecutor() as pool:
            return await get_event_loop().run_in_executor(pool, lambda: res_image(image, size))

    async def getAvatar(self, user_id, avatar_hash, size, fmt):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getAvatar(user_id, avatar_hash, size, fmt)

    async def getBanner(self, user_id, avatar_hash, size, fmt):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getBanner(user_id, avatar_hash, size, fmt)

    async def setAvatarFromBytesIO(self, user_id, image):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setAvatarFromBytesIO(user_id, image)

    async def setBannerFromBytesIO(self, user_id, image):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setBannerFromBytesIO(user_id, image)

"""
def _resizeAnimated(image, size):
    _frames = list(ImageSequence.Iterator(image))
    frames = []
    for idx, frame in enumerate(_frames):
        frame = frame.copy()
        frame.thumbnail(size, Image.ANTIALIAS)
        frames.append(frame)
        #frames[idx] = frame
    print(len(frames))
    im = frames.pop(0)
    im.info = image.info
    b = BytesIO()
    im.save(b, format="GIF", save_all=True, append_images=frames)
    return Image.open(BytesIO(b.getvalue()))
"""

def _resizeAnimated(image, size):
    return image.resize(size)

class FileStorage(_Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        makedirs(self.root, exist_ok=True)

    async def getAvatar(self, user_id, avatar_hash, size, fmt):
        fpath = pjoin(self.root, "avatars", str(user_id), f"{avatar_hash}_{size}.{fmt}")
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

    async def setAvatarFromBytesIO(self, user_id, image):
        avatar_hash = md5()
        avatar_hash.update(image.getvalue())
        avatar_hash = avatar_hash.hexdigest()
        image = Image.open(image)
        a = False
        formats = ["png", "webp"]
        if image.n_frames > 1:
            a = True
            avatar_hash = f"a_{avatar_hash}"
            formats = ["webp", "gif"]
            image.seek(image.tell()+1)
        makedirs(pjoin(self.root, "avatars", str(user_id)), exist_ok=True)
        def save_task():
            for size in [32, 40, 48, 64, 80, 128, 256, 512, 1024]:
                img = image.resize((size, size)) if not a else _resizeAnimated(image, (size, size))
                for form in formats:
                    fpath = pjoin(self.root, "avatars", str(user_id), f"{avatar_hash}_{size}.{form}")
                    img.save(fpath, format=form, save_all=True)
        with ThreadPoolExecutor() as pool:
            await get_event_loop().run_in_executor(pool, save_task)
        return avatar_hash

    async def getBanner(self, user_id, banner_hash, size, fmt):
        fpath = pjoin(self.root, "banners", str(user_id), f"{banner_hash}_{size}.{fmt}")
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

    async def setBannerFromBytesIO(self, user_id, image):
        banner_hash = md5()
        banner_hash.update(image.getvalue())
        banner_hash = banner_hash.hexdigest()
        image = Image.open(image)
        a = False
        formats = ["png", "webp"]
        if image.n_frames > 1:
            a = True
            banner_hash = f"a_{banner_hash}"
            formats = ["webp", "gif"]
            image.seek(image.tell()+1)
        makedirs(pjoin(self.root, "banners", str(user_id)), exist_ok=True)
        def save_task():
                for size in [(600, 240), (300, 120)]:
                    img = image.resize(size) if not a else _resizeAnimated(image, size)
                    for form in formats:
                        fpath = pjoin(self.root, "banners", str(user_id), f"{banner_hash}_{size[0]}.{form}")
                        img.save(fpath, format=form, save_all=True)
        with ThreadPoolExecutor() as pool:
            await get_event_loop().run_in_executor(pool, save_task)
        return banner_hash