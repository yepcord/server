from base64 import b64encode
from time import time
from typing import List

from ..yepcord.classes.user import GuildMember
from ..yepcord.config import Config
from ..yepcord.snowflake import Snowflake
from ..yepcord.ctx import Ctx
from ..yepcord.enums import GatewayOp, ChannelType


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
                    "premium_since": Snowflake.toDatetime(self.user.id).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "verified": bool(self.user.verified),
                    "purchased_flags": 0,
                    "nsfw_allowed": userdata.nsfw_allowed,
                    "mobile": True,  # TODO: check
                    "mfa_enabled": settings.mfa,
                    "id": str(self.user.id),
                    "flags": 0,
                },
                "users": await self.core.getRelatedUsers(self.user),
                "guilds": [await guild.json for guild in await self.core.getUserGuilds(self.user)],
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
                "private_channels": [await channel.json for channel in await self.core.getPrivateChannels(self.user)],
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
                "user_settings": await settings.json,
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

    def __init__(self, message, channel, guild):
        self.message = message
        self.channel = channel
        self.guild = guild

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.message),
                "channel_id": str(self.channel)
            }
        }
        if self.guild is not None:
            data["d"]["guild_id"] = str(self.guild)
        return data

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
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": self.guild_obj
        }
        if "presences" not in data["d"]: data["d"]["presences"] = []
        if "voice_states" not in data["d"]: data["d"]["voice_states"] = []
        if "embedded_activities" not in data["d"]: data["d"]["embedded_activities"] = []

        return data

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

class ChannelUpdateEvent(DispatchEvent):
    NAME = "CHANNEL_UPDATE"

    def __init__(self, channel):
        self.channel = channel

    async def json(self) -> dict:
        j = {
            "t": self.NAME,
            "op": self.OP,
            "d": self.channel
        }
        return j

class ChannelCreateEvent(ChannelUpdateEvent):
    NAME = "CHANNEL_CREATE"

class ChannelDeleteEvent(ChannelUpdateEvent):
    NAME = "CHANNEL_DELETE"

class InviteDeleteEvent(DispatchEvent):
    NAME = "INVITE_DELETE"

    def __init__(self, payload):
        self.payload = payload

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": self.payload
        }
        return data

class GuildMemberRemoveEvent(DispatchEvent):
    NAME = "GUILD_MEMBER_REMOVE"

    def __init__(self, guild_id, user_obj):
        self.guild_id = guild_id
        self.user_obj = user_obj

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.user_obj,
                "guild_id": str(self.guild_id)
            }
        }
        return data

class GuildBanAddEvent(DispatchEvent):
    NAME = "GUILD_BAN_ADD"

    def __init__(self, guild_id, user_obj):
        self.guild_id = guild_id
        self.user_obj = user_obj

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.user_obj,
                "guild_id": str(self.guild_id)
            }
        }
        return data

class GuildBanRemoveEvent(GuildBanAddEvent):
    NAME = "GUILD_BAN_REMOVE"

class MessageBulkDeleteEvent(DispatchEvent):
    NAME = "MESSAGE_DELETE_BULK"

    def __init__(self, guild_id, channel_id, messages):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.messages = messages

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "ids": [str(message_id) for message_id in self.messages],
                "guild_id": str(self.guild_id),
                "channel_id": str(self.channel_id)
            }
        }
        return data

class GuildRoleCreateEvent(DispatchEvent):
    NAME = "GUILD_ROLE_CREATE"

    def __init__(self, guild_id, role_obj):
        self.guild_id = guild_id
        self.role_obj = role_obj

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "role": self.role_obj,
                "guild_id": str(self.guild_id)
            }
        }
        return data

class GuildRoleUpdateEvent(GuildRoleCreateEvent):
    NAME = "GUILD_ROLE_UPDATE"

class GuildRoleDeleteEvent(DispatchEvent):
    NAME = "GUILD_ROLE_DELETE"

    def __init__(self, guild_id, role_id):
        self.guild_id = guild_id
        self.role_id = role_id

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": str(self.guild_id),
                "role_id": str(self.role_id)
            }
        }
        return data

class GuildMemberUpdateEvent(DispatchEvent):
    NAME = "GUILD_MEMBER_UPDATE"

    def __init__(self, guild_id, member_obj):
        self.guild_id = guild_id
        self.member_obj = member_obj

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": self.member_obj
        }
        data["d"]["guild_id"] = str(self.guild_id)
        return data

class GuildMembersChunkEvent(DispatchEvent):
    NAME = "GUILD_MEMBERS_CHUNK"

    def __init__(self, members: List[GuildMember], presences: List, guild_id: int):
        self.members = members
        self.presences = presences
        self.guild_id = guild_id

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "members": [await member.json for member in self.members],
                "presences": self.presences,
                "chunk_index": 0,
                "chunk_count": 1,
                "guild_id": str(self.guild_id)
            }
        }
        return data

class GuildAuditLogEntryCreateEvent(DispatchEvent):
    NAME = "GUILD_AUDIT_LOG_ENTRY_CREATE"

    def __init__(self, entry_obj):
        self.entry_obj = entry_obj

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": self.entry_obj
        }
        return data

class WebhooksUpdateEvent(DispatchEvent):
    NAME = "WEBHOOKS_UPDATE"

    def __init__(self, guild_id, channel_id):
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": str(self.guild_id),
                "channel_id": str(self.channel_id)
            }
        }
        return data

class StickersUpdateEvent(DispatchEvent):
    NAME = "GUILD_STICKERS_UPDATE"

    def __init__(self, guild_id, stickers):
        self.guild_id = guild_id
        self.stickers = stickers

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": str(self.guild_id),
                "stickers": self.stickers
            }
        }
        return data

class UserDeleteEvent(DispatchEvent):
    NAME = "USER_DELETE"

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user_id": str(self.user_id)
            }
        }

class GuildScheduledEventCreateEvent(DispatchEvent):
    NAME = "GUILD_SCHEDULED_EVENT_CREATE"

    def __init__(self, event_obj):
        self.event_obj = event_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.event_obj
        }

class GuildScheduledEventUpdateEvent(GuildScheduledEventCreateEvent):
    NAME = "GUILD_SCHEDULED_EVENT_UPDATE"

class ScheduledEventUserAddEvent(DispatchEvent):
    NAME = "GUILD_SCHEDULED_EVENT_USER_ADD"

    def __init__(self, user_id, event_id, guild_id):
        self.user_id = user_id
        self.event_id = event_id
        self.guild_id = guild_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user_id": str(self.user_id),
                "guild_scheduled_event_id": str(self.event_id),
                "guild_id": str(self.guild_id),
            }
        }

class ScheduledEventUserRemoveEvent(ScheduledEventUserAddEvent):
    NAME = "GUILD_SCHEDULED_EVENT_USER_REMOVE"

class GuildScheduledEventDeleteEvent(GuildScheduledEventCreateEvent):
    NAME = "GUILD_SCHEDULED_EVENT_DELETE"