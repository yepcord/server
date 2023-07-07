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

from datetime import date, datetime, timedelta
from typing import Optional, Any

import ormar
# noinspection PyPackageRequirements
from google.protobuf.wrappers_pb2 import UInt32Value, BoolValue, StringValue, Int32Value
from ormar import ReferentialAction

from . import DefaultMeta
from ..ctx import getCore
from ..enums import RelationshipType, RelTypeDiscord
from ..proto import PreloadedUserSettings, UserContentSettings, Versions, VoiceAndVideoSettings, TextAndImagesSettings, \
    PrivacySettings, StatusSettings, LocalizationSettings, AppearanceSettings, Theme, GuildFolders, GuildFolder, \
    FrecencyUserSettings
from ..snowflake import Snowflake
from ..utils import b64encode, int_length, b64decode, proto_get


class User(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    email: str = ormar.String(max_length=254, unique=True)
    password: str = ormar.String(max_length=128)
    verified: bool = ormar.Boolean(default=False)
    deleted: bool = ormar.Boolean(default=False)

    @property
    async def settings(self) -> UserSettings:
        return await UserSettings.objects.get(id=self.id)

    @property
    async def data(self) -> UserData:
        return await UserData.objects.select_related("user").get(id=self.id)

    @property
    async def userdata(self) -> UserData:
        return await UserData.objects.select_related("user").get(id=self.id)

    @property
    def created_at(self) -> datetime:
        return Snowflake.toDatetime(self.id)

    async def profile_json(self, other_user: User, with_mutual_guilds: bool=False, mutual_friends_count: bool=False,
                           guild_id: int=None) -> dict:
        data = await self.data
        premium_since = self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = {
            "user": {
                "id": str(self.id),
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
            "premium_since": premium_since,
            "premium_guild_since": premium_since,
            "user_profile": {
                "bio": data.bio,
                "accent_color": data.accent_color
            }
        }
        if guild_id and (guild := await getCore().getGuild(guild_id)):
            if member := await getCore().getGuildMember(guild, self.id):
                data["guild_member_profile"] = {"guild_id": str(guild_id)}
                data["guild_member"] = await member.ds_json()
        if mutual_friends_count:
            data["mutual_friends_count"] = 0  # TODO
        if with_mutual_guilds:
            data["mutual_guilds"] = await getCore().getMutualGuildsJ(self, other_user)

        return data


class Session(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    signature: str = ormar.String(max_length=128)

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.user.id).encode('utf8'))}." \
               f"{b64encode(int.to_bytes(self.id, int_length(self.id), 'big'))}." \
               f"{self.signature}"

    @staticmethod
    def extract_token(token: str) -> Optional[tuple[int, int, str]]:
        token = token.split(".")
        if len(token) != 3:
            return
        uid, sid, sig = token
        try:
            uid = int(b64decode(uid))
            sid = int.from_bytes(b64decode(sid), "big")
            b64decode(sig)
        except ValueError:
            return
        return uid, sid, sig

    @classmethod
    async def from_token(cls, token: str) -> Optional[Session]:
        token = Session.extract_token(token)
        if token is None:
            return
        user_id, session_id, signature = token
        return await Session.objects.select_related("user")\
            .get_or_none(id=session_id, user__id=user_id, signature=signature)


class UserData(ormar.Model):
    class Meta(DefaultMeta):
        constraints = [ormar.UniqueColumns("username", "discriminator")]

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    birth: date = ormar.Date()
    username: str = ormar.String(max_length=128)
    discriminator: int = ormar.Integer(minimum=1, maximum=9999)
    premium: bool = ormar.Boolean(default=True)
    flags: int = ormar.BigInteger(default=0)
    public_flags: int = ormar.BigInteger(default=0)
    phone: Optional[str] = ormar.String(max_length=32, nullable=True, default=None)
    bio: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    accent_color: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    avatar: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    avatar_decoration: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    banner: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    banner_color: Optional[int] = ormar.BigInteger(nullable=True, default=None)

    @property
    def s_discriminator(self) -> str:
        return str(self.discriminator).rjust(4, "0")

    @property
    def nsfw_allowed(self) -> bool:
        dn = date.today()
        return dn - self.birth > timedelta(days=18 * 365 + 4)

    @property
    def ds_json(self) -> dict:
        return {
            "id": str(self.id),
            "username": self.username,
            "avatar": self.avatar,
            "avatar_decoration": self.avatar_decoration,
            "discriminator": self.s_discriminator,
            "public_flags": self.public_flags
        }

    async def ds_json_full(self) -> dict:
        settings = await self.user.settings
        return {
            "id": str(self.id),
            "username": self.username,
            "avatar": self.avatar,
            "avatar_decoration": self.avatar_decoration,
            "discriminator": self.s_discriminator,
            "public_flags": self.public_flags,
            "flags": self.flags,
            "banner": self.banner,
            "banner_color": self.banner_color,
            "accent_color": self.accent_color,
            "bio": self.bio,
            "locale": settings.locale,
            "nsfw_allowed": self.nsfw_allowed,
            "mfa_enabled": settings.mfa,
            "email": self.user.email,
            "verified": self.user.verified,
            "phone": self.phone
        }


class UserSettings(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    inline_attachment_media: bool = ormar.Boolean(default=True)
    show_current_game: bool = ormar.Boolean(default=True)
    view_nsfw_guilds: bool = ormar.Boolean(default=False)
    enable_tts_command: bool = ormar.Boolean(default=True)
    render_reactions: bool = ormar.Boolean(default=True)
    gif_auto_play: bool = ormar.Boolean(default=True)
    stream_notifications_enabled: bool = ormar.Boolean(default=True)
    animate_emoji: bool = ormar.Boolean(default=True)
    view_nsfw_commands: bool = ormar.Boolean(default=False)
    detect_platform_accounts: bool = ormar.Boolean(default=True)
    default_guilds_restricted: bool = ormar.Boolean(default=False)
    allow_accessibility_detection: bool = ormar.Boolean(default=False)
    native_phone_integration_enabled: bool = ormar.Boolean(default=True)
    contact_sync_enabled: bool = ormar.Boolean(default=False)
    disable_games_tab: bool = ormar.Boolean(default=False)
    developer_mode: bool = ormar.Boolean(default=False)
    render_embeds: bool = ormar.Boolean(default=True)
    message_display_compact: bool = ormar.Boolean(default=False)
    convert_emoticons: bool = ormar.Boolean(default=True)
    passwordless: bool = ormar.Boolean(default=True)
    personalization: bool = ormar.Boolean(default=False)
    usage_statistics: bool = ormar.Boolean(default=False)
    inline_embed_media: bool = ormar.Boolean(default=True)
    use_thread_sidebar: bool = ormar.Boolean(default=True)
    use_rich_chat_input: bool = ormar.Boolean(default=True)
    expression_suggestions_enabled: bool = ormar.Boolean(default=True)
    view_image_descriptions: bool = ormar.Boolean(default=True)
    afk_timeout: int = ormar.Integer(default=600)
    explicit_content_filter: int = ormar.Integer(default=1)
    timezone_offset: int = ormar.Integer(default=0)
    friend_discovery_flags: int = ormar.Integer(default=0)
    animate_stickers: int = ormar.Integer(default=0)
    theme: str = ormar.String(max_length=8, default="dark", choices=["dark", "light"])  # TODO: add `choices`
    locale: str = ormar.String(max_length=8, default="en-US")
    mfa: str = ormar.String(max_length=64, nullable=True, default=None)
    render_spoilers: str = ormar.String(max_length=16, default="ON_CLICK")  # TODO: add `choices`
    dismissed_contents: str = ormar.String(max_length=64, default="510109000002000080")
    status: str = ormar.String(max_length=32, default="online")  # TODO: add `choices`
    custom_status: Optional[dict] = ormar.JSON(nullable=True, default=None)
    activity_restricted_guild_ids: list = ormar.JSON(default=[])
    friend_source_flags: dict = ormar.JSON(default={"all": True})
    guild_positions: list = ormar.JSON(default=[])
    guild_folders: list = ormar.JSON(default=[])
    restricted_guilds: list = ormar.JSON(default=[])

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


class UserSettingsProto:
    def __init__(self, settings: UserSettings):
        self._settings = settings

    def __getattr__(self, item: str) -> Any:
        return getattr(self._settings, item, None)

    def get(self) -> PreloadedUserSettings:
        proto = PreloadedUserSettings(
            versions=Versions(client_version=14, data_version=1),  # TODO: get data version from database
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
                show_current_game=BoolValue(value=self.show_current_game)
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
    def to_dict(proto: PreloadedUserSettings, changes: dict=None) -> dict:
        if changes is None:
            changes = {}
        fields = [
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

        for proto_path, out_name in fields:
            proto_get(proto, proto_path, output_dict=changes, output_name=out_name)
        return changes

    async def update(self, proto: PreloadedUserSettings) -> None:
        changes = UserSettingsProto.to_dict(proto)
        if (theme := proto_get(proto, "appearance.theme", 1)) is not None:
            changes["theme"] = "dark" if theme == 1 else "light"
        if (custom_status := proto_get(proto, "status.custom_status")) is not None:
            cs = {
                "text": proto_get(custom_status, "text", None),
                "emoji_id": proto_get(custom_status, "emoji_id", None),
                "emoji_name": proto_get(custom_status, "emoji_name", None),
                "expires_at_ms": proto_get(custom_status, "expires_at_ms", None)
            }
            changes["custom_status"] = cs
        if (p := proto_get(proto, "privacy.friend_source_flags.value")) is not None:
            if p == 14:
                changes["friend_source_flags"] = {"all": True}
            elif p == 6:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": True, "mutual_guilds": True}
            elif p == 4:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": True}
            elif p == 2:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": True, "mutual_guilds": False}
            else:
                changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": True}
        else:
            changes["friend_source_flags"] = {"all": False, "mutual_friends": False, "mutual_guilds": False}
        if (dismissed_contents := proto_get(proto, "user_content.dismissed_contents")) is not None:
            changes["dismissed_contents"] = dismissed_contents[:128].hex()
        if guild_folders := proto_get(proto, "guild_folders.folders"):
            folders = []
            for folder in guild_folders:
                folders.append({"guild_ids": list(folder.guild_ids)})
                if folder_id := proto_get(folder, "id.value"): folders[-1]["id"] = {"value": folder_id}
                if folder_name := proto_get(folder, "name.value"): folders[-1]["name"] = {"value": folder_name}
                if folder_color := proto_get(folder, "color.value"): folders[-1]["color"] = {"value": folder_color}
            changes["guild_folders"] = folders
        await self._settings.update(**changes)


class FrecencySettings(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    settings: str = ormar.Text()

    def to_proto(self) -> FrecencyUserSettings:
        proto = FrecencyUserSettings()
        proto.ParseFromString(b64decode(self.settings))
        return proto


class Relationship(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user1: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user1")
    user2: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user2")
    type: int = ormar.Integer(choices=[0, 1, 2])

    def other_user(self, current_user: User) -> User:
        return self.user1 if self.user2 == current_user else self.user2

    def discord_rel_type(self, current_user: User) -> Optional[int]:
        if self.type == RelationshipType.BLOCK and self.user1 != current_user.id:
            return None
        elif self.type == RelationshipType.BLOCK:
            return RelTypeDiscord.BLOCK
        elif self.type == RelationshipType.FRIEND:
            return RelTypeDiscord.FRIEND
        elif self.user1 == current_user:
            return RelTypeDiscord.REQUEST_SENT
        elif self.user2 == current_user:
            return RelTypeDiscord.REQUEST_RECV

    async def ds_json(self, current_user: User, with_data=False) -> Optional[dict]:
        other_user = self.other_user(current_user)
        if (rel_type := self.discord_rel_type(current_user)) is None:
            return
        data = {"user_id": str(other_user.id), "type": rel_type, "nickname": None, "id": str(other_user.id)}
        if with_data:
            userdata = await other_user.data
            data["user"] = userdata.ds_json

        return data


class UserNote(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user")
    target: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="target")
    text: str = ormar.Text(nullable=True, default=None)

    def ds_json(self) -> dict:
        return {
            "user_id": self.user.id,
            "note_user_id": self.target.id,
            "note": self.text,
        }


class MfaCode(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    code: str = ormar.String(max_length=16)
    used: bool = ormar.Boolean(default=False)

    def ds_json(self) -> dict:
        return {
            "user_id": str(self.user.id),
            "code": self.code,
            "consumed": self.used
        }
