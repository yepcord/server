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
  `phone` longtext default null,
  `premium` bool default true,
  `accent_color` longtext default null,
  `avatar` longtext default null,
  `avatar_decoration` longtext default null,
  `banner` longtext default null,
  `banner_color` longtext default null,
  `bio` longtext default null,
  `flags` bigint default null,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `sessions`;
CREATE TABLE `sessions` (
  `uid` bigint not null,
  `sid` bigint not null,
  `key` longtext not null,
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
  `status` text not null default "online",
  `explicit_content_filter` bigint not null default 1,
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
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;