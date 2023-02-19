DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` bigint NOT NULL PRIMARY KEY,
  `email` longtext NOT NULL,
  `password` longtext NOT NULL,
  `key` longtext NOT NULL,
  `verified` bool NOT NULL DEFAULT false
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `sessions`;
CREATE TABLE `sessions` (
  `uid` bigint NOT NULL,
  `sid` bigint NOT NULL,
  `sig` longtext NOT NULL,
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
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
  UNIQUE KEY (`uid`),
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
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
  `dismissed_contents` tinytext NOT NULL DEFAULT "510109000002000080",
  UNIQUE KEY `uid` (`uid`),
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `frecency_settings`;
CREATE TABLE `frecency_settings` (
  `uid` bigint NOT NULL,
  `settings` longtext NOT NULL,
  UNIQUE KEY `uid` (`uid`),
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `relationships`;
CREATE TABLE `relationships` (
  `u1` bigint NOT NULL,
  `u2` bigint NOT NULL,
  `type` int NOT NULL,
  FOREIGN KEY (`u1`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`u2`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `mfa_codes`;
CREATE TABLE `mfa_codes` (
  `uid` bigint NOT NULL,
  `code` text NOT NULL,
  `used` bool NOT NULL DEFAULT false,
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guilds`;
CREATE TABLE `guilds` (
  `id` bigint NOT NULL PRIMARY KEY,
  `owner_id` bigint NOT NULL,
  `name` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `icon` text DEFAULT NULL,
  `description` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `splash` text DEFAULT NULL,
  `discovery_splash` text DEFAULT NULL,
  `j_features` JSON NOT NULL DEFAULT "[]",
  `banner` text DEFAULT NULL,
  `region` text NOT NULL DEFAULT "deprecated",
  `afk_channel_id` bigint DEFAULT NULL,
  `afk_timeout` int DEFAULT 300,
  `system_channel_id` bigint NOT NULL,
  `verification_level` int NOT NULL DEFAULT 0,
  `default_message_notifications` int NOT NULL DEFAULT 0,
  `mfa_level` int NOT NULL DEFAULT 0,
  `explicit_content_filter` int NOT NULL DEFAULT 0,
  `max_members` int NOT NULL DEFAULT 100,
  `vanity_url_code` text DEFAULT NULL,
  `system_channel_flags` int NOT NULL DEFAULT 0,
  `preferred_locale` text NOT NULL DEFAULT "en-US",
  `premium_progress_bar_enabled` bool NOT NULL DEFAULT false,
  `nsfw` bool NOT NULL DEFAULT false,
  `nsfw_level` int NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` bigint NOT NULL PRIMARY KEY,
  `guild_id` bigint NOT NULL,
  `name` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `permissions` bigint NOT NULL DEFAULT 1071698660929,
  `position` int NOT NULL DEFAULT 0,
  `color` int NOT NULL DEFAULT 0,
  `hoist` bool NOT NULL DEFAULT false,
  `managed` bool NOT NULL DEFAULT false,
  `mentionable` bool NOT NULL DEFAULT false,
  `icon` text DEFAULT NULL,
  `unicode_emoji` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `flags` int NOT NULL DEFAULT 0,
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guild_members`;
CREATE TABLE `guild_members` (
  `user_id` bigint NOT NULL,
  `guild_id` bigint NOT NULL,
  `joined_at` int NOT NULL,
  `avatar` text DEFAULT NULL,
  `communication_disabled_until` int DEFAULT NULL,
  `flags` int NOT NULL DEFAULT 0,
  `nick` text DEFAULT NULL,
  `mute` bool NOT NULL DEFAULT false,
  `deaf` bool NOT NULL DEFAULT false,
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guild_members_roles`;
CREATE TABLE `guild_members_roles` (
  `guild_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `role_id` bigint NOT NULL,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `emojis`;
CREATE TABLE `emojis` (
  `id` bigint NOT NULL PRIMARY KEY,
  `name` text NOT NULL,
  `user_id` bigint NOT NULL,
  `guild_id` bigint NOT NULL,
  `j_roles` JSON NOT NULL DEFAULT "[]",
  `require_colons` bool NOT NULL DEFAULT true,
  `managed` bool NOT NULL DEFAULT false,
  `animated` bool NOT NULL DEFAULT false,
  `available` bool NOT NULL DEFAULT true,
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guild_bans`;
CREATE TABLE `guild_bans` (
  `user_id` bigint NOT NULL,
  `guild_id` bigint NOT NULL,
  `reason` text DEFAULT NULL,
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `channels`;
CREATE TABLE `channels` (
  `id` bigint NOT NULL PRIMARY KEY,
  `type` int NOT NULL,
  `guild_id` bigint DEFAULT NULL,
  `position` int DEFAULT NULL,
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
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `permission_overwrites`;
CREATE TABLE `permission_overwrites` (
  `channel_id` bigint NOT NULL,
  `target_id` bigint NOT NULL,
  `type` int NOT NULL,
  `allow` bigint NOT NULL,
  `deny` bigint NOT NULL,
  FOREIGN KEY (`channel_id`) REFERENCES `channels`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
  `id` bigint NOT NULL PRIMARY KEY,
  `content` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `channel_id` bigint NOT NULL,
  `author` bigint NOT NULL,
  `edit_timestamp` bigint DEFAULT NULL,
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
  `guild_id` bigint DEFAULT NULL,
  FOREIGN KEY (`channel_id`) REFERENCES `channels`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `attachments`;
CREATE TABLE `attachments` (
  `id` bigint NOT NULL PRIMARY KEY,
  `channel_id` bigint NOT NULL,
  `message_id` bigint NOT NULL,
  `filename` text NOT NULL,
  `size` bigint NOT NULL,
  `uuid` text NOT NULL,
  `content_type` text DEFAULT NULL,
  `uploaded` bool NOT NULL DEFAULT false,
  `j_metadata` JSON NOT NULL DEFAULT "{}",
  FOREIGN KEY (`message_id`) REFERENCES `messages`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `reactions`;
CREATE TABLE `reactions` (
  `message_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `emoji_id` bigint DEFAULT NULL,
  `emoji_name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  FOREIGN KEY (`message_id`) REFERENCES `messages`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `invites`;
CREATE TABLE `invites` (
  `id` bigint NOT NULL PRIMARY KEY,
  `channel_id` bigint NOT NULL,
  `inviter` bigint NOT NULL,
  `created_at` bigint NOT NULL,
  `max_age` bigint NOT NULL,
  `max_uses` bigint NOT NULL DEFAULT 0,
  `uses` bigint NOT NULL DEFAULT 0,
  `vanity_code` text DEFAULT NULL,
  `guild_id` bigint DEFAULT NULL,
  `type` int NOT NULL DEFAULT 1,
  FOREIGN KEY (`channel_id`) REFERENCES `channels`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `guild_audit_log_entries`;
CREATE TABLE `guild_audit_log_entries` (
  `id` bigint NOT NULL PRIMARY KEY,
  `guild_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `target_id` bigint DEFAULT NULL,
  `action_type` bigint NOT NULL,
  `reason` text DEFAULT NULL,
  `j_changes` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT "[]" CHECK(json_valid(`j_changes`)),
  `j_options` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT "{}" CHECK(json_valid(`j_options`)),
  FOREIGN KEY (`guild_id`) REFERENCES `guilds`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `read_states`;
CREATE TABLE `read_states` (
  `uid` bigint NOT NULL,
  `channel_id` bigint NOT NULL,
  `last_read_id` bigint NOT NULL,
  `count` int NOT NULL DEFAULT 0,
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`channel_id`) REFERENCES `channels`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

DROP TABLE IF EXISTS `notes`;
CREATE TABLE `notes` (
  `uid` bigint NOT NULL,
  `target_uid` bigint NOT NULL,
  `note` text NOT NULL,
  FOREIGN KEY (`uid`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`target_uid`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

#DROP TABLE IF EXISTS `guild_templates`;
#CREATE TABLE `guild_templates` (
#  `id` bigint NOT NULL,
#  `updated_at` bigint NOT NULL,
#  `template` JSON NOT NULL DEFAULT "{}"
#) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

#DROP TABLE IF EXISTS `connections`;
#CREATE TABLE `connections` (
#  `uid` bigint NOT NULL,
#  `type` text NOT NULL,
#  `state` text DEFAULT NULL,
#  `username` text DEFAULT NULL,
#  `service_uid` bigint DEFAULT NULL,
#  `friend_sync` bool NOT NULL DEFAULT false,
#  `j_integrations` JSON NOT NULL DEFAULT "[]",
#  `visible` bool NOT NULL DEFAULT true,
#  `verified` bool NOT NULL DEFAULT true,
#  `revoked` bool NOT NULL DEFAULT false,
#  `show_activity` bool NOT NULL DEFAULT true,
#  `two_way_link` bool NOT NULL DEFAULT false
#) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
