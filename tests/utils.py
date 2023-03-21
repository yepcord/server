from hashlib import sha256
from hmac import new
from json import dumps
from time import time

from src.yepcord.classes.other import JWT
from src.yepcord.utils import b64encode, b64decode


def generateEmailVerificationToken(user_id: int, email: str, key: bytes):
    key = new(key, str(user_id).encode('utf-8'), sha256).digest()
    t = int(time())
    sig = b64encode(new(key, f"{user_id}:{email}:{t}".encode('utf-8'), sha256).digest())
    token = b64encode(dumps({"id": user_id, "email": email, "time": t}))
    token += f".{sig}"
    return token

def generateMfaVerificationKey(nonce: str, mfa_key: str, key: bytes):
    if not (payload := JWT.decode(nonce, key + b64decode(mfa_key))):
        return
    token = JWT.encode({"code": payload["code"]}, key)
    signature = token.split(".")[2]
    return signature.replace("-", "").replace("_", "")[:8].upper()