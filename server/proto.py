from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Dict

def stub(cls):
    def _init(self, *args, **kwargs):
        raise RuntimeError
    cls.__init__ = _init
    return cls

@dataclass
@stub
class Version:
    client_version: Optional[int]
    server_version: Optional[int]
    data_version: Optional[int]

class InboxTab(IntEnum):
    UNSPECIFIED = 0
    MENTIONS = 1
    UNREADS = 2

@dataclass
@stub
class InboxSettings:
    current_tab: Optional[InboxTab]
    viewed_tutorial: Optional[bool]

@dataclass
@stub
class ChannelSettings:
    collapsed_in_inbox: Optional[bool]

@dataclass
@stub
class GuildSettings:
    channels: Dict[int, ChannelSettings]
    hub_progress: Optional[int]
    guild_onboarding_progress: Optional[int]

@dataclass
@stub
class LastDismissedOutboundPromotionStartDate:
    value: Optional[str]

@dataclass
@stub
class PremiumTier0ModalDismissedAt:
    timestamp: Optional[int]

@dataclass
@stub
class UserContentSettings:
    dismissed_contents: Optional[bytes]
    last_dismissed_outbound_promotion_start_date: Optional[LastDismissedOutboundPromotionStartDate]
    premium_tier_0_modal_dismissed_at: Optional[PremiumTier0ModalDismissedAt]

@dataclass
@stub
class VideoFilterBackgroundBlur:
    use_blur: Optional[bool]

@dataclass
@stub
class VideoFilterAsset:
    id: Optional[int]
    asset_hash: Optional[str]

@dataclass
@stub
class AlwaysPreviewVideo:
    value: Optional[bool]

@dataclass
@stub
class AfkTimeout:
    value: Optional[int]

@dataclass
@stub
class StreamNotificationsEnabled:
    value: Optional[bool]

@dataclass
@stub
class NativePhoneIntegrationEnabled:
    value: Optional[bool]

@dataclass
@stub
class VoiceAndVideoSettings:
    blur: Optional[VideoFilterBackgroundBlur]
    preset_option: Optional[int]
    custom_asset: Optional[VideoFilterAsset]
    always_preview_video: Optional[AlwaysPreviewVideo]
    afk_timeout: Optional[AfkTimeout]
    stream_notifications_enabled: Optional[StreamNotificationsEnabled]
    native_phone_integration_enabled: Optional[NativePhoneIntegrationEnabled]

@dataclass
@stub
class DiversitySurrogate:
    value: Optional[str]

@dataclass
@stub
class UseRichChatInput:
    value: Optional[bool]

@dataclass
@stub
class UseThreadSidebar:
    value: Optional[bool]

@dataclass
@stub
class RenderSpoilers:
    value: Optional[str]

@dataclass
@stub
class ViewImageDescriptions:
    value: Optional[bool]

@dataclass
@stub
class ShowCommandSuggestions:
    value: Optional[bool]

@dataclass
@stub
class InlineAttachmentMedia:
    value: Optional[bool]

@dataclass
@stub
class InlineEmbedMedia:
    value: Optional[bool]

@dataclass
@stub
class GifAutoPlay:
    value: Optional[bool]

@dataclass
@stub
class RenderEmbeds:
    value: Optional[bool]

@dataclass
@stub
class RenderReactions:
    value: Optional[bool]

@dataclass
@stub
class AnimateEmoji:
    value: Optional[bool]

@dataclass
@stub
class AnimateStickers:
    value: Optional[int]

@dataclass
@stub
class EnableTtsCommand:
    value: Optional[bool]

@dataclass
@stub
class MessageDisplayCompact:
    value: Optional[bool]

@dataclass
@stub
class ExplicitContentFilter:
    value: Optional[int]

@dataclass
@stub
class ViewNsfwGuilds:
    value: Optional[bool]

@dataclass
@stub
class ConvertEmoticons:
    value: Optional[bool]

@dataclass
@stub
class ExpressionSuggestionsEnabled:
    value: Optional[bool]

@dataclass
@stub
class ViewNsfwCommands:
    value: Optional[bool]

@dataclass
@stub
class TextAndImagesSettings:
    diversity_surrogate: Optional[DiversitySurrogate]
    use_rich_chat_input: Optional[UseRichChatInput]
    use_thread_sidebar: Optional[UseThreadSidebar]
    render_spoilers: Optional[RenderSpoilers]
    emoji_picker_collapsed_sections: Optional[List[str]]
    sticker_picker_collapsed_sections: Optional[List[str]]
    view_image_descriptions: Optional[ViewImageDescriptions]
    show_command_suggestions: Optional[ShowCommandSuggestions]
    inline_attachment_media: Optional[InlineAttachmentMedia]
    inline_embed_media: Optional[InlineEmbedMedia]
    gif_auto_play: Optional[GifAutoPlay]
    render_embeds: Optional[RenderEmbeds]
    render_reactions: Optional[RenderReactions]
    animate_emoji: Optional[AnimateEmoji]
    animate_stickers: Optional[AnimateStickers]
    enable_tts_command: Optional[EnableTtsCommand]
    message_display_compact: Optional[MessageDisplayCompact]
    explicit_content_filter: Optional[ExplicitContentFilter]
    view_nsfw_guilds: Optional[ViewNsfwGuilds]
    convert_emoticons: Optional[ConvertEmoticons]
    expression_suggestions_enabled: Optional[ExpressionSuggestionsEnabled]
    view_nsfw_commands: Optional[ViewNsfwCommands]

@dataclass
@stub
class ShowInAppNotifications:
    value: Optional[bool]

@dataclass
@stub
class NotifyFriendsOnGoLive:
    value: Optional[bool]

@dataclass
@stub
class NotificationSettings:
    show_in_app_notifications: Optional[ShowInAppNotifications]
    notify_friends_on_go_live: Optional[NotifyFriendsOnGoLive]
    notification_center_acked_before_id: Optional[int]

class GuildActivityStatusRestrictionDefault(IntEnum):
    OFF = 0
    ON_FOR_LARGE_GUILDS = 1

@dataclass
@stub
class AllowActivityPartyPrivacyFriends:
    value: Optional[bool]

@dataclass
@stub
class AllowActivityPartyPrivacyVoiceChannel:
    value: Optional[bool]

@dataclass
@stub
class DetectPlatformAccounts:
    value: Optional[bool]

@dataclass
@stub
class Passwordless:
    value: Optional[bool]

@dataclass
@stub
class ContactSyncEnabled:
    value: Optional[bool]

@dataclass
@stub
class FriendSourceFlags:
    value: Optional[int]

@dataclass
@stub
class FriendDiscoveryFlags:
    value: Optional[int]

@dataclass
@stub
class PrivacySettings:
    allow_activity_party_privacy_friends: Optional[AllowActivityPartyPrivacyFriends]
    allow_activity_party_privacy_voice_channel: Optional[AllowActivityPartyPrivacyVoiceChannel]
    restricted_guild_ids: Optional[List[int]]
    default_guilds_restricted: Optional[bool]
    allow_accessibility_detection: Optional[bool]
    detect_platform_accounts: Optional[DetectPlatformAccounts]
    passwordless: Optional[Passwordless]
    contact_sync_enabled: Optional[ContactSyncEnabled]
    friend_source_flags: Optional[FriendSourceFlags]
    friend_discovery_flags: Optional[FriendDiscoveryFlags]
    activity_restricted_guild_ids: Optional[List[int]]
    default_guilds_activity_restricted: Optional[GuildActivityStatusRestrictionDefault]
    activity_joining_restricted_guild_ids: Optional[List[int]]

@dataclass
@stub
class RtcPanelShowVoiceStates:
    value: Optional[bool]

@dataclass
@stub
class DebugSettings:
    rtc_panel_show_voice_states: Optional[RtcPanelShowVoiceStates]

@dataclass
@stub
class InstallShortcutDesktop:
    value: Optional[bool]

@dataclass
@stub
class InstallShortcutStartMenu:
    value: Optional[bool]

@dataclass
@stub
class DisableGamesTab:
    value: Optional[bool]

@dataclass
@stub
class GameLibrarySettings:
    install_shortcut_desktop: Optional[InstallShortcutDesktop]
    install_shortcut_start_menu: Optional[InstallShortcutStartMenu]
    disable_games_tab: Optional[DisableGamesTab]

@dataclass
@stub
class Status:
    status: Optional[str]

@dataclass
@stub
class CustomStatus:
    text: Optional[str]
    emoji_id: Optional[int]
    emoji_name: Optional[str]
    expires_at_ms: Optional[int]

@dataclass
@stub
class ShowCurrentGame:
    value: Optional[bool]

@dataclass
@stub
class StatusSettings:
    status: Optional[Status]
    custom_status: Optional[CustomStatus]
    show_current_game: Optional[ShowCurrentGame]

@dataclass
@stub
class Locale:
    locale_code: Optional[str]

@dataclass
@stub
class TimezoneOffset:
    offset: Optional[int]

@dataclass
@stub
class LocalizationSettings:
    locale: Optional[Locale]
    timezone_offset: Optional[TimezoneOffset]

class Theme(IntEnum):
    UNSET = 0
    DARK = 1
    LIGHT = 2

@dataclass
@stub
class AppearanceSettings:
    theme: Optional[Theme]
    developer_mode: Optional[bool]

@dataclass
@stub
class PreloadedUserSettings:
    versions: Optional[Version]
    inbox: Optional[InboxSettings]
    guilds: Optional[GuildSettings]
    user_content: Optional[UserContentSettings]
    voice_and_video: Optional[VoiceAndVideoSettings]
    text_and_images: Optional[TextAndImagesSettings]
    notifications: Optional[NotificationSettings]
    privacy: Optional[PrivacySettings]
    debug: Optional[DebugSettings]
    game_library: Optional[GameLibrarySettings]
    status: Optional[StatusSettings]
    localization: Optional[LocalizationSettings]
    appearance: Optional[AppearanceSettings]

from .discord_pb2 import *