"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

from base64 import b64encode
from time import time
from typing import List, TYPE_CHECKING

from ..yepcord.config import Config
from ..yepcord.enums import GatewayOp
from ..yepcord.models import Emoji, Application, Integration
from ..yepcord.models.interaction import Interaction
from ..yepcord.snowflake import Snowflake

if TYPE_CHECKING:  # pragma: no cover
    from ..yepcord.models import Channel, Invite, GuildMember, UserData, User, UserSettings
    from ..yepcord.core import Core
    from .gateway import GatewayClient
    from .presences import Presence


class Event:
    pass


class DispatchEvent(Event):
    OP = GatewayOp.DISPATCH
    NAME: str = ""

    async def json(self) -> dict: ...


class RawDispatchEvent(DispatchEvent):
    def __init__(self, data: dict):
        self.data = data

    async def json(self) -> dict:
        return self.data


class RawDispatchEventWrapper(RawDispatchEvent):
    def __init__(self, event: DispatchEvent, data: dict=None):
        super().__init__(data)
        self._event = event

    async def json(self) -> dict:
        return await self._event.json()


class ReadyEvent(DispatchEvent):
    NAME = "READY"

    def __init__(self, user: User, client: GatewayClient, core: Core):
        self.user = user
        self.client = client
        self.core = core

    async def json(self) -> dict:
        userdata = await self.user.userdata
        settings = await self.user.settings
        proto = settings.proto().get()
        data = {
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
                "guilds": [await guild.ds_json(user_id=self.user.id, for_gateway=True, with_channels=True)
                           for guild in await self.core.getUserGuilds(self.user)],
                "session_id": self.client.sid,
                "presences": [],  # TODO
                "relationships": await self.core.getRelationships(self.user),
                "connected_accounts": [],  # TODO
                "consents": {
                    "personalization": {
                        "consented": settings.personalization
                    }
                } if not self.user.is_bot else {},
                "country_code": "US",
                "experiments": [],  # TODO
                "friend_suggestion_count": 0,
                "geo_ordered_rtc_regions": ["yepcord"],
                "guild_experiments": [],  # TODO
                "guild_join_requests": [],  # TODO
                "merged_members": [],  # TODO
                "private_channels": [await channel.ds_json(user_id=self.user.id)
                                     for channel in await self.core.getPrivateChannels(self.user)],
                "read_state": {
                    "version": 1,
                    "partial": False,
                    "entries": await self.core.getReadStatesJ(self.user) if not self.user.is_bot else []
                },
                "resume_gateway_url": f"wss://{Config.GATEWAY_HOST}/",
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
                    "entries": []  # TODO
                },
                "user_settings": settings.ds_json() if not self.user.is_bot else {},
                "user_settings_proto": b64encode(proto.SerializeToString()).decode("utf8") if not self.user.is_bot
                else None
            }
        }
        if self.user.is_bot:
            del data["d"]["user_settings_proto"]
            del data["d"]["read_state"]
            application = await Application.get(id=self.user.id)
            data["d"]["application"] = {
                "id": str(application.id),
                "flags": application.flags,
            }

        return data


class ReadySupplementalEvent(DispatchEvent):
    NAME = "READY_SUPPLEMENTAL"

    def __init__(self, friends_presences: list[dict], guilds_ids: list[int]):
        self.friends_presences = friends_presences
        self.guilds_ids = guilds_ids

    async def json(self) -> dict:
        g = [{"voice_states": [], "id": str(i), "embedded_activities": []} for i in self.guilds_ids]  # TODO
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "merged_presences": {
                    "guilds": [[]],  # TODO
                    "friends": self.friends_presences
                },
                "merged_members": [[]],  # TODO
                "guilds": g
            }
        }


class RelationshipAddEvent(DispatchEvent):
    NAME = "RELATIONSHIP_ADD"

    def __init__(self, user_id: int, userdata: UserData, type_: int):
        self.user_id = user_id
        self.userdata = userdata
        self.type = type_

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.userdata.ds_json,
                "type": self.type,
                "should_notify": True,
                "nickname": None,
                "id": str(self.user_id)
            }
        }


class DMChannelCreateEvent(DispatchEvent):
    NAME = "CHANNEL_CREATE"

    def __init__(self, channel: Channel, *, channel_json_kwargs: dict=None):
        self.channel = channel
        self._channel_kwargs = {} if channel_json_kwargs is None else channel_json_kwargs
        self._channel_kwargs["with_ids"] = False

    async def json(self) -> dict:
        j = {
            "t": self.NAME,
            "op": self.OP,
            "d": await self.channel.ds_json(**self._channel_kwargs)
        }
        return j


class DMChannelUpdateEvent(DMChannelCreateEvent):
    NAME = "CHANNEL_UPDATE"


class RelationshipRemoveEvent(DispatchEvent):
    NAME = "RELATIONSHIP_REMOVE"

    def __init__(self, user_id: int, type_: int):
        self.user_id = user_id
        self.type = type_

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "type": self.type,
                "id": str(self.user_id)
            }
        }


class UserUpdateEvent(DispatchEvent):
    NAME = "USER_UPDATE"

    def __init__(self, user: User, userdata: UserData, settings: UserSettings):
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

    def __init__(self, userdata: UserData, presence: Presence):
        self.userdata = userdata
        self.presence = presence

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.userdata.ds_json,
                "status": self.presence.public_status,
                "last_modified": int(time() * 1000),
                "client_status": {} if self.presence.public_status == "offline"
                else {"desktop": self.presence.public_status},
                "activities": [] if self.presence.public_status == "offline" else self.presence.activities
            }
        }


class MessageCreateEvent(DispatchEvent):
    NAME = "MESSAGE_CREATE"

    def __init__(self, message_obj: dict):
        self.message_obj = message_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.message_obj
        }


class TypingEvent(DispatchEvent):
    NAME = "TYPING_START"

    def __init__(self, user_id: int, channel_id: int):
        self.user_id = user_id
        self.channel_id = channel_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user_id": str(self.user_id),
                "timestamp": int(time()),
                "channel_id": str(self.channel_id)
            }
        }


class MessageUpdateEvent(MessageCreateEvent):
    NAME = "MESSAGE_UPDATE"


class MessageDeleteEvent(DispatchEvent):
    NAME = "MESSAGE_DELETE"

    def __init__(self, message_id: int, channel_id: int, guild_id: int):
        self.message_id = message_id
        self.channel_id = channel_id
        self.guild_id = guild_id

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.message_id),
                "channel_id": str(self.channel_id)
            }
        }
        if self.guild_id is not None:
            data["d"]["guild_id"] = str(self.guild_id)
        return data


class MessageAckEvent(DispatchEvent):
    NAME = "MESSAGE_ACK"

    def __init__(self, ack_object: dict):
        self.ack_object = ack_object

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.ack_object
        }


class ChannelRecipientAddEvent(DispatchEvent):
    NAME = "CHANNEL_RECIPIENT_ADD"

    def __init__(self, channel_id: int, user_obj: dict):
        self.channel_id = channel_id
        self.user_obj = user_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "user": self.user_obj,
                "channel_id": str(self.channel_id)
            }
        }


class ChannelRecipientRemoveEvent(ChannelRecipientAddEvent):
    NAME = "CHANNEL_RECIPIENT_REMOVE"


class DMChannelDeleteEvent(DispatchEvent):
    NAME = "CHANNEL_DELETE"

    def __init__(self, channel_obj: dict):
        self.channel_obj = channel_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.channel_obj
        }


class ChannelPinsUpdateEvent(DispatchEvent):
    NAME = "CHANNEL_PINS_UPDATE"

    def __init__(self, channel_id: int, last_pin_timestamp: str):
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

    def __init__(self, user_id: int, message_id: int, channel_id: int, emoji: dict):
        self.user_id = user_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.emoji = emoji
        if isinstance(emoji["emoji"], Emoji):
            emoji["emoji_id"] = emoji["emoji"].id
        else:
            emoji["emoji_id"] = emoji["emoji"]
        del emoji["emoji"]

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

    def __init__(self, guild_obj: dict):
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

    def __init__(self, guild_id: int):
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

    def __init__(self, members: List[GuildMember], total_members: int, statuses: dict, guild_id: int):
        self.members = members
        self.total_members = total_members
        self.statuses = statuses
        self.groups = {}
        for s in statuses.values():
            if s.public_status not in self.groups:
                self.groups[s.public_status] = 0
            self.groups[s.public_status] += 1
        self.guild_id = guild_id

    # noinspection PyShadowingNames
    async def json(self) -> dict:
        groups = [{"id": status, "count": count} for status, count in self.groups.items()]
        items = []
        for mem in self.members:
            m = await mem.ds_json()
            m["presence"] = {
                "user": {"id": str(mem.user.id)},
                "status": self.statuses[mem.user.id].public_status,
                "client_status": {} if self.statuses[mem.user.id].public_status == "offline" else {
                    "desktop": self.statuses[mem.user.id].public_status
                },
                "activities": self.statuses[mem.user.id].activities
            }
            items.append({"member": m})
        items.sort(key=lambda i: i["member"]["presence"]["status"])
        _ls = None
        _ins: dict = {}
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

    def __init__(self, user_id: int, note: str):
        self.user_id = user_id
        self.note = note

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.user_id),
                "note": self.note
            }
        }


class UserSettingsProtoUpdateEvent(DispatchEvent):
    NAME = "USER_SETTINGS_PROTO_UPDATE"

    def __init__(self, proto: str, type_: int):
        self.proto = proto
        self.type = type_

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

    def __init__(self, guild_id: int, emojis: list[dict]):
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

    def __init__(self, channel_obj: dict):
        self.channel_obj = channel_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.channel_obj
        }


class ChannelCreateEvent(ChannelUpdateEvent):
    NAME = "CHANNEL_CREATE"


class ChannelDeleteEvent(ChannelUpdateEvent):
    NAME = "CHANNEL_DELETE"


class InviteDeleteEvent(DispatchEvent):
    NAME = "INVITE_DELETE"

    def __init__(self, invite: Invite):
        self.invite = invite

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": str(self.invite.channel.guild.id) if self.invite.channel.guild is not None else None,
                "code": self.invite.code,
                "channel_id": str(self.invite.channel.id)
            }
        }
        return data


class GuildMemberRemoveEvent(DispatchEvent):
    NAME = "GUILD_MEMBER_REMOVE"

    def __init__(self, guild_id: int, user_obj: dict):
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

    def __init__(self, guild_id: int, user_obj: dict):
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

    def __init__(self, guild_id: int, channel_id: int, message_ids: list[int]):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_ids = message_ids

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "ids": [str(message_id) for message_id in self.message_ids],
                "guild_id": str(self.guild_id),
                "channel_id": str(self.channel_id)
            }
        }
        return data


class GuildRoleCreateEvent(DispatchEvent):
    NAME = "GUILD_ROLE_CREATE"

    def __init__(self, guild_id: int, role_obj: dict):
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

    def __init__(self, guild_id: int, role_id: int):
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

    def __init__(self, guild_id: int, member_obj: dict):
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

    def __init__(self, members: List[GuildMember], presences: list, guild_id: int):
        self.members = members
        self.presences = presences
        self.guild_id = guild_id

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "members": [await member.ds_json() for member in self.members],
                "presences": self.presences,
                "chunk_index": 0,
                "chunk_count": 1,
                "guild_id": str(self.guild_id)
            }
        }
        return data


class GuildAuditLogEntryCreateEvent(DispatchEvent):
    NAME = "GUILD_AUDIT_LOG_ENTRY_CREATE"

    def __init__(self, entry_obj: dict):
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

    def __init__(self, guild_id: int, channel_id: int):
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

    def __init__(self, guild_id: int, stickers: list[dict]):
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

    def __init__(self, event_obj: dict):
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

    def __init__(self, user_id: int, event_id: int, guild_id: int):
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


class ThreadCreateEvent(DispatchEvent):
    NAME = "THREAD_CREATE"

    def __init__(self, thread_obj: dict):
        self.thread_obj = thread_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.thread_obj
        }


class ThreadMemberUpdateEvent(DispatchEvent):
    NAME = "THREAD_MEMBER_UPDATE"

    def __init__(self, member_obj: dict):
        self.member_obj = member_obj

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": self.member_obj
        }


class IntegrationCreateEvent(DispatchEvent):
    NAME = "INTEGRATION_CREATE"

    def __init__(self, integration: Integration):
        self.integration = integration

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": await self.integration.ds_json(with_user=False, with_guild_id=True)
        }


class IntegrationDeleteEvent(DispatchEvent):
    NAME = "INTEGRATION_DELETE"

    def __init__(self, guild_id: int, application_id: int):
        self.guild_id = guild_id
        self.application_id = application_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.application_id),
                "application_id": str(self.application_id),
                "guild_id": self.guild_id
            }
        }


class GuildIntegrationsUpdateEvent(DispatchEvent):
    NAME = "GUILD_INTEGRATIONS_UPDATE"

    def __init__(self, guild_id: int):
        self.guild_id = guild_id

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "guild_id": self.guild_id,
            }
        }


class InteractionCreateEvent(DispatchEvent):
    NAME = "INTERACTION_CREATE"

    def __init__(self, interaction: Interaction, full: bool, **interaction_kwargs):
        self.interaction = interaction
        self.full = full
        self.interaction_kwargs = interaction_kwargs

    async def json(self) -> dict:
        data = {
            "t": self.NAME,
            "op": self.OP,
        }
        if not self.full:
            return data | {"d": {
                "nonce": str(self.interaction.nonce) if self.interaction.nonce is not None else None,
                "id": str(self.interaction.nonce),
            }}

        return data | {"d": await self.interaction.ds_json(with_token=True, **self.interaction_kwargs)}


class InteractionSuccessEvent(DispatchEvent):
    NAME = "INTERACTION_SUCCESS"

    def __init__(self, interaction: Interaction):
        self.interaction = interaction

    async def json(self) -> dict:
        return {
            "t": self.NAME,
            "op": self.OP,
            "d": {
                "id": str(self.interaction.nonce),
                "nonce": str(self.interaction.nonce) if self.interaction.nonce is not None else None,
            },
        }


class InteractionFailureEvent(InteractionSuccessEvent):
    NAME = "INTERACTION_FAILURE"


