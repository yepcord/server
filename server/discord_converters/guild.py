from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING

from server.classes.user import UserId
from server.ctx import getCore, Ctx
from server.enums import ChannelType
from server.utils import snowflake_timestamp, b64encode, int_length, sf_ts

if TYPE_CHECKING:
    from server.classes.guild import Guild, Role, Invite


async def discord_Guild(guild: Guild) -> dict:
    data = {
        "id": str(guild.id),
        "name": guild.name,
        "icon": guild.icon,
        "description": guild.description,
        "splash": guild.splash,
        "discovery_splash": guild.discovery_splash,
        "features": guild.features,
        "emojis": [
            await emoji.json for emoji in await getCore().getEmojis(guild.id) # Get json for every emoji in guild
        ],
        "stickers": guild.stickers,
        "banner": guild.banner,
        "owner_id": str(guild.owner_id),
        "application_id": None,  # TODO
        "region": guild.region,
        "afk_channel_id": guild.afk_channel_id,
        "afk_timeout": guild.afk_timeout,
        "system_channel_id": str(guild.system_channel_id),
        "widget_enabled": False,  # TODO
        "widget_channel_id": None,  # TODO
        "verification_level": guild.verification_level,
        "roles": [
            await role.json for role in await getCore().getRoles(guild) # Get json for every role in guild
        ],
        "default_message_notifications": guild.default_message_notifications,
        "mfa_level": guild.mfa_level,
        "explicit_content_filter": guild.explicit_content_filter,
        # "max_presences": None, # TODO
        "max_members": guild.max_members,
        "max_stage_video_channel_users": 0,  # TODO
        "max_video_channel_users": 0,  # TODO
        "vanity_url_code": guild.vanity_url_code,
        "premium_tier": 3,  # TODO
        "premium_subscription_count": 30,  # TODO
        "system_channel_flags": guild.system_channel_flags,
        "preferred_locale": guild.preferred_locale,
        "rules_channel_id": None,  # TODO
        "public_updates_channel_id": None,  # TODO
        "hub_type": None,  # TODO
        "premium_progress_bar_enabled": bool(guild.premium_progress_bar_enabled),
        "nsfw": bool(guild.nsfw),
        "nsfw_level": guild.nsfw_level,
        "threads": [],  # TODO
        "guild_scheduled_events": [],  # TODO
        "stage_instances": [],  # TODO
        "application_command_counts": {},  # TODO
        "large": False,  # TODO
        "lazy": True,  # TODO
        "member_count": await getCore().getGuildMemberCount(guild),
    }
    if uid := Ctx.get("user_id"):
        joined_at = (await getCore().getGuildMember(guild, uid)).joined_at
        timestamp = int(snowflake_timestamp(joined_at) / 1000)
        data["joined_at"] = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00")
    if Ctx.get("with_members"):
        data["members"] = [await member.json for member in await getCore().getGuildMembers(guild)]
    if Ctx.get("with_channels"):
        data["channels"] = [await channel.json for channel in await getCore().getGuildChannels(guild)]
    return data


async def discord_Role(role: Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "permissions": str(role.permissions),
        "position": role.position,
        "color": role.color,
        "hoist": bool(role.hoist),
        "managed": bool(role.managed),
        "mentionable": bool(role.mentionable),
        "icon": role.icon,
        "unicode_emoji": role.unicode_emoji,
        "flags": role.flags
    }

async def discord_Emoji(emoji: Emoji) -> dict:
    data = {
        "name": emoji.name,
        "roles": emoji.roles,
        "id": str(emoji.id),
        "require_colons": bool(emoji.require_colons),
        "managed": bool(emoji.managed),
        "animated": bool(emoji.animated),
        "available": bool(emoji.available)
    }
    if Ctx.get("with_user"):
        user = await getCore().getUserData(UserId(emoji.user_id))
        data["user"] = {
            "id": str(emoji.user_id),
            "username": user.username,
            "avatar": user.avatar,
            "avatar_decoration": user.avatar_decoration,
            "discriminator": user.s_discriminator,
            "public_flags": user.public_flags
        }
    return data

async def discord_Invite(invite: Invite) -> dict:
    userdata = await getCore().getUserData(UserId(invite.inviter))
    created_timestamp = int(sf_ts(invite.id) / 1000)
    channel = await getCore().getChannel(invite.channel_id)
    data = {
        "code": b64encode(invite.id.to_bytes(int_length(invite.id), 'big')),
        "inviter": await userdata.json,
        "created_at": datetime.utcfromtimestamp(created_timestamp).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "expires_at": datetime.utcfromtimestamp(created_timestamp+invite.max_age).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "type": invite.type,
        "channel": {
            "id": str(channel.id),
            "type": channel.type
        },
        "max_age": invite.max_age,
    }
    if channel.type == ChannelType.GROUP_DM:
        data["channel"].update({"name": channel.name, "icon": channel.icon})
    if Ctx.get("with_counts"):
        related_users = await getCore().getRelatedUsersToChannel(invite.channel_id)
        data["approximate_member_count"] = len(related_users)
        if channel.type == ChannelType.GROUP_DM:
            data["channel"]["recipients"] = [
                {"username": (await getCore().getUserData(UserId(i))).username}
                for i in related_users
            ]
    # TODO: add guild field
    return data