from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

from pure_protobuf.dataclasses_ import message, field as _field
from pure_protobuf.types import uint32, fixed64, int32, sint32, uint64


def field(num, *args, **kwargs):
    if "default_factory" not in kwargs:
        kwargs["default"] = None
    return _field(num, *args, **kwargs)

@message
@dataclass
class Version:
    client_version: Optional[uint32] = field(1)
    server_version: Optional[uint32] = field(2)
    data_version: Optional[uint32] = field(3)

class InboxTab(IntEnum):
    UNSPECIFIED = 0
    MENTIONS = 1
    UNREADS = 2

@message
@dataclass
class InboxSettings:
    current_tab: Optional[InboxTab] = field(1)
    viewed_tutorial: Optional[bool] = field(2)

@message
@dataclass
class ChannelSettings:
    collapsed_in_inbox: Optional[bool] = field(1)

@message
@dataclass
class GuildSettings:
    #channels: Dict[fixed64, ChannelSettings] = field(1)
    channels: Optional[str] = field(1)
    hub_progress: Optional[uint32] = field(2)
    guild_onboarding_progress: Optional[uint32] = field(3)

@message
@dataclass
class LastDismissedOutboundPromotionStartDate:
    value: Optional[str] = field(1)

@message
@dataclass
class PremiumTier0ModalDismissedAt:
    timestamp: Optional[uint32] = field(1)

@message
@dataclass
class UserContentSettings:
    dismissed_contents: Optional[bytes] = field(1)
    last_dismissed_outbound_promotion_start_date: Optional[LastDismissedOutboundPromotionStartDate] = field(2, default_factory=LastDismissedOutboundPromotionStartDate)
    premium_tier_0_modal_dismissed_at: Optional[PremiumTier0ModalDismissedAt] = field(3, default_factory=PremiumTier0ModalDismissedAt)

@message
@dataclass
class VideoFilterBackgroundBlur:
    use_blur: Optional[bool] = field(1)

@message
@dataclass
class VideoFilterAsset:
    id: Optional[fixed64] = field(1)
    asset_hash: Optional[str] = field(2)

@message
@dataclass
class AlwaysPreviewVideo:
    value: Optional[bool] = field(1)

@message
@dataclass
class AfkTimeout:
    value: Optional[uint32] = field(1)

@message
@dataclass
class StreamNotificationsEnabled:
    value: Optional[bool] = field(1)

@message
@dataclass
class NativePhoneIntegrationEnabled:
    value: Optional[bool] = field(1)

@message
@dataclass
class VoiceAndVideoSettings:
    blur: Optional[VideoFilterBackgroundBlur] = field(1, default_factory=VideoFilterBackgroundBlur)
    preset_option: Optional[uint32] = field(2)
    custom_asset: Optional[VideoFilterAsset] = field(3, default_factory=VideoFilterAsset)
    always_preview_video: Optional[AlwaysPreviewVideo] = field(5, default_factory=AlwaysPreviewVideo)
    afk_timeout: Optional[AfkTimeout] = field(6, default_factory=AfkTimeout)
    stream_notifications_enabled: Optional[StreamNotificationsEnabled] = field(7, default_factory=StreamNotificationsEnabled)
    native_phone_integration_enabled: Optional[NativePhoneIntegrationEnabled] = field(8, default_factory=NativePhoneIntegrationEnabled)

@message
@dataclass
class DiversitySurrogate:
    value: Optional[str] = field(1)

@message
@dataclass
class UseRichChatInput:
    value: Optional[bool] = field(1)

@message
@dataclass
class UseThreadSidebar:
    value: Optional[bool] = field(1)

@message
@dataclass
class RenderSpoilers:
    value: Optional[str] = field(1)

@message
@dataclass
class ViewImageDescriptions:
    value: Optional[bool] = field(1)

@message
@dataclass
class ShowCommandSuggestions:
    value: Optional[bool] = field(1)

@message
@dataclass
class InlineAttachmentMedia:
    value: Optional[bool] = field(1)

@message
@dataclass
class InlineEmbedMedia:
    value: Optional[bool] = field(1)

@message
@dataclass
class GifAutoPlay:
    value: Optional[bool] = field(1)

@message
@dataclass
class RenderEmbeds:
    value: Optional[bool] = field(1)

@message
@dataclass
class RenderReactions:
    value: Optional[bool] = field(1)

@message
@dataclass
class AnimateEmoji:
    value: Optional[bool] = field(1)

@message
@dataclass
class AnimateStickers:
    value: Optional[uint32] = field(1)

@message
@dataclass
class EnableTtsCommand:
    value: Optional[bool] = field(1)

@message
@dataclass
class MessageDisplayCompact:
    value: Optional[bool] = field(1)

@message
@dataclass
class ExplicitContentFilter:
    value: Optional[uint32] = field(1)

@message
@dataclass
class ViewNsfwGuilds:
    value: Optional[bool] = field(1)

@message
@dataclass
class ConvertEmoticons:
    value: Optional[bool] = field(1)

@message
@dataclass
class ExpressionSuggestionsEnabled:
    value: Optional[bool] = field(1)

@message
@dataclass
class ViewNsfwCommands:
    value: Optional[bool] = field(1)

@message
@dataclass
class TextAndImagesSettings:
    diversity_surrogate: Optional[DiversitySurrogate] = field(1, default_factory=DiversitySurrogate)
    use_rich_chat_input: Optional[UseRichChatInput] = field(2, default_factory=UseRichChatInput)
    use_thread_sidebar: Optional[UseThreadSidebar] = field(3, default_factory=UseThreadSidebar)
    render_spoilers: Optional[RenderSpoilers] = field(4, default_factory=RenderSpoilers)
    emoji_picker_collapsed_sections: Optional[List[str]] = field(5, default_factory=list)
    sticker_picker_collapsed_sections: Optional[List[str]] = field(6, default_factory=list)
    view_image_descriptions: Optional[ViewImageDescriptions] = field(7, default_factory=ViewImageDescriptions)
    show_command_suggestions: Optional[ShowCommandSuggestions] = field(8, default_factory=ShowCommandSuggestions)
    inline_attachment_media: Optional[InlineAttachmentMedia] = field(9, default_factory=InlineAttachmentMedia)
    inline_embed_media: Optional[InlineEmbedMedia] = field(10, default_factory=InlineEmbedMedia)
    gif_auto_play: Optional[GifAutoPlay] = field(11, default_factory=GifAutoPlay)
    render_embeds: Optional[RenderEmbeds] = field(12, default_factory=RenderEmbeds)
    render_reactions: Optional[RenderReactions] = field(13, default_factory=RenderReactions)
    animate_emoji: Optional[AnimateEmoji] = field(14, default_factory=AnimateEmoji)
    animate_stickers: Optional[AnimateStickers] = field(15, default_factory=AnimateStickers)
    enable_tts_command: Optional[EnableTtsCommand] = field(16, default_factory=EnableTtsCommand)
    message_display_compact: Optional[MessageDisplayCompact] = field(17, default_factory=MessageDisplayCompact)
    explicit_content_filter: Optional[ExplicitContentFilter] = field(19, default_factory=ExplicitContentFilter)
    view_nsfw_guilds: Optional[ViewNsfwGuilds] = field(20, default_factory=ViewNsfwGuilds)
    convert_emoticons: Optional[ConvertEmoticons] = field(21, default_factory=ConvertEmoticons)
    expression_suggestions_enabled: Optional[ExpressionSuggestionsEnabled] = field(22, default_factory=ExpressionSuggestionsEnabled)
    view_nsfw_commands: Optional[ViewNsfwCommands] = field(23, default_factory=ViewNsfwCommands)

@message
@dataclass
class ShowInAppNotifications:
    value: Optional[bool] = field(1)

@message
@dataclass
class NotifyFriendsOnGoLive:
    value: Optional[bool] = field(1)

@message
@dataclass
class NotificationSettings:
    show_in_app_notifications: Optional[ShowInAppNotifications] = field(1, default_factory=ShowInAppNotifications)
    notify_friends_on_go_live: Optional[NotifyFriendsOnGoLive] = field(2, default_factory=NotifyFriendsOnGoLive)
    notification_center_acked_before_id: Optional[fixed64] = field(3)

class GuildActivityStatusRestrictionDefault(IntEnum):
    OFF = 0
    ON_FOR_LARGE_GUILDS = 1

@message
@dataclass
class AllowActivityPartyPrivacyFriends:
    value: Optional[bool] = field(1)

@message
@dataclass
class AllowActivityPartyPrivacyVoiceChannel:
    value: Optional[bool] = field(1)

@message
@dataclass
class DetectPlatformAccounts:
    value: Optional[bool] = field(1)

@message
@dataclass
class Passwordless:
    value: Optional[bool] = field(1)

@message
@dataclass
class ContactSyncEnabled:
    value: Optional[bool] = field(1)

@message
@dataclass
class FriendSourceFlags:
    value: Optional[uint32] = field(1)

@message
@dataclass
class FriendDiscoveryFlags:
    value: Optional[uint32] = field(1)

@message
@dataclass
class PrivacySettings:
    allow_activity_party_privacy_friends: Optional[AllowActivityPartyPrivacyFriends] = field(1, default_factory=AllowActivityPartyPrivacyFriends)
    allow_activity_party_privacy_voice_channel: Optional[AllowActivityPartyPrivacyVoiceChannel] = field(2, default_factory=AllowActivityPartyPrivacyVoiceChannel)
    restricted_guild_ids: Optional[List[fixed64]] = field(3, default_factory=list)
    default_guilds_restricted: Optional[bool] = field(4)
    allow_accessibility_detection: Optional[bool] = field(7)
    detect_platform_accounts: Optional[DetectPlatformAccounts] = field(8, default_factory=DetectPlatformAccounts)
    passwordless: Optional[Passwordless] = field(9, default_factory=Passwordless)
    contact_sync_enabled: Optional[ContactSyncEnabled] = field(10, default_factory=ContactSyncEnabled)
    friend_source_flags: Optional[FriendSourceFlags] = field(11, default_factory=FriendSourceFlags)
    friend_discovery_flags: Optional[FriendDiscoveryFlags] = field(12, default_factory=FriendDiscoveryFlags)
    activity_restricted_guild_ids: Optional[List[fixed64]] = field(13, default_factory=list)
    default_guilds_activity_restricted: Optional[GuildActivityStatusRestrictionDefault] = field(14)
    activity_joining_restricted_guild_ids: Optional[List[fixed64]] = field(15, default_factory=list)

@message
@dataclass
class RtcPanelShowVoiceStates:
    value: Optional[bool] = field(1)

@message
@dataclass
class DebugSettings:
    rtc_panel_show_voice_states: Optional[RtcPanelShowVoiceStates] = field(1, default_factory=RtcPanelShowVoiceStates)

@message
@dataclass
class InstallShortcutDesktop:
    value: Optional[bool] = field(1)

@message
@dataclass
class InstallShortcutStartMenu:
    value: Optional[bool] = field(1)

@message
@dataclass
class DisableGamesTab:
    value: Optional[bool] = field(1)

@message
@dataclass
class GameLibrarySettings:
    install_shortcut_desktop: Optional[InstallShortcutDesktop] = field(1, default_factory=InstallShortcutDesktop)
    install_shortcut_start_menu: Optional[InstallShortcutStartMenu] = field(2, default_factory=InstallShortcutStartMenu)
    disable_games_tab: Optional[DisableGamesTab] = field(3, default_factory=DisableGamesTab)

@message
@dataclass
class Status:
    status: Optional[str] = field(1)

@message
@dataclass
class CustomStatus:
    text: Optional[str] = field(1)
    emoji_id: Optional[fixed64] = field(2)
    emoji_name: Optional[str] = field(3)
    expires_at_ms: Optional[fixed64] = field(4)

@message
@dataclass
class ShowCurrentGame:
    value: Optional[bool] = field(1)

@message
@dataclass
class StatusSettings:
    status: Optional[Status] = field(1, default_factory=Status)
    custom_status: Optional[CustomStatus] = field(2, default_factory=CustomStatus)
    show_current_game: Optional[ShowCurrentGame] = field(3, default_factory=ShowCurrentGame)

@message
@dataclass
class Locale:
    locale_code: Optional[str] = field(1)

@message
@dataclass
class TimezoneOffset:
    offset: Optional[uint32] = field(1)

@message
@dataclass
class LocalizationSettings:
    locale: Optional[Locale] = field(1, default_factory=Locale)
    timezone_offset: Optional[TimezoneOffset] = field(2, default_factory=TimezoneOffset)

class Theme(IntEnum):
    UNSET = 0
    DARK = 1
    LIGHT = 2

@message
@dataclass
class AppearanceSettings:
    theme: Optional[Theme] = field(1)
    developer_mode: Optional[bool] = field(2)

@message
@dataclass
class PreloadedUserSettings:
    versions: Optional[Version] = field(1, default_factory=Version)
    inbox: Optional[InboxSettings] = field(2, default_factory=InboxSettings)
    guilds: Optional[GuildSettings] = field(3, default_factory=GuildSettings)
    user_content: Optional[UserContentSettings] = field(4, default_factory=UserContentSettings)
    voice_and_video: Optional[VoiceAndVideoSettings] = field(5, default_factory=VoiceAndVideoSettings)
    text_and_images: Optional[TextAndImagesSettings] = field(6, default_factory=TextAndImagesSettings)
    notifications: Optional[NotificationSettings] = field(7, default_factory=NotificationSettings)
    privacy: Optional[PrivacySettings] = field(8, default_factory=PrivacySettings)
    debug: Optional[DebugSettings] = field(9, default_factory=DebugSettings)
    game_library: Optional[GameLibrarySettings] = field(10, default_factory=GameLibrarySettings)
    status: Optional[StatusSettings] = field(11, default_factory=StatusSettings)
    localization: Optional[LocalizationSettings] = field(12, default_factory=LocalizationSettings)
    appearance: Optional[AppearanceSettings] = field(13, default_factory=AppearanceSettings)