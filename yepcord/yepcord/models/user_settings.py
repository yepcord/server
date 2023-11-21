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

from typing import Optional, Any

from google.protobuf.wrappers_pb2 import UInt32Value, BoolValue, StringValue, Int32Value
from protobuf3_to_dict import protobuf_to_dict
from tortoise import fields

from ..enums import Locales
from ._utils import ChoicesValidator, SnowflakeField, Model
import yepcord.yepcord.models as models
from ..proto import PreloadedUserSettings, Versions, UserContentSettings, VoiceAndVideoSettings, \
    TextAndImagesSettings, PrivacySettings, StatusSettings, CustomStatus, LocalizationSettings, AppearanceSettings, \
    GuildFolders, GuildFolder, Theme
from ..utils import dict_get, freeze, unfreeze


class UserSettings(Model):
    id: int = SnowflakeField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    inline_attachment_media: bool = fields.BooleanField(default=True)
    show_current_game: bool = fields.BooleanField(default=True)
    view_nsfw_guilds: bool = fields.BooleanField(default=False)
    enable_tts_command: bool = fields.BooleanField(default=True)
    render_reactions: bool = fields.BooleanField(default=True)
    gif_auto_play: bool = fields.BooleanField(default=True)
    stream_notifications_enabled: bool = fields.BooleanField(default=True)
    animate_emoji: bool = fields.BooleanField(default=True)
    view_nsfw_commands: bool = fields.BooleanField(default=False)
    detect_platform_accounts: bool = fields.BooleanField(default=True)
    default_guilds_restricted: bool = fields.BooleanField(default=False)
    allow_accessibility_detection: bool = fields.BooleanField(default=False)
    native_phone_integration_enabled: bool = fields.BooleanField(default=True)
    contact_sync_enabled: bool = fields.BooleanField(default=False)
    disable_games_tab: bool = fields.BooleanField(default=False)
    developer_mode: bool = fields.BooleanField(default=False)
    render_embeds: bool = fields.BooleanField(default=True)
    message_display_compact: bool = fields.BooleanField(default=False)
    convert_emoticons: bool = fields.BooleanField(default=True)
    passwordless: bool = fields.BooleanField(default=True)
    personalization: bool = fields.BooleanField(default=False)
    usage_statistics: bool = fields.BooleanField(default=False)
    inline_embed_media: bool = fields.BooleanField(default=True)
    use_thread_sidebar: bool = fields.BooleanField(default=True)
    use_rich_chat_input: bool = fields.BooleanField(default=True)
    expression_suggestions_enabled: bool = fields.BooleanField(default=True)
    view_image_descriptions: bool = fields.BooleanField(default=True)
    afk_timeout: int = fields.IntField(default=600)
    explicit_content_filter: int = fields.IntField(default=1)
    timezone_offset: int = fields.IntField(default=0)
    friend_discovery_flags: int = fields.IntField(default=0)
    animate_stickers: int = fields.IntField(default=0)
    theme: str = fields.CharField(max_length=8, default="dark", validators=[ChoicesValidator({"dark", "light"})])
    locale: str = fields.CharField(max_length=8, default="en-US", validators=[ChoicesValidator(Locales.values_set())])
    mfa: str = fields.CharField(max_length=64, null=True, default=None)
    render_spoilers: str = fields.CharField(max_length=16, default="ON_CLICK",
                                            validators=[ChoicesValidator({"ALWAYS", "ON_CLICK", "IF_MODERATOR"})])
    dismissed_contents: str = fields.CharField(max_length=64, default="510109000002000080")
    status: str = fields.CharField(max_length=32, default="online",
                                   validators=[ChoicesValidator({"online", "idle", "dnd", "offline", "invisible"})])
    custom_status: Optional[dict] = fields.JSONField(null=True, default=None)
    activity_restricted_guild_ids: list = fields.JSONField(default=[])
    friend_source_flags: dict = fields.JSONField(default={"all": True})
    guild_positions: list = fields.JSONField(default=[])
    guild_folders: list = fields.JSONField(default=[])
    restricted_guilds: list = fields.JSONField(default=[])

    def ds_json(self) -> dict:
        data = {
            "locale": self.locale,
            "show_current_game": self.show_current_game,
            "restricted_guilds": self.restricted_guilds,
            "default_guilds_restricted": self.default_guilds_restricted,
            "inline_attachment_media": self.inline_attachment_media,
            "inline_embed_media": self.inline_attachment_media,
            "gif_auto_play": self.gif_auto_play,
            "render_embeds": self.render_embeds,
            "render_reactions": self.render_reactions,
            "animate_emoji": self.animate_emoji,
            "enable_tts_command": self.enable_tts_command,
            "message_display_compact": self.message_display_compact,
            "convert_emoticons": self.convert_emoticons,
            "explicit_content_filter": self.explicit_content_filter,
            "disable_games_tab": self.disable_games_tab,
            "theme": self.theme,
            "developer_mode": self.developer_mode,
            "guild_positions": self.guild_positions,
            "detect_platform_accounts": self.detect_platform_accounts,
            "status": self.status,
            "afk_timeout": self.afk_timeout,
            "timezone_offset": self.timezone_offset,
            "stream_notifications_enabled": self.stream_notifications_enabled,
            "allow_accessibility_detection": self.allow_accessibility_detection,
            "contact_sync_enabled": self.contact_sync_enabled,
            "native_phone_integration_enabled": self.native_phone_integration_enabled,
            "animate_stickers": self.animate_stickers,
            "friend_discovery_flags": self.friend_discovery_flags,
            "view_nsfw_guilds": self.view_nsfw_guilds,
            "view_nsfw_commands": self.view_nsfw_commands,
            "passwordless": self.passwordless,
            "friend_source_flags": self.friend_source_flags,
            "guild_folders": self.guild_folders,
            "custom_status": self.custom_status,
            "activity_restricted_guild_ids": self.activity_restricted_guild_ids
        }
        if data["status"] == "offline":
            data["status"] = "invisible"
        return data

    def ds_json_consent(self) -> dict:
        return {
            "personalization": {
                "consented": self.personalization
            },
            "usage_statistics": {
                "consented": self.usage_statistics
            }
        }

    def proto(self) -> UserSettingsProto:
        return UserSettingsProto(self)


class UserSettingsProto:
    def __init__(self, settings: UserSettings):
        self._settings = settings

    def __getattr__(self, item: str) -> Any:
        return getattr(self._settings, item, None)

    def get(self) -> PreloadedUserSettings:
        proto = PreloadedUserSettings(
            versions=Versions(client_version=14, data_version=1),
            user_content=UserContentSettings(dismissed_contents=bytes.fromhex(self.dismissed_contents)),
            voice_and_video=VoiceAndVideoSettings(
                afk_timeout=UInt32Value(value=self.afk_timeout),
                stream_notifications_enabled=BoolValue(value=self.stream_notifications_enabled)
            ),
            text_and_images=TextAndImagesSettings(
                use_rich_chat_input=BoolValue(value=self.use_rich_chat_input),
                use_thread_sidebar=BoolValue(value=self.use_thread_sidebar),
                render_spoilers=StringValue(value=self.render_spoilers),
                inline_attachment_media=BoolValue(value=self.inline_attachment_media),
                inline_embed_media=BoolValue(value=self.inline_embed_media),
                render_embeds=BoolValue(value=self.render_embeds),
                render_reactions=BoolValue(value=self.render_reactions),
                explicit_content_filter=UInt32Value(value=self.explicit_content_filter),
                view_nsfw_guilds=BoolValue(value=self.view_nsfw_guilds),
                convert_emoticons=BoolValue(value=self.convert_emoticons),
                animate_stickers=UInt32Value(value=self.animate_stickers),
                expression_suggestions_enabled=BoolValue(value=self.expression_suggestions_enabled),
                message_display_compact=BoolValue(value=self.message_display_compact),
                view_image_descriptions=BoolValue(value=self.view_image_descriptions)
            ),
            privacy=PrivacySettings(
                friend_source_flags=UInt32Value(value=14),
                default_guilds_restricted=self.default_guilds_restricted,
                allow_accessibility_detection=self.allow_accessibility_detection
            ),
            status=StatusSettings(
                status=StringValue(value=self.status),
                show_current_game=BoolValue(value=self.show_current_game),
                custom_status=CustomStatus(
                    text=self.custom_status.get("text"),
                    expires_at_ms=self.custom_status.get("expires_at_ms"),
                    emoji_id=self.custom_status.get("emoji_id"),
                    emoji_name=self.custom_status.get("emoji_name"),
                ) if self.custom_status else None
            ),
            localization=LocalizationSettings(
                locale=StringValue(value=self.locale),
                timezone_offset=Int32Value(value=self.timezone_offset)
            ),
            appearance=AppearanceSettings(
                theme=Theme.DARK if self.theme == "dark" else Theme.LIGHT,
                developer_mode=self.developer_mode
            ),
            guild_folders=GuildFolders(folders=[GuildFolder(**folder) for folder in self.guild_folders])
        )
        if d := self.friend_source_flags:
            if d["all"]:
                proto.privacy.friend_source_flags.value = 14
            elif d["mutual_friends"] and d["mutual_guilds"]:
                proto.privacy.friend_source_flags.value = 6
            elif d["mutual_guilds"]:
                proto.privacy.friend_source_flags.value = 4
            elif d["mutual_friends"]:
                proto.privacy.friend_source_flags.value = 2
            else:
                proto.privacy.friend_source_flags.value = 0
        return proto

    @staticmethod
    def _to_settings_dict(proto_dict: dict, changes: dict = None) -> dict:
        if changes is None:
            changes = {}
        fields_ = [
            ("text_and_images.inline_attachment_media.value", "inline_attachment_media"),
            ("status.show_current_game.value", "show_current_game"),
            ("text_and_images.view_nsfw_guilds.value", "view_nsfw_guilds"),
            ("text_and_images.enable_tts_command.value", "enable_tts_command"),
            ("text_and_images.render_reactions.value", "render_reactions"),
            ("text_and_images.gif_auto_play.value", "gif_auto_play"),
            ("voice_and_video.stream_notifications_enabled.value", "stream_notifications_enabled"),
            ("text_and_images.animate_emoji.value", "animate_emoji"),
            ("voice_and_video.afk_timeout.value", "afk_timeout"),
            ("text_and_images.view_nsfw_commands.value", "view_nsfw_commands"),
            ("privacy.detect_platform_accounts.value", "detect_platform_accounts"),
            ("text_and_images.explicit_content_filter.value", "explicit_content_filter"),
            ("status.status.value", "status"),
            ("privacy.default_guilds_restricted", "default_guilds_restricted"),
            ("privacy.allow_accessibility_detection", "allow_accessibility_detection"),
            ("localization.locale.locale_code", "locale"),
            ("voice_and_video.native_phone_integration_enabled.value", "native_phone_integration_enabled"),
            ("localization.timezone_offset.offset", "timezone_offset"),
            ("privacy.friend_discovery_flags.value", "friend_discovery_flags"),
            ("privacy.contact_sync_enabled.value", "contact_sync_enabled"),
            ("game_library.disable_games_tab.value", "disable_games_tab"),
            ("appearance.developer_mode", "developer_mode"),
            ("text_and_images.render_embeds.value", "render_embeds"),
            ("text_and_images.animate_stickers.value", "animate_stickers"),
            ("text_and_images.message_display_compact.value", "message_display_compact"),
            ("text_and_images.convert_emoticons.value", "convert_emoticons"),
            ("privacy.passwordless.value", "passwordless"),
            ("privacy.activity_restricted_guild_ids", "activity_restricted_guild_ids"),
            ("privacy.restricted_guild_ids", "restricted_guilds"),
            ("text_and_images.render_spoilers.value", "render_spoilers"),
            ("text_and_images.inline_embed_media.value", "inline_embed_media"),
            ("text_and_images.use_thread_sidebar.value", "use_thread_sidebar"),
            ("text_and_images.use_rich_chat_input.value", "use_rich_chat_input"),
            ("text_and_images.expression_suggestions_enabled.value", "expression_suggestions_enabled"),
            ("text_and_images.view_image_descriptions.value", "view_image_descriptions"),
        ]

        for proto_path, out_name in fields_:
            dict_get(proto_dict, proto_path, output_dict=changes, output_name=out_name)
        return changes

    async def update(self, new_proto: PreloadedUserSettings) -> None:
        old_settings = freeze(protobuf_to_dict(self.get()))
        new_settings = freeze(protobuf_to_dict(new_proto))
        proto_d = unfreeze(new_settings - old_settings)

        changes = UserSettingsProto._to_settings_dict(proto_d)
        changes["theme"] = "dark" if dict_get(proto_d, "appearance.theme", 1) == 1 else "light"
        if custom_status := dict_get(proto_d, "status.custom_status"):
            changes["custom_status"] = {
                "text": dict_get(custom_status, "text", None),
                "emoji_id": dict_get(custom_status, "emoji_id", None),
                "emoji_name": dict_get(custom_status, "emoji_name", None),
                "expires_at_ms": dict_get(custom_status, "expires_at_ms", None)
            }
        cs = changes.get("custom_status", {})
        if ("status" in changes and
                all([val is None for val in (cs.get("text"), cs.get("emoji_id"), cs.get("emoji_name"),)])):
            changes["custom_status"] = {}
        if (friend_source_flags := dict_get(proto_d, "privacy.friend_source_flags.value")) is not None:
            if friend_source_flags == 14:
                changes["friend_source_flags"] = {"all": True}
            elif friend_source_flags == 6:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": True, "mutual_guilds": True}
            elif friend_source_flags == 4:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": True}
            elif friend_source_flags == 2:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": True, "mutual_guilds": False}
            else:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": True}
        else:
            changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": False}
        if (dismissed_contents := dict_get(proto_d, "user_content.dismissed_contents")) is not None:
            changes["dismissed_contents"] = dismissed_contents[:128].hex()
        if guild_folders := dict_get(proto_d, "guild_folders.folders"):
            folders = []
            for folder in guild_folders:
                folders.append({"guild_ids": list(folder.guild_ids)})
                if folder_id := dict_get(folder, "id.value"): folders[-1]["id"] = {"value": folder_id}
                if folder_name := dict_get(folder, "name.value"): folders[-1]["name"] = {"value": folder_name}
                if folder_color := dict_get(folder, "color.value"): folders[-1]["color"] = {"value": folder_color}
            changes["guild_folders"] = folders
        changes = freeze(changes)
        old_settings = freeze(self._settings.__dict__)

        changes = unfreeze(changes - old_settings)
        await self._settings.update(**changes)
