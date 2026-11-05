# HEW2026 v1.0 — MiniMax Code xhigh 版 設計書

日付：2026-11-01
改訂：2026-11-02（§2.5・§11・§11.1・§12 を更新。MySQL を既定 DB に確定）

## 1. 目的

リポジトリ直下に `HEW2026_v1.0_MiniMaxCode_xhigh/` を新規作成し、
`設計・要件/` の正本（要件定義書 Ver0.5・仕様決定事項-2026-10-26・画面遷移図・
DB設計書・関数定義・ロジック・ファイル構造）に基づく Web システムを実装する。

既存版 `HEW2026_v1.0_MiniMaxCode_high/`（Ver0.5 範囲）との差分は、
**出品取消・再出品・管理画面の追加**と**再出品・取消・二重防止などの
データモデルの刷新**である。high 版・TraeWorkCN 版・Chatbox 版は変更しない。

## 2. 正本と優先順位

本設計が参照する正本は次の順で優先する。

1. `設計・要件/仕様決定事項-2026-10-26.md`（業務ルール・仮値・未決の確定）
2. `設計・要件/要件定義書.md`（機能要件・完成条件・画面）
3. `設計・要件/画面遷移図.md`（導線）
4. `設計・要件/関数定義.md`（命名規則・配置先）
5. `設計・要件/ロジック-ファイル構造.md`（処理手順）
6. `設計・要件/db設計.md`・`DB-deploy/deploy.sql`（現行スキーマの記録）

正本にない事項は本設計で確定する。矛盾が生じた場合は上位優先とする。

## 2.5 基点となる実装と成果物の独立性（2026-11-02 決定）

本版の起点は既存版 `HEW2026_v1.0_MiniMaxCode_high/` とする。ただし、
high 版は「模型テスト」提出物なので、次の制約で独立性を保つ。

- **参照するのは設計と業務ルールの事実だけ**。high 版のコードは読んでもよいが、
  コピーして流用するファイルは下記に限る。
  - `app/services/` の業務ロジック（`auction_service` / `artwork_service` /
    `auth_service` / `point_service` / `tag_service` / `notification_service` /
    `image_service` / `layer_service`）— §5 のデータモデル刷新に合わせて改稿する
  - `app/static/js/canvas.js` — 描画セッション API の差分のみ反映する
  - `tests/` のテスト方針（pytest + `TEST_DATABASE_URL`）
- **新規に書き直すもの**。
  - `app/models/` 全部（`active_slot` / `held_points` / `reference_key` /
    `auction_cancellations` / `artworks.status` 拡張）
  - `app/services/cancellation_service.py` / `event_service.py`
  - `app/admin/`（Blueprint・画面・操作）
  - `app/static/css/style.css` — 同じ「製図図面の落札所」テーマでも、
    §9 のとおり token 名・クラス命名・セクション構成は high 版と別の構造にする
  - `app/templates/` — §8 の画面一覧に合わせて
- **丸ごと流用してはいけないもの**。`app/static/css/style.css`、
  `app/templates/` 一式、high 版が生成した `README.md`。
- high 版・TraeWorkCN 版・Chatbox 版のファイルは **1 つも変更しない**。
  参照専用として扱い、書き込みパスの対象外にする。

この方針により、xhigh 版は「Ver0.5 の実測済みの土台 + 本版固有の追加仕様 +
刷新したデータモデル」という差分成果物になる。Ver0.5 をゼロから再実装すると
検証済みコードまで壊す危険が増えるため採らない。

## 3. スコープ

### 3.1 実装する

- 要件定義書 5章の Ver0.5 全機能
  - 5.1 アカウント・認証（ユーザー名認証、復旧コード、表示名）
  - 5.2 描画・下書き保存（Canvas、10秒/30秒/1分/5分、10レイヤー、50操作履歴、
    IndexedDB 復元、PNG + レイヤーZIP の正式保存、60秒保存猶予）
  - 5.3 出品・公開（5/10/15/20分、開始価格0以上、イベント終了時刻の検証）
  - 5.4 手動入札（入力→確認→確定、差額消費、高値更新の返還、同一トランザクション）
  - 5.5 自動入札（代理入札、同額優先、残高不足停止と通知、上限変更・停止）
  - 5.6 オークション終了・落札（落札者確定、出品者への全額加算、ダウンロード権限）
  - 5.7 ボーナスポイント・チャージ画面（仮値の自動付与、課金は表示のみ）
  - 5.8 検索・お気に入り（タグAND、キーワード、作品/オークションのお気に入り分離）
  - 5.9 通知（アプリ内のみ、既読、関連商品へのリンク）
- 要件定義書 6.1 の追加仕様
  - 出品取消（本人・管理者）、未返還分の返還、自動入札の停止、取消履歴の記録
  - 再出品（新規競売の作成、履歴保持、同時開催の防止）
  - 管理者の非公開化・公開復帰
- 管理画面（作品・競売・アカウント・タグ・通知・ポイント操作）
- イベント終了時刻（`EVENT_END_AT`）による新規操作の停止
- 競売終了の定期実行（`flask close-auctions`）

### 3.2 実装しない（理由を記録する）

| 対象 | 理由 |
| --- | --- |
| 制作ライブ配信（6.2）・配信コメント（6.3） | 仕様決定事項7章・10章で配信共有範囲・接続方式・接続/切断検知の方法と秒数が**未決**と明記されている。実装すると未決事項に独自解釈を埋め込むことになる |
| 競売価格・入札履歴・通知のリアルタイム更新 | 3秒以内の更新目標は性能目標であり、実装手段が未確定。更新はページ再表示で代替する |
| Stripe 連携・実課金・決済による残高加算 | 正本の対象外 |
| NFT・タイムラプス・印刷 | 将来機能 |
| 吊り上げ bot | 自動入札とは別機能（正本の対象外） |
| 予約開始（scheduled） | Ver0.5 対象外 |
| ユーザーによる個別入札取消 | 正本に提供しないと明記されている |
| 管理者によるポイントの上限突破 | 上限は環境変数で固定し、管理者でも超過操作は拒否する |

### 3.3 未決・仮値・未実施の区別

| 区分 | 項目 | 本版での扱い |
| --- | --- | --- |
| 仮データ | ボーナス量（登録1,000pt/初出品300pt/描画100pt） | 実装するが `BONUS_*` で上書き可能なまま保持する。確定値として扱わない |
| 仮上限 | レイヤーPNG各5MiB・合計50MiB | 実装する。実機検証は未実施である旨を README に記載する |
| 仮性能目標 | 登録100人・同時利用20人 | 負荷試験は本版の対象外。README に未実施と記載する |
| 検証未実施 | 合成PNG5MiB、実機復元、60秒猶予、競合テスト | 自動テストで確認できる範囲のみ実装する |
| 未決（技術） | 配信方式・共有範囲・切断検知 | 実装対象外。管理画面・配信機能いずれも作らない |

## 4. アーキテクチャ

### 4.1 方針

- Application Factory + Blueprint。ルートは HTTP・認証・入力変換・応答だけを担当し、
  業務ルールはサービス層、構造はモデル層に置く。
- ルート → サービス → モデルの順で依存する。サービスからルートへ依存しない。
- ブラウザ側は描画操作と IndexedDB の一時保存だけを担当する。
  期限・権限・ファイル有効性の判定は常にサーバー側で行う。
- 秘密情報と接続情報は環境変数で管理し、ソースに書かない。

### 4.2 ディレクトリ構成

```text
HEW2026_v1.0_MiniMaxCode_xhigh/
├── main.py                     開発サーバー起動（--host/--port）
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
├── README.md
├── migrations/                 Flask-Migrate のマイグレーション
├── DB-deploy/deploy.sql        スキーマの正
└── app/
    ├── __init__.py             Application Factory、拡張機能・Blueprint・CLI・例外登録
    ├── config.py               環境別設定、.env 読み込み
    ├── extensions.py           db / migrate / login_manager / csrf
    ├── utils.py                UTC↔JST、残り時間、日次キー
    ├── commands.py             init-db / seed-tags / seed-users / seed-demo
    │                           close-auctions / promote-admin
    ├── models/
    │   ├── user.py             資格情報・表示名・残高・role
    │   ├── artwork.py          作品・描画セッション
    │   ├── auction.py          競売（active_slot 付き）
    │   ├── bid.py              入札（held_points 付き）
    │   ├── auto_bid.py         自動入札設定
    │   ├── tag.py              タグ・作品タグ
    │   ├── favorite.py         作品/オークションのお気に入り
    │   ├── wallet.py           ポイント取引履歴（reference_key 付き）
    │   ├── notification.py     アプリ内通知
    │   └── cancellation.py     取消・非公開の操作履歴
    ├── services/
    │   ├── errors.py           BusinessError ほか
    │   ├── auth_service.py     登録・認証・復旧・表示名
    │   ├── image_service.py    PNG の検証と保存
    │   ├── layer_service.py    レイヤー検証と ZIP 化
    │   ├── artwork_service.py  下書き・描画セッション・正式保存
    │   ├── auction_service.py  出品・入札・自動入札・終了確定
    │   ├── cancellation_service.py  取消・返還・自動入札停止・再出品
    │   ├── point_service.py    残高調整・ボーナス
    │   ├── tag_service.py      タグ検索（AND）・タグ管理
    │   ├── notification_service.py  通知生成・一覧・失効
    │   └── event_service.py    イベント終了の受付期限
    ├── auth/routes.py          登録・ログイン・ログアウト・復旧
    ├── artworks/routes.py      描画・保存・出品設定・再出品・ダウンロード
    ├── auctions/routes.py      商品詳細・入札・自動入札・取消
    ├── account/routes.py       アカウント・下書き・出品履歴・お気に入り・ポイント履歴
    ├── search/routes.py        キーワード＋タグAND検索
    ├── favorites/routes.py     お気に入り登録・解除
    ├── notifications/routes.py 通知一覧・既読
    ├── points/routes.py        ボーナス・チャージ・支払い
    ├── admin/routes.py         管理画面（作品・競売・アカウント・タグ・通知・ポイント）
    ├── main/routes.py          ホーム
    ├── templates/              画面一式
    └── static/
        ├── css/style.css       製図図面の落札所
        └── js/canvas.js, detail.js
```

### 4.3 命名規則

`設計・要件/関数定義.md` 2章に準拠する。

- ルート関数は `show_対象`、取得は `get_対象`、一覧は `list_対象の複数形`、
  作成は `create_対象`、更新は `update_対象`、判定は `is_状態` / `has_対象` /
  `can_操作`、検証は `validate_対象`、業務操作は「動詞＋対象」。
- サービス呼び出しは `auction_service.place_bid(...)` のように所属を明示する。
- 内部専用関数は先頭に `_` を1つ付ける。
- 1行79文字以内、コメント・docstringは72文字以内。PEP 8 に従う。
- モデルに業務ロジックとテンプレートロジックを置かない。

## 5. データモデル（high 版に対する意図的な差分）

### 5.1 差分の理由

high 版は `auctions.artwork_id` に UNIQUE を持ち、`Artwork.auction` を
`uselist=False` で定義していた。この形では「取消後に再出品して過去履歴を保持する」
を表現できない。再出品は複数競売を許し、**同時開催だけ1件**にする必要がある。

### 5.2 テーブル定義の要点

| テーブル | 変更点 |
| --- | --- |
| `auctions` | `artwork_id` の UNIQUE を**撤去**。`active_slot` を追加。`status` に `cancelled` を追加。`closed_reason` に `seller_cancelled` / `admin_cancelled` / `hidden` を追加。`previous_auction_id` を追加（再出品の系譜） |
| `artworks` | `status` に `cancelled`（取消済み）と `hidden`（管理者非公開）を追加。`hidden_reason` / `hidden_at` / `hidden_by_id` を追加 |
| `bids` | `held_points` を追加。受理時に預かったpointの残高 |
| `wallet_transactions` | `reference_key` を追加し UNIQUE。冪等性の根拠 |
| `auction_cancellations` | 新規。取消・非公開の操作履歴（競売ID・操作者・理由・種別・日時） |
| `notifications` | `revoked_at` / `revoked_by_id` / `revoke_reason` を追加 |

### 5.3 `active_slot` による同時開催の保証

MySQL / MariaDB には partial unique index がない。そこで次の定義を使う。

```text
active_slot = 1   … 開催中（active）
active_slot = NULL … 終了・取消済み
```

`UNIQUE (artwork_id, active_slot)` に対し、MySQL の UNIQUE 制約では NULL 同士は
衝突しないため、**同一作品で active な競売は同時に1件だけ**が存在することを
データベースが強制する。終了時に `active_slot` を NULL へ戻すことで、
同作品に新たな競売を作れる。

アプリケーション層でも、競売作成・再出品の前に対象作品行を `SELECT ... FOR UPDATE`
でロックし、active な競売の有無を再確認する。二重の防御とする。

### 5.4 `held_points` による未返還額の管理

入札行が「現在この入札が預かっているpoint」を持つ。

- 入札受理時: `held_points = 実際に消費した額`（最高入札者自身の増額なら差額）
- 高値更新時: 前最高入札者の `held_points` を全额返却し `held_points = 0` にする
- 落札確定時: 落札者の `held_points` は確定額として保持されたまま（出品者へ全額を加算する）
- 管理者取消時: `held_points > 0` の入札者へ全額返却し `held_points = 0` にする

この形により、返还対象は「その时被っている額」に限り、
高値更新で既に返還済みの入札を二重に返却しない。取消の再送でも
`held_points` は 0 になっているため、二重返還は構造的に発生しない。

`wallet_transactions.reference_key` は
`bid:{bid_id}:hold` / `bid:{bid_id}:release` / `admin_adjust:{user_id}:{ticket_id}`
のような一意キーを持ち、同一キーの再実行では台帳に行を追加しない。

### 5.5 状態遷移

```text
artworks.status
  draft ──出品──> listed ──落札──> sold
    │              │  │           
    │              │  └──取消/非公開──> cancelled / hidden
    └─（canceled・hidden から再出品可）──> listed

auctions.status
  active ──期限到達──> ended
  active ──取消──> cancelled
```

- `cancelled` / `ended`（落札者なし）の作品は**下書きに戻さない**。公開履歴として表示する。
- `hidden` の作品は一般閲覧から除外する。落札済みなら取引結果は変えず、
  作者・落札者・管理者のみが閲覧できる。
- `hidden` の状態では再出品できない。

## 6. 取消・再出品の業務ルール

正本：要件定義書 6.1、仕様決定事項 6章。

### 6.1 本人による取消

許可条件（すべて満たす場合のみ）:

- ログインユーザーが当該競売の出品者本人
- `auctions.status == active`
- 現在時刻が `end_time` 未満
- 受理済み入札（`bid_status == accepted`）が 0 件

この場合 `held_points` は存在しないため返還は不要。
理由欄は求めない。取消時は `held_points = 0` の入札しか存在しないため、
管理者による取消と同じ経路で処理できる。

### 6.2 管理者による取消

許可条件:

- ログインユーザーが管理者
- 現在時刻が `end_time` 未満
- **理由は必須**

処理内容:

1. 対象競売をロックする
2. `status = cancelled` とし `closed_reason = admin_cancelled` を記録する
3. `held_points > 0` の入札者へ全額返還する（`held_points` を 0 にする）
4. 対象競売の自動入札設定を全て停止する
5. `auction_cancellations` に操作者・日時・理由を記録する
6. 出品者と入札者へ通知を生成する
7. 作品・競売・入札の履歴は削除しない

再送時: `status` が既に `cancelled` なら処理を終了し、二重返還しない。
ロック取得後に状態を再検証するため、入札・終了確定との競合でも
両方とも成功しない。

### 6.3 再出品

許可条件（すべて満たす場合のみ）:

- ログインユーザーが作者本人
- 当該作品に `cancelled` または `ended`（落札者なし）の競売が存在する
- 作品に落札者（`winner_id`）がいない
- 作品に active な競売が1件もない（`active_slot` の UNIQUE 制約でも保証）
- 画像が保存済みである（`save_completed_at` と `image_path` がある）
- 作品の状態が `hidden` でない

処理内容:

1. 対象作品行をロックする
2. 新しい競売を作成する（`active_slot = 1`、`previous_auction_id` に元競売を設定）
3. 作品の状態を `listed` に戻す
4. 過去競売・入札履歴は保持する。商品詳細は対象競売を識別して表示する

画像とレイヤーの再編集は不可。旧競売は再開しない。

### 6.4 管理者による非公開化・公開復帰

非公開化:

- 理由が必須
- 開催中の場合は競売全体を取消し、未返還分を返却する（6.2 と同じ処理）
- 落札済みの場合は取引結果を変えず、作者・落札者・管理者のみが閲覧できる
- 作品の状態を `hidden` にする

公開復帰:

- 理由が必須
- 取消済みの競売は再開しない（競売の状態は `cancelled` のまま）
- 作品の状態を `hidden` 以外に戻す
- 再出品は通常の条件で判定する

### 6.5 ロック順序

`place_bid` / `close_auction` / `cancel_auction` / `create_relisted_auction` は
次の順でロックを取得する。順を揃えないとデッドロックと整合性事故が起きる。

1. 対象競売の行（`auctions`）
2. 作品行（再出品時のみ）
3. ユーザー行（ID 昇順）

## 7. 管理画面

### 7.1 アクセス

- `/admin/` 以下は管理者のみ。`role != 'admin'` のアクセスは 403。
- 一般ユーザーのナビゲーションには管理画面への導線を出さない。
- 管理者の昇格は `flask promote-admin <username>` CLI で行う。

### 7.2 タブ構成

| タブ | 内容 | 操作 |
| --- | --- | --- |
| 作品 | 一覧（状態・作者・現在価格・落札状況） | 非公開化（理由必須）、公開復帰（理由必須） |
| 競売 | 一覧（状態・現在価格・終了時刻・入札件数） | 理由付きで取消 |
| アカウント | 一覧（ユーザー名・表示名・残高・作品数） | 表示名編集、アカウントの有効/無効切替 |
| タグ | 一覧 | 新規追加、未使用タグの削除（使用中タグの削除は拒否） |
| 通知 | 全站通知の一覧（ユーザー・種別・既読・関連競売で絞り込み） | 誤生成通知の失効（理由必須） |
| ポイント | ユーザー残高と取引履歴 | 手動調整（双方向、理由必須、上限あり） |

### 7.3 ポイント手動調整

- 加算・減算の双方向。理由が必須。
- 1回の上限は `ADMIN_ADJUST_MAX_POINTS`（既定 100,000pt）。超過は拒否する。
- 残高が負になる操作は拒否する。
- `reference_key = admin_adjust:{user_id}:{ticket_id}` を用い、同一チケットの再送では
  台帳に行を追加しない。画面を再送しても二重加算にならない。
- 取引履歴には種別 `admin_adjust` として記録し、理由も保存する。
- 管理画面から通知の生成・決済・実課金は行わない。

### 7.4 通知の失効

- 誤生成の是正のみを目的とする。理由が必須。
- 物理削除はしない。`revoked_at` / `revoked_by_id` / `revoke_reason` を記録し、
  一般の一覧・対象競売からのリンク表示から除外する。
- 失効した通知は管理画面の通知タブで確認できる。
- 通知の生成そのものはサーバー側で管理し、管理画面からは生成しない。
  取引通知の重複生成防止は服务端の冪等性で担保する。

## 8. 画面一覧

| 画面 | URL | 権限 |
| --- | --- | --- |
| ホーム | `/` | ゲスト可 |
| 商品詳細（画面内で入札） | `/auctions/<id>` | 閲覧はゲスト可／入札はログイン |
| 絵を描く（時間選択） | `/artworks/draw` | ログイン |
| 描画キャンバス | `/artworks/<id>/canvas` | 作者のみ |
| 出品設定 | `/artworks/<id>/listing` | 作者のみ |
| 取引履歴（過去競売） | `/auctions/<id>/history` | 閲覧は公開 |
| 通知 | `/notifications/` | ログイン |
| ログイン／新規登録 | `/auth/login` `/auth/register` | - |
| パスワード再設定 | `/auth/recover` | - |
| アカウント | `/account/?tab=...` | ログイン |
| ボーナスポイント | `/points/bonus` | ログイン |
| チャージ | `/points/charge` | ログイン |
| 支払い | `/points/payment` | ログイン |
| タグ検索 | `/search/` | ゲスト可 |
| 管理画面 | `/admin/` | 管理者のみ |

入札は専用画面を設けない。入力 → 確認 → 確定を同じ画面で完結させる。

## 9. ビジュアル

「製図図面の落札所」— high 版と同一の視覚方向。CSS は新規に書き、
トークン名・クラス命名・セクション構成は high 版と別の構造にする
（同テーマだが同ファイルではない）。

| 層 | 表現 |
| --- | --- |
| 地 | 濃紺の方眼製図用紙（`repeating-linear-gradient` 2 段） |
| 題字欄 | ヘッダーに図番・版・状態の表題欄 |
| 用紙片 | 白のカードが図面の上に硬投影（ぼかしなし）で浮く |
| 道具立 | 描画ツールは右側の縦什器 |

設計上の決定:

- 色は文脈で切り替わる。図面上と紙片の上で `--text` の意味が変わる。
- 角丸は 2px まで。罫線はヘアライン（1px）＋太罫（2px）の 2 種。
- 状態色は意味に固定する。開催中＝琥珀、落札＝朱、終了＝灰、
  **取消＝灰青**（既存の 3 色と衝突させない新色）、非公開＝灰青の濃色。
- 影はぼかさない。`box-shadow: 3px 3px 0` のような硬い影を使う。
- タイポグラフィは 3 種。見出し＝明朝、本文＝ゴシック、数値・ID・価格＝等幅。
  すべてシステムフォントスタックで外部フォント・CDN に依存しない。
- `:focus-visible` に琥珀の 2px 枠。落槌タイマーは
  `@media (prefers-reduced-motion: reduce)` で脈動を停止する。
- レスポンシブは 1024px / 640px の 2 段。

## 10. テスト

pytest。DB は既定で MySQL を使う（開発 `hew_xhigh` / テスト `hew_xhigh_test`）。
`TEST_DATABASE_URL` 未設定のときだけ一時 SQLite へフォールバックする。
開発用 DB とは必ず分離する。

### 10.1 Ver0.5 のカバレッジ

- 登録・ログイン・ログアウト、重複ユーザー名の拒否
- 復旧コードでの再設定、使用後の無効化、再発行時の旧コード無効化
- 描画セッションの期限確定、開始後の時間変更拒否
- 不正な PNG／レイヤーの拒否、正当な PNG の保存、正式保存の完了
- 保存後の再保存拒否、猶予切れの拒否、下書きの権限チェック
- 出品（開始価格・開催時間・画像必須・イベント終了超過の拒否）
- 入札（消費・最高入札者自身の差額・高値更新の返還・自己入札・残高不足・期限切れ）
- 確認後価格変更時の再確認要求
- 終了確定（落札者・出品者への加算・二重加算なし・入札なし終了）
- 自動入札（競り上げ・同額優先・残高不足で停止と通知）
- CLI `close-auctions` の永続化
- タグ AND 検索、キーワード検索
- 作品／オークションのお気に入り登録・解除
- 通知の生成と既読、所有者チェック
- ボーナス（登録1回・初出品1回・描画はJST 1日1回）
- チャージ／支払い画面が残高を変えないこと

### 10.2 xhigh 固有のカバレッジ

- `held_points` が入札・返還で正しく増減すること
- 高値更新時に正確な額が返還されること（端数の取りこぼしがないこと）
- 管理者取消で**未返還分のみ**全額返還されること
- **取消の再送で二重返還されないこと**
- 本人取消が入札 1 件目で拒否されること
- 管理者が入札後でも取消でき、理由が空なら拒否されること
- 取消時に自動入札が停止されること
- 取消・終了確定・入札が同時に走っても整合すること
- 再出品で新しい競売が作られ、履歴が保持され、`previous_auction_id` が紐づくこと
- 同時開催の競売が 2 件作れないこと
- 落札済み作品の再出品が拒否されること
- 未保存画像の作品の再出品が拒否されること
- `hidden` 作品の再出品が拒否されること
- 非公開化が一般閲覧から作品隠すこと（作者・落札者・管理者は閲覧できる）
- 公開復帰で理由必須であること、取消済み競売が再開しないこと
- 管理画面が一般ユーザーに 403 を返すこと
- タグ削除が使用中タグで拒否されること
- 通知の失効で一般一覧から消え、管理画面で確認できること
- ポイント調整が双方向で働き、上限超過・負残高・理由空を拒否すること
- ポイント調整の再送で二重加算されないこと

### 10.3 手動検証

- ホーム、登録ログイン、描画保存、出品、入札、取消、再出品、検索、通知、
  アカウント、管理画面の各導線
- デスクトップ（1280px）とモバイル（390px）の表示
- キーボードフォーカス、フォームエラー、空状態

## 11. 運用

- `.env` はコミットしない。`.env.example` にはキー名と例だけを置く。
- 本番では `SECRET_KEY` を必ず設定する（未設定かつ `FLASK_ENV=production` で起動を拒否する）。
- 接続情報は `.env` のみで管理する。
- 入札処理は `SELECT ... FOR UPDATE` を使うため MySQL / MariaDB では InnoDB で動作させる。
  SQLite は開発・テスト専用。

### 11.0 DB は MySQL が既定（2026-11-02 決定）

- **既定の DB は MySQL 8.0**。`Config.SQLALCHEMY_DATABASE_URI` の既定値を
  `sqlite:///hew_dev.db` ではなく MySQL の接続 URL にする。
- **専用データベース名を使う**。既存の `hew` / `hew_test` は
  `HEW2026_v1.0_TraeWorkCN_高/` が `hew` を使用中（13 表・デモデータあり）で、
  本版のスキーマ（`active_slot` / `held_points` / `auction_cancellations` ほか）と
  衝突する。既存データを壊さないため本版は専用庫を用意する。

| 用途 | データベース名 | 備考 |
| --- | --- | --- |
| 開発 | `hew_xhigh` | `utf8mb4` |
| テスト | `hew_xhigh_test` | 開発庫と必ず分ける。テストは開発データを洗わない |

- `.env` には `DATABASE_URL`（開発）と `TEST_DATABASE_URL`（テスト）の
  両方を MySQL で書く。`.env.example` は同じキー名のまま、値は
  `<password>` 等のプレースホルダにする。
- `flask init-db` 相当の初期化コマンドで専用庫にテーブルを作る。
  テーブルは Flask-Migrate の管理とし、`deploy.sql` は正本として残す。
- SQLite へ切り替えたい場合は `DATABASE_URL` / `TEST_DATABASE_URL` を差し替える
  だけでよい。フォールバックは「SQLite が既定」ではなく「利用者が明示的に
  SQLite を選んだ場合のみ」。

### 11.0.1 CI

- `.github/workflows/ci.yml` に xhigh 用の job を**追加**する。既存 job は変更しない。
- job は MySQL 8.0 サービスコンテナを使い、`hew_xhigh_test` を作成してから
  `TEST_DATABASE_URL` を差し込んで pytest を実行する。SQLite フォールバックに
  頼らない構成にする（既定 DB と CI の整合を取る）。
- lint は `ruff check --select E9,F63,F7,F82` をブロッキングにする。

- 競売終了は Windows タスクスケジューラから `flask close-auctions` を定期実行する。

### 11.1 設定キーの一覧

| キー | 既定値 | 用途 |
| --- | --- | --- |
| `SECRET_KEY` | （空） | セッション署名。本番では必須 |
| `DATABASE_URL` | `mysql+pymysql://root:<password>@127.0.0.1:3306/hew_xhigh?charset=utf8mb4` | 接続URL。**既定は MySQL** |
| `TEST_DATABASE_URL` | `mysql+pymysql://root:<password>@127.0.0.1:3306/hew_xhigh_test?charset=utf8mb4` | テスト用 DB。**既定は MySQL** |
| `UPLOAD_FOLDER` | `app/uploads` | 保存先 |
| `MAX_IMAGE_BYTES` | 5242880 | 合成 PNG 上限 |
| `MAX_LAYER_BYTES` | 5242880 | レイヤー PNG 上限 |
| `MAX_LAYER_TOTAL_BYTES` | 52428800 | 展開後合計上限 |
| `MAX_LAYERS` | 10 | レイヤー数上限 |
| `CANVAS_SIZE` | 1024 | キャンバス寸法 |
| `SAVE_GRACE_SECONDS` | 60 | 保存猶予 |
| `BID_MIN_INCREMENT` | 1 | 最小上乗せ幅 |
| `DEFAULT_AUCTION_MINUTES` | 10 | 開催時間の初期値 |
| `EVENT_END_AT` | 未設定 | イベント終了時刻（ISO 8601） |
| `BONUS_SIGNUP_POINTS` | 1000 | 登録ボーナス |
| `BONUS_FIRST_LISTING_POINTS` | 300 | 初出品ボーナス |
| `BONUS_DRAW_POINTS` | 100 | 描画ボーナス |
| `ADMIN_ADJUST_MAX_POINTS` | 100000 | 管理者調整の 1 回上限 |

## 12. 完了条件

- `HEW2026_v1.0_MiniMaxCode_xhigh/` が独立して起動でき、README の手順が実際と一致する
- Ver0.5 の全完了条件（要件定義書 8章）を満たす
- 取消・再出品・非公開化・公開復帰・管理画面が仕様どおりに動作する
- 自動テストがすべて通り、主要な手動導線に阻断エラーがない
- 既存版（high / TraeWorkCN / Chatbox 系）のファイルが 1 つも変更されていない
- 製図テーマが主要画面で一貫して現れ、モバイルで横スクロールが発生しない

### 12.1 DB は MySQL で通ること（2026-11-02 追加）

- `Config` の既定 DB が MySQL であり、`.env` を書き換えずに起動하면
  `hew_xhigh` に接続して自作動する
- `hew_xhigh` / `hew_xhigh_test` を作成し、`flask db upgrade`（または
  `init-db`）で全テーブルが建成する
- pytest が `hew_xhigh_test` を使い、`hew_xhigh` のデータが変わらない
  （開発库的演示数据がテストで洗われないこと）
- `hew` / `hew_test` / `hew_acceptance` などの既存 DB は**変更されない**
- CI の xhigh job が MySQL サービスコンテナ上で pytest を通す
