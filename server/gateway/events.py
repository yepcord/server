from ..utils import GATEWAY_OP
from time import time

class Event:
    pass

class RelationshipAddEvent(Event):
    NAME = "RELATIONSHIP_ADD"

    def __init__(self, user_id, userdata, type):
        self.user_id = user_id
        self.userdata = userdata
        self.type = type

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "user": {
                    "username": self.userdata["username"],
                    "public_flags": self.userdata["public_flags"],
                    "id": str(self.user_id),
                    "discriminator": str(self.userdata["discriminator"]).rjust(4, "0"),
                    "avatar_decoration": self.userdata["avatar_decoration"],
                    "avatar": self.userdata["avatar"]
                },
                "type": self.type,
                "should_notify": True,
                "nickname": None,
                "id": str(self.user_id)
            }
        }

class DMChannelCreate(Event):
    NAME = "CHANNEL_CREATE"

    def __init__(self, channel_id, recipients, type, info):
        self.channel_id = channel_id
        self.recipients = recipients
        self.type = type
        self.info = info

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "type": self.type,
                "recipients": self.recipients,
                "last_message_id": str(self.info["last_message_id"]),
                "id": self.channel_id
            }
        }

class RelationshipRemoveEvent(Event):
    NAME = "RELATIONSHIP_REMOVE"

    def __init__(self, user, type):
        self.user = user
        self.type = type

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "type": self.type,
                "id": str(self.user)
            }
        }

class UserUpdateEvent(Event):
    NAME = "USER_UPDATE"

    def __init__(self, user, userdata, settings):
        self.user = user
        self.userdata = userdata
        self.settings = settings

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "verified": True,
                "username": self.userdata["username"],
                "public_flags": self.userdata["public_flags"],
                "phone": self.userdata["phone"],
                "nsfw_allowed": True, # TODO: get from age
                "mfa_enabled": bool(self.settings["mfa"]),
                "locale": self.settings["locale"],
                "id": str(self.user.id),
                "flags": 0,
                "email": self.user.email,
                "discriminator": str(self.userdata["discriminator"]).rjust(4, "0"),
                "bio": self.userdata["bio"],
                "banner_color": self.userdata["banner_color"],
                "banner": self.userdata["banner"],
                "avatar_decoration": self.userdata["avatar_decoration"],
                "avatar": self.userdata["avatar"],
                "accent_color": self.userdata["accent_color"]
            }
        }

class PresenceUpdateEvent(Event):
    NAME = "PRESENCE_UPDATE"

    def __init__(self, user, userdata, status):
        self.user = user
        self.userdata = userdata
        self.status = status

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "user": {
                    "username": self.userdata["username"],
                    "public_flags": self.userdata["public_flags"],
                    "id": str(self.user),
                    "discriminator": str(self.userdata["discriminator"]).rjust(4, "0"),
                    "avatar": self.userdata["avatar"]
                },
                "status": self.status["status"],
                "last_modified": self.status.get("last_modified", int(time() * 1000)),
                "client_status": {} if self.status["status"] == "offline" else {"desktop": self.status["status"]},
                "activities": self.status.get("activities", [])
            }
        }

class MessageCreateEvent(Event):
    NAME = "MESSAGE_CREATE"

    def __init__(self, message):
        self.message = message

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": self.message
        }

class TypingEvent(Event):
    NAME = "TYPING_START"

    def __init__(self, user, channel):
        self.user = user
        self.channel = channel

    @property
    def json(self):
        return {
            "t": self.NAME,
            "op": GATEWAY_OP.DISPATCH,
            "d": {
                "user_id": str(self.user),
                "timestamp": int(time()),
                "channel_id": str(self.channel)
            }
        }