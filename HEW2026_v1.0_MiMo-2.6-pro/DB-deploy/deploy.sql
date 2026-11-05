-- HEW2026 v1.0 目标 schema（2026/10/26 仕様決定事項に対応）
-- MariaDB (XAMPP) / InnoDB / utf8mb4 想定
-- メール廃止・複数入札・復旧コード・重複防止台帳を反映した新スキーマ。

CREATE DATABASE IF NOT EXISTS hew DEFAULT CHARACTER SET utf8mb4;
USE hew;

-- ユーザー（メール列なし。復旧コードはハッシュのみ保持）
CREATE TABLE IF NOT EXISTS users (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username         VARCHAR(20)     NOT NULL,
  disp_name        VARCHAR(50)     NOT NULL,
  password_hash    VARCHAR(255)    NOT NULL,
  recovery_code_hash VARCHAR(255)  NULL,
  role             VARCHAR(10)     NOT NULL DEFAULT 'user',
  point_balance    INT             NOT NULL DEFAULT 0,
  is_active        TINYINT(1)      NOT NULL DEFAULT 1,
  created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 作品（画像なし下書き可・正式保存完了・レイヤーZIP・描画期限を管理）
CREATE TABLE IF NOT EXISTS artworks (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  artist_id         BIGINT UNSIGNED NOT NULL,
  title             VARCHAR(200)    NOT NULL DEFAULT '無題の作品',
  description       TEXT            NULL,
  image_path        VARCHAR(500)    NULL,
  layers_zip_path   VARCHAR(500)    NULL,
  status            VARCHAR(20)     NOT NULL DEFAULT 'draft',
  duration_seconds  INT             NULL,
  drawing_started_at DATETIME       NULL,
  drawing_deadline  DATETIME        NULL,
  frozen_at         DATETIME        NULL,
  saved_at          DATETIME        NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_artworks_artist (artist_id),
  KEY idx_artworks_status (status),
  CONSTRAINT fk_artworks_artist FOREIGN KEY (artist_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- オークション（artwork_id の UNIQUE は廃止し、履歴を保持。
-- 同時開催1件はアプリ側で検証する）
CREATE TABLE IF NOT EXISTS auctions (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  artwork_id     BIGINT UNSIGNED NOT NULL,
  start_price    INT             NOT NULL,
  current_price  INT             NOT NULL,
  status         VARCHAR(20)     NOT NULL DEFAULT 'active',
  start_time     DATETIME        NOT NULL,
  end_time       DATETIME        NOT NULL,
  winner_id      BIGINT UNSIGNED NULL,
  winner_bid_id  BIGINT UNSIGNED NULL,
  final_price    INT             NULL,
  closed_reason  VARCHAR(20)     NULL,
  created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_auctions_status_end (status, end_time),
  KEY idx_auctions_artwork (artwork_id),
  KEY idx_auctions_winner (winner_id),
  CONSTRAINT fk_auctions_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id),
  CONSTRAINT fk_auctions_winner FOREIGN KEY (winner_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 入札（同一オークションへの複数入札を履歴として保存）
CREATE TABLE IF NOT EXISTS bids (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  auction_id   BIGINT UNSIGNED NOT NULL,
  bidder_id    BIGINT UNSIGNED NOT NULL,
  bid_amount   INT             NOT NULL,
  is_auto_bid  TINYINT(1)      NOT NULL DEFAULT 0,
  bid_status   VARCHAR(20)     NOT NULL DEFAULT 'accepted',
  created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_bids_auction_amount (auction_id, bid_amount, created_at),
  KEY idx_bids_bidder (bidder_id, created_at),
  CONSTRAINT fk_bids_auction FOREIGN KEY (auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_bids_bidder FOREIGN KEY (bidder_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 落札入札の参照（bids 作成後に追加）
ALTER TABLE auctions
  ADD CONSTRAINT fk_auctions_winner_bid
  FOREIGN KEY (winner_bid_id) REFERENCES bids (id);

-- 自動入札設定
CREATE TABLE IF NOT EXISTS auto_bid_settings (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  auction_id  BIGINT UNSIGNED NOT NULL,
  user_id     BIGINT UNSIGNED NOT NULL,
  max_amount  INT             NOT NULL,
  is_active   TINYINT(1)      NOT NULL DEFAULT 1,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_auto_bid_auction_user (auction_id, user_id),
  KEY idx_auto_bid_active (auction_id, is_active),
  CONSTRAINT fk_auto_bid_auction FOREIGN KEY (auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_auto_bid_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ポイント取引履歴（増加は正・減少は負）
CREATE TABLE IF NOT EXISTS wallet_transactions (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            BIGINT UNSIGNED NOT NULL,
  transaction_type   VARCHAR(20)     NOT NULL,
  amount             INT             NOT NULL,
  balance_after      INT             NOT NULL,
  related_auction_id BIGINT UNSIGNED NULL,
  related_bid_id     BIGINT UNSIGNED NULL,
  created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_wallet_user (user_id, created_at),
  KEY idx_wallet_auction (related_auction_id),
  KEY idx_wallet_bid (related_bid_id),
  CONSTRAINT fk_wallet_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_wallet_auction FOREIGN KEY (related_auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_wallet_bid FOREIGN KEY (related_bid_id) REFERENCES bids (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ボーナス付与の重複防止台帳
CREATE TABLE IF NOT EXISTS bonus_grants (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  bonus_type  VARCHAR(20)     NOT NULL,
  period_key  VARCHAR(20)     NOT NULL DEFAULT '',
  amount      INT             NOT NULL,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_bonus_grant (user_id, bonus_type, period_key),
  CONSTRAINT fk_bonus_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- アプリ内通知（メール配信なし）
CREATE TABLE IF NOT EXISTS notifications (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            BIGINT UNSIGNED NOT NULL,
  notification_type  VARCHAR(30)     NOT NULL,
  title              VARCHAR(200)    NOT NULL,
  message            TEXT            NOT NULL,
  is_read            TINYINT(1)      NOT NULL DEFAULT 0,
  related_auction_id BIGINT UNSIGNED NULL,
  related_bid_id     BIGINT UNSIGNED NULL,
  created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_notifications_user (user_id, is_read, created_at),
  KEY idx_notifications_auction (related_auction_id),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_notifications_auction FOREIGN KEY (related_auction_id) REFERENCES auctions (id),
  CONSTRAINT fk_notifications_bid FOREIGN KEY (related_bid_id) REFERENCES bids (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- タグ
CREATE TABLE IF NOT EXISTS tags (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name       VARCHAR(50)     NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tags_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 作品×タグ
CREATE TABLE IF NOT EXISTS artwork_tags (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  artwork_id  BIGINT UNSIGNED NOT NULL,
  tag_id      BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_artwork_tag (artwork_id, tag_id),
  KEY idx_artwork_tags_tag (tag_id, artwork_id),
  CONSTRAINT fk_artwork_tags_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id),
  CONSTRAINT fk_artwork_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- オークションのお気に入り
CREATE TABLE IF NOT EXISTS bookmarks (
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

-- 作品のお気に入り
CREATE TABLE IF NOT EXISTS artwork_bookmarks (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    BIGINT UNSIGNED NOT NULL,
  artwork_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_abm_user_artwork (user_id, artwork_id),
  KEY idx_abm_artwork (artwork_id),
  CONSTRAINT fk_abm_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_abm_artwork FOREIGN KEY (artwork_id) REFERENCES artworks (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
