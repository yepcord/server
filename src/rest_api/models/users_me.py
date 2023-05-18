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

from pydantic import BaseModel, validator, Field
from typing import Optional, List

from ...yepcord.errors import InvalidDataErr, Errors


# noinspection PyMethodParameters
class UserUpdate(BaseModel):
    username: Optional[str] = None
    discriminator: Optional[int] = None
    password: Optional[str] = None
    new_password: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = ""

    @validator("discriminator")
    def validate_discriminator(cls, value: Optional[int]):
        if value is not None:
            if value < 1 or value > 9999:
                value = None
        return value

    @property
    def to_json(self) -> dict:
        return self.dict(include={"avatar"}, exclude_defaults=True)


class UserProfileUpdate(BaseModel):
    banner: Optional[str] = ""
    bio: Optional[str] = None
    accent_color: Optional[int] = None

    @property
    def to_json(self) -> dict:
        return self.dict(exclude_defaults=True)


class ConsentSettingsUpdate(BaseModel):
    grant: List[str]
    revoke: List[str]

class SettingsUpdate(BaseModel):
    inline_attachment_media: Optional[bool] = None
    show_current_game: Optional[bool] = None
    view_nsfw_guilds: Optional[bool] = None
    enable_tts_command: Optional[bool] = None
    render_reactions: Optional[bool] = None
    gif_auto_play: Optional[bool] = None
    stream_notifications_enabled: Optional[bool] = None
    animate_emoji: Optional[bool] = None
    afk_timeout: Optional[int] = None
    view_nsfw_commands: Optional[bool] = None
    detect_platform_accounts: Optional[bool] = None
    explicit_content_filter: Optional[int] = None
    default_guilds_restricted: Optional[bool] = None
    allow_accessibility_detection: Optional[bool] = None
    native_phone_integration_enabled: Optional[bool] = None
    friend_discovery_flags: Optional[int] = None
    contact_sync_enabled: Optional[bool] = None
    disable_games_tab: Optional[bool] = None
    developer_mode: Optional[bool] = None
    render_embeds: Optional[bool] = None
    animate_stickers: Optional[int] = None
    message_display_compact: Optional[bool] = None
    convert_emoticons: Optional[bool] = None
    passwordless: Optional[bool] = None
    personalization: Optional[bool] = None
    usage_statistics: Optional[bool] = None
    inline_embed_media: Optional[bool] = None
    use_thread_sidebar: Optional[bool] = None
    use_rich_chat_input: Optional[bool] = None
    expression_suggestions_enabled: Optional[bool] = None
    view_image_descriptions: Optional[bool] = None
    status: Optional[str] = None
    custom_status: Optional[dict] = None
    theme: Optional[str] = None
    locale: Optional[str] = None
    timezone_offset: Optional[int] = None
    activity_restricted_guild_ids: Optional[list] = None
    friend_source_flags: Optional[dict] = None
    guild_positions: Optional[list] = None
    guild_folders: Optional[list] = None
    restricted_guilds: Optional[list] = None
    render_spoilers: Optional[str] = None
    dismissed_contents: Optional[str] = None

    @property
    def to_json(self) -> dict:
        return self.dict(exclude_defaults=True)


class SettingsProtoUpdate(BaseModel):
    settings: str


# noinspection PyMethodParameters
class RelationshipRequest(BaseModel):
    username: str
    discriminator: int

    @validator("discriminator")
    def validate_discriminator(cls, value: int):
        if value < 1 or value > 9999:
            raise InvalidDataErr(400,
                                 Errors.make(50035,
                                             {"name": {"code": "BASE_TYPE_BAD_INT", "message": "Must be between 1 and 9999"}}))
        return value


class PutNote(BaseModel):
    note: Optional[str] = None


class MfaEnable(BaseModel):
    password: str
    secret: Optional[str] = None
    code: Optional[str] = None


class MfaDisable(BaseModel):
    code: str


class MfaCodesVerification(BaseModel):
    nonce: str
    key: str
    regenerate: bool = False


class RelationshipPut(BaseModel):
    type: Optional[int] = None


class DmChannelCreate(BaseModel):
    recipients: List[int]
    name: Optional[str] = None


class DeleteRequest(BaseModel):
    password: str


class GetScheduledEventsQuery(BaseModel):
    guild_ids: list[int] = Field(default_factory=list)

    def __init__(self, **data):
        if "guild_ids" in data:
            data["guild_ids"] = data["guild_ids"].split(",")
        super().__init__(**data)