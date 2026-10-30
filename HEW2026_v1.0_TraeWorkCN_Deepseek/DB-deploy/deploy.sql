-- ========================================
-- HEW2026 Ver0.5 スキーマ（DB設計書 4章 / ER図 準拠）
-- 対象: MariaDB (XAMPP) / MySQL 8.x, InnoDB, utf8mb4
--
-- 要件定義書 10章の修正課題を反映している。
--   * bids.auction_id の UNIQUE を撤廃し、同一オークションへの複数入札を保存する
--   * reserve_price（最低落札価格）は項目だけ残し、Ver0.5の判定では使わない
-- アプリ側のスキーマ管理は Flask-Migrate を想定。このファイルは参照用の正。
-- ========================================

CREATE DATABASE IF NOT EXISTS hew DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE hew;

-- ----------------------------------------
-- users
-- ----------------------------------------
CREATE TABLE users (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username      VARCHAR(20)     NOT NULL,
  disp_name     VARCHAR(50)     NOT NULL COMMENT '初期値はFlask側で user{id} を設定',
  email         VARCHAR(225)    NOT NULL,
  password_hash VARCHAR(255)    NOT NULL,
  role          ENUM('user','admin') NOT NULL DEFAULT 'user',
  point_balance INT UNSIGNED    NOT NULL DEFAULT 0,
  is_active     BOOLEAN         NOT NULL DEFAULT TRUE,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- artworks
-- ----------------------------------------
CREATE TABLE artworks (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  seller_id   BIGINT UNSIGNED NOT NULL,
  title       VARCHAR(200)    NOT NULL,
  description TEXT            NULL,
  image_path  VARCHAR(500)    NOT NULL COMMENT 'アップロード基準からの相対パス',
  status      ENUM('draft','listed','sold','cancelled') NOT NULL DEFAULT 'draft',
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_artworks_seller (seller_id),
  KEY idx_artworks_status (status),
  CONSTRAINT fk_artworks_seller FOREIGN KEY (seller_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- bids（先に作成し、auctions の winner_bid_id 外部キーを ALTER で追加する）
-- ----------------------------------------
CREATE TABLE bids (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  auction_id        BIGINT UNSIGNED NOT NULL COMMENT 'UNIQUE を撤廃：1オークションに複数入札',
  bidder_id         BIGINT UNSIGNED NOT NULL,
  bid_amount        INT UNSIGNED    NOT NULL,
  is_auto_bid       BOOLEAN         NOT NULL DEFAULT FALSE,
  bid_status        ENUM('accepted','rejected') NOT NULL,
  payment_intent_id BIGINT UNSIGNED NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_bids_auction_amount (auction_id, bid_amount, created_at),
  KEY idx_bids_bidder (bidder_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- auctions
-- ----------------------------------------
CREATE TABLE auctions (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  artwork_id    BIGINT UNSIGNED NOT NULL COMMENT '1作品=1オークション（再出品防止）',
  start_price   INT UNSIGNED    NOT NULL,
  current_price INT UNSIGNED    NOT NULL,
  reserve_price INT UNSIGNED    NULL COMMENT 'Ver0.5では使用しない',
  status        ENUM('active','ended','cancelled') NOT NULL DEFAULT 'active',
  start_time    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  end_time      DATETIME        NOT NULL,
  winner_id     BIGINT UNSIGNED NULL,
  winner_bid_id BIGINT UNSIGNED NULL,
  final_price   INT UNSIGNED    NULL,
  closed_reason ENUM('time_expired','seller_finished','cancelled') NULL,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_auction_artwork (artwork_id),
  UNIQUE KEY uq_auction_winner_bid (winner_bid_id),
  KEY idx_auctions_status_end (status, end_time),
  KEY idx_auctions_winner (winner_id),
  CONSTRAINT fk_auctions_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id),
  CONSTRAINT fk_auctions_winner FOREIGN KEY (winner_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE bids
  ADD CONSTRAINT fk_bids_auction FOREIGN KEY (auction_id) REFERENCES auctions (id),
  ADD CONSTRAINT fk_bids_bidder FOREIGN KEY (bidder_id) REFERENCES users (id);

ALTER TABLE auctions
  ADD CONSTRAINT fk_auctions_winner_bid FOREIGN KEY (winner_bid_id) REFERENCES bids (id);

-- ----------------------------------------
-- auto_bid_settings
-- ----------------------------------------
CREATE TABLE auto_bid_settings (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  auction_id  BIGINT UNSIGNED NOT NULL,
  user_id     BIGINT UNSIGNED NOT NULL,
  max_amount  INT UNSIGNED    NOT NULL,
  is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_auto_bid_auction_user (auction_id, user_id),
  KEY idx_auto_bid_active (auction_id, is_active),
  CONSTRAINT fk_auto_bid_auction FOREIGN KEY (auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_auto_bid_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- payment_intents（Ver0.5は画面遷移用の置き場のみ。Stripe連携なし）
-- ----------------------------------------
CREATE TABLE payment_intents (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    BIGINT UNSIGNED NOT NULL,
  auction_id BIGINT UNSIGNED NULL,
  amount     INT UNSIGNED    NOT NULL,
  status     ENUM('pending','succeeded','failed','cancelled') NOT NULL DEFAULT 'pending',
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_payment_intents_user (user_id),
  KEY idx_payment_intents_auction (auction_id),
  KEY idx_payment_intents_status (status),
  CONSTRAINT fk_payment_intents_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_payment_intents_auction FOREIGN KEY (auction_id) REFERENCES auctions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE bids
  ADD CONSTRAINT fk_bids_payment_intent FOREIGN KEY (payment_intent_id) REFERENCES payment_intents (id);

-- ----------------------------------------
-- wallet_transactions
-- ----------------------------------------
CREATE TABLE wallet_transactions (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id           BIGINT UNSIGNED NOT NULL,
  transaction_type  ENUM('charge','bid','refund','purchase','bonus') NOT NULL,
  amount            INT             NOT NULL COMMENT '増加は正・減少は負',
  balance_after     INT UNSIGNED    NOT NULL,
  related_auction_id BIGINT UNSIGNED NULL,
  related_bid_id    BIGINT UNSIGNED NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_wallet_user_created (user_id, created_at),
  KEY idx_wallet_auction (related_auction_id),
  KEY idx_wallet_bid (related_bid_id),
  CONSTRAINT fk_wallet_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_wallet_auction FOREIGN KEY (related_auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_wallet_bid FOREIGN KEY (related_bid_id) REFERENCES bids (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- notifications / notification_deliveries
-- ----------------------------------------
CREATE TABLE notifications (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id           BIGINT UNSIGNED NOT NULL,
  notification_type ENUM('bid_received','auction_ending','auction_won','auction_lost','payment_result') NOT NULL,
  title             VARCHAR(200)    NOT NULL,
  message           TEXT            NOT NULL,
  is_read           BOOLEAN         NOT NULL DEFAULT FALSE,
  related_auction_id BIGINT UNSIGNED NULL,
  related_bid_id    BIGINT UNSIGNED NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_notifications_user_read (user_id, is_read, created_at),
  KEY idx_notifications_auction (related_auction_id),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_notifications_auction FOREIGN KEY (related_auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_notifications_bid FOREIGN KEY (related_bid_id) REFERENCES bids (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE notification_deliveries (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  notification_id BIGINT UNSIGNED NOT NULL,
  channel         ENUM('email')   NOT NULL DEFAULT 'email',
  recipient       VARCHAR(255)    NOT NULL,
  delivery_status ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending',
  sent_at         DATETIME        NULL,
  error_message   VARCHAR(500)    NULL,
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_deliveries_status (delivery_status, created_at),
  KEY idx_deliveries_notification (notification_id),
  CONSTRAINT fk_deliveries_notification FOREIGN KEY (notification_id) REFERENCES notifications (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------
-- bookmarks / artwork_bookmarks / tags / artwork_tags
-- ----------------------------------------
CREATE TABLE bookmarks (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    BIGINT UNSIGNED NOT NULL,
  auction_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_bookmark_user_auction (user_id, auction_id),
  KEY idx_bookmarks_auction (auction_id),
  CONSTRAINT fk_bookmarks_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_bookmarks_auction FOREIGN KEY (auction_id) REFERENCES auctions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE artwork_bookmarks (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    BIGINT UNSIGNED NOT NULL,
  artwork_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_artwork_bookmark_user_artwork (user_id, artwork_id),
  KEY idx_artwork_bookmarks_artwork (artwork_id),
  CONSTRAINT fk_artwork_bookmarks_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_artwork_bookmarks_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tags (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name       VARCHAR(50)     NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tag_name (name),
  KEY idx_tag_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE artwork_tags (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  artwork_id BIGINT UNSIGNED NOT NULL,
  tag_id     BIGINT UNSIGNED NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_artwork_tag (artwork_id, tag_id),
  KEY idx_artwork_tag_tag (tag_id, artwork_id),
  CONSTRAINT fk_artwork_tag_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id),
  CONSTRAINT fk_artwork_tag_tag FOREIGN KEY (tag_id) REFERENCES tags (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
