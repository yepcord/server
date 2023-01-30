from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums import ChannelType

if TYPE_CHECKING:
    from ..classes.channel import Channel

async def discord_Channel(channel: Channel) -> dict:
    if channel.type == ChannelType.GUILD_CATEGORY:
        return {
            "type": channel.type,
            "position": channel.position,
            "permission_overwrites": channel.permission_overwrites,
            "name": channel.name,
            "id": str(channel.id),
            "flags": channel.flags
        }
    elif channel.type == ChannelType.GUILD_TEXT:
        return {
            "type": channel.type,
            "topic": channel.topic,
            "rate_limit_per_user": channel.rate_limit,
            "position": channel.position,
            "permission_overwrites": channel.permission_overwrites,
            "parent_id": str(channel.parent_id),
            "name": channel.name,
            "last_message_id": channel.last_message_id,
            "id": str(channel.id),
            "flags": channel.flags
        }
    elif channel.type == ChannelType.GUILD_VOICE:
        return {
            "user_limit": channel.user_limit,
            "type": channel.type,
            "rtc_region": channel.rtc_region,
            "rate_limit_per_user": channel.rate_limit,
            "position": channel.position,
            "permission_overwrites": channel.permission_overwrites,
            "parent_id": str(channel.parent_id),
            "name": channel.name,
            "last_message_id": channel.last_message_id,
            "id": str(channel.id),
            "flags": channel.flags,
            "bitrate": channel.bitrate
        }