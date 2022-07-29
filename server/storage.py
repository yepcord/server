from aiofiles import open as aopen
from os.path import join as pjoin, isfile
from io import BytesIO
from hashlib import md5
from base64 import b64decode
from PIL import Image
from magic import from_buffer

class _Storage:
    def __init__(self, root_path="files/"):
        self.root = root_path

    async def getAvatar(self, user_id, avatar_hash):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.getAvatar(user_id, avatar_hash)

    async def convertImgToWebp(self, image):
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
        s = image.shape
        if s[0] != s[1]:
            return
        image.save(out, format="WEBP", lossless=True)
        return out

    async def setAvatarFromBytesIO(self, user_id, image):
        if type(self) == _Storage:
            raise NotImplementedError
        return await self.storage.setAvatarFromStream(user_id, image)

class FileStorage(_Storage):
    async def getAvatar(self, user_id, avatar_hash):
        fpath = pjoin(self.root, "avatars", str(user_id), avatar_hash+".webp")
        if not isfile(fpath):
            return
        async with aopen(fpath, "rb") as f:
            return await f.read()

    async def setAvatarFromBytesIO(self, user_id, image):
        avatar_hash = md5()
        avatar_hash.update(image.getvalue())
        avatar_hash = avatar_hash.hexdigest()
        fpath = pjoin(self.root, "avatars", str(user_id), avatar_hash+".webp")
        async with aopen(fpath, "wb") as f:
            await f.write(image.getvalue())
        return avatar_hash