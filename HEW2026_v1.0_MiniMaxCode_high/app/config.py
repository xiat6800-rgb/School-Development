"""環境別設定と ``.env`` の読み込み。

仕様決定事項（2026/10/26）に従い、秘密情報と接続情報は
すべて環境変数で管理する。ソースには直接書かない。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """``.env`` を環境変数へ読み込む（python-dotenv 非依存の簡易実装）。

    既に設定されている環境変数を上書きしない。
    """
    env_path = path or (BASE_DIR / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


load_dotenv()


def _env_int(key: str, default: int) -> int:
    """環境変数を整数として読む。値が不正なら既定値へ戻す。"""
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_datetime(key: str) -> datetime | None:
    """ISO 形式（タイムゾーン付き推奨）の環境変数を UTC で読む。"""
    raw = os.environ.get(key)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class Config:
    """既定設定。環境変数で上書きする。"""

    # --- 基本 ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    TESTING = False

    # --- データベース ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///hew_dev.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQL_ECHO = _env_bool("SQL_ECHO", False)

    # --- フォーム・セキュリティ ---
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7

    # --- 保存先・容量制限（仕様決定事項 2・3章の仮上限） ---
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "app/uploads")
    MAX_IMAGE_BYTES = _env_int("MAX_IMAGE_BYTES", 5 * 1024 * 1024)
    MAX_LAYER_BYTES = _env_int("MAX_LAYER_BYTES", 5 * 1024 * 1024)
    MAX_LAYER_TOTAL_BYTES = _env_int("MAX_LAYER_TOTAL_BYTES", 50 * 1024 * 1024)
    MAX_LAYERS = _env_int("MAX_LAYERS", 10)
    CANVAS_SIZE = _env_int("CANVAS_SIZE", 1024)
    SAVE_GRACE_SECONDS = _env_int("SAVE_GRACE_SECONDS", 60)

    # --- 描画・オークション ---
    DRAW_DURATION_SECONDS = (10, 30, 60, 300)
    AUCTION_DURATION_MINUTES = (5, 10, 15, 20)
    DEFAULT_AUCTION_MINUTES = _env_int("DEFAULT_AUCTION_MINUTES", 10)
    BID_MIN_INCREMENT = _env_int("BID_MIN_INCREMENT", 1)

    # --- 1日開催のイベント終了時刻（未設定なら制限しない） ---
    EVENT_END_AT = _env_datetime("EVENT_END_AT")

    # --- ボーナス（仮データ。将来再検討） ---
    BONUS_SIGNUP_POINTS = _env_int("BONUS_SIGNUP_POINTS", 1000)
    BONUS_FIRST_LISTING_POINTS = _env_int("BONUS_FIRST_LISTING_POINTS", 300)
    BONUS_DRAW_POINTS = _env_int("BONUS_DRAW_POINTS", 100)


class TestingConfig(Config):
    """テスト用設定。

    DB は既定で一時 SQLite を使う。``TEST_DATABASE_URL`` を
    指定すれば専用の MariaDB / MySQL を使える。
    """

    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    UPLOAD_FOLDER = "app/uploads/test"
    EVENT_END_AT = None


def get_config_by_name(name: str | None) -> type[Config]:
    """名前から設定クラスを返す。"""
    if name == "testing":
        return TestingConfig
    return Config


def upload_root(upload_folder: str) -> Path:
    """アップロード実体の保存先ディレクトリを返す（相対パスは BASE_DIR 基準）。"""
    root = Path(upload_folder)
    if not root.is_absolute():
        root = BASE_DIR / root
    return root
