"""アプリケーション設定。

秘密情報・接続情報は .env から読み込み、ソースコードへ直接書かない。
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _as_bool(value, default=False):
    """環境変数の文字列を真偽値へ変換する。"""
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value, default):
    """環境変数の文字列を整数へ変換する。変換できない場合は既定値。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_utc(value):
    """ISO8601 文字列を naive UTC の datetime へ変換する。"""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _upload_root(value):
    """保存先を絶対パスへ解決する。"""
    if not value:
        return os.path.join(BASE_DIR, "instance", "uploads")
    if os.path.isabs(value):
        return value
    return os.path.join(BASE_DIR, value)


class Config:
    """共通設定。環境変数で上書きできる。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "hew.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_ENABLED = True

    UPLOAD_ROOT = _upload_root(os.environ.get("UPLOAD_ROOT"))

    # 画像・レイヤーの上限（仮上限は実機検証する）
    MAX_COMPOSITE_PNG_BYTES = _as_int(
        os.environ.get("MAX_COMPOSITE_PNG_BYTES"), 5 * 1024 * 1024
    )
    MAX_LAYER_PNG_BYTES = _as_int(
        os.environ.get("MAX_LAYER_PNG_BYTES"), 5 * 1024 * 1024
    )
    MAX_LAYER_TOTAL_BYTES = _as_int(
        os.environ.get("MAX_LAYER_TOTAL_BYTES"), 50 * 1024 * 1024
    )
    MAX_LAYERS = 10
    CANVAS_SIZE = 1024
    SAVE_GRACE_SECONDS = 60

    # 描画の制限時間（秒）と競売の開催時間（分）
    DRAWING_DURATIONS = (10, 30, 60, 300)
    AUCTION_DURATIONS = (5, 10, 15, 20)
    DEFAULT_AUCTION_MINUTES = 10

    # 1 日開催の運用（UTC の naive datetime）
    EVENT_ENDS_AT = _as_utc(os.environ.get("EVENT_ENDS_AT"))
    APP_STOPS_AT = _as_utc(os.environ.get("APP_STOPS_AT"))

    # ボーナス（仮データ）
    BONUS_REGISTRATION_POINTS = _as_int(
        os.environ.get("BONUS_REGISTRATION_POINTS"), 1000
    )
    BONUS_FIRST_LISTING_POINTS = _as_int(
        os.environ.get("BONUS_FIRST_LISTING_POINTS"), 300
    )
    BONUS_DAILY_SAVE_POINTS = _as_int(
        os.environ.get("BONUS_DAILY_SAVE_POINTS"), 100
    )

    # 自動入札の 1 回の処理で許す競り上げ回数
    MAX_AUTO_BID_ROUNDS = 50
    AUTO_BID_STOP_NOTICE = True

    # テスト用（conftest から上書きする）
    TESTING = False
    SEED_DEMO = False


class TestConfig(Config):
    """自動テスト用設定。"""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    UPLOAD_ROOT = os.path.join(BASE_DIR, "instance", "uploads-test")
