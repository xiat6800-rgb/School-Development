"""環境別設定。秘密情報・接続情報は .env からのみ読み込む（要件定義書 7.3）。"""
import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

if os.environ.get("SECRET_KEY"):
    _SECRET_KEY = os.environ["SECRET_KEY"]
elif os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY が未設定です。.env に設定してください。")
else:
    _SECRET_KEY = secrets.token_hex(32)


def _env_int(name, default):
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


def _parse_event_end():
    raw = (os.environ.get("EVENT_END_UTC") or "").strip()
    if not raw:
        return None
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class Config:
    SECRET_KEY = _SECRET_KEY
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@127.0.0.1:3306/hew?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    WTF_CSRF_TIME_LIMIT = None

    # 合成PNG・レイヤーZIP送信の上限（ZIP 50MiB + マージン）
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "uploads", "artworks")

    # 描画・出品の選択値（要件定義書 5.2・5.3）
    ALLOWED_DRAWING_DURATIONS = (10, 30, 60, 300)
    ALLOWED_AUCTION_MINUTES = (5, 10, 15, 20)
    DEFAULT_AUCTION_MINUTES = 10
    CANVAS_SIZE = 1024
    MAX_LAYERS = 10
    MAX_COMPOSITE_PNG_BYTES = 5 * 1024 * 1024
    MAX_LAYER_PNG_BYTES = 5 * 1024 * 1024
    MAX_LAYER_TOTAL_BYTES = 50 * 1024 * 1024
    SAVE_GRACE_SECONDS = 60
    MIN_AUCTION_MARGIN_SECONDS = 300

    # ボーナス仮データ（仕様決定事項 5章。将来再検討）
    BONUS_SIGNUP_POINTS = _env_int("BONUS_SIGNUP_POINTS", 1000)
    BONUS_FIRST_LISTING_POINTS = _env_int("BONUS_FIRST_LISTING_POINTS", 300)
    BONUS_DRAW_SAVE_POINTS = _env_int("BONUS_DRAW_SAVE_POINTS", 100)

    # イベント終了日時（UTC）。None なら期間制限なし
    EVENT_END_UTC = _parse_event_end()

    JST_OFFSET_HOURS = 9


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "test_uploads")


_configs = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": Config,
}


def get_config(name):
    return _configs.get(name, Config)
