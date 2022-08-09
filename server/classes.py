from datetime import datetime

from .utils import b64encode, ChannelType, snowflake_timestamp


class _User:
    def __eq__(self, other):
        return isinstance(other, _User) and self.id == other.id

class Session(_User):
    def __init__(self, uid, sid, sig):
        self.id = uid
        self.uid = uid
        self.sid = sid
        self.sig = sig
        self.token = f"{b64encode(str(uid).encode('utf8'))}.{b64encode(int.to_bytes(sid, 6, 'big'))}.{sig}"

class User(_User):
    def __init__(self, uid, email=None, core=None):
        self.id = uid
        self.email = email
        self._core = core
    
    @property
    def settings(self):
        return self._settings()

    @property
    def data(self):
        return self._userdata()

    @property
    def userdata(self):
        return self._userdata()

    async def _settings(self):
        return await self._core.getSettingsForUser(self)

    async def _userdata(self):
        return await self._core.getDataForUser(self)

class LoginUser(_User):
    def __init__(self, uid, session, theme, locale):
        self.id = uid
        self.session = session
        self.theme = theme
        self.locale = locale
        self.token = session.token

class UserId(_User):
    def __init__(self, uid):
        self.id = uid

class _Channel:
    def __eq__(self, other):
        return isinstance(other, _Channel) and self.id == other.id

class DMChannel(_Channel):
    def __init__(self, cid, recipients, core):
        self.id = cid
        self.type = ChannelType.DM
        self.recipients = recipients
        self._core = core

    @property
    def info(self):
        return self._info()

    async def messages(self, limit=50, before=None, after=None):
        limit = int(limit)
        if limit > 100:
            limit = 100
        return await self._core.getChannelMessages(self, limit)

    async def _info(self):
        return await self._core.getChannelInfo(self)

class _Message:
    def __eq__(self, other):
        return isinstance(other, _Message) and self.id == other.id

class Message(_Message):
    def __init__(self, mid, content, channel_id, author, edit=None, attachments=[], embeds=[], reactions=[], pinned=False, webhook=None, application=None, mtype=0, flags=0, reference=None, thread=None, components=[], core=None):
        self.id = mid
        self.content = content
        self.channel_id = channel_id
        self.author = author
        self.edit = edit
        self.attachments = attachments
        self.embeds = embeds
        self.reactions = reactions
        self.pinned = pinned
        self.webhook = webhook
        self.application = application
        self.type = mtype
        self.flags = flags
        self.reference = reference
        self.thread = thread
        self.components = components
        self._core = core

    @property
    def json(self):
        return self._json()

    async def _json(self):
        author = await self._core.getUserData(self.author)
        d = datetime.utcfromtimestamp(int(snowflake_timestamp(self.id) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
        e = datetime.utcfromtimestamp(int(snowflake_timestamp(self.edit) / 1000)).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00") if self.edit else None
        return {
            "id": str(self.id),
            "type": self.type,
            "content": self.content,
            "channel_id": str(self.channel_id),
            "author": {
                "id": str(self.author),
                "username": author["username"],
                "avatar": author["avatar"],
                "avatar_decoration": author["avatar_decoration"],
                "discriminator": str(author["discriminator"]).rjust(4, "0"),
                "public_flags": author["public_flags"]
            },
            "attachments": self.attachments, # TODO: parse attachments
            "embeds": self.embeds, # TODO: parse embeds
            "mentions": [], # TODO: parse mentions
            "mention_roles": [], # TODO: parse mention_roles
            "pinned": self.pinned,
            "mention_everyone": False, # TODO: parse mention_everyone
            "tts": False,
            "timestamp": d,
            "edited_timestamp": e,
            "flags": self.flags,
            "components": self.components, # TODO: parse components
        }