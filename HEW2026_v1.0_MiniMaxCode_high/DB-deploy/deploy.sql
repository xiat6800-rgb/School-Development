-- ========================================
-- HEW2026 v1.0（MiniMax Code 版）スキーマ
--
-- 定義の基準は本ファイルとする。
-- 設計の根拠: 設計・要件/db設計.md / 仕様決定事項-2026-10-26.md
--
-- ポイント:
--   * 時刻は UTC で保存し、画面表示時に日本時間へ変換する
--   * メールアドレスは使わない（ユーザー名 + 復旧コード）
--   * bids.auction_id に一意制約を設けない（同一オークションに複数入札を保存する）
--   * auctions.artwork_id は UNIQUE（Ver0.5 は 1 作品 1 オークション）
--
-- 実行例（MySQL / MariaDB）:
--   mysql -u root -p < DB-deploy/deploy.sql
-- ========================================

CREATE DATABASE IF NOT EXISTS `hew`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `hew`;

-- ----------------------------------------
-- ユーザー
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`          VARCHAR(20)  NOT NULL,
  `disp_name`         VARCHAR(50)  NOT NULL,
  `password_hash`     VARCHAR(255) NOT NULL,
  `recovery_code_hash` VARCHAR(255) NULL,
  `recovery_code_used_at` DATETIME  NULL,
  `role`              VARCHAR(20)  NOT NULL DEFAULT 'user',
  `point_balance`     INT UNSIGNED NOT NULL DEFAULT 0,
  `is_active`         BOOLEAN      NOT NULL DEFAULT TRUE,
  `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- 作品（Ver0.5 では下書き draft → 出品 listed → 落札 sold）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `artworks` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `artist_id`         BIGINT UNSIGNED NOT NULL,
  `title`             VARCHAR(200) NOT NULL DEFAULT '',
  `description`       TEXT         NULL,
  `image_path`        VARCHAR(500) NULL,
  `layer_archive_path` VARCHAR(500) NULL,
  `status`            VARCHAR(20)  NOT NULL DEFAULT 'draft',
  `save_completed_at` DATETIME     NULL,
  `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_artworks_artist` (`artist_id`),
  KEY `idx_artworks_status` (`status`),
  CONSTRAINT `fk_artworks_artist` FOREIGN KEY (`artist_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- 描画セッション（開始時刻・期限・保存猶予をサーバー管理）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `drawing_sessions` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `artwork_id`        BIGINT UNSIGNED NOT NULL,
  `user_id`           BIGINT UNSIGNED NOT NULL,
  `duration_seconds`  INT UNSIGNED NOT NULL,
  `started_at`        DATETIME NOT NULL,
  `deadline_at`       DATETIME NOT NULL,
  `finished_at`       DATETIME NULL,
  `save_grace_until`  DATETIME NULL,
  `status`            VARCHAR(20) NOT NULL DEFAULT 'active',
  `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_drawing_session_artwork` (`artwork_id`),
  KEY `idx_drawing_session_user` (`user_id`),
  CONSTRAINT `fk_drawing_sessions_artwork` FOREIGN KEY (`artwork_id`) REFERENCES `artworks` (`id`),
  CONSTRAINT `fk_drawing_sessions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- オークション
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `auctions` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `artwork_id`    BIGINT UNSIGNED NOT NULL,
  `start_price`   INT UNSIGNED NOT NULL DEFAULT 0,
  `current_price` INT UNSIGNED NOT NULL DEFAULT 0,
  `reserve_price` INT UNSIGNED NULL,
  `status`        VARCHAR(20)  NOT NULL DEFAULT 'active',
  `start_time`    DATETIME NOT NULL,
  `end_time`      DATETIME NOT NULL,
  `winner_id`     BIGINT UNSIGNED NULL,
  `winner_bid_id` BIGINT UNSIGNED NULL,
  `final_price`   INT UNSIGNED NULL,
  `closed_reason` VARCHAR(30) NULL,
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auctions_artwork` (`artwork_id`),
  KEY `idx_auctions_status_end` (`status`, `end_time`),
  KEY `idx_auctions_winner` (`winner_id`),
  CONSTRAINT `fk_auctions_artwork` FOREIGN KEY (`artwork_id`) REFERENCES `artworks` (`id`),
  CONSTRAINT `fk_auctions_winner` FOREIGN KEY (`winner_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- 入札（同一オークションに複数入札を履歴として保存する）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `bids` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `auction_id`    BIGINT UNSIGNED NOT NULL,
  `bidder_id`     BIGINT UNSIGNED NOT NULL,
  `bid_amount`    INT UNSIGNED NOT NULL,
  `is_auto_bid`   BOOLEAN NOT NULL DEFAULT FALSE,
  `bid_status`    VARCHAR(20) NOT NULL DEFAULT 'accepted',
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_bids_auction_amount` (`auction_id`, `bid_amount`, `created_at`),
  KEY `idx_bids_bidder` (`bidder_id`, `created_at`),
  CONSTRAINT `fk_bids_auction` FOREIGN KEY (`auction_id`) REFERENCES `auctions` (`id`),
  CONSTRAINT `fk_bids_bidder` FOREIGN KEY (`bidder_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 落札入札の外部キーは入札テーブル作成後に追加する
SET @has_winner_bid_fk := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
   WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'auctions'
     AND CONSTRAINT_NAME = 'fk_auctions_winner_bid'
);
SET @add_winner_bid_fk := IF(
  @has_winner_bid_fk = 0,
  'ALTER TABLE `auctions` ADD CONSTRAINT `fk_auctions_winner_bid` FOREIGN KEY (`winner_bid_id`) REFERENCES `bids` (`id`)',
  'DO 0'
);
PREPARE stmt FROM @add_winner_bid_fk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------------------
-- 自動入札設定
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `auto_bid_settings` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `auction_id`  BIGINT UNSIGNED NOT NULL,
  `user_id`     BIGINT UNSIGNED NOT NULL,
  `max_amount`  INT UNSIGNED NOT NULL,
  `is_active`   BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auto_bid_auction_user` (`auction_id`, `user_id`),
  KEY `idx_auto_bid_auction_active` (`auction_id`, `is_active`),
  CONSTRAINT `fk_auto_bid_auction` FOREIGN KEY (`auction_id`) REFERENCES `auctions` (`id`),
  CONSTRAINT `fk_auto_bid_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- ポイント取引履歴
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `wallet_transactions` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`           BIGINT UNSIGNED NOT NULL,
  `transaction_type`  VARCHAR(20) NOT NULL,
  `amount`            INT NOT NULL,
  `balance_after`     INT UNSIGNED NOT NULL,
  `related_auction_id` BIGINT UNSIGNED NULL,
  `related_bid_id`    BIGINT UNSIGNED NULL,
  `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_wallet_user` (`user_id`, `created_at`),
  KEY `idx_wallet_auction` (`related_auction_id`),
  KEY `idx_wallet_bid` (`related_bid_id`),
  CONSTRAINT `fk_wallet_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_wallet_auction` FOREIGN KEY (`related_auction_id`) REFERENCES `auctions` (`id`),
  CONSTRAINT `fk_wallet_bid` FOREIGN KEY (`related_bid_id`) REFERENCES `bids` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- ボーナス付与記録（重複付与の防止）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `bonus_grants` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT UNSIGNED NOT NULL,
  `bonus_type` VARCHAR(30) NOT NULL,
  `bonus_date` VARCHAR(10) NOT NULL DEFAULT 'once',
  `amount`     INT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bonus_grant` (`user_id`, `bonus_type`, `bonus_date`),
  KEY `idx_bonus_user` (`user_id`),
  CONSTRAINT `fk_bonus_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- アプリ内通知（メールは使わない）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `notifications` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`           BIGINT UNSIGNED NOT NULL,
  `notification_type` VARCHAR(30) NOT NULL,
  `title`             VARCHAR(200) NOT NULL,
  `message`           TEXT NOT NULL,
  `is_read`           BOOLEAN NOT NULL DEFAULT FALSE,
  `related_auction_id` BIGINT UNSIGNED NULL,
  `related_bid_id`    BIGINT UNSIGNED NULL,
  `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_notifications_user_read` (`user_id`, `is_read`, `created_at`),
  KEY `idx_notifications_auction` (`related_auction_id`),
  CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_notifications_auction` FOREIGN KEY (`related_auction_id`) REFERENCES `auctions` (`id`),
  CONSTRAINT `fk_notifications_bid` FOREIGN KEY (`related_bid_id`) REFERENCES `bids` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- お気に入り（作品とオークションは別テーブル）
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `artwork_bookmarks` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT UNSIGNED NOT NULL,
  `artwork_id` BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_artwork_bookmark` (`user_id`, `artwork_id`),
  KEY `idx_artwork_bookmarks_artwork` (`artwork_id`),
  CONSTRAINT `fk_artwork_bookmarks_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_artwork_bookmarks_artwork` FOREIGN KEY (`artwork_id`) REFERENCES `artworks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `bookmarks` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT UNSIGNED NOT NULL,
  `auction_id` BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auction_bookmark` (`user_id`, `auction_id`),
  KEY `idx_bookmarks_auction` (`auction_id`),
  CONSTRAINT `fk_bookmarks_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_bookmarks_auction` FOREIGN KEY (`auction_id`) REFERENCES `auctions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------
-- タグと作品の中間テーブル
-- ----------------------------------------
CREATE TABLE IF NOT EXISTS `tags` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`       VARCHAR(50) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tags_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `artwork_tags` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `artwork_id` BIGINT UNSIGNED NOT NULL,
  `tag_id`     BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_artwork_tag` (`artwork_id`, `tag_id`),
  KEY `idx_artwork_tags_tag` (`tag_id`, `artwork_id`),
  CONSTRAINT `fk_artwork_tags_artwork` FOREIGN KEY (`artwork_id`) REFERENCES `artworks` (`id`),
  CONSTRAINT `fk_artwork_tags_tag` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
