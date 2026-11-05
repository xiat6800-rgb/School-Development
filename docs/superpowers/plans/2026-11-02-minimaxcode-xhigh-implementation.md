# HEW2026 v1.0 — MiniMax Code xhigh 版 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `HEW2026_v1.0_MiniMaxCode_xhigh/` に、HEW2026 の正本（要件定義書 Ver0.5 + 仕様決定事項-2026-10-26）に基づく Web システムを実装する。対象範囲は Ver0.5 全機能 + 出品取消・再出品・管理画面。既定 DB は MySQL 8.0。

**Architecture:** Flask の Application Factory + Blueprint。routes（HTTP・認証・入力変換）→ services（業務ルール）→ models（表定義）の 3 層。競売の排他制御は MySQL の `SELECT ... FOR UPDATE` で行い、ロック取得順は auctions → artworks → users(ID 昇順) に固定する。ポイントの預託・返還は入札行の `held_points` で追跡し、台帳の一意キー `reference_key` で二重実行を防ぐ。

**Tech Stack:** Python 3.13 / Flask 3.1 / Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 / Flask-Login / Flask-WTF / Flask-Migrate / PyMySQL / MySQL 8.0 / Jinja2 / Vanilla JS + Canvas 1024×1024 / pytest

**設計書:** `docs/superpowers/specs/2026-11-01-minimaxcode-xhigh-design.md`（2026-11-02 改訂）

## Global Constraints

- 成果物の置き場所は `HEW2026_v1.0_MiniMaxCode_xhigh/` のみ。`HEW2026_v1.0_MiniMaxCode_high/`・`HEW2026_v1.0_TraeWorkCN_高/`・`HEW2026_v0.5_Chatbox_DeepSeek4.1Flash/` 配下のファイルは **1 つも変更しない**（読み取り専用）。
- 既定 DB は MySQL 8.0。開発庫 `hew_xhigh` / テスト庫 `hew_xhigh_test` を使い、**`hew`・`hew_test`・`hew_acceptance` には接続しない**（TraeWorkCN 版が `hew` を使用中）。
- `.env` は Git 管理外。接続情報は `.env` にだけ書き、`.env.example` はプレースホルダのみ。
- 時刻は UTC で保存し、画面表示時のみ JST（+9h）へ変換する（`app/utils.py` の `to_jst` / `format_jst` を使う）。
- 命名は `設計・要件/関数定義.md` に従う。ルートは `show_`/`get_`/`list_`/`create_`/`update_`/`is_`/`can_`/`validate_`、業務動作は「動詞 + 対象」（`place_bid` / `cancel_auction` / `create_relisted_auction`）。
- 1 行 79 文字以内、コメント・docstring は 72 文字以内（PEP 8）。
- 状態を書き換える POST はすべて CSRF 対象（Flask-WTF）。テスト時のみ `WTF_CSRF_ENABLED = False`。
- ユーザー・作品・競売は物理削除しない。台帳（`wallet_transactions`）・通知・取消履歴は追記のみ。
- 入札・取消・終了確定は同一トランザクションで処理する。`SELECT ... FOR UPDATE` のロック順は auctions → artworks → users(ID 昇順)。
- サービス層は HTTP に依存しない。エラーは `app/services/errors.py` の例外で投げ、ルート層で flash に変換する。
- 実課金・Stripe・NFT・吊り上げ bot・予約開始・ライブ配信・配信コメントは実装しない。

## File Structure

| パス | 責務 |
| --- | --- |
| `main.py` | 開発サーバー起動 |
| `app/__init__.py` | Application Factory。拡張・Blueprint・CLI・エラーハンドラの登録 |
| `app/config.py` | 環境別設定。`.env` 読み込み。既定は MySQL |
| `app/extensions.py` | `db` / `migrate` / `login_manager` / `csrf` 単一インスタンス |
| `app/utils.py` | UTC↔JST・残り時間・日次キー |
| `app/commands.py` | `init-db` / `seed-tags` / `seed-users` / `seed-demo` / `close-auctions` / `promote-admin` |
| `app/models/` | 表定義のみ。業務ロジック禁止 |
| `app/services/` | 業務ルール。入札・返還・取消・通知・bonus |
| `app/*/routes.py` | HTTP 層。1 ルート 25 行以内 |
| `app/templates/` | Jinja2 画面 |
| `app/static/css/style.css` | 製図図面の落札所テーマ（high 版と別構成で書き直す） |
| `app/static/js/canvas.js` / `detail.js` | 描画 UI・入札 UI。DOM 契約は high 版と同一 |
| `migrations/` | Flask-Migrate のマイグレーション |
| `tests/` | pytest |
| `DB-deploy/deploy.sql` | スキーマの正（参照用） |

---

### Task 1: 基座の複製と MySQL 既定化

`HEW2026_v1.0_MiniMaxCode_high/` を基点として複製し、DB を MySQL 既定に切り替える。以降すべてのタスクはこのディレクトリで進める。

**Files:**
- Create: `HEW2026_v1.0_MiniMaxCode_xhigh/**`（high 版から複製）
- Create: `HEW2026_v1.0_MiniMaxCode_xhigh/.env`
- Modify: `HEW2026_v1.0_MiniMaxCode_xhigh/.env.example`
- Modify: `HEW2026_v1.0_MiniMaxCode_xhigh/app/config.py`
- Test: `HEW2026_v1.0_MiniMaxCode_xhigh/tests/test_config.py`

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces: `app.config.DEFAULT_DATABASE_URL` / `DEFAULT_TEST_DATABASE_URL` / `Config` / `TestingConfig`。以降すべてのタスクが `create_app()` の `app.config["SQLALCHEMY_DATABASE_URI"]` を前提にする。

- [ ] **Step 1: ディレクトリを複製する**

```powershell
$ErrorActionPreference = 'Stop'
$base = 'C:\Users\12764\Desktop\学校开发\HEW2026'
$src  = Join-Path $base 'HEW2026_v1.0_MiniMaxCode_high'
$dst  = Join-Path $base 'HEW2026_v1.0_MiniMaxCode_xhigh'
if (Test-Path $dst) { throw "既に存在: $dst" }
robocopy $src $dst /E /XD __pycache__ .pytest_cache instance .idea app\uploads /XF .env *.pyc *.db
if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }
New-Item -ItemType Directory -Force -Path (Join-Path $dst 'app\uploads\artworks') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dst 'app\uploads\layers') | Out-Null
Set-Content -Encoding UTF8 (Join-Path $dst 'app\uploads\artworks\.gitkeep') ''
Set-Content -Encoding UTF8 (Join-Path $dst 'app\uploads\layers\.gitkeep') ''
```

- [ ] **Step 2: 複製が成功し、high 版が無傷であることを確認する**

```powershell
git -C 'C:\Users\12764\Desktop\学校开发\HEW2026' status --porcelain -- HEW2026_v1.0_MiniMaxCode_high
```
Expected: 出力なし（high 版に差分が無いこと）

- [ ] **Step 3: MySQL の専用データベースを作成する**

```powershell
$env:MYSQL_PWD = 'JIE2651xt.'
& 'D:\Program Files\mysql-8.0.43-winx64\bin\mysql.exe' -u root -h 127.0.0.1 -P 3306 -e @"
CREATE DATABASE IF NOT EXISTS hew_xhigh CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE DATABASE IF NOT EXISTS hew_xhigh_test CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
"@
```
Expected: エラーなし。`show databases;` で `hew_xhigh` と `hew_xhigh_test` が並ぶ

- [ ] **Step 4: `.env` を書く**

`HEW2026_v1.0_MiniMaxCode_xhigh/.env` を作成（Git 管理外・`.gitignore` 済み）:

```text
FLASK_ENV=development
SECRET_KEY=dev-only-change-me-1f4c9a7b2e6d8a3c5b0e9f1a2c3d4e5f

DATABASE_URL=mysql+pymysql://root:JIE2651xt.@127.0.0.1:3306/hew_xhigh?charset=utf8mb4
TEST_DATABASE_URL=mysql+pymysql://root:JIE2651xt.@127.0.0.1:3306/hew_xhigh_test?charset=utf8mb4
SQL_ECHO=false

UPLOAD_FOLDER=app/uploads
MAX_IMAGE_BYTES=5242880
MAX_LAYER_BYTES=5242880
MAX_LAYER_TOTAL_BYTES=52428800
MAX_LAYERS=10
CANVAS_SIZE=1024
SAVE_GRACE_SECONDS=60

BID_MIN_INCREMENT=1
DEFAULT_AUCTION_MINUTES=10
EVENT_END_AT=

BONUS_SIGNUP_POINTS=1000
BONUS_FIRST_LISTING_POINTS=300
BONUS_DRAW_POINTS=100
ADMIN_ADJUST_MAX_POINTS=100000
```

- [ ] **Step 5: `.env.example` をプレースホルダに整える**

`HEW2026_v1.0_MiniMaxCode_xhigh/.env.example` の該当行を次に置き換える（他の行は既存のコメント付きのまま残す）:

```text
# --- データベース（既定は MySQL） ---
DATABASE_URL=mysql+pymysql://root:<password>@127.0.0.1:3306/hew_xhigh?charset=utf8mb4
TEST_DATABASE_URL=mysql+pymysql://root:<password>@127.0.0.1:3306/hew_xhigh_test?charset=utf8mb4
SQL_ECHO=false
```

- [ ] **Step 6: `app/config.py` の DB 既定値を MySQL にする**

`app/config.py` の `load_dotenv()` 呼び出しの直後に次の定数を追加する:

```python
DEFAULT_DATABASE_URL = (
    "mysql+pymysql://root:root@127.0.0.1:3306/hew_xhigh?charset=utf8mb4"
)
DEFAULT_TEST_DATABASE_URL = (
    "mysql+pymysql://root:root@127.0.0.1:3306/hew_xhigh_test?charset=utf8mb4"
)
```

`Config` クラス側を次のように置き換える:

```python
    # --- データベース ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )
```

`TestingConfig` 側を次のように置き換える:

```python
    # 既定は専用の MySQL テストデータベース。SQLite は明示指定時のみ。
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL
    )
```

- [ ] **Step 7: 失敗するテストを書く**

`tests/test_config.py` を作成:

```python
"""設定の既定値が MySQL であることを確かめる。"""

from app.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    Config,
    TestingConfig,
)


def test_default_urls_point_to_mysql():
    assert DEFAULT_DATABASE_URL.startswith("mysql+pymysql://")
    assert "hew_xhigh" in DEFAULT_DATABASE_URL
    assert DEFAULT_TEST_DATABASE_URL.startswith("mysql+pymysql://")
    assert "hew_xhigh_test" in DEFAULT_TEST_DATABASE_URL


def test_effective_uris_are_mysql():
    assert Config.SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://")
    assert TestingConfig.SQLALCHEMY_DATABASE_URI.startswith("mysql+pymysql://")


def test_dev_and_test_databases_are_separated():
    dev = Config.SQLALCHEMY_DATABASE_URI
    test = TestingConfig.SQLALCHEMY_DATABASE_URI
    assert dev != test
    assert "hew_xhigh_test" not in dev
```

- [ ] **Step 8: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_config.py -q
```
Expected: 3 passed

- [ ] **Step 9: 複製した既存テストが MySQL 上で通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: high 版から複製した全テストが PASS する（MySQL でも通ることの確認。落ちた場合は SQLite 固有依存を `tests/conftest.py` で解消してから次へ進む）

- [ ] **Step 10: マイグレーションの基準を作り、起動確認する**

Task 2 以降は `flask db migrate` で差分を作るため、Task 1 で**ベースラインの
マイグレーションを先に確定**する。`flask init-db`（`db.create_all()`）を先に
実行すると、Task 2 の `db migrate` が全テーブルを CREATE する差分を作り、
`db upgrade` が「テーブルが既に存在する」で失敗する。

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
$env:FLASK_APP = 'main.py'
python -m flask db init
python -m flask db migrate -m "baseline: Ver0.5 schema (high 版から継承)"
python -m flask db upgrade
python -m flask seed-tags
python -m flask routes | Select-Object -First 5
```
Expected: `migrations/` が生成され、upgrade が成功する。ルート一覧に `/`
`/auctions/<int:auction_id>` 等が並ぶ

`flask init-db`（`db.create_all()`）は開発用の近道として CLI には残すが、
マイグレーションの基準が確立した後は使わない（Task 2 の差分が適用できなくなる）。

- [ ] **Step 11: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): high 版を基点複製し、既定 DB を MySQL へ切替"
```

---

### Task 2: データモデルの刷新

`active_slot` / `held_points` / `reference_key` / `auction_cancellations` を導入する。high 版の `auctions.artwork_id` UNIQUE では「取消後に再出品して履歴を保持する」を表現できないため、UNIQUE を撤去して `active_slot` に置き換える。

**Files:**
- Modify: `app/models/auction.py`
- Modify: `app/models/artwork.py`
- Modify: `app/models/bid.py`
- Modify: `app/models/wallet.py`
- Modify: `app/models/notification.py`
- Create: `app/models/cancellation.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/0001_xhigh_schema.py`
- Test: `tests/test_models_xhigh.py`

**Interfaces:**
- Consumes: Task 1 の `create_app()` と MySQL 接続
- Produces:
  - `Auction.active_slot`（`1` = 開催中 / `NULL` = 終了・取消済み）、`Auction.previous_auction_id`、`Auction.CANCELLED`
  - `Artwork.CANCELLED` / `Artwork.HIDDEN`、`Artwork.hidden_reason` / `hidden_at` / `hidden_by_id`、`Artwork.active_auction` プロパティ
  - `Bid.held_points`
  - `WalletTransaction.reference_key`
  - `Notification.revoked_at` / `revoked_by_id` / `revoke_reason`
  - `AuctionCancellation` モデルと `app.models.cancellation` の定数

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_models_xhigh.py` を作成:

```python
"""xhigh 版で追加・変更したモデルの確認。"""

from app.extensions import db
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.cancellation import AuctionCancellation
from app.models.notification import Notification
from app.models.wallet import WalletTransaction


def test_auction_has_active_slot_and_previous_link(app):
    columns = {c.name for c in Auction.__table__.columns}
    assert "active_slot" in columns
    assert "previous_auction_id" in columns


def test_artwork_auction_relationship_is_a_list(app):
    assert isinstance(Artwork.__mapper__.relationships["auction"].uselist, bool)
    assert Artwork.__mapper__.relationships["auction"].uselist is True


def test_bid_tracks_held_points(app):
    assert "held_points" in {c.name for c in Bid.__table__.columns}


def test_wallet_transaction_has_reference_key(app):
    assert "reference_key" in {c.name for c in WalletTransaction.__table__.columns}


def test_notification_can_be_revoked(app):
    columns = {c.name for c in Notification.__table__.columns}
    assert {"revoked_at", "revoked_by_id", "revoke_reason"} <= columns


def test_auction_cancellations_table_exists(app):
    assert db.session.execute(
        db.text("SHOW TABLES LIKE 'auction_cancellations'")
    ).first() is not None


def test_only_one_active_auction_per_artwork(app, make_user, make_artwork):
    """UNIQUE (artwork_id, active_slot) が開催中 1 件しか作れないこと。"""
    from sqlalchemy.exc import IntegrityError

    seller = make_user("seller")
    artwork = make_artwork(seller)
    now = db.func.now()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    db.session.commit()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    else:
        db.session.rollback()
        raise AssertionError("同時開催の競売が 2 件作れてしまった")


def test_closed_auction_frees_the_active_slot(app, make_user, make_artwork):
    """終了後は active_slot が NULL になり、再出品の余地ができる。"""
    seller = make_user("seller")
    artwork = make_artwork(seller)
    now = db.func.now()
    auction = Auction(
        artwork_id=artwork.id,
        start_price=1,
        current_price=1,
        status="active",
        active_slot=1,
        start_time=now,
        end_time=now,
    )
    db.session.add(auction)
    db.session.commit()
    auction.status = "ended"
    auction.active_slot = None
    db.session.commit()
    db.session.add(
        Auction(
            artwork_id=artwork.id,
            start_price=1,
            current_price=1,
            status="active",
            active_slot=1,
            start_time=now,
            end_time=now,
        )
    )
    db.session.commit()
    assert Auction.query.filter_by(artwork_id=artwork.id).count() == 2


def test_auction_cancellation_record_fields(app):
    columns = {c.name for c in AuctionCancellation.__table__.columns}
    assert {
        "auction_id",
        "artwork_id",
        "action",
        "actor_id",
        "reason",
        "refunded_points",
    } <= columns
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_models_xhigh.py -q
```
Expected: FAIL（`active_slot` 等のカラムが無い、`app.models.cancellation` が無い）

- [ ] **Step 3: `app/models/auction.py` を書き換える**

定数と `Auction` クラスを次のように置き換える（`accepted_bids` / `top_bid` / `is_active` / `has_winner` はそのまま残す）:

```python
ACTIVE = "active"
ENDED = "ended"
CANCELLED = "cancelled"

REASON_TIME_EXPIRED = "time_expired"
REASON_SELLER_CANCELLED = "seller_cancelled"
REASON_ADMIN_CANCELLED = "admin_cancelled"
REASON_HIDDEN = "hidden"

# 開催中のときだけ 1 が入る。MySQL の UNIQUE 制約は NULL 同士を
# 衝突させないので、UNIQUE (artwork_id, active_slot) により
# 「同一作品で同時開催の競売は高々 1 件」が DB で保証される。
ACTIVE_SLOT = 1


class Auction(db.Model):
    """作品の競売。"""

    __tablename__ = "auctions"
    __table_args__ = (
        db.UniqueConstraint(
            "artwork_id", "active_slot", name="uq_auctions_artwork_active_slot"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    start_price = db.Column(db.Integer, nullable=False, default=0)
    current_price = db.Column(db.Integer, nullable=False, default=0)
    reserve_price = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ACTIVE, index=True)
    active_slot = db.Column(db.Integer, nullable=True, default=ACTIVE_SLOT)
    previous_auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    winner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    winner_bid_id = db.Column(
        db.Integer,
        db.ForeignKey("bids.id", use_alter=True, name="fk_auctions_winner_bid"),
        nullable=True,
    )
    final_price = db.Column(db.Integer, nullable=True)
    closed_reason = db.Column(db.String(30), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    winner = db.relationship("User", foreign_keys=[winner_id])
    bids = db.relationship(
        "Bid",
        backref="auction",
        order_by="Bid.created_at",
        lazy="selectin",
        foreign_keys="Bid.auction_id",
    )
```

- [ ] **Step 4: `app/models/artwork.py` を書き換える**

定数ブロックと `Artwork` の該当部分を次のようにする:

```python
DRAFT = "draft"
LISTED = "listed"
SOLD = "sold"
CANCELLED = "cancelled"
HIDDEN = "hidden"
```

```python
    image_path = db.Column(db.String(500), nullable=True)
    layer_archive_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=DRAFT, index=True)
    hidden_reason = db.Column(db.String(300), nullable=True)
    hidden_at = db.Column(db.DateTime, nullable=True)
    hidden_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    save_completed_at = db.Column(db.DateTime, nullable=True)
```

作品と競売の relation は 1 対多へ変更する（再出品で競売が増えるため）:

```python
    auction = db.relationship(
        "Auction", backref="artwork", cascade="all, delete-orphan"
    )
```

`Artwork` に次のプロパティを追加する（既存コードの `artwork.auction` 相当を担保する）:

```python
    @property
    def active_auction(self):
        """開催中の競売を返す。なければ None。"""
        for auction in self.auctions:
            if auction.status == ACTIVE:
                return auction
        return None

    @property
    def is_hidden(self) -> bool:
        """管理者によって非公開化された作品かどうかを返す。"""
        return self.status == HIDDEN
```

**この relation をリスト化すると壊れる呼び出し箇所（Task 2 で必ず直す）**

`Artwork.auction` がスカラーからリストになると、`artwork.auction.id` や
`artwork.auction is not None` が意味を失う。次の 7 箇所を
`artwork.active_auction` に置き換えること（Task 4 ではなく **Task 2** で直す）。

1. `app/services/auction_service.py:72` —
   `if artwork.auction is not None:` → `if artwork.active_auction is not None:`
2. `app/artworks/routes.py:236` — `auction = artwork.auction` →
   `auction = artwork.active_auction`
3. `app/templates/account/index.html:94,96,98` —
   `artwork.auction.current_price` / `artwork.auction.id` を
   `artwork.active_auction.current_price` / `artwork.active_auction.id` に。
   既存の `{% if artwork.auction %}` は `{% if artwork.active_auction %}` に
4. `app/templates/account/index.html:120,122` — `favorite.artwork.auction.id` →
   `favorite.artwork.active_auction.id`（条件も同様に）
5. `app/templates/search/index.html:41,43,44` — `artwork.auction` を
   `artwork.active_auction` に

**テスト側**（既存テストの書き換え。テストの意図は変えない）:

- `tests/test_artworks.py:159` — `assert artwork.auction is None` →
  `assert artwork.active_auction is None`
- `tests/test_artworks.py:181` — `auction = refreshed.auction` →
  `auction = refreshed.active_auction`

**変えてはいけないもの**：`Auction.artwork`（backref 側）と
`auction.artwork` はスادئルのままである。`app/auctions/routes.py:24,58`、
`app/templates/auctions/detail.html:105`、`account/index.html:138-141` などは
`auction.artwork` を使うため変更不要。

`app/models/artwork.py` の先頭 import に `from app.models.auction import ACTIVE` を追加する。`auction.py` は `app.extensions` と `app.utils` しか import しないので循環参照は発生しない。

`Artwork.is_public` は「非 draft なら公開」のまま据え置く（取消済み・未落札終了は
下書きへ戻さず公開履歴として残すのが正本 6 章の考え方だから）。ただし公開状態を
列挙している箇所は Task 8 Step 5 で 4 箇所まとめて更新する。

- [ ] **Step 5: `app/models/bid.py` に `held_points` を追加する**

```python
    bid_amount = db.Column(db.Integer, nullable=False)
    # 入札受理時に残高から差し引いた額のうち、まだ返却していない額。
    # 最高入札の入札行だけが正の値を保持する。
    held_points = db.Column(db.Integer, nullable=False, default=0)
    is_auto_bid = db.Column(db.Boolean, nullable=False, default=False)
```

- [ ] **Step 6: `app/models/wallet.py` に `reference_key` を追加する**

```python
    related_bid_id = db.Column(
        db.Integer, db.ForeignKey("bids.id"), nullable=True
    )
    # 同一キーの再実行で台帳に 2 行目を追加しないための一意キー。
    reference_key = db.Column(
        db.String(120), nullable=True, unique=True, index=True
    )
    reason = db.Column(db.String(300), nullable=True)
```

- [ ] **Step 7: `app/models/notification.py` に失効カラムを追加する**

```python
    related_bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    revoke_reason = db.Column(db.String(300), nullable=True)
```

- [ ] **Step 8: `app/models/cancellation.py` を新規作成する**

```python
"""取消・非公開の操作履歴。

作品・競売・入札の履歴は削除しない。操作の事実だけを残す。
"""

from __future__ import annotations

from app.extensions import db
from app.utils import utcnow

ACTION_SELLER_CANCEL = "seller_cancel"
ACTION_ADMIN_CANCEL = "admin_cancel"
ACTION_HIDE = "hide"
ACTION_RESTORE = "restore"


class AuctionCancellation(db.Model):
    """取消・非公開化・公開復帰の操作履歴。"""

    __tablename__ = "auction_cancellations"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer, db.ForeignKey("auctions.id"), nullable=True, index=True
    )
    artwork_id = db.Column(
        db.Integer, db.ForeignKey("artworks.id"), nullable=False, index=True
    )
    action = db.Column(db.String(30), nullable=False, index=True)
    actor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    reason = db.Column(db.String(300), nullable=True)
    refunded_points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    actor = db.relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:  # pragma: no cover - デバッグ用
        return f"<AuctionCancellation {self.id} {self.action}>"
```

- [ ] **Step 9: `app/models/__init__.py` と `app/services/__init__.py` を更新する**

`app/models/__init__.py` は 13 個的名字を `__all__` で公開している。ここに
`AuctionCancellation` を追加する。

```python
from app.models.cancellation import AuctionCancellation

__all__ = [
    "Artwork",
    "ArtworkFavorite",
    "ArtworkTag",
    "Auction",
    "AuctionCancellation",
    "AuctionFavorite",
    "AutoBidSetting",
    "Bid",
    "BonusGrant",
    "DrawingSession",
    "Notification",
    "Tag",
    "User",
    "WalletTransaction",
]
```

`app/services/__init__.py` も同様に、`cancellation_service` と `event_service` を
import して `__all__` に追加する。

```python
from app.services import cancellation_service  # noqa: F401
from app.services import event_service  # noqa: F401
```

- [ ] **Step 10: マイグレーションを作る**

Task 1 でベースライン移行（`050023b212ca`）が既に存在する。ここでは**差分だけ**を
生成する。`flask db init` は**，絶対に**実行しない（`migrations/` が既にあるので
エラーになる）。

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
$env:FLASK_APP = 'main.py'
python -m flask db migrate -m "xhigh schema: active_slot / held_points / reference_key / cancellations"
python -m flask db upgrade
```
Expected: 差分用のバージョンファイル（`migrations/versions/` 配下に 2 つ目）が
生成され、upgrade が成功する

**生成されたマイグレーションを目視確認すること（重要）**

Alembic の autogenerate は、SQLAlchemy の `use_alter=True` を使った**循環外鍵
`fk_auctions_winner_bid`** を `op.create_table()` の中で**静かに落とす**。
Task 1 のベースラインで実際に起き、下流の FK 定義が DB から消えた。
今回の差分でも、外キーを追加する差分を取ると、同じ循環外鍵が落ちる可能性がある。

必須手順:

1. 生成された差分ファイルを開き、`auctions` テーブルに対する
   `fk_auctions_winner_bid` の作成が**含まれているか**を確認する。
2. 含まれていなければ、Task 1 のベースラインで採ったのと同じ方式
   （`op.batch_alter_table("auctions")` + `create_foreign_key(...)`）で
   差分ファイルに追記する。
3. 適用後、`information_schema` で以下の存在を実測する。

```sql
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_schema = 'hew_xhigh' AND table_name = 'auctions';
```

4. 最後に**無差分を確認**する。これが Task 2 の完了条件そのもの。

```powershell
python -m flask db check
```
Expected: `No new upgrade operations detected.`（Task 1 と同じ）

この 4 手順を飛ばさないこと。差分が正しくても循環外鍵が欠けていれば、
Task 4 の落札確定（`winner_bid_id`）と Task 5 の取消（作品→競売→入札の連鎖）が
壊れる。

- [ ] **Step 11: `DB-deploy/deploy.sql` を更新する**

`DB-deploy/deploy.sql` は「定義の基準は本ファイルとする」と明記された DDL の正であり、
先頭に `USE hew;` が書いてある。**`USE hew_xhigh;` に変更する**（既存の `hew` 庫は
TraeWorkCN 版が使用中なので書き換えてはいけない）。続けて以下を反映する。

- `auctions`：`artwork_id` の `UNIQUE KEY uq_auctions_artwork` を撤去し、
  `active_slot INT NULL`、`previous_auction_id INT NULL`（自己 FK）を追加、
  `UNIQUE KEY uq_auctions_artwork_active_slot (artwork_id, active_slot)` を追加
- `artworks`：`hidden_reason` / `hidden_at` / `hidden_by_id` を追加
- `bids`：`held_points INT NOT NULL DEFAULT 0` を追加
- `wallet_transactions`：`reference_key VARCHAR(120) NULL UNIQUE`、`reason VARCHAR(300) NULL` を追加
- `notifications`：`revoked_at` / `revoked_by_id` / `revoke_reason` を追加
- `auction_cancellations` テーブルを新設

```sql
CREATE TABLE IF NOT EXISTS auction_cancellations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  auction_id INT NULL,
  artwork_id INT NOT NULL,
  action VARCHAR(30) NOT NULL,
  actor_id INT NOT NULL,
  reason VARCHAR(300) NULL,
  refunded_points INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_cancellations_auction (auction_id),
  KEY idx_cancellations_artwork (artwork_id),
  KEY idx_cancellations_action (action),
  CONSTRAINT fk_cancellations_auction FOREIGN KEY (auction_id) REFERENCES auctions(id),
  CONSTRAINT fk_cancellations_artwork FOREIGN KEY (artwork_id) REFERENCES artworks(id),
  CONSTRAINT fk_cancellations_actor FOREIGN KEY (actor_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

- [ ] **Step 12: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_models_xhigh.py -q
```
Expected: 9 passed

- [ ] **Step 13: 既存テストが通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS（`Artwork.auction` がリストになった影響でテストが落ちる場合は、テスト側ではなく本体側で `active_auction` を使う形に直す）

- [ ] **Step 14: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): データモデル刷新（active_slot / held_points / reference_key / 取消履歴）"
```

---

### Task 3: 台帳の冪等化（reference_key）

取消の再送や終了確定の再実行で、ポイントが二重增减しないことを保証する土台。

**Files:**
- Modify: `app/services/point_service.py`
- Test: `tests/test_point_service_idempotent.py`

**Interfaces:**
- Consumes: Task 2 の `WalletTransaction.reference_key`
- Produces: `adjust_balance(user, amount, transaction_type, related_auction_id=None, related_bid_id=None, reference_key=None, reason=None) -> WalletTransaction`。`reference_key` 指定時、同一キーの行が既にある場合は残高を変更せずその行を返す。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_point_service_idempotent.py` を作成:

```python
"""reference_key による台帳の冪等性の確認。"""

from app.extensions import db
from app.models.wallet import TYPE_BID, WalletTransaction
from app.services.point_service import adjust_balance


def test_same_reference_key_does_not_change_balance_twice(app, make_user):
    user = make_user("alice", points=1000)
    first = adjust_balance(user, -100, TYPE_BID, reference_key="bid:1:hold")
    db.session.commit()
    second = adjust_balance(user, -100, TYPE_BID, reference_key="bid:1:hold")
    db.session.commit()
    assert user.point_balance == 900
    assert first.id == second.id
    assert WalletTransaction.query.filter_by(reference_key="bid:1:hold").count() == 1


def test_different_reference_keys_are_recorded_separately(app, make_user):
    user = make_user("alice", points=1000)
    adjust_balance(user, -100, TYPE_BID, reference_key="bid:1:hold")
    adjust_balance(user, -50, TYPE_BID, reference_key="bid:2:hold")
    db.session.commit()
    assert user.point_balance == 850
    assert WalletTransaction.query.count() == 2


def test_reference_key_is_optional(app, make_user):
    user = make_user("alice", points=1000)
    adjust_balance(user, -10, TYPE_BID)
    adjust_balance(user, -10, TYPE_BID)
    db.session.commit()
    assert user.point_balance == 980
    assert WalletTransaction.query.count() == 2
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_point_service_idempotent.py -q
```
Expected: FAIL（`adjust_balance` が `reference_key` を受け付けない）

- [ ] **Step 3: `adjust_balance` を実装する**

`app/services/point_service.py` の `adjust_balance` を下列に置き換える:

```python
def adjust_balance(
    user,
    amount: int,
    transaction_type: str,
    related_auction_id: int | None = None,
    related_bid_id: int | None = None,
    reference_key: str | None = None,
    reason: str | None = None,
) -> WalletTransaction:
    """残高を変更し、履歴を記録する。

    残高が負になる場合は例外を発生させ、変更しない。
    ``reference_key`` を指定した場合、同じキーの履歴が既にあれば
    残高を変更せずその行を返す。再送・二重実行の防止に使う。
    """
    amount = int(amount)
    if reference_key:
        existing = WalletTransaction.query.filter_by(
            reference_key=reference_key
        ).first()
        if existing is not None:
            return existing

    current = get_point_balance(user)
    if current + amount < 0:
        raise InsufficientPointsError(
            f"残高が不足しています（現在 {current}pt）。"
        )
    user.point_balance = current + amount
    transaction = WalletTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=user.point_balance,
        related_auction_id=related_auction_id,
        related_bid_id=related_bid_id,
        reference_key=reference_key,
        reason=reason,
    )
    db.session.add(transaction)
    return transaction
```

- [ ] **Step 4: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_point_service_idempotent.py -q
```
Expected: 3 passed

- [ ] **Step 5: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): 台帳に reference_key を追加し冪等な残高変更を実現"
```

---

### Task 4: 入札の預託・返還の刷新（held_points）

high 版は前最高入札者へ「入札額全額」を返しているが、同一投标者が連名で増額した場合は実際に支払った額より多く返り、架空のポイント中生む。`held_points` で「その入札が今預かっている額」を追跡して解決する。

**Files:**
- Modify: `app/services/auction_service.py`
- Test: `tests/test_bid_held_points.py`

**Interfaces:**
- Consumes: Task 2 の `Bid.held_points`、Task 3 の `adjust_balance(reference_key=...)`
- Produces: `place_bid(...)` が `Bid.held_points` を正しく設定し、被超過時に `held_points` ぶんだけ返却する。`close_auction` は落札者の `held_points` をそのまま確定額として保持し、二重引落ししない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_bid_held_points.py` を作成:

```python
"""入札の預託額（held_points）に関する確認。"""

from app.extensions import db
from app.models.auction import Auction
from app.services import auction_service


def test_self_raise_then_outbid_keeps_balance_consistent(
    app, make_user, make_auction, login
):
    """同一投标者の増額後に超過されても、支払った額だけ返る。"""
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    bob = make_user("bob", points=1000)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()
    auction_service.place_bid(auction.id, alice, 150)
    db.session.commit()
    assert alice.point_balance == 850

    auction_service.place_bid(auction.id, bob, 200)
    db.session.commit()

    # alice は 100 + 50 = 150pt 支払っているので 150pt 戻る
    assert alice.point_balance == 1000
    assert bob.point_balance == 800


def test_top_bid_holds_the_paid_amount(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    bid = auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()
    assert bid.held_points == 100


def test_superseded_bid_holds_nothing(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    first = auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()
    second = auction_service.place_bid(auction.id, alice, 150)
    db.session.commit()
    assert first.held_points == 0
    assert second.held_points == 150


def test_close_auction_does_not_deduct_winner_twice(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    auction_service.place_bid(auction.id, alice, 300)
    db.session.commit()
    alice_balance = alice.point_balance

    auction_service.close_auction(auction.id)
    db.session.commit()

    assert alice.point_balance == alice_balance
    assert seller.point_balance == 300


def test_close_auction_twice_adds_seller_points_once(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    auction_service.place_bid(auction.id, alice, 300)
    db.session.commit()

    auction_service.close_auction(auction.id)
    db.session.commit()
    auction_service.close_auction(auction.id)
    db.session.commit()

    assert seller.point_balance == 300
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_bid_held_points.py -q
```
Expected: FAIL（`held_points` 属性が無い / 残高が 900 にならない）

- [ ] **Step 3: `place_bid` を書き換える**

`app/services/auction_service.py` の `place_bid` を下列に置き換える:

```python
def place_bid(
    auction_id: int,
    bidder,
    amount: int,
    is_auto: bool = False,
    expected_price: int | None = None,
) -> Bid:
    """入札を確定する。

    残高の減算・前最高入札者への返還・入札履歴・取引履歴・現在価格の
    更新を同一トランザクションで行う。返却額は入札額ではなく
    その入札が実際に預かっている額（``held_points``）に限る。
    """
    try:
        bid_amount = int(amount)
    except (TypeError, ValueError) as exc:
        raise ValidationError("入札額を入力してください。") from exc
    if bid_amount < 0:
        raise ValidationError("入札額に負の値は指定できません。")

    auction = _lock_auction(auction_id)
    now = utcnow()

    if expected_price is not None and int(expected_price) != auction.current_price:
        raise BusinessRuleError(
            "現在価格が変わりました。金額を確認して再度お試しください。"
        )

    _validate_bid(auction, bidder, bid_amount, now)

    top_bid = _top_accepted_bid(auction)
    previous_bidder_id = top_bid.bidder_id if top_bid is not None else None
    previous_held = int(top_bid.held_points or 0) if top_bid is not None else 0

    # 最高入札者自身の増額は差額だけ、それ以外は入札全額を消費する。
    if previous_bidder_id == bidder.id:
        spend = bid_amount - auction.current_price
        new_held = previous_held + spend
    else:
        spend = bid_amount
        new_held = spend

    lock_targets = [bidder.id]
    if previous_bidder_id and previous_bidder_id != bidder.id:
        lock_targets.append(previous_bidder_id)
    locked_users = _lock_users(lock_targets)

    bidder_row = locked_users.get(bidder.id, bidder)
    if bidder_row.point_balance < spend:
        raise InsufficientPointsError(
            f"入札には {spend}pt 必要です（残高 {bidder_row.point_balance}pt）。"
        )

    bid = Bid(
        auction=auction,
        bidder_id=bidder.id,
        bid_amount=bid_amount,
        is_auto_bid=is_auto,
        bid_status=ACCEPTED,
        held_points=new_held,
    )
    db.session.add(bid)
    db.session.flush()

    adjust_balance(
        bidder_row,
        -spend,
        TYPE_BID,
        related_auction_id=auction.id,
        related_bid_id=bid.id,
        reference_key=f"bid:{bid.id}:hold",
    )

    if previous_bidder_id and previous_bidder_id != bidder.id:
        previous_user = locked_users.get(previous_bidder_id)
        if previous_user is not None and previous_held > 0:
            adjust_balance(
                previous_user,
                previous_held,
                TYPE_REFUND,
                related_auction_id=auction.id,
                related_bid_id=top_bid.id,
                reference_key=f"bid:{top_bid.id}:release",
            )
        top_bid.held_points = 0
    elif top_bid is not None and previous_bidder_id == bidder.id:
        # 自分の増額。預託は新しい入札行へ移し、旧行は 0 にする。
        top_bid.held_points = 0

    auction.current_price = bid_amount
    db.session.flush()

    _notify_bid(auction, bid, previous_bidder_id, previous_held)
    return bid
```

- [ ] **Step 4: `_notify_bid` の文面を預託額に合わせる**

`app/services/auction_service.py` の `_notify_bid` 内で `previous_amount` を使っている箇所を `previous_held` に置き換え、メッセージを次のようにする:

```python
            message=(
                f"「{artwork_title}」の現在価格は {bid.bid_amount}pt になりました。"
                f"減少した {previous_held}pt は残高に戻ります。"
            ),
```

関数定義の引数名も `previous_amount` から `previous_held` へ変更する。

- [ ] **Step 5: `close_auction` の確定処理を預託額に合わせる**

`close_auction` 内で、落札者の入札の `held_points` は確定額として保持したままにする（返金しない）。次の行を追加する:

```python
    # 落札者の預託は確定額として保持する（二重引落し防止）。
    top_bid.held_points = int(top_bid.held_points or 0)
```

終了時に `active_slot` を解放する処理も追加する:

```python
    auction.status = ENDED
    auction.closed_reason = REASON_TIME_EXPIRED
    auction.active_slot = None
```

- [ ] **Step 6: `create_auction` の `active_slot` 配線を確認する**

`create_auction` 内の `Auction(...)` 構築に `active_slot=ACTIVE_SLOT` が付き、
「すでにオークションがある」判定が `artwork.active_auction is not None` に
直っていることを確認する（この 2 点は **Task 2 で導入済み**。Task 2 が
漏らしていた場合はここで補う）。

```python
    if artwork.active_auction is not None:
        raise BusinessRuleError("この作品には開催中のオークションがあります。")
```

`artwork.status != "draft"` の判定（初回出品のみ）はそのまま残す。再出品は
Task 5 の `create_relisted_auction` が別経路で扱う。

- [ ] **Step 7: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_bid_held_points.py -q
```
Expected: 5 passed

- [ ] **Step 8: 全テストを通す**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 9: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "fix(xhigh): 入札の預託額 held_points を導入し返還過剰を解消"
```

---

### Task 5: 取消・再出品・非公開化のサービス

**Files:**
- Create: `app/services/cancellation_service.py`
- Test: `tests/test_cancellation_and_relist.py`

**Interfaces:**
- Consumes: Task 2 の `Auction.active_slot` / `AuctionCancellation` / `Artwork.HIDDEN`、Task 3 の `adjust_balance(reference_key=...)`、Task 4 の `held_points`
- Produces:
  - `cancel_auction_by_seller(user, auction) -> Auction`
  - `cancel_auction_by_admin(user, auction, reason: str) -> Auction`
  - `create_relisted_auction(user, artwork, start_price: int, duration_minutes: int) -> Auction`
  - `hide_artwork(user, artwork, reason: str) -> Artwork`
  - `restore_artwork(user, artwork, reason: str) -> Artwork`
  - `list_cancellations(artwork_id: int) -> list[AuctionCancellation]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_cancellation_and_relist.py` を作成:

```python
"""出品取消・再出品・非公開化の確認。"""

from app.extensions import db
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.cancellation import AuctionCancellation
from app.models.user import User
from app.services import auction_service, cancellation_service


def _admin(app, make_user):
    admin = make_user("admin", points=0)
    admin.role = "admin"
    db.session.commit()
    return admin


def test_seller_can_cancel_before_any_bid(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    result = cancellation_service.cancel_auction_by_seller(seller, auction)
    db.session.commit()
    assert result.status == "cancelled"
    assert result.active_slot is None
    assert result.closed_reason == "seller_cancelled"


def test_seller_cannot_cancel_after_a_bid(app, make_user, make_auction):
    from app.services.errors import BusinessRuleError

    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()

    try:
        cancellation_service.cancel_auction_by_seller(seller, auction)
    except BusinessRuleError:
        db.session.rollback()
    else:
        raise AssertionError("入札後の本人取消が通ってしまった")


def test_admin_cancel_refunds_only_unreturned_points(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    admin = _admin(app, make_user)
    auction = make_auction(seller, start_price=100)

    auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()
    assert alice.point_balance == 900

    cancellation_service.cancel_auction_by_admin(admin, auction, "運営判断")
    db.session.commit()

    assert alice.point_balance == 1000
    assert auction.status == "cancelled"
    assert auction.closed_reason == "admin_cancelled"


def test_admin_cancel_twice_does_not_refund_twice(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    admin = _admin(app, make_user)
    auction = make_auction(seller, start_price=100)
    auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()

    cancellation_service.cancel_auction_by_admin(admin, auction, "運営判断")
    db.session.commit()
    cancellation_service.cancel_auction_by_admin(admin, auction, "運営判断")
    db.session.commit()

    assert alice.point_balance == 1000


def test_admin_cancel_requires_reason(app, make_user, make_auction):
    from app.services.errors import ValidationError

    seller = make_user("seller", points=0)
    admin = _admin(app, make_user)
    auction = make_auction(seller, start_price=100)
    try:
        cancellation_service.cancel_auction_by_admin(admin, auction, "")
    except ValidationError:
        db.session.rollback()
    else:
        raise AssertionError("理由なしの取消が通ってしまった")


def test_admin_cancel_stops_auto_bid(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    admin = _admin(app, make_user)
    auction = make_auction(seller, start_price=100)
    auction_service.configure_auto_bid(alice, auction, 500)
    db.session.commit()

    cancellation_service.cancel_auction_by_admin(admin, auction, "運営判断")
    db.session.commit()

    from app.models.auto_bid import AutoBidSetting

    setting = AutoBidSetting.query.filter_by(
        auction_id=auction.id, user_id=alice.id
    ).first()
    assert setting.is_active is False


def test_cancellation_is_recorded(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    admin = _admin(app, make_user)
    auction = make_auction(seller, start_price=100)
    cancellation_service.cancel_auction_by_admin(admin, auction, "運営判断")
    db.session.commit()
    record = AuctionCancellation.query.filter_by(
        auction_id=auction.id, action="admin_cancel"
    ).first()
    assert record is not None
    assert record.reason == "運営判断"
    assert record.actor_id == admin.id


def test_relist_creates_new_auction_and_keeps_history(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    cancellation_service.cancel_auction_by_seller(seller, auction)
    db.session.commit()

    new_auction = cancellation_service.create_relisted_auction(
        seller, auction.artwork, 200, 10
    )
    db.session.commit()

    assert new_auction.id != auction.id
    assert new_auction.previous_auction_id == auction.id
    assert new_auction.active_slot == 1
    assert Auction.query.filter_by(artwork_id=auction.artwork_id).count() == 2


def test_relist_rejects_two_active_auctions(app, make_user, make_auction):
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    cancellation_service.cancel_auction_by_seller(seller, auction)
    db.session.commit()
    cancellation_service.create_relisted_auction(seller, auction.artwork, 200, 10)
    db.session.commit()

    from app.services.errors import BusinessRuleError

    try:
        cancellation_service.create_relisted_auction(
            seller, auction.artwork, 300, 10
        )
    except BusinessRuleError:
        db.session.rollback()
    else:
        raise AssertionError("同時開催の競売が 2 件作れてしまった")


def test_relist_rejects_sold_artwork(app, make_user, make_auction):
    from app.services.errors import BusinessRuleError

    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    auction_service.place_bid(auction.id, alice, 100)
    db.session.commit()
    auction_service.close_auction(auction.id)
    db.session.commit()

    try:
        cancellation_service.create_relisted_auction(
            seller, auction.artwork, 200, 10
        )
    except BusinessRuleError:
        db.session.rollback()
    else:
        raise AssertionError("落札済みなのに再出品できた")


def test_hide_and_restore_artwork(app, make_user, make_artwork):
    admin = _admin(app, make_user)
    seller = make_user("seller", points=0)
    artwork = make_artwork(seller)

    cancellation_service.hide_artwork(admin, artwork, ".Tree")
    db.session.commit()
    assert artwork.status == "hidden"
    assert artwork.hidden_reason == "Tree"

    cancellation_service.restore_artwork(admin, artwork, "Tree")
    db.session.commit()
    assert artwork.status != "hidden"


def test_non_admin_cannot_hide(app, make_user, make_artwork):
    from app.services.errors import PermissionDeniedError

    seller = make_user("seller", points=0)
    artwork = make_artwork(seller)
    try:
        cancellation_service.hide_artwork(seller, artwork, "テスト")
    except PermissionDeniedError:
        db.session.rollback()
    else:
        raise AssertionError("一般ユーザーが非公開化できた")
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_cancellation_and_relist.py -q
```
Expected: FAIL（`app.services.cancellation_service` が無い）

- [ ] **Step 3: `app/services/cancellation_service.py` を作成する**

```python
"""出品取消・再出品・非公開化。

正本：要件定義書 6.1、仕様決定事項 6章。
- 取消は履歴を残し、競売・入札・作品の実体は削除しない
- 返戻は「その入札がまだ預かっている額」だけ
- 再出品は新しい競売を作り、過去履歴は保持する
"""

from __future__ import annotations

from datetime import timedelta

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.artwork import CANCELLED as ARTWORK_CANCELLED
from app.models.artwork import HIDDEN, LISTED, SOLD
from app.models.auction import (
    ACTIVE,
    ACTIVE_SLOT,
    CANCELLED,
    ENDED,
    REASON_ADMIN_CANCELLED,
    REASON_HIDDEN,
    REASON_SELLER_CANCELLED,
)
from app.models.auto_bid import AutoBidSetting
from app.models.bid import ACCEPTED, Bid
from app.models.cancellation import (
    ACTION_ADMIN_CANCEL,
    ACTION_HIDE,
    ACTION_RESTORE,
    ACTION_SELLER_CANCEL,
    AuctionCancellation,
)
from app.models.notification import TYPE_AUCTION_CANCELLED
from app.models.user import User
from app.models.wallet import TYPE_CANCEL_REFUND
from app.services.errors import (
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.notification_service import create_notification
from app.services.point_service import adjust_balance
from app.utils import utcnow


def _lock_auction(auction_id: int):
    """競売行をロックして取得する。"""
    from app.models.auction import Auction

    statement = (
        select(Auction)
        .where(Auction.id == auction_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    auction = db.session.execute(statement).scalar_one_or_none()
    if auction is None:
        raise NotFoundError("オークションが見つかりません。")
    return auction


def _release_held_points(auction) -> int:
    """預託中のポイントを全額返却し、返却合計を返す。

    入札行の ``held_points`` を 0 にすることで、再実行しても
    二重返還されない。返却は台帳の一意キーでも保護する。
    """
    released = 0
    bids = (
        Bid.query.filter_by(auction_id=auction.id, bid_status=ACCEPTED)
        .order_by(Bid.id.asc())
        .all()
    )
    for bid in bids:
        held = int(bid.held_points or 0)
        if held <= 0:
            continue
        bidder = db.session.get(User, bid.bidder_id)
        if bidder is not None:
            adjust_balance(
                bidder,
                held,
                TYPE_CANCEL_REFUND,
                related_auction_id=auction.id,
                related_bid_id=bid.id,
                reference_key=f"bid:{bid.id}:cancel-release",
            )
        bid.held_points = 0
        released += held
    db.session.flush()
    return released


def _stop_auto_bids(auction) -> None:
    """対象競売の自動入札をすべて停止する。"""
    settings = AutoBidSetting.query.filter_by(auction_id=auction.id).all()
    for setting in settings:
        setting.is_active = False
    db.session.flush()


def _record(
    artwork_id: int,
    action: str,
    actor,
    reason: str | None,
    auction_id: int | None = None,
    refunded: int = 0,
) -> AuctionCancellation:
    """操作履歴を記録する。"""
    record = AuctionCancellation(
        auction_id=auction_id,
        artwork_id=artwork_id,
        action=action,
        actor_id=actor.id,
        reason=(reason or "").strip() or None,
        refunded_points=refunded,
    )
    db.session.add(record)
    db.session.flush()
    return record


def cancel_auction_by_seller(user, auction) -> "Auction":
    """出品者本人による取消。

    開催中・終了前・受理済み入札なしのときだけ取消できる。
    """
    if auction.artwork.artist_id != user.id:
        raise PermissionDeniedError("自分の出品だけを取り消せます。")
    if auction.status != ACTIVE:
        raise BusinessRuleError("このオークションは終了しています。")
    if utcnow() >= auction.end_time:
        raise BusinessRuleError("終了日時を過ぎているため取り消せません。")
    has_bid = (
        Bid.query.filter_by(auction_id=auction.id, bid_status=ACCEPTED).first()
        is not None
    )
    if has_bid:
        raise BusinessRuleError("入札を受け付けているため取り消せません。")

    auction.status = CANCELLED
    auction.closed_reason = REASON_SELLER_CANCELLED
    auction.active_slot = None
    auction.artwork.status = ARTWORK_CANCELLED
    _stop_auto_bids(auction)
    _record(
        auction.artwork_id,
        ACTION_SELLER_CANCEL,
        user,
        None,
        auction_id=auction.id,
    )
    create_notification(
        user_id=auction.artwork.artist_id,
        notification_type=TYPE_AUCTION_CANCELLED,
        title="出品を取り消しました",
        message=(
            f"「{auction.artwork.title or '作品'}」の出品を取り消しました。"
        ),
        related_auction_id=auction.id,
    )
    db.session.flush()
    return auction


def cancel_auction_by_admin(user, auction, reason: str) -> "Auction":
    """管理者による取消。入札があっても終了前なら取り消せる。

    理由は必須。取消した入札の未返還分を全額返し、自動入札を停止する。
    """
    if not getattr(user, "is_admin", False):
        raise PermissionDeniedError("管理者だけが行えます。")
    text = (reason or "").strip()
    if not text:
        raise ValidationError("取消の理由を入力してください。")
    if auction.status == CANCELLED:
        return auction
    if auction.status != ACTIVE:
        raise BusinessRuleError("このオークションは終了しています。")
    if utcnow() >= auction.end_time:
        raise BusinessRuleError("終了日時を過ぎているため取り消せません。")

    auction.status = CANCELLED
    auction.closed_reason = REASON_ADMIN_CANCELLED
    auction.active_slot = None
    refunded = _release_held_points(auction)
    _stop_auto_bids(auction)
    auction.artwork.status = ARTWORK_CANCELLED
    _record(
        auction.artwork_id,
        ACTION_ADMIN_CANCEL,
        user,
        text,
        auction_id=auction.id,
        refunded=refunded,
    )

    seller_id = auction.artwork.artist_id
    create_notification(
        user_id=seller_id,
        notification_type=TYPE_AUCTION_CANCELLED,
        title="出品が取り消されました",
        message=(
            f"「{auction.artwork.title or '作品'}」は運営により"
            f"出品が取り消されました（理由: {text}）。"
        ),
        related_auction_id=auction.id,
    )
    for bid in (
        Bid.query.filter_by(auction_id=auction.id, bid_status=ACCEPTED).all()
    ):
        if bid.bidder_id == seller_id:
            continue
        create_notification(
            user_id=bid.bidder_id,
            notification_type=TYPE_AUCTION_CANCELLED,
            title="出品が取り消されました",
            message=(
                f"「{auction.artwork.title or '作品'}」の出品が取り消されました。"
                "預託していたポイントは残高に戻ります。"
            ),
            related_auction_id=auction.id,
        )
    db.session.flush()
    return auction


def create_relisted_auction(
    user,
    artwork,
    start_price: int,
    duration_minutes: int,
) -> "Auction":
    """取消済み・未落札終了の作品から新しい競売を作る。"""
    from app.models.auction import Auction

    if artwork.artist_id != user.id:
        raise PermissionDeniedError("自分の作品だけを出品できます。")
    if artwork.status == HIDDEN:
        raise BusinessRuleError("非公開の作品は再出品できません。")
    if not artwork.is_saved:
        raise BusinessRuleError("画像が保存されていない作品は再出品できません。")

    # 作品行を先にロックする（auctions → artworks → users の順）。
    # ロックを取得してから競売の状態を判定することで、
    # 同時に実行された再出品が 2 件通らないようにする。
    from app.models.artwork import Artwork

    artwork_row = db.session.execute(
        select(Artwork)
        .where(Artwork.id == artwork.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if artwork_row is None:
        raise NotFoundError("作品が見つかりません。")

    previous = (
        Auction.query.filter_by(artwork_id=artwork.id)
        .order_by(Auction.id.desc())
        .first()
    )
    if previous is None:
        raise BusinessRuleError("再出品できる過去の競売がありません。")
    if previous.status == ACTIVE:
        raise BusinessRuleError("この作品には開催中のオークションがあります。")
    if previous.winner_id is not None:
        raise BusinessRuleError("落札済みの作品は再出品できません。")
    if previous.status not in (CANCELLED, ENDED):
        raise BusinessRuleError("再出品できる状態ではありません。")

    try:
        price = int(start_price)
    except (TypeError, ValueError) as exc:
        raise ValidationError("開始価格を入力してください。") from exc
    if price < 0:
        raise ValidationError("開始価格は 0 以上の整数で入力してください。")

    allowed = tuple(current_app.config["AUCTION_DURATION_MINUTES"])
    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError) as exc:
        raise ValidationError("開催時間を選択してください。") from exc
    if minutes not in allowed:
        raise ValidationError("開催時間は 5分・10分・15分・20分から選択してください。")

    now = utcnow()
    end_time = now + timedelta(minutes=minutes)
    event_end = current_app.config.get("EVENT_END_AT")
    if event_end is not None and end_time > event_end:
        raise BusinessRuleError(
            "イベント終了までに開催時間を確保できないため再出品できません。"
        )

    auction = Auction(
        artwork_id=artwork.id,
        start_price=price,
        current_price=price,
        status=ACTIVE,
        active_slot=ACTIVE_SLOT,
        previous_auction_id=previous.id,
        start_time=now,
        end_time=end_time,
    )
    db.session.add(auction)
    artwork.status = LISTED
    db.session.flush()
    return auction


def hide_artwork(user, artwork, reason: str) -> "Artwork":
    """管理者が作品を非公開にする。"""
    if not getattr(user, "is_admin", False):
        raise PermissionDeniedError("管理者だけが行えます。")
    text = (reason or "").strip()
    if not text:
        raise ValidationError("非公開化の理由を入力してください。")
    if artwork.status == HIDDEN:
        return artwork

    from app.models.auction import Auction

    auction = (
        Auction.query.filter_by(artwork_id=artwork.id, status=ACTIVE).first()
    )
    if auction is not None:
        cancel_auction_by_admin(user, auction, text)

    artwork.status = HIDDEN
    artwork.hidden_reason = text
    artwork.hidden_at = utcnow()
    artwork.hidden_by_id = user.id
    _record(
        artwork.id,
        ACTION_HIDE,
        user,
        text,
        auction_id=auction.id if auction is not None else None,
    )
    db.session.flush()
    return artwork


def restore_artwork(user, artwork, reason: str) -> "Artwork":
    """管理者が作品を公開へ戻す。取消済みの競売は再開しない。"""
    if not getattr(user, "is_admin", False):
        raise PermissionDeniedError("管理者だけが行えます。")
    text = (reason or "").strip()
    if not text:
        raise ValidationError("公開復帰の理由を入力してください。")
    if artwork.status != HIDDEN:
        return artwork

    from app.models.auction import Auction

    # 落札済みなら取引結果は変えない。落札実績があれば SOLD に戻す。
    has_winner = (
        Auction.query.filter_by(artwork_id=artwork.id)
        .filter(Auction.winner_id.isnot(None))
        .first()
        is not None
    )
    artwork.status = SOLD if has_winner else LISTED
    artwork.hidden_reason = None
    artwork.hidden_at = None
    artwork.hidden_by_id = None
    _record(artwork.id, ACTION_RESTORE, user, text)
    db.session.flush()
    return artwork


def list_cancellations(artwork_id: int) -> list[AuctionCancellation]:
    """作品の取消・非公開の履歴を新しい順に返す。"""
    return (
        AuctionCancellation.query.filter_by(artwork_id=artwork_id)
        .order_by(AuctionCancellation.created_at.desc())
        .all()
    )
```

**注意:** `AuctionCancellation.auction_id` は Task 2 で `nullable=True` に定義済み。
公開復帰（`restore_artwork`）では競売を持たない記録になるため `auction_id=None` を
渡す。通知タイトル・返还理由の文言は上記のコードで確定済み。

- [ ] **Step 4: 通知種別と台帳種別を追加する**

`app/models/notification.py` に次の定数を追加する:

```python
TYPE_AUCTION_CANCELLED = "auction_cancelled"
```

`app/models/wallet.py` には取消返還用の台帳種別を追加する（既存の
`bid` / `refund` / `sale` / `bonus` とは区別して、取消による返戻が
通常の超過返还と混ざらないようにする）:

```python
TYPE_CANCEL_REFUND = "cancel_refund"
TYPE_ADMIN_ADJUST = "admin_adjust"
```

- [ ] **Step 5: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_cancellation_and_relist.py -q
```
Expected: 13 passed

- [ ] **Step 6: 全テストを通す**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 7: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): 出品取消・再出品・非公開化のサービスを実装"
```

---

### Task 6: イベント終了の受付制御

**Files:**
- Create: `app/services/event_service.py`
- Modify: `app/services/auth_service.py`
- Modify: `app/services/auction_service.py`
- Modify: `app/services/cancellation_service.py`
- Test: `tests/test_event_end.py`

**Interfaces:**
- Consumes: `app.config.Config.EVENT_END_AT`
- Produces: `is_event_ended(now=None) -> bool`、`ensure_event_open(operation: str) -> None`。新規登録・描画開始・出品・再出品で `ensure_event_open` を呼ぶ。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_event_end.py` を作成:

```python
"""イベント終了時刻で受付を止めることの確認。"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models.user import User
from app.services import auction_service, event_service
from app.utils import utcnow


@pytest.fixture()
def closed_event(app):
    app.config["EVENT_END_AT"] = utcnow() - timedelta(minutes=1)
    yield app
    app.config["EVENT_END_AT"] = None


def test_is_event_ended(closed_event):
    assert event_service.is_event_ended() is True


def test_is_event_ended_without_limit(app):
    app.config["EVENT_END_AT"] = None
    assert event_service.is_event_ended() is False


def test_ensure_event_open_raises(closed_event):
    from app.services.errors import BusinessRuleError

    try:
        event_service.ensure_event_open("登録")
    except BusinessRuleError:
        db.session.rollback()
    else:
        raise AssertionError("イベント終了後の登録が通ってしまった")


def test_registration_is_blocked_after_event_end(closed_event, client):
    response = client.post(
        "/auth/register",
        data={"username": "latecomer", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert User.query.filter_by(username="latecomer").first() is None


def test_listing_is_blocked_after_event_end(closed_event, make_user, make_artwork):
    from app.services.errors import BusinessRuleError

    seller = make_user("seller", points=0)
    artwork = make_artwork(seller)
    try:
        auction_service.create_auction(seller, artwork, "作品", "説明", [], 100, 10)
    except BusinessRuleError:
        db.session.rollback()
    else:
        raise AssertionError("イベント終了後の出品が通ってしまった")
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_event_end.py -q
```
Expected: FAIL（`app.services.event_service` が無い）

- [ ] **Step 3: `app/services/event_service.py` を作成する**

```python
"""イベント終了時刻の受付制御。

イベント終了後は新規登録・描画開始・出品・再出品を止める。
閲覧・ログイン・ダウンロードは終了後も許される。
"""

from __future__ import annotations

from flask import current_app

from app.services.errors import BusinessRuleError
from app.utils import utcnow


def get_event_end_at():
    """イベント終了時刻を返す。未設定なら None。"""
    return current_app.config.get("EVENT_END_AT")


def is_event_ended(now=None) -> bool:
    """イベント終了時刻を過ぎているかを返す。"""
    end_at = get_event_end_at()
    if end_at is None:
        return False
    return (now or utcnow()) >= end_at


def ensure_event_open(operation: str) -> None:
    """イベント終了後の新規操作を拒否する。"""
    if is_event_ended():
        raise BusinessRuleError(
            f"イベントが終了しているため{operation}できません。"
        )
```

- [ ] **Step 4: 呼び出し側に組み込む**

- `app/services/auth_service.py` の登録処理の先頭で `ensure_event_open("新規登録")` を呼ぶ。
- `app/artworks/routes.py` の `start_drawing` で `ensure_event_open("描画の開始")` を呼ぶ。
- `app/services/auction_service.py` の `create_auction` で `ensure_event_open("出品")` を呼ぶ。
- `app/services/cancellation_service.py` の `create_relisted_auction` で `ensure_event_open("再出品")` を呼ぶ。

いずれも失敗時は `BusinessRuleError` が例外として上がるので、既存の `app/__init__.py` のエラーハンドラが flash へ変換する。

- [ ] **Step 5: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_event_end.py -q
```
Expected: 5 passed

- [ ] **Step 6: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): イベント終了時刻で新規受付を停止"
```

---

### Task 7: 管理画面

**Files:**
- Create: `app/admin/__init__.py`
- Create: `app/admin/routes.py`
- Modify: `app/templates/base.html`（管理者向けのナビ導線）
- Create: `app/templates/admin/index.html`
- Create: `app/templates/admin/artworks.html`
- Create: `app/templates/admin/auctions.html`
- Create: `app/templates/admin/users.html`
- Create: `app/templates/admin/tags.html`
- Create: `app/templates/admin/notifications.html`
- Create: `app/templates/admin/points.html`
- Modify: `app/__init__.py`（Blueprint 登録）
- Modify: `app/commands.py`（`promote-admin` 追加）
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: Task 5 の `cancellation_service`、Task 3 の `adjust_balance(reference_key=...)`
- Produces:
  - Blueprint `admin_bp`（`url_prefix="/admin"`）
  - `GET /admin/` … `GET /admin/points`
  - `POST /admin/artworks/<int:artwork_id>/hide` / `/restore`
  - `POST /admin/auctions/<int:auction_id>/cancel`
  - `POST /admin/users/<int:user_id>/display-name` / `/toggle-active`
  - `POST /admin/tags` / `POST /admin/tags/<int:tag_id>/delete`
  - `POST /admin/notifications/<int:notification_id>/revoke`
  - `POST /admin/points/adjust`
  - CLI `flask promote-admin <username>`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_admin.py` を作成:

```python
"""管理画面と管理者権限の確認。"""

from app.extensions import db
from app.models.user import User


def _make_admin(app, make_user, name="admin"):
    admin = make_user(name, points=0)
    admin.role = "admin"
    db.session.commit()
    return admin


def test_admin_page_requires_login(client):
    response = client.get("/admin/")
    assert response.status_code in (302, 401, 403)


def test_admin_page_forbidden_for_normal_user(client, make_user, login):
    make_user("alice")
    login("alice")
    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_page_opens_for_admin(client, make_user, login):
    _make_admin(None, make_user)
    login("admin")
    response = client.get("/admin/")
    assert response.status_code == 200


def test_promote_admin_command(app, runner, make_user):
    make_user("bob")
    result = runner.invoke(args=["promote-admin", "bob"])
    assert result.exit_code == 0
    assert User.query.filter_by(username="bob").first().role == "admin"


def test_admin_can_hide_artwork(client, make_user, make_artwork, login):
    _make_admin(None, make_user)
    seller = make_user("seller", points=0)
    artwork = make_artwork(seller)
    login("admin")
    response = client.post(
        f"/admin/artworks/{artwork.id}/hide",
        data={"reason": "運用方針による非公開"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert artwork.status == "hidden"


def test_admin_can_cancel_auction(client, make_user, make_auction, login):
    _make_admin(None, make_user)
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    login("admin")
    response = client.post(
        f"/admin/auctions/{auction.id}/cancel",
        data={"reason": "違反行為"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert auction.status == "cancelled"


def test_admin_point_adjust_is_idempotent(app, make_user):
    from app.services.point_service import adjust_balance

    admin = _make_admin(app, make_user)
    user = make_user("alice", points=1000)
    adjust_balance(
        admin,
        500,
        "admin_adjust",
        reference_key="admin_adjust:1:ticket-1",
        reason="テスト",
    )
    db.session.commit()
    adjust_balance(
        admin,
        500,
        "admin_adjust",
        reference_key="admin_adjust:1:ticket-1",
        reason="テスト",
    )
    db.session.commit()
    assert user.point_balance == 1000
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_admin.py -q
```
Expected: FAIL（`/admin/` が 404）

- [ ] **Step 3: `app/admin/__init__.py` を作成する**

既存 9 つの Blueprint はすべて `url_prefix` を設定せず、URL ルール側へ
フルパスを書いている（`app/auth/__init__.py:5` など）。この流儀に揃える。

```python
"""管理画面の Blueprint。"""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__)

from app.admin import routes  # noqa: E402,F401
```

そのため各ルートのルールは `@admin_bp.route("/admin/artworks")` のように
`/admin` を含むフルパスで書く（Step 4 のコードはそのままこの方式）。

- [ ] **Step 4: `app/admin/routes.py` を作成する**

```python
"""管理画面。管理者のみ閲覧できる。"""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models.artwork import Artwork
from app.models.auction import Auction
from app.models.notification import Notification
from app.models.tag import Tag
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import auction_service, cancellation_service
from app.services.errors import ServiceError
from app.services.point_service import adjust_balance
from app.utils import utcnow


def _require_admin() -> None:
    """管理者でなければ 403 を返す。"""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@admin_bp.before_request
@login_required
def _guard():
    _require_admin()


def _redirect_back(default: str = "admin.index"):
    return redirect(request.referrer or url_for(default))


@admin_bp.route("/admin/")
def index():
    """管理画面のトップ。"""
    counts = {
        "artworks": Artwork.query.count(),
        "auctions": Auction.query.count(),
        "users": User.query.count(),
        "notifications": Notification.query.count(),
    }
    return render_template("admin/index.html", counts=counts)


@admin_bp.route("/admin/artworks")
def list_artworks():
    """作品一覧。"""
    artworks = (
        Artwork.query.order_by(Artwork.created_at.desc()).limit(200).all()
    )
    return render_template("admin/artworks.html", artworks=artworks)


@admin_bp.route("/admin/auctions")
def list_auctions():
    """競売一覧。"""
    auctions = (
        Auction.query.order_by(Auction.created_at.desc()).limit(200).all()
    )
    return render_template("admin/auctions.html", auctions=auctions)


@admin_bp.route("/admin/users")
def list_users():
    """アカウント一覧。"""
    users = User.query.order_by(User.id.asc()).limit(200).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/admin/tags")
def list_tags():
    """タグ一覧。"""
    tags = Tag.query.order_by(Tag.id.asc()).all()
    return render_template("admin/tags.html", tags=tags)


@admin_bp.route("/admin/notifications")
def list_notifications():
    """通知一覧。"""
    notifications = (
        Notification.query.order_by(Notification.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("admin/notifications.html", notifications=notifications)


@admin_bp.route("/admin/points")
def list_points():
    """残高と取引履歴。"""
    users = User.query.order_by(User.id.asc()).limit(200).all()
    transactions = (
        WalletTransaction.query.order_by(WalletTransaction.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("admin/points.html", users=users, transactions=transactions)


@admin_bp.route("/admin/artworks/<int:artwork_id>/hide", methods=["POST"])
def hide_artwork(artwork_id: int):
    """作品を非公開にする（理由必須）。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    try:
        cancellation_service.hide_artwork(
            current_user, artwork, request.form.get("reason", "")
        )
        db.session.commit()
        flash("作品を非公開にしました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return _redirect_back("admin.list_artworks")


@admin_bp.route("/admin/artworks/<int:artwork_id>/restore", methods=["POST"])
def restore_artwork(artwork_id: int):
    """作品を公開へ戻す（理由必須）。"""
    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    try:
        cancellation_service.restore_artwork(
            current_user, artwork, request.form.get("reason", "")
        )
        db.session.commit()
        flash("作品を公開に戻しました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return _redirect_back("admin.list_artworks")


@admin_bp.route("/admin/auctions/<int:auction_id>/cancel", methods=["POST"])
def cancel_auction(auction_id: int):
    """競売を取り消す（理由必須）。"""
    auction = db.session.get(Auction, auction_id)
    if auction is None:
        abort(404)
    try:
        cancellation_service.cancel_auction_by_admin(
            current_user, auction, request.form.get("reason", "")
        )
        db.session.commit()
        flash("オークションを取り消しました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return _redirect_back("admin.list_auctions")


@admin_bp.route("/admin/users/<int:user_id>/display-name", methods=["POST"])
def update_display_name(user_id: int):
    """表示名を編集する。"""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    name = (request.form.get("disp_name") or "").strip()[:50]
    if not name:
        flash("表示名を入力してください。", "error")
        return _redirect_back("admin.list_users")
    user.disp_name = name
    db.session.commit()
    flash("表示名を更新しました。", "success")
    return _redirect_back("admin.list_users")


@admin_bp.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
def toggle_user_active(user_id: int):
    """アカウントの有効・無効を切り替える。"""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    user.is_active = not user.is_active
    db.session.commit()
    flash("アカウント状態を切り替えました。", "success")
    return _redirect_back("admin.list_users")


@admin_bp.route("/admin/tags", methods=["POST"])
def create_tag():
    """タグを追加する。"""
    name = (request.form.get("name") or "").strip()[:50]
    if not name:
        flash("タグ名を入力してください。", "error")
        return _redirect_back("admin.list_tags")
    if Tag.query.filter_by(name=name).first() is not None:
        flash("同じ名前のタグが既にあります。", "error")
        return _redirect_back("admin.list_tags")
    db.session.add(Tag(name=name))
    db.session.commit()
    flash("タグを追加しました。", "success")
    return _redirect_back("admin.list_tags")


@admin_bp.route("/admin/tags/<int:tag_id>/delete", methods=["POST"])
def delete_tag(tag_id: int):
    """未使用のタグを削除する。"""
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        abort(404)
    if tag.artworks:
        flash("使用中のタグは削除できません。", "error")
        return _redirect_back("admin.list_tags")
    db.session.delete(tag)
    db.session.commit()
    flash("タグを削除しました。", "success")
    return _redirect_back("admin.list_tags")


@admin_bp.route("/admin/notifications/<int:notification_id>/revoke", methods=["POST"])
def revoke_notification(notification_id: int):
    """誤生成の通知を失効する（理由必須）。"""
    notification = db.session.get(Notification, notification_id)
    if notification is None:
        abort(404)
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("理由を入力してください。", "error")
        return _redirect_back("admin.list_notifications")
    notification.revoked_at = utcnow()
    notification.revoked_by_id = current_user.id
    notification.revoke_reason = reason
    db.session.commit()
    flash("通知を失効しました。", "success")
    return _redirect_back("admin.list_notifications")


@admin_bp.route("/admin/points/adjust", methods=["POST"])
def adjust_points():
    """ポイント残高を手動調整する（理由必須・再送しても二重反映しない）。"""
    try:
        user_id = int(request.form.get("user_id", ""))
    except ValueError:
        flash("ユーザーを選択してください。", "error")
        return _redirect_back("admin.list_points")
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        flash("調整額を入力してください。", "error")
        return _redirect_back("admin.list_points")
    reason = (request.form.get("reason") or "").strip()
    ticket = (request.form.get("ticket") or "").strip()
    if not reason:
        flash("理由を入力してください。", "error")
        return _redirect_back("admin.list_points")
    if not ticket:
        flash("整理番号（ticket）を入力してください。", "error")
        return _redirect_back("admin.list_points")

    limit = int(current_app.config.get("ADMIN_ADJUST_MAX_POINTS", 100000))
    if abs(amount) > limit:
        flash(f"1 回の調整上限は {limit}pt です。", "error")
        return _redirect_back("admin.list_points")

    try:
        adjust_balance(
            user,
            amount,
            "admin_adjust",
            reference_key=f"admin_adjust:{user.id}:{ticket}",
            reason=reason,
        )
        db.session.commit()
        flash("残高を調整しました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return _redirect_back("admin.list_points")
```

`current_app` を使うため、import 行に `from flask import abort, current_app, flash, redirect, render_template, request, url_for` を含める。

- [ ] **Step 5: テンプレートを作成する**

`app/templates/admin/*.html` はいずれも既存の `app/templates/base.html` を継承する
（別基底を足さず、ベース側のナビゲーションとエラーページを共通で使い回す）。

`app/templates/base.html` のログイン後のナビ（`base.html:16-25`）に、
管理者にだけ表示する導線を 1 つ追加する。

```html
{% if current_user.is_authenticated and current_user.is_admin %}
<a class="nav-link" href="{{ url_for('admin.index') }}">管理画面</a>
{% endif %}
```

管理画面の各テンプレートは `base.html` を継承し、管理画面用のタブナビを
`{% block content %}` の先頭に置く。

```html
{% extends "base.html" %}
{% block content %}
<nav class="admin-tabs">
  <a href="{{ url_for('admin.index') }}">概要</a>
  <a href="{{ url_for('admin.list_artworks') }}">作品</a>
  <a href="{{ url_for('admin.list_auctions') }}">競売</a>
  <a href="{{ url_for('admin.list_users') }}">アカウント</a>
  <a href="{{ url_for('admin.list_tags') }}">タグ</a>
  <a href="{{ url_for('admin.list_notifications') }}">通知</a>
  <a href="{{ url_for('admin.list_points') }}">ポイント</a>
</nav>
<h1>管理画面</h1>
<!-- タブごとの一覧とフォーム -->
{% endblock %}
```

`app/templates/admin/index.html` は件数サマリのみ。`artworks.html` /
`auctions.html` / `users.html` / `tags.html` / `notifications.html` /
`points.html` は該当データの一覧と操作フォームを置く。フォームの action は
Task 7 の Interfaces に書いた URL をそのまま使い、CSRF は `{{ csrf_token() }}` を
必ず入れる。理由必須のフォーム（非公開化・取消・公開復帰・通知失効・
ポイント調整）は `reason` 欄を空にせず渡せないようにする（サーバー側でも
検証する）。

一般ユーザーには管理画面への導線を出さない（`base.html` の条件分岐で担保する）。

- [ ] **Step 6: Blueprint を登録する**

`app/__init__.py` の `_register_blueprints` に次を追加する:

```python
    from app.admin.routes import admin_bp

    app.register_blueprint(admin_bp)
```

- [ ] **Step 7: `promote-admin` コマンドを追加する**

`app/commands.py` に次を追加する:

```python
@app.cli.command("promote-admin")
@click.argument("username")
@with_appcontext
def promote_admin(username: str) -> None:
    """ユーザーを管理者にする。"""
    from app.models.user import User

    user = User.query.filter_by(username=username).first()
    if user is None:
        click.echo(f"ユーザー {username} が見つかりません。")
        return
    user.role = "admin"
    db.session.commit()
    click.echo(f"{username} を管理者にしてしました。")


```

- [ ] **Step 8: 失効した通知を一般の一覧から隠す**

通知の取得は `app/services/notification_service.py` に集約されている（ルートは
サービス層を呼ぶ）。失効の判定はサービス層で入れ、ルートは其为を扱わない。

`app/services/notification_service.py` の 2 関数を次のように置き換える。

```python
def list_user_notifications(user, limit: int = 100) -> list[Notification]:
    """本人の通知を新しい順に取得する。失効済みの通知は含めない。"""
    return (
        Notification.query.filter_by(user_id=user.id)
        .filter(Notification.revoked_at.is_(None))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def count_unread(user) -> int:
    """未読通知の件数を返す。失効済みの通知は数えない。"""
    return (
        Notification.query.filter_by(user_id=user.id, is_read=False)
        .filter(Notification.revoked_at.is_(None))
        .count()
    )
```

`app/notifications/routes.py` の `mark_notification_read` では、所有者の確認に加えて
失効済みでないことも確認し、失効済みなら flash で知らせる。

```python
@notifications_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    """通知を既読にする。"""
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        abort(404)
    if notification.revoked_at is not None:
        flash("この通知は失効されています。", "error")
        return redirect(url_for("notifications.show_notifications"))
    notification.is_read = True
    db.session.commit()
    return redirect(url_for("notifications.show_notifications"))
```
- [ ] **Step 9: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_admin.py -q
```
Expected: 7 passed

- [ ] **Step 10: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): 管理画面（作品・競売・アカウント・タグ・通知・ポイント）を追加"
```

---

### Task 8: 一般画面への取消・再出品の接続

**Files:**
- Modify: `app/auctions/routes.py`
- Modify: `app/artworks/routes.py`
- Modify: `app/account/routes.py`
- Modify: `app/main/routes.py`
- Modify: `app/services/tag_service.py`
- Modify: `app/templates/auctions/detail.html`
- Modify: `app/templates/account/index.html`
- Modify: `app/templates/main/home.html`
- Modify: `app/templates/search/index.html`
- Test: `tests/test_cancel_relist_ui.py`

**Interfaces:**
- Consumes: Task 5 の `cancellation_service`、Task 6 の `event_service`
- Produces:
  - `POST /auctions/<int:auction_id>/cancel`（本人取消）
  - `POST /artworks/<int:artwork_id>/relist`（再出品）
  - `GET /auctions/<int:auction_id>/history`（過去競売の取引履歴）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_cancel_relist_ui.py` を作成:

```python
"""一般画面から取消・再出品できることの確認。"""

from app.extensions import db


def test_seller_can_cancel_from_detail_page(
    client, make_user, make_auction, login
):
    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    login("seller")
    response = client.post(
        f"/auctions/{auction.id}/cancel",
        data={},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert auction.status == "cancelled"


def test_normal_user_cannot_cancel_others_auction(
    client, make_user, make_auction, login
):
    from app.services.errors import PermissionDeniedError

    seller = make_user("seller", points=0)
    alice = make_user("alice", points=1000)
    auction = make_auction(seller, start_price=100)
    login("alice")
    response = client.post(
        f"/auctions/{auction.id}/cancel",
        data={},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert auction.status == "active"


def test_artist_can_relist_from_account_page(
    client, make_user, make_auction, login
):
    from app.services import cancellation_service

    seller = make_user("seller", points=0)
    auction = make_auction(seller, start_price=100)
    cancellation_service.cancel_auction_by_seller(seller, auction)
    db.session.commit()

    login("seller")
    response = client.post(
        f"/artworks/{auction.artwork_id}/relist",
        data={"start_price": "300", "duration_minutes": "10"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert auction.artwork.auctions.count() == 2


def test_hidden_artwork_is_not_listed_on_home(client, make_user, make_artwork):
    from app.services import cancellation_service

    admin = make_user("admin", points=0)
    admin.role = "admin"
    db.session.commit()
    seller = make_user("seller", points=0)
    artwork = make_artwork(seller, status="listed")
    cancellation_service.hide_artwork(admin, artwork, "運用方針")
    db.session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert artwork.title.encode("utf-8") not in response.data
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_cancel_relist_ui.py -q
```
Expected: FAIL（404 / 状態が変化しない）

- [ ] **Step 3: 取消ルートを追加する**

`app/auctions/routes.py` に次を追加する:

```python
@auctions_bp.route("/auctions/<int:auction_id>/cancel", methods=["POST"])
@login_required
def cancel_auction(auction_id: int):
    """出品者本人による取消。"""
    from app.services import cancellation_service

    auction = auction_service.get_auction(auction_id)
    try:
        cancellation_service.cancel_auction_by_seller(current_user, auction)
        db.session.commit()
        flash("出品を取り消しました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return redirect(url_for("auctions.show_auction_detail", auction_id=auction_id))
```

- [ ] **Step 4: 再出品ルートを追加する**

`app/artworks/routes.py` に次を追加する:

```python
@artworks_bp.route("/artworks/<int:artwork_id>/relist", methods=["POST"])
@login_required
def relist_artwork(artwork_id: int):
    """取消済み・未落札終了の作品から新しい競売を作る。"""
    from app.services import cancellation_service

    artwork = db.session.get(Artwork, artwork_id)
    if artwork is None:
        abort(404)
    try:
        cancellation_service.create_relisted_auction(
            current_user,
            artwork,
            request.form.get("start_price", 0),
            request.form.get("duration_minutes", 10),
        )
        db.session.commit()
        flash("再出品しました。", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(error.message, "error")
    return redirect(url_for("account.show_account"))
```

- [ ] **Step 5: 公開状態の一覧と非公開作品の除外を 4 箇所で揃える**

公開状態は `("listed", "sold")` のハードコードが 4 箇所に散らばっている。取消済み
（`cancelled`）は下書きへ戻さず公開履歴として残すので集合に含め、非公開
（`hidden`）は一般閲覧から除外する。4 箇所すべてを同じ定義に揃える。

1) `app/services/tag_service.py` の定数を拡張する。

```python
PUBLIC_STATUSES = ("listed", "sold", "cancelled")
```

2) `app/main/routes.py` の `home`（`main/routes.py:21` 付近）の作品取得条件。

```python
Artwork.query.filter(Artwork.status.in_(PUBLIC_STATUSES))
```

3) `app/search/routes.py` の検索条件（`search/routes.py:33` 付近）も同じ集合を使う。

```python
Artwork.status.in_(PUBLIC_STATUSES)
```

4) `app/templates/account/index.html` では、非公開作品も作者本人には見えるように
   する（管理者は全件）。`app/services/artwork_service.py` の
   `list_user_listings` が `("listed", "sold")` で対象の作品 を絞っている場合は
   `cancelled` も含める。

加えて、非公開作品（`status == hidden`）は一般閲覧に一切出さない。
`Artwork.is_public`（`status != DRAFT`）は作品単体对自己的公開判定として残し、
一覧側の除外は上記 4 箇所で担保する。
- [ ] **Step 6: テンプレートに導線を追加する**

- `app/templates/auctions/detail.html`: 出品者本人かつ入札なし・開催中なら「出品を取り消す」フォームを出す。
- `app/templates/account/index.html`: 作品一覧に「再出品」フォーム（開始価格・開催時間）を出す。
- `app/templates/main/home.html`: 開催中の競売一覧は `active_auction` を基準に組み立てる。

- [ ] **Step 7: 取引履歴画面を追加する**

`app/auctions/routes.py` に過去競売の取引履歴画面を追加する（設計書 §8 の `/auctions/<id>/history`）:

```python
@auctions_bp.route("/auctions/<int:auction_id>/history")
def show_auction_history(auction_id: int):
    """同じ作品の過去の競売と入札履歴を表示する。"""
    from app.models.auction import Auction

    auction = auction_service.get_auction(auction_id)
    history = (
        Auction.query.filter_by(artwork_id=auction.artwork_id)
        .order_by(Auction.id.desc())
        .all()
    )
    return render_template(
        "auctions/history.html", auction=auction, history=history
    )
```

`app/templates/auctions/history.html` を新規作成し、所属する作品・競売番号・状態・現在価格・終了時刻・入札件数と入札履歴（入札者・金額・時刻）を一覧表示する。覧ーは公開可とし、非公開作品（`status == hidden`）は作者・落札者・管理者にだけ表示する。

- [ ] **Step 8: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_cancel_relist_ui.py -q
```
Expected: 4 passed

- [ ] **Step 9: 全テストを通す**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 10: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "feat(xhigh): 一般画面から出品取消と再出品を実行できるようにする"
```

---

### Task 9: CSS の書き直し

同じ「製図図面の落札所」テーマでも、token 名・クラス命名・セクション構成は high 版と別にし、xhigh として独立した画面にする。

**Files:**
- Rewrite: `app/static/css/style.css`
- Modify: `app/templates/base.html`
- Modify: `app/templates/admin/*.html`
- Test: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `app/static/js/canvas.js` / `detail.js` が参照する DOM id（`canvas` `timer` `save-form` `pen-type` `pen-color` `pen-size` `btn-undo` `btn-redo` `btn-clear` `btn-add-layer` `btn-delete-layer` `btn-layer-up` `btn-layer-down` `layer-select` `layer-visible` `layer-opacity` `btn-finish` `status` / `auction-timer` `bid-form` `expected-price` `bid-confirmed` `current-price` `auto-bid-form` `auto-bid-max`）と `data-*` 属性（`data-deadline` `data-grace-seconds` `data-listing-url` `data-end-time`）
- Produces: 画面用のクラス命名。JS 側の DOM 契約は変更しない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_ui_contract.py` を作成:

```python
"""CSS 書き直し後も JS が必要とする DOM 契約が変わっていないことの確認。"""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_canvas_js_dom_contract_is_intact():
    source = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
    ids = set(re.findall(r"getElementById\('([^']+)'\)", source))
    required = {
        "canvas",
        "timer",
        "save-form",
        "pen-type",
        "pen-color",
        "pen-size",
        "btn-undo",
        "btn-redo",
        "btn-clear",
        "btn-add-layer",
        "btn-delete-layer",
        "btn-layer-up",
        "btn-layer-down",
        "layer-select",
        "layer-visible",
        "layer-opacity",
        "btn-finish",
        "status",
    }
    assert required <= ids


def test_detail_js_dom_contract_is_intact():
    source = (STATIC / "js" / "detail.js").read_text(encoding="utf-8")
    ids = set(re.findall(r"getElementById\('([^']+)'\)", source))
    required = {
        "auction-timer",
        "bid-form",
        "expected-price",
        "bid-confirmed",
        "current-price",
        "auto-bid-form",
        "auto-bid-max",
    }
    assert required <= ids


def test_css_uses_new_token_names():
    source = (STATIC / "css" / "style.css").read_text(encoding="utf-8")
    assert "--sheet-ink" in source
    assert "--sheet-rule" in source
    assert "--sheet-field" in source
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_ui_contract.py -q
```
Expected: 3 passed だが `test_css_uses_new_token_names` が FAIL（token 名が未変更）

- [ ] **Step 3: CSS を書き直す**

`app/static/css/style.css` を新規に書き直す。9 節構成（トークン → 基盤 → 題字欄 → 用紙片 → 部品 → フォーム → 表一覧 → 描画台 → レスポンシブ）を維持しつつ、token 名を次のように変更する。

| high 版 | xhigh 版 |
| --- | --- |
| `--text` | `--sheet-ink` |
| `--bg` | `--sheet-field` |
| `--line` | `--sheet-rule` |
| `--muted` | `--sheet-pencil` |
| `--accent` | `--sheet-amber` |
| `--danger` | `--sheet-vermilion` |

設計上の決定は次で固定する。

- 角丸は 2px まで。罫線はヘアライン 1px と太罫 2px の 2 種。
- 影はぼかさない。`box-shadow: 3px 3px 0` のような硬い影を使う。
- 状態色は意味に固定する。開催中＝琥珀、落札＝朱、終了＝灰、取消＝灰青、非公開＝灰青の濃色。
- 見出し＝日文明朝、本文＝ゴシック、数値・ID・価格＝等幅。外部フォント・CDN に依存しない。
- `:focus-visible` に琥珀の 2px 枠、`prefers-reduced-motion` で脈動を停止する。
- レスポンシブは 1024px / 640px の 2 段。

- [ ] **Step 4: テンプレートのクラス名を CSS に合わせる**

`app/templates/base.html` と `app/templates/admin/*.html` のクラス名を書き直した CSS の命名に合わせる。JS の参照する id は変えない。

- [ ] **Step 5: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_ui_contract.py -q
```
Expected: 3 passed

- [ ] **Step 6: 全テストを通す**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 7: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh
git commit -m "refactor(xhigh): CSS を書き直し、token 名と構成を high 版と分離"
```

---

### Task 10: CI・README・通し確認

**Files:**
- Modify: `.github/workflows/ci.yml`（job を追加。既存 job は変更しない）
- Modify: `HEW2026_v1.0_MiniMaxCode_xhigh/README.md`
- Modify: `HEW2026_v1.0_MiniMaxCode_xhigh/requirements.txt`
- Modify: `HEW2026_v1.0_MiniMaxCode_xhigh/tools/smoke_check.py`
- Test: `tests/test_smoke_contract.py`

**Interfaces:**
- Consumes: Task 1〜9 の成果物
- Produces: CI の `xhigh` job、README の手順書、スモークチェック

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_smoke_contract.py` を作成:

```python
"""README と CLI コマンドの整合確認。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_readme_mentions_mysql_databases():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "hew_xhigh" in readme
    assert "hew_xhigh_test" in readme


def test_cli_has_required_commands(app):
    from app.commands import register_commands

    names = set(app.cli.commands.keys())
    assert {
        "init-db",
        "seed-tags",
        "seed-users",
        "seed-demo",
        "close-auctions",
        "promote-admin",
    } <= names
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests/test_smoke_contract.py -q
```
Expected: `test_readme_mentions_mysql_databases` が FAIL（README が旧内容）

- [ ] **Step 3: CI に xhigh の job を追加する**

`.github/workflows/ci.yml` の `jobs:` に次の job を**追加**する（既存の `test` と `security` job は変更しない）:

```yaml
  xhigh:
    name: xhigh (MySQL)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: ci-root-password
          MYSQL_DATABASE: hew_xhigh_test
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h 127.0.0.1 -pci-root-password"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=10
    env:
      SECRET_KEY: ci-dummy-secret-key
      DATABASE_URL: mysql+pymysql://root:ci-root-password@127.0.0.1:3306/hew_xhigh?charset=utf8mb4
      TEST_DATABASE_URL: mysql+pymysql://root:ci-root-password@127.0.0.1:3306/hew_xhigh_test?charset=utf8mb4
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: HEW2026_v1.0_MiniMaxCode_xhigh/requirements.txt

      - name: 作業ディレクトリの確認
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: |
          echo "pwd = $(pwd)"
          ls

      - name: Install dependencies
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff pytest-cov

      - name: "Ruff (blocking: syntax / undefined name)"
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: ruff check --select E9,F63,F7,F82 .

      - name: Ruff (report only)
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: ruff check . --exit-zero

      - name: Pytest (MySQL)
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: pytest tests -q --cov=app --cov-report=term-missing

      - name: Bandit (static security scan)
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: bandit -r app -x app/static,app/__pycache__ -ll

      - name: pip-audit (known CVEs in dependencies)
        working-directory: HEW2026_v1.0_MiniMaxCode_xhigh
        run: pip-audit -r requirements.txt
        continue-on-error: true
```

- [ ] **Step 4: README を書き直す**

`HEW2026_v1.0_MiniMaxCode_xhigh/README.md` を、次を必ず含む内容に書き直す。

- 対象範囲が「Ver0.5 + 出品取消・再出品 + 管理画面」であること
- DB が **MySQL が既定**であること。開発庫 `hew_xhigh`、テスト庫 `hew_xhigh_test`
- 起動手順（venv 作成 → pip install → `flask init-db` → `seed-tags` → `seed-users` → `seed-demo` → `python main.py`）
- `flask promote-admin <username>` で管理者を作ること
- `flask close-auctions` を Windows タスクスケジューラで定期実行すること
- テスト手順（`pytest tests -q`）と、テストが MySQL を使うこと
- 設計からの意図的な変更（`active_slot` / `held_points` / `reference_key`、レイヤー ZIP はサーバー側生成、非公開作品、管理者画面）
- 未実施・未決事項（ライブ配信・コメント・実課金・負荷試験）

- [ ] **Step 5: requirements.txt を確認する**

`requirements.txt` に `pymysql` と `pillow` が含まれることを確認する。無い場合は次を追加する:

```
pymysql==1.1.1
pillow==11.0.0
```

（バージョンは `pip freeze` の実測値に合わせる）

- [ ] **Step 6: スモークチェックを MySQL 前提に直す**

`tools/smoke_check.py` を確認し、SQLite 固定の処理があれば `DATABASE_URL` / `TEST_DATABASE_URL` の読み取りに置き換える。実行して通ることを確認する。

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python tools/smoke_check.py
```
Expected: 正常終了（異常があれば修正する）

- [ ] **Step 7: テストを実行して通ることを確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 8: 開発サーバーで通し確認する**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
$env:FLASK_APP = 'main.py'
python main.py
```
別ターミナルで `http://127.0.0.1:5000/` を開き、登録 → 描画 → 保存 → 出品 → 入札 → 取消 → 再出品 → 管理画面まで一通り触る。

- [ ] **Step 9: 最終確認**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git status --porcelain -- HEW2026_v1.0_MiniMaxCode_high HEW2026_v1.0_TraeWorkCN_高
```
Expected: 出力なし（既存実装へ変更を加えていないこと）

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026\HEW2026_v1.0_MiniMaxCode_xhigh'
python -m pytest tests -q
```
Expected: 全 PASS

- [ ] **Step 10: コミットする**

```powershell
cd 'C:\Users\12764\Desktop\学校开发\HEW2026'
git add HEW2026_v1.0_MiniMaxCode_xhigh .github/workflows/ci.yml
git commit -m "ci(xhigh): MySQL サービスコンテナでの job を追加し README を更新"
```

---

## Self-Review

**Spec coverage**

| 設計書の項目 | 担当タスク |
| --- | --- |
| §3.1 Ver0.5 全機能 | Task 1（基座）で既存実装を継承、Task 4 で入札を刷新 |
| §3.1 出品取消・再出品 | Task 5, Task 8 |
| §3.1 管理画面 | Task 7 |
| §3.1 イベント終了時刻 | Task 6 |
| §3.1 競売終了の定期実行 | Task 1（`close-auctions` を継承）、Task 10 |
| §5 データモデル刷新 | Task 2 |
| §5.3 `active_slot` による同時開催の保証 | Task 2 |
| §5.4 `held_points` による未返還額の管理 | Task 2, Task 4 |
| §6 取消・再出品の業務ルール | Task 5 |
| §6.5 ロック順序 | Task 4（auctions → users）、Task 5（auctions → users） |
| §7 管理画面 | Task 7 |
| §8 画面一覧 | Task 8（`/auctions/<id>/history` は Task 8 の Produces に含める） |
| §9 ビジュアル | Task 9 |
| §10 テスト | 各タスクのテストステップ + Task 10 |
| §11 運用（MySQL 既定・専用 DB・CI） | Task 1, Task 10 |
| §12 完了条件 | Task 10 Step 9 |

**Gap 指摘と解消**

- 設計書 §8 の `GET /auctions/<id>/history` は Task 8 Step 7 に実装手順を追加済み。
- 設計書 §7.3 の通知失効は Task 7 Step 8 で一般の一覧から除外する実装を追加済み。
- 残る未実施は設計書 3.2 に従い意図的にスコープ外（ライブ配信・コメント・実課金・NFT・吊り上げ bot）。

**Placeholder scan**

「TBD」「TODO」「後で決める類」の記述なし。すべてのコードブロックに実物が入っている。Task 5 Step 3 の通知タイトルと `_record` の引数順は、high 版のコード盘点（2026-11-02）で確認した実相に合わせて計画段階で修正済み。

**Type consistency**

- `adjust_balance(user, amount, transaction_type, related_auction_id=None, related_bid_id=None, reference_key=None, reason=None)` — Task 3 で定義し、Task 4・Task 5・Task 7 から同じシグネチャで呼ぶ。
- `place_bid(auction_id, bidder, amount, is_auto=False, expected_price=None) -> Bid` — Task 4 で維持。
- `cancel_auction_by_seller(user, auction)` / `cancel_auction_by_admin(user, auction, reason)` / `create_relisted_auction(user, artwork, start_price, duration_minutes)` / `hide_artwork(user, artwork, reason)` / `restore_artwork(user, artwork, reason)` — Task 5 で定義し、Task 7・Task 8 から同じ名前で呼ぶ。
- `ensure_event_open(operation: str)` / `is_event_ended(now=None) -> bool` — Task 6 で定義。
- `Auction.active_slot` / `Bid.held_points` / `WalletTransaction.reference_key` / `Notification.revoked_at` — Task 2 で定義し、Task 3・Task 4・Task 5・Task 7 が参照する。
