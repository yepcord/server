from datetime import datetime
from .utils import snowflake_timestamp
from .enums import ChannelType


async def userSettingsResponse(user):
    settings = await user.settings
    if settings.status == "offline":
        settings.status = "invisible"
    return {
        "locale": settings.locale,
        "show_current_game": settings.show_current_game,
        "restricted_guilds": settings.restricted_guilds,
        "default_guilds_restricted": settings.default_guilds_restricted,
        "inline_attachment_media": settings.inline_attachment_media,
        "inline_embed_media": settings.inline_attachment_media,
        "gif_auto_play": settings.gif_auto_play,
        "render_embeds": settings.render_embeds,
        "render_reactions": settings.render_reactions,
        "animate_emoji": settings.animate_emoji,
        "enable_tts_command": settings.enable_tts_command,
        "message_display_compact": settings.message_display_compact,
        "convert_emoticons": settings.convert_emoticons,
        "explicit_content_filter": settings.explicit_content_filter,
        "disable_games_tab": settings.disable_games_tab,
        "theme": settings.theme,
        "developer_mode": settings.developer_mode,
        "guild_positions": settings.guild_positions,
        "detect_platform_accounts": settings.detect_platform_accounts,
        "status": settings.status,
        "afk_timeout": settings.afk_timeout,
        "timezone_offset": settings.timezone_offset,
        "stream_notifications_enabled": settings.stream_notifications_enabled,
        "allow_accessibility_detection": settings.allow_accessibility_detection,
        "contact_sync_enabled": settings.contact_sync_enabled,
        "native_phone_integration_enabled": settings.native_phone_integration_enabled,
        "animate_stickers": settings.animate_stickers,
        "friend_discovery_flags": settings.friend_discovery_flags,
        "view_nsfw_guilds": settings.view_nsfw_guilds,
        "view_nsfw_commands": settings.view_nsfw_commands,
        "passwordless": settings.passwordless,
        "friend_source_flags": settings.friend_source_flags,
        "guild_folders": settings.guild_folders,
        "custom_status": settings.custom_status,
        "activity_restricted_guild_ids": settings.activity_restricted_guild_ids
    }


async def userdataResponse(user):
    data = await user.data
    settings = await user.settings
    return {
        "id": str(user.id),
        "username": data.username,
        "avatar": data.avatar,
        "avatar_decoration": data.avatar_decoration,
        "discriminator": data.s_discriminator,
        "public_flags": data.public_flags,
        "flags": data.flags,
        "banner": data.banner,
        "banner_color": data.banner_color,
        "accent_color": data.accent_color,
        "bio": data.bio,
        "locale": settings.locale,
        "nsfw_allowed": True,  # TODO: get from age
        "mfa_enabled": settings.mfa,
        "email": user.email,
        "verified": True,
        "phone": data.phone
    }


async def userConsentResponse(user):
    settings = await user.settings
    return {
        "personalization": {
            "consented": settings.personalization
        },
        "usage_statistics": {
            "consented": settings.usage_statistics
        }
    }


async def userProfileResponse(user):
    data = await user.data
    s = snowflake_timestamp(user.id)
    d = datetime.utcfromtimestamp(int(s/1000)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "user": {
            "id": str(user.id),
            "username": data.username,
            "avatar": data.avatar,
            "avatar_decoration": data.avatar_decoration,
            "discriminator": data.s_discriminator,
            "public_flags": data.public_flags,
            "flags": data.flags,
            "banner": data.banner,
            "banner_color": data.banner_color,
            "accent_color": data.accent_color,
            "bio": data.bio
        },
        "connected_accounts": [],  # TODO
        "premium_since": d,
        "premium_guild_since": s,
        "user_profile": {
            "bio": data.bio,
            "accent_color": data.accent_color
        }
    }


async def channelInfoResponse(channel, user, ids=True):
    _recipients = channel.recipients.copy()
    _recipients.remove(user.id)
    recipients = _recipients
    if not ids:
        recipients = []
        for u in _recipients:
            u = await channel._core.getUser(u)
            data = await u.data
            recipients.append({
                "id": str(u.id),
                "username": data.username,
                "avatar": data.avatar,
                "avatar_decoration": data.avatar_decoration,
                "discriminator": data.s_discriminator,
                "public_flags": data.public_flags
            })
    if channel.type == ChannelType.DM:
        return {
            "type": channel.type,
            "recipient_ids" if ids else "recipients": recipients,
            "last_message_id": channel.last_message_id,
            "id": str(channel.id)
        }
    elif channel.type == ChannelType.GROUP_DM:
        j = {
            "type": channel.type,
            "recipient_ids" if ids else "recipients": recipients,
            "last_message_id": channel.last_message_id,
            "id": str(channel.id),
            "owner_id": str(channel.owner_id),
            "name": channel.name,
            "icon": channel.icon
        }