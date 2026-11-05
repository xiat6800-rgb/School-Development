# HEW2026 v1.0

HEW（描いて・出品して・ポイントで競り合う）の v1.0 実装です。
対象範囲は Ver0.5（[要件定義書](../設計・要件/要件定義書.md) §5〜§5.9 と §8 の完成条件、
[仕様決定事項 2026/10/26](../設計・要件/仕様決定事項-2026-10-26.md) を正本とする）。
出品取消・再出品・制作配信・コメント（要件定義書 §6 の追加仕様）は対象外。

## 技術構成

- Python / Flask（Application Factory + Blueprint）
- Flask-Login / Werkzeug（パスワード・復旧コードのハッシュ）/ Flask-WTF（CSRF）
- Flask-SQLAlchemy + Flask-Migrate。開発は SQLite（`instance/hew_dev.db`）、
  本番は MariaDB（XAMPP）。目標スキーマは [DB-deploy/deploy.sql](DB-deploy/deploy.sql)
- 描画: Canvas + VanillaJS（1,024×1,024px 固定・最大10レイヤー・履歴50操作）
- ブラウザ内の一時保存: IndexedDB（ペン離し・レイヤー操作完了時）

## 機能

| 領域 | 内容 |
| --- | --- |
| 認証 | ユーザー名＋パスワード。メール不使用。復旧コードは1度だけ表示しハッシュ保存・使用後無効化。ログイン中はパスワード確認で再発行 |
| 描画 | 10秒・30秒・1分・5分の制限時間（開始後変更不可・サーバー管理）。Gペン/丸ペン/ぼかし/消しゴム、レイヤー追加・削除・順序・表示・不透明度（履歴対象） |
| 正式保存 | 合成PNG（5MiB以内）とレイヤー付きZIP（独自形式: PNG群＋manifest.json）の両方保存で成功。固定後60秒の保存猶予。保存後は加筆・差し替え不可 |
| 出品 | 下書きからタイトル・説明・タグ・開始価格（0以上の整数pt）・開催時間（5/10/15/20分・初期値10分）を設定し即時開始。イベント終了まで確保できない出品は拒否 |
| 入札 | 商品詳細画面内で完結。最小+1pt、自己入札禁止、残高確認、手動確認後の価格変動は再確認。高値更新で前最高入札者へ即時返還、自分の増額は差額のみ消費 |
| 自動入札 | 上限額の範囲で最小の勝ち額だけ競り上げる（1pt単位）。同額上限は先に設定したユーザー優先。上限全額は確保せず、実際の入札額だけ消費。残高不足は停止＋本人通知 |
| 終了・落札 | `flask close-auctions` で確定。最高入札者に落札、出品者へ全額（手数料なし）加算。入札なしは未落札。再実行でも加算・通知は重複しない |
| ボーナス | 登録1,000pt（1回）・初出品300pt（1回）・正式保存100pt（日本時間の暦日1日1回）。自動付与・再送で重複しない |
| 検索 | タグAND検索 |
| お気に入り | 作品（artwork_bookmarks）とオークション（bookmarks）を別テーブルで管理 |
| 通知 | アプリ内のみ。入札受付・高値更新・落札確定・未落札終了・自動入札停止。メールなし |
| ダウンロード | 作者と落札確定済みの落札者に原寸PNG・レイヤーZIPを提供。公開画像は一般閲覧継続 |
| 課金画面 | 遷移先のみ用意。Stripe通信・決済・残高変更なし |

## 起動

```powershell
cd HEW2026_v1.0
pip install -r requirements.txt
Copy-Item .env.example .env   # SECRET_KEY を書き換える
python main.py
```

### CLI

```powershell
$env:FLASK_APP = "main.py"
flask seed-users   # 開発用ユーザー（alice / bob / carol）
flask seed-tags    # 初期タグ
flask close-auctions   # 終了対象の競売を確定（タスクスケジューラから定期実行）
```

### テスト

```powershell
python -m pytest tests -q
```

## ディレクトリ

```
HEW2026_v1.0/
├── main.py                  # 開発サーバー
├── app/
│   ├── __init__.py          # Application Factory
│   ├── config.py            # 環境別設定（.env）
│   ├── extensions.py        # db / migrate / login_manager / csrf
│   ├── models/              # user, artwork, auction(+bid/auto), tag, favorite, point, notification
│   ├── auth/ artworks/ auctions/ search/ favorites/ points/ notifications/  # Blueprint
│   ├── services/            # 画面上でなく業務処理を担当
│   ├── commands.py          # seed-users / seed-tags / close-auctions
│   ├── templates/           # 日本語UI
│   └── static/js/canvas.js  # 描画・レイヤー・履歴・IndexedDB・タイマー
├── DB-deploy/deploy.sql     # MariaDB 目標スキーマ
└── tests/                   # 52 tests
```

## 補足

- 時刻は UTC で保存し、画面表示は日本時間想定（表示上は UTC 表記を明示）。
- 復旧コードとパスワードを両方失った場合は復旧できない旨を登録時に明示。
- イベント終了時刻は `EVENT_END_AT`（UTC ISO8601）で設定。終了で新規登録・
  描画開始・出品を停止し、競売の確定は `close-auctions` で完了させる。
