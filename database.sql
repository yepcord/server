DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` bigint not null,
  `email` longtext not null,
  `password` longtext not null,
  `key` longtext not null,
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `userdata`;
CREATE TABLE `userdata` (
  `uid` bigint not null,
  `birth` longtext not null,
  `username` longtext not null,
  `discriminator` int not null,
  `phone` longtext default null,
  `accent_color` bigint default null,
  `avatar` longtext default null,
  `avatar_decoration` longtext default null,
  `banner` longtext default null,
  `banner_color` bigint default null,
  `bio` longtext not null default "",
  `flags` bigint default 0,
  `public_flags` bigint default 0,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `sessions`;
CREATE TABLE `sessions` (
  `uid` bigint not null,
  `sid` bigint not null,
  `sig` longtext not null
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `relationships`;
CREATE TABLE `relationships` (
  `u1` bigint not null,
  `u2` bigint not null,
  `type` int not null
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `uid` bigint not null,
  `inline_attachment_media` bool not null default true,
  `show_current_game` bool not null default true,
  `view_nsfw_guilds` bool not null default false,
  `enable_tts_command` bool not null default true,
  `render_reactions` bool not null default true,
  `gif_auto_play` bool not null default true,
  `stream_notifications_enabled` bool not null default true,
  `animate_emoji` bool not null default true,
  `afk_timeout` bigint not null default 600,
  `view_nsfw_commands` bool not null default false,
  `detect_platform_accounts` bool not null default true,
  `explicit_content_filter` int not null default 1,
  `custom_status` longtext default null,
  `default_guilds_restricted` bool not null default false,
  `theme` text not null default "dark",
  `allow_accessibility_detection` bool not null default false,
  `locale` text not null default "ru",
  `native_phone_integration_enabled` bool not null default true,
  `timezone_offset` int not null default 0,
  `friend_discovery_flags` bigint not null default 0,
  `contact_sync_enabled` bool not null default false,
  `disable_games_tab` bool not null default false,
  `developer_mode` bool not null default false,
  `render_embeds` bool not null default true,
  `animate_stickers` bigint not null default 0,
  `message_display_compact` bool not null default false,
  `convert_emoticons` bool not null default true,
  `passwordless` bool not null default true,
  `mfa` text default null,

  `j_activity_restricted_guild_ids` JSON not null default "[]",
  `j_friend_source_flags` JSON not null default '{"all": true}',
  `j_guild_positions` JSON not null default "[]",
  `j_guild_folders` JSON not null default "[]",
  `j_restricted_guilds` JSON not null default "[]",

  `personalization` bool not null default false,
  `usage_statistics` bool not null default false,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `mfa_codes`;
CREATE TABLE `mfa_codes` (
  `uid` bigint not null,
  `code` text not null,
  `used` bool not null default false
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `channels`;
CREATE TABLE `channels` (
  `id` bigint not null,
  `type` int not null,
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `dm_channels`;
CREATE TABLE `dm_channels` (
  `id` bigint not null,
  `recipients` JSON not null default "[]",
  `name` text default null,
  `icon` text default null,
  `owner_id` bigint default null,
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
  `id` bigint not null,
  `content` longtext default null,
  `channel_id` bigint not null,
  `author` bigint not null,
  `edit_timestamp` bigint default null,
  `attachments` JSON not null default "[]",
  `embeds` JSON not null default "[]",
  `reactions` JSON not null default "[]",
  `pinned` bool not null default false,
  `webhook_id` bigint default null,
  `application_id` bigint default null,
  `type` int default 0,
  `flags` int default 0,
  `message_reference` bigint default null,
  `thread` bigint default null,
  `components` JSON not null default "[]",
  `sticker_items` JSON not null default "[]",
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `presences`;
CREATE TABLE `presences` (
  `uid` bigint not null,
  `status` text not null default "online",
  `online` bool not null default true,
  `modified` bigint not null default 0,
  `activities` JSON not null default "[]",
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;