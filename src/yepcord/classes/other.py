import re
from base64 import b32decode
from email.message import EmailMessage
from hashlib import sha512
from hmac import new
from json import loads, dumps
from struct import pack, unpack
from time import time
from typing import Union, Optional
from zlib import compressobj, Z_FULL_FLUSH

from aiosmtplib import send as smtp_send, SMTPConnectError

from ..config import Config
from ..utils import b64decode, b64encode


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
        except (IndexError, AssertionError, ValueError):
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

class BitFlags:
    def __init__(self, value: int, cls):
        self.cls = cls
        self.value = value
        self.parsedFlags = self.parseFlags()

    def parseFlags(self) -> list:
        flags = []
        value = self.value
        self.value = 0
        for val in self.cls.values().values():
            if (value & val) == val:
                flags.append(val)
                self.value |= val
        return flags

    def add(self, val: int):
        if val not in self.parsedFlags:
            self.value |= val
            self.parsedFlags.append(val)
        return self

    def remove(self, val: int):
        if val in self.parsedFlags:
            self.value &= ~val
            self.parsedFlags.remove(val)
        return self


class MFA:
    _re = re.compile(r'^[A-Z0-9]{16}$')

    def __init__(self, key: str, uid: int):
        self.key = str(key).upper()
        self.uid = self.id = uid

    def getCode(self) -> str:
        key = b32decode(self.key.upper() + '=' * ((8 - len(self.key)) % 8))
        counter = pack('>Q', int(time() / 30))
        mac = new(key, counter, "sha1").digest()
        offset = mac[-1] & 0x0f
        binary = unpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
        return str(binary)[-6:].zfill(6)

    @property
    def valid(self) -> bool:
        return bool(self._re.match(self.key))