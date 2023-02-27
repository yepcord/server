# All 'User' classes (User, Session, UserSettings, etc.)
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .guild import Role
    from .channel import Channel

from schema import And, Use, Or, Optional as sOptional, Regex

from ..errors import InvalidDataErr, Errors
from ..snowflake import Snowflake
from ..ctx import getCore
from ..enums import RelationshipType, UserFlags as UserFlagsE, GuildPermissions
from ..model import model, field, Model
from ..proto import AppearanceSettings, Locale, TimezoneOffset, Theme, LocalizationSettings, ShowCurrentGame, \
    Status, StatusSettings, PrivacySettings, FriendSourceFlags, ViewImageDescriptions, MessageDisplayCompact, \
    ExpressionSuggestionsEnabled, AnimateStickers, ConvertEmoticons, ViewNsfwGuilds, ExplicitContentFilter, \
    RenderReactions, RenderEmbeds, InlineEmbedMedia, InlineAttachmentMedia, RenderSpoilers, UseThreadSidebar, \
    UseRichChatInput, TextAndImagesSettings, StreamNotificationsEnabled, AfkTimeout, VoiceAndVideoSettings, \
    UserContentSettings, Version, PreloadedUserSettings
from ..utils import b64encode, b64decode, proto_get, NoneType


class _User:
    id: int

    def __eq__(self, other):
        return isinstance(other, _User) and self.id == other.id

    def get(self, item, default=None):
        if not hasattr(self, item):
            return default
        return getattr(self, item)

class UserId(_User):
    def __init__(self, uid: int):
        self.id = uid

@model
@dataclass
class Session(_User, Model):
    uid: int
    sid: int
    sig: str

    @property
    def id(self) -> int:
        return self.uid

    @property
    def token(self) -> str:
        return f"{b64encode(str(self.uid).encode('utf8'))}.{b64encode(int.to_bytes(self.sid, 6, 'big'))}.{self.sig}"

    @classmethod
    def from_token(cls, token: str) -> Optional[Session]:
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
        return cls(uid, sid, sig)

@model
@dataclass
class UserSettings(Model):
    uid: int = field(id_field=True)
    mfa: Optional[str] = field(default=None, nullable=True, validation=Or(NoneType, str))
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
    status: Optional[str] = field(validation=And(Use(str), Use(str.lower), lambda s: s in ("online", "invisible", "dnd", "idle")), default=None)
    custom_status: Optional[dict] = field(validation=Or(And(Use(dict), lambda d: "text" in d), NoneType), db_name="j_custom_status", nullable=True, default=None)
    theme: Optional[str] = field(validation=And(Use(str), Use(str.lower), lambda s: s in ("light", "dark")), default=None)
    locale: Optional[str] = field(validation=And(Use(str), lambda s: 2 <= len(s) <= 6), default=None)
    timezone_offset: Optional[int] = field(validation=And(Use(int), lambda i: -600 <= i <= 840), default=None)
    activity_restricted_guild_ids: Optional[list] = field(validation=[Use(int)], db_name="j_activity_restricted_guild_ids", default=None)
    friend_source_flags: Optional[dict] = field(validation={"all": Use(bool), sOptional("mutual_friends"): Use(bool),
                                          sOptional("mutual_guilds"): Use(bool)}, db_name="j_friend_source_flags", default=None)
    guild_positions: Optional[list] = field(validation=[Use(int)], db_name="j_guild_positions", default=None)
    guild_folders: Optional[list] = field(validation=[Use(int)], db_name="j_guild_folders", default=None)
    restricted_guilds: Optional[list] = field(validation=[Use(int)], db_name="j_restricted_guilds", default=None)
    render_spoilers: Optional[str] = field(validation=And(Use(str), Use(str.upper), lambda s: s in ("ON_CLICK", "IF_MODERATOR", "ALWAYS")), default=None)
    dismissed_contents: Optional[str] = field(validation=And(Use(str), lambda s: len(s) % 2 == 0), excluded=True, default=None)

    @property
    async def json(self) -> dict:
        data = self.toJSON()
        data["mfa"] = bool(data["mfa"])
        return data

    def to_proto(self) -> PreloadedUserSettings:
        proto = PreloadedUserSettings(
            versions=Version(client_version=14, data_version=1), # TODO: get data version from database
            user_content=UserContentSettings(dismissed_contents=bytes.fromhex(self.dismissed_contents)),
            voice_and_video=VoiceAndVideoSettings(
                afk_timeout=AfkTimeout(value=self.get("afk_timeout", 600)),
                stream_notifications_enabled=StreamNotificationsEnabled(
                    value=bool(self.get("stream_notifications_enabled", True))
                )
            ),
            text_and_images=TextAndImagesSettings(
                use_rich_chat_input=UseRichChatInput(value=self.get("use_rich_chat_input", True)),
                use_thread_sidebar=UseThreadSidebar(value=self.get("use_thread_sidebar", True)),
                render_spoilers=RenderSpoilers(value=self.get("render_spoilers", "ON_CLICK")),
                inline_attachment_media=InlineAttachmentMedia(value=self.get("inline_attachment_media", True)),
                inline_embed_media=InlineEmbedMedia(value=self.get("inline_embed_media", True)),
                render_embeds=RenderEmbeds(value=self.get("render_embeds", True)),
                render_reactions=RenderReactions(value=self.get("render_reactions", True)),
                explicit_content_filter=ExplicitContentFilter(value=self.get("explicit_content_filter", True)),
                view_nsfw_guilds=ViewNsfwGuilds(value=self.get("view_nsfw_guilds", False)),
                convert_emoticons=ConvertEmoticons(value=self.get("convert_emoticons", True)),
                animate_stickers=AnimateStickers(value=self.get("animate_stickers", 1)),
                expression_suggestions_enabled=ExpressionSuggestionsEnabled(value=self.get("expression_suggestions_enabled", True)),
                message_display_compact=MessageDisplayCompact(value=self.get("message_display_compact", False)),
                view_image_descriptions=ViewImageDescriptions(value=self.get("view_image_descriptions", False))
            ),
            privacy=PrivacySettings(
                friend_source_flags=FriendSourceFlags(value=14),
                default_guilds_restricted=self.get("default_guilds_restricted", False),
                allow_accessibility_detection=self.get("allow_accessibility_detection", False)
            ),
            status=StatusSettings(
                status=Status(status=self.get("status", "online")),
                show_current_game=ShowCurrentGame(value=bool(self.get("show_current_game", True)))
            ),
            localization=LocalizationSettings(
                locale=Locale(locale_code=self.get("locale", "en_US")),
                timezone_offset=TimezoneOffset(offset=self.get("timezone_offset", 0))
            ),
            appearance=AppearanceSettings(
                theme=Theme.DARK if self.get("theme", "dark") == "dark" else Theme.LIGHT,
                developer_mode=bool(self.get("developer_mode", False))
            )
        )
        if d := self.get("friend_source_flags"):
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

    def from_proto(self, proto):
        self.set(
            inline_attachment_media=proto_get(proto, "text_and_images.inline_attachment_media.value"),
            show_current_game=proto_get(proto, "status.show_current_game.value"),
            view_nsfw_guilds=proto_get(proto, "text_and_images.view_nsfw_guilds.value"),
            enable_tts_command=proto_get(proto, "text_and_images.enable_tts_command.value"),
            render_reactions=proto_get(proto, "text_and_images.render_reactions.value"),
            gif_auto_play=proto_get(proto, "text_and_images.gif_auto_play.value"),
            stream_notifications_enabled=proto_get(proto, "voice_and_video.stream_notifications_enabled.value"),
            animate_emoji=proto_get(proto, "text_and_images.animate_emoji.value"),
            afk_timeout=proto_get(proto, "voice_and_video.afk_timeout.value"),
            view_nsfw_commands=proto_get(proto, "text_and_images.view_nsfw_commands.value"),
            detect_platform_accounts=proto_get(proto, "privacy.detect_platform_accounts.value"),
            explicit_content_filter=proto_get(proto, "text_and_images.explicit_content_filter.value"),
            status=proto_get(proto, "status.status.status"),
            default_guilds_restricted=proto_get(proto, "privacy.default_guilds_restricted"),
            theme="dark" if proto_get(proto, "appearance.theme", 1) == 1 else "light",
            allow_accessibility_detection=proto_get(proto, "privacy.allow_accessibility_detection"),
            locale=proto_get(proto, "localization.locale.locale_code"),
            native_phone_integration_enabled=proto_get(proto, "voice_and_video.native_phone_integration_enabled.value"),
            timezone_offset=proto_get(proto, "localization.timezone_offset.offset"),
            friend_discovery_flags=proto_get(proto, "privacy.friend_discovery_flags.value"),
            contact_sync_enabled=proto_get(proto, "privacy.contact_sync_enabled.value"),
            disable_games_tab=proto_get(proto, "game_library.disable_games_tab.value"),
            developer_mode=proto_get(proto, "appearance.developer_mode"),
            render_embeds=proto_get(proto, "text_and_images.render_embeds.value"),
            animate_stickers=proto_get(proto, "text_and_images.animate_stickers.value"),
            message_display_compact=proto_get(proto, "text_and_images.message_display_compact.value"),
            convert_emoticons=proto_get(proto, "text_and_images.convert_emoticons.value"),
            passwordless=proto_get(proto, "privacy.passwordless.value"),
            activity_restricted_guild_ids=proto_get(proto, "privacy.activity_restricted_guild_ids"),
            restricted_guilds=proto_get(proto, "privacy.restricted_guild_ids"),
            render_spoilers=proto_get(proto, "text_and_images.render_spoilers.value"),
            inline_embed_media=proto_get(proto, "text_and_images.inline_embed_media.value"),
            use_thread_sidebar=proto_get(proto, "text_and_images.use_thread_sidebar.value"),
            use_rich_chat_input=proto_get(proto, "text_and_images.use_rich_chat_input.value"),
            expression_suggestions_enabled=proto_get(proto, "text_and_images.expression_suggestions_enabled.value"),
            view_image_descriptions=proto_get(proto, "text_and_images.view_image_descriptions.value"),
        )
        if proto_get(proto, "status.custom_status") is not None:
            cs = {}
            custom_status = proto_get(proto, "status.custom_status")
            cs["text"] = proto_get(custom_status, "text", None)
            cs["emoji_id"] = proto_get(custom_status, "emoji_id", None)
            cs["emoji_name"] = proto_get(custom_status, "emoji_name", None)
            cs["expires_at_ms"] = proto_get(custom_status, "expires_at_ms", None)
            self.set(custom_status=cs)
        if (p := proto_get(proto, "privacy.friend_source_flags.value")) is not None:
            if p == 14:
                self.set(friend_source_flags={"all": True})
            elif p == 6:
                self.set(friend_source_flags={"all": False, "mutual_friends": True, "mutual_guilds": True})
            elif p == 4:
                self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": True})
            elif p == 2:
                self.set(friend_source_flags={"all": False, "mutual_friends": True, "mutual_guilds": False})
            else:
                self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": True})
        else:
            self.set(friend_source_flags={"all": False, "mutual_friends": False, "mutual_guilds": False})
        if (p := proto_get(proto, "user_content.dismissed_contents")) is not None:
            self.set(dismissed_contents=p[:64].hex())
        self.__post_init__()
        return self

@model
@dataclass
class UserData(Model):
    uid: int = field(id_field=True)
    birth: Optional[str] = None
    username: Optional[str] = None
    discriminator: Optional[int] = None
    bio: Optional[str] = None
    flags: Optional[int] = None
    public_flags: Optional[int] = None
    phone: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    premium: Optional[bool] = field(validation=Or(Use(bool), NoneType), default=None, nullable=True)
    accent_color: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)
    avatar: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    avatar_decoration: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    banner: Optional[str] = field(validation=Or(str, NoneType), default=None, nullable=True)
    banner_color: Optional[int] = field(validation=Or(int, NoneType), default=None, nullable=True)

    @property
    async def json(self) -> dict:
        return {
            "id": str(self.uid),
            "username": self.username,
            "avatar": self.avatar,
            "avatar_decoration": self.avatar_decoration,
            "discriminator": self.s_discriminator,
            "public_flags": self.public_flags
        }

    @property
    def s_discriminator(self) -> str:
        return str(self.discriminator).rjust(4, "0")

    @property
    def nsfw_allowed(self) -> bool:
        db = datetime.strptime(self.birth, "%Y-%m-%d")
        dn = datetime.utcnow()
        return dn-db > timedelta(days=18*365+4)

@model
@dataclass
class User(_User, Model):
    id: int = field(id_field=True)
    email: Optional[str] = field(validation=And(
        Use(str),
        Use(str.lower), lambda s: Regex(r'^[a-z0-9_\.]{1,64}@[a-zA-Z-_\.]{2,250}?\.[a-zA-Z]{2,6}$').validate(s)),
        default=None)
    password: Optional[str] = None
    key: Optional[str] = None
    verified: Optional[bool] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self._uSettings = None
        self._uData = None
        self._uFrecencySettings = None

    @property
    async def settings(self) -> UserSettings:
        if not self._uSettings:
            self._uSettings = await getCore().getUserSettings(self)
        return self._uSettings

    @property
    async def data(self) -> UserData:
        return await self.userdata

    @property
    async def userdata(self) -> UserData:
        if not self._uData:
            self._uData = await getCore().getUserData(self)
        return self._uData

    @property
    async def settings_proto(self) -> PreloadedUserSettings:
        settings = await self.settings
        return settings.to_proto()

    @property
    async def frecency_settings_proto(self) -> bytes:
        if not self._uFrecencySettings:
            self._uFrecencySettings = await getCore().getFrecencySettings(self)
        return b64decode(self._uFrecencySettings.encode("utf8"))

@model
@dataclass
class Relationship(Model):
    u1: int
    u2: int
    type: int

    def discord_type(self, current_uid: int) -> int:
        t: int = self.type
        if t == RelationshipType.PENDING:
            if self.u1 == current_uid:
                return 4
            else:
                return 3
        return t

@model
@dataclass
class UserNote(Model):
    user_id: int = field(db_name="uid")
    note_user_id: int = field(db_name="target_uid")
    note: str = field(validation=Or(Use(str), NoneType), nullable=True)

class UserFlags:
    def __init__(self, value: int):
        self.value = value
        self.parsedFlags = self.parseFlags(value)

    @staticmethod
    def parseFlags(value: int) -> list:
        flags = []
        for val in UserFlagsE.values().values():
            if (value & val) == val:
                flags.append(val)
        return flags

    def add(self, val: int):
        if val not in self.parsedFlags:
            self.value += val
            self.parsedFlags.append(val)
        return self

    def remove(self, val: int):
        if val in self.parsedFlags:
            self.value -= val
            self.parsedFlags.remove(val)
        return self

class PermissionsChecker:
    def __init__(self, member: GuildMember):
        self.member = member

    async def check(self, *check_permissions, channel: Optional[Channel]=None) -> None:
        def _check(perms: int, perm: int) -> bool:
            return (perms & perm) == perm
        guild = await getCore().getGuild(self.member.guild_id)
        if guild.owner_id == self.member.user_id:
            return
        permissions = await self.member.permissions
        if _check(permissions, GuildPermissions.ADMINISTRATOR):
            return
        if channel:
            overwrites = await getCore().getOverwritesForMember(channel, self.member)
            for overwrite in overwrites:
                permissions &= ~overwrite.deny
                permissions |= overwrite.allow

        for permission in check_permissions:
            if not _check(permissions, permission):
                raise InvalidDataErr(403, Errors.make(50013))

    async def canKickOrBan(self, target_member: GuildMember) -> bool:
        if self.member.user_id == target_member.user_id:
            return False
        guild = await getCore().getGuild(self.member.guild_id)
        if target_member.user_id == guild.owner_id:
            return False
        if self.member.user_id == guild.owner_id:
            return True
        self_top_role = await self.member.top_role
        target_top_role = await target_member.top_role
        if self_top_role.position <= target_top_role.position:
            return False
        return True

    async def canChangeRolesPositions(self, roles_changes: dict, current_roles: Optional[List[Role]]=None) -> bool:
        guild = await getCore().getGuild(self.member.guild_id)
        if self.member.user_id == guild.owner_id:
            return True
        roles_ids = {role.id: role for role in current_roles}
        top_role = await self.member.top_role
        for role_change in roles_changes:
            role_id = int(role_change["id"])
            position = role_change["position"]
            if roles_ids[role_id].position >= top_role.position or position >= top_role.position:
                return False
        return True

@model
@dataclass
class GuildMember(_User, Model):
    user_id: int
    guild_id: int
    joined_at: int
    avatar: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    communication_disabled_until: Optional[int] = field(default=None, nullable=True, validation=Or(int, NoneType))
    flags: Optional[int] = None
    nick: Optional[str] = field(default=None, nullable=True, validation=Or(str, NoneType))
    mute: Optional[bool] = False
    deaf: Optional[bool] = False

    @property
    async def json(self) -> dict:
        userdata = await getCore().getUserData(UserId(self.user_id))
        data = {
            "avatar": self.avatar,
            "communication_disabled_until": self.communication_disabled_until,
            "flags": self.flags,
            "joined_at": datetime.utcfromtimestamp(self.joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "nick": self.nick,
            "is_pending": False,  # TODO
            "pending": False,  # TODO
            "premium_since": Snowflake.toDatetime(userdata.uid).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "roles": [str(role) for role in await getCore().getMemberRolesIds(self)],
            "user": await userdata.json,
            "mute": self.mute,
            "deaf": self.deaf
        }
        return data

    @property
    async def data(self) -> UserData:
        _user = User(self.user_id)
        d = await _user.data
        if self.avatar:
            d.avatar = self.avatar
        return d

    @property
    def id(self) -> int:
        return self.user_id

    @property
    def perm_checker(self) -> PermissionsChecker:
        return PermissionsChecker(self)

    @property
    async def user(self) -> User:
        return await getCore().getUser(self.user_id)

    @property
    async def roles(self) -> List[Role]:
        return await getCore().getMemberRoles(self)

    @property
    async def roles_w_default(self) -> List[Role]:
        return await getCore().getMemberRoles(self, True)

    @property
    async def top_role(self) -> Role:
        if not (roles := await self.roles):
            return await getCore().getRole(self.guild_id)
        return roles[-1]

    async def checkPermission(self, *check_permissions, channel: Optional[Channel]=None) -> None:
        return await self.perm_checker.check(*check_permissions, channel=channel)

    @property
    async def permissions(self) -> int:
        permissions = 0
        for role in await self.roles_w_default:
            permissions |= role.permissions
        return permissions