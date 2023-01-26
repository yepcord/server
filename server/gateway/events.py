from base64 import b64encode
from datetime import datetime
from typing import List

from ..classes.user import GuildMember
from ..config import Config
from ..ctx import Ctx
from ..utils import snowflake_timestamp
from ..enums import GatewayOp, ChannelType
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
        Ctx["user_id"] = self.user.id
        Ctx["with_channels"] = True
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "v": 9,
                "user": {
                    "email": self.user.email,
                    "phone": userdata.phone,
                    "username": userdata.username,
                    "discriminator": userdata.s_discriminator,
                    "bio": userdata.bio,
                    "avatar": userdata.avatar,
                    "avatar_decoration": userdata.avatar_decoration,
                    "accent_color": userdata.accent_color,
                    "banner": userdata.banner,
                    "banner_color": userdata.banner_color,
                    "premium": True,
                    "premium_type": 2,
                    "premium_since": datetime.utcfromtimestamp(int(snowflake_timestamp(self.user.id)/1000)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "verified": bool(self.user.verified),
                    "purchased_flags": 0,
                    "nsfw_allowed": userdata.nsfw_allowed,  # TODO: check
                    "mobile": True,  # TODO: check
                    "mfa_enabled": settings.mfa,
                    "id": str(self.user.id),
                    "flags": 0,
                },
                "users": await self.core.getRelatedUsers(self.user),
                "guilds": [await guild.json for guild in await self.core.getUserGuilds(self.user)], # TODO
                "session_id": self.client.sid,
                "presences": [], # TODO
                "relationships": await self.core.getRelationships(self.user),
                "connected_accounts": [], # TODO
                "consents": {
                    "personalization": {
                        "consented": settings.personalization
                    }
                },
                "country_code": "US",
                "experiments": [], # TODO
                "friend_suggestion_count": 0,
                "geo_ordered_rtc_regions": ["yepcord"],
                "guild_experiments": [], # TODO
                "guild_join_requests": [], # TODO
                "merged_members": [], # TODO
                "private_channels": await self.core.getPrivateChannels(self.user),
                "read_state": {
                    "version": 1,
                    "partial": False,
                    "entries": await self.core.getReadStatesJ(self.user)
                },
                "resume_gateway_url": f"wss://{Config('GATEWAY_HOST')}/",
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
                    "entries": [] # TODO
                },
                "user_settings": settings.to_json(for_db=False),
                "user_settings_proto": b64encode(proto.SerializeToString()).decode("utf8")
            }
        }

class ReadySupplementalEvent(DispatchEvent):
    NAME = "READY_SUPPLEMENTAL"

    def __init__(self, friends_presences, guilds_ids):
        self.friends_presences = friends_presences
        self.guilds_ids = guilds_ids

    async def json(self) -> dict:
        g = [{"voice_states": [], "id": str(i), "embedded_activities": []} for i in self.guilds_ids] # TODO
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "merged_presences": {
                    "guilds": [[]], # TODO
                    "friends": self.friends_presences
                },
                "merged_members": [[]], # TODO
                "guilds": g
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
                    "discriminator": self.userdata.s_discriminator,
                    "avatar_decoration": self.userdata.avatar_decoration,
                    "avatar": self.userdata.avatar
                },
                "type": self.type,
                "should_notify": True,
                "nickname": None,
                "id": str(self.user_id)
            }
        }

class DMChannelCreateEvent(DispatchEvent):
    NAME = "CHANNEL_CREATE"

    def __init__(self, channel, recipients):
        self.channel = channel
        self.recipients = recipients

    async def json(self) -> dict:
        j = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "type": self.channel.type,
                "recipients": self.recipients,
                "last_message_id": str(self.channel.last_message_id),
                "id": str(self.channel.id)
            }
        }
        if self.channel.type == ChannelType.GROUP_DM:
            j["d"]["owner_id"] = str(self.channel.owner_id)
            j["d"]["icon"] = self.channel.icon
            j["d"]["name"] = self.channel.name
        return j

class DMChannelUpdateEvent(DMChannelCreateEvent):
    NAME = "CHANNEL_UPDATE"

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
                "verified": self.user.verified,
                "username": self.userdata.username,
                "public_flags": self.userdata.public_flags,
                "phone": self.userdata.phone,
                "nsfw_allowed": self.userdata.nsfw_allowed,
                "mfa_enabled": bool(self.settings.mfa),
                "locale": self.settings.locale,
                "id": str(self.user.id),
                "flags": 0,
                "email": self.user.email,
                "discriminator": self.userdata.s_discriminator,
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
                    "discriminator": self.userdata.s_discriminator,
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

class ChannelRecipientAddEvent(DispatchEvent):
    NAME = "CHANNEL_RECIPIENT_ADD"

    def __init__(self, channel_id, user):
        self.channel_id = channel_id
        self.user = user

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.user,
                "channel_id": str(self.channel_id)
            }
        }

class ChannelRecipientRemoveEvent(ChannelRecipientAddEvent):
    NAME = "CHANNEL_RECIPIENT_REMOVE"

class DMChannelDeleteEvent(DispatchEvent):
    NAME = "CHANNEL_DELETE"

    def __init__(self, channel):
        self.channel = channel

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.channel
        }

class ChannelPinsUpdateEvent(DispatchEvent):
    NAME = "CHANNEL_PINS_UPDATE"

    def __init__(self, channel_id, last_pin_timestamp):
        self.channel_id = channel_id
        self.last_pin_timestamp = last_pin_timestamp

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "last_pin_timestamp": self.last_pin_timestamp,
                "channel_id": str(self.channel_id)
            }
        }

class MessageReactionAddEvent(DispatchEvent):
    NAME = "MESSAGE_REACTION_ADD"

    def __init__(self, user_id, message_id, channel_id, emoji):
        self.user_id = user_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.emoji = emoji

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user_id": str(self.user_id),
                "channel_id": str(self.channel_id),
                "message_id": str(self.message_id),
                "emoji": self.emoji
            }
        }

class MessageReactionRemoveEvent(MessageReactionAddEvent):
    NAME = "MESSAGE_REACTION_REMOVE"

class GuildCreateEvent(DispatchEvent):
    NAME = "GUILD_CREATE"

    def __init__(self, guild_obj):
        self.guild_obj = guild_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.guild_obj
        }

class GuildUpdateEvent(GuildCreateEvent):
    NAME = "GUILD_UPDATE"

class GuildDeleteEvent(DispatchEvent):
    NAME = "GUILD_DELETE"

    def __init__(self, guild_id):
        self.guild_id = guild_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.guild_id)
            }
        }

class GuildMembersListUpdateEvent(DispatchEvent):
    NAME = "GUILD_MEMBER_LIST_UPDATE"

    def __init__(self, members: List[GuildMember], total_members: int, statuses, guild_id):
        self.members = members
        self.total_members = total_members
        self.statuses = statuses
        self.groups = {}
        for s in statuses.values():
            if s["status"] not in self.groups:
                self.groups[s["status"]] = 0
            self.groups[s["status"]] += 1
        self.guild_id = guild_id

    async def json(self) -> dict:
        groups = [{"id": status, "count": count} for status, count in self.groups.items()]
        items = []
        for mem in self.members:
            m = await mem.json
            m["presence"] = {
                "user": {"id": str(mem.user_id)},
                "status": self.statuses[mem.user_id]["status"],
                "client_status": {} if self.statuses[mem.user_id]["status"] == "offline" else {"desktop": self.statuses[mem.user_id]["status"]},
                "activities": self.statuses[mem.user_id].get("activities", [])
            }
            items.append({"member": m})
        items.sort(key=lambda i: i["member"]["presence"]["status"])
        _ls = None
        _ins = {}
        _offset = 0
        for idx, i in enumerate(items):
            if (_s := i["member"]["presence"]["status"]) != _ls:
                group = {"id": _s, "count": self.groups[_s]}
                _ins[idx+_offset] = {"group": group}
                _offset += 1
            _ls = _s
        for idx, ins in _ins.items():
            items.insert(idx, ins)
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "ops": [{
                    "range": [0, 99],
                    "op": "SYNC",
                    "items": items
                }],
                "online_count": self.statuses.get("online", 0),
                "member_count": self.total_members,
                "id": "everyone",
                "guild_id": str(self.guild_id),
                "groups": groups
            }
        }

class UserNoteUpdateEvent(DispatchEvent):
    NAME = "USER_NOTE_UPDATE"

    def __init__(self, uid, note):
        self.uid = uid
        self.note = note

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.uid),
                "note": self.note
            }
        }

class UserSettingsProtoUpdateEvent(DispatchEvent):
    NAME = "USER_SETTINGS_PROTO_UPDATE"

    def __init__(self, proto, stype):
        self.proto = proto
        self.type = stype

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "settings": {
                    "type": self.type,
                    "proto": self.proto
                },
                "partial": False
            }
        }

class GuildEmojisUpdate(DispatchEvent):
    NAME = "GUILD_EMOJIS_UPDATE"

    def __init__(self, guild_id, emojis):
        self.guild_id = guild_id
        self.emojis = emojis

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": str(self.guild_id),
                "emojis": self.emojis
            }
        }