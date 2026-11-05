# HEW2026 v1.0 — Qoder（思考程度: 中）

Qoder Desktop エージェントが `設計・要件/` の要件定義書 Ver0.5 に基づいて実装したバージョン。
実装範囲は Ver0.5 の機能要件（認証・描画・出品・入札・自動入札・終了/落札・ボーナス・検索・お気に入り・通知・チャージ画面）で、6章の追加仕様（取消・再出品・配信・コメント）は未実装。

## 技術構成（要件定義書 7.4 に準拠）

| 分野 | 構成 |
| --- | --- |
| サーバー | Python / Flask（Application Factory + Blueprint） |
| フロント | HTML + CSS + Vanilla JS（Canvas 1,024×1,024px、IndexedDB 一時保存、独自形式レイヤーZIPをブラウザ側で生成） |
| DB | MariaDB（XAMPP、`mysql+pymysql`）。テストは SQLite |
| 認証 | Flask-Login + Werkzeug ハッシュ + Flask-WTF CSRF。ユーザー名認証・メール不使用・復旧コードはハッシュ保存 |
| 定期処理 | `flask close-auctions` を Windows タスクスケジューラから実行 |

## セットアップ

```powershell
cd HEW2026_v1.0_Qoder_中
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # SECRET_KEY / DATABASE_URL を設定
flask --app main db init; flask --app main db migrate -m "init"; flask --app main db upgrade
flask --app main seed-tags
flask --app main seed-users   # 開発用ユーザー（任意）
python main.py
```

イベント終了日時を設定する場合は `.env` の `EVENT_END_UTC`（ISO 形式・UTC）を使用する。未設定なら期間制限なし。

## テスト

```powershell
pip install pytest
$env:SECRET_KEY = "local-dummy-secret"
pytest
```

要件定義書 8 章の完成条件に対応するテストを `tests/` に収める（認証・描画保存・出品・入札/返却・自動入札・終了/落札・ポイント整合・タグAND検索・お気に入り・通知）。

## 主な設計判断

- 入札は `auctions` 行を `SELECT ... FOR UPDATE` でロックし、残高・入札履歴・取引履歴・現在価格を同一トランザクションで更新する（SQLite テストではロック句は無視される）。
- 最高入札者自身の増額は差額だけ消費、別ユーザーの高値更新時は前最高入札者へ入札額を即返却する。
- 自動入札は反復処理で 1pt 単位に競り上げ、同額上限は設定日時が早い方を優先。実行時の残高不足は停止して本人へ通知する。
- ボーナスは `bonus_grants.grant_key` の一意制約で再送時の重複付与を防止（登録 1,000pt / 初出品 300pt / 正式保存 100pt は仮データ、描画ボーナスは日本時間の暦日で 1 日 1 回）。
- 正式保存は合成PNGとレイヤーZIPの両方の保存成功が条件。片方が失敗したら保存済みファイルを巻き戻す。保存猶予は期限後 60 秒。
- 時刻は UTC で保存し、`jst` テンプレートフィルターで日本時間表示。
- 原寸PNG・レイヤーZIPは公開静的ディレクトリに置かず、権限チェック付きルート（作者・落札確定済みの落札者）で配信する。
