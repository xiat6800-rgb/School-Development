# ER図（Mermaid）

2026/10/26更新：以下は**現行SQLの図**であり、最新製品要件を満たす移行後の図ではない。
メール必須・メール配信・入札最大1件・作品最大1競売などは現行の制約であり、採用仕様ではない。
[仕様決定事項](仕様決定事項-2026-10-26.md)と[DB設計書の差分](db設計.md)に従い、今後移行する。
目標はユーザー名認証・メール不使用、1競売に複数入札、1作品に複数の競売履歴（同時開催最大1件）、1作品1配信。
制作セッション・レイヤーZIP・復旧コード・非公開状態・返還／加算履歴・コメント監査も追加設計が必要。今回SQLは変更しない。


[`DB-deploy/deploy.sql`](../DB-deploy/deploy.sql)の有効なテーブル定義・外部キー・一意制約をもとにしたHEW Ver0.5のER図です。詳細な型・デフォルト値・運用方針は[`db設計.md`](db設計.md)を参照してください。1作品に対するオークションは0〜1件、1オークションに対する入札も現行SQLの一意制約により0〜1件です。

エンティティ名は図中で大文字に統一しています。実テーブル名は小文字・複数形のsnake_caseで、図中の`TAGS`は`tags`に対応します。`||`は必須の1件、`o|`は0〜1件、`o{`は0件以上を表します。属性の`UK`は単一カラムの一意制約を示し、複合一意制約は補足に記載します。数値型の`UNSIGNED`、NULL許可、ENUMの値、デフォルト値はDB設計書に記載します。

```mermaid
erDiagram
    direction TB
    USERS ||--o{ ARTWORKS : "出品する"
    USERS ||--o{ BIDS : "入札する"
    USERS ||--o{ AUTO_BID_SETTINGS : "自動入札を設定する"
    USERS ||--o{ BOOKMARKS : "登録する"
    USERS ||--o{ ARTWORK_BOOKMARKS : "作品をお気に入り登録する"
    USERS ||--o{ PAYMENT_INTENTS : "決済する"
    USERS ||--o{ WALLET_TRANSACTIONS : "ポイントを消費・返却する"
    USERS ||--o{ NOTIFICATIONS : "受信する"
    USERS o|--o{ AUCTIONS : "落札者になる"

    ARTWORKS ||--o| AUCTIONS : "1作品につき最大1オークション"
    ARTWORKS ||--o{ ARTWORK_BOOKMARKS : "お気に入り登録される"
    ARTWORKS ||--o{ ARTWORK_TAGS : "タグ付けされる"
    TAGS ||--o{ ARTWORK_TAGS : "作品に付与される"
    AUCTIONS ||--o| BIDS : "最大1件の入札を持つ"
    AUCTIONS ||--o{ AUTO_BID_SETTINGS : "自動入札設定を持つ"
    AUCTIONS ||--o{ BOOKMARKS : "ブックマークされる"
    AUCTIONS o|--o{ PAYMENT_INTENTS : "決済に関連する"
    AUCTIONS o|--o{ WALLET_TRANSACTIONS : "ポイント取引に関連する"
    AUCTIONS o|--o{ NOTIFICATIONS : "通知に関連する"
    BIDS o|--o| AUCTIONS : "落札入札として確定される"
    BIDS o|--o{ WALLET_TRANSACTIONS : "ポイント取引に関連する"
    BIDS o|--o{ NOTIFICATIONS : "通知に関連する"
    PAYMENT_INTENTS o|--o{ BIDS : "入札に関連する"
    NOTIFICATIONS ||--o{ NOTIFICATION_DELIVERIES : "メール配信する"

    USERS {
        bigint id PK
        varchar(20) username UK
        varchar(50) disp_name
        varchar(225) email UK
        varchar password_hash
        enum role
        int point_balance
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    ARTWORKS {
        bigint id PK
        bigint artist_id FK
        varchar title
        text description
        varchar image_path
        enum status
        datetime created_at
        datetime updated_at
    }

    AUCTIONS {
        bigint id PK
        bigint artwork_id FK,UK
        int start_price
        int current_price
        int reserve_price
        enum status
        datetime start_time
        datetime end_time
        bigint winner_id FK
        bigint winner_bid_id FK,UK
        int final_price
        enum closed_reason
        datetime created_at
        datetime updated_at
    }

    BIDS {
        bigint id PK
        bigint auction_id FK,UK
        bigint bidder_id FK
        int bid_amount
        boolean is_auto_bid
        enum bid_status
        bigint payment_intent_id FK
        datetime created_at
    }

    AUTO_BID_SETTINGS {
        bigint id PK
        bigint auction_id FK
        bigint user_id FK
        int max_amount
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    PAYMENT_INTENTS {
        bigint id PK
        bigint user_id FK
        bigint auction_id FK
        int amount
        enum status
        datetime created_at
        datetime updated_at
    }

    WALLET_TRANSACTIONS {
        bigint id PK
        bigint user_id FK
        enum transaction_type
        int amount
        int balance_after
        bigint related_auction_id FK
        bigint related_bid_id FK
        datetime created_at
    }

    NOTIFICATIONS {
        bigint id PK
        bigint user_id FK
        enum notification_type
        varchar title
        text message
        boolean is_read
        bigint related_auction_id FK
        bigint related_bid_id FK
        datetime created_at
    }

    BOOKMARKS {
        bigint id PK
        bigint user_id FK
        bigint auction_id FK
        datetime created_at
    }

    ARTWORK_BOOKMARKS {
        bigint id PK
        bigint user_id FK
        bigint artwork_id FK
        datetime created_at
    }

    TAGS {
        bigint id PK
        varchar name UK
        datetime created_at
        datetime updated_at
    }

    ARTWORK_TAGS {
        bigint id PK
        bigint artwork_id FK
        bigint tag_id FK
        datetime created_at
    }

    NOTIFICATION_DELIVERIES {
        bigint id PK
        bigint notification_id FK
        enum channel
        varchar recipient
        enum delivery_status
        datetime sent_at
        varchar error_message
        datetime created_at
        datetime updated_at
    }

    classDef core fill:#1f4b7a,color:#ffffff,stroke:#163754,stroke-width:2px
    classDef transaction fill:#e8f1fb,color:#102a43,stroke:#6c9bc9
    classDef discovery fill:#eaf7ed,color:#163b22,stroke:#71ad7e
    classDef support fill:#fff2cc,color:#5c4700,stroke:#d6b656

    class USERS,ARTWORKS,AUCTIONS core
    class BIDS,AUTO_BID_SETTINGS,WALLET_TRANSACTIONS transaction
    class TAGS,ARTWORK_TAGS,BOOKMARKS,ARTWORK_BOOKMARKS discovery
    class PAYMENT_INTENTS,NOTIFICATIONS,NOTIFICATION_DELIVERIES support
```

## 補足

- `users.email`は`VARCHAR(225)`、`username`は`VARCHAR(20)`で、いずれも一意かつ必須とする。画面表示用の`disp_name`は`VARCHAR(50) NOT NULL`で、一意制約・DBのDEFAULT指定はない。SQLのコメントに従い、Flask側で`user{user.id}`形式の初期値を設定する想定である。
- PNG保存時に`artworks`へ`draft`を作成し、作者が出品設定を完了した時だけ`auctions`を作成して`listed`へ更新する。
- `auctions.artwork_id` の一意制約により、1作品を複数回出品できない。初期実装ではオークション作成と同時に`active`となる。
- `bids.auction_id`は必須かつ一意のため、同一オークションへの複数入札は保存できない。
- `auctions.winner_id`と`winner_bid_id`はNULLを許可する。`winner_bid_id`は一意で、1入札が落札入札として参照されるオークションは最大1件となる。同じオークションの入札か、落札者と入札者が一致するかはアプリケーション側で検証する。
- `bookmarks` は `user_id` と `auction_id` の組み合わせを一意にする。
- `artwork_bookmarks` は `user_id` と `artwork_id` の組み合わせを一意にする。オークションと作品のお気に入りを混在させない。
- `tags`と`artwork_tags`により、作品とタグを多対多で関連付ける。`artwork_tags`は`artwork_id`と`tag_id`の組み合わせを一意にする。
- オークションの出品者は `auctions.artwork_id → artworks.artist_id` から取得し、`auctions` には保持しない。
- ポイントの即時減算・高値更新時の返却はアプリケーション側の運用方針である。現行SQLの`bids.auction_id`の一意制約では、複数入札を履歴として保存する運用と整合しない。
- `auto_bid_settings` は `auction_id` と `user_id` の組み合わせを一意にする。
- `payment_intents`の`provider`、`provider_intent_id`、`currency`はSQLでコメントアウトされており、図にも含めない。
