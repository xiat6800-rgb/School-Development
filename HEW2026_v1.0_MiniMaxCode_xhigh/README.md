# HEW2026 v1.0 — MiniMax Code / MiniMax M3.1 Flash 版

`../設計・要件` の **要件定義書 Ver.0.5（2026-10-26 更新）** と
**仕様決定事項-2026-10-26** に沿って実装した、
サイト上で描いた絵をポイントで競り合うオークションの Web システムです。

- サーバー: Python 3.13 / Flask（Application Factory + Blueprint）
- フロント: HTML / CSS / Vanilla JavaScript（Canvas 描画・多レイヤー）
- DB: MySQL 8 / MariaDB（utf8mb4）。開発確認用に SQLite へ切り替え可能
- 認証: Flask-Login + Werkzeug パスワードハッシュ（**ユーザー名認証・メール不使用**）
- フォーム: Flask-WTF（全 POST に CSRF）

> 対象範囲は **Ver0.5** です。出品取消・再出品・制作ライブ配信・配信コメントは
> 要件定義書6章の追加仕様として設計的对象に含まれますが、この版では
> **実装していません**（第 5 章「設計からの意図的な変更」を参照）。

---

## 1. すぐに動かす

```bash
cd HEW2026_v1.0_MiniMaxCode_MiniMaxM3.1Flash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

set FLASK_APP=main.py
python -m flask init-db
python -m flask seed-tags
python -m flask seed-users --password <開発用パスワード>
python -m flask seed-demo

python main.py
# http://127.0.0.1:5000
```

SQLite で試す場合は `.env` の `DATABASE_URL` を `sqlite:///hew_dev.db` に変更し、
`python -m flask init-db` でテーブルを作成してから同じ seed コマンドを実行します。

`seed-users` は `sample1` / `sample2` / `sample3` を作成し、指定したパスワードと
復旧コードを表示します。`seed-demo` は `sample1` を出品者としてデモ作品 3 点と
開催中のオークションを作成します。

## 2. MySQL（XAMPP / MariaDB）で動かす

1. `.env` の `DATABASE_URL` を環境に合わせて変更します（パスワードは `.env` のみ）。

```text
DATABASE_URL=mysql+pymysql://root:your-password@127.0.0.1:3306/hew?charset=utf8mb4
```

2. スキーマを作成します。

```bash
# 参照用 SQL をそのまま流す（DB 設計書の正）
mysql -u root -p < DB-deploy/deploy.sql

# または Flask-Migrate で管理する
python -m flask db init
python -m flask db migrate -m "HEW Ver0.5 schema"
python -m flask db upgrade
```

3. 初期データを投入します。

```bash
python -m flask seed-tags
python -m flask seed-users --password <開発用パスワード>
python -m flask seed-demo
```

`flask init-db` はモデル定義から直接テーブルを作る開発用の近道です。

## 3. 画面一覧（画面遷移図の Ver0.5 対象）

| 画面 | URL | 権限 | 内容 |
| --- | --- | --- | --- |
| 1 ホーム | `/` | ゲスト可 | 公開作品・開催中オークション・タグへの入口 |
| 2 商品詳細 | `/auctions/<id>` | 閲覧はゲスト可／入札はログイン | 画面内で入札（入力 → 確認 → 確定）、自動入札、お気に入り 2 種、入札履歴 |
| 4 支払い | `/points/payment` | ログイン | 遷移先のみ。決済通信なし |
| 5 絵を描く | `/artworks/draw` | ログイン | 10秒 / 30秒 / 1分 / 5分、Gペン・丸ペン・ぼかし・消しゴム、レイヤー操作、Undo/Redo、IndexedDB 復元、時間切れ自動保存 |
| 6 出品設定 | `/artworks/<id>/listing` | 作者のみ | タイトル・説明・タグ・開始価格・終了日時 |
| 7 通知 | `/notifications/` | ログイン | 一覧・既読・商品詳細へ |
| 8 ログイン / 新規登録 | `/auth/login` `/auth/register` | - | ユーザー名 + パスワード。登録時に復旧コードを 1 回表示 |
| 8-2 パスワード再設定 | `/auth/recover` | - | ユーザー名 + 復旧コードで再設定（使用後に無効化） |
| 9 アカウント | `/account/?tab=...` | ログイン | 下書き・出品中・作品/オークションお気に入り・自動入札・ポイント履歴・表示名編集・復旧コード再発行 |
| 10 ボーナスポイント | `/points/bonus` | ログイン | 付与条件・残高・履歴 |
| 11 チャージ | `/points/charge` | ログイン | 課金未提供である旨を表示 |
| タグ検索 | `/search/` | ゲスト可 | 複数タグは AND、キーワード併用可 |

画面 3（専用入札画面）は商品詳細へ統合済み。画面 12・13（ライブ配信）と 14（管理画面）は
Ver0.5 の対象外のため実装していません。

## 4. 要件と実装の対応

| 要件 | 実装 |
| --- | --- |
| 5.1 登録・ログイン | `app/auth/`、`app/services/auth_service.py`。ユーザー名は一意、パスワードは Werkzeug でハッシュ化。表示名の初期値は `user{id}` で編集可能。復旧コードはハッシュ保存・使用後無効化 |
| 5.2 描画・下書き保存 | `app/static/js/canvas.js`（サーバー期限・多レイヤー・IndexedDB 一時保存・50 操作履歴）、`app/services/image_service.py`（PNG 署名・IHDR 寸法・容量を検証）、`app/services/layer_service.py`（レイヤー検証と ZIP 化）。保存後の加筆ルートは存在しない |
| 5.3 出品＝オークション開始 | `app/artworks/routes.py`・`app/services/auction_service.py`。`draft → listed` と同時に `auctions(status=active)` を作成。1 作品 1 オークション（UNIQUE） |
| 5.4 入札・消費・返却 | `app/services/auction_service.py`。`auctions` → 入札者 → 前最高入札者の順に `SELECT ... FOR UPDATE`。残高減算・入札・`wallet_transactions`・`current_price` を同一トランザクションで更新。高値更新時は前最高入札者へ同額返却 |
| 5.5 自動入札 | 同じトランザクション内で上限額と残高の範囲内のみ上乗せ。同額上限なら `created_at` が早い設定を優先 |
| 5.6 終了・落札 | `flask close-auctions`。`winner_id / winner_bid_id / final_price / status=ended / closed_reason=time_expired` を記録。出品者へ落札額全額を加算。入札なしは落札者なし、落札時の再差し引きなし |
| 5.7 ボーナス・課金 | `app/services/point_service.py`（登録・初出品・描画保存）。チャージ／支払いは表示のみで、決済通信・残高変更なし |
| 5.8 検索・お気に入り | `app/services/tag_service.py`（タグ AND は `GROUP BY ... HAVING COUNT(DISTINCT tag) = 選択数`）。`bookmarks` と `artwork_bookmarks` を分離 |
| 5.9 通知 | `app/services/notification_service.py`。アプリ内通知のみ（メールは使わない） |
| 7.3 セキュリティ | 全 POST に CSRF、所有者チェック、画像は静的ディレクトリ外＋権限付きルート、UTC 保存＋日本時間表示、秘密情報は `.env` のみ |

### 未決事項（仕様決定事項 10章）の既定値

`.env` で変更できます。決定が変わってもコード修正なしで追従できます。

| 項目 | 既定値・扱い |
| --- | --- |
| ボーナス付与 | 登録 1,000pt（1回）／初出品 300pt（1回）／描画 100pt（日本時間 1 日 1 回） |
| 自動入札の上乗せ幅 | 最小 1pt 上乗せ（`BID_MIN_INCREMENT`） |
| 同額上限 | 設定日時が早いユーザーを優先 |
| 残高不足の自動入札 | その回は発動せず、設定を停止し本人へ通知 |
| 入札なしで終了した作品 | `listed` のまま（再出品は Ver0.5 対象外） |
| 画像上限 | 合成 PNG 5MiB・レイヤー PNG 各 5MiB・展開後合計 50MiB（仮上限）／Canvas は 1024×1024 |
| 描画の保存猶予 | 期限到達または完成操作から 60 秒（`SAVE_GRACE_SECONDS`） |
| 落札後のポイント移転 | Ver0.5 では行わない（未決のため） |

## 5. 設計書からの意図的な変更

- **メールアドレスを廃止**し、ユーザー名 + 復旧コードの認証に変更しました（仕様決定事項1章）。
- **レイヤー ZIP はサーバー側で組み立てます**。ブラウザは合成 PNG と各レイヤーの PNG を
  送信し、サーバーが `layers/*.png` と `manifest.json`（名前・順序・表示・不透明度）を
  含む ZIP を作ります。編集履歴（undo/redo）は含めません。作成は `app/services/layer_service.py`。
- **`bids.auction_id` の UNIQUE を撤廃**し、同一オークションへの複数入札・自動入札の
  履歴を保存できるようにしました（db設計 5.2 の運用方針）。
- **自動入札は「代理入札」として解決**します。競り上げ額は、上限額が最も高い設定者が
  勝つために必要な最小額（2 番目に高い上限額 + 1，上限内のみ）。同額の上限は設定が
  早い用户在優先します。上限全額は確保せず、実際に入札した額だけを消費します。
- `reserve_price` は項目だけ残し、落札判定では使用しません。
- 描画終了を理由とするオークション終了（`seller_finished`）は行いません。
- 保存後に編集できるのは出品情報（タイトル・説明・タグ）だけです。描画画面へ戻る導線は
  作りません。
- PNG は `app/uploads/artworks/`（static の外）へ保存し、`/artworks/<id>/image` の権限チェック
  経由で配信します。下書きを URL 直打ちで閲覧できないようにするためです。
- 開発確認用に SQLite を許容します（`.env` の `DATABASE_URL` を差し替えるだけ）。
  テストも `TEST_DATABASE_URL` 未設定時は一時 SQLite で実行します。
- `payment_intents`・`notification_deliveries`・`unsloth_compiled_cache` は
  現行 SQL にあるが Ver0.5 の要件に不要のため本版では作らず、テーブルも持たない。

## 6. テスト

```bash
python -m pytest -q
```

54 件のテストが主要な画面遷移と業務ルールを検証します。

- 登録・ログイン・ログアウト、重複ユーザー名、復旧コードでの再設定と使用後の無効化
- 描画セッションの期限確定、不正な PNG／レイヤーの拒否、正式保存、描画ボーナスの 1 日 1 回
- 保存後の再保存拒否、猶予切れの拒否、下書きの権限チェック
- 出品（開始価格・開催時間・画像必須）、入札（消費・差額・返還・自己入札・残高不足・
  期限切れ）、終了確定（落札者・出品者加算・二重加算なし・入札なし終了）
- 自動入札（競り上げ・同額優先・残高不足で停止と通知）、CLI `close-auctions` の永続化
- タグ AND 検索、作品／オークションのお気に入り登録・解除、通知の生成と既読（所有者チェック）

スモークテスト（実サーバー相当の通し確認）:

```bash
python tools/smoke_check.py
```

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
  config.py                環境別設定（.env 読み込み）
  extensions.py            db / migrate / login_manager / csrf
  utils.py                 UTC↔JST・残り時間
  models/                  user artwork drawing_session auction bid auto_bid tag
                           favorite wallet(+bonus) notification
  auth/ artworks/ auctions/ account/ search/ favorites/ notifications/ points/ main/
  services/                auth / image / layer / artwork / auction / point / tag / notification
  commands.py              init-db / seed-tags / seed-users / seed-demo / close-auctions
  templates/               画面 1〜11 + エラーページ
  static/css/js            style.css / canvas.js / detail.js
  uploads/                 保存済み PNG とレイヤー ZIP（Git 管理外・静的公開しない）
DB-deploy/deploy.sql       スキーマの正
tests/                     pytest
tools/smoke_check.py       通しの動作確認
tools/make_preview_pages.py  ログイン後画面の静的プレビュー生成（開発用）
tools/cdp_shot.py          実幅ピクセルのスクリーンショット取得（開発用・CDP 経由）
```

## 9. ビジュアル設計

この版の CSS は **「製図図面の落札所」** をテーマとしています。
入札＝製図の落札、という行為の比喩をそのまま画面構成に落とし込んだものです。

| 層 | 表現 | 実装 |
| --- | --- | --- |
| 地 | 深靛の方眼製図用紙 | `body` に 2 段の repeating-linear-gradient で 20mm 方眼 |
| 題字欄 | ヘッダーに SHEET 01/01・REV v1.0・落札所 の表題欄 | `header .sheet-mark` / `.header-actions` |
| 用紙片 | 白のカードが図面の上に浮く | `.card` は紙色地＋**硬投影**（ぼかしなし）＋切り取りマーク |
| 道具立 | 描画ツールは右側の縦什器 | `.studio` は `grid-template-columns: minmax(0,1fr) 264px` |

設計上の決定:

- **色は文脈で切り替わる**。図面上では `--text` が明色、用紙片の上では墨色へ切り替わります
  （`.card` 内で CSS 変数を上書き）。同じクラス名でも紙の上と図の上で読み方が変わりません。
- **角丸は最小**。角丸 2px まで。罫線はヘアライン（1px）＋太罫（2px）の 2 種。
- **状態色は意味に固定**。開催中＝琥珀 `#c08a1e`、落札＝朱 `#b23a2f`、終了＝灰。
- **影はぼかさない**。`box-shadow: 3px 3px 0` のような硬い影で「紙が図面に乗っている」
  物理感を出しています。
- **タイポグラフィ 3 種**。見出し＝日文明朝（Yu Mincho / Hiragino Mincho ProN）、
  本文＝ゴシック、数値・ID・価格＝等幅。すべてシステムフォントスタックで、
  外部フォント・CDN への依存はありません。
- **アクセシビリティ**。`:focus-visible` に琥珀の 2px 枠、落槌タイマーは
  `@media (prefers-reduced-motion: reduce)` で脈動を停止。レスポンシブは 1024px / 640px の 2 段。

`app/static/css/style.css` は 9 節構成（トークン → 基盤 → 題字欄 → 用紙片 → 部品 →
フォーム → 表一覧 → 描画台 → レスポンシブ）。コメントは日本語で記述しています。

> 描画画面の DOM 契約（`canvas.js` / `detail.js` が参照する id・data 属性・form action）は
> CSS 再設計でも変更していません。レイアウトのみ `.studio` ラッパーへ組み替えています。

## 10. 運用上の注意

- `.env` はコミットしないでください。`.env.example` にはキー名と例だけを載せています。
- 本番では `SECRET_KEY` を必ず設定してください（未設定かつ `FLASK_ENV=production` の場合は
  起動を拒否します）。
- MySQL の接続情報（ユーザー・パスワード）は `.env` のみで管理します。
- 画像の実体と `instance/` 配下の DB は配布物に含めない想定です。
- 入札処理は `SELECT ... FOR UPDATE` を使うため、MySQL / MariaDB では InnoDB で
  動作してください。SQLite は開発・テスト専用です。
