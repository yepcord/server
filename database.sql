DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` bigint NOT NULL,
  `email` longtext NOT NULL,
  `password` longtext NOT NULL,
  `key` longtext NOT NULL,
  `verified` bool NOT NULL DEFAULT false,
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `userdata`;
CREATE TABLE `userdata` (
  `uid` bigint NOT NULL,
  `birth` longtext NOT NULL,
  `username` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `discriminator` int NOT NULL,
  `phone` longtext DEFAULT NULL,
  `premium` bool DEFAULT NULL,
  `accent_color` bigint DEFAULT NULL,
  `avatar` longtext DEFAULT NULL,
  `avatar_decoration` longtext DEFAULT NULL,
  `banner` longtext DEFAULT NULL,
  `banner_color` bigint DEFAULT NULL,
  `bio` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT "",
  `flags` bigint DEFAULT 0,
  `public_flags` bigint DEFAULT 0,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `sessions`;
CREATE TABLE `sessions` (
  `uid` bigint NOT NULL,
  `sid` bigint NOT NULL,
  `sig` longtext NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `relationships`;
CREATE TABLE `relationships` (
  `u1` bigint NOT NULL,
  `u2` bigint NOT NULL,
  `type` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `uid` bigint NOT NULL,
  `inline_attachment_media` bool NOT NULL DEFAULT true,
  `show_current_game` bool NOT NULL DEFAULT true,
  `view_nsfw_guilds` bool NOT NULL DEFAULT false,
  `enable_tts_command` bool NOT NULL DEFAULT true,
  `render_reactions` bool NOT NULL DEFAULT true,
  `gif_auto_play` bool NOT NULL DEFAULT true,
  `stream_notifications_enabled` bool NOT NULL DEFAULT true,
  `animate_emoji` bool NOT NULL DEFAULT true,
  `afk_timeout` bigint NOT NULL DEFAULT 600,
  `view_nsfw_commands` bool NOT NULL DEFAULT false,
  `detect_platform_accounts` bool NOT NULL DEFAULT true,
  `explicit_content_filter` int NOT NULL DEFAULT 1,
  `status` longtext NOT NULL DEFAULT "online",
  `j_custom_status` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL CHECK(json_valid(`j_custom_status`)),
  `default_guilds_restricted` bool NOT NULL DEFAULT false,
  `theme` text NOT NULL DEFAULT "dark",
  `allow_accessibility_detection` bool NOT NULL DEFAULT false,
  `locale` text NOT NULL DEFAULT "en-US",
  `native_phone_integration_enabled` bool NOT NULL DEFAULT true,
  `timezone_offset` int NOT NULL DEFAULT 0,
  `friend_discovery_flags` bigint NOT NULL DEFAULT 0,
  `contact_sync_enabled` bool NOT NULL DEFAULT false,
  `disable_games_tab` bool NOT NULL DEFAULT false,
  `developer_mode` bool NOT NULL DEFAULT false,
  `render_embeds` bool NOT NULL DEFAULT true,
  `animate_stickers` bigint NOT NULL DEFAULT 0,
  `message_display_compact` bool NOT NULL DEFAULT false,
  `convert_emoticons` bool NOT NULL DEFAULT true,
  `passwordless` bool NOT NULL DEFAULT true,
  `mfa` text DEFAULT NULL,

  `j_activity_restricted_guild_ids` JSON NOT NULL DEFAULT "[]",
  `j_friend_source_flags` JSON NOT NULL DEFAULT '{"all": true}',
  `j_guild_positions` JSON NOT NULL DEFAULT "[]",
  `j_guild_folders` JSON NOT NULL DEFAULT "[]",
  `j_restricted_guilds` JSON NOT NULL DEFAULT "[]",

  `personalization` bool NOT NULL DEFAULT false,
  `usage_statistics` bool NOT NULL DEFAULT false,

  `render_spoilers` text NOT NULL DEFAULT "ON_CLICK",
  `inline_embed_media` bool NOT NULL DEFAULT true,
  `use_thread_sidebar` bool NOT NULL DEFAULT true,
  `use_rich_chat_input` bool NOT NULL DEFAULT true,
  `expression_suggestions_enabled` bool NOT NULL DEFAULT true,
  `view_image_descriptions` bool NOT NULL DEFAULT true,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `mfa_codes`;
CREATE TABLE `mfa_codes` (
  `uid` bigint NOT NULL,
  `code` text NOT NULL,
  `used` bool NOT NULL DEFAULT false
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `channels`;
CREATE TABLE `channels` (
  `id` bigint NOT NULL,
  `type` int NOT NULL,
  `guild_id` bigint DEFAULT NULL,
  `position` int DEFAULT NULL,
  `j_permission_overwrites` JSON DEFAULT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `topic` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `nsfw` bool DEFAULT NULL,
  `bitrate` int DEFAULT NULL,
  `user_limit` int DEFAULT NULL,
  `rate_limit` int DEFAULT NULL,
  `j_recipients` JSON DEFAULT NULL,
  `icon` text DEFAULT NULL,
  `owner_id` bigint DEFAULT NULL,
  `application_id` bigint DEFAULT NULL,
  `parent_id` bigint DEFAULT NULL,
  `rtc_region` text DEFAULT NULL,
  `video_quality_mode` int DEFAULT NULL,
  `j_thread_metadata` JSON DEFAULT NULL,
  `default_auto_archive` int DEFAULT NULL,
  `flags` int DEFAULT NULL,
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
  `id` bigint NOT NULL,
  `content` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `channel_id` bigint NOT NULL,
  `author` bigint NOT NULL,
  `edit_timestamp` bigint DEFAULT NULL,
  `j_attachments` JSON NOT NULL DEFAULT "[]",
  `j_embeds` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT "[]" CHECK(json_valid(`j_embeds`)),
  `pinned` bool NOT NULL DEFAULT false,
  `webhook_id` bigint DEFAULT NULL,
  `application_id` bigint DEFAULT NULL,
  `type` int DEFAULT 0,
  `flags` int DEFAULT 0,
  `message_reference` bigint DEFAULT NULL,
  `thread` bigint DEFAULT NULL,
  `j_components` JSON NOT NULL DEFAULT "[]",
  `j_sticker_items` JSON NOT NULL DEFAULT "[]",
  `j_extra_data` JSON NOT NULL DEFAULT "{}",
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `read_states`;
CREATE TABLE `read_states` (
  `uid` bigint NOT NULL,
  `channel_id` bigint NOT NULL,
  `last_read_id` bigint NOT NULL,
  `count` int NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `notes`;
CREATE TABLE `notes` (
  `uid` bigint NOT NULL,
  `target_uid` bigint NOT NULL,
  `note` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `attachments`;
CREATE TABLE `attachments` (
  `id` bigint NOT NULL,
  `channel_id` bigint NOT NULL,
  `filename` text NOT NULL,
  `size` bigint NOT NULL,
  `uuid` text NOT NULL,
  `content_type` text DEFAULT NULL,
  `uploaded` bool NOT NULL DEFAULT false,
  `j_metadata` JSON NOT NULL DEFAULT "{}",
  UNIQUE KEY `id` (`id`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `connections`;
CREATE TABLE `connections` (
  `uid` bigint NOT NULL,
  `type` text NOT NULL,
  `state` text DEFAULT NULL,
  `username` text DEFAULT NULL,
  `service_uid` bigint DEFAULT NULL,
  `friend_sync` bool NOT NULL DEFAULT false,
  `j_integrations` JSON NOT NULL DEFAULT "[]",
  `visible` bool NOT NULL DEFAULT true,
  `verified` bool NOT NULL DEFAULT true,
  `revoked` bool NOT NULL DEFAULT false,
  `show_activity` bool NOT NULL DEFAULT true,
  `two_way_link` bool NOT NULL DEFAULT false
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `frecency_settings`;
CREATE TABLE `frecency_settings` (
  `uid` bigint NOT NULL,
  `settings` longtext NOT NULL,
  UNIQUE KEY `uid` (`uid`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guild_templates`;
CREATE TABLE `guild_templates` (
  `code` text NOT NULL,
  `template` JSON NOT NULL DEFAULT "{}",
  UNIQUE KEY `code` (`code`) USING HASH
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `reactions`;
CREATE TABLE `reactions` (
  `message_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `emoji_id` bigint DEFAULT NULL,
  `emoji_name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;