from email.message import EmailMessage
from hashlib import sha256, sha512
from hmac import new
from json import loads, dumps
from time import time
from typing import Union, Optional
from zlib import compressobj, Z_FULL_FLUSH

from aiosmtplib import send as smtp_send, SMTPConnectError

from server.config import Config
from server.utils import b64decode, b64encode


class ZlibCompressor:
    def __init__(self):
        self.cObj = compressobj()

    def __call__(self, data):
        return self.cObj.compress(data) + self.cObj.flush(Z_FULL_FLUSH)

#class UserConnection(DBModel): # TODO: implement UserConnection
#    FIELDS = ("type", "state", "username", "service_uid", "friend_sync", "integrations", "visible",
#              "verified", "revoked", "show_activity", "two_way_link",)
#    ID_FIELD = "uid"
#    DB_FIELDS = {"integrations": "j_integrations"}
#
#    def __init__(self, uid, type, state=Null, username=Null, service_uid=Null, friend_sync=Null, integrations=Null,
#                 visible=Null, verified=Null, revoked=Null, show_activity=Null, two_way_link=Null):
#        self.uid = uid
#        self.type = type
#        self.state = state
#        self.username = username
#        self.service_uid = service_uid
#        self.friend_sync = friend_sync
#        self.integrations = integrations
#        self.visible = visible
#        self.verified = verified
#        self.revoked = revoked
#        self.show_activity = show_activity
#        self.two_way_link = two_way_link
#
#        self._checkNulls()


class EmailMsg:
    def __init__(self, to: str, subject: str, text: str):
        self.to = to
        self.subject = subject
        self.text = text

    async def send(self):
        message = EmailMessage()
        message["From"] = "no-reply@yepcord.ml"
        message["To"] = self.to
        message["Subject"] = self.subject
        message.set_content(self.text)
        try:
            await smtp_send(message, hostname=Config('SMTP_HOST'), port=int(Config('SMTP_PORT')))
        except SMTPConnectError:
            pass # TODO: write warning to log

"""
class GuildTemplate(DBModel):
    FIELDS = ("template",)
    ID_FIELD = "id"
    DB_FIELDS = {"template": "j_template"}
    SCHEMA = Schema({
        "id": int,
        "updated_at": Or(int, NoneType),
        "template": {
           "name": str,
           "description": Or(str, NoneType),
           "usage_count": int,
           "creator_id": Use(int),
           "creator":{
              "id": Use(int),
              "username": str,
              "avatar": Or(str, NoneType),
              "avatar_decoration":Or(str, NoneType),
              "discriminator": Use(int),
              "public_flags": int
           },
           "source_guild_id": Use(int),
           "serialized_source_guild": {
              "name": str,
              "description": Or(str, NoneType),
              "region": str,
              "verification_level": int,
              "default_message_notifications": int,
              "explicit_content_filter": int,
              "preferred_locale": str,
              "afk_timeout": int,
              "roles":[{
                    "id": int,
                    "name": str,
                    "color": int,
                    "hoist": bool,
                    "mentionable": bool,
                    "permissions": Use(int),
                    "icon": Or(str, NoneType),
                    "unicode_emoji": Or(str, NoneType)
              }],
              "channels":[{
                    "id": int,
                    "type": And(Use(int), lambda i: i in ChannelType.values()),
                    "name": str,
                    "position": int,
                    "topic": Or(str, NoneType),
                    "bitrate": int,
                    "user_limit": int,
                    "nsfw": bool,
                    "rate_limit_per_user": int,
                    "parent_id": Or(int, NoneType),
                    "default_auto_archive_duration": Or(int, NoneType),
                    "permission_overwrites": [Any], # TODO
                    "available_tags": Any, # TODO
                    "template": str,
                    "default_reaction_emoji": Or(str, NoneType),
                    "default_thread_rate_limit_per_user": Or(int, NoneType),
                    "default_sort_order": Any # TODO
              }],
              "afk_channel_id": Or(int, NoneType),
              "system_channel_id": int,
              "system_channel_flags": int
           },
           "is_dirty": Any # TODO
        }
    })

    def __init__(self, id, template):
        self.code = id
        self.template = template

        self._checkNulls()
        self.to_typed_json(with_id=True, with_values=True)
"""

class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(cls.__class__, cls).__new__(cls)
        return cls._instance

    @classmethod
    def getInstance(cls):
        return cls._instance


class JWT:
    """
    Json Web Token Hmac-sha512 implementation
    """

    @staticmethod
    def decode(token: str, secret: Union[str, bytes]) -> Optional[dict]:
        if isinstance(secret, str):
            secret = b64decode(secret)

        try:
            header, payload, signature = token.split(".")
            header_dict = loads(b64decode(header).decode("utf8"))
            assert header_dict.get("alg") == "HS512"
            assert header_dict.get("typ") == "JWT"
            assert (exp := header_dict.get("exp", 0)) > time() or exp == 0
            signature = b64decode(signature)
        except (IndexError, AssertionError, ValueError) as e:
            return

        sig = f"{header}.{payload}".encode("utf8")
        sig = new(secret, sig, sha512).digest()
        if sig == signature:
            payload = b64decode(payload).decode("utf8")
            return loads(payload)

    @staticmethod
    def encode(payload: dict, secret: Union[str, bytes], expire_timestamp: Union[int, float]=0) -> str:
        if isinstance(secret, str):
            secret = b64decode(secret)

        header = {
            "alg": "HS512",
            "typ": "JWT",
            "exp": int(expire_timestamp)
        }
        header = b64encode(dumps(header, separators=(',', ':')))
        payload = b64encode(dumps(payload, separators=(',', ':')))

        signature = f"{header}.{payload}".encode("utf8")
        signature = new(secret, signature, sha512).digest()
        signature = b64encode(signature)

        return f"{header}.{payload}.{signature}"