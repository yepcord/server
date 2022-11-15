from io import BytesIO

from PIL import Image
from async_timeout import timeout
from magic import from_buffer
from quart import Quart, request
from uuid import UUID

from server.classes import Emoji
from ..config import Config
from ..core import Core, CDN
from ..storage import FileStorage, S3Storage
from ..utils import b64decode, ALLOWED_AVATAR_SIZES


class YEPcord(Quart):
    async def process_response(self, response, request_context=None):
        response = await super(YEPcord, self).process_response(response, request_context)
        response.headers['Server'] = "YEPcord"
        response.headers['Access-Control-Allow-Origin'] = "*"
        response.headers['Access-Control-Allow-Headers'] = "*"
        response.headers['Access-Control-Allow-Methods'] = "*"
        response.headers['Content-Security-Policy'] = "connect-src *;"
        
        return response

app = YEPcord("YEPcord-api")
core = Core(b64decode(Config("KEY")))
storage = Config("STORAGE_TYPE")
if storage == "local" or storage is None:
    storage = FileStorage(Config("STORAGE_PATH", "files/"))
elif storage.lower() == "s3":
    a = (Config("S3_ENDPOINT"), Config("S3_KEYID"), Config("S3_ACCESSKEY"), Config("S3_BUCKET"))
    if None in a:
        raise Exception("You must set 'S3_ENDPOINT', 'S3_KEYID', 'S3_ACCESSKEY', 'S3_BUCKET' variables for using s3 storage type.")
    storage = S3Storage(*a)
cdn = CDN(storage, core)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

@app.before_serving
async def before_serving():
    await core.initDB(
        host=Config("DB_HOST"),
        port=3306,
        user=Config("DB_USER"),
        password=Config("DB_PASS"),
        db=Config("DB_NAME"),
        autocommit=True
    )

# Auth

@app.route("/avatars/<int:uid>/<string:name>", methods=["GET"])
async def avatars_uid_hash(uid, name):
    ahash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = int(request.args.get("size", 1024))
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if size not in ALLOWED_AVATAR_SIZES:
        return b'', 400
    if size > 1024: size = 1024
    avatar = await cdn.getAvatar(uid, ahash, size, fmt)
    if not avatar:
        return b'', 404
    return avatar, 200, {"Content-Type": f"image/{fmt}"}

@app.route("/banners/<int:uid>/<string:name>", methods=["GET"])
async def banners_uid_hash(uid, name):
    bhash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = int(request.args.get("size", 600))
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if size not in [600, 480, 300]:
        return b'', 400
    banner = await cdn.getBanner(uid, bhash, size, fmt)
    if not banner:
        return b'', 404
    return banner, 200, {"Content-Type": "image/webp"}

@app.route("/channel-icons/<int:cid>/<string:name>", methods=["GET"])
async def channelicons_cid_hash(cid, name):
    ihash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = int(request.args.get("size", 1024))
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if size not in ALLOWED_AVATAR_SIZES:
        return b'', 400
    if size > 1024: size = 1024
    icon = await cdn.getChannelIcon(cid, ihash, size, fmt)
    if not icon:
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{fmt}"}

@app.route("/icons/<int:gid>/<string:name>", methods=["GET"])
async def icons_gid_hash(gid, name):
    ihash = name.split(".")[0]
    fmt = name.split(".")[1]
    size = int(request.args.get("size", 1024))
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if size not in ALLOWED_AVATAR_SIZES:
        return b'', 400
    if size > 1024: size = 1024
    icon = await cdn.getGuildIcon(gid, ihash, size, fmt)
    if not icon:
        return b'', 404
    return icon, 200, {"Content-Type": f"image/{fmt}"}

@app.route("/emojis/<string:name>", methods=["GET"])
async def emojis_eid(name):
    eid = int(name.split(".")[0])
    fmt = name.split(".")[1]
    size = int(request.args.get("size", 56))
    if fmt not in ["webp", "png", "jpg", "gif"]:
        return b'', 400
    if size not in ALLOWED_AVATAR_SIZES:
        return b'', 400
    if size > 56: size = 56
    em = await core.getEmoji(eid)
    if not em:
        for a in (False, True):
            emoji = await cdn.getEmoji(eid, size, fmt, a)
            if emoji:
                break
    else:
        emoji = await cdn.getEmoji(eid, size, fmt, em.animated)
    if not emoji:
        return b'', 404
    return emoji, 200, {"Content-Type": f"image/{fmt}"}

@app.route("/attachments/<int:channel_id>/<int:attachment_id>/<string:name>", methods=["GET"])
async def attachments_channelid_attachmentid_name(channel_id, attachment_id, name):
    att = await core.getAttachment(attachment_id)
    if not att:
        return b'', 404
    h = {}
    if att.get("content_type"):
        h["Content-Type"] = att.content_type
    att = await cdn.getAttachment(channel_id, attachment_id, name)
    if not att:
        return b'', 404
    return att, 200, h

@app.route("/upload/attachment/<string:uuid>/<string:filename>", methods=["PUT"])
async def upload_attachment_uuid_filename(uuid, filename):
    try:
        uuid = str(UUID(uuid))
    except ValueError:
        return "Not found", 404
    if not (attachment := await core.getAttachmentByUUID(uuid)):
        return "Not found", 404
    if attachment.filename != filename:
        return "Not found", 404
    if attachment.uploaded:
        return ""
    if request.content_length > 100*1024*1024:
        return "Payload Too Large", 413
    async with timeout(100):
        data = await request.body
    meta = {}
    ct = attachment.get("content_type")
    if not ct:
        ct = from_buffer(data[:1024], mime=True)
    if ct.startswith("image/"):
        img = Image.open(BytesIO(data))
        meta.update({"height": img.height, "width": img.width})
        img.close()
    await cdn.uploadAttachment(data, attachment)
    await core.updateAttachment(attachment, attachment.copy().set(uploaded=True, metadata=meta, content_type=ct))

if __name__ == "__main__":
    from uvicorn import run as urun
    urun('main:app', host="0.0.0.0", port=8003, reload=True, use_colors=False)