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
from typing import Any


class E:
    __values = None
    __reversed = None
    __values_set = None

    @classmethod
    def values(cls):
        if cls.__values is None:
            attrs = [i for i in cls.__dict__.keys() if not i.startswith("__")]
            cls.__values = {attr: getattr(cls, attr) for attr in attrs}

        return cls.__values

    @classmethod
    def reversed(cls):
        if cls.__reversed is None:
            values = cls.values()
            cls.__reversed = {v: k for k, v in values.items()}

        return cls.__reversed

    @classmethod
    def values_set(cls) -> set[Any]:
        if cls.__values_set is None:
            cls.__values_set = set(cls.values().values())

        return cls.__values_set


class RelationshipType(E):
    PENDING = 0
    FRIEND = 1
    BLOCK = 2


class RelTypeDiscord(E):
    FRIEND = 1
    BLOCK = 2
    REQUEST_RECV = 3
    REQUEST_SENT = 4


class GatewayOp(E):
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    STATUS = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    GUILD_MEMBERS = 8
    INV_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12
    UNKNOWN = 13
    LAZY_REQUEST = 14


class ChannelType(E):
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_NEWS = 5
    GUILD_NEWS_THREAD = 10
    GUILD_PUBLIC_THREAD = 11
    GUILD_PRIVATE_THREAD = 12
    GUILD_STAGE_VOICE = 13
    GUILD_DIRECTORY = 14


GUILD_CHANNELS = (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY, ChannelType.GUILD_NEWS)


class MessageType(E):
    DEFAULT = 0
    RECIPIENT_ADD = 1
    RECIPIENT_REMOVE = 2
    CALL = 3
    CHANNEL_NAME_CHANGE = 4
    CHANNEL_ICON_CHANGE = 5
    CHANNEL_PINNED_MESSAGE = 6
    USER_JOIN = 7
    GUILD_BOOST = 8
    GUILD_BOOST_TIER_1 = 9
    GUILD_BOOST_TIER_2 = 10
    GUILD_BOOST_TIER_3 = 11
    CHANNEL_FOLLOW_ADD = 12
    GUILD_DISCOVERY_DISQUALIFIED = 14
    GUILD_DISCOVERY_REQUALIFIED = 15
    GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING = 16
    GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING = 17
    THREAD_CREATED = 18
    REPLY = 19
    CHAT_INPUT_COMMAND = 20
    THREAD_STARTER_MESSAGE = 21
    GUILD_INVITE_REMINDER = 22
    CONTEXT_MENU_COMMAND = 23
    AUTO_MODERATION_ACTION = 24


# https://discord.com/developers/docs/resources/user#user-object-user-flags
class UserFlags(E):
    STAFF = 1 << 0
    PARTNER = 1 << 1
    HYPESQUAD_EVENTS = 1 << 2
    BUG_HUNTER_LEVEL_1 = 1 << 3
    # MFA_SMS = 1 << 4 # Unused
    # PREMIUM_PROMO_DISMISSED = 1 << 5 # Unused
    HYPESQUAD_ONLINE_HOUSE_1 = 1 << 6
    HYPESQUAD_ONLINE_HOUSE_2 = 1 << 7
    HYPESQUAD_ONLINE_HOUSE_3 = 1 << 8
    PREMIUM_EARLY_SUPPORTER = 1 << 9
    TEAM_PSEUDO_USER = 1 << 10
    # INTERNAL_APPLICATION = 1 << 11 # Unused
    # SYSTEM = 1 << 12 # Unused
    # HAS_UNREAD_URGENT_MESSAGES = 1 << 13 # Unused
    BUG_HUNTER_LEVEL_2 = 1 << 14
    # UNDERAGE_DELETED = 1 << 15 # Unused
    VERIFIED_BOT = 1 << 16
    VERIFIED_DEVELOPER = 1 << 17
    CERTIFIED_MODERATOR = 1 << 18
    BOT_HTTP_INTERACTIONS = 1 << 19
    ACTIVE_DEVELOPER = 1 << 22


# https://discord.com/developers/docs/topics/permissions#permissions-bitwise-permission-flags
class GuildPermissions(E):
    CREATE_INSTANT_INVITE = 1 << 0
    KICK_MEMBERS = 1 << 1
    BAN_MEMBERS = 1 << 2
    ADMINISTRATOR = 1 << 3
    MANAGE_CHANNELS = 1 << 4
    MANAGE_GUILD = 1 << 5
    ADD_REACTIONS = 1 << 6
    VIEW_AUDIT_LOG = 1 << 7
    PRIORITY_SPEAKER = 1 << 8
    STREAM = 1 << 9
    VIEW_CHANNEL = 1 << 10
    SEND_MESSAGES = 1 << 11
    SEND_TTS_MESSAGES = 1 << 12
    MANAGE_MESSAGES = 1 << 13
    EMBED_LINKS = 1 << 14
    ATTACH_FILES = 1 << 15
    READ_MESSAGE_HISTORY = 1 << 16
    MENTION_EVERYONE = 1 << 17
    USE_EXTERNAL_EMOJIS = 1 << 18
    VIEW_GUILD_INSIGHTS = 1 << 19
    CONNECT = 1 << 20
    SPEAK = 1 << 21
    MUTE_MEMBERS = 1 << 22
    DEAFEN_MEMBERS = 1 << 23
    MOVE_MEMBERS = 1 << 24
    USE_VAD = 1 << 25
    CHANGE_NICKNAME = 1 << 26
    MANAGE_NICKNAMES = 1 << 27
    MANAGE_ROLES = 1 << 28
    MANAGE_WEBHOOKS = 1 << 29
    MANAGE_EMOJIS_AND_STICKERS = 1 << 30
    USE_APPLICATION_COMMANDS = 1 << 31
    REQUEST_TO_SPEAK = 1 << 32
    MANAGE_EVENTS = 1 << 33
    MANAGE_THREADS = 1 << 34
    CREATE_PUBLIC_THREADS = 1 << 35
    CREATE_PRIVATE_THREADS = 1 << 36
    USE_EXTERNAL_STICKERS = 1 << 37
    SEND_MESSAGES_IN_THREADS = 1 << 38
    USE_EMBEDDED_ACTIVITIES = 1 << 39
    MODERATE_MEMBERS = 1 << 40


# https://discord.com/developers/docs/resources/audit-log#audit-log-entry-object-audit-log-events
class AuditLogEntryType(E):
    GUILD_UPDATE = 1
    CHANNEL_CREATE = 10
    CHANNEL_UPDATE = 11
    CHANNEL_DELETE = 12
    CHANNEL_OVERWRITE_CREATE = 13
    CHANNEL_OVERWRITE_UPDATE = 14
    CHANNEL_OVERWRITE_DELETE = 15
    MEMBER_KICK = 20
    MEMBER_PRUNE = 21
    MEMBER_BAN_ADD = 22
    MEMBER_BAN_REMOVE = 23
    MEMBER_UPDATE = 24
    MEMBER_ROLE_UPDATE = 25
    MEMBER_MOVE = 26
    MEMBER_DISCONNECT = 27
    BOT_ADD = 28
    ROLE_CREATE = 30
    ROLE_UPDATE = 31
    ROLE_DELETE = 32
    INVITE_CREATE = 40
    INVITE_UPDATE = 41
    INVITE_DELETE = 42
    WEBHOOK_CREATE = 50
    WEBHOOK_UPDATE = 51
    WEBHOOK_DELETE = 52
    EMOJI_CREATE = 60
    EMOJI_UPDATE = 61
    EMOJI_DELETE = 62
    MESSAGE_DELETE = 72
    MESSAGE_BULK_DELETE = 73
    MESSAGE_PIN = 74
    MESSAGE_UNPIN = 75
    INTEGRATION_CREATE = 80
    INTEGRATION_UPDATE = 81
    INTEGRATION_DELETE = 82
    STAGE_INSTANCE_CREATE = 83
    STAGE_INSTANCE_UPDATE = 84
    STAGE_INSTANCE_DELETE = 85
    STICKER_CREATE = 90
    STICKER_UPDATE = 91
    STICKER_DELETE = 92
    GUILD_SCHEDULED_EVENT_CREATE = 100
    GUILD_SCHEDULED_EVENT_UPDATE = 101
    GUILD_SCHEDULED_EVENT_DELETE = 102
    THREAD_CREATE = 110
    THREAD_UPDATE = 111
    THREAD_DELETE = 112
    APPLICATION_COMMAND_PERMISSION_UPDATE = 121
    AUTO_MODERATION_RULE_CREATE = 140
    AUTO_MODERATION_RULE_UPDATE = 141
    AUTO_MODERATION_RULE_DELETE = 142
    AUTO_MODERATION_BLOCK_MESSAGE = 143
    AUTO_MODERATION_FLAG_TO_CHANNEL = 144
    AUTO_MODERATION_USER_COMMUNICATION_DISABLED = 145


# https://discord.com/developers/docs/resources/webhook#webhook-object-webhook-types
class WebhookType(E):
    INCOMING = 1
    CHANNEL_FOLLOWER = 2
    APPLICATION = 3


# https://discord.com/developers/docs/resources/guild#guild-object-system-channel-flags
class SystemChannelFlags(E):
    SUPPRESS_JOIN_NOTIFICATIONS = 1 << 0
    SUPPRESS_PREMIUM_SUBSCRIPTIONS = 1 << 1
    SUPPRESS_GUILD_REMINDER_NOTIFICATIONS = 1 << 2
    SUPPRESS_JOIN_NOTIFICATION_REPLIES = 1 << 3
    SUPPRESS_ROLE_SUBSCRIPTION_PURCHASE_NOTIFICATIONS = 1 << 4
    SUPPRESS_ROLE_SUBSCRIPTION_PURCHASE_NOTIFICATION_REPLIES = 1 << 5


# https://discord.com/developers/docs/resources/sticker#sticker-object-sticker-types
class StickerType(E):
    STANDART = 1
    GUILD = 2


# https://discord.com/developers/docs/resources/sticker#sticker-object-sticker-types
class StickerFormat(E):
    PNG = 1
    APNG = 2
    LOTTIE = 3
    GIF = 4


# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-entity-types
class ScheduledEventEntityType(E):
    STAGE_INSTANCE = 1
    VOICE = 2
    EXTERNAL = 3


# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
class ScheduledEventStatus(E):
    SCHEDULED = 1
    ACTIVE = 2
    COMPLETED = 3
    CANCELED = 4


class ApplicationScope(E):
    ACTIVITIES_READ = "activities.read"
    ACTIVITIES_WRITE = "activities.write"
    APPLICATIONS_BUILDS_READ = "applications.builds.read"
    APPLICATIONS_BUILDS_WRITE = "applications.builds.upload"
    APPLICATIONS_COMMANDS = "applications.commands"
    APPLICATIONS_COMMANDS_UPDATE = "applications.commands.update"
    APPLICATIONS_COMMANDS_PERMISSIONS = "applications.commands.permissions.update"
    APPLICATIONS_ENTIITLEMENTS = "applications.entitlements"
    APPLICATIONS_STORE_UPDATE = "applications.store.update"
    BOT = "bot"
    CONNECTIONS = "connections"
    DM_CHANNELS_READ = "dm_channels.read"
    EMAIL = "email"
    GDM_JOIN = "gdm.join"
    GUILDS = "guilds"
    GUILDS_JOIN = "guilds.join"
    GUILDS_MEMBERS = "guilds.members.read"
    IDENTIFY = "identify"
    MESSAGES_READ = "messages.read"
    RELATIONSHIPS_READ = "relationships.read"
    ROLE_CONNECTIONS_WRITE = "role_connections.write"
    RPC = "rpc"
    RPC_ACTIVITIES_WRITE = "rpc.activities.write"
    RPC_NOTIFICATIONS_READ = "rpc.notifications.read"
    RPC_VOICE_READ = "rpc.voice.read"
    RPC_VOICE_WRITE = "rpc.voice.write"
    VOICE = "voice"
    WEBHOOK_INCOMING = "webhook.incoming"


class ApplicationCommandType(E):
    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionType(E):
    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


class Locales(E):
    INDONESIAN = "id"
    DANISH = "da"
    GERMAN = "de"
    ENGLISH_UK = "en-GB"
    ENGLISH_US = "en-US"
    SPANISH = "es-ES"
    FRENCH = "fr"
    CROATIAN = "hr"
    ITALIAN = "it"
    LITHUANIAN = "lt"
    HUNGARIAN = "hu"
    DUTCH = "nl"
    NORWEGIAN = "no"
    POLISH = "pl"
    PORTUGUESE = "pt-BR"
    ROMANIAN = "ro"
    FINNISH = "fi"
    SWEDISH = "sv-SE"
    VIETNAMESE = "vi"
    TURKISH = "tr"
    CZECH = "cs"
    GREEK = "el"
    BULGARIAN = "bg"
    RUSSIAN = "ru"
    UKRAINIAN = "uk"
    HINDI = "hi"
    THAI = "th"
    CHINESE_CHINA = "zh-CN"
    JAPANESE = "ja"
    CHINESE_TAIWAN = "zh-TW"
    KOREAN = "ko"


class InteractionType(E):
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class InteractionStatus(E):
    PENDING = 1
    RESPONDED = 2
    FAILED = 3
    DEFERRED = 4


class MessageFlags(E):
    CROSSPOSTED = 1 << 0
    IS_CROSSPOST = 1 << 1
    SUPPRESS_EMBEDS = 1 << 2
    SOURCE_MESSAGE_DELETED = 1 << 3
    URGENT = 1 << 4
    HAS_THREAD = 1 << 5
    EPHEMERAL = 1 << 6
    LOADING = 1 << 7
    FAILED_TO_MENTION_SOME_ROLES_IN_THREAD = 1 << 8
    SUPPRESS_NOTIFICATIONS = 1 << 12
    IS_VOICE_MESSAGE = 1 << 13


class InteractionCallbackType:
    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFFERED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9
    PREMIUM_REQUIRED = 10
