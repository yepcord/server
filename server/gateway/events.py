from base64 import b64encode
from datetime import datetime
from ..utils import GatewayOp, snowflake_timestamp
from time import time


class Event:
    pass


class DispatchEvent(Event):
    OP = GatewayOp.DISPATCH


class ReadyEvent(DispatchEvent):
    NAME = "READY"

    def __init__(self, user, client, core):
        self.user = user
        self.client = client
        self.core = core

    async def json(self) -> dict:
        userdata = await self.user.userdata
        settings = await self.user.settings
        proto = settings.to_proto()
        #print(proto.voice_and_video.stream_notifications_enabled)
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "v": 9,
                "user": {
                    "email": self.user.email,
                    "phone": userdata.phone,
                    "username": userdata.username,
                    "discriminator": str(userdata.discriminator).rjust(4, "0"),
                    "bio": userdata.bio,
                    "avatar": userdata.avatar,
                    "avatar_decoration": userdata.avatar_decoration,
                    "accent_color": userdata.accent_color,
                    "banner": userdata.banner,
                    "banner_color": userdata.banner_color,
                    "premium": True,
                    "premium_type": 2,
                    "premium_since": datetime.utcfromtimestamp(int(snowflake_timestamp(self.user.id)/1000)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "verified": True,
                    "purchased_flags": 0,
                    "nsfw_allowed": True,  # TODO: check
                    "mobile": True,  # TODO: check
                    "mfa_enabled": settings.mfa,
                    "id": str(self.user.id),
                    "flags": 0,
                },
                "users": await self.core.getRelatedUsers(self.user),
                "guilds": [],
                "session_id": self.client.sid,
                "presences": [],
                "relationships": await self.core.getRelationships(self.user),
                "connected_accounts": [],
                "consents": {
                    "personalization": {
                        "consented": settings.personalization
                    }
                },
                "country_code": "US",
                "experiments": [],
                "friend_suggestion_count": 0,
                "geo_ordered_rtc_regions": ["yepcord"],
                "guild_experiments": [],
                "guild_join_requests": [],
                "merged_members": [],
                "private_channels": await self.core.getPrivateChannels(self.user),
                "read_state": {
                    "version": 1,
                    "partial": False,
                    "entries": await self.core.getReadStatesJ(self.user)
                },
                "resume_gateway_url": "wss://127.0.0.1/",
                "session_type": "normal",
                "sessions": [{
                    "status": "online",
                    "session_id": self.client.sid,
                    "client_info": {
                        "version": 0,
                        "os": "windows",
                        "client": "web"
                    },
                    "activities": []
                }],
                "tutorial": None,
                "user_guild_settings": {
                    "version": 0,
                    "partial": False,
                    "entries": []
                },
                "user_settings": settings.to_json(),
                "user_settings_proto": b64encode(proto.dumps()).decode("utf8")
            }
        }


class ReadySupplementalEvent(DispatchEvent):
    NAME = "READY_SUPPLEMENTAL"

    def __init__(self, friends_presences):
        self.friends_presences = friends_presences

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "merged_presences": {
                    "guilds": [], # TODO
                    "friends": self.friends_presences
                },
                "merged_members": [], # TODO
                "guilds": [] # TODO
            }
        }


class RelationshipAddEvent(DispatchEvent):
    NAME = "RELATIONSHIP_ADD"

    def __init__(self, user_id, userdata, type):
        self.user_id = user_id
        self.userdata = userdata
        self.type = type

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": {
                    "username": self.userdata.username,
                    "public_flags": self.userdata.public_flags,
                    "id": str(self.user_id),
                    "discriminator": str(self.userdata.discriminator).rjust(4, "0"),
                    "avatar_decoration": self.userdata.avatar_decoration,
                    "avatar": self.userdata.avatar
                },
                "type": self.type,
                "should_notify": True,
                "nickname": None,
                "id": str(self.user_id)
            }
        }


class DMChannelCreate(DispatchEvent):
    NAME = "CHANNEL_CREATE"

    def __init__(self, channel_id, recipients, type, info):
        self.channel_id = channel_id
        self.recipients = recipients
        self.type = type
        self.info = info

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "type": self.type,
                "recipients": self.recipients,
                "last_message_id": str(self.info["last_message_id"]),
                "id": self.channel_id
            }
        }


class RelationshipRemoveEvent(DispatchEvent):
    NAME = "RELATIONSHIP_REMOVE"

    def __init__(self, user, type):
        self.user = user
        self.type = type

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "type": self.type,
                "id": str(self.user)
            }
        }


class UserUpdateEvent(DispatchEvent):
    NAME = "USER_UPDATE"

    def __init__(self, user, userdata, settings):
        self.user = user
        self.userdata = userdata
        self.settings = settings

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "verified": True,
                "username": self.userdata.username,
                "public_flags": self.userdata.public_flags,
                "phone": self.userdata.phone,
                "nsfw_allowed": True,  # TODO: get from age
                "mfa_enabled": bool(self.settings.mfa),
                "locale": self.settings.locale,
                "id": str(self.user.id),
                "flags": 0,
                "email": self.user.email,
                "discriminator": str(self.userdata.discriminator).rjust(4, "0"),
                "bio": self.userdata.bio,
                "banner_color": self.userdata.banner_color,
                "banner": self.userdata.banner,
                "avatar_decoration": self.userdata.avatar_decoration,
                "avatar": self.userdata.avatar,
                "accent_color": self.userdata.accent_color
            }
        }


class PresenceUpdateEvent(DispatchEvent):
    NAME = "PRESENCE_UPDATE"

    def __init__(self, user, userdata, status):
        self.user = user
        self.userdata = userdata
        self.status = status

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": {
                    "username": self.userdata.username,
                    "public_flags": self.userdata.public_flags,
                    "id": str(self.user),
                    "discriminator": str(self.userdata.discriminator).rjust(4, "0"),
                    "avatar": self.userdata.avatar
                },
                "status": self.status["status"],
                "last_modified": self.status.get("last_modified", int(time() * 1000)),
                "client_status": {} if self.status["status"] == "offline" else {"desktop": self.status["status"]},
                "activities": self.status.get("activities", [])
            }
        }


class MessageCreateEvent(DispatchEvent):
    NAME = "MESSAGE_CREATE"

    def __init__(self, message):
        self.message = message

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.message
        }


class TypingEvent(DispatchEvent):
    NAME = "TYPING_START"

    def __init__(self, user, channel):
        self.user = user
        self.channel = channel

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user_id": str(self.user),
                "timestamp": int(time()),
                "channel_id": str(self.channel)
            }
        }


class MessageUpdateEvent(MessageCreateEvent):
    NAME = "MESSAGE_UPDATE"


class MessageDeleteEvent(DispatchEvent):
    NAME = "MESSAGE_DELETE"

    def __init__(self, message, channel):
        self.message = message
        self.channel = channel

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.message),
                "channel_id": str(self.channel)
            }
        }


class MessageAckEvent(DispatchEvent):
    NAME = "MESSAGE_ACK"

    def __init__(self, ack_object):
        self.ack_object = ack_object

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.ack_object
        }
