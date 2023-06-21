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
from datetime import date
from typing import Optional

import ormar
from ormar import ReferentialAction

from . import DefaultMeta
from ..utils import b64encode, int_length, b64decode


class User(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    email: str = ormar.String(max_length=254, unique=True)
    password: str = ormar.String(max_length=128)
    verified: bool = ormar.Boolean(default=False)
    deleted: bool = ormar.Boolean(default=False)


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


class UserData(ormar.Model):
    class Meta(DefaultMeta):
        constraints = [ormar.UniqueColumns("username", "discriminator")]

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    birth: date = ormar.Date()
    username: str = ormar.String(max_length=128)
    discriminator: int = ormar.Integer(minimum=1, maximum=9999)
    premium: bool = ormar.Boolean(default=True)
    flags: int = ormar.BigInteger()
    public_flags: int = ormar.BigInteger()
    phone: Optional[str] = ormar.String(max_length=32, nullable=True, default=None)
    bio: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    accent_color: Optional[int] = ormar.BigInteger(nullable=True, default=None)
    avatar: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    avatar_decoration: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    banner: Optional[str] = ormar.String(max_length=256, nullable=True, default=None)
    banner_color: Optional[int] = ormar.BigInteger(nullable=True, default=None)


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
    theme: str = ormar.String(max_length=8, default="dark") # TODO: add `choices`
    locale: str = ormar.String(max_length=8, default="en-US")
    mfa: str = ormar.String(max_length=64, nullable=True, default=None)
    render_spoilers: str = ormar.String(max_length=16, default="ON_CLICK") # TODO: add `choices`
    dismissed_contents: str = ormar.String(max_length=64, default="510109000002000080")
    status: str = ormar.String(max_length=32, default="online") # TODO: add `choices`
    custom_status: Optional[dict] = ormar.JSON(nullable=True, default=None)
    activity_restricted_guild_ids: list = ormar.JSON(default=[])
    friend_source_flags: dict = ormar.JSON(default={"all": True})
    guild_positions: list = ormar.JSON(default=[])
    guild_folders: list = ormar.JSON(default=[])
    restricted_guilds: list = ormar.JSON(default=[])


class FrecencySettings(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=False)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    settings: str = ormar.Text()


class Relationship(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user1: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user1")
    user2: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user2")
    type: int = ormar.Integer() # TODO: add `choices`


class UserNote(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="user")
    target: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE, related_name="target")


class MfaCode(ormar.Model):
    class Meta(DefaultMeta):
        pass

    id: int = ormar.BigInteger(primary_key=True, autoincrement=True)
    user: User = ormar.ForeignKey(User, ondelete=ReferentialAction.CASCADE)
    code: str = ormar.String(max_length=16)
    used: bool = ormar.Boolean(default=False)
