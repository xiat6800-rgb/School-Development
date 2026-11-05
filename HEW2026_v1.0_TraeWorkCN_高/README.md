# HEW2026 v1.0 — TraeWorkCN / DeepSeek 版

`../設計・要件` の **要件定義書 Ver.0.5（2026-09-18 更新）** に沿って実装した、
サイト上で描いた絵をポイントで競り合うオークションの Web システムです。

- サーバー: Python 3.13 / Flask（Application Factory + Blueprint）
- フロント: HTML / CSS / Vanilla JavaScript（Canvas 描画）
- DB: MySQL 8 / MariaDB（utf8mb4）。開発確認用に SQLite へ切り替え可能
- 認証: Flask-Login + Werkzeug パスワードハッシュ
- フォーム: Flask-WTF（全 POST に CSRF）
- スキーマ: `DB-deploy/deploy.sql` を正とし、Flask-Migrate でも管理可能

---

## 1. すぐに動かす

同梱の `.env` はローカルの MySQL を指しています（`.env` は Git 管理外）。

```bash
cd HEW2026_v1.0_TraeWorkCN_Deepseek
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

set FLASK_APP=main.py
python -m flask seed-tags
python -m flask seed-users --password <開発用パスワード>
python -m flask seed-demo

python main.py
# http://127.0.0.1:5000
```

SQLite で試す場合は `.env` の `DATABASE_URL` を `sqlite:///hew_dev.db` に変更し、
`python -m flask init-db` でテーブルを作成してから同じ seed コマンドを実行します。

`seed-users` は `sample1` / `sample2` / `sample3` を作成し、指定したパスワードを表示します。
`seed-demo` は `sample1` を出品者としてデモ作品 3 点と開催中のオークションを作成します。

## 2. MySQL（XAMPP / MariaDB）で動かす

1. `.env` の `DATABASE_URL` を環境に合わせて変更する（パスワードは `.env` のみに書く）。

```text
DATABASE_URL=mysql+pymysql://root:your-password@127.0.0.1:3306/hew?charset=utf8mb4
```

2. スキーマを作成する。どちらか一方を実行します。

```bash
# A. 参照用 SQL をそのまま流す（DB 設計書の正）
mysql -u root -p < DB-deploy/deploy.sql

# B. Flask-Migrate で管理する
python -m flask db init
python -m flask db migrate -m "HEW Ver0.5 schema"
python -m flask db upgrade
```

3. 初期データを投入する。

```bash
python -m flask seed-tags
python -m flask seed-users --password <開発用パスワード>
python -m flask seed-demo
```

`flask init-db` はモデル定義から直接テーブルを作る開発用の近道です。
本番相当のスキーマ管理は `deploy.sql` または Flask-Migrate を使用してください。

## 3. 画面一覧（画面遷移図の Ver0.5 対象）

| 画面 | URL | 権限 | 内容 |
| --- | --- | --- | --- |
| 1 ホーム | `/` | ゲスト可 | 公開作品・開催中オークション・タグへの入口 |
| 2 商品詳細 | `/auctions/<id>` | 閲覧はゲスト可／入札はログイン | 画面内で入札（入力 → 確認 → 確定）、自動入札、お気に入り 2 種、入札履歴 |
| 4 支払い | `/points/payment` | ログイン | 遷移先のみ。決済通信なし |
| 5 絵を描く | `/artworks/draw` | ログイン | 10秒 / 30秒 / 1分 / 5分、Gペン・丸ペン・ぼかし・消しゴム、Undo、時間切れ自動保存 |
| 6 出品設定 | `/artworks/<id>/listing` | 作者のみ | タイトル・説明・タグ・開始価格・終了日時 |
| 7 通知 | `/notifications/` | ログイン | 一覧・既読・商品詳細へ。メール配信結果も表示 |
| 8 ログイン / 新規登録 | `/auth/login` `/auth/register` | - | メールアドレス + パスワード |
| 9 アカウント | `/account/?tab=...` | ログイン | 下書き・出品中・作品/オークションお気に入り・自動入札・ポイント履歴・表示名編集 |
| 10 ボーナスポイント | `/points/bonus` | ログイン | 付与条件・残高・履歴 |
| 11 チャージ | `/points/charge` | ログイン | 課金未提供である旨を表示 |
| タグ検索 | `/search/` | ゲスト可 | 複数タグは AND、キーワード併用可 |

画面 3（専用入札画面）は商品詳細へ統合済み。画面 12・13（ライブ配信）と 14（管理画面）は
Ver0.5 の対象外のため実装していません。

## 4. 要件と実装の対応

| 要件 | 実装 |
| --- | --- |
| 5.1 登録・ログイン | `app/auth/`。ユーザー名/メールは一意、パスワードは Werkzeug でハッシュ化。表示名の初期値は `user{id}` で編集可能 |
| 5.2 描画・下書き保存 | `app/static/js/canvas.js`（開始後に制限時間をロック、時間切れで自動保存）、`app/services/image_service.py`（PNG 署名・IHDR 寸法・バイト数を検証し UUID 名で保存）。下書きへの加筆ルートは存在しない |
| 5.3 出品＝オークション開始 | `app/artworks/routes.py`。`draft → listed` と同時に `auctions(status=active)` を作成。1 作品 1 オークション（UNIQUE） |
| 5.4 入札・消費・返却 | `app/services/auction_service.py`。`auctions` → 入札者 → 前最高入札者の順に `SELECT ... FOR UPDATE`。残高減算・入札・`wallet_transactions`・`current_price` を同一トランザクションで更新。高値更新時は前最高入札者へ同額返却 |
| 5.5 自動入札 | 手動入札と同じトランザクション内で、上限額と残高の範囲内のみ上乗せ。上限額が同額なら `created_at` が早い設定を優先（`BID_INCREMENT` は `.env` で変更可） |
| 5.6 終了・落札 | `flask close-auctions`。`winner_id / winner_bid_id / final_price / status=ended / closed_reason=time_expired` を記録。入札なしは落札者なし、落札時の再差し引きなし |
| 5.7 ボーナス・課金 | `app/services/bonus_service.py`（登録・初出品・描画）。チャージ／支払いは表示のみで、Stripe 通信・決済・残高変更なし |
| 5.8 検索・お気に入り | `app/search/routes.py`（タグ AND は `GROUP BY ... HAVING COUNT(DISTINCT tag) = 選択数`）。`bookmarks` と `artwork_bookmarks` を分離 |
| 5.9 通知 | `app/services/notification_service.py`。`notifications` へアプリ内通知、`notification_deliveries` へ送信先・状態・送信日時を記録。SMTP 未設定なら `pending` |
| 7.3 セキュリティ | 全 POST に CSRF、所有者チェック、画像は静的ディレクトリ外＋権限付きルート、UTC 保存＋日本時間表示、秘密情報は `.env` のみ |

### 未決事項（要件定義書 9章）の既定値

`.env` で変更できます。決定が変わってもコード修正なしで追従できます。

| 項目 | 既定値・扱い |
| --- | --- |
| ボーナス付与 | 登録 1,000pt（1回）／初出品 500pt（1回）／描画 100pt（最大10回） |
| 自動入札の上乗せ幅 | `BID_INCREMENT=100` |
| 同額上限 | 設定日時が早いユーザーを優先（後から同額を設定したユーザーは上限ちょうどでは譲る） |
| 残高不足の自動入札 | その回は発動せず、設定は有効のまま。次点の候補を試す |
| 入札なしで終了した作品 | `listed` のまま（再出品は Ver0.5 対象外） |
| 画像上限 | 2MB・2048×2048（Canvas は 800×600） |
| メール再送 | 生成時に 1 通だけ試行し結果を記録（再送ジョブは未実装） |
| 落札後のポイント移転 | Ver0.5 では行わない（未決のため） |

## 5. 設計書からの意図的な変更

- `bids.auction_id` の UNIQUE を撤廃し、同一オークションへの複数入札・自動入札の履歴を保存できるようにした（要件定義書 10章の修正課題）。
- `reserve_price` は項目だけ残し、落札判定では使用しない。
- 描画終了を理由とするオークション終了（`seller_finished`）は行わない。
- 保存後に編集できるのは出品情報（タイトル・説明・タグ）だけ。描画画面へ戻る導線は作らない。
- PNG は `app/uploads/artworks/`（static の外）へ保存し、`/artworks/<id>/image` の権限チェック経由で配信する。下書きを URL 直打ちで閲覧できないようにするため。
- 開発確認用に SQLite を許容（`.env` の `DATABASE_URL` を差し替えるだけ）。テストも `TEST_DATABASE_URL` 未設定時は一時 SQLite で実行する。

## 6. テスト

```bash
python -m pytest -q
```

開発 DB と分離する場合は `.env` の `TEST_DATABASE_URL` に専用 MySQL を指定します。
カバレッジ: 登録・ログイン・重複拒否／PNG 検証と下書き権限／出品と初出品ボーナス／
手動入札の消費・返却／自動入札の上限と同額優先／自己入札・残高不足・終了後の拒否／
落札確定と二重引き去りなし／入札なし終了／タグ AND 検索／キーワード検索／
お気に入り登録・解除／通知の所有者チェックと既読／ポイント画面のログイン必須。

## 7. オークション終了の定期実行

要件定義書 7.4 のとおり、Windows タスクスケジューラから CLI を定期実行します（1 分ごとの例）。

```bat
schtasks /Create /SC MINUTE /MO 1 /TN "HEW-close-auctions" ^
  /TR "cmd /c cd /d <このプロジェクトの絶対パス> && .venv\Scripts\flask close-auctions"
```

## 8. ディレクトリ

```text
main.py                    開発サーバー起動
app/
  __init__.py              Application Factory・Blueprint/CLI 登録・エラーハンドラ
  config.py                環境別設定（.env）
  extensions.py            db / migrate / login_manager / csrf
  utils.py                 UTC↔JST・残り時間・安全なリダイレクト
  models/                  user artwork auction bid tag favorite auto_bid wallet notification payment
  auth/ artworks/ auctions/ search/ favorites/ account/ notifications/ points/ main/
  services/                image / auction / bonus / tag / notification
  commands.py              init-db / seed-tags / seed-users / seed-demo / close-auctions
  templates/               画面 1〜11 + エラー
  static/css/js             style.css / canvas.js / detail.js
  uploads/artworks/        保存済み PNG（Git 管理外・静的公開しない）
DB-deploy/deploy.sql       スキーマの正
tests/                     pytest
```

## 9. 運用上の注意

- `.env` はコミットしないでください。`.env.example` にはキー名と例だけを載せています。
- 本番では `SECRET_KEY` を必ず設定してください（未設定かつ `FLASK_ENV=production` の場合は起動を拒否します）。
- MySQL の接続情報（ユーザー・パスワード）は `.env` のみで管理します。
- 画像の実体と `instance/` 配下の DB は配布物に含めない想定です。
