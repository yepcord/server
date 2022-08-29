from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Dict

def protoStub(cls):
    def _init(self, *args, **kwargs):
        raise RuntimeError
    def _ParseFromString(self, data: bytes) -> None:
        raise RuntimeError
    def _SerializeToString(self) -> bytes:
        raise RuntimeError
    cls.__init__ = _init
    cls.ParseFromString = _ParseFromString
    cls.SerializeToString = _SerializeToString
    return cls

@dataclass
@protoStub
class Version:
    client_version: Optional[int]
    server_version: Optional[int]
    data_version: Optional[int]

class InboxTab(IntEnum):
    UNSPECIFIED = 0
    MENTIONS = 1
    UNREADS = 2

@dataclass
@protoStub
class InboxSettings:
    current_tab: Optional[InboxTab]
    viewed_tutorial: Optional[bool]

@dataclass
@protoStub
class ChannelSettings:
    collapsed_in_inbox: Optional[bool]

@dataclass
@protoStub
class GuildSettings:
    channels: Dict[int, ChannelSettings]
    hub_progress: Optional[int]
    guild_onboarding_progress: Optional[int]

@dataclass
@protoStub
class LastDismissedOutboundPromotionStartDate:
    value: Optional[str]

@dataclass
@protoStub
class PremiumTier0ModalDismissedAt:
    timestamp: Optional[int]

@dataclass
@protoStub
class UserContentSettings:
    dismissed_contents: Optional[bytes]
    last_dismissed_outbound_promotion_start_date: Optional[LastDismissedOutboundPromotionStartDate]
    premium_tier_0_modal_dismissed_at: Optional[PremiumTier0ModalDismissedAt]

@dataclass
@protoStub
class VideoFilterBackgroundBlur:
    use_blur: Optional[bool]

@dataclass
@protoStub
class VideoFilterAsset:
    id: Optional[int]
    asset_hash: Optional[str]

@dataclass
@protoStub
class AlwaysPreviewVideo:
    value: Optional[bool]

@dataclass
@protoStub
class AfkTimeout:
    value: Optional[int]

@dataclass
@protoStub
class StreamNotificationsEnabled:
    value: Optional[bool]

@dataclass
@protoStub
class NativePhoneIntegrationEnabled:
    value: Optional[bool]

@dataclass
@protoStub
class VoiceAndVideoSettings:
    blur: Optional[VideoFilterBackgroundBlur]
    preset_option: Optional[int]
    custom_asset: Optional[VideoFilterAsset]
    always_preview_video: Optional[AlwaysPreviewVideo]
    afk_timeout: Optional[AfkTimeout]
    stream_notifications_enabled: Optional[StreamNotificationsEnabled]
    native_phone_integration_enabled: Optional[NativePhoneIntegrationEnabled]

@dataclass
@protoStub
class DiversitySurrogate:
    value: Optional[str]

@dataclass
@protoStub
class UseRichChatInput:
    value: Optional[bool]

@dataclass
@protoStub
class UseThreadSidebar:
    value: Optional[bool]

@dataclass
@protoStub
class RenderSpoilers:
    value: Optional[str]

@dataclass
@protoStub
class ViewImageDescriptions:
    value: Optional[bool]

@dataclass
@protoStub
class ShowCommandSuggestions:
    value: Optional[bool]

@dataclass
@protoStub
class InlineAttachmentMedia:
    value: Optional[bool]

@dataclass
@protoStub
class InlineEmbedMedia:
    value: Optional[bool]

@dataclass
@protoStub
class GifAutoPlay:
    value: Optional[bool]

@dataclass
@protoStub
class RenderEmbeds:
    value: Optional[bool]

@dataclass
@protoStub
class RenderReactions:
    value: Optional[bool]

@dataclass
@protoStub
class AnimateEmoji:
    value: Optional[bool]

@dataclass
@protoStub
class AnimateStickers:
    value: Optional[int]

@dataclass
@protoStub
class EnableTtsCommand:
    value: Optional[bool]

@dataclass
@protoStub
class MessageDisplayCompact:
    value: Optional[bool]

@dataclass
@protoStub
class ExplicitContentFilter:
    value: Optional[int]

@dataclass
@protoStub
class ViewNsfwGuilds:
    value: Optional[bool]

@dataclass
@protoStub
class ConvertEmoticons:
    value: Optional[bool]

@dataclass
@protoStub
class ExpressionSuggestionsEnabled:
    value: Optional[bool]

@dataclass
@protoStub
class ViewNsfwCommands:
    value: Optional[bool]

@dataclass
@protoStub
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
@protoStub
class ShowInAppNotifications:
    value: Optional[bool]

@dataclass
@protoStub
class NotifyFriendsOnGoLive:
    value: Optional[bool]

@dataclass
@protoStub
class NotificationSettings:
    show_in_app_notifications: Optional[ShowInAppNotifications]
    notify_friends_on_go_live: Optional[NotifyFriendsOnGoLive]
    notification_center_acked_before_id: Optional[int]

class GuildActivityStatusRestrictionDefault(IntEnum):
    OFF = 0
    ON_FOR_LARGE_GUILDS = 1

@dataclass
@protoStub
class AllowActivityPartyPrivacyFriends:
    value: Optional[bool]

@dataclass
@protoStub
class AllowActivityPartyPrivacyVoiceChannel:
    value: Optional[bool]

@dataclass
@protoStub
class DetectPlatformAccounts:
    value: Optional[bool]

@dataclass
@protoStub
class Passwordless:
    value: Optional[bool]

@dataclass
@protoStub
class ContactSyncEnabled:
    value: Optional[bool]

@dataclass
@protoStub
class FriendSourceFlags:
    value: Optional[int]

@dataclass
@protoStub
class FriendDiscoveryFlags:
    value: Optional[int]

@dataclass
@protoStub
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
@protoStub
class RtcPanelShowVoiceStates:
    value: Optional[bool]

@dataclass
@protoStub
class DebugSettings:
    rtc_panel_show_voice_states: Optional[RtcPanelShowVoiceStates]

@dataclass
@protoStub
class InstallShortcutDesktop:
    value: Optional[bool]

@dataclass
@protoStub
class InstallShortcutStartMenu:
    value: Optional[bool]

@dataclass
@protoStub
class DisableGamesTab:
    value: Optional[bool]

@dataclass
@protoStub
class GameLibrarySettings:
    install_shortcut_desktop: Optional[InstallShortcutDesktop]
    install_shortcut_start_menu: Optional[InstallShortcutStartMenu]
    disable_games_tab: Optional[DisableGamesTab]

@dataclass
@protoStub
class Status:
    status: Optional[str]

@dataclass
@protoStub
class CustomStatus:
    text: Optional[str]
    emoji_id: Optional[int]
    emoji_name: Optional[str]
    expires_at_ms: Optional[int]

@dataclass
@protoStub
class ShowCurrentGame:
    value: Optional[bool]

@dataclass
@protoStub
class StatusSettings:
    status: Optional[Status]
    custom_status: Optional[CustomStatus]
    show_current_game: Optional[ShowCurrentGame]

@dataclass
@protoStub
class Locale:
    locale_code: Optional[str]

@dataclass
@protoStub
class TimezoneOffset:
    offset: Optional[int]

@dataclass
@protoStub
class LocalizationSettings:
    locale: Optional[Locale]
    timezone_offset: Optional[TimezoneOffset]

class Theme(IntEnum):
    UNSET = 0
    DARK = 1
    LIGHT = 2

@dataclass
@protoStub
class AppearanceSettings:
    theme: Optional[Theme]
    developer_mode: Optional[bool]

@dataclass
@protoStub
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

class GIFType(IntEnum):
    NONE = 0
    IMAGE = 1
    VIDEO = 2

@dataclass
@protoStub
class FavoriteGIF:
    format: Optional[GIFType]
    src: Optional[str]
    width: Optional[int]
    height: Optional[int]
    order: Optional[int]

@dataclass
@protoStub
class FavoriteGIFs:
    gifs: Optional[Dict[str, FavoriteGIF]]
    hide_tooltip: Optional[bool]

@dataclass
@protoStub
class FavoriteStickers:
    stickers_ids: Optional[List[int]]

@dataclass
@protoStub
class FrecencyItem:
    total_uses: Optional[int]
    recent_uses: Optional[List[int]]
    frecency: Optional[int]
    score: Optional[int]

@dataclass
@protoStub
class StickerFrecency:
    stickers: Optional[Dict[int, FrecencyItem]]

@dataclass
@protoStub
class FavoriteEmojis:
    emojis: Optional[List[str]]

@dataclass
@protoStub
class EmojiFrecency:
    emojis: Optional[Dict[str, FrecencyItem]]

@dataclass
@protoStub
class ApplicationCommandFrecency:
    application_commands: Optional[Dict[str, FrecencyItem]]

@dataclass
@protoStub
class FrecencyUserSettings:
    versions: Optional[Version]
    favorite_gifs: Optional[FavoriteGIFs]
    favorite_stickers: Optional[FavoriteStickers]
    sticker_frecency: Optional[StickerFrecency]
    favorite_emojis: Optional[FavoriteEmojis]
    emoji_frecency: Optional[EmojiFrecency]
    application_command_frecency: Optional[ApplicationCommandFrecency]

from .discord_pb2 import *