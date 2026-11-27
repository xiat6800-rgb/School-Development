# DB設計書

## 2026/10/26の確定仕様と現行SQLの差分

本書のカラム表は現行[deploy.sql](../DB-deploy/deploy.sql)の記録であり、目標仕様とは区別する。
最新仕様は[仕様決定事項](仕様決定事項-2026-10-26.md)を優先する。今回はSQL・モデル・マイグレーションを変更していない。

| 対象 | 現行の問題 | 今後必要な変更 |
| --- | --- | --- |
| ユーザー | `email`が必須 | メールを一切使わない構成へ移行。復旧コードのハッシュ・無効化を管理 |
| 複数入札 | `bids.auction_id`が一意 | 複数入札履歴・最高入札者自身の差額消費・返還を管理 |
| 再出品 | `auctions.artwork_id`が一意 | 過去履歴を保持し、同時開催だけ最大1件に制限 |
| 作品・制作 | 画像必須、描画時間ENUMの値が重複 | 画像なし下書き、制作開始・期限・保存猶予・正式保存完了を管理。10・30・60・300秒に対応 |
| 配布データ | PNGのみを想定 | 非公開の原寸PNG・全レイヤーZIP・構成情報、取得権限を管理 |
| 公開状態 | 取消と非公開の扱いが未整理 | 未落札・取消の公開履歴と、管理者の非公開・公開復帰を区別 |
| ポイント | 確定代金・重複防止が未具体化 | 出品者への全額加算、ボーナス、未返還額と重複防止履歴を管理 |
| 通知 | メール配信・課金結果を含む | アプリ内のみ。対象と契機は仕様決定事項8章に従う |
| 配信・コメント | 新仕様未反映 | 1作品1配信、描画期限連動、200文字・連投制限、監査・本文消去期限を管理 |

以降に残るメール・決済関連テーブルは現行スキーマの記録であり、使用する製品要件ではない。


## 1. 目的
HEWの現行SQL構造を記録する。メール・決済の旧定義を含むため、製品要件は冒頭の差分と仕様決定事項を参照する。

現行スキーマには新しい制作配信・コメント設計が未反映。これらは追加仕様として設計対象であり、NFT・タイムラプス・印刷とは区別する。

定義の基準は[`DB-deploy/deploy.sql`](../DB-deploy/deploy.sql)とする。コメントアウトされたカラムは現行のテーブル定義に含めない。

DB前提:

- データベース名は`hew`（SQLで作成・選択する）。
- 想定環境はMariaDB（XAMPP）、InnoDB、utf8mb4。ただし、SQLにストレージエンジン・文字コードの明示指定はなく、実際の設定は環境に依存する。
- 時刻をUTCで保存し、画面表示時に日本時間へ変換する運用を想定する。ただし、SQLにタイムゾーン指定はないため、接続・サーバー側で設定する。

## 2. 設計方針

- 1ユーザーは複数の作品・入札を持てる。オークションの出品者は、関連する作品の出品者として取得する。
- 1作品に対してオークションは0件または1件とする。`auctions.artwork_id`の一意制約により、同じ作品に複数のオークションを登録できない。
- 現行SQLでは`bids.auction_id`が一意であり、1オークションに保存できる入札は0件または1件となる。複数入札・高値更新を想定した運用との相違は5章に記載する。
- 作品とタグは多対多とし、タグで作品を検索できるようにする。
- オークションのお気に入りと作品のお気に入りは別テーブルで管理する。
- 描画を保存した作品は`draft`とし、作者が出品設定を完了した時だけオークションを作成して公開する。
- 入札の受理時にポイントを即時減算し、高値更新で前最高入札者へ即時返却する。
- オークション終了時に落札入札・落札者・確定額を記録する。
- ポイント残高の変更は履歴と同一トランザクションで処理する。
- 取引履歴を保護するため、ユーザー・作品・オークションは原則として物理削除しない。

命名規則: テーブル名は小文字・複数形のsnake_case、主キーは`id`、外部キーは`{対象}_id`、日時は`created_at`、`updated_at`とする。

## 3. エンティティと関係
親1件に対する子の件数と、子から見た参照の必須・任意を示す。任意参照の外部キーはNULLを許可する。

| 親テーブル | 子テーブル（外部キー） | 親1件に対する子の件数 | 子からの参照 |
| --- | --- | --- | --- |
| users | artworks(artist_id), bids(bidder_id), auto_bid_settings(user_id), bookmarks(user_id), artwork_bookmarks(user_id), wallet_transactions(user_id), payment_intents(user_id), notifications(user_id) | 0件以上 | 必須 |
| users | auctions(winner_id) | 0件以上 | 任意 |
| artworks | auctions(artwork_id) | 0〜1件 | 必須 |
| artworks | artwork_bookmarks(artwork_id), artwork_tags(artwork_id) | 0件以上 | 必須 |
| tags | artwork_tags(tag_id) | 0件以上 | 必須 |
| auctions | bids(auction_id) | 0〜1件 | 必須 |
| auctions | auto_bid_settings(auction_id), bookmarks(auction_id) | 0件以上 | 必須 |
| auctions | payment_intents(auction_id), wallet_transactions(related_auction_id), notifications(related_auction_id) | 0件以上 | 任意 |
| bids | auctions(winner_bid_id) | 0〜1件 | 任意 |
| bids | wallet_transactions(related_bid_id), notifications(related_bid_id) | 0件以上 | 任意 |
| payment_intents | bids(payment_intent_id) | 0件以上 | 任意 |
| notifications | notification_deliveries(notification_id) | 0件以上 | 必須 |

## 4. テーブル定義

### 4.1 users
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | ユーザーID |
| username | VARCHAR(20) | NOT NULL, UNIQUE | 一意のユーザー名 |
| disp_name | VARCHAR(50) | NOT NULL | 表示名。初期値はFlask側で設定する |
| email | VARCHAR(225) | NOT NULL, UNIQUE | ログインに使用するメールアドレス |
| password_hash | VARCHAR(255) | NOT NULL | パスワードハッシュ |
| role | ENUM('user','admin') | NOT NULL DEFAULT 'user' | 権限 |
| point_balance | INT UNSIGNED | NOT NULL DEFAULT 0 | 所持ポイント |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | 有効フラグ |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 登録日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

`disp_name`にはDBのDEFAULT指定がない。SQLのコメントではFlask側で`user{user.id}`形式の初期値を設定する想定とされている。表示名は一意制約を持たず、`username`とは別に管理する。後から編集可能とし、入力値の検証はFlask側で行う。

### 4.2 artworks
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 作品ID |
| artist_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 出品者ID |
| title | VARCHAR(200) | NOT NULL | 作品タイトル |
| description | TEXT | NULL | 作品説明 |
| image_path | VARCHAR(500) | NOT NULL | PNG画像の相対保存先 |
| status | ENUM('draft','listed','sold','cancelled') | NOT NULL DEFAULT 'draft' | 状態 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `(artist_id)`, `(status)`

### 4.3 auctions
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | オークションID |
| artwork_id | BIGINT UNSIGNED | NOT NULL, UNIQUE, FK -> artworks(id) | 作品ID。再出品を防止する |
| start_price | INT UNSIGNED | NOT NULL | 開始価格 |
| current_price | INT UNSIGNED | NOT NULL | 現在価格 |
| reserve_price | INT UNSIGNED | NULL | 最低落札価格 |
| status | ENUM('active','ended','cancelled') | NOT NULL DEFAULT 'active' | 状態。初期実装では作成と同時に開始する |
| start_time | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 開始日時 |
| end_time | DATETIME | NOT NULL | 終了日時 |
| winner_id | BIGINT UNSIGNED | NULL, FK -> users(id) | 落札者ID |
| winner_bid_id | BIGINT UNSIGNED | NULL, UNIQUE, FK -> bids(id) | 落札を確定した入札ID |
| final_price | INT UNSIGNED | NULL | 確定落札額 |
| closed_reason | ENUM('time_expired','seller_finished','cancelled') | NULL | 終了理由 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `(status, end_time)`, `(winner_id)`

### 4.4 bids
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 入札ID |
| auction_id | BIGINT UNSIGNED | NOT NULL, UNIQUE, FK -> auctions(id) | オークションID。1オークションにつき最大1入札 |
| bidder_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 入札者ID |
| bid_amount | INT UNSIGNED | NOT NULL | 入札額 |
| is_auto_bid | BOOLEAN | NOT NULL DEFAULT FALSE | 自動入札による入札か |
| bid_status | ENUM('accepted','rejected') | NOT NULL | 入札状態 |
| payment_intent_id | BIGINT UNSIGNED | NULL, FK -> payment_intents(id) | 関連決済ID |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 入札日時 |

インデックス: `(auction_id, bid_amount, created_at)`, `(bidder_id, created_at)`

### 4.5 auto_bid_settings
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 自動入札設定ID |
| auction_id | BIGINT UNSIGNED | NOT NULL, FK -> auctions(id) | 対象オークションID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 設定ユーザーID |
| max_amount | INT UNSIGNED | NOT NULL | 自動入札の上限額 |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | 有効フラグ |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 設定日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `UNIQUE(auction_id, user_id)`, `(auction_id, is_active)`

### 4.6 payment_intents
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 決済ID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 顧客ID |
| auction_id | BIGINT UNSIGNED | NULL, FK -> auctions(id) | 関連オークション |
| amount | INT UNSIGNED | NOT NULL | 決済金額 |
| status | ENUM('pending','succeeded','failed','cancelled') | NOT NULL DEFAULT 'pending' | 決済状態 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `(user_id)`, `(auction_id)`, `(status)`

`provider`、`provider_intent_id`、`currency`はSQLでコメントアウトされており、作成されない。

### 4.7 wallet_transactions
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 取引ID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | ユーザーID |
| transaction_type | ENUM('charge','bid','refund','purchase','bonus') | NOT NULL | 取引種別 |
| amount | INT | NOT NULL | 取引額。増加は正、減少は負 |
| balance_after | INT UNSIGNED | NOT NULL | 取引後残高 |
| related_auction_id | BIGINT UNSIGNED | NULL, FK -> auctions(id) | 関連オークション |
| related_bid_id | BIGINT UNSIGNED | NULL, FK -> bids(id) | 関連入札 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |

インデックス: `(user_id, created_at)`, `(related_auction_id)`, `(related_bid_id)`

### 4.8 notifications
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 通知ID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 対象ユーザー |
| notification_type | ENUM('bid_received','auction_ending','auction_won','auction_lost','payment_result') | NOT NULL | 通知種別 |
| title | VARCHAR(200) | NOT NULL | タイトル |
| message | TEXT | NOT NULL | 本文 |
| is_read | BOOLEAN | NOT NULL DEFAULT FALSE | 既読フラグ |
| related_auction_id | BIGINT UNSIGNED | NULL, FK -> auctions(id) | 関連オークション |
| related_bid_id | BIGINT UNSIGNED | NULL, FK -> bids(id) | 関連入札 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 生成日時 |

インデックス: `(user_id, is_read, created_at)`, `(related_auction_id)`

### 4.9 bookmarks
| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | ブックマークID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 登録ユーザーID |
| auction_id | BIGINT UNSIGNED | NOT NULL, FK -> auctions(id) | 対象オークションID |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 登録日時 |

インデックス: `UNIQUE(user_id, auction_id)`, `(auction_id)`

### 4.10 notification_deliveries
メール通知の配信結果を記録する。アプリ内通知は`notifications`で管理し、メール送信の再試行・失敗確認は本テーブルで行う。

| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 配信履歴ID |
| notification_id | BIGINT UNSIGNED | NOT NULL, FK -> notifications(id) | 対象通知ID |
| channel | ENUM('email') | NOT NULL DEFAULT 'email' | 配信チャネル |
| recipient | VARCHAR(255) | NOT NULL | 送信先メールアドレスのスナップショット |
| delivery_status | ENUM('pending','sent','failed') | NOT NULL DEFAULT 'pending' | 配信状態 |
| sent_at | DATETIME | NULL | 送信完了日時 |
| error_message | VARCHAR(500) | NULL | 失敗理由 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `(delivery_status, created_at)`, `(notification_id)`

### 4.11 artwork_bookmarks
作品をお気に入り登録するためのテーブル。`bookmarks`は従来どおりオークションのお気に入り専用とし、対象を混在させない。

| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 作品お気に入りID |
| user_id | BIGINT UNSIGNED | NOT NULL, FK -> users(id) | 登録ユーザーID |
| artwork_id | BIGINT UNSIGNED | NOT NULL, FK -> artworks(id) | 対象作品ID |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 登録日時 |

インデックス: `UNIQUE(user_id, artwork_id)`, `(artwork_id)`

### 4.12 tags
作品の分類・検索に使用するタグのマスタテーブル。タグ名は一意とする。

| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | タグID |
| name | VARCHAR(50) | NOT NULL, UNIQUE | タグ名 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新日時 |

インデックス: `UNIQUE(name)`（カラムのUNIQUE指定に加え、`idx_tag_name`でも明示定義されている）

### 4.13 artwork_tags
作品とタグを対応付ける中間テーブル。1作品に複数タグ、1タグに複数作品を関連付ける。

| カラム名 | 型 | 制約 | 説明 |
| --- | --- | --- | --- |
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 作品タグID |
| artwork_id | BIGINT UNSIGNED | NOT NULL, FK -> artworks(id) | 対象作品ID |
| tag_id | BIGINT UNSIGNED | NOT NULL, FK -> tags(id) | タグID |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 登録日時 |

インデックス: `UNIQUE(artwork_id, tag_id)`, `(tag_id, artwork_id)`

## 5. 制約と運用ルール

### 5.1 現行SQLで定義される制約

- 4章のPK・NOT NULL・UNIQUE・外部キー・DEFAULTとインデックスを定義する。各`id`は`BIGINT UNSIGNED`の自動採番主キーである。
- `bids.auction_id`のUNIQUE制約は入札状態に関係なく適用されるため、同一オークションへの2件目の入札は保存できない。下記の高値更新・返金・自動入札など、複数の入札を履歴として保存する運用とは整合しない。
- `auctions.winner_bid_id`の外部キーは参照先作成後に追加される。`bids.payment_intent_id`は現行SQLではコメントアウトされており、有効な外部キーではない。
- 外部キーに`ON DELETE`・`ON UPDATE`の明示指定はなく、参照中の親行の削除・キー更新はデフォルト動作で制限される。CASCADEは定義されていない。
- 落札入札が同じオークションの入札であることや、落札者がその入札者と一致することを保証する複合制約はない。アプリケーション側で検証する必要がある。

### 5.2 目標とするアプリケーション側の運用方針
以下は運用上の要件であり、SQLだけでは処理・検証されない。複数入札を前提とする処理には、5.1に記載したUNIQUE制約との調整が必要となる。

- `auctions.start_price` は0以上、`current_price` は開始価格以上とする。
- `bids.bid_amount` は現在価格より大きい値とする。出品者本人の入札・自動入札設定は不可とする。
- オークションの出品者判定は`auctions.artwork_id`で作品を取得し、`artworks.artist_id`（現行SQL名）を使用する。`auctions`に出品者IDを重複保存しない。
- `artwork_bookmarks`は同一ユーザーが同一作品を重複して登録できない。作品をお気に入り一覧で取得する際は`artwork_bookmarks.created_at`の降順とする。
- タグ検索は`artwork_tags.tag_id`を起点に作品を取得する。1作品への同一タグの重複付与は不可とする。
- `artworks`は`draft → listed → sold`、または`draft / listed → cancelled`と遷移する。`draft`は作者だけが閲覧・編集でき、`listed`以降を公開する。
- 初期実装のオークションは作成と同時に`active`となり、終了日時の定期処理で`ended`へ遷移する。終了・取消済みには入札不可とする。予約開始の`scheduled`状態は後続拡張とする。
- 落札時は`winner_id`、`winner_bid_id`、`final_price`を同一トランザクションで確定する。最低落札価格は使わず、受理済み入札があれば最高入札者が落札する。出品者へ全額を一度だけ加算する。
- 入札処理では対象`auctions`行と入札者`users`行を`SELECT ... FOR UPDATE`でロックし、最新価格・状態・残高を検証してから、入札・残高・履歴を同一トランザクションで更新する。
- 受理した入札では、最高入札者自身の増額は差額、それ以外は入札額を減算して`bid`取引を記録する。別ユーザーによる高値更新時は前最高入札者の未返還額を返却して`refund`取引を記録する。残高更新・入札・取引履歴は同一トランザクションで処理し、残高は負にしない。
- 自動入札は`max_amount`の範囲内で処理し、同額上限なら設定日時が早いものを優先する。
- 決済・課金は対象外。コメントアウトされた`bids.payment_intent_id`を有効な現行カラムとして扱わない。
- ユーザー・作品・オークションは削除の代わりに`is_active`または`status`で無効化する。
- タグを複数指定した検索はAND条件とし、選択したすべてのタグを持つ作品だけを返す。
- 通知はアプリ内だけに保存し、メール配信は行わない。既存の`notification_deliveries`は廃止対象として移行を設計する。
